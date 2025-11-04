"""
Extrator especializado para Sacada (VTEX + React/Apollo)
Extrai dados do Apollo Cache (GraphQL normalizado) no HTML

Compatível com QuintApp:
- extrair_produtos(url_base, callback=None, max_produtos=None) -> List[Dict]
- extrair_detalhes_paralelo(produtos, callback=None, max_produtos=None, max_workers=20) -> (str, List[Dict])

Observações:
- Ignora sitemap product-0 (produtos antigos/inativos)
- Prioriza product-1, product-2, product-3
"""

import httpx
from bs4 import BeautifulSoup
import json
from typing import Dict, Optional, List, Tuple
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse

def extrair_apollo_cache(html: str) -> Optional[Dict]:
    """Extrai dados do Apollo Cache no HTML"""
    soup = BeautifulSoup(html, 'html.parser')
    
    # Procurar script com Apollo Cache (contém "Product:")
    scripts = [s for s in soup.find_all('script') if s.text and 'Product:' in s.text]
    
    if not scripts:
        return None
    
    try:
        # Parse JSON do Apollo Cache
        cache_data = json.loads(scripts[0].text)
        return cache_data
    except:
        return None

def resolver_referencia(cache: Dict, ref: any) -> any:
    """Resolve referências do GraphQL normalizado"""
    if isinstance(ref, dict) and 'id' in ref:
        key = ref['id']
        return cache.get(key, ref)
    return ref

def extrair_produto_sacada(url: str, timeout: int = 15) -> Dict:
    """
    Extrai dados de produto do Sacada
    
    Retorna dict com: nome, preco, preco_original, marca, categoria, sku, url
    """
    try:
        # Fazer requisição
        resp = httpx.get(url, timeout=timeout, follow_redirects=True)
        
        if resp.status_code != 200:
            return {
                'url': url,
                'erro': f'Status {resp.status_code}'
            }
        
        # Extrair Apollo Cache
        cache = extrair_apollo_cache(resp.text)
        
        if not cache:
            return {
                'url': url,
                'erro': 'Apollo Cache não encontrado'
            }
        
        # Encontrar chave do produto (começa com "Product:")
        product_keys = [k for k in cache.keys() if k.startswith('Product:') and '.' not in k]
        
        if not product_keys:
            return {
                'url': url,
                'erro': 'Produto não encontrado no cache'
            }
        
        product_key = product_keys[0]
        product = cache[product_key]
        
        # Extrair dados básicos
        nome = product.get('productName', 'N/A')
        marca = product.get('brand', 'N/A')
        product_id = product.get('productId', 'N/A')
        descricao = product.get('description', 'N/A')
        
        # Extrair categorias
        categories_obj = product.get('categories')
        if isinstance(categories_obj, dict) and 'json' in categories_obj:
            categorias = categories_obj['json']
            # Pegar categoria mais específica (última antes de /)
            categoria = categorias[0].strip('/').split('/')[-1] if categorias else 'N/A'
        else:
            categoria = 'N/A'
        
        # Extrair preços (resolver referências)
        preco = 'N/A'
        preco_original = 'N/A'
        
        price_range_ref = product.get('priceRange')
        if isinstance(price_range_ref, dict) and 'id' in price_range_ref:
            price_range = resolver_referencia(cache, price_range_ref)
            
            # Preço de venda
            if 'sellingPrice' in price_range:
                selling_ref = price_range['sellingPrice']
                selling_data = resolver_referencia(cache, selling_ref)
                if 'lowPrice' in selling_data:
                    preco = selling_data['lowPrice']
            
            # Preço de lista
            if 'listPrice' in price_range:
                list_ref = price_range['listPrice']
                list_data = resolver_referencia(cache, list_ref)
                if 'lowPrice' in list_data:
                    preco_original = list_data['lowPrice']
        
        # Extrair primeiro SKU
        items = product.get('items', [])
        sku = 'N/A'
        if items:
            first_item_ref = items[0]
            if isinstance(first_item_ref, dict) and 'id' in first_item_ref:
                first_item = resolver_referencia(cache, first_item_ref)
                sku = first_item.get('itemId', 'N/A')
        
        return {
            'url': url,
            'nome': nome,
            'preco': f'R$ {preco}' if preco != 'N/A' else 'N/A',
            'preco_original': f'R$ {preco_original}' if preco_original != 'N/A' else 'N/A',
            'marca': marca,
            'categoria': categoria,
            'sku': sku,
            'product_id': product_id,
            'descricao': descricao[:200] + '...' if len(descricao) > 200 else descricao,
        }
        
    except Exception as e:
        return {
            'url': url,
            'erro': str(e)
        }

def extrair_urls_sitemap(sitemap_url: str) -> List[str]:
    """Extrai URLs de produtos do sitemap"""
    try:
        resp = httpx.get(sitemap_url, timeout=15)
        soup = BeautifulSoup(resp.text, 'xml')
        urls = [loc.text for loc in soup.find_all('loc')]
        return urls
    except:
        return []


# ==========================
# Integração QuintApp
# ==========================
def _descobrir_produtos_categorias(url_base: str, max_produtos: int = 100) -> List[str]:
    """Descobre produtos navegando pelas categorias (quando sitemap não existe)"""
    base = url_base.rstrip('/')
    produtos = []
    
    try:
        # Buscar categorias na homepage
        r = httpx.get(base, timeout=15)
        soup = BeautifulSoup(r.text, 'html.parser')
        
        # Encontrar links de categorias
        categorias = [a.get('href') for a in soup.find_all('a', href=True) if '/shop/' in a.get('href', '')]
        categorias = list(set(categorias))[:10]  # Limita a 10 categorias
        
        print(f"[SACADA] Descobrindo produtos em {len(categorias)} categorias...")
        
        for cat in categorias:
            if len(produtos) >= max_produtos:
                break
            
            cat_url = f"{base}{cat}" if cat.startswith('/') else cat
            # Aumenta PS (itens por página) para pegar mais produtos
            cat_url = cat_url.split('?')[0] + '?PS=100'
            
            try:
                r_cat = httpx.get(cat_url, timeout=15)
                soup_cat = BeautifulSoup(r_cat.text, 'html.parser')
                
                # Buscar links de produtos VTEX (terminam com /p ou /p?)
                # Filtra apenas links que são produtos (não categorias/páginas)
                links = [a.get('href') for a in soup_cat.find_all('a', href=True) 
                        if a.get('href', '').endswith('/p') or '/p?' in a.get('href', '')]
                # Limpar e normalizar URLs (remover query params)
                links = [l.split('?')[0] if '?' in l else l for l in links]
                links = [f"{base}{l}" if l.startswith('/') else l for l in links]
                links = list(set(links))
                
                produtos.extend(links)
                print(f"[SACADA]   {cat.split('/')[2] if len(cat.split('/')) > 2 else 'categoria'}: +{len(links)} produtos")
            except Exception as e:
                print(f"[SACADA]   Erro em categoria: {e}")
                continue
        
        # Deduplica
        produtos = list(set(produtos))[:max_produtos]
        return produtos
    except Exception as e:
        print(f"[SACADA] Erro descobrindo por categorias: {e}")
        return []

def _listar_sitemaps_produto(url_base: str) -> List[str]:
    """Retorna lista de sitemaps de produto válidos, ignorando product-0"""
    base = url_base.rstrip('/')
    index_url = f"{base}/sitemap.xml"
    sitemaps = []
    
    try:
        r = httpx.get(index_url, timeout=15, follow_redirects=True)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, 'xml')
            for loc in soup.find_all('loc'):
                u = loc.get_text(strip=True)
                if '/sitemap/' in u and 'product' in u and 'product-0' not in u:
                    sitemaps.append(u)
        else:
            print(f"[SACADA] Sitemap retornou status {r.status_code}")
    except httpx.ConnectError as e:
        print(f"[SACADA] ❌ Erro de conexão: URL '{base}' não acessível. Verifique o domínio.")
        print(f"[SACADA] Dica: O domínio correto do Sacada pode ser diferente (ex: lojasacada.com.br)")
        return []  # Não usar fallback se não conseguir conectar
    except Exception as e:
        print(f"[SACADA] Erro ao acessar sitemap: {e}")

    # Fallback: tentar product-1,2,3
    if not sitemaps:
        print(f"[SACADA] Tentando fallback sitemap: product-1,2,3...")
        for i in (1, 2, 3):
            try:
                test_url = f"{base}/sitemap/product-{i}.xml"
                r_test = httpx.get(test_url, timeout=10)
                if r_test.status_code == 200:
                    sitemaps.append(test_url)
            except:
                pass
    
    return sitemaps


def extrair_produtos(url_base: str, callback=None, max_produtos: Optional[int] = None) -> List[Dict]:
    """
    Retorna lista de links de produtos a partir dos sitemaps de produto.
    Se sitemaps não existirem, descobre produtos navegando categorias.
    Formato: [{ 'url': str, 'nome': str }]
    """
    def log(msg: str):
        if callback:
            callback(msg)
        print(f"[SACADA/LINKS] {msg}")

    sitemaps = _listar_sitemaps_produto(url_base)
    log(f"Sitemaps de produto: {len(sitemaps)}")

    urls: List[str] = []
    
    # Se não há sitemaps, tenta descoberta por categorias
    if not sitemaps:
        log("Sitemap não disponível, usando descoberta por categorias...")
        urls = _descobrir_produtos_categorias(url_base, max_produtos or 100)
        log(f"Produtos descobertos: {len(urls)}")
    else:
        # Usa sitemaps
        for sm in sitemaps:
            links = extrair_urls_sitemap(sm)
            # Filtra URLs de produto VTEX (terminam com /p)
            links = [u for u in links if u.endswith('/p')]
            if links:
                log(f"{sm.split('/')[-1]}: {len(links)} URLs")
                urls.extend(links)
            if max_produtos and len(urls) >= max_produtos:
                break

    # Deduplica mantendo ordem
    vistos = set()
    urls_unicas = []
    for u in urls:
        if u not in vistos:
            vistos.add(u)
            urls_unicas.append(u)

    if max_produtos:
        urls_unicas = urls_unicas[:max_produtos]

    produtos = [{
        'url': u,
        'nome': u.rstrip('/').split('/')[-2].replace('-', ' ').title() if u.endswith('/p') else u.split('/')[-1].replace('-', ' ').title()
    } for u in urls_unicas]

    log(f"Total de produtos para detalhar: {len(produtos)}")
    return produtos


def _processar_detalhe(url: str, indice: int, total: int) -> Dict:
    dados = extrair_produto_sacada(url)
    dados['indice'] = indice
    # Normaliza campos principais
    if 'preco' in dados and isinstance(dados['preco'], (int, float)):
        dados['preco'] = f"R$ {dados['preco']:.2f}"
    return dados


def extrair_detalhes_paralelo(produtos: List[Dict], callback=None, 
                              max_produtos: Optional[int] = None, max_workers: int = 20) -> Tuple[str, List[Dict]]:
    """
    Extrai detalhes em paralelo via Apollo Cache.
    Retorna (texto_resumo, detalhes)
    """
    if max_produtos:
        produtos = produtos[:max_produtos]

    total = len(produtos)
    resultados: List[Dict] = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_processar_detalhe, prod['url'], i + 1, total): i
            for i, prod in enumerate(produtos)
        }
        for fut in as_completed(futures):
            try:
                res = fut.result()
                resultados.append(res)
                if callback:
                    callback(f"✓ [{res.get('indice','?')}/{total}] {res.get('nome','Produto')} ")
            except Exception as e:
                if callback:
                    callback(f"✗ Erro: {e}")

    resultados.sort(key=lambda x: x.get('indice', 0))

    # Monta texto de resumo compatível
    texto = f"=== {len(resultados)} PRODUTOS PROCESSADOS (SACADA) ===\n\n"
    for r in resultados[:10]:
        texto += f"[{r.get('indice')}] {r.get('nome','N/A')} - {r.get('preco','N/A')}\n{r.get('url')}\n\n"

    return texto, resultados

def main():
    """Teste do extrator"""
    print("=== EXTRATOR SACADA (Apollo Cache) ===\n")
    
    # Testar com URL de exemplo
    test_url = 'https://www.sacada.com/blusa-malha-amarracao-01041624-0002/p'
    
    print(f"Testando: {test_url}\n")
    
    resultado = extrair_produto_sacada(test_url)
    
    print("Resultado:")
    for chave, valor in resultado.items():
        print(f"  {chave}: {valor}")
    
    # Testar com múltiplos produtos do sitemap
    print("\n" + "="*60)
    print("Testando extração em lote (sitemap product-1)")
    print("="*60 + "\n")
    
    sitemap_url = 'https://www.sacada.com/sitemap/product-1.xml'
    urls = extrair_urls_sitemap(sitemap_url)
    
    print(f"URLs encontradas: {len(urls)}")
    print(f"Testando primeiras 5...\n")
    
    for i, url in enumerate(urls[:5], 1):
        print(f"{i}. {url}")
        resultado = extrair_produto_sacada(url)
        
        if 'erro' in resultado:
            print(f"   ✗ Erro: {resultado['erro']}")
        else:
            print(f"   ✓ {resultado['nome']}")
            print(f"   ✓ {resultado['preco']}")
            print(f"   ✓ Marca: {resultado['marca']}")
        
        time.sleep(1)  # Rate limit
        print()

if __name__ == '__main__':
    main()
