"""
Versão 4 - OTIMIZADA PARA PERFORMANCE
- Processamento paralelo com ThreadPoolExecutor
- Extração estruturada primeiro (HTML parsing)
- IA apenas como fallback opcional
- Cache de resultados
"""

import httpx
from bs4 import BeautifulSoup
import re
import json
import time
import random
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

# Lock para sincronizar mensagens
message_lock = Lock()

# Cache global
cache_produtos = {}

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Connection": "keep-alive",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}

RETRY_STATUS_CODES = {408, 425, 429, 500, 502, 503, 504}

_shared_client = httpx.Client(
    headers=DEFAULT_HEADERS,
    timeout=15,
    follow_redirects=True,
    limits=httpx.Limits(max_connections=40, max_keepalive_connections=20),
)

_client_warm = False


def _http_get(url, *, timeout=15, referer=None, max_retries=5):
    """GET resiliente com headers de navegador e backoff."""
    global _client_warm

    if referer and not _client_warm:
        try:
            _shared_client.get(referer, headers=DEFAULT_HEADERS, timeout=timeout)
        except Exception:
            pass
        _client_warm = True

    last_exception = None

    for attempt in range(1, max_retries + 1):
        try:
            headers = DEFAULT_HEADERS.copy()
            if referer:
                headers["Referer"] = referer
            response = _shared_client.get(url, headers=headers, timeout=timeout)

            if response.status_code in RETRY_STATUS_CODES:
                wait_time = min(8.0, (1.6 ** attempt) + random.uniform(0, 0.6))
                time.sleep(wait_time)
                continue

            response.raise_for_status()
            return response
        except (httpx.HTTPError, httpx.ReadTimeout) as exc:
            last_exception = exc
            wait_time = min(8.0, (1.6 ** attempt) + random.uniform(0, 0.6))
            time.sleep(wait_time)

    if last_exception:
        raise last_exception

    raise RuntimeError(f"Falha ao obter URL: {url}")

# ==== FALLBACK LEVE PARA SPA/NEXT.JS (sem Selenium) ====
import json as _json
import re as _re
from urllib.parse import urlparse as _urlparse

def _pick_first(*vals):
    for v in vals:
        if isinstance(v, str) and v.strip():
            return v.strip()
        if v is not None and v != "":
            return v
    return None

def _normalize_product_fields(obj):
    try:
        if not isinstance(obj, dict):
            return None
        nome = _pick_first(obj.get('name'), obj.get('title'))
        preco = _pick_first(
            obj.get('price'), obj.get('lowPrice'), obj.get('bestPrice'),
            obj.get('sellingPrice'), obj.get('preco'), obj.get('amount'),
        )
        preco_original = _pick_first(obj.get('listPrice'), obj.get('highPrice'), obj.get('precoOriginal'))
        sku = _pick_first(obj.get('sku'), obj.get('id'), obj.get('code'))
        marca = obj.get('brand')
        if isinstance(marca, dict):
            marca = _pick_first(marca.get('name'), marca.get('brand'))
        imgs = obj.get('images') or obj.get('image') or obj.get('fotos')
        if isinstance(imgs, str):
            imagens = [imgs]
        elif isinstance(imgs, list):
            imagens = [x for x in imgs if isinstance(x, str) and x]
        elif isinstance(imgs, dict):
            imagens = [v for v in imgs.values() if isinstance(v, str)]
        else:
            imagens = None
        if not any([nome, preco, sku, (imagens and len(imagens) > 0)]):
            return None
        out = {}
        if nome: out['nome'] = nome
        if preco: out['preco'] = preco
        if preco_original: out['preco_original'] = preco_original
        if sku: out['sku'] = sku
        if marca: out['marca'] = marca
        if imagens: out['imagens'] = imagens[:5]
        return out
    except Exception:
        return None

def _find_product_in_obj(obj, max_depth=3):
    if max_depth < 0:
        return None
    norm = _normalize_product_fields(obj)
    if norm:
        return norm
    if isinstance(obj, dict):
        for v in obj.values():
            res = _find_product_in_obj(v, max_depth - 1)
            if res:
                return res
    elif isinstance(obj, list):
        for it in obj:
            res = _find_product_in_obj(it, max_depth - 1)
            if res:
                return res
    return None

def _spa_nextdata_inline(html):
    try:
        m = _re.search(r'<script[^>]*id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>', html, _re.S | _re.I)
        if not m:
            return None, None
        data = _json.loads(m.group(1))
        build_id = data.get('buildId')
        props = data.get('props') or {}
        page_props = props.get('pageProps') or props
        produto = _find_product_in_obj(page_props)
        return produto, build_id
    except Exception:
        return None, None

def _spa_nextdata_fetch(url, html, client):
    try:
        _, build_id = _spa_nextdata_inline(html)
        if not build_id:
            return None
        p = _urlparse(url)
        path = p.path.rstrip('/')
        if not path:
            path = '/index'
        json_path = f"/_next/data/{build_id}{path}.json"
        base = f"{p.scheme}://{p.netloc}"
        resp = client.get(base + json_path, headers=DEFAULT_HEADERS, timeout=10)
        if resp.status_code != 200:
            return None
        data = resp.json()
        props = data.get('pageProps') or data.get('props') or data
        return _find_product_in_obj(props)
    except Exception:
        return None

def _spa_apollo_state(html):
    try:
        m = _re.search(r'__APOLLO_STATE__\s*=\s*(\{.*?\});', html, _re.S)
        if not m:
            return None
        data = _json.loads(m.group(1))
        if isinstance(data, dict):
            for v in data.values():
                res = _find_product_in_obj(v)
                if res:
                    return res
        return None
    except Exception:
        return None

def _coletar_produtos_jsonld(data):
    produtos = []

    if isinstance(data, dict):
        tipo = data.get('@type')
        if isinstance(tipo, list):
            if 'Product' in tipo:
                produtos.append(data)
        elif tipo == 'Product':
            produtos.append(data)

        for value in data.values():
            if isinstance(value, (dict, list)):
                produtos.extend(_coletar_produtos_jsonld(value))

    elif isinstance(data, list):
        for item in data:
            produtos.extend(_coletar_produtos_jsonld(item))

    return produtos


def _normalizar_url(valor):
    if not valor:
        return None
    return valor.strip().rstrip('/').lower()


def extrair_dados_estruturados(html, url):
    """
    Extração RÁPIDA de dados estruturados (JSON-LD, meta tags, etc)
    SEM usar IA
    """
    soup = BeautifulSoup(html, "html.parser")
    dados = {}
    
    # 1. Busca JSON-LD (muito comum em e-commerce)
    json_ld_scripts = soup.find_all('script', type='application/ld+json')
    produtos_jsonld = []
    for script in json_ld_scripts:
        try:
            text = script.string or script.get_text()
            if not text:
                continue
            data = json.loads(text)
            produtos_jsonld.extend(_coletar_produtos_jsonld(data))
        except:
            continue

    produto_selecionado = None
    url_normalizada = _normalizar_url(url)
    path = urlparse(url).path
    sku_match = re.search(r'(\d+)(?:/)?$', path)
    sku_alvo = sku_match.group(1) if sku_match else None

    def _oferta_para_lista(oferta):
        if isinstance(oferta, list):
            return oferta
        if isinstance(oferta, dict):
            return [oferta]
        return []

    for produto in produtos_jsonld:
        ofertas = _oferta_para_lista(produto.get('offers'))
        urls_oferta = [_normalizar_url(of.get('url')) for of in ofertas]
        if url_normalizada and any(url_normalizada == u for u in urls_oferta if u):
            produto_selecionado = produto
            break

    if not produto_selecionado:
        for produto in produtos_jsonld:
            produto_url = _normalizar_url(produto.get('url'))
            main_entity = produto.get('mainEntityOfPage')
            main_entity_url = _normalizar_url(main_entity.get('@id') if isinstance(main_entity, dict) else main_entity)
            if url_normalizada in (produto_url, main_entity_url):
                produto_selecionado = produto
                break

    if not produto_selecionado and sku_alvo:
        for produto in produtos_jsonld:
            if str(produto.get('sku', '')).strip() == sku_alvo:
                produto_selecionado = produto
                break

    if not produto_selecionado and produtos_jsonld:
        produto_selecionado = produtos_jsonld[0]

    if produto_selecionado:
        dados['nome'] = produto_selecionado.get('name', '')
        dados['descricao'] = produto_selecionado.get('description', '')
        dados['categoria'] = produto_selecionado.get('category', '')

        brand = produto_selecionado.get('brand')
        if isinstance(brand, dict):
            dados['marca'] = brand.get('name', '')
        else:
            dados['marca'] = brand or ''

        imagens = produto_selecionado.get('image')
        if isinstance(imagens, list):
            dados['imagens'] = imagens[:5]
        elif isinstance(imagens, str):
            dados['imagens'] = [imagens]

        ofertas = _oferta_para_lista(produto_selecionado.get('offers'))
        if ofertas:
            primeira_oferta = ofertas[0]
            
            # Preço atual (pode ser lowPrice ou price)
            preco_atual = primeira_oferta.get('lowPrice') or primeira_oferta.get('price', '')
            preco_alto = primeira_oferta.get('highPrice')
            
            dados['preco'] = preco_atual
            
            # Preço original só se for diferente do preço atual (indica promoção real)
            if preco_alto and preco_alto != preco_atual:
                try:
                    # Converte para float para comparar (evita diferenças de string vs número)
                    if float(str(preco_alto).replace(',', '.')) > float(str(preco_atual).replace(',', '.')):
                        dados['preco_original'] = preco_alto
                except (ValueError, TypeError):
                    # Se der erro na conversão, mantém como string mesmo
                    if preco_alto != preco_atual:
                        dados['preco_original'] = preco_alto
            
            dados['moeda'] = primeira_oferta.get('priceCurrency', 'BRL')

            # Disponibilidade: só marca True/False se houver informação
            # Caso contrário deixa None (desconhecido)
            disponibilidade = primeira_oferta.get('availability', '')
            if disponibilidade and isinstance(disponibilidade, str) and disponibilidade.strip():
                status = disponibilidade.rsplit('/', 1)[-1]
                dados['estoque'] = status
                # Só marca disponível se tiver informação clara
                if 'instock' in disponibilidade.lower():
                    dados['disponivel'] = True
                elif 'outofstock' in disponibilidade.lower() or 'discontinued' in disponibilidade.lower():
                    dados['disponivel'] = False
                else:
                    dados['disponivel'] = None
            else:
                # Sem informação de availability no JSON-LD
                dados['disponivel'] = None
                dados['estoque'] = None

            inventario = primeira_oferta.get('inventoryLevel')
            quantidade = None
            if isinstance(inventario, dict):
                quantidade = inventario.get('value')
            elif isinstance(inventario, (str, int, float)):
                quantidade = inventario

            if quantidade is not None:
                try:
                    dados['estoque_quantidade'] = int(float(str(quantidade).replace(',', '.')))
                except ValueError:
                    dados['estoque_quantidade'] = str(quantidade)
    
    # Complementa preço original buscando no HTML (mesmo se JSON-LD existir)
    # Muitos sites (ex: VTEX) têm listPrice no HTML mas não no JSON-LD
    if not dados.get('preco_original'):
        list_price_elem = soup.find(class_=re.compile(r'listPrice|list-price|preco-de|price-from|old-price', re.IGNORECASE))
        if list_price_elem:
            list_price_text = list_price_elem.get_text(strip=True)
            match = re.search(r'R\$\s*(\d{1,3}(?:\.\d{3})*(?:,\d{2}))', list_price_text)
            if match:
                preco_original_html = match.group(1)
                # Só adiciona se for diferente do preço atual
                if dados.get('preco') and preco_original_html != str(dados.get('preco')):
                    try:
                        p_orig = float(preco_original_html.replace('.', '').replace(',', '.'))
                        p_atual = float(str(dados.get('preco')).replace('.', '').replace(',', '.'))
                        if p_orig > p_atual:
                            dados['preco_original'] = preco_original_html
                    except:
                        pass
    
    # 2. Meta tags (rápido)
    if not dados.get('nome'):
        og_title = soup.find('meta', property='og:title')
        if og_title:
            dados['nome'] = og_title.get('content', '')
        else:
            h1 = soup.find('h1')
            if h1:
                dados['nome'] = h1.get_text(strip=True)
    
    if not dados.get('preco'):
        # Busca por meta tags de preço
        price_meta = soup.find('meta', property='product:price:amount')
        if price_meta:
            dados['preco'] = price_meta.get('content', '')
        else:
            # Busca elementos específicos de preço (VTEX, Nuvemshop, etc)
            # Preço de lista (original, geralmente riscado)
            list_price = soup.find(class_=re.compile(r'listPrice|list-price|preco-de|price-from', re.IGNORECASE))
            if list_price:
                list_price_text = list_price.get_text(strip=True)
                # Extrai só o número
                match = re.search(r'R\$\s*(\d{1,3}(?:\.\d{3})*(?:,\d{2}))', list_price_text)
                if match:
                    dados['preco_original'] = match.group(1)
            
            # Preço de venda (atual/promocional)
            selling_price = soup.find(class_=re.compile(r'sellingPrice|selling-price|preco-por|price-to|bestPrice', re.IGNORECASE))
            if selling_price:
                selling_price_text = selling_price.get_text(strip=True)
                match = re.search(r'R\$\s*(\d{1,3}(?:\.\d{3})*(?:,\d{2}))', selling_price_text)
                if match:
                    dados['preco'] = match.group(1)
            
            # Se ainda não achou, busca padrões no HTML geral
            if not dados.get('preco'):
                precos_encontrados = re.findall(r'R\$\s*(\d{1,3}(?:\.\d{3})*(?:,\d{2}))', html)
                
                if len(precos_encontrados) >= 2:
                    # Se encontrou 2+ preços, assume padrão: [original, promocional]
                    # Verifica qual é maior (original deve ser maior)
                    try:
                        p1 = float(precos_encontrados[0].replace('.', '').replace(',', '.'))
                        p2 = float(precos_encontrados[1].replace('.', '').replace(',', '.'))
                        if p1 > p2:
                            dados['preco_original'] = precos_encontrados[0]
                            dados['preco'] = precos_encontrados[1]
                        else:
                            dados['preco'] = precos_encontrados[0]
                            dados['preco_original'] = precos_encontrados[1]
                    except:
                        dados['preco'] = precos_encontrados[0]
                elif len(precos_encontrados) == 1:
                    dados['preco'] = precos_encontrados[0]
            
            # Busca também texto explícito "de" e "por"
            match_promo = re.search(r'de\s+R\$\s*(\d{1,3}(?:\.\d{3})*(?:,\d{2}))\s+(?:por|para)\s+R\$\s*(\d{1,3}(?:\.\d{3})*(?:,\d{2}))', html, re.IGNORECASE)
            if match_promo:
                dados['preco_original'] = match_promo.group(1)
                dados['preco'] = match_promo.group(2)
    
    if not dados.get('marca'):
        brand_meta = soup.find('meta', property='product:brand')
        if brand_meta:
            dados['marca'] = brand_meta.get('content', '')
    
    if not dados.get('imagens'):
        og_image = soup.find('meta', property='og:image')
        if og_image:
            dados['imagens'] = [og_image.get('content', '')]
    
    # 3. Breadcrumb rápido - separa categoria, subcategoria e tags completas
    if not dados.get('categoria'):
        # Tenta múltiplas formas de encontrar breadcrumb
        breadcrumb = (
            soup.find(attrs={"class": re.compile(r"breadcrumb", re.I)}) or
            soup.find(attrs={"itemtype": "http://schema.org/BreadcrumbList"}) or
            soup.find(attrs={"typeof": "BreadcrumbList"}) or
            soup.find("nav", attrs={"aria-label": re.compile(r"breadcrumb", re.I)}) or
            soup.find("ol", attrs={"class": re.compile(r"breadcrumb", re.I)}) or
            soup.find("ul", attrs={"class": re.compile(r"breadcrumb", re.I)})
        )
        
        if breadcrumb:
            # Tenta pegar links ou spans
            items = breadcrumb.find_all(['a', 'span', 'li'])
            # Filtra palavras que não são categorias reais
            categorias = []
            for item in items:
                texto = item.get_text(strip=True)
                # Remove itens vazios e palavras comuns de navegação
                if texto and texto not in ['Início', 'Home', 'OFF', 'Shop', '', '>', '»', '/']:
                    categorias.append(texto)
            if categorias:
                # Categorias completas: todas as tags separadas por |
                dados['categorias_completas'] = ' | '.join(categorias)
                
                # Categoria: última tag (mais específica)
                dados['categoria'] = categorias[-1] if len(categorias) >= 1 else ''
                
                # Subcategoria: penúltima tag
                dados['subcategoria'] = categorias[-2] if len(categorias) >= 2 else ''
    
    # 4. Nome limpo (remove códigos)
    if dados.get('nome'):
        dados['nome_limpo'] = re.sub(r'\s*\(\s*\d+\s*\)', '', dados['nome']).strip()
    
    # Fallback SPA/Next.js (sem Selenium): tenta __NEXT_DATA__, rota _next/data e Apollo State
    # Ativa se: não tem preço OU (tem nome genérico E não tem produto real)
    nome_generico = dados.get('nome', '').lower()
    eh_site_spa = 'matcon' in nome_generico or 'materiais' in nome_generico or 'ferramentas' in nome_generico
    precisa_fallback = not dados.get('preco') or (eh_site_spa and not dados.get('marca'))
    
    if precisa_fallback:
        produto_inline, _build = _spa_nextdata_inline(html)
        produto = produto_inline or _spa_nextdata_fetch(url, html, _shared_client) or _spa_apollo_state(html)
        if produto:
            # Mescla dados, priorizando o que veio do fallback
            for k, v in produto.items():
                if v and (not dados.get(k) or k == 'nome'):  # Sobrescreve nome genérico
                    dados[k] = v
        
        # Fallback adicional: extrai do título da página se for Next.js App Router
        if not dados.get('preco') and 'self.__next_f' in html:
            # Next.js 13+ App Router - extrai do title
            title_tag = soup.find('title')
            if title_tag:
                title_text = title_tag.get_text()
                # Remove nome da loja do título
                title_limpo = re.sub(r'^.*?\|\s*', '', title_text)
                title_limpo = re.sub(r'\s*\|\s*.*?$', '', title_limpo)
                if title_limpo and len(title_limpo) > 10:
                    dados['nome'] = title_limpo.strip()
                    dados['disponivel'] = False  # Marca como indisponível já que não conseguiu extrair detalhes
                    dados['erro'] = 'Next.js App Router - dados carregados via streaming (não scrapeável)'

    dados['url'] = url
    
    return dados

def processar_produto_individual(url, index, total):
    """
    Processa um produto individual - RÁPIDO
    Tenta sem /p automaticamente se der 404 (fix para VTEX)
    """
    try:
        # Verifica cache
        if url in cache_produtos:
            return cache_produtos[url]
        
        # Request
        parsed = urlparse(url)
        referer = f"{parsed.scheme}://{parsed.netloc}/"
        
        try:
            response = _http_get(url, timeout=15, referer=referer)
            status_code = response.status_code
        except httpx.HTTPStatusError as e:
            # Se deu 404 e URL termina com /p, tenta sem o /p
            if e.response.status_code == 404 and url.endswith('/p'):
                url_sem_p = url[:-2]
                try:
                    response = _http_get(url_sem_p, timeout=15, referer=referer)
                    status_code = response.status_code
                    url = url_sem_p  # Usa a URL corrigida
                except:
                    raise e  # Se falhar novamente, propaga o erro original
            else:
                raise e
        
        # Pausa curta para evitar gatilho de rate-limit em massa
        time.sleep(random.uniform(0.05, 0.2))
        
        # Extração estruturada (rápida)
        dados = extrair_dados_estruturados(response.text, url)
        dados['status_http'] = status_code
        
        # Se for 404 ou erro similar, marca claramente
        if status_code == 404:
            dados['erro'] = 'Produto não encontrado (404)'
            dados['nome'] = dados.get('nome') or 'Produto removido/não existe'
        elif status_code >= 400:
            dados['erro'] = f'Erro HTTP {status_code}'
        
        # Se status 200 mas não extraiu dados básicos, pode ser site SPA/React
        if status_code == 200 and not dados.get('nome'):
            dados['nome'] = 'Matcon.casa | Materiais de Construção e Ferramentas Online'
            dados['erro'] = 'Site React/SPA - conteúdo carregado via JavaScript (não scrapeável com HTTP simples)'
            dados['disponivel'] = None
        
        # Salva no cache
        cache_produtos[url] = dados
        
        return dados
        
    except httpx.HTTPStatusError as e:
        # Erro HTTP específico (404, 403, etc)
        status = e.response.status_code if hasattr(e, 'response') else 'desconhecido'
        return {
            'url': url,
            'status_http': status,
            'erro': f'HTTP {status}: {str(e)}',
            'nome': 'Produto não acessível' if status == 404 else 'Erro ao acessar',
            'preco': None
        }
    except Exception as e:
        # Outros erros (timeout, connection, etc)
        return {
            'url': url,
            'status_http': 'erro',
            'erro': str(e),
            'nome': 'Erro ao processar',
            'preco': None
        }

def extrair_detalhes_paralelo(produtos_input, show_message, max_produtos=10, max_workers=5):
    """
    Extração de detalhes com PROCESSAMENTO PARALELO
    produtos_input: pode ser lista de dicts ou string com URLs
    max_workers: número de threads simultâneas (padrão 5)
    """
    show_message(f"Iniciando extracao PARALELA com {max_workers} threads...")
    
    # Parse URLs - aceita lista ou string
    urls_produtos = []
    
    if isinstance(produtos_input, list):
        # Lista de dicionários (formato V4)
        for item in produtos_input:
            if isinstance(item, dict) and 'url' in item:
                urls_produtos.append(item['url'])
            elif isinstance(item, str):
                urls_produtos.append(item)
    else:
        # String com URLs (formato antigo)
        linhas = produtos_input.strip().split('\n')
        for linha in linhas:
            linha = linha.strip()
            if linha.startswith('http'):
                # Remove numeração se houver (ex: "1. http://...")
                url = re.sub(r'^\d+\.\s*', '', linha)
                urls_produtos.append(url)
    
    # Limita quantidade
    if len(urls_produtos) > max_produtos:
        urls_produtos = urls_produtos[:max_produtos]
        show_message(f"Limitando a {max_produtos} produtos para analise")
    
    show_message(f"Processando {len(urls_produtos)} produtos em paralelo...")
    
    # Processamento paralelo
    resultados = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submete todas as tarefas
        futures = {
            executor.submit(processar_produto_individual, url, i+1, len(urls_produtos)): (url, i+1) 
            for i, url in enumerate(urls_produtos)
        }
        
        # Coleta resultados conforme ficam prontos
        for future in as_completed(futures):
            url, index = futures[future]
            try:
                resultado = future.result()
                resultados.append((index, resultado))
                
                with message_lock:
                    show_message(f"Concluido {index}/{len(urls_produtos)}: {resultado.get('nome', 'N/A')[:50]}...")
            except Exception as e:
                with message_lock:
                    show_message(f"Erro no produto {index}: {e}")
    
    # Ordena resultados pela ordem original
    resultados.sort(key=lambda x: x[0])
    dados_ordenados = []
    
    # Formata saída
    output = []
    output.append("=== DETALHES DOS PRODUTOS (V4 - PARALELO) ===")
    output.append(f"Produtos processados: {len(resultados)}")
    output.append(f"Threads utilizadas: {max_workers}")
    output.append("")
    
    for index, dados in resultados:
        dados_copia = dict(dados)
        dados_copia.setdefault('indice', index)
        dados_ordenados.append(dados_copia)
        output.append(f"--- PRODUTO {index} ---")
        output.append(f"URL: {dados.get('url', 'N/A')}")
        output.append(f"Nome: {dados.get('nome', 'N/A')}")
        output.append(f"Nome Limpo: {dados.get('nome_limpo', 'N/A')}")
        output.append(f"Preco: {dados.get('preco', 'N/A')} {dados.get('moeda', '')}")
        output.append(f"Marca: {dados.get('marca', 'N/A')}")
        output.append(f"Categoria: {dados.get('categoria', 'N/A')}")
        output.append(f"Estoque: {dados.get('estoque', 'N/A')}")
        
        if dados.get('imagens'):
            output.append(f"Imagens ({len(dados['imagens'])}):")
            for img in dados['imagens'][:3]:
                output.append(f"  - {img}")
        
        if dados.get('descricao'):
            desc = dados['descricao'][:200]
            output.append(f"Descricao: {desc}...")
        
        if dados.get('erro'):
            output.append(f"ERRO: {dados['erro']}")
        
        output.append("")
    
    resultado_final = "\n".join(output)
    
    # Salva resultado
    with open("detalhes_extraidos.txt", "w", encoding="utf-8") as f:
        f.write(resultado_final)
    
    show_message(f"Extracao paralela concluida! {len(resultados)} produtos processados")
    return resultado_final, dados_ordenados
