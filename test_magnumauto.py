"""
Diagnóstico Magnum Auto
Screenshot mostra: 49 produtos encontrados, mas todos N/A (nome, preço, marca)
"""
import asyncio
import httpx
from bs4 import BeautifulSoup
import json

BASE_URL = "https://www.magnumauto.com.br"

async def diagnosticar():
    print("="*60)
    print("DIAGNÓSTICO: MAGNUM AUTO")
    print("="*60)
    
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        # 1. Testar homepage
        print(f"\n1️⃣ Testando homepage: {BASE_URL}")
        try:
            r = await client.get(BASE_URL)
            print(f"   Status: {r.status_code}")
            soup = BeautifulSoup(r.text, 'html.parser')
            
            # Detectar plataforma
            if 'woocommerce' in r.text.lower():
                print("   ✅ Plataforma: WooCommerce")
            elif 'shopify' in r.text.lower():
                print("   ✅ Plataforma: Shopify")
            elif 'vtex' in r.text.lower():
                print("   ✅ Plataforma: VTEX")
            else:
                print("   ⚠️  Plataforma: Desconhecida")
            
        except Exception as e:
            print(f"   ❌ Erro: {e}")
        
        # 2. Buscar sitemap
        print(f"\n2️⃣ Buscando sitemap")
        sitemap_urls = [
            f"{BASE_URL}/sitemap.xml",
            f"{BASE_URL}/sitemap_index.xml",
            f"{BASE_URL}/product-sitemap.xml",
            f"{BASE_URL}/wp-sitemap.xml"
        ]
        
        sitemap_encontrado = None
        for sitemap_url in sitemap_urls:
            try:
                r = await client.get(sitemap_url)
                if r.status_code == 200 and 'xml' in r.headers.get('content-type', ''):
                    print(f"   ✅ Sitemap encontrado: {sitemap_url}")
                    sitemap_encontrado = sitemap_url
                    print(f"   Tamanho: {len(r.text)} bytes")
                    
                    # Contar URLs de produtos
                    if '<loc>' in r.text:
                        urls = r.text.count('<loc>')
                        print(f"   URLs encontradas: {urls}")
                    
                    break
            except:
                continue
        
        if not sitemap_encontrado:
            print("   ⚠️  Nenhum sitemap encontrado")
        
        # 3. Testar página de produto específica
        print(f"\n3️⃣ Testando página de produto")
        
        # Tentar encontrar um produto no sitemap
        produto_url = None
        if sitemap_encontrado:
            try:
                r = await client.get(sitemap_encontrado)
                soup = BeautifulSoup(r.text, 'xml')
                locs = soup.find_all('loc')
                
                # Pegar primeira URL que parece produto
                for loc in locs[:20]:
                    url = loc.get_text().strip()
                    # URLs de produtos WooCommerce geralmente têm /produto/ ou /product/
                    if '/produto/' in url or '/product/' in url or url.count('/') >= 4:
                        produto_url = url
                        break
                
                if produto_url:
                    print(f"   URL de teste: {produto_url}")
                else:
                    print("   ⚠️  Nenhuma URL de produto encontrada no sitemap")
            except Exception as e:
                print(f"   ⚠️  Erro ao parsear sitemap: {e}")
        
        # Se não encontrou no sitemap, tentar buscar na homepage
        if not produto_url:
            print("   Buscando produto na homepage...")
            try:
                r = await client.get(BASE_URL)
                soup = BeautifulSoup(r.text, 'html.parser')
                
                # Procurar links de produtos
                for link in soup.find_all('a', href=True):
                    href = link['href']
                    if '/produto/' in href or '/product/' in href:
                        if href.startswith('http'):
                            produto_url = href
                        else:
                            produto_url = BASE_URL + href
                        break
                
                if produto_url:
                    print(f"   ✅ Produto encontrado: {produto_url}")
            except Exception as e:
                print(f"   ❌ Erro ao buscar na homepage: {e}")
        
        # 4. Analisar estrutura do produto
        if produto_url:
            print(f"\n4️⃣ Analisando produto: {produto_url}")
            try:
                r = await client.get(produto_url)
                print(f"   Status: {r.status_code}")
                
                with open('magnumauto_produto.html', 'w', encoding='utf-8') as f:
                    f.write(r.text)
                print(f"   ✅ HTML salvo em: magnumauto_produto.html")
                
                soup = BeautifulSoup(r.text, 'html.parser')
                
                # Procurar JSON-LD
                json_lds = soup.find_all('script', type='application/ld+json')
                print(f"\n   JSON-LD encontrados: {len(json_lds)}")
                for i, script in enumerate(json_lds):
                    try:
                        data = json.loads(script.string)
                        tipo = data.get('@type', 'Unknown')
                        print(f"   - Script {i+1}: {tipo}")
                        
                        if tipo == 'Product':
                            print(f"      ✅ Produto JSON-LD encontrado!")
                            print(f"      Nome: {data.get('name', 'N/A')}")
                            
                            offers = data.get('offers', {})
                            if isinstance(offers, dict):
                                preco = offers.get('price', 'N/A')
                                print(f"      Preço: {preco}")
                            elif isinstance(offers, list) and offers:
                                preco = offers[0].get('price', 'N/A')
                                print(f"      Preço: {preco}")
                    except:
                        pass
                
                # Procurar preço no HTML
                print(f"\n   Procurando preço no HTML...")
                price_patterns = [
                    ('span', {'class': 'price'}),
                    ('span', {'class': 'woocommerce-Price-amount'}),
                    ('p', {'class': 'price'}),
                    ('div', {'class': 'price'}),
                    ('span', {'itemprop': 'price'}),
                    ('meta', {'property': 'product:price:amount'})
                ]
                
                for tag, attrs in price_patterns:
                    elements = soup.find_all(tag, attrs)
                    if elements:
                        print(f"   ✅ [{tag}] encontrado: {len(elements)} elemento(s)")
                        for elem in elements[:2]:
                            texto = elem.get('content') or elem.get_text()
                            print(f"      Valor: {texto.strip()[:100]}")
                
                # Procurar linhas com R$
                print(f"\n   Linhas com 'R$':")
                lines_with_price = [line for line in r.text.split('\n') if 'R$' in line]
                print(f"   Encontradas: {len(lines_with_price)} linhas")
                for line in lines_with_price[:3]:
                    print(f"      {line.strip()[:100]}")
                
            except Exception as e:
                print(f"   ❌ Erro: {e}")

asyncio.run(diagnosticar())
