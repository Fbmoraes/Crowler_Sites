"""
Diagnóstico completo do site Katsukazan (Nuvemshop)
"""

import asyncio
import httpx
from bs4 import BeautifulSoup
import json

async def diagnosticar_katsukazan():
    url_base = "https://katsukazan.com.br"
    
    print(f"🔍 Diagnosticando {url_base}\n")
    
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        # 1. Testar sitemap
        print("=" * 60)
        print("FASE 1: Testando sitemaps")
        print("=" * 60)
        
        sitemap_urls = [
            f"{url_base}/sitemap.xml",
            f"{url_base}/sitemap_products.xml",
            f"{url_base}/sitemap_index.xml",
            f"{url_base}/product-sitemap.xml",
            f"{url_base}/sitemap_products_1.xml"
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
                    
                    # Parse rápido
                    soup = BeautifulSoup(sitemap_content, 'xml')
                    
                    # Verifica se é index
                    sitemaps = soup.find_all('sitemap')
                    if sitemaps:
                        print(f"   📚 SITEMAP INDEX com {len(sitemaps)} sitemaps")
                        for i, sm in enumerate(sitemaps[:5], 1):
                            loc = sm.find('loc')
                            if loc:
                                print(f"      {i}. {loc.text}")
                    else:
                        # URLs diretas
                        urls = soup.find_all('url')
                        print(f"   📦 {len(urls)} URLs encontradas")
                        
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
            print("\n❌ Nenhum sitemap encontrado!")
            print("\n🔍 Tentando buscar produtos na homepage...")
            
            resp = await client.get(url_base)
            print(f"Status homepage: {resp.status_code}")
            
            with open("katsukazan_homepage.html", "w", encoding="utf-8") as f:
                f.write(resp.text)
            print("✅ Homepage salva em katsukazan_homepage.html")
            
            return
        
        # 2. Testar um produto
        print("\n" + "=" * 60)
        print("FASE 2: Testando extração de produto")
        print("=" * 60)
        
        # Pega primeira URL de produto do sitemap
        soup = BeautifulSoup(sitemap_content, 'xml')
        
        # Se for index, expande primeiro sitemap
        sitemaps = soup.find_all('sitemap')
        if sitemaps:
            primeiro_sitemap = sitemaps[0].find('loc').text
            print(f"\n🔍 Expandindo primeiro sitemap: {primeiro_sitemap}")
            resp = await client.get(primeiro_sitemap)
            sitemap_content = resp.text
            soup = BeautifulSoup(sitemap_content, 'xml')
        
        urls = soup.find_all('url')
        
        if not urls:
            print("❌ Nenhuma URL encontrada")
            return
        
        # Pega primeiro produto
        produto_url = urls[0].find('loc').text
        print(f"\n🔍 Testando produto: {produto_url}")
        
        resp = await client.get(produto_url)
        print(f"Status: {resp.status_code}")
        
        with open("katsukazan_produto.html", "w", encoding="utf-8") as f:
            f.write(resp.text)
        print("✅ HTML salvo em katsukazan_produto.html")
        
        # 3. Analisar estrutura do produto
        print("\n" + "=" * 60)
        print("FASE 3: Analisando estrutura HTML")
        print("=" * 60)
        
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # JSON-LD
        print("\n📋 JSON-LD Scripts:")
        json_lds = soup.find_all('script', type='application/ld+json')
        print(f"Encontrados: {len(json_lds)}")
        
        for i, script in enumerate(json_lds, 1):
            try:
                data = json.loads(script.string)
                print(f"\nScript #{i}:")
                print(f"  @type: {data.get('@type', 'N/A')}")
                
                if data.get('@type') == 'Product':
                    print(f"  Nome: {data.get('name', 'N/A')}")
                    print(f"  Marca: {data.get('brand', {}).get('name', 'N/A') if isinstance(data.get('brand'), dict) else data.get('brand', 'N/A')}")
                    
                    offers = data.get('offers', {})
                    if isinstance(offers, dict):
                        print(f"  Preço: {offers.get('price', 'N/A')}")
                        print(f"  Moeda: {offers.get('priceCurrency', 'N/A')}")
                    
                    print(f"  Disponibilidade: {offers.get('availability', 'N/A')}")
                    print(f"  Imagem: {data.get('image', 'N/A')[:60]}...")
            except Exception as e:
                print(f"  Erro ao parsear: {e}")
        
        # Open Graph
        print("\n🏷️ Open Graph Tags:")
        og_tags = {
            'og:title': soup.find('meta', property='og:title'),
            'og:price:amount': soup.find('meta', property='og:price:amount'),
            'og:price:currency': soup.find('meta', property='og:price:currency'),
            'og:image': soup.find('meta', property='og:image'),
            'product:price:amount': soup.find('meta', property='product:price:amount'),
            'product:price:currency': soup.find('meta', property='product:price:currency')
        }
        
        for key, tag in og_tags.items():
            if tag:
                print(f"  {key}: {tag.get('content', 'N/A')}")
        
        # Seletores HTML comuns
        print("\n🔍 Seletores HTML:")
        
        # Título
        title_selectors = [
            ('h1.product-name', soup.find('h1', class_='product-name')),
            ('h1.product-title', soup.find('h1', class_='product-title')),
            ('.product-name', soup.find(class_='product-name')),
            ('h1', soup.find('h1')),
            ('[itemprop="name"]', soup.find(attrs={'itemprop': 'name'}))
        ]
        
        print("\nTítulo:")
        for selector, elem in title_selectors:
            if elem:
                text = elem.get_text(strip=True)[:60]
                print(f"  ✅ {selector}: {text}")
                break
        else:
            print("  ❌ Nenhum título encontrado")
        
        # Preço
        price_selectors = [
            ('.price', soup.find_all(class_='price')),
            ('.product-price', soup.find_all(class_='product-price')),
            ('[itemprop="price"]', soup.find_all(attrs={'itemprop': 'price'})),
            ('.valor', soup.find_all(class_='valor')),
            ('.price-regular', soup.find_all(class_='price-regular')),
            ('[data-price]', soup.find_all(attrs={'data-price': True}))
        ]
        
        print("\nPreços:")
        for selector, elems in price_selectors:
            if elems:
                print(f"  ✅ {selector} ({len(elems)} encontrados):")
                for elem in elems[:3]:
                    text = elem.get_text(strip=True)
                    price_attr = elem.get('content') or elem.get('data-price')
                    if price_attr:
                        print(f"     - {text} (attr: {price_attr})")
                    else:
                        print(f"     - {text}")
        
        # Marca
        print("\nMarca:")
        brand_selectors = [
            ('.brand', soup.find(class_='brand')),
            ('.product-brand', soup.find(class_='product-brand')),
            ('[itemprop="brand"]', soup.find(attrs={'itemprop': 'brand'}))
        ]
        
        for selector, elem in brand_selectors:
            if elem:
                print(f"  ✅ {selector}: {elem.get_text(strip=True)}")
                break
        else:
            print("  ⚠️ Nenhuma marca encontrada")
        
        # Buscar qualquer texto com R$
        print("\n💰 Textos com R$ no HTML:")
        all_text = soup.get_text()
        lines_with_real = [line.strip() for line in all_text.split('\n') if 'R$' in line]
        
        if lines_with_real:
            print(f"Encontradas {len(lines_with_real)} linhas com R$:")
            for line in lines_with_real[:5]:
                if line:
                    print(f"  - {line[:80]}")
        else:
            print("  ❌ Nenhuma linha com R$ encontrada")
        
        # Scripts e dados estruturados
        print("\n📜 Scripts especiais:")
        
        # Nuvemshop geralmente tem dados em scripts
        scripts = soup.find_all('script')
        print(f"Total de scripts: {len(scripts)}")
        
        for script in scripts:
            script_text = script.string
            if script_text and ('product' in script_text.lower() or 'price' in script_text.lower()):
                if 'window' in script_text or 'var ' in script_text:
                    print(f"\n  Script com dados de produto:")
                    print(f"    {script_text[:200]}...")

asyncio.run(diagnosticar_katsukazan())
