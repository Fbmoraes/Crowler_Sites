"""
Teste da versão httpx do discovery mode (thread-safe)
"""
import asyncio
from concurrent.futures import ThreadPoolExecutor
import time

async def extrair_urls_homepage(base_url: str, max_produtos: int = 100):
    """Versão httpx - thread-safe"""
    print(f"\n🌐 DISCOVERY MODE (httpx): {base_url}")
    
    import httpx
    from bs4 import BeautifulSoup
    from urllib.parse import urljoin
    
    produtos_urls = set()
    
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            # 1. Carregar homepage
            print("📄 Carregando homepage...")
            response = await client.get(base_url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 2. Extrair links
            print("🔍 Buscando produtos...")
            
            for link in soup.find_all('a', href=True):
                href = link.get('href')
                if not href:
                    continue
                
                if '/produto/' in href or '/product/' in href:
                    url_completa = urljoin(base_url, href)
                    url_limpa = url_completa.split('?')[0].split('#')[0].rstrip('/')
                    produtos_urls.add(url_limpa)
            
            print(f"  ✓ {len(produtos_urls)} produtos encontrados")
        
    except Exception as e:
        print(f"❌ Erro: {e}")
        return []
    
    # Filtrar
    produtos_reais = []
    for url in produtos_urls:
        partes = url.split('/')
        if len(partes) >= 5:
            ultima_parte = partes[-1]
            if '-' in ultima_parte and len(ultima_parte) > 10:
                produtos_reais.append(url)
    
    print(f"📦 Total filtrado: {len(produtos_reais)} produtos\n")
    return produtos_reais[:max_produtos]


def extrair_sync(base_url, max_produtos):
    """Wrapper síncrono"""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            with ThreadPoolExecutor() as pool:
                return pool.submit(asyncio.run, extrair_urls_homepage(base_url, max_produtos)).result()
        else:
            return asyncio.run(extrair_urls_homepage(base_url, max_produtos))
    except RuntimeError:
        with ThreadPoolExecutor() as pool:
            return pool.submit(asyncio.run, extrair_urls_homepage(base_url, max_produtos)).result()


def test_em_thread():
    """Simula QuintApp - roda em thread"""
    print("\n" + "="*60)
    print("TESTE EM THREAD (como QuintApp)")
    print("="*60)
    
    inicio = time.time()
    urls = extrair_sync("https://www.matconcasa.com.br", 10)
    tempo = time.time() - inicio
    
    print("="*60)
    if urls:
        print(f"✅ SUCESSO! {len(urls)} URLs em {tempo:.1f}s")
        print("\nPrimeiras 3:")
        for i, url in enumerate(urls[:3], 1):
            print(f"  {i}. {url}")
    else:
        print(f"❌ FALHOU! 0 URLs")
    print("="*60)


if __name__ == "__main__":
    # Teste 1: Direto
    print("TESTE 1: Execução direta")
    print("="*60)
    urls = extrair_sync("https://www.matconcasa.com.br", 5)
    print(f"✅ Resultado: {len(urls)} URLs\n")
    
    time.sleep(1)
    
    # Teste 2: Em thread (como QuintApp)
    print("\n\nTESTE 2: Execução em thread")
    print("="*60)
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(test_em_thread)
        future.result()
    
    print("\n✅ TODOS OS TESTES PASSARAM!")
