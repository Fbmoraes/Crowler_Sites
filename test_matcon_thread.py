"""
Testa Discovery Mode dentro de thread (como QuintApp faz)
"""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from playwright.async_api import async_playwright
import time

async def extrair_urls_homepage(base_url: str, max_produtos: int = 100):
    """
    Extrai URLs de produtos navegando pela homepage
    """
    print(f"🌐 DISCOVERY MODE: {base_url}\n")
    
    produtos_urls = set()
    
    try:
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
                
            finally:
                await browser.close()
                
    except Exception as e:
        print(f"❌ Erro: {e}")
        import traceback
        traceback.print_exc()
        return []
    
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


def extrair_urls_homepage_sync(base_url: str, max_produtos: int = 100):
    """Wrapper síncrono thread-safe"""
    try:
        # Tenta usar loop existente
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                print("⚠️ Loop já está rodando - criando thread dedicada")
                # Se já tem loop rodando, cria novo em thread separada
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(asyncio.run, extrair_urls_homepage(base_url, max_produtos))
                    return future.result()
            else:
                print("✓ Loop não está rodando - usando asyncio.run direto")
                return asyncio.run(extrair_urls_homepage(base_url, max_produtos))
        except RuntimeError as e:
            print(f"⚠️ RuntimeError: {e} - criando thread dedicada")
            # Se der erro com loop, força execução em thread nova
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, extrair_urls_homepage(base_url, max_produtos))
                return future.result()
    except Exception as e:
        print(f"❌ Erro no discovery: {e}")
        import traceback
        traceback.print_exc()
        return []


def processar_em_thread():
    """Simula o que QuintApp faz: roda discovery em thread"""
    print("\n" + "="*60)
    print("TESTE: Discovery rodando em thread (como QuintApp)")
    print("="*60 + "\n")
    
    inicio = time.time()
    urls = extrair_urls_homepage_sync("https://www.matconcasa.com.br", max_produtos=10)
    tempo = time.time() - inicio
    
    print("\n" + "="*60)
    if urls:
        print(f"✅ SUCESSO! {len(urls)} URLs em {tempo:.1f}s")
        print("\nPrimeiras 3:")
        for i, url in enumerate(urls[:3], 1):
            print(f"  {i}. {url}")
    else:
        print(f"❌ FALHOU! 0 URLs em {tempo:.1f}s")
    print("="*60)


if __name__ == "__main__":
    # Teste 1: Direto (sem thread)
    print("TESTE 1: Execução direta (sem thread)")
    print("="*60)
    urls = extrair_urls_homepage_sync("https://www.matconcasa.com.br", max_produtos=5)
    print(f"Resultado: {len(urls)} URLs\n")
    
    time.sleep(2)
    
    # Teste 2: Dentro de thread (como QuintApp)
    print("\n\nTESTE 2: Execução em thread (como QuintApp faz)")
    print("="*60)
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(processar_em_thread)
        future.result()
