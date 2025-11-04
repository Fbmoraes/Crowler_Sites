"""
Testar correção CebModas - JavaScript vars
"""
from extract_detailsv8 import extrair_detalhes_paralelo

def callback(msg):
    print(f"[CALLBACK] {msg}")

produtos = [
    {'url': 'https://www.cebmodaseacessorios.com.br/boneca-minha-primeira-oracao', 'nome': ''},
    {'url': 'https://www.cebmodaseacessorios.com.br/chocalhobabybee-', 'nome': ''},
]

print("=== Teste CebModas - Correção JavaScript ===\n")
import time
start = time.time()

tipo, resultados = extrair_detalhes_paralelo(produtos, callback, max_produtos=2, max_workers=2)

elapsed = time.time() - start
print(f"\n=== Resultados ({elapsed:.1f}s) ===")
print(f"Tipo: {tipo}")
print(f"Total: {len(resultados)}\n")

for r in resultados:
    print(f"Nome: {r.get('nome', 'N/A')}")
    print(f"Preço: {r.get('preco', 'N/A')}")
    print(f"Marca: {r.get('marca', 'N/A')}")
    print(f"URL: {r.get('url')}")
    print("-" * 60)
