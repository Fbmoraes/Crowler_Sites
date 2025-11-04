"""
🛡️ VERSÃO ULTRA CONSERVADORA - Ajustada para servidor mais restritivo
Rate: 3 RPS (vs 4 anterior)
Concorrência: 2 URLs (vs 3 anterior)
"""

import asyncio
import httpx
import time
import json
import random
from bs4 import BeautifulSoup
import re

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]


class TokenBucket:
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
    max_retries: int = 5  # Mais retries
) -> dict:
    
    for tentativa in range(max_retries):
        inicio = time.time()
        
        try:
            await rate_limiter.acquire()
            
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
            
            # 429: esperar MUITO mais tempo
            if response.status_code == 429:
                if tentativa < max_retries - 1:
                    wait_time = (2 ** tentativa) * 3  # 3s, 6s, 12s, 24s, 48s
                    print(f"    ⚠️  429 detected, waiting {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    return {"erro": "HTTP 429 - Max retries", "status": 429, "url": url}
            
            if response.status_code != 200:
                return {"erro": f"HTTP {response.status_code}", "status": response.status_code, "url": url}
            
            html = response.text
            
            if not html or len(html) < 1000:
                if tentativa < max_retries - 1:
                    await asyncio.sleep(2 ** tentativa)
                    continue
                return {"erro": f"HTML vazio ({len(html)} bytes)", "url": url}
            
            soup = BeautifulSoup(html, 'html.parser')
            
            produto = {
                'nome': None,
                'preco': None,
                'preco_original': None,
                'sku': None,
                'marca': 'Não informado',
                'disponivel': True,
            }
            
            # Nome
            h1_tags = soup.find_all('h1')
            if len(h1_tags) >= 2:
                produto['nome'] = h1_tags[1].get_text(strip=True)
            elif h1_tags:
                produto['nome'] = h1_tags[0].get_text(strip=True)
            
            if not produto['nome'] or len(produto['nome']) < 10:
                title = soup.find('title')
                if title:
                    parts = title.get_text().split('|')
                    if len(parts) >= 2:
                        produto['nome'] = parts[-1].strip()
            
            # Preços
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
            
            # SKU
            sku_match = re.search(r'-(\d+)$', url)
            if sku_match:
                produto['sku'] = sku_match.group(1)
            
            # Marca
            texto_completo = soup.get_text()
            marca_match = re.search(r'marca[:\s]*([A-Z][A-Za-z]+)', texto_completo, re.IGNORECASE)
            if marca_match:
                produto['marca'] = marca_match.group(1)
            
            produto['disponivel'] = 'indisponível' not in texto_completo.lower()
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


async def testar_conservador():
    with open('urls_matcon_100.txt', 'r', encoding='utf-8') as f:
        urls = [line.strip() for line in f if line.strip()][:50]
    
    print("=" * 100)
    print("TESTE ULTRA CONSERVADOR - Ajustado para servidor restritivo")
    print("=" * 100)
    print(f"📦 URLs: {len(urls)}")
    print(f"⚡ Rate limit: 3 requests/second (reduzido de 4)")
    print(f"🔄 Concorrência: 2 URLs simultâneas (reduzido de 3)")
    print(f"⏱️  Timeout: 15s (aumentado de 10s)")
    print(f"🔁 Max retries: 5 (aumentado de 3)")
    print(f"⏳ Retry delay: 3s, 6s, 12s, 24s, 48s (mais agressivo)")
    print("=" * 100)
    print()
    
    rate_limiter = TokenBucket(rate=3.0)  # REDUZIDO de 4.0
    resultados = []
    erros = 0
    erros_429 = 0
    total_bytes = 0
    
    concorrencia = 2  # REDUZIDO de 3
    
    async with httpx.AsyncClient() as client:
        inicio_total = time.time()
        
        for lote_idx in range(0, len(urls), concorrencia):
            lote = urls[lote_idx:lote_idx + concorrencia]
            
            print(f"[Lote {lote_idx//concorrencia + 1}/{(len(urls)-1)//concorrencia + 1}] Processando {len(lote)} URLs...")
            
            tasks = [extrair_produto_via_html(client, url, rate_limiter) for url in lote]
            produtos = await asyncio.gather(*tasks)
            
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
                    bytes_val = produto.get('bytes', 0) / 1024
                    tentativas = produto.get('tentativas', 1)
                    total_bytes += produto.get('bytes', 0)
                    retry_str = f"[{tentativas}x]" if tentativas > 1 else ""
                    print(f"  [{idx_global:2d}/50] ✅ {nome:45s} | R$ {preco:>10s} | {tempo:.2f}s | {bytes_val:.0f}KB {retry_str}")
                
                resultados.append(produto)
            
            print()
            
            # Pausa adicional entre lotes para ser mais gentil
            if lote_idx + concorrencia < len(urls):
                await asyncio.sleep(0.5)
        
        tempo_total = time.time() - inicio_total
        sucesso = len(urls) - erros
        
        print("=" * 100)
        print("📊 RESULTADOS - CONFIGURAÇÃO CONSERVADORA")
        print("=" * 100)
        print(f"✅ Sucesso: {sucesso}/{len(urls)} ({sucesso/len(urls)*100:.1f}%)")
        print(f"❌ Erros: {erros}")
        if erros_429 > 0:
            print(f"⚠️  Erros 429: {erros_429}")
        print(f"⏱️  Tempo total: {tempo_total:.2f}s")
        if len(urls) > 0:
            print(f"⚡ Tempo médio: {tempo_total/len(urls):.3f}s por produto")
        if sucesso > 0:
            print(f"📦 Média bytes: {total_bytes/sucesso/1024:.0f}KB/produto")
        
        estimativa_800 = (tempo_total/len(urls)) * 800 if len(urls) > 0 else 0
        print(f"\n📈 Estimativa 800 produtos: {estimativa_800/60:.1f} minutos")
        print("=" * 100)
        
        with open('resultados_conservador.json', 'w', encoding='utf-8') as f:
            json.dump(resultados, f, ensure_ascii=False, indent=2)
        
        print(f"\n💾 Salvos em: resultados_conservador.json")


if __name__ == "__main__":
    asyncio.run(testar_conservador())
