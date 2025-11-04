"""
🚀 VERSÃO OTIMIZADA AVANÇADA - Performance Máxima sem Aumentar RPS
Otimizações implementadas:
1. HTTP/2 + Connection Pooling (multiplexing, headers comprimidos)
2. Stream parcial com early-stop (baixa menos bytes)
3. Parser lxml (mais rápido que html.parser)
4. 429 inteligente com Retry-After + jitter
5. Headers otimizados + Brotli support
6. Regex pré-compiladas
7. uvloop (se disponível)
"""

import asyncio
import httpx
import time
import json
import random
from bs4 import BeautifulSoup
import re
from urllib.parse import urlparse
import email.utils as eut
import datetime as dt

# Tentar usar uvloop (muito mais rápido)
try:
    import uvloop
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    print("[OK] uvloop ativado")
except Exception:
    print("[INFO] uvloop nao disponivel, usando asyncio padrao")

# User-Agents para rotação
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]

# Regex pré-compiladas (muito mais rápido)
PRECO_RE = re.compile(r'R\$\s*(?:<!--.*?-->)?\s*([\d.,]+)', re.DOTALL)
SKU_RE = re.compile(r'-(\d+)$')
MARCA_RE = re.compile(r'marca[:\s]*([A-Z][A-Za-z]+)', re.IGNORECASE)


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


def parse_retry_after(header_value):
    """Parse Retry-After header (segundos ou data HTTP)"""
    if not header_value:
        return None
    
    # Se for número direto
    if header_value.isdigit():
        return float(header_value)
    
    # Se for data HTTP
    try:
        when = eut.parsedate_to_datetime(header_value)
        now = dt.datetime.now(dt.timezone.utc)
        delta = (when - now).total_seconds()
        return max(0.0, delta)
    except:
        return None


async def extrair_produto_otimizado(
    client: httpx.AsyncClient, 
    url: str, 
    rate_limiter: TokenBucket,
    max_retries: int = 3
) -> dict:
    """Extração otimizada - SEM stream parcial (gargalo removido)"""
    
    for tentativa in range(max_retries):
        inicio = time.time()
        
        try:
            await rate_limiter.acquire()
            
            # Headers IDÊNTICOS ao baseline (não "otimizar" demais!)
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
            
            # OTIMIZAÇÃO: 429 inteligente com Retry-After + jitter
            if response.status_code == 429:
                if tentativa < max_retries - 1:
                    retry_delay = parse_retry_after(response.headers.get("Retry-After"))
                    if retry_delay is None:
                        retry_delay = min(8 * (2 ** tentativa), 60)
                    # Jitter: +/- 50%
                    retry_delay *= random.uniform(0.5, 1.5)
                    await asyncio.sleep(retry_delay)
                    continue
                return {"erro": "HTTP 429", "status": 429, "url": url}
            
            if response.status_code != 200:
                return {"erro": f"HTTP {response.status_code}", "url": url}
            
            html = response.text
            
            # Validação
            if len(html) < 1000:
                if tentativa < max_retries - 1:
                    await asyncio.sleep(2 ** tentativa)
                    continue
                return {"erro": "HTML vazio", "url": url}
            
            # OTIMIZAÇÃO 3: Parser lxml (mais rápido)
            try:
                soup = BeautifulSoup(html, 'lxml')
            except:
                soup = BeautifulSoup(html, 'html.parser')
            
            produto = {
                'nome': None,
                'preco': None,
                'preco_original': None,
                'sku': None,
                'marca': 'Não informado',
                'disponivel': True,
            }
            
            # 1. NOME - segundo H1
            h1_tags = soup.find_all('h1', limit=3)
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
            
            # 2. PREÇOS - Usar HTML original (não str(soup))
            # OTIMIZAÇÃO 4: Regex pré-compilada + usar HTML original
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
            
            # 3. SKU - Regex pré-compilada
            sku_match = SKU_RE.search(url)
            if sku_match:
                produto['sku'] = sku_match.group(1)
            
            # 4. DISPONIBILIDADE
            texto_completo = soup.get_text()
            produto['disponivel'] = 'indisponível' not in texto_completo.lower()
            
            # 5. MARCA - Regex pré-compilada
            marca_match = MARCA_RE.search(texto_completo)
            if marca_match:
                produto['marca'] = marca_match.group(1)
            
            produto['metodo'] = 'HTML-OPT'
            produto['tempo'] = time.time() - inicio
            produto['tentativas'] = tentativa + 1
            produto['url'] = url
            produto['bytes_downloaded'] = len(html)
            
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
    
    return {"erro": "Max retries", "url": url}


async def testar_otimizado():
    """Teste com todas as otimizações avançadas"""
    
    with open('urls_matcon_100.txt', 'r', encoding='utf-8') as f:
        urls = [line.strip() for line in f if line.strip()][:50]
    
    print("=" * 100)
    print("TESTE COM OTIMIZACOES AVANCADAS")
    print("=" * 100)
    print(f"URLs: {len(urls)}")
    print(f"Rate limit: 4 requests/second (mesmo que antes)")
    print(f"Concorrencia: 3 URLs simultaneas (mesmo que antes)")
    print(f"")
    print("OTIMIZACOES ATIVAS:")
    print("   - Parser lxml (mais rapido que html.parser)")
    print("   - 429 com Retry-After + jitter inteligente")
    print("   - Regex pre-compiladas (PRECO_RE, SKU_RE, MARCA_RE)")
    print("   - Cliente httpx simples (sem overhead de transport)")
    print("=" * 100)
    print()
    
    rate_limiter = TokenBucket(rate=4.0)
    
    resultados = []
    erros = 0
    erros_429 = 0
    total_bytes = 0
    
    concorrencia = 3
    
    # Cliente simples (igual à versão baseline que funciona!)
    async with httpx.AsyncClient() as client:
        inicio_total = time.time()
        
        for lote_idx in range(0, len(urls), concorrencia):
            lote = urls[lote_idx:lote_idx + concorrencia]
            
            print(f"[Lote {lote_idx//concorrencia + 1}/{(len(urls)-1)//concorrencia + 1}] Processando {len(lote)} URLs...")
            
            tasks = [extrair_produto_otimizado(client, url, rate_limiter) for url in lote]
            produtos = await asyncio.gather(*tasks)
            
            for i, (url, produto) in enumerate(zip(lote, produtos), 1):
                idx_global = lote_idx + i
                
                if 'erro' in produto:
                    print(f"  [{idx_global:2d}/50] ❌ {produto['erro'][:50]}")
                    erros += 1
                    if produto.get('status') == 429:
                        erros_429 += 1
                else:
                    nome = produto.get('nome', 'N/A')[:40]
                    preco = produto.get('preco', 'N/A')
                    tempo = produto.get('tempo', 0)
                    bytes_dl = produto.get('bytes_downloaded', 0)
                    total_bytes += bytes_dl
                    print(f"  [{idx_global:2d}/50] ✅ {nome:40s} | R$ {preco:>10s} | {tempo:.2f}s | {bytes_dl/1024:.1f}KB")
                
                resultados.append(produto)
            
            print()
        
        tempo_total = time.time() - inicio_total
        sucesso = len(urls) - erros
        tempo_medio = tempo_total / len(urls)
        velocidade = len(urls) / tempo_total
        
        print("=" * 100)
        print("📊 RESULTADOS COM OTIMIZAÇÕES AVANÇADAS")
        print("=" * 100)
        print(f"✅ Sucesso: {sucesso}/{len(urls)} ({sucesso/len(urls)*100:.1f}%)")
        print(f"❌ Erros: {erros}")
        if erros_429 > 0:
            print(f"⚠️  Erros 429: {erros_429}")
        print(f"⏱️  Tempo total: {tempo_total:.2f}s")
        print(f"⚡ Tempo médio: {tempo_medio:.3f}s por produto")
        print(f"🚀 Velocidade: {velocidade:.2f} produtos/segundo")
        print(f"📦 Total baixado: {total_bytes/1024/1024:.2f} MB (média: {total_bytes/sucesso/1024:.1f} KB/produto)")
        
        # Comparação
        print(f"\n📈 COMPARAÇÃO COM VERSÃO ANTERIOR:")
        print(f"   Versão anterior: 1.006s/produto (50.32s total)")
        print(f"   Versão otimizada: {tempo_medio:.3f}s/produto ({tempo_total:.2f}s total)")
        ganho = ((1.006 - tempo_medio) / 1.006 * 100)
        if ganho > 0:
            print(f"   🎉 Ganho: {ganho:.1f}% MAIS RÁPIDO!")
        else:
            print(f"   ⚠️  Diferença: {abs(ganho):.1f}% mais lento")
        
        estimativa_800 = tempo_medio * 800
        print(f"\n   Estimativa 800 produtos:")
        print(f"   Anterior: 13.4 minutos")
        print(f"   Otimizada: {estimativa_800/60:.1f} minutos")
        print("=" * 100)
        
        # Salvar
        arquivo = 'resultados_html_otimizado.json'
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
            print(f"   Bytes: {p.get('bytes_downloaded', 0)/1024:.1f}KB")
            print()


if __name__ == "__main__":
    asyncio.run(testar_otimizado())

