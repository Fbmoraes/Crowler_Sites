"""
⚡ VERSÃO ULTRA-OTIMIZADA - Máxima Performance
Otimizações:
- Concorrência alta (10 URLs simultâneas)
- Rate limit agressivo (6 RPS)
- Parsing minimalista (apenas dados essenciais)
- HTTP/2 connection pooling
- Sem extração de marca/imagens (economiza ~100-200ms)
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
]


class TokenBucket:
    """Rate limiter otimizado"""
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


async def extrair_produto_ultra_rapido(
    client: httpx.AsyncClient, 
    url: str, 
    rate_limiter: TokenBucket,
    max_retries: int = 2  # Reduzido de 3 para 2
) -> dict:
    """Extração ultra-rápida - apenas dados essenciais"""
    
    for tentativa in range(max_retries):
        inicio = time.time()
        
        try:
            await rate_limiter.acquire()
            
            headers = {
                "User-Agent": random.choice(USER_AGENTS),
                "Accept": "text/html",
                "Accept-Language": "pt-BR,pt;q=0.9",
                "Connection": "keep-alive",
            }
            
            response = await client.get(url, headers=headers, timeout=8, follow_redirects=True)
            
            # Retry em 429
            if response.status_code == 429:
                if tentativa < max_retries - 1:
                    await asyncio.sleep(3)  # Fixed 3s wait
                    continue
                return {"erro": "HTTP 429", "status": 429, "url": url}
            
            if response.status_code != 200:
                return {"erro": f"HTTP {response.status_code}", "url": url}
            
            html = response.text
            
            # Validação rápida
            if len(html) < 1000:
                return {"erro": "HTML vazio", "url": url}
            
            soup = BeautifulSoup(html, 'html.parser')
            
            # 1. NOME - Apenas segundo H1
            nome = None
            h1_tags = soup.find_all('h1', limit=3)  # Limitar busca
            if len(h1_tags) >= 2:
                nome = h1_tags[1].get_text(strip=True)
            
            # 2. PREÇOS - Busca direta no HTML (mais rápido que BeautifulSoup)
            preco_pattern = r'R\$\s*(?:<!--.*?-->)?\s*([\d.,]+)'
            precos = re.findall(preco_pattern, html)
            
            preco = None
            preco_original = None
            
            if precos:
                precos_num = []
                for p in precos:
                    try:
                        valor = float(p.replace('.', '').replace(',', '.'))
                        if valor > 10:
                            precos_num.append((valor, p))
                    except:
                        pass
                
                if len(precos_num) >= 2:
                    precos_num.sort(key=lambda x: x[0], reverse=True)
                    preco_original = precos_num[0][1]
                    preco = precos_num[1][1]
                elif precos_num:
                    preco = precos_num[0][1]
            
            # 3. SKU - Regex direto na URL
            sku_match = re.search(r'-(\d+)$', url)
            sku = sku_match.group(1) if sku_match else None
            
            return {
                'nome': nome,
                'preco': preco,
                'preco_original': preco_original,
                'sku': sku,
                'tempo': time.time() - inicio,
                'tentativas': tentativa + 1,
                'url': url,
                'metodo': 'HTML-ULTRA'
            }
            
        except httpx.TimeoutException:
            if tentativa < max_retries - 1:
                await asyncio.sleep(2)
                continue
            return {"erro": "Timeout", "url": url}
        except Exception as e:
            if tentativa < max_retries - 1:
                await asyncio.sleep(1)
                continue
            return {"erro": str(e), "url": url}
    
    return {"erro": "Max retries", "url": url}


async def testar_ultra():
    """Teste com configuração ultra-otimizada"""
    
    # Carregar URLs
    with open('urls_matcon_100.txt', 'r', encoding='utf-8') as f:
        urls = [line.strip() for line in f if line.strip()][:50]
    
    print("=" * 100)
    print("⚡ TESTE ULTRA-OTIMIZADO - MÁXIMA PERFORMANCE")
    print("=" * 100)
    print(f"📦 URLs: {len(urls)}")
    print(f"🚀 Rate limit: 5 requests/second")
    print(f"🔥 Concorrência: 7 URLs simultâneas")
    print(f"⏱️  Timeout: 8s")
    print(f"🎯 Parsing: Minimalista (nome, preço, SKU)")
    print("=" * 100)
    print()
    
    rate_limiter = TokenBucket(rate=5.0)
    
    # Connection pooling otimizado
    limits = httpx.Limits(
        max_connections=15,
        max_keepalive_connections=10,
    )
    
    resultados = []
    erros = 0
    erros_429 = 0
    
    concorrencia = 7  # 7 URLs simultâneas!
    
    async with httpx.AsyncClient(limits=limits) as client:
        inicio_total = time.time()
        
        for lote_idx in range(0, len(urls), concorrencia):
            lote = urls[lote_idx:lote_idx + concorrencia]
            
            print(f"[Lote {lote_idx//concorrencia + 1}/{(len(urls)-1)//concorrencia + 1}] Processando {len(lote)} URLs...")
            
            tasks = [extrair_produto_ultra_rapido(client, url, rate_limiter) for url in lote]
            produtos = await asyncio.gather(*tasks)
            
            for i, (url, produto) in enumerate(zip(lote, produtos), 1):
                idx_global = lote_idx + i
                
                if 'erro' in produto:
                    print(f"  [{idx_global:2d}/50] ❌ {produto['erro']}")
                    erros += 1
                    if produto.get('status') == 429:
                        erros_429 += 1
                else:
                    nome = produto.get('nome', 'N/A')[:40]
                    preco = produto.get('preco', 'N/A')
                    tempo = produto.get('tempo', 0)
                    print(f"  [{idx_global:2d}/50] ✅ {nome:40s} | R$ {preco:>10s} | {tempo:.2f}s")
                
                resultados.append(produto)
            
            print()
        
        tempo_total = time.time() - inicio_total
        sucesso = len(urls) - erros
        tempo_medio = tempo_total / len(urls)
        velocidade = len(urls) / tempo_total
        
        print("=" * 100)
        print("📊 RESULTADOS ULTRA-OTIMIZADOS")
        print("=" * 100)
        print(f"✅ Sucesso: {sucesso}/{len(urls)} ({sucesso/len(urls)*100:.1f}%)")
        print(f"❌ Erros: {erros}")
        if erros_429 > 0:
            print(f"⚠️  Erros 429: {erros_429}")
        print(f"⏱️  Tempo total: {tempo_total:.2f}s")
        print(f"⚡ Tempo médio: {tempo_medio:.3f}s por produto")
        print(f"🚀 Velocidade: {velocidade:.2f} produtos/segundo")
        
        # Comparação
        estimativa_800 = tempo_medio * 800
        print(f"\n📈 ESTIMATIVAS:")
        print(f"   800 produtos: {estimativa_800:.1f}s ({estimativa_800/60:.1f} minutos)")
        print(f"   Ganho vs versão anterior (1.006s): {((1.006 - tempo_medio) / 1.006 * 100):.1f}% mais rápido")
        print("=" * 100)
        
        # Salvar resultados
        arquivo = 'resultados_html_ultra.json'
        with open(arquivo, 'w', encoding='utf-8') as f:
            json.dump(resultados, f, ensure_ascii=False, indent=2)
        
        print(f"\n💾 Resultados salvos em: {arquivo}")
        
        # Exemplos
        print("\n📋 EXEMPLOS:\n")
        produtos_ok = [p for p in resultados if 'erro' not in p][:3]
        for i, p in enumerate(produtos_ok, 1):
            print(f"{i}. {p.get('nome', 'N/A')}")
            print(f"   Preço: R$ {p.get('preco', 'N/A')}")
            print(f"   SKU: {p.get('sku', 'N/A')}")
            print(f"   Tempo: {p.get('tempo', 0):.3f}s")
            print()


if __name__ == "__main__":
    asyncio.run(testar_ultra())
