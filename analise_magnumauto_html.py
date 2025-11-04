"""
Analisar HTML do MagnumAuto
"""
from bs4 import BeautifulSoup

soup = BeautifulSoup(open('debug_magnumauto.html', encoding='utf-8'), 'html.parser')

print("=== Análise HTML MagnumAuto ===\n")

# 1. Classes com "price"
print("1. Classes com 'price', 'valor', 'preco':")
prices = soup.find_all(class_=lambda x: x and any(k in str(x).lower() for k in ['price', 'valor', 'preco']))
print(f"   Total: {len(prices)}")
for p in prices[:10]:
    classes = ' '.join(p.get('class', []))
    text = p.get_text(strip=True)[:100]
    print(f"   - {classes}: {text}")

# 2. Atributo itemprop
print("\n2. Elementos com itemprop:")
items = soup.find_all(attrs={'itemprop': True})
print(f"   Total: {len(items)}")
for item in items[:10]:
    prop = item.get('itemprop')
    text = item.get_text(strip=True)[:50]
    print(f"   - {prop}: {text}")

# 3. Data attributes
print("\n3. Atributos data-*:")
data_elements = [el for el in soup.find_all() if any(k.startswith('data-') for k in el.attrs.keys())]
print(f"   Total: {len(data_elements)}")
for el in data_elements[:10]:
    data_attrs = {k:v for k,v in el.attrs.items() if k.startswith('data-')}
    print(f"   - {el.name}: {str(data_attrs)[:100]}")

# 4. Span, div, p com R$
print("\n4. Elementos com 'R$' no texto:")
rs_elements = soup.find_all(string=lambda t: t and 'R$' in t)
print(f"   Total: {len(rs_elements)}")
for el in rs_elements[:10]:
    parent = el.parent
    classes = ' '.join(parent.get('class', []))
    print(f"   - {parent.name}.{classes}: {el.strip()[:80]}")

# 5. Meta tags
print("\n5. Meta tags relevantes:")
for prop in ['og:price:amount', 'product:price:amount', 'price']:
    meta = soup.find('meta', attrs={'property': prop}) or soup.find('meta', attrs={'name': prop})
    if meta:
        print(f"   - {prop}: {meta.get('content')}")
