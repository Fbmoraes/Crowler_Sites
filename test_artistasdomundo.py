"""
Diagnóstico Artistas do Mundo
Verificar estrutura, plataforma e como extrair dados
"""
import asyncio
import httpx
from bs4 import BeautifulSoup
import json

BASE_URL = "https://www.artistasdomundo.com.br"

async def diagnosticar():
    print("="*60)
    print("DIAGNÓSTICO: ARTISTAS DO MUNDO")
    print("="*60)
    
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        # 1. Testar homepage
        print(f"\n1️⃣ Testando homepage: {BASE_URL}")
        try:
            r = await client.get(BASE_URL)
            print(f"   Status: {r.status_code}")
            
            # Detectar plataforma
            plataformas = {
                'woocommerce': 'WooCommerce',
                'shopify': 'Shopify',
                'vtex': 'VTEX',
                'tray': 'Tray',
                'nuvemshop': 'Nuvemshop',
                'magento': 'Magento',
                'opencart': 'OpenCart'
            }
            
            for key, name in plataformas.items():
                if key in r.text.lower():
                    print(f"   ✅ Plataforma detectada: {name}")
                    break
            else:
                print("   ⚠️  Plataforma: Não identificada")
            
            soup = BeautifulSoup(r.text, 'html.parser')
            
            # Procurar meta tags úteis
            print("\n   Meta tags:")
            og_tags = soup.find_all('meta', {'property': lambda x: x and x.startswith('og:')})
            for tag in og_tags[:5]:
                prop = tag.get('property')
                content = tag.get('content', '')[:100]
                print(f"      {prop}: {content}")
            
        except Exception as e:
            print(f"   ❌ Erro: {e}")
            return
        
        # 2. Buscar sitemap
        print(f"\n2️⃣ Buscando sitemap")
        sitemap_urls = [
            f"{BASE_URL}/sitemap.xml",
            f"{BASE_URL}/sitemap_index.xml",
            f"{BASE_URL}/product-sitemap.xml",
            f"{BASE_URL}/sitemap-products.xml",
            f"{BASE_URL}/wp-sitemap.xml"
        ]
        
        sitemap_encontrado = None
        for sitemap_url in sitemap_urls:
            try:
                r = await client.get(sitemap_url)
                if r.status_code == 200:
                    print(f"   ✅ Sitemap encontrado: {sitemap_url}")
                    sitemap_encontrado = sitemap_url
                    print(f"   Tamanho: {len(r.text)} bytes")
                    
                    # Contar URLs
                    urls_count = r.text.count('<loc>')
                    print(f"   URLs encontradas: {urls_count}")
                    
                    # Mostrar primeiras URLs
                    soup = BeautifulSoup(r.text, 'xml')
                    locs = soup.find_all('loc')
                    print(f"\n   Primeiras URLs:")
                    for loc in locs[:5]:
                        print(f"      {loc.get_text()[:100]}")
                    
                    break
            except Exception as e:
                continue
        
        if not sitemap_encontrado:
            print("   ⚠️  Nenhum sitemap encontrado")
            print("   Tentando buscar produtos na homepage...")
            
            # Buscar links de produtos na homepage
            try:
                r = await client.get(BASE_URL)
                soup = BeautifulSoup(r.text, 'html.parser')
                
                produto_links = []
                for link in soup.find_all('a', href=True):
                    href = link['href']
                    # Padrões comuns de URL de produto
                    if any(x in href.lower() for x in ['/produto/', '/product/', '/p/', '/item/']):
                        if href.startswith('http'):
                            produto_links.append(href)
                        elif href.startswith('/'):
                            produto_links.append(BASE_URL + href)
                
                if produto_links:
                    print(f"   ✅ Encontrados {len(produto_links)} links de produtos na homepage")
                    sitemap_encontrado = "homepage"
                    
                    # Usar primeiro link para teste
                    produto_url = produto_links[0]
                else:
                    print("   ⚠️  Nenhum link de produto encontrado na homepage")
                    return
            except Exception as e:
                print(f"   ❌ Erro ao buscar na homepage: {e}")
                return
        
        # 3. Testar página de produto
        print(f"\n3️⃣ Testando página de produto")
        
        # Pegar URL de teste
        produto_url = None
        if sitemap_encontrado and sitemap_encontrado != "homepage":
            try:
                r = await client.get(sitemap_encontrado)
                soup = BeautifulSoup(r.text, 'xml')
                locs = soup.find_all('loc')
                
                # Pegar primeira URL que parece produto
                for loc in locs[:20]:
                    url = loc.get_text().strip()
                    # Filtrar URLs de produtos (geralmente têm mais segmentos)
                    if url.count('/') >= 4:
                        produto_url = url
                        break
            except:
                pass
        
        if not produto_url and 'produto_links' in locals():
            produto_url = produto_links[0]
        
        if not produto_url:
            print("   ⚠️  Não foi possível encontrar URL de produto para teste")
            return
        
        print(f"   URL de teste: {produto_url}")
        
        # 4. Analisar estrutura do produto
        print(f"\n4️⃣ Analisando produto: {produto_url}")
        try:
            r = await client.get(produto_url)
            print(f"   Status: {r.status_code}")
            
            if r.status_code != 200:
                print(f"   ❌ Produto não acessível")
                return
            
            # Salvar HTML
            with open('artistasdomundo_produto.html', 'w', encoding='utf-8') as f:
                f.write(r.text)
            print(f"   ✅ HTML salvo em: artistasdomundo_produto.html")
            
            soup = BeautifulSoup(r.text, 'html.parser')
            
            # Procurar JSON-LD
            print(f"\n   📋 JSON-LD:")
            json_lds = soup.find_all('script', type='application/ld+json')
            print(f"   Total: {len(json_lds)} scripts")
            
            for i, script in enumerate(json_lds):
                try:
                    data = json.loads(script.string)
                    tipo = data.get('@type', 'Unknown')
                    print(f"   - Script {i+1}: {tipo}")
                    
                    if tipo == 'Product':
                        print(f"      ✅ PRODUTO JSON-LD ENCONTRADO!")
                        print(f"      Nome: {data.get('name', 'N/A')}")
                        
                        offers = data.get('offers', {})
                        if isinstance(offers, dict):
                            preco = offers.get('price', 'N/A')
                            print(f"      Preço: {preco}")
                        elif isinstance(offers, list) and offers:
                            preco = offers[0].get('price', 'N/A')
                            print(f"      Preço: {preco}")
                        
                        brand = data.get('brand', {})
                        if isinstance(brand, dict):
                            marca = brand.get('name', 'N/A')
                        else:
                            marca = brand
                        print(f"      Marca: {marca}")
                        
                        image = data.get('image', 'N/A')
                        if isinstance(image, list):
                            image = image[0] if image else 'N/A'
                        print(f"      Imagem: {image[:100] if isinstance(image, str) else image}")
                        
                except Exception as e:
                    print(f"      ⚠️  Erro ao parsear: {e}")
            
            # Procurar preço no HTML
            print(f"\n   💰 Procurando preço no HTML:")
            price_selectors = [
                ('span', {'class': 'price'}),
                ('span', {'class': 'woocommerce-Price-amount'}),
                ('p', {'class': 'price'}),
                ('div', {'class': 'price'}),
                ('span', {'itemprop': 'price'}),
                ('meta', {'property': 'product:price:amount'}),
                ('div', {'class': 'product-price'}),
                ('span', {'class': 'amount'})
            ]
            
            for tag, attrs in price_selectors:
                elements = soup.find_all(tag, attrs)
                if elements:
                    print(f"   ✅ [{tag}] encontrado: {len(elements)} elemento(s)")
                    for elem in elements[:2]:
                        texto = elem.get('content') or elem.get_text()
                        print(f"      Valor: {texto.strip()[:100]}")
            
            # Procurar linhas com R$
            print(f"\n   💵 Linhas com 'R$':")
            lines_with_price = [line.strip() for line in r.text.split('\n') if 'R$' in line]
            print(f"   Encontradas: {len(lines_with_price)} linhas")
            for line in lines_with_price[:5]:
                print(f"      {line[:150]}")
            
            # Procurar API endpoints
            print(f"\n   🔌 APIs detectadas:")
            api_patterns = [
                '/api/catalog',
                '/rest/V1/',
                '/products.json',
                '/api/products',
                '.json'
            ]
            
            for pattern in api_patterns:
                if pattern in r.text:
                    print(f"   ✅ Padrão encontrado: {pattern}")
            
        except Exception as e:
            print(f"   ❌ Erro: {e}")

asyncio.run(diagnosticar())
