"""
Extrator MatConcasa - Next.js/React SPA que requer JavaScript
Usa Playwright para renderizar e extrair dados
"""

import asyncio
from playwright.async_api import async_playwright
import httpx
from bs4 import BeautifulSoup
from typing import List, Dict, Tuple, Optional, Callable
import re

def extrair_urls_homepage_sync(base_url: str, max_produtos: int = 100, callback: Optional[Callable] = None) -> List[Dict]:
    """Versão síncrona para compatibilidade com QuintApp"""
    try:
        # Tenta usar loop existente
        loop = asyncio.get_running_loop()
        # Se há loop rodando, cria tarefa nele
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(lambda: asyncio.run(extrair_urls_homepage(base_url, max_produtos, callback)))
            return future.result()
    except RuntimeError:
        # Não há loop rodando, pode usar asyncio.run
        return asyncio.run(extrair_urls_homepage(base_url, max_produtos, callback))

async def extrair_urls_homepage(base_url: str, max_produtos: int = 100, callback: Optional[Callable] = None) -> List[Dict]:
    """
    Extrai URLs de produtos da homepage e categorias usando httpx (mais rápido que Playwright)
    """
    produtos = []
    urls_visitadas = set()
    
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        try:
            # 1. Homepage
            r = await client.get(base_url)
            soup = BeautifulSoup(r.text, 'html.parser')
            
            # Encontrar links de produtos
            for link in soup.find_all('a', href=True):
                href = link['href']
                if '/produto/' in href:
                    url_completa = href if href.startswith('http') else f"{base_url.rstrip('/')}{href}"
                    if url_completa not in urls_visitadas:
                        urls_visitadas.add(url_completa)
                        nome = link.get_text(strip=True) or "Produto"
                        produtos.append({'url': url_completa, 'nome': nome})
                        
                        if callback:
                            callback(f"✓ {len(produtos)}/{max_produtos} URLs coletadas")
                        
                        if len(produtos) >= max_produtos:
                            return produtos
            
            # 2. Buscar categorias
            categorias = []
            for link in soup.find_all('a', href=True):
                href = link['href']
                if any(cat in href for cat in ['/categoria/', '/departamento/', '/c/']):
                    url_cat = href if href.startswith('http') else f"{base_url.rstrip('/')}{href}"
                    if url_cat not in categorias:
                        categorias.append(url_cat)
            
            # 3. Visitar algumas categorias
            for cat_url in categorias[:5]:  # Limitar a 5 categorias
                if len(produtos) >= max_produtos:
                    break
                
                try:
                    r = await client.get(cat_url)
                    soup = BeautifulSoup(r.text, 'html.parser')
                    
                    for link in soup.find_all('a', href=True):
                        href = link['href']
                        if '/produto/' in href:
                            url_completa = href if href.startswith('http') else f"{base_url.rstrip('/')}{href}"
                            if url_completa not in urls_visitadas:
                                urls_visitadas.add(url_completa)
                                nome = link.get_text(strip=True) or "Produto"
                                produtos.append({'url': url_completa, 'nome': nome})
                                
                                if callback:
                                    callback(f"✓ {len(produtos)}/{max_produtos} URLs coletadas")
                                
                                if len(produtos) >= max_produtos:
                                    break
                except:
                    continue
            
        except Exception as e:
            print(f"Erro ao extrair URLs: {e}")
    
    return produtos

def extrair_detalhes_paralelo(produtos: List[Dict], callback: Optional[Callable] = None, 
                             max_produtos: Optional[int] = None, max_workers: int = 5) -> Tuple[str, List[Dict]]:
    """
    Extrai detalhes dos produtos usando Playwright (necessário para renderizar JavaScript)
    max_workers limitado a 5 para não sobrecarregar (Playwright é pesado)
    """
    try:
        # Tenta usar loop existente
        loop = asyncio.get_running_loop()
        # Se há loop rodando, cria tarefa em thread separada
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(lambda: asyncio.run(_extrair_detalhes_async(produtos, callback, max_produtos, max_workers)))
            return future.result()
    except RuntimeError:
        # Não há loop rodando, pode usar asyncio.run
        return asyncio.run(_extrair_detalhes_async(produtos, callback, max_produtos, max_workers))

async def _extrair_detalhes_async(produtos: List[Dict], callback: Optional[Callable], 
                                  max_produtos: Optional[int], max_workers: int) -> Tuple[str, List[Dict]]:
    """Extrai detalhes usando Playwright com paralelização controlada"""
    
    if max_produtos:
        produtos = produtos[:max_produtos]
    
    resultados = []
    total = len(produtos)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        
        # Processar em batches para controlar concorrência
        batch_size = max_workers
        for i in range(0, len(produtos), batch_size):
            batch = produtos[i:i + batch_size]
            tasks = []
            
            for produto in batch:
                task = _extrair_produto_com_playwright(browser, produto, callback, i + len(tasks) + 1, total)
                tasks.append(task)
            
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in batch_results:
                if isinstance(result, dict) and result.get('nome'):
                    resultados.append(result)
        
        await browser.close()
    
    return "matcon", resultados

async def _extrair_produto_com_playwright(browser, produto: Dict, callback: Optional[Callable], 
                                         index: int, total: int) -> Dict:
    """Extrai dados de um produto usando Playwright"""
    
    context = await browser.new_context()
    page = await context.new_page()
    
    try:
        url = produto['url']
        await page.goto(url, wait_until='networkidle', timeout=30000)
        
        # Aguardar renderização (MatConcasa é Next.js, precisa de tempo)
        await page.wait_for_timeout(3000)
        
        dados = {
            'url': url,
            'nome': '',
            'preco': '',
            'marca': '',
            'categoria': '',
            'imagem': ''
        }
        
        # Nome - tentar vários seletores (EVITAR h1 do banner)
        for selector in [
            '[class*="ProductName"]', '[class*="product-name"]', '[data-testid="product-name"]',
            'main h1', 'article h1', '[class*="titulo"]', '[class*="Title"]'
        ]:
            try:
                element = await page.query_selector(selector)
                if element:
                    texto = await element.text_content()
                    if texto and texto.strip() and 'Parceria' not in texto and 'MATCON' not in texto:
                        dados['nome'] = texto.strip()
                        break
            except:
                continue
        
        # Se não encontrou nome, tentar title da página
        if not dados['nome']:
            try:
                title = await page.title()
                # Limpar title (remover "| Matcon.casa" etc)
                if title:
                    parts = title.split('|')
                    if len(parts) > 1 and 'Matcon' not in parts[0]:
                        dados['nome'] = parts[0].strip()
            except:
                pass
        
        # Preço - tentar vários seletores
        for selector in [
            '[class*="price"]', '[class*="Price"]', '[class*="valor"]',
            '[data-testid="price"]', '[itemprop="price"]'
        ]:
            try:
                element = await page.query_selector(selector)
                if element:
                    texto = await element.text_content()
                    if texto:
                        # Extrair apenas números e vírgula/ponto
                        preco_match = re.search(r'[\d.,]+', texto.replace('.', '').replace(',', '.'))
                        if preco_match:
                            dados['preco'] = preco_match.group()
                            break
            except:
                continue
        
        # Marca
        for selector in ['[class*="brand"]', '[class*="Brand"]', '[class*="marca"]', '[itemprop="brand"]']:
            try:
                element = await page.query_selector(selector)
                if element:
                    texto = await element.text_content()
                    if texto and texto.strip():
                        dados['marca'] = texto.strip()
                        break
            except:
                continue
        
        # Imagem
        for selector in ['[class*="product-image"] img', '[class*="ProductImage"] img', 'img[itemprop="image"]', 'main img']:
            try:
                element = await page.query_selector(selector)
                if element:
                    src = await element.get_attribute('src')
                    if src and src.startswith('http'):
                        dados['imagem'] = src
                        break
            except:
                continue
        
        if callback:
            status = "✓" if dados['nome'] and dados['preco'] else "⚠"
            callback(f"{status} {index}/{total}: {dados['nome'][:50] if dados['nome'] else 'Sem nome'}")
        
        return dados
        
    except Exception as e:
        print(f"Erro ao extrair {produto['url']}: {e}")
        return {
            'url': produto['url'],
            'nome': '',
            'preco': '',
            'marca': '',
            'categoria': '',
            'imagem': ''
        }
    finally:
        await context.close()

# Interface para QuintApp
def extrair_produtos(url_base: str, callback: Optional[Callable] = None, max_produtos: Optional[int] = None) -> List[Dict]:
    """Função compatível com QuintApp - coleta URLs"""
    return extrair_urls_homepage_sync(url_base, max_produtos or 100, callback)

if __name__ == "__main__":
    # Teste rápido
    print("=== Teste MatConcasa ===\n")
    
    # 1. Descobrir URLs
    print("1. Descobrindo URLs...\n")
    urls = extrair_produtos("https://www.matconcasa.com.br", max_produtos=5)
    print(f"\n✓ {len(urls)} URLs encontradas\n")
    
    # 2. Extrair detalhes
    print("2. Extraindo detalhes...\n")
    tipo, produtos = extrair_detalhes_paralelo(urls, max_produtos=5, max_workers=2)
    
    print(f"\n=== Resultados ===")
    print(f"Tipo: {tipo}")
    print(f"Produtos extraídos: {len(produtos)}")
    print(f"Com nome e preço: {len([p for p in produtos if p.get('nome') and p.get('preco')])}")
    
    for i, p in enumerate(produtos[:3], 1):
        print(f"\nProduto {i}:")
        print(f"  Nome: {p.get('nome', 'N/A')[:80]}")
        print(f"  Preço: {p.get('preco', 'N/A')}")
        print(f"  Marca: {p.get('marca', 'N/A')}")
