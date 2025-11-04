"""
🔬 TESTE DE LIMITE - Encontrar ponto ótimo velocidade vs confiabilidade

Estratégia: Testar múltiplas velocidades com 10 URLs cada para encontrar:
1. Limite máximo (até começar ter 429s)
2. Ponto 90% confiabilidade
3. Ponto 70% confiabilidade

Velocidades testadas: 1.0, 0.8, 0.6, 0.5, 0.4 pps
"""

import asyncio
import httpx
import time
import json
import random
from bs4 import BeautifulSoup
import re
from typing import Dict, Any, Tuple

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]

PRECO_RE = re.compile(r'R\$\s*(?:<!--.*?-->)?\s*([\d.,]+)', re.DOTALL)
SKU_RE = re.compile(r'-(\d+)$')


class LeakyBucket:
    def __init__(self, pps: float, jitter_frac: float = 0.20):
        assert pps > 0
        self.base_interval = 1.0 / pps
        self.jitter_frac = jitter_frac
        self.next_slot = time.monotonic()
        self.lock = asyncio.Lock()

    async def acquire(self, retry_after_seconds: float = None):
        async with self.lock:
            now = time.monotonic()
            
            if retry_after_seconds and retry_after_seconds > 0:
                self.next_slot = max(self.next_slot, now + retry_after_seconds)

            delay = max(0.0, self.next_slot - now)
            if delay:
                await asyncio.sleep(delay)

            jitter = random.uniform(1 - self.jitter_frac, 1 + self.jitter_frac)
            self.next_slot = max(self.next_slot, time.monotonic()) + self.base_interval * jitter


async def extrair_simples(
    client: httpx.AsyncClient,
    url: str,
    rate_limiter: LeakyBucket,
    max_retries: int = 3
) -> Dict[str, Any]:
    """Extração simplificada para teste de velocidade"""
    
    retry_after = None
    
    for tentativa in range(max_retries):
        inicio = time.time()
        
        try:
            await rate_limiter.acquire(retry_after)
            
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
            
            if response.status_code == 429:
                if tentativa < max_retries - 1:
                    retry_after = min(60, (2 ** tentativa) * random.uniform(1.0, 3.0))
                    continue
                else:
                    return {
                        "erro": "HTTP 429",
                        "status": 429,
                        "url": url,
                        "tempo": time.time() - inicio,
                        "tentativas": tentativa + 1
                    }
            
            if response.status_code != 200:
                return {
                    "erro": f"HTTP {response.status_code}",
                    "status": response.status_code,
                    "url": url,
                    "tempo": time.time() - inicio
                }
            
            html = response.text
            
            if len(html) < 1000:
                if tentativa < max_retries - 1:
                    await asyncio.sleep(2 ** tentativa)
                    continue
                return {"erro": "HTML vazio", "url": url}
            
            # Extração mínima (só nome e preço)
            soup = BeautifulSoup(html, 'lxml' if 'lxml' in str(BeautifulSoup) else 'html.parser')
            
            nome = None
            h1_tags = soup.find_all('h1')
            if len(h1_tags) >= 2:
                nome = h1_tags[1].get_text(strip=True)
            elif h1_tags:
                nome = h1_tags[0].get_text(strip=True)
            
            precos = PRECO_RE.findall(html)
            preco = None
            if precos:
                precos_num = []
                for p in precos:
                    try:
                        valor = float(p.replace('.', '').replace(',', '.'))
                        if valor > 10:
                            precos_num.append((valor, p))
                    except:
                        pass
                if precos_num:
                    precos_num.sort(key=lambda x: x[0])
                    preco = precos_num[0][1]
            
            return {
                "nome": nome,
                "preco": preco,
                "tempo": time.time() - inicio,
                "tentativas": tentativa + 1,
                "url": url,
                "bytes": len(html)
            }
            
        except httpx.TimeoutException:
            if tentativa < max_retries - 1:
                await asyncio.sleep(2 ** tentativa)
                continue
            return {"erro": "Timeout", "url": url, "tempo": time.time() - inicio}
        except Exception as e:
            if tentativa < max_retries - 1:
                await asyncio.sleep(1)
                continue
            return {"erro": str(e), "url": url, "tempo": time.time() - inicio}
    
    return {"erro": "Max retries", "url": url}


async def testar_velocidade(pps: float, urls: list, label: str) -> Tuple[float, int, int, float]:
    """
    Testa uma velocidade específica
    Retorna: (taxa_sucesso, sucessos, erros_429, tempo_medio)
    """
    rate_limiter = LeakyBucket(pps=pps, jitter_frac=0.20)
    resultados = []
    erros_429 = 0
    
    async with httpx.AsyncClient(limits=httpx.Limits(max_connections=1, max_keepalive_connections=1)) as client:
        inicio_total = time.time()
        
        for idx, url in enumerate(urls, 1):
            produto = await extrair_simples(client, url, rate_limiter)
            resultados.append(produto)
            
            if 'erro' in produto:
                status = "429" if produto.get('status') == 429 else "ERR"
                if produto.get('status') == 429:
                    erros_429 += 1
                print(f"  [{idx:2d}/10] {status}")
            else:
                print(f"  [{idx:2d}/10] OK  ({produto.get('tempo', 0):.2f}s)")
        
        tempo_total = time.time() - inicio_total
    
    sucessos = sum(1 for r in resultados if 'erro' not in r)
    taxa_sucesso = sucessos / len(urls) * 100
    tempo_medio = tempo_total / len(urls)
    
    return taxa_sucesso, sucessos, erros_429, tempo_medio


async def teste_progressivo():
    """Teste progressivo para encontrar limites"""
    
    # Carregar 10 URLs para teste rápido
    with open('urls_matcon_100.txt', 'r', encoding='utf-8') as f:
        todas_urls = [line.strip() for line in f if line.strip()]
        urls_teste = todas_urls[:10]  # Primeiras 10
    
    print("=" * 100)
    print("TESTE DE LIMITE - Encontrando ponto otimo velocidade vs confiabilidade")
    print("=" * 100)
    print(f"URLs por teste: {len(urls_teste)}")
    print(f"Objetivo: Encontrar velocidade maxima com ~70-90% sucesso")
    print("=" * 100)
    print()
    
    # Velocidades a testar (do mais rápido ao mais lento)
    velocidades = [
        (1.2, "1.2 pps (~0.83s entre reqs) - MUITO AGRESSIVO"),
        (1.0, "1.0 pps (1.0s entre reqs) - AGRESSIVO"),
        (0.8, "0.8 pps (~1.25s entre reqs) - RAPIDO"),
        (0.6, "0.6 pps (~1.67s entre reqs) - MODERADO"),
        (0.5, "0.5 pps (2.0s entre reqs) - CONSERVADOR"),
        (0.4, "0.4 pps (~2.5s entre reqs) - MUITO CONSERVADOR"),
    ]
    
    resultados_finais = []
    
    for pps, label in velocidades:
        print(f"\n{'='*100}")
        print(f"TESTANDO: {label}")
        print(f"{'='*100}")
        
        taxa, sucessos, erros_429, tempo_medio = await testar_velocidade(pps, urls_teste, label)
        
        resultado = {
            "pps": pps,
            "label": label,
            "taxa_sucesso": taxa,
            "sucessos": sucessos,
            "erros_429": erros_429,
            "tempo_medio": tempo_medio,
            "estimativa_800": (tempo_medio * 800) / 60
        }
        resultados_finais.append(resultado)
        
        print(f"\nRESULTADO:")
        print(f"  Sucesso: {sucessos}/10 ({taxa:.0f}%)")
        print(f"  Erros 429: {erros_429}")
        print(f"  Tempo medio: {tempo_medio:.2f}s/produto")
        print(f"  Estimativa 800 produtos: {resultado['estimativa_800']:.1f} minutos")
        
        if taxa >= 90:
            print(f"  -> EXCELENTE! {taxa:.0f}% sucesso")
        elif taxa >= 70:
            print(f"  -> BOM! {taxa:.0f}% sucesso (70%+ target)")
        else:
            print(f"  -> RUIM! {taxa:.0f}% sucesso (abaixo do target)")
        
        # Se encontrarmos 100% sucesso, não precisa testar mais lento
        if taxa == 100 and pps >= 0.5:
            print(f"\n  >>> OTIMO! 100% sucesso em {pps} pps. Nao precisa testar mais lento.")
            break
    
    print(f"\n{'='*100}")
    print("RESUMO FINAL - TODOS OS TESTES")
    print(f"{'='*100}")
    print(f"{'PPS':<6} | {'Tempo/prod':<12} | {'Sucesso':<10} | {'429s':<6} | {'800 prods':<12} | Avaliacao")
    print("-" * 100)
    
    for r in resultados_finais:
        avaliacao = "EXCELENTE" if r['taxa_sucesso'] >= 90 else ("BOM" if r['taxa_sucesso'] >= 70 else "RUIM")
        print(f"{r['pps']:<6.1f} | {r['tempo_medio']:<12.2f}s | {r['taxa_sucesso']:>6.0f}% | "
              f"{r['erros_429']:>6d} | {r['estimativa_800']:>10.1f}min | {avaliacao}")
    
    print(f"\n{'='*100}")
    print("RECOMENDACOES:")
    print(f"{'='*100}")
    
    # Encontrar melhor opção por critério
    melhor_100 = next((r for r in resultados_finais if r['taxa_sucesso'] == 100), None)
    melhor_90 = next((r for r in resultados_finais if r['taxa_sucesso'] >= 90), None)
    melhor_70 = next((r for r in resultados_finais if r['taxa_sucesso'] >= 70), None)
    
    if melhor_100:
        print(f"\n1. MAXIMA VELOCIDADE COM 100% SUCESSO:")
        print(f"   -> {melhor_100['pps']} pps ({melhor_100['tempo_medio']:.2f}s/produto)")
        print(f"   -> Estimativa 800 produtos: {melhor_100['estimativa_800']:.1f} minutos")
        print(f"   -> RECOMENDADO para producao!")
    
    if melhor_90 and melhor_90 != melhor_100:
        print(f"\n2. VELOCIDADE COM 90%+ SUCESSO:")
        print(f"   -> {melhor_90['pps']} pps ({melhor_90['tempo_medio']:.2f}s/produto)")
        print(f"   -> Estimativa 800 produtos: {melhor_90['estimativa_800']:.1f} minutos")
        print(f"   -> Alternativa mais rapida com poucos erros")
    
    if melhor_70 and melhor_70 not in [melhor_100, melhor_90]:
        print(f"\n3. VELOCIDADE COM 70%+ SUCESSO:")
        print(f"   -> {melhor_70['pps']} pps ({melhor_70['tempo_medio']:.2f}s/produto)")
        print(f"   -> Estimativa 800 produtos: {melhor_70['estimativa_800']:.1f} minutos")
        print(f"   -> Target minimo de confiabilidade")
    
    print(f"\n{'='*100}")
    
    # Salvar resultados
    with open('teste_limites.json', 'w', encoding='utf-8') as f:
        json.dump(resultados_finais, f, ensure_ascii=False, indent=2)
    
    print(f"\nResultados salvos em: teste_limites.json")


if __name__ == "__main__":
    asyncio.run(teste_progressivo())
