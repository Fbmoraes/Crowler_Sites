"""
Debug MagnumAuto - 35 URLs mas N/A nos dados
"""
import httpx
from bs4 import BeautifulSoup
import json

url = "https://magnumauto.com.br/produto/l-a-10/"

print("=== Debug MagnumAuto ===\n")
print(f"URL: {url}\n")

r = httpx.get(url, follow_redirects=True, timeout=15)
print(f"Status: {r.status_code}")
print(f"Content-Type: {r.headers.get('content-type')}\n")

soup = BeautifulSoup(r.text, 'html.parser')

# 1. JSON-LD
print("1. JSON-LD:")
scripts = soup.find_all('script', type='application/ld+json')
print(f"   Scripts encontrados: {len(scripts)}")
for i, s in enumerate(scripts, 1):
    try:
        data = json.loads(s.string)
        print(f"\n   Script {i}:")
        print(f"   Type: {data.get('@type')}")
        if data.get('@type') == 'Product':
            print(f"   Nome: {data.get('name', 'N/A')}")
            offers = data.get('offers', {})
            if isinstance(offers, dict):
                print(f"   Preço: {offers.get('price', offers.get('lowPrice', 'N/A'))}")
            print(f"   Marca: {data.get('brand', {}).get('name', 'N/A')}")
    except:
        print(f"   Script {i}: Erro ao parsear")

# 2. OpenGraph
print("\n2. OpenGraph:")
og_title = soup.find('meta', property='og:title')
og_price = soup.find('meta', property='og:price:amount')
print(f"   Title: {og_title.get('content') if og_title else 'N/A'}")
print(f"   Price: {og_price.get('content') if og_price else 'N/A'}")

# 3. HTML Prices
print("\n3. Seletores de Preço:")
price_selectors = [
    '[class*="price"]', '[class*="Price"]', '[class*="valor"]',
    '[itemprop="price"]', '[data-price]'
]
for sel in price_selectors:
    elements = soup.select(sel)
    if elements:
        print(f"   {sel}: {len(elements)} encontrados")
        for el in elements[:2]:
            print(f"      - {el.get_text(strip=True)[:50]}")

# 4. Title e H1
print("\n4. Title e H1:")
title = soup.find('title')
h1 = soup.find('h1')
print(f"   Title: {title.get_text(strip=True) if title else 'N/A'}")
print(f"   H1: {h1.get_text(strip=True) if h1 else 'N/A'}")

# 5. Salvar HTML
with open('debug_magnumauto.html', 'w', encoding='utf-8') as f:
    f.write(r.text)
print(f"\n✓ HTML salvo em: debug_magnumauto.html")
