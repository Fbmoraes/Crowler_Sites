"""
MagnumAuto com Playwright - testar se preço aparece com JS
"""
import asyncio
from playwright.async_api import async_playwright

async def test():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        print("=== MagnumAuto com Playwright ===\n")
        print("Navegando...")
        await page.goto("https://magnumauto.com.br/produto/l-a-10/", wait_until="networkidle", timeout=30000)
        
        # Aguardar preço aparecer
        await asyncio.sleep(3)
        
        # Buscar preço
        html = await page.content()
        
        # Salvar HTML renderizado
        with open('magnumauto_rendered.html', 'w', encoding='utf-8') as f:
            f.write(html)
        print("✓ HTML renderizado salvo\n")
        
        # Procurar preço no HTML renderizado
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, 'html.parser')
        
        # R$ no texto
        rs = soup.find_all(string=lambda t: t and 'R$' in t)
        print(f"Elementos com R$: {len(rs)}")
        for r in rs[:5]:
            print(f"  - {r.strip()[:100]}")
        
        # Classes com price
        prices = soup.find_all(class_=lambda x: x and 'price' in str(x).lower())
        print(f"\nClasses com 'price': {len(prices)}")
        for p in prices[:5]:
            classes = ' '.join(p.get('class', []))
            print(f"  - {classes}: {p.get_text(strip=True)[:100]}")
        
        await browser.close()

asyncio.run(test())
