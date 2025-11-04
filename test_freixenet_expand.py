"""
Teste: Expandir sitemap do Freixenet
"""
import httpx
import re

url = "https://www.freixenet.com.br"

print("EXPANDINDO SITEMAP RECURSIVO")
print("=" * 60)

# Sitemap principal
sitemap_url = f"{url}/sitemap.xml"
r = httpx.get(sitemap_url, timeout=10)
print(f"Sitemap principal: {len(re.findall(r'<loc>(.*?)</loc>', r.text))} índices")

# Busca sitemap de produtos
sitemap_produtos_url = f"{url}/sitemap/product-0.xml"
print(f"\nBuscando: {sitemap_produtos_url}")

r = httpx.get(sitemap_produtos_url, timeout=10)
print(f"Status: {r.status_code}")

if r.status_code == 200:
    urls = re.findall(r'<loc>(.*?)</loc>', r.text)
    print(f"Total produtos: {len(urls)}")
    
    print("\nPrimeiros 10 produtos:")
    for u in urls[:10]:
        print(f"  {u}")
    
    print("\nPadrão das URLs:")
    # Detecta padrão comum
    paths = [u.split('freixenet.com.br')[-1] for u in urls]
    print(f"  Exemplos de paths:")
    for p in paths[:5]:
        print(f"    {p}")
    
    # Verifica terminação
    with_p = [u for u in urls if u.endswith('/p')]
    print(f"\n  URLs terminando em /p: {len(with_p)} ({len(with_p)/len(urls)*100:.1f}%)")
