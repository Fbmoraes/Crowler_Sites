"""
Teste do Discovery Mode para MatConcasa
"""

import sys
sys.path.insert(0, r'c:\Users\adria\OneDrive\Documents\projetometa\Crowler_Sites')

print("Testando MatConcasa Discovery Mode...\n")

try:
    from quintapp import extrair_urls_homepage_sync
    
    print("✅ Import OK")
    
    # Testa discovery mode
    print("\n🌐 Testando discovery (limite 10 produtos)...")
    urls = extrair_urls_homepage_sync("https://www.matconcasa.com.br", max_produtos=10)
    
    print(f"\n✅ Sucesso! {len(urls)} URLs encontradas")
    
    if urls:
        print("\nPrimeiras 5 URLs:")
        for i, url in enumerate(urls[:5], 1):
            print(f"  {i}. {url}")
    else:
        print("\n⚠️ Nenhuma URL encontrada - pode ser problema com Playwright")
        
except Exception as e:
    print(f"\n❌ Erro: {e}")
    import traceback
    traceback.print_exc()
