"""
Debug: Descobrir estrutura do MagnumAuto
"""
import httpx
from bs4 import BeautifulSoup

base = "https://www.magnumauto.com.br"

print("=== MagnumAuto - Descoberta ===\n")

# 1. Sitemap
print("1. Testando sitemap:")
sitemap_urls = [
    f"{base}/sitemap.xml",
    f"{base}/sitemap_index.xml",
    f"{base}/product-sitemap.xml",
]

for url in sitemap_urls:
    try:
        r = httpx.get(url, timeout=10, follow_redirects=True)
        if r.status_code == 200:
            print(f"   ✓ {url} - Status: {r.status_code}")
            soup = BeautifulSoup(r.text, 'xml')
            locs = soup.find_all('loc')
            print(f"     Total URLs: {len(locs)}")
            # Pega primeiras 3 URLs de produto
            product_urls = [loc.text for loc in locs if '/produto' in loc.text or '/product' in loc.text or 'magnumauto.com.br/' in loc.text][:3]
            if product_urls:
                print(f"     Exemplos:")
                for pu in product_urls:
                    print(f"       - {pu}")
        else:
            print(f"   ✗ {url} - Status: {r.status_code}")
    except Exception as e:
        print(f"   ✗ {url} - Erro: {e}")

# 2. Homepage
print("\n2. Homepage:")
try:
    r = httpx.get(base, timeout=10, follow_redirects=True)
    print(f"   Status: {r.status_code}")
    soup = BeautifulSoup(r.text, 'html.parser')
    
    # Buscar links de produtos
    product_links = []
    for a in soup.find_all('a', href=True):
        href = a['href']
        if href.startswith('/') and len(href) > 1:
            full_url = base + href
            if full_url not in product_links and '?' not in href:
                product_links.append(full_url)
    
    print(f"   Links únicos encontrados: {len(product_links)}")
    print("   Primeiros 5:")
    for link in product_links[:5]:
        print(f"     - {link}")
        
except Exception as e:
    print(f"   Erro: {e}")
