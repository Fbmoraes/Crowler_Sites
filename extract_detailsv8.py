"""
EXTRACT DETAILS V8 - Ultra-Simplificado
Estratégia: ThreadPool + JSON-LD + Retry
"""
import httpx
from bs4 import BeautifulSoup
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

# Cliente HTTP compartilhado
client = httpx.Client(
    headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0'},
    timeout=15,
    follow_redirects=True,
    limits=httpx.Limits(max_connections=40)
)

def extrair_json_ld(soup):
    """Extrai dados de JSON-LD"""
    dados = {}
    
    for script in soup.find_all('script', type='application/ld+json'):
        try:
            data = json.loads(script.string)
            if isinstance(data, list):
                data = next((d for d in data if d.get('@type') == 'Product'), {})
            
            if data.get('@type') == 'Product':
                dados['nome'] = data.get('name')
                
                # Extrai preço - suporta Offer e AggregateOffer
                # Alguns sites (Wix/EMC Medical) usam "Offers" com O maiúsculo
                offers = data.get('offers') or data.get('Offers', {})
                if isinstance(offers, dict):
                    offer_type = offers.get('@type', '')
                    
                    if offer_type == 'AggregateOffer':
                        # Usa lowPrice para AggregateOffer
                        preco = offers.get('lowPrice') or offers.get('highPrice')
                        if preco:
                            dados['preco'] = str(preco)
                    else:
                        # Offer simples
                        preco = offers.get('price')
                        if preco:
                            dados['preco'] = str(preco)
                elif isinstance(offers, list):
                    # Lista de offers - pega o primeiro preço
                    for offer in offers:
                        preco = offer.get('price')
                        if preco:
                            dados['preco'] = str(preco)
                            break
                
                dados['marca'] = data.get('brand', {}).get('name') if isinstance(data.get('brand'), dict) else data.get('brand')
                dados['imagem'] = data.get('image', [None])[0] if isinstance(data.get('image'), list) else data.get('image')
                break
        except:
            pass
    
    return dados

def extrair_opengraph(soup):
    """Extrai dados de OpenGraph"""
    dados = {}
    
    og_title = soup.find('meta', property='og:title')
    if og_title:
        dados['nome'] = og_title.get('content')
    
    og_price = soup.find('meta', property='og:price:amount')
    if og_price:
        dados['preco'] = og_price.get('content')
    
    og_image = soup.find('meta', property='og:image')
    if og_image:
        dados['imagem'] = og_image.get('content')
    
    return dados

def extrair_javascript_vars(html_text):
    """Extrai dados de variáveis JavaScript inline (ex: Lojas Virtuais)"""
    dados = {}
    
    # Preço em var produto_preco = 57.90;
    match = re.search(r'var produto_preco\s*=\s*([\d.]+)', html_text)
    if match:
        dados['preco'] = match.group(1)
    
    return dados

def extrair_html(soup):
    """Extrai dados do HTML"""
    dados = {}
    
    # Nome
    h1 = soup.find('h1')
    if h1:
        dados['nome'] = h1.get_text(strip=True)
    
    # Preço
    for selector in [
        {'class': re.compile(r'price|preco', re.I)},
        {'itemprop': 'price'}
    ]:
        elem = soup.find(attrs=selector)
        if elem:
            texto = elem.get_text(strip=True)
            match = re.search(r'(\d+[.,]\d+)', texto)
            if match:
                dados['preco'] = match.group(1)
                break
    
    return dados

def processar_produto(produto, indice, total):
    """Processa um produto (com retry)"""
    url = produto['url']
    
    for tentativa in range(3):
        try:
            response = client.get(url)
            
            if response.status_code == 429:
                import time
                time.sleep(2 ** tentativa)
                continue
            
            if response.status_code != 200:
                continue
            
            soup = BeautifulSoup(response.text, 'lxml')
            
            # Cascata de extração
            dados = extrair_json_ld(soup)
            if not dados.get('nome') or not dados.get('preco'):
                dados.update(extrair_javascript_vars(response.text))
            if not dados.get('nome'):
                dados.update(extrair_opengraph(soup))
            if not dados.get('nome'):
                dados.update(extrair_html(soup))
            
            dados['url'] = url
            dados['indice'] = indice
            
            print(f"✅ [{indice}/{total}] {dados.get('nome', 'Produto')[:40]}")
            return dados
            
        except Exception as e:
            if tentativa == 2:
                print(f"❌ [{indice}/{total}] Erro: {url}")
                return {'url': url, 'indice': indice, 'erro': str(e)}
            import time
            time.sleep(0.5)
    
    return {'url': url, 'indice': indice, 'erro': 'Max retries'}

def extrair_detalhes_paralelo(produtos, show_message, max_produtos=10, max_workers=20):
    """Extração paralela com ThreadPool"""
    
    show_message(f"Processando {len(produtos)} produtos com {max_workers} threads...")
    
    # Limita quantidade
    produtos_processar = produtos[:max_produtos]
    
    resultados = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(processar_produto, prod, i+1, len(produtos_processar)): i
            for i, prod in enumerate(produtos_processar)
        }
        
        for future in as_completed(futures):
            try:
                resultado = future.result()
                resultados.append(resultado)
            except Exception as e:
                print(f"Erro: {e}")
    
    # Ordena por índice
    resultados.sort(key=lambda x: x.get('indice', 0))
    
    # Formata saída
    texto = f"=== {len(resultados)} PRODUTOS PROCESSADOS ===\n\n"
    for r in resultados:
        texto += f"Produto {r.get('indice')}\n"
        texto += f"Nome: {r.get('nome', 'N/A')}\n"
        texto += f"Preço: {r.get('preco', 'N/A')}\n"
        texto += f"URL: {r.get('url', 'N/A')}\n\n"
    
    show_message(f"✅ {len(resultados)} produtos processados!")
    
    return texto, resultados
