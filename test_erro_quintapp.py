"""
Teste rápido do QuintApp para ver o erro
"""
import sys
import traceback

try:
    from extract_linksv8 import extrair_produtos
    
    def callback(msg):
        print(f"[LOG] {msg}")
    
    print("Testando Gigabarato...")
    produtos = extrair_produtos("https://www.gigabarato.com.br", callback, max_produtos=5)
    print(f"\nSucesso! {len(produtos)} produtos encontrados")
    
    if produtos:
        print("\nPrimeiros produtos:")
        for i, p in enumerate(produtos[:3], 1):
            print(f"{i}. {p['nome']}")
            print(f"   {p['url']}")

except Exception as e:
    print(f"\n❌ ERRO:")
    print(f"Tipo: {type(e).__name__}")
    print(f"Mensagem: {str(e)}")
    print(f"\nTraceback completo:")
    traceback.print_exc()
