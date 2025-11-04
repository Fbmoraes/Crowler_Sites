"""
Testar Sacada com descoberta por categorias
"""
from extract_sacada import extrair_produtos, extrair_detalhes_paralelo

print("=== Teste Sacada - Descoberta por Categorias ===\n")

# Descobrir produtos
produtos = extrair_produtos('https://www.sacada.com/', max_produtos=5)

print(f"\n=== Produtos Descobertos: {len(produtos)} ===\n")
for p in produtos[:5]:
    print(f"  - {p['nome'][:50]}")
    print(f"    {p['url']}")

if produtos:
    print(f"\n=== Extraindo Detalhes ===\n")
    
    def callback(msg):
        print(f"[CALLBACK] {msg}")
    
    tipo, resultados = extrair_detalhes_paralelo(produtos[:3], callback, max_produtos=3, max_workers=2)
    
    print(f"\n=== Resultados ===")
    print(f"Tipo: {tipo}\n")
    
    for r in resultados:
        print(f"Nome: {r.get('nome', 'N/A')}")
        print(f"Preço: {r.get('preco', 'N/A')}")
        print(f"Marca: {r.get('marca', 'N/A')}")
        print(f"Categoria: {r.get('categoria', 'N/A')}")
        print(f"URL: {r.get('url')}")
        print("-" * 70)
