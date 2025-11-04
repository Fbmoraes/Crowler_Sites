#!/usr/bin/env python3
"""
TESTE CONSERVADOR FINAL - Encontrando velocidade REAL com 70%+ confiabilidade
==============================================================================

HIPOTESE: 1.2 pps funciona em teste curto (10 URLs) mas falha em teste longo (20 URLs)
OBJETIVO: Testar velocidades conservadoras em TESTE LONGO (50 URLs) para ver comportamento real

Velocidades a testar:
- 1.0 pps: ~1.0s entre reqs - CONSERVADOR
- 0.8 pps: ~1.25s entre reqs - MUITO CONSERVADOR
- 0.6 pps: ~1.67s entre reqs - ULTRA CONSERVADOR

URLs: 50 (mesmo que teste inicial que teve 100%)
"""

import asyncio
import httpx
import time
import random
import json
from datetime import datetime
from typing import Optional

# ================================================================================================
# LEAKY BUCKET COM FULL JITTER (AWS Best Practices)
# ================================================================================================
class LeakyBucket:
    """
    Rate limiter tipo LeakyBucket com Full Jitter.
    - Garante intervalo constante entre requisições
    - Full Jitter: adiciona variação aleatória para evitar thundering herd
    """
    def __init__(self, pps: float, jitter_frac: float = 0.20):
        self.base_interval = 1.0 / pps
        self.jitter_frac = jitter_frac
        self.next_slot = time.monotonic()
        self.lock = asyncio.Lock()
    
    async def acquire(self):
        async with self.lock:
            now = time.monotonic()
            wait = max(0, self.next_slot - now)
            
            if wait > 0:
                await asyncio.sleep(wait)
            
            # Full Jitter: AWS recommendation
            jitter_range = self.base_interval * self.jitter_frac
            jitter = random.uniform(-jitter_range, jitter_range)
            next_interval = self.base_interval + jitter
            
            self.next_slot = time.monotonic() + next_interval


# ================================================================================================
# EXTRAÇÃO HTML SSR (Server-Side Rendering)
# ================================================================================================
async def extrair_produto_html(client: httpx.AsyncClient, url: str, rate_limiter: LeakyBucket) -> dict:
    """
    Extrai dados do produto via HTML SSR.
    Retorna: {sucesso, tempo_resposta, erro_429, erro_msg}
    """
    await rate_limiter.acquire()
    
    start = time.perf_counter()
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8',
            'Connection': 'keep-alive',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
        }
        
        response = await client.get(url, headers=headers, timeout=20.0)
        elapsed = time.perf_counter() - start
        
        if response.status_code == 429:
            return {"sucesso": False, "tempo": elapsed, "erro_429": True, "erro_msg": "429 Too Many Requests"}
        
        if response.status_code == 200:
            html_size = len(response.text)
            # Verificar se HTML não está truncado (deve ter >100KB)
            if html_size < 100_000:
                return {"sucesso": False, "tempo": elapsed, "erro_429": False, "erro_msg": f"HTML muito pequeno: {html_size} bytes"}
            return {"sucesso": True, "tempo": elapsed, "erro_429": False, "erro_msg": None}
        
        return {"sucesso": False, "tempo": elapsed, "erro_429": False, "erro_msg": f"HTTP {response.status_code}"}
    
    except httpx.TimeoutException as e:
        elapsed = time.perf_counter() - start
        return {"sucesso": False, "tempo": elapsed, "erro_429": False, "erro_msg": "Timeout"}
    except httpx.ConnectError as e:
        elapsed = time.perf_counter() - start
        return {"sucesso": False, "tempo": elapsed, "erro_429": False, "erro_msg": f"Connection Error: {str(e)[:50]}"}
    except Exception as e:
        elapsed = time.perf_counter() - start
        return {"sucesso": False, "tempo": elapsed, "erro_429": False, "erro_msg": f"Erro: {str(e)[:50]}"}


# ================================================================================================
# TESTE COMPLETO
# ================================================================================================
async def testar_velocidade(pps: float, descricao: str, num_urls: int = 50) -> dict:
    """
    Testa uma velocidade específica com N URLs.
    """
    print(f"\n{'='*100}")
    print(f"TESTANDO: {pps} pps ({descricao})")
    print(f"{'='*100}")
    
    # URLs de teste (mesmas do teste inicial que teve 100%)
    urls_teste = [
        "https://www.casasbahia.com.br/geladeira-refrigerador-electrolux-frost-free-duplex-427l-prata-dw48x-1567087316/p/1567087316",
        "https://www.casasbahia.com.br/geladeira-refrigerador-electrolux-cycle-defrost-240l-branco-re31-1567091052/p/1567091052",
        "https://www.casasbahia.com.br/geladeira-refrigerador-electrolux-frost-free-duplex-435l-preto-dmre49bt-1567087238/p/1567087238",
        "https://www.casasbahia.com.br/geladeira-refrigerador-electrolux-frost-free-duplex-382l-inox-tf42s-1567087317/p/1567087317",
        "https://www.casasbahia.com.br/geladeira-refrigerador-electrolux-frost-free-duplex-453l-inox-df52x-1567087329/p/1567087329",
        "https://www.casasbahia.com.br/geladeira-refrigerador-electrolux-frost-free-duplex-427l-inox-df51x-1567087330/p/1567087330",
        "https://www.casasbahia.com.br/geladeira-refrigerador-electrolux-frost-free-290l-branco-re31-1567091062/p/1567091062",
        "https://www.casasbahia.com.br/geladeira-refrigerador-electrolux-frost-free-310l-branco-rfe39-1567087245/p/1567087245",
        "https://www.casasbahia.com.br/geladeira-refrigerador-brastemp-frost-free-duplex-400l-branco-brm54hb-1567087224/p/1567087224",
        "https://www.casasbahia.com.br/geladeira-refrigerador-brastemp-frost-free-duplex-478l-inox-bre59ak-1567087205/p/1567087205",
        "https://www.casasbahia.com.br/geladeira-refrigerador-brastemp-frost-free-duplex-500l-inox-brw59ae-1567087219/p/1567087219",
        "https://www.casasbahia.com.br/geladeira-refrigerador-brastemp-frost-free-duplex-375l-branco-brm44hb-1567087225/p/1567087225",
        "https://www.casasbahia.com.br/geladeira-refrigerador-consul-frost-free-duplex-405l-branco-crd46ab-1567087201/p/1567087201",
        "https://www.casasbahia.com.br/geladeira-refrigerador-consul-frost-free-duplex-340l-branco-crm39ab-1567087202/p/1567087202",
        "https://www.casasbahia.com.br/geladeira-refrigerador-consul-cycle-defrost-300l-branco-crc34gb-1567087203/p/1567087203",
        "https://www.casasbahia.com.br/geladeira-refrigerador-consul-frost-free-261l-branco-cra30fb-1567087204/p/1567087204",
        "https://www.casasbahia.com.br/geladeira-refrigerador-samsung-frost-free-duplex-384l-inox-rt38k5530s8-1567087206/p/1567087206",
        "https://www.casasbahia.com.br/geladeira-refrigerador-samsung-frost-free-duplex-453l-inox-rt46k6361sl-1567087207/p/1567087207",
        "https://www.casasbahia.com.br/geladeira-refrigerador-lg-frost-free-duplex-438l-aco-escovado-gr-x51mbms-1567087208/p/1567087208",
        "https://www.casasbahia.com.br/geladeira-refrigerador-lg-frost-free-duplex-509l-aco-escovado-gs65sdn-1567087209/p/1567087209",
        "https://www.casasbahia.com.br/geladeira-refrigerador-lg-frost-free-254l-aco-escovado-gn-b251slsw-1567087210/p/1567087210",
        "https://www.casasbahia.com.br/geladeira-refrigerador-panasonic-frost-free-duplex-435l-aco-escovado-nr-bt51pv3xa-1567087211/p/1567087211",
        "https://www.casasbahia.com.br/geladeira-refrigerador-midea-frost-free-duplex-404l-inox-mrd42x-1567087212/p/1567087212",
        "https://www.casasbahia.com.br/geladeira-refrigerador-philco-frost-free-duplex-340l-branco-prf340b-1567087213/p/1567087213",
        "https://www.casasbahia.com.br/geladeira-refrigerador-continental-cycle-defrost-320l-branco-tc35-1567087214/p/1567087214",
        "https://www.casasbahia.com.br/fogao-electrolux-4-bocas-branco-52sbx-1567087215/p/1567087215",
        "https://www.casasbahia.com.br/fogao-brastemp-5-bocas-inox-bfs5gcr-1567087216/p/1567087216",
        "https://www.casasbahia.com.br/fogao-consul-4-bocas-branco-cft520-1567087217/p/1567087217",
        "https://www.casasbahia.com.br/microondas-electrolux-31l-branco-mef41-1567087218/p/1567087218",
        "https://www.casasbahia.com.br/microondas-panasonic-32l-inox-nn-st65hsruk-1567087220/p/1567087220",
        "https://www.casasbahia.com.br/lavadora-electrolux-12kg-branca-lac12-1567087221/p/1567087221",
        "https://www.casasbahia.com.br/lavadora-brastemp-11kg-branca-bwj11ab-1567087222/p/1567087222",
        "https://www.casasbahia.com.br/lavadora-consul-16kg-branca-cwl16ab-1567087223/p/1567087223",
        "https://www.casasbahia.com.br/ar-condicionado-split-12000-btus-electrolux-ecoturbo-branco-vi12f-1567087226/p/1567087226",
        "https://www.casasbahia.com.br/ar-condicionado-split-9000-btus-samsung-inverter-branco-ar09tvhzdwk-1567087227/p/1567087227",
        "https://www.casasbahia.com.br/ar-condicionado-janela-7500-btus-consul-mecanico-ccb07eb-1567087228/p/1567087228",
        "https://www.casasbahia.com.br/televisao-samsung-55-4k-uhd-smart-un55au7700-1567087229/p/1567087229",
        "https://www.casasbahia.com.br/televisao-lg-50-4k-uhd-smart-50un7310psc-1567087230/p/1567087230",
        "https://www.casasbahia.com.br/notebook-dell-inspiron-i15-3501-a30p-intel-core-i3-4gb-256gb-ssd-15-6-windows-11-1567087231/p/1567087231",
        "https://www.casasbahia.com.br/notebook-lenovo-ideapad-3i-82md0008br-intel-core-i5-8gb-256gb-ssd-15-6-windows-11-1567087232/p/1567087232",
        "https://www.casasbahia.com.br/smartphone-samsung-galaxy-a54-5g-128gb-preto-1567087233/p/1567087233",
        "https://www.casasbahia.com.br/smartphone-motorola-moto-g23-128gb-azul-1567087234/p/1567087234",
        "https://www.casasbahia.com.br/ferro-de-passar-philco-pfv3100a-azul-1567087235/p/1567087235",
        "https://www.casasbahia.com.br/aspirador-de-po-electrolux-ease-c3-1400w-vermelho-eoc30-1567087236/p/1567087236",
        "https://www.casasbahia.com.br/ventilador-mallory-air-timer-ts-turbo-silence-40cm-preto-b94400921-1567087237/p/1567087237",
        "https://www.casasbahia.com.br/purificador-de-agua-electrolux-pe12b-branco-1567087239/p/1567087239",
        "https://www.casasbahia.com.br/cafeteira-nespresso-essenza-mini-branca-c30-br3-wh-ne-1567087240/p/1567087240",
        "https://www.casasbahia.com.br/liquidificador-philips-walita-daily-ri2110-2l-400w-preto-1567087241/p/1567087241",
        "https://www.casasbahia.com.br/batedeira-planetaria-philips-walita-ri7915-400w-vermelha-1567087242/p/1567087242",
        "https://www.casasbahia.com.br/panela-eletrica-de-arroz-britania-bpa5vi-5-xicaras-vermelha-1567087243/p/1567087243"
    ]
    
    # Limitar ao número solicitado
    urls = urls_teste[:num_urls]
    
    rate_limiter = LeakyBucket(pps=pps, jitter_frac=0.20)
    
    async with httpx.AsyncClient(
        follow_redirects=True,
        http2=False,
        limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
    ) as client:
        resultados = []
        
        for i, url in enumerate(urls, 1):
            resultado = await extrair_produto_html(client, url, rate_limiter)
            resultados.append(resultado)
            
            if resultado["sucesso"]:
                status = "OK "
            elif resultado["erro_429"]:
                status = "429"
            else:
                status = f"ERR ({resultado.get('erro_msg', 'Unknown')[:20]})"
            
            print(f"  [{i:2d}/{len(urls)}] {status} ({resultado['tempo']:.2f}s)")
        
        # Estatísticas
        sucessos = sum(1 for r in resultados if r["sucesso"])
        erros_429 = sum(1 for r in resultados if r["erro_429"])
        tempos_sucesso = [r["tempo"] for r in resultados if r["sucesso"]]
        tempo_medio = sum(tempos_sucesso) / len(tempos_sucesso) if tempos_sucesso else 0
        
        percentual = (sucessos / len(urls)) * 100
        estimativa_800 = (tempo_medio * 800) / 60  # minutos
        
        print(f"\nRESULTADO:")
        print(f"  Sucesso: {sucessos}/{len(urls)} ({percentual:.0f}%)")
        print(f"  Erros 429: {erros_429}")
        print(f"  Tempo médio: {tempo_medio:.2f}s/produto")
        print(f"  Estimativa 800 produtos: {estimativa_800:.1f} minutos")
        
        avaliacao = ""
        if percentual >= 90:
            avaliacao = "EXCELENTE! >=90% sucesso"
        elif percentual >= 70:
            avaliacao = "BOM! 70-89% sucesso - ACEITAVEL"
        else:
            avaliacao = "INSUFICIENTE! <70% sucesso"
        
        print(f"  -> {avaliacao}")
        
        return {
            "pps": pps,
            "descricao": descricao,
            "num_urls": len(urls),
            "sucessos": sucessos,
            "percentual": percentual,
            "erros_429": erros_429,
            "tempo_medio": tempo_medio,
            "estimativa_800": estimativa_800,
            "avaliacao": avaliacao
        }


# ================================================================================================
# MAIN
# ================================================================================================
async def main():
    print("="*100)
    print("TESTE CONSERVADOR FINAL - 50 URLs por velocidade")
    print("="*100)
    print("Objetivo: Encontrar velocidade REAL com 70%+ sucesso em teste longo")
    print("="*100)
    
    velocidades = [
        (1.0, "~1.0s entre reqs - CONSERVADOR"),
        (0.8, "~1.25s entre reqs - MUITO CONSERVADOR"),
        (0.6, "~1.67s entre reqs - ULTRA CONSERVADOR"),
    ]
    
    todos_resultados = []
    
    for pps, descricao in velocidades:
        resultado = await testar_velocidade(pps, descricao, num_urls=50)
        todos_resultados.append(resultado)
        
        # Se encontrar >=70% sucesso, testar velocidade acima
        if resultado["percentual"] >= 70:
            print(f"\n  >>> ENCONTROU! {pps} pps tem {resultado['percentual']:.0f}% sucesso")
            
            # Testar velocidade intermediária (pps + 0.1)
            if pps < 1.2:
                pps_teste = round(pps + 0.1, 1)
                print(f"\n  >>> Testando velocidade intermediária: {pps_teste} pps")
                resultado_inter = await testar_velocidade(
                    pps_teste, 
                    f"~{1.0/pps_teste:.2f}s entre reqs - TESTE INTERMEDIARIO",
                    num_urls=50
                )
                todos_resultados.append(resultado_inter)
            
            break
    
    # Resumo final
    print(f"\n{'='*100}")
    print("RESUMO FINAL - TODOS OS TESTES")
    print(f"{'='*100}")
    print(f"{'PPS':<6} | {'Tempo/prod':<12} | {'Sucesso':<10} | {'429s':<6} | {'800 prods':<12} | Avaliacao")
    print("-"*100)
    
    for r in todos_resultados:
        print(f"{r['pps']:<6.1f} | {r['tempo_medio']:>10.2f} s | {r['sucessos']:>3d}/{r['num_urls']:<3d} ({r['percentual']:>3.0f}%) | {r['erros_429']:>6d} | {r['estimativa_800']:>10.1f}min | {r['avaliacao']}")
    
    # Recomendação
    print(f"\n{'='*100}")
    print("RECOMENDACOES:")
    print(f"{'='*100}")
    
    melhores = [r for r in todos_resultados if r["percentual"] >= 70]
    
    if melhores:
        melhor = max(melhores, key=lambda x: x["pps"])  # Mais rápido com >=70%
        print(f"\n1. VELOCIDADE MAXIMA COM >=70% SUCESSO:")
        print(f"   -> {melhor['pps']} pps ({melhor['tempo_medio']:.2f}s/produto)")
        print(f"   -> Sucesso: {melhor['percentual']:.0f}%")
        print(f"   -> Estimativa 800 produtos: {melhor['estimativa_800']:.1f} minutos")
        print(f"   -> RECOMENDADO para producao!")
    else:
        mais_seguro = max(todos_resultados, key=lambda x: x["percentual"])
        print(f"\n1. NENHUMA VELOCIDADE ALCANCOU 70% SUCESSO")
        print(f"   -> Melhor resultado: {mais_seguro['pps']} pps ({mais_seguro['percentual']:.0f}% sucesso)")
        print(f"   -> Considere usar 0.3 pps (ja validado com 100% sucesso)")
    
    print(f"{'='*100}\n")
    
    # Salvar resultados
    with open("teste_conservador_final.json", "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "resultados": todos_resultados
        }, f, indent=2, ensure_ascii=False)
    
    print(f"Resultados salvos em: teste_conservador_final.json")
    print(f"{'='*100}\n")


if __name__ == "__main__":
    asyncio.run(main())
