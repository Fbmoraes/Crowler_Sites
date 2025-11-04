"""
EXTRAÇÃO HÍBRIDA ULTRA-RÁPIDA - MATCON CASA
Estratégia: JSON endpoints > JSON-LD > DOM (nessa ordem)
Meta: 800 produtos em ~3-5 minutos com 100% de qualidade

ARQUITETURA OTIMIZADA:
- Página única compartilhada (estável)
- User-Agent rotation (simples e eficaz)
- Timeouts otimizados (1.5s vs 3.5s)
"""

import asyncio
import json
import random
import re
import time
from datetime import datetime
from typing import Dict, List, Optional, Set
import httpx
from playwright.async_api import async_playwright, Page, Response
from bs4 import BeautifulSoup
import extruct
from w3lib.html import get_base_url


# ============================================================================
# CONFIGURAÇÕES
# ============================================================================
RATE_LIMIT_RPS = 6   # Requisições por segundo (conservador)
MAX_CONCURRENT = 8   # Requisições HTTP simultâneas (conservador)
TIMEOUT_HTTP = 12  # Timeout para requisições HTTP
TIMEOUT_BROWSER = 15  # Timeout para browser (fallback)

# CEP fixo para consistência de preços
CEP_FIXO = "01310-100"  # São Paulo - SP

# Lista de User-Agents para rotação (simples mas eficaz)
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]


# ============================================================================
# FUNÇÃO AUXILIAR PARA LER URLS
# ============================================================================
def ler_urls(arquivo: str = "urls_matcon_100.txt") -> List[str]:
    """Lê URLs de um arquivo de texto."""
    try:
        with open(arquivo, 'r', encoding='utf-8') as f:
            return [linha.strip() for linha in f if linha.strip()]
    except FileNotFoundError:
        print(f"❌ Arquivo de URLs '{arquivo}' não encontrado.")
        return []


# ============================================================================
# TOKEN BUCKET RATE LIMITER
# ============================================================================
class TokenBucket:
    """Rate limiter com token bucket"""
    
    def __init__(self, rate: float):
        self.rate = rate  # tokens por segundo
        self.tokens = rate
        self.last_update = time.time()
        self.lock = asyncio.Lock()
    
    async def acquire(self):
        """Aguarda até ter token disponível"""
        async with self.lock:
            now = time.time()
            elapsed = now - self.last_update
            self.tokens = min(self.rate, self.tokens + elapsed * self.rate)
            self.last_update = now
            
            if self.tokens < 1:
                wait_time = (1 - self.tokens) / self.rate
                await asyncio.sleep(wait_time)
                self.tokens = 0
            else:
                self.tokens -= 1


# ============================================================================
# ETAPA 1: SNIFFAR ENDPOINTS JSON
# ============================================================================
async def descobrir_endpoints(url_exemplo: str) -> Set[str]:
    """
    Abre 1 página e captura todos os endpoints JSON que o Next.js usa
    """
    print("🔍 Descobrindo endpoints JSON...")
    json_endpoints = set()
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        
        async def handle_response(response: Response):
            try:
                content_type = response.headers.get("content-type", "")
                if "application/json" in content_type:
                    url = response.url
                    # Filtrar endpoints relevantes
                    if re.search(r'(api|search|product|catalog|graphql|vtex|algolia)', url, re.I):
                        json_endpoints.add(url)
                        print(f"   📡 Endpoint encontrado: {url[:80]}...")
            except:
                pass
        
        page.on("response", handle_response)
        
        try:
            await page.goto(url_exemplo, wait_until="domcontentloaded", timeout=15000)
            # Aguardar produtos carregarem
            await page.wait_for_selector("h1", timeout=10000)
            await asyncio.sleep(2)  # Aguardar chamadas assíncronas
        except Exception as e:
            print(f"   ⚠️  Erro ao carregar: {e}")
        
        await browser.close()
    
    print(f"✅ {len(json_endpoints)} endpoints descobertos")
    return json_endpoints


# ============================================================================
# ETAPA 2: EXTRAIR VIA JSON-LD (INSTANTÂNEO)
# ============================================================================
async def extrair_via_jsonld(client: httpx.AsyncClient, url: str) -> Optional[Dict]:
    """
    Tenta extrair dados via JSON-LD (schema.org Product)
    Mais rápido: ~100-200ms, sem browser
    """
    try:
        response = await client.get(url, timeout=TIMEOUT_HTTP)
        html = response.text
        
        # Usar extruct para extrair microdata estruturado
        data = extruct.extract(html, base_url=get_base_url(html, url))
        
        # Procurar por Product schema
        products = [
            item for item in data.get("json-ld", [])
            if isinstance(item.get("@type"), str) and item["@type"] == "Product"
            or isinstance(item.get("@type"), list) and "Product" in item["@type"]
        ]
        
        if products:
            produto = products[0]
            offers = produto.get("offers", {})
            
            return {
                "nome": produto.get("name"),
                "preco": offers.get("price"),
                "preco_original": offers.get("highPrice"),
                "disponivel": offers.get("availability") == "https://schema.org/InStock",
                "marca": produto.get("brand", {}).get("name") if isinstance(produto.get("brand"), dict) else None,
                "imagens": [produto.get("image")] if isinstance(produto.get("image"), str) else produto.get("image", [])[:5],
                "sku": produto.get("sku"),
                "metodo": "JSON-LD"
            }
    except:
        pass
    
    return None


# ============================================================================
# ETAPA 2.5: EXTRAIR VIA API PRODUCT/BASIC (DESCOBERTA NO DIAGNÓSTICO!)
# ============================================================================
async def extrair_via_api_product_basic(
    client: httpx.AsyncClient, 
    url: str
) -> Optional[Dict]:
    """
    Tenta usar a API /api/product/basic descoberta no diagnóstico
    Ultra rápido: ~100-300ms, sem browser!
    """
    try:
        # Extrair SKU da URL (último número antes do final)
        match = re.search(r'-(\d+)$', url)
        if not match:
            return None
        
        sku = match.group(1)
        
        # Testar API /api/product/basic (descoberta no diagnóstico)
        api_url = "https://www.matconcasa.com.br/api/product/basic"
        
        # Payload que a API espera (capturado do diagnóstico)
        payload = {
            "sku": sku,
            "storeId": 7,  # matcon_sp
        }
        
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": random.choice(USER_AGENTS),
        }
        
        response = await client.post(
            api_url,
            json=payload,
            headers=headers,
            timeout=TIMEOUT_HTTP
        )
        
        # Debug: mostrar resposta se não for 200
        if response.status_code != 200:
            print(f"   [DEBUG] API retornou {response.status_code} para SKU {sku}")
            return None
        
        if response.status_code == 200:
            data = response.json()
            
            # Adaptar estrutura da resposta
            if isinstance(data, dict):
                produto = data.get("product") or data.get("data") or data
                
                # Extrair preço
                preco = None
                preco_original = None
                
                if "price" in produto:
                    preco = str(produto["price"])
                elif "finalPrice" in produto:
                    preco = str(produto["finalPrice"])
                elif "sellingPrice" in produto:
                    preco = str(produto["sellingPrice"])
                
                if "originalPrice" in produto:
                    preco_original = str(produto["originalPrice"])
                elif "listPrice" in produto:
                    preco_original = str(produto["listPrice"])
                
                # Extrair imagens
                imagens = []
                if "images" in produto:
                    imagens = produto["images"][:5] if isinstance(produto["images"], list) else [produto["images"]]
                elif "image" in produto:
                    imagens = [produto["image"]]
                elif "mediaGallery" in produto:
                    imagens = [img.get("url") or img.get("file") for img in produto["mediaGallery"][:5]]
                
                return {
                    "nome": produto.get("name") or produto.get("title"),
                    "preco": preco,
                    "preco_original": preco_original,
                    "disponivel": produto.get("available") or produto.get("inStock") or produto.get("stockStatus") == "in_stock",
                    "marca": produto.get("brand") or produto.get("manufacturer"),
                    "imagens": imagens,
                    "sku": produto.get("sku") or sku,
                    "metodo": "API-PRODUCT-BASIC"
                }
    except Exception as e:
        # Debug: mostrar erro para ajustar
        pass
    
    return None


# ============================================================================
# ETAPA 3: EXTRAIR VIA ENDPOINT JSON DIRETO (FALLBACK)
# ============================================================================
async def extrair_via_api_json(
    client: httpx.AsyncClient, 
    url: str, 
    endpoints_conhecidos: Set[str]
) -> Optional[Dict]:
    """
    Tenta chamar API JSON diretamente (se endpoint foi descoberto)
    """
    # Extrair slug/id da URL
    match = re.search(r'/produto/([^/]+)', url)
    if not match:
        return None
    
    slug = match.group(1)
    
    # Tentar padrões comuns de API
    api_patterns = [
        f"https://www.matconcasa.com.br/api/product/{slug}",
        f"https://www.matconcasa.com.br/api/products/{slug}",
        f"https://www.matconcasa.com.br/_next/data/*/produto/{slug}.json",
    ]
    
    for api_url in api_patterns:
        try:
            response = await client.get(api_url, timeout=TIMEOUT_HTTP)
            if response.status_code == 200:
                data = response.json()
                
                # Tentar extrair dados (estrutura varia por plataforma)
                # Adaptar conforme o que foi descoberto no sniffing
                if "product" in data:
                    p = data["product"]
                    return {
                        "nome": p.get("name") or p.get("title"),
                        "preco": p.get("price") or p.get("sellingPrice"),
                        "preco_original": p.get("listPrice"),
                        "disponivel": p.get("available") or p.get("inStock"),
                        "marca": p.get("brand"),
                        "imagens": p.get("images", [])[:5],
                        "sku": p.get("sku") or p.get("id"),
                        "metodo": "API-JSON"
                    }
        except:
            continue
    
    return None


# ============================================================================
# ETAPA 4: FALLBACK VIA DOM (MAIS LENTO)
# ============================================================================
async def extrair_via_dom(page: Page, url: str) -> Dict:
    """
    Último recurso: usar Playwright com seletores específicos
    """
    try:
        # Aguardar resposta específica de preço (mais rápido que networkidle)
        response = await page.goto(url, wait_until="domcontentloaded", timeout=TIMEOUT_BROWSER * 1000)
        if response and response.status >= 400:
            return {
                "nome": None,
                "preco": None,
                "preco_original": None,
                "disponivel": None,
                "marca": None,
                "imagens": [],
                "sku": None,
                "metodo": "DOM",
                "erro": f"HTTP {response.status}"
            }
        
        # Aguardar h1 aparecer
        await page.wait_for_selector("h1", timeout=10000)
        # Reduzido: 1.5s é suficiente para hidratação na maioria dos casos
        await page.wait_for_timeout(1500)
        
        # Extrair via JavaScript (1 round-trip só)
        dados = await page.evaluate('''
            () => {
                // Nome
                const h1s = Array.from(document.querySelectorAll('h1'));
                const productH1 = h1s.find(h1 => {
                    const text = h1.textContent;
                    return /\\d/.test(text) && text.length > 20 && 
                           !text.includes('Vendido') && !text.includes('Parceria');
                });
                const nome = productH1?.textContent.trim() || document.title.split('|').pop().trim();
                
                // Preços
                const bodyText = document.body.innerText;
                const precoMatch = bodyText.match(/de\\s+R\\$\\s*([\\d.,]+).*?R\\$\\s*([\\d.,]+)/is);
                const preco = precoMatch ? precoMatch[2] : null;
                const precoOriginal = precoMatch ? precoMatch[1] : null;
                
                // Imagens
                const imgs = Array.from(document.querySelectorAll('img'))
                    .map(img => img.src)
                    .filter(src => src && src.includes('http') && !src.includes('logo'))
                    .slice(0, 5);
                
                // Disponibilidade
                const disponivel = !bodyText.toLowerCase().includes('indisponível');
                
                return { nome, preco, precoOriginal, imgs, disponivel };
            }
        ''')
        
        return {
            "nome": dados.get("nome"),
            "preco": dados.get("preco"),
            "preco_original": dados.get("precoOriginal"),
            "disponivel": dados.get("disponivel"),
            "marca": None,
            "imagens": dados.get("imgs", []),
            "sku": None,
            "metodo": "DOM"
        }
        
    except Exception as e:
        return {
            "nome": None,
            "preco": None,
            "preco_original": None,
            "disponivel": None,
            "marca": None,
            "imagens": [],
            "sku": None,
            "metodo": "DOM",
            "erro": str(e)
        }


# ============================================================================
# ORQUESTRADOR PRINCIPAL (ARQUITETURA SIMPLIFICADA)
# ============================================================================
class ExtractorHibrido:
    """Extrator híbrido com fallbacks inteligentes"""
    
    def __init__(self):
        self.rate_limiter = TokenBucket(RATE_LIMIT_RPS)
        self.stats = {
            "api_product_basic": 0,  # Nova API descoberta!
            "jsonld": 0,
            "api_json": 0,
            "dom": 0,
            "erro": 0,
            "retry_429": 0,  # Contador de retries por 429
        }
        self.resultados: List[Dict] = []
        self.browser_page: Optional[Page] = None
        self.page_lock = asyncio.Lock()
    
    async def setup(self, url_exemplo: str):
        """Descobrir endpoints antes de começar"""
        self.endpoints_descobertos = await descobrir_endpoints(url_exemplo)
    
    async def extrair_produto(
        self, 
        client: httpx.AsyncClient,
        url: str,
        index: int,
        total: int
    ) -> Dict:
        """
        Extrai 1 produto tentando métodos na ordem:
        1. JSON-LD (mais rápido)
        2. API JSON (rápido)
        3. DOM (mais lento)
        """
        await self.rate_limiter.acquire()
        
        resultado = {
            "url": url,
            "index": index,
            "nome": None,
            "preco": None,
            "preco_original": None,
            "disponivel": None,
            "marca": None,
            "imagens": [],
            "sku": None,
            "metodo": None,
            "erro": None
        }
        
        inicio = time.time()
        
        # TENTATIVA 1: API PRODUCT/BASIC (descoberta no diagnóstico - ultra rápido!)
        dados = await extrair_via_api_product_basic(client, url)
        if dados and dados.get("nome") and dados.get("preco"):
            resultado.update(dados)
            self.stats["api_product_basic"] += 1
            tempo = time.time() - inicio
            print(f"⚡ [{index}/{total}] API-BASIC | {dados['nome'][:50]}... | R${dados['preco']} | {tempo:.2f}s")
            return resultado
        
        # TENTATIVA 2: JSON-LD (fallback)
        dados = await extrair_via_jsonld(client, url)
        if dados and dados.get("nome") and dados.get("preco"):
            resultado.update(dados)
            self.stats["jsonld"] += 1
            tempo = time.time() - inicio
            print(f"✅ [{index}/{total}] JSON-LD | {dados['nome'][:50]}... | R${dados['preco']} | {tempo:.2f}s")
            return resultado
        
        # TENTATIVA 3: API JSON genérica (fallback)
        dados = await extrair_via_api_json(client, url, self.endpoints_descobertos)
        if dados and dados.get("nome") and dados.get("preco"):
            resultado.update(dados)
            self.stats["api_json"] += 1
            tempo = time.time() - inicio
            print(f"✅ [{index}/{total}] API-JSON | {dados['nome'][:50]}... | R${dados['preco']} | {tempo:.2f}s")
            return resultado
        
        # TENTATIVA 3: DOM (fallback com página compartilhada)
        if self.browser_page:
            async with self.page_lock:
                dados = await extrair_via_dom(self.browser_page, url)
            if dados.get("nome") and dados.get("preco"):
                resultado.update(dados)
                self.stats["dom"] += 1
                tempo = time.time() - inicio
                print(f"✅ [{index}/{total}] DOM | {dados['nome'][:50]}... | R${dados['preco']} | {tempo:.2f}s")
            else:
                self.stats["erro"] += 1
                resultado["erro"] = dados.get("erro") or "Dados incompletos"
                print(f"⚠️  [{index}/{total}] Falhou | {url[:60]}...")
            return resultado
        
        # Falha total
        self.stats["erro"] += 1
        resultado["erro"] = "Todos os métodos falharam"
        print(f"❌ [{index}/{total}] ERRO | {url[:60]}...")
        return resultado
    
    async def extrair_produto_com_retry(
        self, 
        client: httpx.AsyncClient,
        url: str,
        index: int,
        total: int,
        max_retries: int = 3
    ) -> Dict:
        """
        Extrai produto com retry inteligente para 429 e exponential backoff
        """
        for tentativa in range(max_retries):
            try:
                resultado = await self.extrair_produto(client, url, index, total)
                
                # Se sucesso, retornar
                if not resultado.get("erro"):
                    return resultado
                
                # Detectar erro 429
                erro_str = str(resultado.get("erro", "")).lower()
                if "429" in erro_str or "too many requests" in erro_str:
                    self.stats["retry_429"] += 1
                    
                    # Tentar extrair Retry-After do erro (se tiver)
                    retry_after = 5  # default 5 segundos
                    
                    # Se não é a última tentativa, retry
                    if tentativa < max_retries - 1:
                        print(f"⏸️  429 detectado! Aguardando {retry_after}s antes de retry {tentativa + 2}/{max_retries}...")
                        await asyncio.sleep(retry_after)
                        continue
                    else:
                        print(f"❌ [{index}/{total}] 429 - Max retries atingido: {url[:60]}...")
                        return resultado
                
                # Para outros erros, exponential backoff
                if tentativa < max_retries - 1:
                    wait_time = 2 ** tentativa  # 1s, 2s, 4s
                    print(f"⏸️  Erro detectado. Retry {tentativa + 2}/{max_retries} em {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    continue
                
                # Última tentativa falhou
                return resultado
                
            except Exception as e:
                if tentativa < max_retries - 1:
                    wait_time = 2 ** tentativa
                    print(f"⏸️  Exceção: {str(e)[:50]}. Retry {tentativa + 2}/{max_retries} em {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    return {
                        "url": url,
                        "index": index,
                        "nome": None,
                        "preco": None,
                        "preco_original": None,
                        "disponivel": None,
                        "marca": None,
                        "imagens": [],
                        "sku": None,
                        "metodo": None,
                        "erro": f"Exceção após {max_retries} tentativas: {str(e)}"
                    }
        
        # Nunca deveria chegar aqui
        return resultado
    
    async def processar_lote(self, urls: List[str]):
        """Processa lote de URLs com concorrência e retry inteligente"""
        print(f"\n🚀 Processando {len(urls)} URLs...")
        print(f"⚙️  Rate limit: {RATE_LIMIT_RPS} rps | Concorrência: {MAX_CONCURRENT}")
        print(f"🔄 Retry automático: até 3 tentativas com backoff")
        print("=" * 80)
        
        # Cliente HTTP compartilhado
        async with httpx.AsyncClient(
            timeout=TIMEOUT_HTTP,
            limits=httpx.Limits(max_connections=MAX_CONCURRENT),
            follow_redirects=True
        ) as client:
            
            # Browser para fallback DOM (apenas 1 instância)
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                
                # User-Agent aleatório
                user_agent = random.choice(USER_AGENTS)
                print(f"🌐 User-Agent: {user_agent[:60]}...")
                print()
                
                context = await browser.new_context(
                    user_agent=user_agent,
                    viewport={"width": 1920, "height": 1080}
                )
                self.browser_page = await context.new_page()
                
                # Processar com semáforo para controlar concorrência
                semaforo = asyncio.Semaphore(MAX_CONCURRENT)
                
                async def processar_com_semaforo(url: str, idx: int):
                    async with semaforo:
                        # MUDANÇA PRINCIPAL: usar extrair_produto_com_retry
                        return await self.extrair_produto_com_retry(client, url, idx + 1, len(urls))
                
                # Executar em paralelo
                tasks = [processar_com_semaforo(url, i) for i, url in enumerate(urls)]
                self.resultados = await asyncio.gather(*tasks)
                
                await browser.close()


# ============================================================================
# MAIN
# ============================================================================
async def main():
    print("=" * 80)
    print("🚀 EXTRATOR HÍBRIDO v2.1 - COM RETRY INTELIGENTE")
    print("=" * 80)
    print()
    
    # ETAPA 1: Setup
    urls = ler_urls()
    if not urls:
        return
    
    # Teste com 10 URLs para validar otimizações
    urls = urls[:10]

    extrator = ExtractorHibrido()
    
    # Descobrir endpoints da API (opcional, pode ser feito uma vez)
    await extrator.setup(urls[0])
    
    # ETAPA 2: Processar lote
    inicio = datetime.now()
    await extrator.processar_lote(urls)
    fim = datetime.now()
    
    duracao = (fim - inicio).total_seconds()
    
    # Relatório final
    print()
    print("=" * 80)
    print("📊 RELATÓRIO FINAL")
    print("=" * 80)
    print()
    print(f"⏱️  Tempo: {duracao:.2f}s ({duracao/60:.2f}min)")
    print(f"⚡ Velocidade: {duracao/len(urls):.3f}s/produto")
    print(f"📈 Estimativa 800: {(duracao/len(urls)) * 800:.1f}s ({(duracao/len(urls)) * 800 / 60:.1f}min)")
    print()
    print(f"✅ Sucesso: {len(urls) - extrator.stats['erro']}/{len(urls)}")
    print(f"   • ⚡ API Product/Basic: {extrator.stats['api_product_basic']} (NOVO!)")
    print(f"   • JSON-LD: {extrator.stats['jsonld']}")
    print(f"   • API JSON genérica: {extrator.stats['api_json']}")
    print(f"   • DOM: {extrator.stats['dom']}")
    print(f"❌ Erros: {extrator.stats['erro']}")
    print(f"🔄 Retries por 429: {extrator.stats['retry_429']}")
    print()
    
    # Salvar
    arquivo = f"resultados_hybrid_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(arquivo, 'w', encoding='utf-8') as f:
        json.dump({
            "stats": {
                "total": len(urls),
                "sucesso": len(urls) - extrator.stats['erro'],
                "duracao_segundos": duracao,
                "velocidade_media": duracao / len(urls),
                **extrator.stats
            },
            "produtos": extrator.resultados
        }, f, ensure_ascii=False, indent=2)
    
    print(f"💾 Salvo: {arquivo}")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
