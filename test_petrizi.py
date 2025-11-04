"""
Diagnóstico completo do Petrizi (Tray)
"""

import asyncio
import httpx
from bs4 import BeautifulSoup
import json

async def diagnosticar_petrizi():
    url_base = "https://petrizi.com.br"
    
    print(f"🔍 Diagnosticando {url_base}\n")
    
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        # 1. Testar sitemaps
        print("=" * 60)
        print("FASE 1: Testando sitemaps")
        print("=" * 60)
        
        sitemap_urls = [
            f"{url_base}/sitemap.xml",
            f"{url_base}/sitemap_products.xml",
            f"{url_base}/sitemap_index.xml",
            f"{url_base}/sitemap/products.xml",
            f"{url_base}/sitemap/sitemap.xml"
        ]
        
        sitemap_encontrado = None
        
        for sitemap_url in sitemap_urls:
            try:
                print(f"\n🔍 Tentando: {sitemap_url}")
                resp = await client.get(sitemap_url)
                
                print(f"   Status: {resp.status_code}")
                
                if resp.status_code == 200:
                    print(f"   ✅ Content-Type: {resp.headers.get('content-type')}")
                    print(f"   ✅ Tamanho: {len(resp.text)} bytes")
                    
                    sitemap_encontrado = sitemap_url
                    sitemap_content = resp.text
                    
                    # Parse
                    soup = BeautifulSoup(sitemap_content, 'xml')
                    
                    # Index?
                    sitemaps = soup.find_all('sitemap')
                    if sitemaps:
                        print(f"   📚 SITEMAP INDEX com {len(sitemaps)} sitemaps")
                        for i, sm in enumerate(sitemaps[:5], 1):
                            loc = sm.find('loc')
                            if loc:
                                print(f"      {i}. {loc.text}")
                    else:
                        urls = soup.find_all('url')
                        print(f"   📦 {len(urls)} URLs")
                        
                        if urls:
                            print(f"   Primeiras 3 URLs:")
                            for i, url_tag in enumerate(urls[:3], 1):
                                loc = url_tag.find('loc')
                                if loc:
                                    print(f"      {i}. {loc.text}")
                    
                    break
            
            except Exception as e:
                print(f"   ❌ Erro: {e}")
        
        if not sitemap_encontrado:
            print("\n⚠️ Nenhum sitemap encontrado! Tentando homepage...")
            
            try:
                resp = await client.get(url_base)
                print(f"Status homepage: {resp.status_code}")
                
                with open("petrizi_homepage.html", "w", encoding="utf-8") as f:
                    f.write(resp.text)
                print("✅ Homepage salva")
                
                soup = BeautifulSoup(resp.text, 'html.parser')
                
                # Procura links de produtos
                product_links = []
                for a in soup.find_all('a', href=True):
                    href = a['href']
                    if any(pattern in href.lower() for pattern in ['/produto/', '/product/', '/p/', 'produto.php']):
                        if href.startswith('http'):
                            product_links.append(href)
                        else:
                            product_links.append(f"{url_base}{href}")
                
                print(f"\n📦 Links de produtos na homepage: {len(set(product_links))}")
                
                if product_links:
                    print("\nPrimeiros 5 links:")
                    for i, link in enumerate(list(set(product_links))[:5], 1):
                        print(f"  {i}. {link}")
                    
                    # Testa primeiro produto
                    sitemap_content = None
                    produto_url = list(set(product_links))[0]
                else:
                    print("❌ Nenhum link de produto encontrado")
                    return
            
            except Exception as e:
                print(f"❌ Erro: {e}")
                return
        else:
            # Parse sitemap
            soup = BeautifulSoup(sitemap_content, 'xml')
            
            # Se index, expande primeiro
            sitemaps = soup.find_all('sitemap')
            if sitemaps:
                primeiro = sitemaps[0].find('loc').text
                print(f"\n🔍 Expandindo: {primeiro}")
                resp = await client.get(primeiro)
                sitemap_content = resp.text
                soup = BeautifulSoup(sitemap_content, 'xml')
            
            urls = soup.find_all('url')
            if not urls:
                print("❌ Nenhuma URL")
                return
            
            produto_url = urls[0].find('loc').text
        
        # 2. Testa produto
        print("\n" + "=" * 60)
        print("FASE 2: Testando produto")
        print("=" * 60)
        
        print(f"\n🔍 Produto: {produto_url}")
        
        resp = await client.get(produto_url)
        print(f"Status: {resp.status_code}")
        
        with open("petrizi_produto.html", "w", encoding="utf-8") as f:
            f.write(resp.text)
        print("✅ HTML salvo em petrizi_produto.html")
        
        # 3. Analisa estrutura
        print("\n" + "=" * 60)
        print("FASE 3: Analisando estrutura")
        print("=" * 60)
        
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # JSON-LD
        print("\n📋 JSON-LD:")
        json_lds = soup.find_all('script', type='application/ld+json')
        print(f"Encontrados: {len(json_lds)}")
        
        for i, script in enumerate(json_lds, 1):
            try:
                data = json.loads(script.string)
                if isinstance(data, list):
                    data = data[0] if data else {}
                
                print(f"\nScript #{i} - Type: {data.get('@type', 'N/A')}")
                
                if data.get('@type') == 'Product':
                    print(f"  Nome: {data.get('name')}")
                    
                    offers = data.get('offers', {})
                    if isinstance(offers, dict):
                        print(f"  Preço: {offers.get('price')} {offers.get('priceCurrency')}")
                    elif isinstance(offers, list) and offers:
                        print(f"  Preço: {offers[0].get('price')} {offers[0].get('priceCurrency')}")
                    
                    print(f"  Marca: {data.get('brand')}")
                    
                    print("\n  JSON completo:")
                    print(json.dumps(data, indent=2, ensure_ascii=False)[:800])
            
            except Exception as e:
                print(f"  Erro: {e}")
        
        # Open Graph
        print("\n🏷️ Open Graph:")
        og_tags = {
            'og:title': soup.find('meta', property='og:title'),
            'og:price:amount': soup.find('meta', property='og:price:amount'),
            'og:image': soup.find('meta', property='og:image'),
            'product:price:amount': soup.find('meta', property='product:price:amount')
        }
        
        for key, tag in og_tags.items():
            if tag:
                print(f"  {key}: {tag.get('content')}")
        
        # HTML
        print("\n💰 Buscando preços:")
        
        price_selectors = [
            ('.price', soup.find_all(class_='price')),
            ('.product-price', soup.find_all(class_='product-price')),
            ('[data-price]', soup.find_all(attrs={'data-price': True})),
            ('.valor', soup.find_all(class_='valor')),
            ('[itemprop="price"]', soup.find_all(attrs={'itemprop': 'price'})),
            ('#preco', soup.find_all(id='preco'))
        ]
        
        for selector, elems in price_selectors:
            if elems:
                print(f"\n  ✅ {selector} ({len(elems)} encontrados):")
                for elem in elems[:3]:
                    text = elem.get_text(strip=True)
                    attr = elem.get('data-price') or elem.get('content')
                    if attr:
                        print(f"     - '{text}' | Attr: '{attr}'")
                    else:
                        print(f"     - '{text}'")
        
        # R$
        print("\n💵 Linhas com R$:")
        all_text = soup.get_text()
        lines = [l.strip() for l in all_text.split('\n') if 'R$' in l]
        
        if lines:
            print(f"Encontradas {len(lines)} linhas:")
            for line in lines[:10]:
                if line:
                    print(f"  - {line[:80]}")
        else:
            print("  ❌ Nenhuma")
        
        # Scripts com dados
        print("\n📜 Scripts com 'price' ou 'produto':")
        scripts = soup.find_all('script')
        
        for script in scripts:
            if script.string:
                text = script.string.lower()
                if ('price' in text or 'preco' in text or 'produto' in text) and len(script.string) < 2000:
                    print(f"\n  Script encontrado:")
                    print(f"    {script.string[:300]}...")
                    break

asyncio.run(diagnosticar_petrizi())
