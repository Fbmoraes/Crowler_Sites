"""
Diagnóstico rápido: EMC Medical
"""
import requests
from bs4 import BeautifulSoup

url = "https://www.emcmedical.com.br"
print("="*60)
print("DIAGNÓSTICO: EMC MEDICAL")
print("="*60)

try:
    print(f"\n1️⃣ Homepage: {url}")
    r = requests.get(url, timeout=15)
    print(f"   Status: {r.status_code}")
    
    # Detectar plataforma
    text = r.text.lower()
    plataformas = {
        'vtex': 'VTEX',
        'shopify': 'Shopify', 
        'tray': 'Tray',
        'woocommerce': 'WooCommerce',
        'nuvemshop': 'Nuvemshop',
        'magento': 'Magento'
    }
    
    for key, name in plataformas.items():
        if key in text:
            print(f"   ✅ Plataforma: {name}")
            break
    
    # Testar sitemap
    print(f"\n2️⃣ Sitemap:")
    try:
        r2 = requests.get(f"{url}/sitemap.xml", timeout=10)
        if r2.status_code == 200:
            print(f"   ✅ Encontrado - {r2.text.count('<loc>')} URLs")
        else:
            print(f"   ❌ Não encontrado ({r2.status_code})")
    except:
        print(f"   ❌ Erro ao acessar")
    
    # Buscar produtos na homepage
    print(f"\n3️⃣ Produtos na homepage:")
    soup = BeautifulSoup(r.text, 'html.parser')
    
    links = []
    for a in soup.find_all('a', href=True):
        href = a['href']
        if any(x in href.lower() for x in ['/produto/', '/product/', '/p/']):
            if href.startswith('http'):
                links.append(href)
            elif href.startswith('/'):
                links.append(url + href)
    
    print(f"   Links encontrados: {len(links)}")
    
    if links:
        # Testar um produto
        print(f"\n4️⃣ Testando produto: {links[0][:80]}...")
        r3 = requests.get(links[0], timeout=10)
        soup2 = BeautifulSoup(r3.text, 'html.parser')
        
        jsons = soup2.find_all('script', type='application/ld+json')
        print(f"   JSON-LD: {len(jsons)} scripts")
        
        if jsons:
            import json
            for s in jsons:
                try:
                    data = json.loads(s.string)
                    if data.get('@type') == 'Product':
                        print(f"   ✅ Product JSON-LD encontrado!")
                        print(f"   Nome: {data.get('name', 'N/A')[:50]}")
                        offers = data.get('offers', {})
                        if isinstance(offers, dict):
                            print(f"   Preço: R$ {offers.get('price', 'N/A')}")
                except:
                    pass
        
        # Verificar preço no HTML
        price_count = r3.text.count('R$')
        print(f"   Linhas com R$: {price_count}")
    
except Exception as e:
    print(f"❌ Erro: {e}")
