"""
Diagnóstico completo do MH Studios (Shopify)
"""

import asyncio
import httpx
from bs4 import BeautifulSoup
import json

async def diagnosticar_mhstudios():
    url_base = "https://mhstudios.com.br"
    
    print(f"🔍 Diagnosticando {url_base}\n")
    
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        # 1. Testar sitemaps
        print("=" * 60)
        print("FASE 1: Testando sitemaps")
        print("=" * 60)
        
        sitemap_urls = [
            f"{url_base}/sitemap.xml",
            f"{url_base}/sitemap_products.xml",
            f"{url_base}/sitemap_products_1.xml",
            f"{url_base}/sitemap_index.xml"
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
            return
        
        # 2. Expandir se for index
        soup = BeautifulSoup(sitemap_content, 'xml')
        sitemaps = soup.find_all('sitemap')
        
        if sitemaps:
            # Procura sitemap de produtos
            for sm in sitemaps:
                loc = sm.find('loc')
                if loc and 'product' in loc.text.lower():
                    print(f"\n🔍 Expandindo sitemap de produtos: {loc.text}")
                    resp = await client.get(loc.text)
                    sitemap_content = resp.text
                    soup = BeautifulSoup(sitemap_content, 'xml')
                    break
        
        urls = soup.find_all('url')
        if not urls:
            print("❌ Nenhuma URL encontrada")
            return
        
        print(f"\n📦 Total de URLs: {len(urls)}")
        
        # 3. Testar primeiro produto
        print("\n" + "=" * 60)
        print("FASE 2: Testando produto")
        print("=" * 60)
        
        produto_url = urls[0].find('loc').text
        print(f"\n🔍 Produto: {produto_url}")
        
        resp = await client.get(produto_url)
        print(f"Status: {resp.status_code}")
        
        with open("mhstudios_produto.html", "w", encoding="utf-8") as f:
            f.write(resp.text)
        print("✅ HTML salvo em mhstudios_produto.html")
        
        # 4. Analisar estrutura
        print("\n" + "=" * 60)
        print("FASE 3: Analisando estrutura")
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
                    
                    offers = data.get('offers', {})
                    if isinstance(offers, dict):
                        print(f"  Preço: {offers.get('price', 'N/A')}")
                        print(f"  Moeda: {offers.get('priceCurrency', 'N/A')}")
                    elif isinstance(offers, list) and offers:
                        print(f"  Preço: {offers[0].get('price', 'N/A')}")
                        print(f"  Moeda: {offers[0].get('priceCurrency', 'N/A')}")
                    
                    print(f"  Marca: {data.get('brand', {}).get('name', 'N/A') if isinstance(data.get('brand'), dict) else data.get('brand', 'N/A')}")
                    print(f"  Imagem: {data.get('image', 'N/A')[:60] if isinstance(data.get('image'), str) else 'N/A'}...")
                    
                    # Mostra JSON completo para análise
                    print(f"\n  JSON completo:")
                    print(json.dumps(data, indent=4, ensure_ascii=False)[:500])
            except Exception as e:
                print(f"  Erro: {e}")
        
        # Open Graph
        print("\n🏷️ Open Graph Tags:")
        og_tags = {
            'og:title': soup.find('meta', property='og:title'),
            'og:price:amount': soup.find('meta', property='og:price:amount'),
            'og:price:currency': soup.find('meta', property='og:price:currency'),
            'og:image': soup.find('meta', property='og:image'),
            'product:price:amount': soup.find('meta', property='product:price:amount')
        }
        
        for key, tag in og_tags.items():
            if tag:
                print(f"  {key}: {tag.get('content', 'N/A')}")
        
        # Buscar preço no HTML
        print("\n💰 Buscando preços no HTML:")
        
        # Seletores Shopify comuns
        price_selectors = [
            ('.price', soup.find_all(class_='price')),
            ('.product-price', soup.find_all(class_='product-price')),
            ('[data-price]', soup.find_all(attrs={'data-price': True})),
            ('.money', soup.find_all(class_='money')),
            ('[itemprop="price"]', soup.find_all(attrs={'itemprop': 'price'})),
            ('.price-item', soup.find_all(class_='price-item'))
        ]
        
        for selector, elems in price_selectors:
            if elems:
                print(f"\n  ✅ {selector} ({len(elems)} encontrados):")
                for elem in elems[:3]:
                    text = elem.get_text(strip=True)
                    data_price = elem.get('data-price') or elem.get('content')
                    if data_price:
                        print(f"     - Texto: '{text}' | Attr: '{data_price}'")
                    else:
                        print(f"     - Texto: '{text}'")
        
        # Buscar R$ no texto
        print("\n💵 Linhas com R$:")
        all_text = soup.get_text()
        lines_with_real = [line.strip() for line in all_text.split('\n') if 'R$' in line]
        
        if lines_with_real:
            print(f"Encontradas {len(lines_with_real)} linhas:")
            for line in lines_with_real[:10]:
                if line:
                    print(f"  - {line[:80]}")
        else:
            print("  ❌ Nenhuma linha com R$ encontrada")
        
        # Shopify API
        print("\n" + "=" * 60)
        print("FASE 4: Testando Shopify API")
        print("=" * 60)
        
        # Shopify tem API JSON
        product_handle = produto_url.split('/products/')[-1].split('?')[0]
        api_url = f"{url_base}/products/{product_handle}.json"
        
        print(f"\n🔍 API URL: {api_url}")
        
        try:
            resp = await client.get(api_url)
            print(f"Status: {resp.status_code}")
            
            if resp.status_code == 200:
                data = resp.json()
                print("\n✅ API JSON disponível!")
                
                product = data.get('product', {})
                print(f"\nProduto:")
                print(f"  ID: {product.get('id')}")
                print(f"  Título: {product.get('title')}")
                print(f"  Vendor: {product.get('vendor')}")
                print(f"  Product Type: {product.get('product_type')}")
                
                variants = product.get('variants', [])
                if variants:
                    print(f"\n  Variantes: {len(variants)}")
                    print(f"  Primeira variante:")
                    v = variants[0]
                    print(f"    ID: {v.get('id')}")
                    print(f"    Price: {v.get('price')}")
                    print(f"    Compare at price: {v.get('compare_at_price')}")
                    print(f"    Available: {v.get('available')}")
                
                # Salvar JSON completo
                with open("mhstudios_api.json", "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                print("\n✅ JSON completo salvo em mhstudios_api.json")
        
        except Exception as e:
            print(f"❌ Erro na API: {e}")

asyncio.run(diagnosticar_mhstudios())
