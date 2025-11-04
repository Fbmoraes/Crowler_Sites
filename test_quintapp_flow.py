"""
Simular exatamente o que QuintApp faz
"""
import traceback
from extract_matcon_final import extrair_produtos, extrair_detalhes_paralelo

print("=== Simulação QuintApp ===\n")

url = "https://www.matconcasa.com.br"

try:
    # Fase 1: Extração de links (como QuintApp faz)
    print("1. Extração de links...")
    produtos_links = extrair_produtos(url, callback=None, max_produtos=3)
    print(f"   ✓ {len(produtos_links)} produtos encontrados")
    print(f"   Formato: {type(produtos_links[0]) if produtos_links else 'vazio'}")
    
    if produtos_links:
        print(f"   Exemplo: {produtos_links[0]}")
    
    # Fase 2: Extração de detalhes (como QuintApp faz)
    print("\n2. Extração de detalhes...")
    print(f"   Chamando: extrair_detalhes_paralelo(produtos_links, None, 1, 20)")
    
    tipo, detalhes = extrair_detalhes_paralelo(
        produtos_links,
        callback=None,
        max_produtos=1,
        max_workers=1  # Reduzir para debug
    )
    
    print(f"   ✓ Tipo: {tipo}")
    print(f"   ✓ Detalhes: {len(detalhes)}")
    
    if detalhes:
        d = detalhes[0]
        print(f"\n   Resultado:")
        for k, v in d.items():
            print(f"   - {k}: {v if len(str(v)) < 60 else str(v)[:60]+'...'}")
    
    print("\n✅ Sucesso!")

except Exception as e:
    print(f"\n❌ ERRO: {e}")
    print(f"\nTraceback:")
    traceback.print_exc()
