"""
Debug Sacada - verificar por que não encontra produtos
"""

print("=== Debug Sacada ===\n")

try:
    from extract_sacada import extrair_produtos
    
    print("1. Testando extrair_produtos...")
    urls = extrair_produtos('https://www.sacada.com', max_produtos=10)
    
    print(f"\n✓ URLs encontradas: {len(urls)}")
    
    if urls:
        print("\nPrimeiras URLs:")
        for i, u in enumerate(urls[:5], 1):
            print(f"  {i}. {u.get('url', 'N/A')[:80]}")
    else:
        print("\n❌ PROBLEMA: Nenhuma URL encontrada!")
        print("\nTestando sitemap manualmente...")
        
        import httpx
        from bs4 import BeautifulSoup
        
        # Testar sitemap
        print("\n2. Verificando sitemap...")
        r = httpx.get('https://www.sacada.com/sitemap.xml', follow_redirects=True)
        print(f"   Status: {r.status_code}")
        
        soup = BeautifulSoup(r.text, 'xml')
        sitemaps = soup.find_all('loc')
        print(f"   Sitemaps encontrados: {len(sitemaps)}")
        
        product_sitemaps = [s.text for s in sitemaps if 'product' in s.text.lower()]
        print(f"   Sitemaps de produtos: {len(product_sitemaps)}")
        
        if product_sitemaps:
            print(f"\n   Exemplo: {product_sitemaps[0]}")
            
            # Testar primeiro sitemap de produtos
            r2 = httpx.get(product_sitemaps[0], follow_redirects=True)
            print(f"   Status sitemap produto: {r2.status_code}")
            
            soup2 = BeautifulSoup(r2.text, 'xml')
            urls_produtos = soup2.find_all('loc')
            print(f"   URLs de produtos: {len(urls_produtos)}")
            
            if urls_produtos:
                print(f"\n   Primeiras URLs:")
                for i, u in enumerate(urls_produtos[:3], 1):
                    print(f"     {i}. {u.text[:80]}")

except Exception as e:
    print(f"\n❌ ERRO: {e}")
    import traceback
    traceback.print_exc()
