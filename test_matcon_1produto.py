"""
Teste do extrator completo com 1 produto
"""
from extract_matcon_final import extrair_produtos, extrair_detalhes_paralelo

print("=== Teste MatConcasa Final (1 produto) ===\n")

print("1. Descobrindo URLs...")
urls = extrair_produtos("https://www.matconcasa.com.br", max_produtos=1)
print(f"   ✓ {len(urls)} URL encontrada")
print(f"   URL: {urls[0]['url']}\n")

print("2. Extraindo detalhes...")
tipo, produtos = extrair_detalhes_paralelo(urls, max_produtos=1, max_workers=1)

print(f"\n=== Resultados ===")
print(f"Tipo: {tipo}")
print(f"Produtos: {len(produtos)}")

if produtos:
    p = produtos[0]
    print(f"\n📦 Produto:")
    print(f"   URL: {p.get('url', 'N/A')[:80]}")
    print(f"   Nome: {p.get('nome', 'N/A')}")
    print(f"   Preço: R$ {p.get('preco', 'N/A')}")
    print(f"   Categoria: {p.get('categoria', 'N/A')}")
    print(f"   Imagem: {'✓' if p.get('imagem') else '✗'}")
    
    if p.get('nome') and p.get('preco'):
        print(f"\n✅ SUCESSO! Dados extraídos corretamente")
    else:
        print(f"\n⚠️ ATENÇÃO: Alguns dados faltando")
else:
    print("\n❌ Nenhum produto extraído")
