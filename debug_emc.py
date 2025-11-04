"""
Debug EMC Medical - Marca funciona, preço N/A
"""
import httpx
from bs4 import BeautifulSoup
import json

# Primeiro encontrar uma URL de produto
print("=== EMC Medical ===\n")
print("1. Buscando sitemap...")

base = "https://www.emcmedical.com.br"
r = httpx.get(f"{base}/sitemap.xml", timeout=10)
soup = BeautifulSoup(r.text, 'xml')
locs = [l.text for l in soup.find_all('loc')]

product_urls = [l for l in locs if '/produto' in l or '/product' in l or (base in l and '/' != l.split(base)[1])][:3]
if not product_urls:
    # Pega qualquer URL que não seja o base
    product_urls = [l for l in locs if l != base and l != f"{base}/"][:3]

print(f"   URLs encontradas: {len(locs)}")
print(f"   URLs de produto (primeiras 3): {len(product_urls)}")
for url in product_urls:
    print(f"     - {url}")

if product_urls:
    url = product_urls[0]
    print(f"\n2. Analisando: {url}\n")
    
    r = httpx.get(url, follow_redirects=True, timeout=15)
    print(f"   Status: {r.status_code}")
    
    soup = BeautifulSoup(r.text, 'html.parser')
    
    # JSON-LD
    print("\n   JSON-LD:")
    scripts = soup.find_all('script', type='application/ld+json')
    print(f"   Scripts: {len(scripts)}")
    for i, s in enumerate(scripts, 1):
        try:
            data = json.loads(s.string)
            tipo = data.get('@type')
            print(f"   Script {i} - Type: {tipo}")
            if tipo == 'Product':
                print(f"     Nome: {data.get('name', 'N/A')}")
                print(f"     Marca: {data.get('brand', {}).get('name', 'N/A')}")
                offers = data.get('offers', {})
                if isinstance(offers, dict):
                    print(f"     Preço: {offers.get('price', offers.get('lowPrice', 'N/A'))}")
                    print(f"     Offers keys: {list(offers.keys())}")
        except Exception as e:
            print(f"   Script {i}: Erro - {e}")
    
    # OpenGraph
    print("\n   OpenGraph:")
    for prop in ['og:price:amount', 'product:price:amount']:
        meta = soup.find('meta', property=prop)
        if meta:
            print(f"     {prop}: {meta.get('content')}")
    
    # R$ no texto
    print("\n   Elementos com R$:")
    rs_elements = soup.find_all(string=lambda t: t and 'R$' in t)
    print(f"     Total: {len(rs_elements)}")
    for el in rs_elements[:3]:
        print(f"       - {el.strip()[:80]}")
    
    # Salvar HTML
    with open('debug_emc.html', 'w', encoding='utf-8') as f:
        f.write(r.text)
    print(f"\n   ✓ HTML salvo: debug_emc.html")
