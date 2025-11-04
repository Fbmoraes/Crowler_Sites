import httpx
from bs4 import BeautifulSoup

url = "https://www.matconcasa.com.br/produto/ducha-hydra-optima-8-temperaturas-5500w-127v-dpop-8-551br-362905"

r = httpx.get(url, timeout=15, follow_redirects=True)
soup = BeautifulSoup(r.text, 'html.parser')

print(f"Status: {r.status_code}\n")

# JSON-LD
scripts = soup.find_all('script', type='application/ld+json')
print(f"JSON-LD Scripts: {len(scripts)}\n")

# OpenGraph
print("=== OpenGraph Tags ===")
for tag in soup.find_all('meta', property=lambda x: x and x.startswith('og:')):
    if tag.get('content'):
        print(f"{tag.get('property')}: {tag.get('content')[:100]}")

# Meta product
print("\n=== Product Meta Tags ===")
for tag in soup.find_all('meta', attrs={'name': lambda x: x and 'product' in x.lower() if x else False}):
    print(f"{tag.get('name')}: {tag.get('content', 'N/A')[:100]}")

# Price selectors
print("\n=== Price Selectors ===")
prices = soup.select('[class*="price"], [class*="Price"], [class*="valor"]')
for p in prices[:5]:
    print(f"{p.get('class')}: {p.get_text(strip=True)[:50]}")

# Title
print("\n=== Title ===")
title = soup.find('title')
if title:
    print(title.get_text(strip=True))

# H1
print("\n=== H1 ===")
h1 = soup.find('h1')
if h1:
    print(h1.get_text(strip=True))

# Look for data attributes
print("\n=== Data Attributes (price, product) ===")
for tag in soup.find_all(attrs={'data-price': True}):
    print(f"data-price: {tag.get('data-price')}")
for tag in soup.find_all(attrs={'data-product-name': True}):
    print(f"data-product-name: {tag.get('data-product-name')}")
