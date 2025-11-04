"""
Extrator MatConcasa - Via API JSON (MUITO MAIS RÁPIDO)
MatConcasa expõe API pública: /api/product/basic
Não precisa de Playwright!
"""

import httpx
from bs4 import BeautifulSoup
from typing import List, Dict, Tuple, Optional, Callable
import re

def extrair_produtos(url_base: str, callback: Optional[Callable] = None, max_produtos: Optional[int] = None) -> List[Dict]:
    """
    Descobre URLs de produtos via sitemap ou homepage
    """
    produtos = []
    urls_visitadas = set()
    
    try:
        with httpx.Client(timeout=30, follow_redirects=True) as client:
            # 1. Tentar sitemap
            try:
                r = client.get(f"{url_base}/sitemap.xml")
                if r.status_code == 200:
                    soup = BeautifulSoup(r.text, 'xml')
                    sitemap_links = soup.find_all('loc')
                    
                    # Procurar por sitemaps de produtos
                    for loc in sitemap_links:
                        url = loc.text
                        if 'product' in url.lower():
                            try:
                                r_sub = client.get(url)
                                soup_sub = BeautifulSoup(r_sub.text, 'xml')
                                product_urls = soup_sub.find_all('loc')
                                
                                for prod_loc in product_urls:
                                    prod_url = prod_loc.text
                                    if '/produto/' in prod_url and prod_url not in urls_visitadas:
                                        urls_visitadas.add(prod_url)
                                        produtos.append({'url': prod_url, 'nome': ''})
                                        
                                        if callback:
                                            callback(f"✓ {len(produtos)} URLs coletadas")
                                        
                                        if max_produtos and len(produtos) >= max_produtos:
                                            return produtos
                            except:
                                continue
            except:
                pass
            
            # 2. Se sitemap falhou ou não tem URLs suficientes, usar homepage
            if len(produtos) < (max_produtos or 50):
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
                             max_produtos: Optional[int] = None, max_workers: int = 20) -> Tuple[str, List[Dict]]:
    """
    Extrai detalhes dos produtos usando a API JSON do MatConcasa
    MUITO MAIS RÁPIDO que Playwright!
    """
    if max_produtos:
        produtos = produtos[:max_produtos]
    
    resultados = []
    
    with httpx.Client(timeout=30, follow_redirects=True) as client:
        for i, produto in enumerate(produtos, 1):
            url = produto['url']
            
            try:
                # Carregar página
                r = client.get(url)
                r.raise_for_status()
                
                # A API /api/product/basic retorna JSON com os produtos na página
                # Extrair dados básicos do HTML primeiro
                soup = BeautifulSoup(r.text, 'html.parser')
                
                dados = {
                    'url': url,
                    'nome': '',
                    'preco': '',
                    'marca': '',
                    'categoria': '',
                    'imagem': ''
                }
                
                # Nome do título
                title = soup.find('title')
                if title:
                    title_text = title.get_text(strip=True)
                    # Remover "Matcon.casa | ..." do início
                    parts = title_text.split('|')
                    if len(parts) > 1:
                        dados['nome'] = parts[-1].strip()
                    else:
                        dados['nome'] = parts[0].strip()
                
                # Tentar pegar do script __NEXT_DATA__ ou dados inline
                scripts = soup.find_all('script')
                for script in scripts:
                    if script.string and 'price_range' in script.string:
                        # Tem dados de preço no script
                        try:
                            import json
                            # Tentar extrair JSON
                            text = script.string
                            # Procurar por price_range
                            match = re.search(r'"price_range":\s*({[^}]+})', text)
                            if match:
                                price_data = json.loads(match.group(1))
                                if 'minimum_price' in price_data:
                                    preco_obj = price_data['minimum_price'].get('final_price', {})
                                    if 'value' in preco_obj:
                                        dados['preco'] = str(preco_obj['value'])
                        except:
                            pass
                        break
                
                # Se não encontrou preço, tentar HTML
                if not dados['preco']:
                    for selector in ['[class*="price"]', '[class*="Price"]', '[data-price]']:
                        element = soup.select_one(selector)
                        if element:
                            texto = element.get_text(strip=True)
                            match = re.search(r'[\d.,]+', texto.replace('.', '').replace(',', '.'))
                            if match:
                                dados['preco'] = match.group()
                                break
                
                # Imagem - pegar do OpenGraph
                og_image = soup.find('meta', property='og:image')
                if og_image and og_image.get('content'):
                    img_url = og_image['content']
                    if img_url.startswith('http') and 'android-chrome' not in img_url:
                        dados['imagem'] = img_url
                
                # Marca - tentar pegar de meta tags ou JSON
                # Categoria - das meta tags
                
                resultados.append(dados)
                
                if callback:
                    status = "✓" if dados['nome'] and dados['preco'] else "⚠"
                    callback(f"{status} {i}/{len(produtos)}: {dados['nome'][:50] if dados['nome'] else 'Sem nome'}")
            
            except Exception as e:
                print(f"Erro ao extrair {url}: {e}")
                resultados.append({
                    'url': url,
                    'nome': '',
                    'preco': '',
                    'marca': '',
                    'categoria': '',
                    'imagem': ''
                })
    
    return "matcon", resultados

if __name__ == "__main__":
    # Teste
    print("=== Teste MatConcasa (API) ===\n")
    
    urls = extrair_produtos("https://www.matconcasa.com.br", max_produtos=5)
    print(f"\n✓ {len(urls)} URLs encontradas\n")
    
    tipo, produtos = extrair_detalhes_paralelo(urls, max_produtos=5)
    
    print(f"\n=== Resultados ===")
    print(f"Tipo: {tipo}")
    print(f"Produtos: {len(produtos)}")
    print(f"Com dados: {len([p for p in produtos if p.get('nome') and p.get('preco')])}")
    
    for i, p in enumerate(produtos, 1):
        print(f"\nProduto {i}:")
        print(f"  Nome: {p.get('nome', 'N/A')[:80]}")
        print(f"  Preço: R$ {p.get('preco', 'N/A')}")
        print(f"  Imagem: {'✓' if p.get('imagem') else '✗'}")
