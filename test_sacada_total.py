"""
Conta TODOS os produtos do Sacada
"""
import httpx
import re

url = "https://www.sacada.com"

print("EXPANDINDO TODOS OS SITEMAPS DE PRODUTOS")
print("=" * 60)

# Busca índice
r = httpx.get(f"{url}/sitemap.xml", timeout=10)
sitemaps = re.findall(r'<loc>(.*?)</loc>', r.text)

# Filtra apenas sitemaps de produtos
product_sitemaps = [s for s in sitemaps if 'product' in s.lower()]
print(f"Sitemaps de produtos encontrados: {len(product_sitemaps)}")

total_produtos = 0
todos_produtos = []

for sitemap_url in product_sitemaps:
    print(f"\nBuscando: {sitemap_url.split('/')[-1]}")
    try:
        r2 = httpx.get(sitemap_url, timeout=10)
        urls = re.findall(r'<loc>(.*?)</loc>', r2.text)
        print(f"  Produtos: {len(urls)}")
        total_produtos += len(urls)
        todos_produtos.extend(urls)
    except Exception as e:
        print(f"  Erro: {e}")

print("\n" + "=" * 60)
print(f"TOTAL: {total_produtos} produtos no Sacada!")
print("=" * 60)

print("\nÚltimos 10 produtos:")
for p in todos_produtos[-10:]:
    print(f"  {p}")
