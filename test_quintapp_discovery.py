"""
Teste rápido da lógica de discovery no QuintApp
"""
import asyncio
from playwright.async_api import async_playwright

async def testar_discovery_matcon():
    """Testa discovery no MatConcasa"""
    base_url = "https://www.matconcasa.com.br/"
    print(f"\n🌐 Testando Discovery: {base_url}\n")
    
    produtos_urls = set()
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        try:
            # 1. Carregar homepage
            print("📄 Carregando homepage...")
            await page.goto(base_url, wait_until='networkidle', timeout=30000)
            await page.wait_for_timeout(3000)
            
            # 2. Extrair links da homepage
            print("🔍 Buscando produtos na homepage...")
            links = await page.evaluate('''
                () => {
                    const links = document.querySelectorAll('a[href*="/produto/"]');
                    return Array.from(links).map(a => a.href);
                }
            ''')
            
            for link in links:
                if link:
                    produtos_urls.add(link.split('?')[0].rstrip('/'))
            
            print(f"  ✓ {len(produtos_urls)} produtos na homepage")
            
            # 3. Testar uma categoria
            cat_url = base_url.rstrip('/') + "/ferramentas/"
            print(f"\n📁 Testando categoria: {cat_url}")
            
            try:
                await page.goto(cat_url, wait_until='domcontentloaded', timeout=15000)
                await page.wait_for_timeout(2000)
                
                # Scroll
                for i in range(2):
                    await page.evaluate('window.scrollBy(0, window.innerHeight)')
                    await page.wait_for_timeout(800)
                    print(f"  📜 Scroll {i+1}/2")
                
                links_cat = await page.evaluate('''
                    () => {
                        const links = document.querySelectorAll('a[href*="/produto/"]');
                        return Array.from(links).map(a => a.href);
                    }
                ''')
                
                novos = 0
                for link in links_cat:
                    if link:
                        url_limpa = link.split('?')[0].rstrip('/')
                        if url_limpa not in produtos_urls:
                            produtos_urls.add(url_limpa)
                            novos += 1
                
                print(f"  ✓ {novos} novos produtos (total: {len(produtos_urls)})")
                
            except Exception as e:
                print(f"  ⚠️ Erro na categoria: {e}")
        
        finally:
            await browser.close()
    
    # Filtrar produtos reais
    produtos_reais = []
    for url in produtos_urls:
        partes = url.split('/')
        if len(partes) >= 5:
            ultima_parte = partes[-1]
            if '-' in ultima_parte and len(ultima_parte) > 10:
                produtos_reais.append(url)
    
    print(f"\n📦 Total filtrado: {len(produtos_reais)} produtos reais")
    print(f"\n✅ Teste concluído! Discovery funcionando.")
    
    # Mostra primeiros 5
    print(f"\n📋 Primeiros 5 produtos:")
    for i, url in enumerate(produtos_reais[:5], 1):
        print(f"  {i}. {url}")
    
    return produtos_reais


if __name__ == "__main__":
    produtos = asyncio.run(testar_discovery_matcon())
    print(f"\n🎉 Discovery encontrou {len(produtos)} produtos!")
