"""
Teste específico para Dermomanipulações
Investigar problemas de extração
"""

import asyncio
import httpx
from bs4 import BeautifulSoup
import json
from urllib.parse import urljoin

async def testar_dermo():
    url_base = "https://www.dermomanipulacoes.com.br"
    
    print(f"🔍 Testando {url_base}\n")
    
    # 1. Buscar sitemap
    print("=" * 60)
    print("FASE 1: Buscando sitemap")
    print("=" * 60)
    
    sitemap_urls = [
        f"{url_base}/sitemap.xml",
        f"{url_base}/sitemap_products.xml",
        f"{url_base}/sitemap_index.xml",
        f"{url_base}/product-sitemap.xml"
    ]
    
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        sitemap_encontrado = None
        
        for sitemap_url in sitemap_urls:
            try:
                print(f"\n🔍 Tentando: {sitemap_url}")
                resp = await client.get(sitemap_url)
                
                if resp.status_code == 200:
                    print(f"✅ Encontrado! Status: {resp.status_code}")
                    print(f"   Content-Type: {resp.headers.get('content-type')}")
                    print(f"   Tamanho: {len(resp.text)} bytes")
                    sitemap_encontrado = sitemap_url
                    sitemap_content = resp.text
                    break
                else:
                    print(f"❌ Status: {resp.status_code}")
            except Exception as e:
                print(f"❌ Erro: {e}")
        
        if not sitemap_encontrado:
            print("\n⚠️ Nenhum sitemap encontrado! Tentando scraping direto...")
            
            # Tenta página inicial para ver estrutura
            print(f"\n🔍 Buscando página inicial: {url_base}")
            resp = await client.get(url_base)
            print(f"Status: {resp.status_code}")
            
            with open("dermo_homepage.html", "w", encoding="utf-8") as f:
                f.write(resp.text)
            print("✅ HTML salvo em dermo_homepage.html")
            
            # Procura por links de produtos
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # Padrões comuns de URLs de produtos
            product_links = []
            
            # Links com /produto/, /product/, /p/
            for a in soup.find_all('a', href=True):
                href = a['href']
                if any(pattern in href.lower() for pattern in ['/produto/', '/product/', '/p/']):
                    full_url = urljoin(url_base, href)
                    if full_url not in product_links:
                        product_links.append(full_url)
            
            print(f"\n📦 Links de produtos encontrados na homepage: {len(product_links)}")
            if product_links:
                print("\nPrimeiros 10 links:")
                for i, link in enumerate(product_links[:10], 1):
                    print(f"  {i}. {link}")
            
            # Testa um produto
            if product_links:
                print("\n" + "=" * 60)
                print("FASE 2: Testando extração de 1 produto")
                print("=" * 60)
                
                test_url = product_links[0]
                print(f"\n🔍 Produto de teste: {test_url}")
                
                resp = await client.get(test_url)
                print(f"Status: {resp.status_code}")
                
                with open("dermo_produto.html", "w", encoding="utf-8") as f:
                    f.write(resp.text)
                print("✅ HTML salvo em dermo_produto.html")
                
                # Extrai informações
                soup = BeautifulSoup(resp.text, 'html.parser')
                
                # JSON-LD
                json_lds = soup.find_all('script', type='application/ld+json')
                print(f"\n📋 Scripts JSON-LD encontrados: {len(json_lds)}")
                
                for i, script in enumerate(json_lds, 1):
                    try:
                        data = json.loads(script.string)
                        print(f"\nJSON-LD #{i}:")
                        print(f"  Type: {data.get('@type', 'N/A')}")
                        if data.get('@type') == 'Product':
                            print(f"  Nome: {data.get('name', 'N/A')}")
                            print(f"  Preço: {data.get('offers', {}).get('price', 'N/A')}")
                            print(f"  Marca: {data.get('brand', {}).get('name', 'N/A')}")
                    except:
                        print(f"  (Erro ao parsear)")
                
                # Open Graph
                print("\n🏷️ Open Graph Tags:")
                og_tags = {
                    'title': soup.find('meta', property='og:title'),
                    'price': soup.find('meta', property='og:price:amount'),
                    'image': soup.find('meta', property='og:image')
                }
                
                for key, tag in og_tags.items():
                    if tag:
                        print(f"  {key}: {tag.get('content', 'N/A')}")
                
                # HTML fallback
                print("\n🔍 Buscando por seletores HTML:")
                
                # Título
                selectors_title = [
                    ('h1.product-name', soup.find('h1', class_='product-name')),
                    ('h1.product-title', soup.find('h1', class_='product-title')),
                    ('.product-name', soup.find(class_='product-name')),
                    ('h1', soup.find('h1'))
                ]
                
                for selector, element in selectors_title:
                    if element:
                        print(f"  Título ({selector}): {element.get_text(strip=True)[:50]}")
                        break
                
                # Preço
                selectors_price = [
                    ('.price', soup.find(class_='price')),
                    ('.product-price', soup.find(class_='product-price')),
                    ('[itemprop="price"]', soup.find(attrs={'itemprop': 'price'})),
                    ('.valor', soup.find(class_='valor'))
                ]
                
                for selector, element in selectors_price:
                    if element:
                        print(f"  Preço ({selector}): {element.get_text(strip=True)}")
                        break
                
                # Imagem
                selectors_image = [
                    ('.product-image img', soup.select_one('.product-image img')),
                    ('.main-image', soup.find(class_='main-image')),
                    ('[itemprop="image"]', soup.find(attrs={'itemprop': 'image'}))
                ]
                
                for selector, element in selectors_image:
                    if element:
                        img_url = element.get('src') or element.get('data-src')
                        if img_url:
                            print(f"  Imagem ({selector}): {img_url[:60]}...")
                            break
        
        else:
            # Parse sitemap
            print("\n" + "=" * 60)
            print("FASE 2: Analisando sitemap")
            print("=" * 60)
            
            soup = BeautifulSoup(sitemap_content, 'xml')
            
            # Checa se é index
            sitemaps = soup.find_all('sitemap')
            if sitemaps:
                print(f"\n📚 Sitemap INDEX encontrado com {len(sitemaps)} sitemaps:")
                for i, sm in enumerate(sitemaps[:5], 1):
                    loc = sm.find('loc')
                    if loc:
                        print(f"  {i}. {loc.text}")
                
                # Expande primeiro sitemap que parece produtos
                for sm in sitemaps:
                    loc = sm.find('loc')
                    if loc and 'product' in loc.text.lower():
                        print(f"\n🔍 Expandindo sitemap de produtos: {loc.text}")
                        resp = await client.get(loc.text)
                        sitemap_content = resp.text
                        soup = BeautifulSoup(sitemap_content, 'xml')
                        break
            
            # Conta URLs
            urls = soup.find_all('url')
            print(f"\n📦 Total de URLs no sitemap: {len(urls)}")
            
            if urls:
                print("\nPrimeiras 5 URLs:")
                for i, url_tag in enumerate(urls[:5], 1):
                    loc = url_tag.find('loc')
                    if loc:
                        print(f"  {i}. {loc.text}")
                
                # Testa primeiro produto
                print("\n" + "=" * 60)
                print("FASE 3: Testando extração de 1 produto do sitemap")
                print("=" * 60)
                
                test_url = urls[0].find('loc').text
                print(f"\n🔍 Produto de teste: {test_url}")
                
                resp = await client.get(test_url)
                print(f"Status: {resp.status_code}")
                
                with open("dermo_produto.html", "w", encoding="utf-8") as f:
                    f.write(resp.text)
                print("✅ HTML salvo em dermo_produto.html")
                
                # Extrai informações (mesmo código acima)
                soup = BeautifulSoup(resp.text, 'html.parser')
                
                # JSON-LD
                json_lds = soup.find_all('script', type='application/ld+json')
                print(f"\n📋 Scripts JSON-LD encontrados: {len(json_lds)}")
                
                for i, script in enumerate(json_lds, 1):
                    try:
                        data = json.loads(script.string)
                        print(f"\nJSON-LD #{i}:")
                        print(f"  Type: {data.get('@type', 'N/A')}")
                        if data.get('@type') == 'Product':
                            print(f"  Nome: {data.get('name', 'N/A')}")
                            print(f"  Preço: {data.get('offers', {}).get('price', 'N/A')}")
                            print(f"  Marca: {data.get('brand', {}).get('name', 'N/A')}")
                    except:
                        print(f"  (Erro ao parsear)")
                
                # Open Graph
                print("\n🏷️ Open Graph Tags:")
                og_tags = {
                    'title': soup.find('meta', property='og:title'),
                    'price': soup.find('meta', property='og:price:amount'),
                    'image': soup.find('meta', property='og:image')
                }
                
                for key, tag in og_tags.items():
                    if tag:
                        print(f"  {key}: {tag.get('content', 'N/A')}")

if __name__ == "__main__":
    asyncio.run(testar_dermo())
