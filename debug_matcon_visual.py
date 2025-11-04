"""
Debug visual do MatConcasa para entender estrutura da página
"""

import asyncio
from playwright.async_api import async_playwright

async def debug_matcon():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)  # headless=False para ver
        page = await browser.new_page()
        
        url = "https://www.matconcasa.com.br/produto/ducha-hydra-optima-8-temperaturas-5500w-127v-dpop-8-551br-362905"
        
        print(f"Abrindo: {url}\n")
        await page.goto(url, wait_until='networkidle', timeout=30000)
        
        print("Aguardando 3s para renderização...")
        await page.wait_for_timeout(3000)
        
        # Salvar screenshot
        await page.screenshot(path='debug_matcon_screenshot.png', full_page=True)
        print("✓ Screenshot salvo: debug_matcon_screenshot.png\n")
        
        # Testar seletores
        print("=== Testando Seletores ===\n")
        
        selectors = {
            'h1': 'h1',
            'main h1': 'main h1',
            'title': None,  # especial
            '[class*="ProductName"]': '[class*="ProductName"]',
            '[class*="product-name"]': '[class*="product-name"]',
        }
        
        for name, selector in selectors.items():
            if selector is None:  # title
                title = await page.title()
                print(f"{name}: {title}")
            else:
                try:
                    elements = await page.query_selector_all(selector)
                    print(f"\n{name}: {len(elements)} encontrados")
                    for i, el in enumerate(elements[:3], 1):
                        texto = await el.text_content()
                        print(f"  {i}. {texto[:100]}")
                except Exception as e:
                    print(f"{name}: Erro - {e}")
        
        print("\n\nMantendo navegador aberto por 30s para inspeção manual...")
        print("Pressione Ctrl+C para fechar antes")
        
        try:
            await page.wait_for_timeout(30000)
        except KeyboardInterrupt:
            print("\nFechando...")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(debug_matcon())
