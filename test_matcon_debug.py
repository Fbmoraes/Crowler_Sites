"""
Teste simplificado com muito debug
"""
import asyncio
from playwright.async_api import async_playwright

async def test():
    print("1. Iniciando Playwright...")
    
    try:
        async with async_playwright() as p:
            print("2. Lançando browser...")
            browser = await p.chromium.launch(headless=True)
            
            print("3. Criando página...")
            page = await browser.new_page()
            
            api_interceptada = False
            
            async def handle_response(response):
                nonlocal api_interceptada
                if '/api/product/basic' in response.url:
                    print(f"   ✅ API INTERCEPTADA: {response.url}")
                    api_interceptada = True
                    try:
                        data = await response.json()
                        items = data.get('items', [])
                        if items:
                            produto = items[0]
                            print(f"   Nome: {produto.get('name')}")
                            print(f"   Preço: {produto.get('price_range', {}).get('minimum_price', {}).get('final_price', {}).get('value')}")
                    except Exception as e:
                        print(f"   Erro ao ler JSON: {e}")
            
            page.on('response', handle_response)
            
            url = "https://www.matconcasa.com.br/produto/ducha-hydra-optima-8-temperaturas-5500w-127v-dpop-8-551br-362905"
            
            print(f"4. Navegando para: {url[:80]}...")
            await page.goto(url, wait_until='networkidle', timeout=30000)
            
            print("5. Aguardando 3 segundos...")
            await page.wait_for_timeout(3000)
            
            print(f"6. API foi interceptada? {api_interceptada}")
            
            print("7. Fechando browser...")
            await browser.close()
            
            print("✅ TESTE CONCLUÍDO!")
            
    except Exception as e:
        print(f"❌ ERRO: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("=== Teste MatConcasa Debug ===\n")
    asyncio.run(test())
