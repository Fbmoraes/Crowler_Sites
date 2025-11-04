"""
🚀 EXTRAÇÃO OTIMIZADA VIA HTML SSR - VERSÃO REFINADA
Correções:
1. Seletor de H1 mais preciso
2. Rate limiting inteligente
3. Extração melhorada de preços
4. Retry automático para 429
"""

import asyncio
import httpx
from bs4 import BeautifulSoup
import re
import json
import time
import random


# User-Agents para rotação
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]


class TokenBucket:
    """Rate limiter simples"""
    def __init__(self, rate: float):
        self.rate = rate
        self.tokens = rate
        self.last_update = time.time()
        self.lock = asyncio.Lock()
    
    async def acquire(self):
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


async def extrair_produto_via_html_refinado(
    client: httpx.AsyncClient, 
    url: str, 
    rate_limiter: TokenBucket,
    max_retries: int = 3
) -> dict:
    """Extrai produto direto do HTML com retry e rate limiting"""
    
    for tentativa in range(max_retries):
        inicio = time.time()
        
        try:
            # Rate limiting
            await rate_limiter.acquire()
            
            # Headers mais completos (removido Accept-Encoding pois httpx lida automaticamente)
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
            
            response = await client.get(url, headers=headers, timeout=10, follow_redirects=True)
            
            # Detectar 429 e fazer retry
            if response.status_code == 429:
                if tentativa < max_retries - 1:
                    wait_time = 2 ** tentativa  # Exponential backoff: 1s, 2s, 4s
                    print(f"   ⏸️  429 detectado! Aguardando {wait_time}s (tentativa {tentativa + 1}/{max_retries})")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    return {"erro": "HTTP 429 - Max retries atingido", "status": 429}
            
            if response.status_code != 200:
                return {"erro": f"HTTP {response.status_code}", "status": response.status_code}
            
            html = response.text
            soup = BeautifulSoup(html, 'html.parser')
            
            # Extrair dados
            produto = {}
            
            # DEBUG: Ver se HTML está vazio
            if not html or len(html) < 1000:
                print(f"   ⚠️  HTML muito curto: {len(html)} bytes (possível 404/redirect)")
                if tentativa < max_retries - 1:
                    await asyncio.sleep(2 ** tentativa)
                    continue
                return {"erro": f"HTML vazio ({len(html)} bytes)", "url": url}
            
            # 1. NOME - O segundo H1 é sempre o nome do produto
            nome = None
            h1_tags = soup.find_all('h1')
            
            if len(h1_tags) >= 2:
                # Segundo H1 é o nome do produto
                nome = h1_tags[1].get_text(strip=True)
            elif h1_tags:
                # Fallback: primeiro H1
                nome = h1_tags[0].get_text(strip=True)
            
            # Fallback: usar title da página
            if not nome or len(nome) < 10:
                title = soup.find('title')
                if title:
                    # Extrair da estrutura: "Site | Nome do Produto"
                    parts = title.get_text().split('|')
                    if len(parts) >= 2:
                        nome = parts[-1].strip()  # Último segmento após |
            
            produto['nome'] = nome
            
            # 2. PREÇOS - Buscar no HTML direto (pega comentários <!-- -->)
            html_str = str(soup)
            
            # Padrão: "de R$ <!-- -->2.706,38" e "R$ <!-- -->2.463,73"
            preco_pattern = r'R\$\s*(?:<!--.*?-->)?\s*([\d.,]+)'
            precos_encontrados = re.findall(preco_pattern, html_str)
            
            if precos_encontrados:
                # Converter para float para filtrar
                precos_num = []
                for p in precos_encontrados:
                    try:
                        valor = float(p.replace('.', '').replace(',', '.'))
                        if valor > 10:  # Filtrar valores muito pequenos
                            precos_num.append((valor, p))
                    except:
                        pass
                
                if len(precos_num) >= 2:
                    # Ordenar por valor
                    precos_num.sort(key=lambda x: x[0], reverse=True)
                    produto['preco_original'] = precos_num[0][1]  # Maior preço (original)
                    produto['preco'] = precos_num[1][1]  # Segundo maior (final)
                elif precos_num:
                    produto['preco'] = precos_num[0][1]
            
            # 3. IMAGENS - Melhorar filtros
            imagens = []
            for img in soup.find_all('img'):
                src = img.get('src') or img.get('data-src') or img.get('data-lazy-src')
                if src:
                    # Filtros de qualidade
                    if ('http' in src and 
                        'logo' not in src.lower() and
                        'icon' not in src.lower() and
                        'banner' not in src.lower() and
                        img.get('width', 100) != '1'):  # Não é pixel de tracking
                        
                        # Preferir imagens do domínio api.matconcasa
                        if 'api.matconcasa' in src or 'media' in src:
                            imagens.insert(0, src)  # Priorizar no início
                        else:
                            imagens.append(src)
            
            # Remover duplicatas mantendo ordem
            imagens_unicas = []
            seen = set()
            for img in imagens:
                # Normalizar URL (remover query params para comparação)
                img_base = img.split('?')[0]
                if img_base not in seen:
                    seen.add(img_base)
                    imagens_unicas.append(img)
            
            produto['imagens'] = imagens_unicas[:5]
            
            # 4. DISPONIBILIDADE
            texto_completo = soup.get_text()
            produto['disponivel'] = 'indisponível' not in texto_completo.lower()
            
            # 5. SKU
            sku_match = re.search(r'-(\d+)$', url)
            if sku_match:
                produto['sku'] = sku_match.group(1)
            
            # 6. MARCA (se encontrar)
            marca_match = re.search(r'marca[:\s]*([A-Z][A-Za-z]+)', texto_completo, re.IGNORECASE)
            if marca_match:
                produto['marca'] = marca_match.group(1)
            
            produto['metodo'] = 'HTML-SSR'
            produto['tempo'] = time.time() - inicio
            produto['tentativas'] = tentativa + 1
            produto['url'] = url
            
            return produto
            
        except httpx.TimeoutException:
            if tentativa < max_retries - 1:
                print(f"   ⏸️  Timeout! Retry {tentativa + 2}/{max_retries}")
                await asyncio.sleep(1)
                continue
            return {"erro": "Timeout", "url": url}
            
        except Exception as e:
            if tentativa < max_retries - 1:
                print(f"   ⏸️  Erro: {str(e)[:50]}... Retry {tentativa + 2}/{max_retries}")
                await asyncio.sleep(1)
                continue
            return {"erro": str(e), "url": url}
    
    return {"erro": "Max retries atingido", "url": url}


async def testar_refinado():
    """Testa versão refinada"""
    
    urls = [
        "https://www.matconcasa.com.br/produto/furadeira-makita-de-impacto-1-2-1010w-220v-hp2070-220v-281700",
        "https://www.matconcasa.com.br/produto/tupia-laminadora-makita-1-4-530w-127v-3709127v-250228",
        "https://www.matconcasa.com.br/produto/furadeira-parafusadeira-black-decker-3-8-12v-bateria-com-13-acessorios-ld12s-br-403644",
        "https://www.matconcasa.com.br/produto/inversora-de-solda-intech-compacta-com-acessorios-160a-bivolt-7898632332698-405435",
        "https://www.matconcasa.com.br/produto/martelete-dewalt-sds-plus-rompedor-220v-800w-d25133kb2-412615",
        "https://www.matconcasa.com.br/produto/torques-berg-armador-12-5648512-91073",
        "https://www.matconcasa.com.br/produto/soquete-excellent-bits-com-catraca-encaixe-1-4-e-3-8-com-40-pecas-8zi-402602",
        "https://www.matconcasa.com.br/produto/soprador-termico-hikari-hk-510-2000w-127v-21d001-412973",
    ]
    
    print("=" * 100)
    print("🚀 TESTE REFINADO - EXTRAÇÃO VIA HTML SSR COM RETRY E RATE LIMITING")
    print("=" * 100)
    print()
    
    # Rate limiter: 5 requisições por segundo (otimizado!)
    rate_limiter = TokenBucket(rate=5.0)
    
    resultados = []
    erros = 0
    
    # ⚡ PROCESSAMENTO PARALELO - 5 URLs simultâneas
    concorrencia = 5
    
    async with httpx.AsyncClient() as client:
        inicio_total = time.time()
        
        # Processar em lotes paralelos
        for lote_idx in range(0, len(urls), concorrencia):
            lote = urls[lote_idx:lote_idx + concorrencia]
            
            print(f"[Lote {lote_idx//concorrencia + 1}] Processando {len(lote)} URLs em paralelo...")
            
            # Executar URLs do lote em paralelo
            tasks = [extrair_produto_via_html_refinado(client, url, rate_limiter) for url in lote]
            produtos = await asyncio.gather(*tasks)
            
            # Mostrar resultados do lote
            for i, (url, produto) in enumerate(zip(lote, produtos), 1):
                idx_global = lote_idx + i
                print(f"  [{idx_global}/{len(urls)}] ", end="")
                
                if 'erro' in produto:
                    print(f"❌ Erro: {produto['erro']}")
                    erros += 1
                else:
                    nome = produto.get('nome') or 'SEM NOME'
                    print(f"✅ {nome[:60]} | R$ {produto.get('preco', 'N/A')} | {produto.get('tempo', 0):.3f}s")
                
                resultados.append(produto)
            print()
        
        tempo_total = time.time() - inicio_total
        sucesso = len(urls) - erros
        tempo_medio = tempo_total / len(urls)
        
        print("=" * 100)
        print("📊 RESULTADOS FINAIS")
        print("=" * 100)
        print(f"✅ Sucesso: {sucesso}/{len(urls)} ({sucesso/len(urls)*100:.1f}%)")
        print(f"❌ Erros: {erros}")
        print(f"⏱️  Tempo total: {tempo_total:.2f}s")
        print(f"⚡ Tempo médio: {tempo_medio:.3f}s por produto")
        print(f"🚀 Velocidade: {1/tempo_medio:.1f} produtos/segundo")
        print(f"📈 Estimativa 800 produtos: {tempo_medio * 800:.1f}s ({tempo_medio * 800 / 60:.1f}min)")
        print()
        
        # Salvar resultados
        with open("resultados_html_ssr_refinado.json", "w", encoding="utf-8") as f:
            json.dump({
                "total": len(urls),
                "sucesso": sucesso,
                "erros": erros,
                "tempo_total": tempo_total,
                "tempo_medio": tempo_medio,
                "produtos": resultados
            }, f, ensure_ascii=False, indent=2)
        
        print("💾 Resultados salvos em: resultados_html_ssr_refinado.json")
        print()
        
        # Mostrar exemplos de sucesso
        print("📋 EXEMPLOS DE PRODUTOS EXTRAÍDOS:")
        print()
        sucessos = [r for r in resultados if 'erro' not in r]
        for i, prod in enumerate(sucessos[:3], 1):
            print(f"{i}. {prod.get('nome', 'N/A')}")
            print(f"   Preço: R$ {prod.get('preco', 'N/A')}")
            print(f"   SKU: {prod.get('sku', 'N/A')}")
            print()
        
        print("=" * 100)


if __name__ == "__main__":
    asyncio.run(testar_refinado())
