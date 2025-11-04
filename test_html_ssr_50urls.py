"""
🚀 TESTE DE CARGA - 50 URLs com Processamento Paralelo Otimizado
Objetivo: Validar estabilidade e performance em lote maior
"""

import asyncio
import httpx
import time
import json
import random
from bs4 import BeautifulSoup
import re

# User-Agents para rotação
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/120.0.0.0",
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


async def extrair_produto_via_html(
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
            
            # Headers (SEM Accept-Encoding manual - httpx lida automaticamente)
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
                    wait_time = (2 ** tentativa) * 2  # Exponential backoff mais agressivo: 2s, 4s, 8s
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    return {"erro": "HTTP 429 - Max retries atingido", "status": 429, "url": url}
            
            if response.status_code != 200:
                return {"erro": f"HTTP {response.status_code}", "status": response.status_code, "url": url}
            
            html = response.text
            soup = BeautifulSoup(html, 'html.parser')
            
            produto = {
                'nome': None,
                'preco': None,
                'preco_original': None,
                'imagens': [],
                'marca': 'Não informado',
                'sku': None,
                'disponivel': True,
            }
            
            # Verificar HTML vazio
            if not html or len(html) < 1000:
                if tentativa < max_retries - 1:
                    await asyncio.sleep(2 ** tentativa)
                    continue
                return {"erro": f"HTML vazio ({len(html)} bytes)", "url": url}
            
            # 1. NOME - O segundo H1 é sempre o nome do produto
            nome = None
            h1_tags = soup.find_all('h1')
            
            if len(h1_tags) >= 2:
                nome = h1_tags[1].get_text(strip=True)
            elif h1_tags:
                nome = h1_tags[0].get_text(strip=True)
            
            # Fallback: usar title da página
            if not nome or len(nome) < 10:
                title = soup.find('title')
                if title:
                    parts = title.get_text().split('|')
                    if len(parts) >= 2:
                        nome = parts[-1].strip()
            
            produto['nome'] = nome
            
            # 2. PREÇOS - Buscar no HTML direto (pega comentários <!-- -->)
            html_str = str(soup)
            preco_pattern = r'R\$\s*(?:<!--.*?-->)?\s*([\d.,]+)'
            precos_encontrados = re.findall(preco_pattern, html_str)
            
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
            
            # 4. DISPONIBILIDADE
            texto_completo = soup.get_text()
            produto['disponivel'] = 'indisponível' not in texto_completo.lower()
            
            # 5. SKU
            sku_match = re.search(r'-(\d+)$', url)
            if sku_match:
                produto['sku'] = sku_match.group(1)
            
            # 6. MARCA
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
                await asyncio.sleep(2 ** tentativa)
                continue
            return {"erro": "Timeout", "url": url}
        except Exception as e:
            if tentativa < max_retries - 1:
                await asyncio.sleep(1)
                continue
            return {"erro": str(e), "url": url}
    
    return {"erro": "Max retries atingido", "url": url}


async def testar_50_urls():
    """Teste de carga com 50 URLs"""
    
    # Carregar URLs do arquivo
    with open('urls_matcon_100.txt', 'r', encoding='utf-8') as f:
        urls = [line.strip() for line in f if line.strip()][:50]
    
    print("=" * 100)
    print("🚀 TESTE DE CARGA - 50 URLs COM PROCESSAMENTO PARALELO OTIMIZADO")
    print("=" * 100)
    print(f"📦 URLs carregadas: {len(urls)}")
    print(f"⚡ Rate limit: 4 requests/second (conservador)")
    print(f"🔄 Concorrência: 3 URLs simultâneas")
    print(f"⏱️  Timeout: 10s por request")
    print("=" * 100)
    print()
    
    # Rate limiter: 4 requisições por segundo (mais conservador)
    rate_limiter = TokenBucket(rate=4.0)
    
    resultados = []
    erros = 0
    erros_429 = 0
    
    # Processamento paralelo - 3 URLs simultâneas (reduzido)
    concorrencia = 3
    
    async with httpx.AsyncClient() as client:
        inicio_total = time.time()
        
        # Processar em lotes paralelos
        for lote_idx in range(0, len(urls), concorrencia):
            lote = urls[lote_idx:lote_idx + concorrencia]
            
            print(f"[Lote {lote_idx//concorrencia + 1}/{(len(urls)-1)//concorrencia + 1}] Processando {len(lote)} URLs...")
            
            # Executar URLs do lote em paralelo
            tasks = [extrair_produto_via_html(client, url, rate_limiter) for url in lote]
            produtos = await asyncio.gather(*tasks)
            
            # Mostrar resultados do lote
            for i, (url, produto) in enumerate(zip(lote, produtos), 1):
                idx_global = lote_idx + i
                
                if 'erro' in produto:
                    print(f"  [{idx_global:2d}/50] ❌ {produto['erro'][:50]}")
                    erros += 1
                    if produto.get('status') == 429:
                        erros_429 += 1
                else:
                    nome = produto.get('nome', 'SEM NOME')[:45]
                    preco = produto.get('preco', 'N/A')
                    tempo = produto.get('tempo', 0)
                    print(f"  [{idx_global:2d}/50] ✅ {nome:45s} | R$ {preco:>10s} | {tempo:.2f}s")
                
                resultados.append(produto)
            
            print()
        
        tempo_total = time.time() - inicio_total
        sucesso = len(urls) - erros
        tempo_medio = tempo_total / len(urls)
        velocidade = len(urls) / tempo_total
        
        print("=" * 100)
        print("📊 RESULTADOS FINAIS")
        print("=" * 100)
        print(f"✅ Sucesso: {sucesso}/{len(urls)} ({sucesso/len(urls)*100:.1f}%)")
        print(f"❌ Erros: {erros}")
        if erros_429 > 0:
            print(f"⚠️  Erros 429 (Rate Limit): {erros_429}")
        print(f"⏱️  Tempo total: {tempo_total:.2f}s")
        print(f"⚡ Tempo médio: {tempo_medio:.3f}s por produto")
        print(f"🚀 Velocidade: {velocidade:.1f} produtos/segundo")
        print(f"📈 Estimativa 800 produtos: {tempo_medio * 800:.1f}s ({tempo_medio * 800 / 60:.1f}min)")
        print("=" * 100)
        
        # Salvar resultados
        arquivo_resultado = 'resultados_html_ssr_50urls.json'
        with open(arquivo_resultado, 'w', encoding='utf-8') as f:
            json.dump(resultados, f, ensure_ascii=False, indent=2)
        
        print(f"\n💾 Resultados salvos em: {arquivo_resultado}")
        
        # Mostrar exemplos de produtos extraídos
        print("\n📋 EXEMPLOS DE PRODUTOS EXTRAÍDOS:\n")
        produtos_sucesso = [p for p in resultados if 'erro' not in p][:5]
        for i, p in enumerate(produtos_sucesso, 1):
            print(f"{i}. {p.get('nome', 'N/A')}")
            print(f"   Preço: R$ {p.get('preco', 'N/A')}")
            if p.get('preco_original'):
                print(f"   De: R$ {p.get('preco_original')}")
            print(f"   SKU: {p.get('sku', 'N/A')}")
            print()
        
        print("=" * 100)


if __name__ == "__main__":
    asyncio.run(testar_50_urls())
