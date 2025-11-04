"""
Debug Sacada - Por que só encontrou 1 produto?
"""
import httpx
from bs4 import BeautifulSoup

base = "https://www.sacada.com"

print("=== Debug Descoberta Sacada ===\n")

# 1. Buscar categorias
r = httpx.get(base, timeout=15)
soup = BeautifulSoup(r.text, 'html.parser')

categorias = [a.get('href') for a in soup.find_all('a', href=True) if '/shop/' in a.get('href', '')]
categorias = list(set(categorias))

print(f"Categorias encontradas: {len(categorias)}\n")
for i, cat in enumerate(categorias[:5], 1):
    print(f"{i}. {cat}")

# 2. Testar uma categoria
cat = "/shop/roupas/vestidos?PS=12&order=OrderByReleaseDateDESC"
cat_url = f"{base}{cat}".split('?')[0] + '?PS=100'

print(f"\n=== Testando: {cat_url} ===\n")

r_cat = httpx.get(cat_url, timeout=15)
soup_cat = BeautifulSoup(r_cat.text, 'html.parser')

# Buscar TODOS os links (debug completo)
all_links = [a.get('href') for a in soup_cat.find_all('a', href=True)]
print(f"Total de links na página: {len(all_links)}\n")

# Links com /p
links_p = [l for l in all_links if l and '/p' in l]
print(f"Links com '/p': {len(links_p)}")
for link in links_p[:10]:
    print(f"  - {link}")

# Links com /p?
links_pq = [l for l in all_links if l and '/p?' in l]
print(f"\nLinks com '/p?': {len(links_pq)}")
for link in links_pq[:10]:
    print(f"  - {link}")

# Padrões de produto VTEX
print(f"\n=== Padrões VTEX ===")
patterns = ['/p?', '/p/', '-/p', '/product/']
for pattern in patterns:
    matches = [l for l in all_links if l and pattern in l]
    print(f"Pattern '{pattern}': {len(matches)} matches")
    if matches:
        print(f"  Exemplo: {matches[0]}")
