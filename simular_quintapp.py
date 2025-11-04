"""
Simulação do QuintApp com extratores integrados
Testa múltiplas plataformas simultaneamente
"""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed

# Imports dos extratores
from extract_linksv8 import extrair_produtos as extrair_produtos_generico
from extract_dermo_quintapp import extrair_produtos as extrair_produtos_dermo
from extract_katsukazan import extrair_produtos as extrair_produtos_katsukazan

def detectar_extrator(url: str):
    """Detecta qual extrator usar"""
    url_lower = url.lower()
    
    if 'dermomanipulacoes' in url_lower:
        return 'dermo', extrair_produtos_dermo
    
    if 'katsukazan' in url_lower:
        return 'katsukazan', extrair_produtos_katsukazan
    
    return 'generico', extrair_produtos_generico


def processar_plataforma(url: str, max_produtos: int = 10):
    """Processa uma plataforma"""
    inicio = time.time()
    
    try:
        tipo, extrair_fn = detectar_extrator(url)
        nome = url.split('//')[-1].split('/')[0]
        
        print(f"\n[{nome}] Iniciando com extrator '{tipo}'...")
        
        produtos = extrair_fn(url, None, max_produtos)
        
        tempo = time.time() - inicio
        
        return {
            'url': url,
            'nome': nome,
            'tipo_extrator': tipo,
            'sucesso': True,
            'produtos': len(produtos),
            'tempo': tempo,
            'produtos_por_segundo': len(produtos) / tempo if tempo > 0 else 0
        }
    
    except Exception as e:
        tempo = time.time() - inicio
        return {
            'url': url,
            'nome': url.split('//')[-1].split('/')[0],
            'tipo_extrator': 'erro',
            'sucesso': False,
            'produtos': 0,
            'tempo': tempo,
            'erro': str(e)
        }


def main():
    print("=" * 70)
    print("SIMULAÇÃO QUINTAPP - PROCESSAMENTO PARALELO")
    print("=" * 70)
    
    # URLs de teste
    urls = [
        "https://www.dermomanipulacoes.com.br",
        "https://katsukazan.com.br",
        "https://www.gigabarato.com.br"
    ]
    
    max_produtos_por_site = 10
    max_threads = 3
    
    print(f"\nConfigurações:")
    print(f"  - Sites: {len(urls)}")
    print(f"  - Produtos por site: {max_produtos_por_site}")
    print(f"  - Threads paralelas: {max_threads}")
    
    inicio_total = time.time()
    resultados = []
    
    # Processa em paralelo
    with ThreadPoolExecutor(max_workers=max_threads) as executor:
        futures = {
            executor.submit(processar_plataforma, url, max_produtos_por_site): url 
            for url in urls
        }
        
        for future in as_completed(futures):
            resultado = future.result()
            resultados.append(resultado)
            
            if resultado['sucesso']:
                print(f"\n✅ {resultado['nome']}")
                print(f"   Extrator: {resultado['tipo_extrator']}")
                print(f"   Produtos: {resultado['produtos']}")
                print(f"   Tempo: {resultado['tempo']:.1f}s")
                print(f"   Velocidade: {resultado['produtos_por_segundo']:.1f} prod/s")
            else:
                print(f"\n❌ {resultado['nome']}")
                print(f"   Erro: {resultado['erro'][:80]}")
    
    tempo_total = time.time() - inicio_total
    
    # Resumo final
    print("\n" + "=" * 70)
    print("RESUMO FINAL")
    print("=" * 70)
    
    sucesso = [r for r in resultados if r['sucesso']]
    falhas = [r for r in resultados if not r['sucesso']]
    
    print(f"\n✅ Sucessos: {len(sucesso)}/{len(resultados)}")
    print(f"❌ Falhas: {len(falhas)}/{len(resultados)}")
    print(f"\n⏱️ Tempo total: {tempo_total:.1f}s")
    
    if sucesso:
        total_produtos = sum(r['produtos'] for r in sucesso)
        print(f"📦 Total de produtos: {total_produtos}")
        print(f"🚀 Velocidade média: {total_produtos / tempo_total:.1f} produtos/segundo")
        
        print("\n📊 Detalhamento por extrator:")
        for tipo in ['dermo', 'katsukazan', 'generico']:
            sites = [r for r in sucesso if r['tipo_extrator'] == tipo]
            if sites:
                prods = sum(s['produtos'] for s in sites)
                tempo_medio = sum(s['tempo'] for s in sites) / len(sites)
                print(f"   {tipo.capitalize()}: {len(sites)} sites, {prods} produtos, {tempo_medio:.1f}s médio")
    
    print("\n✅ Simulação concluída!")


if __name__ == "__main__":
    main()
