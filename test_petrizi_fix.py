"""
Teste rápido do fix do Petrizi
"""

print("Testando Petrizi...")

try:
    from extract_petrizi import extrair_produtos
    
    print("✅ Import OK")
    
    # Testa se a função é síncrona agora
    import inspect
    if inspect.iscoroutinefunction(extrair_produtos):
        print("❌ ERRO: extrair_produtos ainda é async!")
    else:
        print("✅ extrair_produtos é síncrona")
    
    # Testa chamada (limitado a 3 produtos)
    print("\nTestando extração de 3 produtos...")
    produtos = extrair_produtos("https://www.petrizi.com.br", max_produtos=3)
    
    print(f"\n✅ Sucesso! {len(produtos)} produtos extraídos")
    
    if produtos:
        print("\nPrimeiro produto:")
        p = produtos[0]
        print(f"  Nome: {p.get('nome', 'N/A')}")
        print(f"  Preço: R$ {p.get('preco', 0):.2f}")
        print(f"  Marca: {p.get('marca', 'N/A')}")
        
except Exception as e:
    print(f"❌ Erro: {e}")
    import traceback
    traceback.print_exc()
