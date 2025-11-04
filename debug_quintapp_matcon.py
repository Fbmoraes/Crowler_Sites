"""
Debug do erro no QuintApp
"""
import traceback

print("=== Debug MatConcasa ===\n")

try:
    print("1. Importando módulo...")
    from extract_matcon_final import extrair_produtos, extrair_detalhes_paralelo
    print("   ✓ Importado com sucesso\n")
    
    print("2. Testando extrair_produtos...")
    urls = extrair_produtos('https://www.matconcasa.com.br', max_produtos=2)
    print(f"   ✓ {len(urls)} URLs encontradas\n")
    
    if urls:
        print("3. Testando extrair_detalhes_paralelo...")
        tipo, produtos = extrair_detalhes_paralelo(urls, max_produtos=1, max_workers=1)
        print(f"   ✓ Tipo: {tipo}")
        print(f"   ✓ Produtos: {len(produtos)}")
        
        if produtos:
            p = produtos[0]
            print(f"\n   Resultado:")
            print(f"   - Nome: {p.get('nome', 'N/A')}")
            print(f"   - Preço: {p.get('preco', 'N/A')}")
    
    print("\n✅ Tudo funcionando!")
    
except Exception as e:
    print(f"\n❌ ERRO: {e}")
    print(f"\nTraceback completo:")
    traceback.print_exc()
