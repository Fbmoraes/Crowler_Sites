"""
Teste: extract_linksv8 com Freixenet
"""
from extract_linksv8 import extrair_produtos

def callback(msg):
    print(msg)

print("Testando Freixenet com extract_linksv8 melhorado...")
print("=" * 60)

produtos = extrair_produtos("https://www.freixenet.com.br", callback, max_produtos=None)

print("\n" + "=" * 60)
print(f"RESULTADO: {len(produtos)} produtos encontrados")
print("=" * 60)

if produtos:
    print("\nPrimeiros 10 produtos:")
    for i, p in enumerate(produtos[:10], 1):
        print(f"{i}. {p['nome']}")
        print(f"   {p['url']}")
