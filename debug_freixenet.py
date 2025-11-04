"""
Debug Freixenet - Verificar estrutura de preços
"""
import httpx
from bs4 import BeautifulSoup
import json

url = 'https://www.freixenet.com.br/italian-rose-750ml-8410036806934/p'

print(f"Testando: {url}\n")

try:
    r = httpx.get(url, timeout=15, follow_redirects=True)
    print(f"Status: {r.status_code}\n")
    
    soup = BeautifulSoup(r.text, 'html.parser')
    
    # JSON-LD
    print("="*60)
    print("JSON-LD Scripts")
    print("="*60)
    scripts = soup.find_all('script', type='application/ld+json')
    print(f"Encontrados: {len(scripts)}\n")
    
    for i, script in enumerate(scripts, 1):
        if script.string:
            try:
                data = json.loads(script.string)
                print(f"Script {i}:")
                print(f"  Type: {data.get('@type', 'N/A')}")
                
                if data.get('@type') == 'Product':
                    print(f"  Nome: {data.get('name', 'N/A')}")
                    offers = data.get('offers', {})
                    print(f"  Offers: {offers}")
                    if isinstance(offers, dict):
                        print(f"    price: {offers.get('price', 'N/A')}")
                        print(f"    priceCurrency: {offers.get('priceCurrency', 'N/A')}")
                        print(f"    availability: {offers.get('availability', 'N/A')}")
                print()
            except:
                print(f"Script {i}: Erro ao parsear JSON")
                print(script.string[:200])
                print()
    
    # OpenGraph
    print("="*60)
    print("OpenGraph Meta Tags")
    print("="*60)
    og_tags = soup.find_all('meta', property=lambda x: x and 'og:' in x)
    for tag in og_tags:
        print(f"  {tag.get('property')}: {tag.get('content')}")
    
    # HTML Preço
    print("\n" + "="*60)
    print("HTML - Seletores de Preço")
    print("="*60)
    
    # Procura por classes comuns de preço
    price_selectors = [
        {'class': lambda x: x and 'price' in x.lower()},
        {'class': lambda x: x and 'preco' in x.lower()},
        {'itemprop': 'price'},
        {'class': 'sellingPrice'},
        {'class': 'bestPrice'},
    ]
    
    for selector in price_selectors:
        elements = soup.find_all(attrs=selector)
        if elements:
            print(f"\nSeletor {selector}:")
            for elem in elements[:3]:
                print(f"  Tag: {elem.name}")
                print(f"  Class: {elem.get('class')}")
                print(f"  Text: {elem.get_text(strip=True)[:100]}")
                print(f"  Content attr: {elem.get('content')}")
                print()

except Exception as e:
    print(f"Erro: {e}")
    import traceback
    traceback.print_exc()
