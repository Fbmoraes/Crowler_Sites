"""
🚀 VERSÃO AVANÇADA - Estratégias Profissionais
1. LeakyBucket com jitter + Retry-After (AWS best practices)
2. JSON-LD extraction (Schema.org structured data)
3. Hydration JSON (__NEXT_DATA__, __INITIAL_STATE__, etc.)
4. HTTP/2 + concorrência controlada

Baseado em:
- AWS Exponential Backoff and Jitter: https://aws.amazon.com/blogs/architecture/exponential-backoff-and-jitter/
- MDN Retry-After: https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Retry-After
- Google Product Structured Data: https://developers.google.com/search/docs/appearance/structured-data/product
"""

import asyncio
import httpx
import time
import json
import random
from bs4 import BeautifulSoup
import re
from typing import Optional, Dict, Any

# User-Agents
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]

# Regex pré-compiladas (fallback para HTML puro)
PRECO_RE = re.compile(r'R\$\s*(?:<!--.*?-->)?\s*([\d.,]+)', re.DOTALL)
SKU_RE = re.compile(r'-(\d+)$')
MARCA_RE = re.compile(r'marca[:\s]*([A-Z][A-Za-z]+)', re.IGNORECASE)


class LeakyBucket:
    """
    Rate limiter profissional com:
    - Vazamento constante (leaky bucket)
    - Full Jitter (AWS recommendation)
    - Retry-After support (RFC 6585)
    """
    def __init__(self, pps: float, jitter_frac: float = 0.20):
        assert pps > 0, "Products per second must be positive"
        self.base_interval = 1.0 / pps              # ex.: 0.3 pps -> 3.333s
        self.jitter_frac = jitter_frac               # +/-20% por padrão (AWS recommendation)
        self.next_slot = time.monotonic()
        self.lock = asyncio.Lock()

    async def acquire(self, retry_after_seconds: Optional[float] = None):
        """
        Aguarda até próximo slot disponível.
        Se retry_after_seconds > 0, empurra janela para respeitar servidor.
        """
        async with self.lock:
            now = time.monotonic()
            
            # Se servidor mandou Retry-After, respeitar!
            if retry_after_seconds and retry_after_seconds > 0:
                self.next_slot = max(self.next_slot, now + retry_after_seconds)

            # Aguardar até próximo slot
            delay = max(0.0, self.next_slot - now)
            if delay:
                await asyncio.sleep(delay)

            # Agendar próximo slot com Full Jitter (AWS best practice)
            jitter = random.uniform(1 - self.jitter_frac, 1 + self.jitter_frac)
            self.next_slot = max(self.next_slot, time.monotonic()) + self.base_interval * jitter


def parse_retry_after(header_value: Optional[str]) -> Optional[float]:
    """Parse Retry-After header (segundos ou HTTP-date)"""
    if not header_value:
        return None
    try:
        return float(header_value)
    except ValueError:
        # Pode ser HTTP-date, mas por simplicidade retornar None
        # Em produção, implementar parsing de RFC 7231 date
        return None


def extrair_via_jsonld(html: str) -> Optional[Dict[str, Any]]:
    """
    Extrai dados estruturados do JSON-LD (Schema.org Product).
    Retorna dict com: nome, sku, ean, marca, preco, moeda, imagens, disponivel
    
    Ref: https://developers.google.com/search/docs/appearance/structured-data/product
    """
    soup = BeautifulSoup(html, 'lxml')
    
    for tag in soup.find_all('script', type='application/ld+json'):
        try:
            data = json.loads(tag.string or "{}")
        except Exception:
            continue
        
        # Pode vir dict ou lista
        items = data if isinstance(data, list) else [data]
        
        for item in items:
            tipo = item.get('@type', '')
            
            # Procurar Product, IndividualProduct, ProductGroup
            if tipo in ('Product', 'IndividualProduct', 'ProductGroup'):
                offers = item.get('offers') or {}
                
                # Normalizar offers (pode ser lista)
                if isinstance(offers, list):
                    offers = offers[0] if offers else {}
                
                # Extrair brand (pode ser string ou objeto)
                brand = item.get('brand')
                if isinstance(brand, dict):
                    brand = brand.get('name')
                
                # Extrair imagens (pode ser string ou lista)
                images = item.get('image')
                if isinstance(images, str):
                    images = [images]
                elif not isinstance(images, list):
                    images = []
                
                return {
                    "nome": item.get('name'),
                    "sku": item.get('sku') or item.get('mpn'),
                    "ean": (item.get('gtin13') or item.get('gtin') or 
                           item.get('gtin14') or item.get('gtin8')),
                    "marca": brand,
                    "preco": offers.get('price'),
                    "moeda": offers.get('priceCurrency'),
                    "imagens": images,
                    "disponivel": offers.get('availability'),
                    "fonte": "JSON-LD"
                }
    
    return None


def extrair_via_hydration(html: str) -> Optional[Dict[str, Any]]:
    """
    Extrai dados do hydration JSON (ex: __NEXT_DATA__, __INITIAL_STATE__).
    Frameworks modernos (Next.js, Gatsby, etc.) expõem dados completos em JSON.
    
    Ref: https://stackoverflow.com/questions/69396462/how-to-remove-next-data-from-dom-in-nextjs
    """
    # Procurar __NEXT_DATA__
    m = re.search(r'<script[^>]*id="__NEXT_DATA__"[^>]*type="application/json">(.*?)</script>', 
                  html, re.DOTALL | re.IGNORECASE)
    
    if not m:
        # Tentar __INITIAL_STATE__ ou variações
        m = re.search(r'window\.__INITIAL_STATE__\s*=\s*({.*?});', html, re.DOTALL)
    
    if not m:
        return None
    
    try:
        data = json.loads(m.group(1))
    except Exception:
        return None
    
    # Estrutura varia por framework - tentar campos comuns
    # Converter para string para busca case-insensitive
    blob = json.dumps(data)
    
    # Extrair campos comuns (adaptar conforme site específico)
    result = {}
    
    # Nome do produto
    nome_match = re.search(r'"(?:name|title|productName)"\s*:\s*"([^"]+)"', blob, re.IGNORECASE)
    if nome_match:
        result['nome'] = nome_match.group(1)
    
    # Preço
    preco_match = re.search(r'"(?:price|sellingPrice)"\s*:\s*"?(?:R\$\s*)?([\d.,]+)"?', blob, re.IGNORECASE)
    if preco_match:
        result['preco'] = preco_match.group(1)
    
    # SKU
    sku_match = re.search(r'"(?:sku|productId|itemId)"\s*:\s*"?(\d+)"?', blob, re.IGNORECASE)
    if sku_match:
        result['sku'] = sku_match.group(1)
    
    # EAN
    ean_match = re.search(r'"(?:ean|gtin|gtin13)"\s*:\s*"?(\d+)"?', blob, re.IGNORECASE)
    if ean_match:
        result['ean'] = ean_match.group(1)
    
    if result:
        result['fonte'] = 'Hydration-JSON'
        return result
    
    return None


def extrair_via_html_fallback(html: str, url: str) -> Dict[str, Any]:
    """
    Fallback: extração tradicional por parsing HTML.
    Usado quando JSON-LD e Hydration falham.
    """
    soup = BeautifulSoup(html, 'lxml')
    
    produto = {
        'nome': None,
        'preco': None,
        'preco_original': None,
        'sku': None,
        'marca': 'Não informado',
        'ean': None,
        'imagens': [],
        'disponivel': True,
        'fonte': 'HTML-Fallback'
    }
    
    # 1. NOME - segundo H1
    h1_tags = soup.find_all('h1')
    if len(h1_tags) >= 2:
        produto['nome'] = h1_tags[1].get_text(strip=True)
    elif h1_tags:
        produto['nome'] = h1_tags[0].get_text(strip=True)
    
    # Fallback: title
    if not produto['nome'] or len(produto['nome']) < 10:
        title = soup.find('title')
        if title:
            parts = title.get_text().split('|')
            if len(parts) >= 2:
                produto['nome'] = parts[-1].strip()
    
    # 2. PREÇOS - usar regex pré-compilada
    precos_encontrados = PRECO_RE.findall(html)
    
    if precos_encontrados:
        precos_num = []
        for p in precos_encontrados:
            try:
                valor = float(p.replace('.', '').replace(',', '.'))
                if valor > 10:
                    precos_num.append((valor, p))
            except:
                pass
        
        if len(precos_num) >= 2:
            precos_num.sort(key=lambda x: x[0], reverse=True)
            produto['preco_original'] = precos_num[0][1]
            produto['preco'] = precos_num[1][1]
        elif precos_num:
            produto['preco'] = precos_num[0][1]
    
    # 3. IMAGENS
    imgs = soup.find_all('img')
    imagens_unicas = []
    seen = set()
    for img in imgs:
        src = img.get('src', '')
        if src and ('produto' in src.lower() or 'product' in src.lower()):
            img_base = src.split('?')[0]
            if img_base not in seen:
                seen.add(img_base)
                imagens_unicas.append(src)
    
    produto['imagens'] = imagens_unicas[:5]
    
    # 4. SKU - usar regex pré-compilada
    sku_match = SKU_RE.search(url)
    if sku_match:
        produto['sku'] = sku_match.group(1)
    
    # 5. MARCA - usar regex pré-compilada
    texto_completo = soup.get_text()
    marca_match = MARCA_RE.search(texto_completo)
    if marca_match:
        produto['marca'] = marca_match.group(1)
    
    # 6. DISPONIBILIDADE
    produto['disponivel'] = 'indisponível' not in texto_completo.lower()
    
    return produto


async def extrair_produto_avancado(
    client: httpx.AsyncClient,
    url: str,
    rate_limiter: LeakyBucket,
    max_retries: int = 5
) -> Dict[str, Any]:
    """
    Extração avançada com estratégias em cascata:
    1. JSON-LD (Schema.org)
    2. Hydration JSON
    3. HTML fallback
    """
    
    retry_after = None
    
    for tentativa in range(max_retries):
        inicio = time.time()
        
        try:
            # Rate limiting com Retry-After support
            await rate_limiter.acquire(retry_after)
            
            # Headers completos
            headers = {
                "User-Agent": random.choice(USER_AGENTS),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
                "Referer": "https://www.matconcasa.com.br/",
                "DNT": "1",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "same-origin",
                "Cache-Control": "max-age=0",
            }
            
            response = await client.get(url, headers=headers, timeout=15, follow_redirects=True)
            
            # Tratamento 429 com Retry-After (RFC 6585)
            if response.status_code == 429:
                retry_after = parse_retry_after(response.headers.get("Retry-After"))
                
                if retry_after is None:
                    # Fallback: Full Jitter exponential backoff (AWS recommendation)
                    retry_after = min(60, (2 ** tentativa) * random.uniform(1.0, 3.0))
                
                if tentativa < max_retries - 1:
                    print(f"    [429] Waiting {retry_after:.1f}s (Retry-After)...")
                    # Não fazer sleep aqui - o acquire() no próximo loop vai lidar
                    continue
                else:
                    return {"erro": "HTTP 429", "status": 429, "url": url}
            
            if response.status_code != 200:
                return {"erro": f"HTTP {response.status_code}", "status": response.status_code, "url": url}
            
            html = response.text
            
            if not html or len(html) < 1000:
                if tentativa < max_retries - 1:
                    await asyncio.sleep(2 ** tentativa)
                    continue
                return {"erro": f"HTML vazio ({len(html)} bytes)", "url": url}
            
            # ESTRATÉGIA 1: JSON-LD (melhor opção - dados estruturados)
            produto = extrair_via_jsonld(html)
            
            # ESTRATÉGIA 2: Hydration JSON (segunda melhor)
            if not produto or not produto.get('nome'):
                hydration = extrair_via_hydration(html)
                if hydration:
                    produto = hydration if not produto else {**produto, **hydration}
            
            # ESTRATÉGIA 3: HTML Fallback (última opção)
            if not produto or not produto.get('nome'):
                produto = extrair_via_html_fallback(html, url)
            
            # Completar campos comuns
            produto['tempo'] = time.time() - inicio
            produto['tentativas'] = tentativa + 1
            produto['url'] = url
            produto['bytes'] = len(html)
            
            return produto
            
        except httpx.TimeoutException:
            if tentativa < max_retries - 1:
                await asyncio.sleep(2 ** tentativa)
                continue
            return {"erro": "Timeout", "url": url}
        except Exception as e:
            if tentativa < max_retries - 1:
                await asyncio.sleep(1)
                continue
            return {"erro": str(e), "url": url}
    
    return {"erro": "Max retries atingido", "url": url}


async def testar_avancado():
    """Teste com estratégias avançadas"""
    
    with open('urls_matcon_100.txt', 'r', encoding='utf-8') as f:
        urls = [line.strip() for line in f if line.strip()][:50]
    
    print("=" * 100)
    print("EXTRACAO AVANCADA - Estrategias Profissionais")
    print("=" * 100)
    print(f"URLs: {len(urls)}")
    print(f"")
    print("ESTRATEGIAS:")
    print("  1. LeakyBucket com Full Jitter (AWS best practices)")
    print("  2. Retry-After support (RFC 6585)")
    print("  3. JSON-LD extraction (Schema.org Product)")
    print("  4. Hydration JSON (__NEXT_DATA__, etc.)")
    print("  5. HTML fallback (tradicional)")
    print(f"")
    print(f"CONFIGURACAO:")
    print(f"  - Rate: 0.4 produtos/segundo (~2.5s entre requisicoes)")
    print(f"  - Concorrencia: 1 (sequencial para maximo controle)")
    print(f"  - Jitter: +/-20% (evita thundering herd)")
    print(f"  - HTTP: 1.1 (h2 nao instalado - use 'pip install httpx[http2]')")
    print("=" * 100)
    print()
    
    # LeakyBucket: 0.4 produtos/segundo = 1 produto a cada ~2.5s
    # Ajuste: 0.3 pps (MAIS LENTO mas 100% sucesso) | 0.5 pps (MAIS RÁPIDO mas pode ter 429s)
    rate_limiter = LeakyBucket(pps=0.4, jitter_frac=0.20)
    
    resultados = []
    erros = 0
    total_bytes = 0
    
    # HTTP/1.1 + concorrência 1 (controle máximo)
    # Para HTTP/2: pip install httpx[http2]
    async with httpx.AsyncClient(limits=httpx.Limits(max_connections=1,
                                                     max_keepalive_connections=1)) as client:
        inicio_total = time.time()
        
        for idx, url in enumerate(urls, 1):
            print(f"[{idx:2d}/{len(urls)}] Processando...")
            
            produto = await extrair_produto_avancado(client, url, rate_limiter)
            
            if 'erro' in produto:
                print(f"        X {produto['erro'][:60]}")
                erros += 1
            else:
                nome = produto.get('nome', 'SEM NOME')[:50]
                preco = produto.get('preco', 'N/A')
                tempo = produto.get('tempo', 0)
                bytes_val = produto.get('bytes', 0) / 1024
                fonte = produto.get('fonte', '?')
                tentativas = produto.get('tentativas', 1)
                total_bytes += produto.get('bytes', 0)
                
                retry_str = f"[{tentativas}x]" if tentativas > 1 else ""
                print(f"        OK {nome[:50]:50s}")
                print(f"           Preco: R$ {str(preco):>10s} | Tempo: {tempo:.2f}s | {bytes_val:.0f}KB | {fonte} {retry_str}")
                
                if produto.get('ean'):
                    print(f"           EAN: {produto['ean']}")
            
            resultados.append(produto)
            print()
        
        tempo_total = time.time() - inicio_total
        sucesso = len(urls) - erros
        
        print("=" * 100)
        print("RESULTADOS FINAIS")
        print("=" * 100)
        print(f"Sucesso: {sucesso}/{len(urls)} ({sucesso/len(urls)*100:.1f}%)")
        print(f"Erros: {erros}")
        print(f"Tempo total: {tempo_total:.2f}s")
        if len(urls) > 0:
            print(f"Tempo medio: {tempo_total/len(urls):.3f}s por produto")
        if sucesso > 0:
            print(f"Bytes medio: {total_bytes/sucesso/1024:.0f}KB/produto")
        
        # Contar fontes de dados
        fontes = {}
        for p in resultados:
            if 'erro' not in p:
                fonte = p.get('fonte', 'Unknown')
                fontes[fonte] = fontes.get(fonte, 0) + 1
        
        print(f"\nFONTES DE DADOS:")
        for fonte, count in fontes.items():
            print(f"  - {fonte}: {count} produtos ({count/sucesso*100:.1f}%)")
        
        estimativa_800 = (tempo_total/len(urls)) * 800 if len(urls) > 0 else 0
        print(f"\nEstimativa 800 produtos: {estimativa_800/60:.1f} minutos")
        print("=" * 100)
        
        with open('resultados_avancado.json', 'w', encoding='utf-8') as f:
            json.dump(resultados, f, ensure_ascii=False, indent=2)
        
        print(f"\nSalvo em: resultados_avancado.json")


if __name__ == "__main__":
    asyncio.run(testar_avancado())
