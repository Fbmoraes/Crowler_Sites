"""
Interceptar e usar a API do MatConcasa diretamente
"""

import asyncio
from playwright.async_api import async_playwright
import json

async def intercept_and_extract():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)  # Visível para debug
        page = await browser.new_page()
        
        api_data = {}
        
        # Interceptar a resposta da API /api/product/basic
        async def handle_response(response):
            if '/api/product/basic' in response.url:
                try:
                    data = await response.json()
                    api_data['product_basic'] = data
                    print(f"\n✅ INTERCEPTADO: /api/product/basic")
                    print(f"   Total produtos: {data.get('total_count', 0)}")
                    print(f"   Items: {len(data.get('items', []))}")
                except Exception as e:
                    print(f"Erro ao ler API: {e}")
        
        page.on('response', handle_response)
        
        url = "https://www.matconcasa.com.br/produto/ducha-hydra-optima-8-temperaturas-5500w-127v-dpop-8-551br-362905"
        
        print(f"Abrindo: {url}\n")
        await page.goto(url, wait_until='networkidle', timeout=30000)
        
        # Aguardar a API carregar
        await page.wait_for_timeout(3000)
        
        if 'product_basic' in api_data:
            print("\n=== DADOS DA API ===")
            data = api_data['product_basic']
            
            # Extrair primeiro produto
            items = data.get('items', [])
            if items:
                produto = items[0]
                
                print(f"\n📦 Produto:")
                print(f"   ID: {produto.get('id')}")
                print(f"   SKU: {produto.get('sku')}")
                print(f"   Nome: {produto.get('name')}")
                print(f"   Status: {produto.get('stock_status')}")
                
                # Preço
                price_range = produto.get('price_range', {})
                min_price = price_range.get('minimum_price', {})
                final_price = min_price.get('final_price', {})
                
                print(f"\n💰 Preço:")
                print(f"   Valor: {final_price.get('value')}")
                print(f"   Moeda: {final_price.get('currency')}")
                
                # Desconto
                discount = min_price.get('discount', {})
                if discount.get('percent_off', 0) > 0:
                    print(f"   Desconto: {discount.get('percent_off')}%")
                    print(f"   Preço original: {min_price.get('regular_price', {}).get('value')}")
                
                # Imagem
                small_image = produto.get('small_image', {})
                print(f"\n🖼️ Imagem:")
                print(f"   URL: {small_image.get('url', 'N/A')[:80]}")
                
                # Categorias
                categorias = produto.get('categories', [])
                if categorias:
                    print(f"\n📁 Categorias:")
                    for cat in categorias[:3]:
                        print(f"   - {cat.get('name')}")
                
                # Salvar JSON completo
                with open('produto_matcon_interceptado.json', 'w', encoding='utf-8') as f:
                    json.dump(produto, f, indent=2, ensure_ascii=False)
                print(f"\n✅ JSON completo salvo em: produto_matcon_interceptado.json")
        else:
            print("\n❌ API não foi interceptada!")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(intercept_and_extract())
