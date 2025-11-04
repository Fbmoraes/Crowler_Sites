"""
🚀 TESTE TURBO - Encontrar limite máximo absoluto
Testando velocidades muito agressivas: 2.0, 1.8, 1.5, 1.2 pps
"""

import asyncio
import httpx
import time
import json
import random
from bs4 import BeautifulSoup
import re
from typing import Dict, Any

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]

PRECO_RE = re.compile(r'R\$\s*(?:<!--.*?-->)?\s*([\d.,]+)', re.DOTALL)


class LeakyBucket:
    def __init__(self, pps: float, jitter_frac: float = 0.20):
        self.base_interval = 1.0 / pps
        self.jitter_frac = jitter_frac
        self.next_slot = time.monotonic()
        self.lock = asyncio.Lock()

    async def acquire(self):
        async with self.lock:
            now = time.monotonic()
            delay = max(0.0, self.next_slot - now)
            if delay:
                await asyncio.sleep(delay)
            jitter = random.uniform(1 - self.jitter_frac, 1 + self.jitter_frac)
            self.next_slot = max(self.next_slot, time.monotonic()) + self.base_interval * jitter


async def extrair_turbo(client, url, rate_limiter) -> Dict[str, Any]:
    inicio = time.time()
    
    try:
        await rate_limiter.acquire()
        
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9",
            "Referer": "https://www.matconcasa.com.br/",
            "DNT": "1",
            "Connection": "keep-alive",
        }
        
        response = await client.get(url, headers=headers, timeout=10, follow_redirects=True)
        
        if response.status_code == 429:
            return {"erro": "429", "status": 429, "tempo": time.time() - inicio}
        
        if response.status_code != 200:
            return {"erro": f"HTTP {response.status_code}", "tempo": time.time() - inicio}
        
        html = response.text
        if len(html) < 1000:
            return {"erro": "HTML vazio", "tempo": time.time() - inicio}
        
        soup = BeautifulSoup(html, 'lxml')
        h1_tags = soup.find_all('h1')
        nome = h1_tags[1].get_text(strip=True) if len(h1_tags) >= 2 else (h1_tags[0].get_text(strip=True) if h1_tags else None)
        
        precos = PRECO_RE.findall(html)
        preco = precos[0] if precos else None
        
        return {
            "nome": nome,
            "preco": preco,
            "tempo": time.time() - inicio,
            "bytes": len(html)
        }
    except Exception as e:
        return {"erro": str(e), "tempo": time.time() - inicio}


async def testar_turbo():
    with open('urls_matcon_100.txt', 'r', encoding='utf-8') as f:
        urls = [line.strip() for line in f if line.strip()][:20]  # 20 URLs para teste mais robusto
    
    print("=" * 100)
    print("TESTE TURBO - Encontrando limite MAXIMO absoluto")
    print("=" * 100)
    print(f"URLs: {len(urls)}")
    print("=" * 100)
    print()
    
    velocidades = [
        (2.5, "2.5 pps (~0.4s entre reqs) - EXTREMO"),
        (2.0, "2.0 pps (0.5s entre reqs) - MUITO AGRESSIVO"),
        (1.5, "1.5 pps (~0.67s entre reqs) - AGRESSIVO"),
        (1.2, "1.2 pps (~0.83s entre reqs) - RAPIDO"),
    ]
    
    resultados = []
    
    for pps, label in velocidades:
        print(f"\n{'='*100}")
        print(f"TESTANDO: {label}")
        print(f"{'='*100}")
        
        rate_limiter = LeakyBucket(pps=pps, jitter_frac=0.20)
        produtos = []
        erros_429 = 0
        
        async with httpx.AsyncClient(limits=httpx.Limits(max_connections=2, max_keepalive_connections=2)) as client:
            inicio_total = time.time()
            
            for idx, url in enumerate(urls, 1):
                produto = await extrair_turbo(client, url, rate_limiter)
                produtos.append(produto)
                
                if 'erro' in produto:
                    if produto.get('status') == 429:
                        erros_429 += 1
                        print(f"  [{idx:2d}/20] 429")
                    else:
                        print(f"  [{idx:2d}/20] ERR")
                else:
                    print(f"  [{idx:2d}/20] OK  ({produto['tempo']:.2f}s)")
            
            tempo_total = time.time() - inicio_total
        
        sucessos = sum(1 for p in produtos if 'erro' not in p)
        taxa = sucessos / len(urls) * 100
        tempo_medio = tempo_total / len(urls)
        
        resultado = {
            "pps": pps,
            "label": label,
            "taxa_sucesso": taxa,
            "sucessos": sucessos,
            "total": len(urls),
            "erros_429": erros_429,
            "tempo_medio": tempo_medio,
            "estimativa_800": (tempo_medio * 800) / 60
        }
        resultados.append(resultado)
        
        print(f"\nRESULTADO:")
        print(f"  Sucesso: {sucessos}/{len(urls)} ({taxa:.0f}%)")
        print(f"  Erros 429: {erros_429}")
        print(f"  Tempo medio: {tempo_medio:.2f}s/produto")
        print(f"  Estimativa 800: {resultado['estimativa_800']:.1f} minutos")
        
        if taxa == 100:
            print(f"  >>> PERFEITO! 100% sucesso")
        elif taxa >= 90:
            print(f"  >>> EXCELENTE! {taxa:.0f}% sucesso")
        elif taxa >= 70:
            print(f"  >>> BOM! {taxa:.0f}% sucesso")
        else:
            print(f"  >>> LIMITE ULTRAPASSADO! {taxa:.0f}% sucesso")
    
    print(f"\n{'='*100}")
    print("RESUMO FINAL")
    print(f"{'='*100}")
    print(f"{'PPS':<6} | {'Tempo/prod':<12} | {'Sucesso':<15} | {'429s':<6} | {'800 prods':<12}")
    print("-" * 100)
    
    for r in resultados:
        print(f"{r['pps']:<6.1f} | {r['tempo_medio']:<12.2f}s | {r['sucessos']:>2d}/{r['total']:<2d} ({r['taxa_sucesso']:>5.0f}%) | "
              f"{r['erros_429']:>6d} | {r['estimativa_800']:>10.1f}min")
    
    print(f"\n{'='*100}")
    print("RECOMENDACAO FINAL:")
    print(f"{'='*100}")
    
    melhor = max((r for r in resultados if r['taxa_sucesso'] >= 90), 
                 key=lambda x: x['pps'], default=None)
    
    if melhor:
        print(f"\nVELOCIDADE MAXIMA COM 90%+ SUCESSO:")
        print(f"  -> {melhor['pps']} pps")
        print(f"  -> {melhor['tempo_medio']:.2f}s por produto")
        print(f"  -> {melhor['taxa_sucesso']:.0f}% taxa de sucesso")
        print(f"  -> {melhor['estimativa_800']:.1f} minutos para 800 produtos")
        print(f"\nUSE NO extract_advanced.py:")
        print(f"  rate_limiter = LeakyBucket(pps={melhor['pps']}, jitter_frac=0.20)")
    
    with open('teste_turbo.json', 'w', encoding='utf-8') as f:
        json.dump(resultados, f, ensure_ascii=False, indent=2)
    
    print(f"\nResultados salvos em: teste_turbo.json")
    print("=" * 100)


if __name__ == "__main__":
    asyncio.run(testar_turbo())
