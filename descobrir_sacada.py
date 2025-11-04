"""#!/usr/bin/env python3

Sacada - Descobrir padrão de sitemap VTEX"""

"""Descobrir URLs de produtos da Sacada Shop

import httpx"""

from bs4 import BeautifulSoup

import httpx

base = "https://www.sacada.com"from bs4 import BeautifulSoup



print("=== Sacada - Descoberta de Sitemap ===\n")print("Verificando Sacada...")

print("=" * 80)

# Testar múltiplos padrões VTEX

patterns = [base_url = "https://www.sacada.com"

    "/sitemap.xml",

    "/sitemap/sitemap.xml",# 1. Verificar sitemap

    "/sitemap-products.xml",print("\n1. Verificando sitemap.xml...")

    "/sitemap/products.xml",try:

    "/sitemap/product.xml",    r = httpx.get(f"{base_url}/sitemap.xml", timeout=10)

    "/sitemap/product-0.xml",    print(f"Status: {r.status_code}")

    "/sitemap/product-1.xml",    if r.status_code == 200:

    "/api/catalog_system/pub/products/search",  # API VTEX        print(f"Conteúdo (200 chars): {r.text[:200]}")

]except Exception as e:

    print(f"Erro: {e}")

found_sitemaps = []

# 2. Verificar robots.txt

for pattern in patterns:print("\n2. Verificando robots.txt...")

    url = base + patterntry:

    try:    r = httpx.get(f"{base_url}/robots.txt", timeout=10)

        r = httpx.get(url, timeout=10, follow_redirects=True)    print(f"Status: {r.status_code}")

        if r.status_code == 200:    if r.status_code == 200:

            print(f"✓ {pattern} - Status: 200")        print("Conteúdo:")

            found_sitemaps.append(url)        print(r.text[:500])

            except Exception as e:

            # Se é XML, contar URLs    print(f"Erro: {e}")

            if 'xml' in r.headers.get('content-type', ''):

                soup = BeautifulSoup(r.text, 'xml')# 3. Analisar homepage

                locs = soup.find_all('loc')print("\n3. Analisando homepage...")

                print(f"  URLs: {len(locs)}")try:

                if locs:    r = httpx.get(base_url, timeout=10, follow_redirects=True)

                    print(f"  Primeira: {locs[0].text[:80]}")    print(f"Status: {r.status_code}")

        else:    print(f"URL final: {r.url}")

            print(f"✗ {pattern} - Status: {r.status_code}")    

    except Exception as e:    soup = BeautifulSoup(r.text, 'lxml')

        print(f"✗ {pattern} - Erro: {str(e)[:50]}")    

    # Procurar links de produto

# Testar homepage para buscar links de sitemap    links_produto = []

print(f"\n2. Analisando homepage...")    

try:    # Padrões comuns: /produto/, /p/, /pd/, /item/

    r = httpx.get(base, timeout=10)    for a in soup.find_all('a', href=True):

    soup = BeautifulSoup(r.text, 'html.parser')        href = a['href']

            if any(pattern in href.lower() for pattern in ['/produto/', '/p/', '/pd/', '/item/', '-p-']):

    # Buscar links para sitemap no HTML            if href.startswith('http'):

    sitemap_links = soup.find_all('a', href=lambda h: h and 'sitemap' in h.lower())                links_produto.append(href)

    print(f"   Links com 'sitemap': {len(sitemap_links)}")            else:

    for link in sitemap_links[:5]:                links_produto.append(base_url + href if href.startswith('/') else base_url + '/' + href)

        print(f"     - {link.get('href')}")    

        links_produto = list(set(links_produto))

    # Buscar no robots.txt referência a sitemap    

    print(f"\n3. Verificando robots.txt...")    print(f"\nEncontrados {len(links_produto)} links de produto na homepage:")

    r_robots = httpx.get(f"{base}/robots.txt", timeout=10)    for i, link in enumerate(links_produto[:10], 1):

    if r_robots.status_code == 200:        print(f"{i}. {link}")

        lines = [l for l in r_robots.text.split('\n') if 'sitemap' in l.lower()]    

        print(f"   Linhas com 'sitemap': {len(lines)}")    if links_produto:

        for line in lines[:5]:        print(f"\nPadrão detectado:")

            print(f"     {line.strip()}")        primeiro = links_produto[0]

except Exception as e:        print(f"Exemplo: {primeiro}")

    print(f"   Erro: {e}")        

        # Analisar padrão

print(f"\n=== Sitemaps Encontrados: {len(found_sitemaps)} ===")        if '/produto/' in primeiro:

for sm in found_sitemaps:            print("Padrão: /produto/")

    print(f"  - {sm}")        elif '/p/' in primeiro:

            print("Padrão: /p/")
        elif '-p-' in primeiro:
            print("Padrão: -p-")

except Exception as e:
    print(f"Erro: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 80)
