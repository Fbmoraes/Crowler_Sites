"""
Teste de integração dos extratores no QuintApp
"""

# Testa imports
try:
    from extract_linksv8 import extrair_produtos as extrair_produtos_generico
    print("✅ Extrator genérico OK")
except Exception as e:
    print(f"❌ Extrator genérico: {e}")

try:
    from extract_dermo_quintapp import extrair_produtos as extrair_produtos_dermo
    print("✅ Extrator Dermomanipulações OK")
    DERMO_DISPONIVEL = True
except Exception as e:
    print(f"❌ Extrator Dermomanipulações: {e}")
    DERMO_DISPONIVEL = False

try:
    from extract_katsukazan import extrair_produtos as extrair_produtos_katsukazan
    print("✅ Extrator Katsukazan OK")
    KATSUKAZAN_DISPONIVEL = True
except Exception as e:
    print(f"❌ Extrator Katsukazan: {e}")
    KATSUKAZAN_DISPONIVEL = False

# Testa detecção
def detectar_extrator(url: str):
    url_lower = url.lower()
    
    if 'dermomanipulacoes' in url_lower and DERMO_DISPONIVEL:
        return 'dermo', extrair_produtos_dermo
    
    if 'katsukazan' in url_lower and KATSUKAZAN_DISPONIVEL:
        return 'katsukazan', extrair_produtos_katsukazan
    
    return 'generico', extrair_produtos_generico

# Testa URLs
print("\n" + "=" * 60)
print("TESTE DE DETECÇÃO DE EXTRATORES")
print("=" * 60)

urls_teste = [
    "https://www.dermomanipulacoes.com.br",
    "https://katsukazan.com.br",
    "https://www.gigabarato.com.br",
    "https://www.sacada.com"
]

for url in urls_teste:
    tipo, fn = detectar_extrator(url)
    print(f"\n{url}")
    print(f"  → Extrator: {tipo}")

# Testa extração rápida
print("\n" + "=" * 60)
print("TESTE RÁPIDO DE EXTRAÇÃO")
print("=" * 60)

print("\n1. Katsukazan (5 produtos):")
if KATSUKAZAN_DISPONIVEL:
    produtos = extrair_produtos_katsukazan("https://katsukazan.com.br", None, 5)
    print(f"   ✅ {len(produtos)} produtos extraídos")
    if produtos:
        print(f"   Exemplo: {produtos[0].get('nome', 'N/A')[:50]} - {produtos[0].get('preco', 'N/A')}")
else:
    print("   ⚠️ Extrator não disponível")

print("\n2. Dermomanipulações (5 produtos):")
if DERMO_DISPONIVEL:
    produtos = extrair_produtos_dermo("https://www.dermomanipulacoes.com.br", None, 5)
    print(f"   ✅ {len(produtos)} produtos extraídos")
    if produtos:
        print(f"   Exemplo: {produtos[0].get('nome', 'N/A')[:50]} - {produtos[0].get('preco', 'N/A')}")
else:
    print("   ⚠️ Extrator não disponível")

print("\n✅ Todos os testes concluídos!")
