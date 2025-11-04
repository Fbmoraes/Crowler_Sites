"""
Teste específico de produto do MH Studios
"""

import asyncio
import httpx
from bs4 import BeautifulSoup
import json

async def testar_produto_real():
    # Pega URL de produto real do sitemap
    url_base = "https://mhstudios.com.br"
    
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        # Busca sitemap de produtos
        print("🔍 Buscando sitemap de produtos...")
        resp = await client.get(f"{url_base}/sitemap_products_1.xml?from=9689740017983&to=10144737558847")
        
        soup = BeautifulSoup(resp.text, 'xml')
        urls = soup.find_all('url')
        
        print(f"📦 {len(urls)} produtos no sitemap")
        
        # Pega primeiro produto válido (não homepage)
        produto_url = None
        for url_tag in urls:
            loc = url_tag.find('loc')
            if loc:
                url = loc.text
                if '/products/' in url:
                    produto_url = url
                    break
        
        if not produto_url:
            print("❌ Nenhum produto encontrado")
            return
        
        print(f"\n🔍 Testando: {produto_url}")
        
        # Testa HTML
        print("\n" + "=" * 60)
        print("HTML DO PRODUTO")
        print("=" * 60)
        
        resp = await client.get(produto_url)
        print(f"Status: {resp.status_code}")
        
        with open("mhstudios_produto_real.html", "w", encoding="utf-8") as f:
            f.write(resp.text)
        print("✅ HTML salvo")
        
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # JSON-LD
        print("\n📋 JSON-LD:")
        json_lds = soup.find_all('script', type='application/ld+json')
        
        for i, script in enumerate(json_lds, 1):
            try:
                data = json.loads(script.string)
                
                # Se for lista, pega primeiro item
                if isinstance(data, list):
                    data = data[0] if data else {}
                
                print(f"\nScript #{i} - Type: {data.get('@type', 'N/A')}")
                
                if data.get('@type') == 'Product':
                    print(f"  Nome: {data.get('name')}")
                    
                    offers = data.get('offers', {})
                    if isinstance(offers, dict):
                        print(f"  Preço: {offers.get('price')} {offers.get('priceCurrency')}")
                        print(f"  Disponibilidade: {offers.get('availability')}")
                    
                    print("\n  JSON completo:")
                    print(json.dumps(data, indent=2, ensure_ascii=False))
            
            except Exception as e:
                print(f"  Erro: {e}")
        
        # Testa API Shopify
        print("\n" + "=" * 60)
        print("SHOPIFY API")
        print("=" * 60)
        
        product_handle = produto_url.split('/products/')[-1].split('?')[0]
        api_url = f"{url_base}/products/{product_handle}.json"
        
        print(f"🔍 API: {api_url}")
        
        try:
            resp = await client.get(api_url)
            print(f"Status: {resp.status_code}")
            
            if resp.status_code == 200:
                data = resp.json()
                product = data.get('product', {})
                
                print(f"\n✅ Produto via API:")
                print(f"  ID: {product.get('id')}")
                print(f"  Título: {product.get('title')}")
                print(f"  Vendor: {product.get('vendor')}")
                
                variants = product.get('variants', [])
                if variants:
                    print(f"\n  Variantes ({len(variants)}):")
                    for v in variants[:3]:
                        print(f"    - {v.get('title')}: R$ {v.get('price')} (disponível: {v.get('available')})")
                
                with open("mhstudios_api_real.json", "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                print("\n✅ JSON salvo em mhstudios_api_real.json")
            else:
                print(f"❌ API retornou {resp.status_code}")
        
        except Exception as e:
            print(f"❌ Erro na API: {e}")

asyncio.run(testar_produto_real())
