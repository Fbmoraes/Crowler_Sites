"""
EXTRATOR DERMOMANIPULAÇÕES - INTEGRAÇÃO QUINTAPP
Compatível com extract_linksv8.py e extract_detailsv8.py
"""

import asyncio
import httpx
from bs4 import BeautifulSoup
import json
from urllib.parse import urlparse
from typing import List, Dict, Callable


def extrair_produtos(url_base: str, callback: Callable = None, max_produtos: int = None) -> List[Dict]:
    """
    Interface compatível com QuintApp
    Extrai produtos do Dermomanipulações
    """
    return asyncio.run(_extrair_dermo(url_base, callback, max_produtos))


async def _extrair_dermo(url_base: str, callback: Callable = None, max_produtos: int = None) -> List[Dict]:
    """
    Extrai produtos do Dermomanipulações usando JSON-LD das categorias
    """
    def log(msg):
        if callback:
            callback(msg)
        print(f"[DERMO] {msg}")
    
    log("Buscando sitemap...")
    
    produtos = []
    
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        try:
            # Buscar sitemap
            resp = await client.get(f"{url_base}/sitemap.xml")
            
            if resp.status_code != 200:
                log(f"Erro ao buscar sitemap: status {resp.status_code}")
                return []
            
            soup = BeautifulSoup(resp.text, 'xml')
            urls = soup.find_all('url')
            
            log(f"Sitemap: {len(urls)} URLs")
            
            # Filtrar categorias (não produtos individuais)
            excluir_patterns = [
                '/atendimento', '/quemsomos', '/contato', '/politica',
                '/termos', '/duvidas', '/trocas', '/entrega', '/compra',
                '/pagamento', '/receita', '/carrinho', '/checkout',
                '/login', '/cadastro', '/conta', '/pedidos', '/favoritos',
                '/home-', '/dia-', '/outlet', '/frete', '/formas', '/nossos'
            ]
            
            categorias_urls = []
            
            for url_tag in urls:
                loc = url_tag.find('loc')
                if loc:
                    url = loc.text.strip()
                    
                    # Pular homepage e produtos individuais
                    if url == f"{url_base}/" or url == url_base or '/produto/' in url:
                        continue
                    
                    path = urlparse(url).path.lower()
                    
                    # Pular institucionais
                    if any(excluir in path for excluir in excluir_patterns):
                        continue
                    
                    # URLs curtas = categorias
                    path_limpo = path.strip('/')
                    if path_limpo and '/' not in path_limpo:
                        categorias_urls.append(url)
            
            log(f"Categorias encontradas: {len(categorias_urls)}")
            log("Extraindo produtos das categorias...")
            
            # Processa categorias e extrai produtos do JSON-LD
            for i, cat_url in enumerate(categorias_urls, 1):
                try:
                    resp = await client.get(cat_url)
                    
                    if resp.status_code == 200:
                        soup = BeautifulSoup(resp.text, 'html.parser')
                        
                        # Busca JSON-LD ItemList
                        json_lds = soup.find_all('script', type='application/ld+json')
                        
                        for script in json_lds:
                            try:
                                data = json.loads(script.string)
                                
                                if data.get('@type') == 'ItemList':
                                    items = data.get('itemListElement', [])
                                    
                                    for item in items:
                                        if item.get('@type') == 'Product':
                                            produto = {
                                                'nome': item.get('name'),
                                                'url': item.get('url'),
                                                'imagem': item.get('image')
                                            }
                                            
                                            # Extrai preço
                                            offers = item.get('offers', {})
                                            if isinstance(offers, dict):
                                                preco = offers.get('price')
                                                if preco:
                                                    produto['preco'] = f"R$ {float(preco):.2f}"
                                            
                                            # Adiciona se válido
                                            if produto['nome'] and produto['url']:
                                                produtos.append(produto)
                                    
                                    if items:
                                        log(f"[{i}/{len(categorias_urls)}] {cat_url.split('/')[-1]}: {len(items)} produtos")
                                        
                                        # Se já atingiu o limite, para
                                        if max_produtos and len(produtos) >= max_produtos:
                                            log(f"Limite de {max_produtos} produtos atingido")
                                            return produtos[:max_produtos]
                            
                            except:
                                continue
                    
                    # Rate limit
                    await asyncio.sleep(0.3)
                
                except Exception as e:
                    log(f"Erro em {cat_url}: {str(e)[:50]}")
                    continue
            
            log(f"Total de produtos encontrados: {len(produtos)}")
            
            if max_produtos:
                produtos = produtos[:max_produtos]
                log(f"Limitado a {len(produtos)} produtos")
            
            return produtos
        
        except Exception as e:
            log(f"Erro na extração: {e}")
            return []


def extrair_detalhes_paralelo(produtos: List[Dict], callback: Callable = None, 
                              max_produtos: int = None, max_workers: int = 20):
    """
    Interface compatível com QuintApp
    Produtos do Dermomanipulações já vêm com detalhes, apenas retorna
    """
    if callback:
        callback(f"Produtos já extraídos: {len(produtos)}")
    
    if max_produtos:
        produtos = produtos[:max_produtos]
    
    return len(produtos), produtos


# Teste standalone
if __name__ == "__main__":
    print("🧪 Teste do extrator Dermomanipulações\n")
    
    def callback_test(msg):
        print(f"  {msg}")
    
    produtos = extrair_produtos(
        "https://www.dermomanipulacoes.com.br",
        callback=callback_test,
        max_produtos=20
    )
    
    print(f"\n✅ {len(produtos)} produtos extraídos\n")
    
    if produtos:
        print("📦 Primeiros 3 produtos:")
        for i, prod in enumerate(produtos[:3], 1):
            print(f"\n{i}. {prod.get('nome', 'N/A')}")
            print(f"   Preço: {prod.get('preco', 'N/A')}")
            print(f"   URL: {prod.get('url', 'N/A')[:60]}...")
