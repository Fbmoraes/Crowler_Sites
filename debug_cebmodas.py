"""
Debug CebModas - site lento (173s para 7 produtos)
"""
import httpx
from bs4 import BeautifulSoup
import time

base = "https://www.cebmodaseacessorios.com.br"

print("=== CebModas - Investigação ===\n")

# 1. Sitemap
print("1. Testando sitemap...")
start = time.time()
try:
    r = httpx.get(f"{base}/sitemap.xml", timeout=15, follow_redirects=True)
    elapsed = time.time() - start
    print(f"   Status: {r.status_code} ({elapsed:.1f}s)")
    
    if r.status_code == 200:
        soup = BeautifulSoup(r.text, 'xml')
        locs = [l.text for l in soup.find_all('loc')]
        print(f"   URLs: {len(locs)}")
        
        # URLs de produto
        product_urls = [l for l in locs if '/produto/' in l or '/product/' in l]
        if not product_urls:
            product_urls = [l for l in locs if l != base][:3]
        
        print(f"   URLs de produto (primeiras 3): {len(product_urls)}")
        for url in product_urls[:3]:
            print(f"     - {url}")
        
        if product_urls:
            # Testar um produto
            url = product_urls[0]
            print(f"\n2. Testando produto: {url}")
            
            start = time.time()
            r = httpx.get(url, timeout=30, follow_redirects=True)
            elapsed = time.time() - start
            
            print(f"   Status: {r.status_code} ({elapsed:.1f}s)")
            print(f"   Content-Length: {len(r.text)} bytes")
            
            soup = BeautifulSoup(r.text, 'html.parser')
            
            # JSON-LD
            scripts = soup.find_all('script', type='application/ld+json')
            print(f"   JSON-LD scripts: {len(scripts)}")
            
            if scripts:
                import json
                for i, s in enumerate(scripts, 1):
                    try:
                        data = json.loads(s.string)
                        tipo = data.get('@type')
                        print(f"   Script {i} - Type: {tipo}")
                        if tipo == 'Product':
                            print(f"     Nome: {data.get('name', 'N/A')[:60]}")
                            print(f"     Marca: {data.get('brand', {}).get('name', 'N/A')}")
                            offers = data.get('offers') or data.get('Offers', {})
                            if isinstance(offers, dict):
                                print(f"     Preço: {offers.get('price', 'N/A')}")
                    except Exception as e:
                        print(f"   Script {i}: Erro - {e}")
            
            # Salvar HTML
            with open('debug_cebmodas.html', 'w', encoding='utf-8') as f:
                f.write(r.text)
            print(f"\n   ✓ HTML salvo: debug_cebmodas.html")
            
except Exception as e:
    elapsed = time.time() - start
    print(f"   Erro ({elapsed:.1f}s): {e}")
