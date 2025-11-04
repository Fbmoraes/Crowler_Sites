"""
Teste do Discovery Mode isolado (sem depender de quintapp)
"""
import asyncio
from playwright.async_api import async_playwright

async def extrair_urls_homepage(base_url: str, max_produtos: int = 100):
    """
    Extrai URLs de produtos navegando pela homepage
    """
    print(f"🌐 DISCOVERY MODE: {base_url}\n")
    
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
                    const links = document.querySelectorAll('a[href*="/produto/"], a[href*="/product/"], a[href*="/p/"]');
                    return Array.from(links).map(a => a.href);
                }
            ''')
            
            for link in links:
                if link:
                    produtos_urls.add(link.split('?')[0].rstrip('/'))
            
            print(f"  ✓ {len(produtos_urls)} produtos na homepage")
            
            # 3. Tentar categorias principais
            if len(produtos_urls) < max_produtos:
                print(f"\n📁 Buscando em categorias...")
                
                categorias_padrao = [
                    "/produto/", "/produtos/", "/product/", "/products/",
                    "/ferramentas/", "/casa/", "/cozinha/", "/banheiro/",
                ]
                
                for cat in categorias_padrao[:3]:  # Limita a 3 categorias no teste
                    if len(produtos_urls) >= max_produtos:
                        break
                    
                    cat_url = base_url.rstrip('/') + cat
                    
                    try:
                        print(f"  Tentando: {cat}")
                        await page.goto(cat_url, wait_until='domcontentloaded', timeout=15000)
                        await page.wait_for_timeout(2000)
                        
                        # Scroll para lazy loading
                        for _ in range(2):
                            await page.evaluate('window.scrollBy(0, window.innerHeight)')
                            await page.wait_for_timeout(800)
                        
                        links_cat = await page.evaluate('''
                            () => {
                                const links = document.querySelectorAll('a[href*="/produto/"], a[href*="/product/"], a[href*="/p/"]');
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
                        
                        if novos > 0:
                            print(f"    ✓ +{novos} produtos (total: {len(produtos_urls)})")
                        
                    except Exception as e:
                        print(f"    ✗ Erro: {str(e)[:50]}")
            
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
    
    print(f"\n📦 Total filtrado: {len(produtos_reais)} produtos")
    
    return produtos_reais[:max_produtos]


if __name__ == "__main__":
    print("Testando Discovery Mode para MatConcasa\n")
    print("="*60)
    
    try:
        urls = asyncio.run(extrair_urls_homepage("https://www.matconcasa.com.br", max_produtos=10))
        
        print("\n" + "="*60)
        print(f"✅ SUCESSO! {len(urls)} URLs encontradas\n")
        
        if urls:
            print("Primeiras 5 URLs:")
            for i, url in enumerate(urls[:5], 1):
                print(f"  {i}. {url}")
        else:
            print("⚠️ Nenhuma URL encontrada")
            
    except Exception as e:
        print(f"\n❌ ERRO: {e}")
        import traceback
        traceback.print_exc()
