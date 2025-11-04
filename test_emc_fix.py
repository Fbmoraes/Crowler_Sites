"""
Testar correção EMC Medical - Offers com O maiúsculo
"""
from extract_detailsv8 import extrair_detalhes_paralelo

# Mock callback
def callback(msg):
    print(f"[CALLBACK] {msg}")

produtos = [
    {'url': 'https://www.emcmedical.com.br/product-page/lumbamed-basic', 'nome': ''},
    {'url': 'https://www.emcmedical.com.br/product-page/cinta-para-coluna-lumbamed-disc', 'nome': ''},
]

print("=== Teste EMC Medical - Correção Offers ===\n")
tipo, resultados = extrair_detalhes_paralelo(produtos, callback, max_produtos=2, max_workers=2)

print(f"\n=== Resultados ===")
print(f"Tipo: {tipo}")
print(f"Total: {len(resultados)}\n")

for r in resultados:
    print(f"Nome: {r.get('nome', 'N/A')}")
    print(f"Preço: {r.get('preco', 'N/A')}")
    print(f"Marca: {r.get('marca', 'N/A')}")
    print(f"URL: {r.get('url')}")
    print("-" * 60)
