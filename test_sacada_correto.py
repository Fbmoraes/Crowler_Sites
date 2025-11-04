"""
Teste diagnóstico: Sacada (URL correta)
"""
import httpx
import re
from bs4 import BeautifulSoup

url = "https://www.sacada.com"

# 1. Testa sitemap
print("=" * 60)
print("TESTANDO SITEMAP")
print("=" * 60)

sitemap_url = f"{url}/sitemap.xml"
try:
    r = httpx.get(sitemap_url, follow_redirects=True, timeout=10)
    print(f"Status: {r.status_code}")
    
    if r.status_code == 200:
        urls = re.findall(r'<loc>(.*?)</loc>', r.text)
        print(f"Total URLs: {len(urls)}")
        
        # É índice?
        if any('.xml' in u for u in urls):
            print("\n⚠️ É um ÍNDICE de sitemaps!")
            print("Sitemaps filhos:")
            for u in urls:
                if '.xml' in u:
                    print(f"  - {u}")
            
            # Tenta expandir sitemap de produtos
            product_sitemap = [u for u in urls if 'product' in u.lower()]
            if product_sitemap:
                print(f"\nExpandindo sitemap de produtos: {product_sitemap[0]}")
                r2 = httpx.get(product_sitemap[0], timeout=10)
                urls_produtos = re.findall(r'<loc>(.*?)</loc>', r2.text)
                print(f"  Total produtos: {len(urls_produtos)}")
                print("\n  Primeiros 10 produtos:")
                for u in urls_produtos[:10]:
                    print(f"    {u}")
                
                # Detecta padrão
                print("\n  Padrão das URLs:")
                paths = [u.split('sacada.com')[-1] for u in urls_produtos]
                print("    Exemplos de paths:")
                for p in paths[:5]:
                    print(f"      {p}")
        else:
            print("\nPrimeiras 10 URLs:")
            for url_sitemap in urls[:10]:
                print(f"  - {url_sitemap}")
            
            # Analisa estrutura
            niveis = {}
            for u in urls:
                nivel = u.count('/')
                niveis[nivel] = niveis.get(nivel, 0) + 1
            
            print("\nDistribuição por níveis:")
            for n in sorted(niveis.keys()):
                print(f"  Nível {n}: {niveis[n]} URLs")

except Exception as e:
    print(f"Erro: {e}")

# 2. Testa homepage
print("\n" + "=" * 60)
print("TESTANDO HOMEPAGE")
print("=" * 60)

try:
    r = httpx.get(url, follow_redirects=True, timeout=10)
    soup = BeautifulSoup(r.text, 'html.parser')
    
    print(f"Status: {r.status_code}")
    print(f"Total de links: {len(soup.find_all('a', href=True))}")
    
    # Busca produtos
    links = soup.find_all('a', href=True)
    produtos = []
    for link in links:
        href = link.get('href')
        if href.startswith('/') and href.count('/') >= 2:
            full_url = url + href
            if full_url.count('/') >= 4:
                produtos.append(full_url)
        elif href.startswith('http') and 'sacada' in href:
            if href.count('/') >= 4:
                produtos.append(href)
    
    produtos_unicos = list(set(produtos))
    print(f"\nProdutos potenciais: {len(produtos_unicos)}")
    if produtos_unicos:
        print("Exemplos:")
        for p in produtos_unicos[:10]:
            print(f"  {p}")

except Exception as e:
    print(f"Erro: {e}")

# 3. Testa plataforma
print("\n" + "=" * 60)
print("DETECTANDO PLATAFORMA")
print("=" * 60)

try:
    r = httpx.get(url, follow_redirects=True, timeout=10)
    html = r.text.lower()
    
    plataformas = {
        'VTEX': ['vtex', 'vteximg'],
        'Shopify': ['shopify', 'myshopify'],
        'WooCommerce': ['wp-content', 'woocommerce'],
        'Magento': ['magento', '/pub/static/frontend'],
        'Nuvemshop': ['nuvemshop', 'cdn.awsli'],
        'Tray': ['tray', 'traycdn'],
        'Wix': ['wix', 'wixstatic'],
    }
    
    print("Plataforma detectada:")
    for nome, keywords in plataformas.items():
        if any(kw in html for kw in keywords):
            print(f"  ✅ {nome}")
            break
    else:
        print("  ⚠️ Plataforma não identificada")

except Exception as e:
    print(f"Erro: {e}")
