import httpx
from bs4 import BeautifulSoup
import json

print("=== ANÁLISE COMPLETA SACADA (VTEX) ===\n")

# 1. Testar sitemap
print("1. TESTANDO SITEMAP:")
try:
    resp = httpx.get('https://www.sacada.com/sitemap/sitemap-product-0.xml', timeout=15)
    soup = BeautifulSoup(resp.text, 'xml')
    urls = [loc.text for loc in soup.find_all('loc')[:5]]
    print(f"✓ Status: {resp.status_code}")
    print(f"✓ URLs encontradas: {len(soup.find_all('loc'))}")
    print(f"✓ Primeiras 3 URLs:")
    for url in urls[:3]:
        print(f"  - {url}")
except Exception as e:
    print(f"✗ Erro: {e}")

# 2. Testar produto individual
print("\n2. TESTANDO PRODUTO INDIVIDUAL:")
test_url = 'https://www.sacada.com/look-13-inverno-17/p'
try:
    resp = httpx.get(test_url, timeout=15, follow_redirects=True)
    print(f"✓ Status: {resp.status_code}")
    print(f"✓ Final URL: {resp.url}")
    print(f"✓ Size: {len(resp.text)} bytes")
    
    # Procurar por dados estruturados
    soup = BeautifulSoup(resp.text, 'html.parser')
    
    # a) JSON-LD
    json_ld = soup.find_all('script', type='application/ld+json')
    print(f"✓ JSON-LD scripts: {len(json_ld)}")
    
    # b) __RUNTIME__
    runtime_scripts = [s for s in soup.find_all('script') if '__RUNTIME__' in s.text]
    print(f"✓ __RUNTIME__ scripts: {len(runtime_scripts)}")
    if runtime_scripts:
        print("  → Contém dados React/VTEX hidratados")
    
    # c) __STATE__
    state_scripts = [s for s in soup.find_all('script') if '__STATE__' in s.text or '__NEXT_DATA__' in s.text]
    print(f"✓ __STATE__/__NEXT_DATA__: {len(state_scripts)}")
    
    # d) vtex.js
    vtex_scripts = [s for s in soup.find_all('script') if 'vtex' in s.get('src', '').lower()]
    print(f"✓ Scripts VTEX: {len(vtex_scripts)}")
    
except Exception as e:
    print(f"✗ Erro: {e}")

# 3. Testar API VTEX comum
print("\n3. TESTANDO API VTEX:")
api_endpoints = [
    'https://www.sacada.com/api/catalog_system/pub/products/search',
    'https://www.sacada.com/api/catalog/pvt/product/get/17',
]

for endpoint in api_endpoints:
    try:
        resp = httpx.get(endpoint, timeout=10)
        print(f"✓ {endpoint}")
        print(f"  Status: {resp.status_code}, Size: {len(resp.text)}")
        if resp.status_code == 200 and len(resp.text) > 10:
            try:
                data = resp.json()
                print(f"  → JSON válido: {type(data)}")
            except:
                print(f"  → HTML (não é API)")
    except Exception as e:
        print(f"✗ {endpoint}: {e}")

# 4. Extrair productId de URL real
print("\n4. EXTRAINDO productId DE URL REAL:")
try:
    # Pegar URL real do sitemap
    resp = httpx.get('https://www.sacada.com/sitemap/sitemap-product-0.xml', timeout=10)
    soup = BeautifulSoup(resp.text, 'xml')
    real_url = soup.find('loc').text if soup.find('loc') else test_url
    
    print(f"✓ URL teste: {real_url}")
    
    # Carregar página
    resp = httpx.get(real_url, timeout=15, follow_redirects=True)
    soup = BeautifulSoup(resp.text, 'html.parser')
    
    # Procurar productId no HTML
    html_text = resp.text
    
    # Padrões comuns VTEX
    patterns = [
        '"productId":"',
        '"productId":',
        'productId=',
        'product_id:',
    ]
    
    for pattern in patterns:
        if pattern in html_text:
            start = html_text.index(pattern) + len(pattern)
            end = start + 20
            snippet = html_text[start:end]
            print(f"✓ Encontrado {pattern}: {snippet}")
            break
    else:
        print("✗ ProductId não encontrado no HTML")
        
except Exception as e:
    print(f"✗ Erro: {e}")

print("\n=== FIM ANÁLISE ===")
