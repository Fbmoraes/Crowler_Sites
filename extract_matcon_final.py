"""
Extrator MatConcasa - DEFINITIVO
Usa interceptação da API /api/product/basic com Playwright
ESTRATÉGIA: Abre a página, intercepta a API, extrai os dados do JSON
"""

import asyncio
from playwright.async_api import async_playwright
from typing import List, Dict, Tuple, Optional, Callable
import httpx
from bs4 import BeautifulSoup
import concurrent.futures

def extrair_produtos(url_base: str, callback: Optional[Callable] = None, max_produtos: Optional[int] = None) -> List[Dict]:
    """
    Descobre URLs de produtos via sitemap/homepage (httpx - rápido)
    """
    produtos = []
    urls_visitadas = set()
    
    try:
        with httpx.Client(timeout=30, follow_redirects=True) as client:
            # Tentar homepage
            r = client.get(url_base)
            soup = BeautifulSoup(r.text, 'html.parser')
            
            for link in soup.find_all('a', href=True):
                href = link['href']
                if '/produto/' in href:
                    url_completa = href if href.startswith('http') else f"{url_base.rstrip('/')}{href}"
                    if url_completa not in urls_visitadas:
                        urls_visitadas.add(url_completa)
                        produtos.append({'url': url_completa, 'nome': ''})
                        
                        if callback:
                            callback(f"✓ {len(produtos)} URLs coletadas")
                        
                        if max_produtos and len(produtos) >= max_produtos:
                            return produtos
    except Exception as e:
        print(f"Erro ao coletar URLs: {e}")
    
    return produtos

def extrair_detalhes_paralelo(produtos: List[Dict], callback: Optional[Callable] = None, 
                             max_produtos: Optional[int] = None, max_workers: int = 3) -> Tuple[str, List[Dict]]:
    """
    Extrai detalhes interceptando a API do MatConcasa
    max_workers=3 (Playwright é pesado, não fazer muitas instâncias)
    """
    try:
        loop = asyncio.get_running_loop()
        # Já tem loop rodando, usar thread isolada
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(lambda: asyncio.run(_extrair_detalhes_async(produtos, callback, max_produtos, max_workers)))
            # Timeout de 5 minutos para não travar
            return future.result(timeout=300)
    except RuntimeError:
        # Não tem loop, pode usar asyncio.run direto
        return asyncio.run(_extrair_detalhes_async(produtos, callback, max_produtos, max_workers))
    except Exception as e:
        print(f"❌ Erro em extrair_detalhes_paralelo: {e}")
        import traceback
        traceback.print_exc()
        # Retornar vazio em caso de erro
        return "matcon", []

async def _extrair_detalhes_async(produtos: List[Dict], callback: Optional[Callable], 
                                  max_produtos: Optional[int], max_workers: int) -> Tuple[str, List[Dict]]:
    """Extrai detalhes usando Playwright + API Intercept"""
    
    if max_produtos:
        produtos = produtos[:max_produtos]
    
    resultados = []
    total = len(produtos)
    
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=['--disable-blink-features=AutomationControlled']  # Evitar detecção de bot
            )
            
            # Processar em batches pequenos
            batch_size = max_workers
            for i in range(0, len(produtos), batch_size):
                batch = produtos[i:i + batch_size]
                tasks = []
                
                for idx, produto in enumerate(batch):
                    task = _extrair_produto_api(browser, produto, callback, i + idx + 1, total)
                    tasks.append(task)
                
                batch_results = await asyncio.gather(*tasks, return_exceptions=True)
                
                for result in batch_results:
                    if isinstance(result, dict):
                        resultados.append(result)
                    elif isinstance(result, Exception):
                        print(f"⚠️ Erro em produto: {result}")
                        # Adicionar produto vazio
                        resultados.append({
                            'url': '',
                            'nome': '',
                            'preco': '',
                            'marca': '',
                            'categoria': '',
                            'imagem': ''
                        })
            
            await browser.close()
    except Exception as e:
        print(f"❌ Erro no Playwright: {e}")
        import traceback
        traceback.print_exc()
    
    return "matcon", resultados

async def _extrair_produto_api(browser, produto: Dict, callback: Optional[Callable], 
                               index: int, total: int) -> Dict:
    """Extrai um produto interceptando a API"""
    
    context = None
    page = None
    
    try:
        context = await browser.new_context()
        page = await context.new_page()
        
        # Timeout mais curto para não travar
        page.set_default_timeout(20000)  # 20 segundos
        
        api_data = {}
        
        # Interceptar API
        async def handle_response(response):
            if '/api/product/basic' in response.url:
                try:
                    data = await response.json()
                    api_data['products'] = data.get('items', [])
                except:
                    pass
        
        page.on('response', handle_response)
        
        url = produto['url']
        print(f"   [{index}/{total}] Processando: {url[:60]}...")
        
        await page.goto(url, wait_until='networkidle', timeout=25000)
        await page.wait_for_timeout(2000)  # Aguardar API
        
        dados = {
            'url': url,
            'nome': '',
            'preco': '',
            'marca': '',
            'categoria': '',
            'imagem': ''
        }
        
        # Se interceptou a API, usar os dados dela
        if 'products' in api_data and api_data['products']:
            # Pegar o primeiro produto (normalmente é o produto da página)
            produto_api = api_data['products'][0]
            
            dados['nome'] = produto_api.get('name', '')
            
            # Preço
            price_range = produto_api.get('price_range', {})
            min_price = price_range.get('minimum_price', {})
            final_price = min_price.get('final_price', {})
            if 'value' in final_price:
                dados['preco'] = str(final_price['value'])
            
            # Imagem
            small_image = produto_api.get('small_image', {})
            img_url = small_image.get('url', '')
            if img_url and img_url.startswith('http') and 'placeholder' not in img_url:
                dados['imagem'] = img_url
            
            # Categoria
            categorias = produto_api.get('categories', [])
            if categorias:
                dados['categoria'] = categorias[0].get('name', '')
            
            # Marca - não vem na API basic, tentar pegar de variants
            variants = produto_api.get('variants', [])
            if variants:
                variant_product = variants[0].get('product', {})
                small_img = variant_product.get('small_image', {})
                if small_img.get('url'):
                    # Usar imagem do variant (melhor qualidade)
                    img_variant = small_img['url']
                    if 'placeholder' not in img_variant:
                        dados['imagem'] = img_variant
        
        if callback:
            status = "✓" if dados['nome'] and dados['preco'] else "⚠"
            callback(f"{status} {index}/{total}: {dados['nome'][:50] if dados['nome'] else 'Sem dados'}")
        
        print(f"   ✓ [{index}/{total}] {dados['nome'][:50] if dados['nome'] else 'N/A'} - R$ {dados['preco']}")
        return dados
        
    except Exception as e:
        print(f"   ❌ [{index}/{total}] Erro: {e}")
        return {
            'url': produto.get('url', ''),
            'nome': '',
            'preco': '',
            'marca': '',
            'categoria': '',
            'imagem': ''
        }
    finally:
        if context:
            try:
                await context.close()
            except:
                pass

if __name__ == "__main__":
    # Teste
    print("=== Teste MatConcasa (API Intercept) ===\n")
    
    urls = extrair_produtos("https://www.matconcasa.com.br", max_produtos=3)
    print(f"\n✓ {len(urls)} URLs encontradas\n")
    
    tipo, produtos = extrair_detalhes_paralelo(urls, max_produtos=3, max_workers=2)
    
    print(f"\n=== Resultados ===")
    print(f"Tipo: {tipo}")
    print(f"Produtos: {len(produtos)}")
    print(f"Com dados completos: {len([p for p in produtos if p.get('nome') and p.get('preco')])}")
    
    for i, p in enumerate(produtos, 1):
        print(f"\nProduto {i}:")
        print(f"  Nome: {p.get('nome', 'N/A')[:80]}")
        print(f"  Preço: R$ {p.get('preco', 'N/A')}")
        print(f"  Categoria: {p.get('categoria', 'N/A')}")
        print(f"  Imagem: {'✓' if p.get('imagem') else '✗'}")
