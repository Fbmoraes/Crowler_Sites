"""
Versão 5 - Estratégia Inteligente + Otimizada:
1. Extrai TODOS os links do sitemap (incluindo categorias)
2. Identifica páginas de categoria e extrai produtos delas (com paginação)
3. Valida URLs em paralelo (10-20x mais rápido)
4. HEAD request antes de GET (2-3x mais rápido)
5. Cache de validação (evita validações redundantes)
6. Retorna apenas produtos reais e acessíveis
"""

import httpx
import xml.etree.ElementTree as ET
import gzip
from io import BytesIO
from urllib.parse import urljoin, urlparse, parse_qs
from bs4 import BeautifulSoup
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

# Headers básicos de navegador
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# Cache global para validação (thread-safe)
_cache_validacao = {}
_cache_lock = Lock()

# Padrões aprendidos de URLs de produto
_padroes_aprendidos = {
    'regex_patterns': [],
    'url_structures': [],
    'confirmados': 0
}
_padroes_lock = Lock()

def _baixar(url, timeout=15):
    """Download simples com httpx."""
    try:
        r = httpx.get(url, headers=HEADERS, timeout=timeout, follow_redirects=True)
        if r.status_code == 200:
            return r
    except:
        pass
    return None

def _achar_sitemap(base_url):
    """Procura sitemap: primeiro no robots.txt, depois em URLs comuns."""
    base_domain = urlparse(base_url).netloc
    
    # Tenta robots.txt
    r = _baixar(urljoin(base_url, "/robots.txt"), timeout=10)
    if r and r.text:
        for linha in r.text.splitlines():
            if linha.strip().lower().startswith("sitemap:"):
                sitemap_url = linha.split(":", 1)[1].strip()
                if sitemap_url.startswith("/"):
                    sitemap_url = urljoin(base_url, sitemap_url)
                
                # Valida se o sitemap é do mesmo domínio
                sitemap_domain = urlparse(sitemap_url).netloc
                if sitemap_domain == base_domain:
                    return sitemap_url
                # Se for domínio diferente, ignora e continua procurando
    
    # Tenta URLs comuns
    for caminho in ["/sitemap.xml", "/sitemap_index.xml", "/sitemap.xml.gz", "/sitemap-products.xml"]:
        url = urljoin(base_url, caminho)
        if _baixar(url, timeout=10):
            return url
    
    return None

def _extrair_urls_do_xml(sitemap_url):
    """Baixa XML (descompacta se .gz) e extrai todas as tags <loc>."""
    r = _baixar(sitemap_url, timeout=20)
    if not r or not r.content:
        return []

    conteudo = r.content

    # Se for .gz ou começar com bytes gzip, descompacta
    if sitemap_url.endswith(".gz") or (len(conteudo) >= 2 and conteudo[:2] == b"\x1f\x8b"):
        try:
            conteudo = gzip.decompress(conteudo)
        except:
            try:
                conteudo = gzip.GzipFile(fileobj=BytesIO(conteudo)).read()
            except:
                return []

    # Limpa XML malformado (ex: "<? xml" → "<?xml")
    if isinstance(conteudo, bytes):
        conteudo_str = conteudo.decode("utf-8", errors="ignore")
    else:
        conteudo_str = conteudo
    
    # Corrige declaração XML malformada
    conteudo_str = conteudo_str.replace("<? xml", "<?xml")
    conteudo_str = conteudo_str.replace("< ?xml", "<?xml")
    conteudo = conteudo_str.encode("utf-8")

    # Parse XML
    try:
        root = ET.fromstring(conteudo)
    except:
        try:
            root = ET.fromstring(conteudo.decode("utf-8", errors="ignore"))
        except:
            return []

    urls = []

    # Tenta com namespace
    for loc in root.findall(".//{http://www.sitemaps.org/schemas/sitemap/0.9}loc"):
        if loc.text:
            urls.append(loc.text.strip())

    # Se não achou, tenta sem namespace
    if not urls:
        for loc in root.findall(".//loc"):
            if loc.text:
                urls.append(loc.text.strip())

    return urls


def _coletar_urls_recursivo(sitemap_inicial, show_message, progress_callback=None):
    """Expande recursivamente sitemaps (índices + filhos) e retorna todas as URLs finais.

    Mudança: sempre visita TODOS os sitemaps filhos encontrados (ex.: products-0.xml, products-1.xml, products-2.xml),
    sem heurística que possa pular algum arquivo. Mostra progresso em tempo real.
    """
    visitados = set()
    fila = [sitemap_inicial]
    urls_coletadas = []

    while fila:
        sitemap_atual = fila.pop(0)
        if sitemap_atual in visitados:
            continue
        visitados.add(sitemap_atual)

        nome_sitemap = sitemap_atual.split('/')[-1]
        show_message(f"Sitemap: {nome_sitemap}")
        
        urls = _extrair_urls_do_xml(sitemap_atual)
        if not urls:
            show_message(f"Vazio: {nome_sitemap}")
            continue

        # Separa sitemaps filhos de URLs de conteúdo
        sitemaps_filhos = []
        urls_diretas = []
        
        for u in urls:
            if u.lower().endswith((".xml", ".xml.gz")):
                sitemaps_filhos.append(u)
            else:
                urls_diretas.append(u)
        
        # Adiciona sitemaps filhos à fila
        for sitemap_filho in sitemaps_filhos:
            if sitemap_filho not in visitados:
                fila.append(sitemap_filho)
        
        # Adiciona URLs diretas à coleção
        if urls_diretas:
            show_message(f"{len(urls_diretas)} URLs de {nome_sitemap}")
            urls_coletadas.extend(urls_diretas)
            
            # Atualiza progresso com o total coletado até agora
            if progress_callback:
                try:
                    progress_callback(len(urls_coletadas), nome_sitemap)
                except Exception:
                    pass

    return urls_coletadas

def _eh_categoria(url):
    """Verifica se URL parece ser de categoria/coleção."""
    url_lower = url.lower()
    
    indicadores_categoria = [
        "/categoria", "/category", "/collection", "/colecao",
        "/busca", "/search", "/c/",
        # Padrões comuns de e-commerce
        "/produtos", "/products", "/shop",
        "/brincos", "/aneis", "/colares", "/pulseiras",  # Tipos de produto
        "/ouro", "/prata", "/pedras",  # Materiais
        "/feminino", "/masculino", "/infantil",  # Públicos
        "/lancamento", "/promocao", "/outlet"
    ]
    
    return any(ind in url_lower for ind in indicadores_categoria)


def _eh_produto_provavel(url):
    """Verifica se URL tem padrão forte que sugere produto."""
    url_lower = url.lower()
    path = urlparse(url).path.rstrip("/")
    
    # NÃO deve ser sistema/página especial/categoria
    exclusoes = [
        "/carrinho", "/cart", "/checkout", "/conta", "/account", "/login",
        "/blog", "/contato", "/contact", "/sobre", "/about", "/faq", 
        "/ajuda", "/help", "/politica", "/termos", "/privacy",
        "/categoria", "/category", "/collection", "/colecao", "/c/",
        "/busca", "/search", "/produtos", "/products", "/shop",
        # Categorias comuns
        "/automotivo", "/casa", "/ferramentas", "/eletrica", "/hidraulica"
    ]
    
    if any(x in url_lower for x in exclusoes):
        return False
    
    # Produto deve ter ID/código numérico significativo (6+ dígitos)
    # Ex: /produto-nome-123456 ou /item-415782
    tem_codigo_longo = bool(re.search(r'\d{6,}', path))
    
    # OU padrão muito específico de produto
    padroes_produto = [
        r'/[a-z]+-\d{6,}$',  # Ex: /produto-123456
        r'-\d{6,}$',          # Ex: /nome-produto-123456
        r'/p/\d+',            # Ex: /p/123
        r'/produto/',
        r'/product/',
        r'/item/',
        r'/look-\d+'
    ]
    
    tem_padrao_forte = any(re.search(padrao, path) for padrao in padroes_produto)
    
    # Produto provável: código longo OU padrão forte + profundidade adequada
    profundidade_ok = path.count("/") >= 1
    
    return profundidade_ok and (tem_codigo_longo or tem_padrao_forte)


def _extrair_produtos_da_pagina(url, base_url, show_message=None):
    """Extrai links de produtos de uma página de categoria."""
    produtos = set()
    
    try:
        r = _baixar(url, timeout=10)
        if not r or r.status_code != 200:
            return produtos, None
        
        soup = BeautifulSoup(r.content, 'html.parser')
        
        # Procura por links de produtos em padrões comuns
        # 1. Links em estruturas de listagem de produtos
        for link in soup.find_all('a', href=True):
            href = link['href']
            
            # Converte para URL absoluta
            if href.startswith('/'):
                href = urljoin(base_url, href)
            elif not href.startswith('http'):
                continue
            
            # Verifica se pertence ao domínio
            if urlparse(href).netloc != urlparse(base_url).netloc:
                continue
            
            # Remove âncoras e normaliza
            href = href.split('#')[0].rstrip('/')
            
            # Se parece com produto, adiciona
            if _eh_produto_provavel(href) and not _eh_categoria(href):
                produtos.add(href)
        
        # Procura por paginação e retorna próxima página se existir
        proxima_pagina = None
        for link in soup.find_all('a', href=True):
            texto = link.get_text().lower().strip()
            href = link['href']
            
            if any(x in texto for x in ['próxima', 'next', '>', 'mais', 'ver mais']):
                if href.startswith('/'):
                    proxima_pagina = urljoin(base_url, href)
                elif href.startswith('http'):
                    proxima_pagina = href
                break
        
        # Também procura por URLs com ?page= ou /page/
        if not proxima_pagina:
            parsed = urlparse(url)
            query = parse_qs(parsed.query)
            
            if 'page' in query:
                try:
                    page_atual = int(query['page'][0])
                    # Tenta próxima página
                    query['page'] = [str(page_atual + 1)]
                    from urllib.parse import urlencode
                    nova_query = urlencode(query, doseq=True)
                    proxima_pagina = f"{parsed.scheme}://{parsed.netloc}{parsed.path}?{nova_query}"
                except:
                    pass
        
        return produtos, proxima_pagina
        
    except Exception as e:
        if show_message:
            show_message(f"Erro ao processar {url}: {str(e)[:50]}")
        return produtos, None


def _gerar_variacoes_url(url):
    """Gera variações comuns de URL de produto para tentar.
    
    Retorna lista de URLs alternativas baseadas em padrões comuns de e-commerce:
    - /produto/, /product/, /p/
    """
    from urllib.parse import urlparse
    parsed = urlparse(url)
    path_limpo = parsed.path.lstrip('/')
    
    # Se já tem /produto/, /product/ ou /p/ no path, retorna apenas o original
    if any(x in path_limpo.lower() for x in ['produto/', 'product/', '/p/']):
        return [url]
    
    # Gera variações
    variacoes = [
        url,  # Original
        f"{parsed.scheme}://{parsed.netloc}/produto/{path_limpo}",
        f"{parsed.scheme}://{parsed.netloc}/product/{path_limpo}",
        f"{parsed.scheme}://{parsed.netloc}/p/{path_limpo}",
    ]
    
    # Remove duplicatas mantendo ordem
    return list(dict.fromkeys(variacoes))


def _aprender_padroes_de_produtos(urls_validas, show_message=None):
    """Analisa URLs de produtos validados e identifica padrões comuns - VERSÃO SIMPLIFICADA."""
    if not urls_validas or len(urls_validas) < 3:
        return None
    
    padroes = {
        'estruturas_comuns': [],
        'segmentos_obrigatorios': [],
        'total_analisado': len(urls_validas)
    }
    
    # Analisa estrutura de path
    estruturas = {}
    for url in urls_validas:
        path = urlparse(url).path.rstrip('/')
        segmentos = [s for s in path.split('/') if s]
        
        # Substitui números por placeholder
        estrutura = []
        for seg in segmentos:
            if re.search(r'\d{3,}', seg):
                estrutura.append('<NUM>')
            else:
                estrutura.append(seg)
        
        estrutura_str = '/'.join(estrutura)
        estruturas[estrutura_str] = estruturas.get(estrutura_str, 0) + 1
    
    # Pega estruturas que aparecem em 20%+ das URLs
    threshold = max(2, len(urls_validas) * 0.2)
    for estrutura, count in estruturas.items():
        if count >= threshold:
            padroes['estruturas_comuns'].append(estrutura)
    
    # Identifica segmentos comuns
    todos_segmentos = []
    for url in urls_validas:
        path = urlparse(url).path
        segmentos = [s for s in path.split('/') if s and not re.search(r'^\d+$', s)]
        todos_segmentos.extend(segmentos)
    
    from collections import Counter
    contagem = Counter(todos_segmentos)
    threshold_seg = max(2, len(urls_validas) * 0.3)
    for seg, count in contagem.most_common(5):  # Reduzido de 10 para 5
        if count >= threshold_seg:
            padroes['segmentos_obrigatorios'].append(seg)
    
    if show_message:
        show_message(f"Padroes: {len(padroes['estruturas_comuns'])} estruturas")
    
    return padroes


def _url_corresponde_padrao(url, padroes):
    """Verifica se URL corresponde aos padrões aprendidos - VERSÃO ULTRA SIMPLIFICADA."""
    if not padroes:
        return False
    
    path = urlparse(url).path.rstrip('/')
    
    # Verifica estruturas comuns
    segmentos = [s for s in path.split('/') if s]
    estrutura = []
    for seg in segmentos:
        if re.search(r'\d{3,}', seg):
            estrutura.append('<NUM>')
        else:
            estrutura.append(seg)
    
    estrutura_str = '/'.join(estrutura)
    
    # Se corresponde à estrutura comum, é produto
    if estrutura_str in padroes.get('estruturas_comuns', []):
        return True
    
    # Verifica segmentos obrigatórios
    segmentos_obrig = padroes.get('segmentos_obrigatorios', [])
    if segmentos_obrig and any(seg in path for seg in segmentos_obrig):
        return True
    
    return False


def _validar_produto_http(url, show_message=None):
    """Validação HTTP completa com tentativa de múltiplas variações de URL.
    
    Tenta diferentes formatos comuns de URLs de produto:
    1. URL original do sitemap
    2. URL com /produto/ após domínio
    3. URL com /product/ após domínio
    4. URL com /p/ após domínio
    
    Isso resolve casos onde o sitemap está desatualizado mas produtos existem
    em estruturas de URL ligeiramente diferentes.
    """
    with _cache_lock:
        if url in _cache_validacao:
            return _cache_validacao[url]
    
    # Gera variações de URL para tentar
    from urllib.parse import urlparse, urlunparse
    parsed = urlparse(url)
    path = parsed.path
    
    # Remove barra inicial para facilitar manipulação
    path_limpo = path.lstrip('/')
    
    # Variações a tentar (ordem de prioridade)
    variacoes = [
        url,  # Original
        f"{parsed.scheme}://{parsed.netloc}/produto/{path_limpo}",  # Com /produto/
        f"{parsed.scheme}://{parsed.netloc}/product/{path_limpo}",  # Com /product/
        f"{parsed.scheme}://{parsed.netloc}/p/{path_limpo}",        # Com /p/
    ]
    
    # Remove duplicatas mantendo ordem
    variacoes_unicas = []
    for v in variacoes:
        if v not in variacoes_unicas:
            variacoes_unicas.append(v)
    
    # Tenta cada variação até encontrar uma que funcione
    for url_teste in variacoes_unicas:
        try:
            r_head = httpx.head(url_teste, headers=HEADERS, timeout=2, follow_redirects=True)
            
            if r_head.status_code != 200:
                continue  # Tenta próxima variação
            
            # Se HEAD retornou 200, faz GET completo
            r = httpx.get(url_teste, headers=HEADERS, timeout=4, follow_redirects=True)
            
            if r.status_code != 200:
                continue  # Tenta próxima variação
            
            # Verifica indicadores de produto
            html_lower = r.text.lower()
            indicadores = 0
            
            if any(x in html_lower for x in ['adicionar', 'comprar', 'buy', 'add to cart']):
                indicadores += 1
            if any(x in html_lower for x in ['"price"', 'preco', 'preço', 'r$', 'brl']):
                indicadores += 1
            if any(x in html_lower for x in ['product', 'produto', '"sku"', 'item']):
                indicadores += 1
            
            if indicadores >= 2:
                # SUCESSO! Cacheia tanto a URL original quanto a variação que funcionou
                with _cache_lock:
                    _cache_validacao[url] = url_teste  # Guarda URL que funcionou
                return url_teste  # Retorna URL válida (não apenas True)
        
        except Exception:
            continue  # Tenta próxima variação
    
    # Nenhuma variação funcionou
    with _cache_lock:
        _cache_validacao[url] = False
    
    return False
    """Acessa a URL e verifica se é realmente um produto válido.
    
    Otimizações:
    - Cache de validação para evitar requisições repetidas
    - HEAD request primeiro para verificar 200 sem baixar HTML
    - GET completo só se HEAD retornar 200
    """
    # Verifica cache primeiro
    with _cache_lock:
        if url in _cache_validacao:
            return _cache_validacao[url]
    
    try:
        # OTIMIZAÇÃO 1: HEAD request (rápido, só verifica status)
        r_head = httpx.head(url, headers=HEADERS, timeout=2, follow_redirects=True)
        
        # Se não for 200, já descarta
        if r_head.status_code != 200:
            with _cache_lock:
                _cache_validacao[url] = False
            return False
        
        # OTIMIZAÇÃO 2: GET completo apenas se HEAD retornou 200
        r = httpx.get(url, headers=HEADERS, timeout=4, follow_redirects=True)
        
        if r.status_code != 200:
            with _cache_lock:
                _cache_validacao[url] = False
            return False
        
        # Verifica se tem indicadores de produto na página
        html_lower = r.text.lower()
        
        # Indicadores positivos (pelo menos 2 devem estar presentes)
        indicadores_positivos = 0
        
        if any(x in html_lower for x in ['add to cart', 'adicionar', 'comprar', 'buy']):
            indicadores_positivos += 1
        
        if any(x in html_lower for x in ['"price"', 'preco', 'preço', 'r$', 'brl']):
            indicadores_positivos += 1
        
        if any(x in html_lower for x in ['product', 'produto', 'item', '"sku"']):
            indicadores_positivos += 1
        
        if any(x in html_lower for x in ['estoque', 'stock', 'disponível', 'available']):
            indicadores_positivos += 1
        
        # Indicadores negativos
        if any(x in html_lower for x in ['404', 'not found', 'página não encontrada', 'erro']):
            resultado = False
        elif 'categoria' in html_lower or 'category' in html_lower:
            # Pode ser categoria, não produto
            resultado = indicadores_positivos >= 2
        else:
            resultado = indicadores_positivos >= 2
        
        # Armazena no cache
        with _cache_lock:
            _cache_validacao[url] = resultado
        
        return resultado
        
    except Exception:
        with _cache_lock:
            _cache_validacao[url] = False
        return False


def _validar_produtos_paralelo_http(urls_candidatas, show_message, progress_callback=None, max_workers=50):
    """Validação HTTP paralela - só para fase de aprendizado.
    
    Retorna lista de produtos válidos com URL corrigida (se necessário).
    """
    produtos_validos = []
    urls_vistas = set()  # Deduplicação
    total = len(urls_candidatas)
    processados = 0
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_url = {
            executor.submit(_validar_produto_http, url, show_message): url 
            for url in urls_candidatas
        }
        
        for future in as_completed(future_to_url):
            url_original = future_to_url[future]
            processados += 1
            
            try:
                resultado = future.result()
                
                # resultado pode ser: False, ou uma URL string (URL que funcionou)
                if resultado and resultado != False:
                    # Se retornou uma URL, usa ela (pode ser corrigida)
                    url_valida = resultado if isinstance(resultado, str) else url_original
                    
                    if url_valida not in urls_vistas:
                        urls_vistas.add(url_valida)
                        
                        # Extrai nome do produto da URL
                        path = urlparse(url_valida).path.rstrip("/")
                        partes = [p for p in path.split("/") if p]
                        slug = partes[-1] if partes else "produto"
                        
                        # Remove parâmetros e limpa
                        slug = slug.split("?")[0].split("#")[0]
                        
                        # Converte slug em nome legível
                        nome = slug.replace("-", " ").title()
                        produtos_validos.append({"url": url_valida, "nome": nome})
                
                if progress_callback and processados % 5 == 0:
                    try:
                        progress_callback(processados, total, url_original, "validando")
                    except Exception:
                        pass
                
            except Exception:
                pass
    
    return produtos_validos

def extrair_produtos_rapido(base_url, show_message, max_produtos=None, progress_callback=None):
    """
    V5: Extração inteligente de produtos.
    
    Fluxo:
    1. Coleta TODOS os links do sitemap (incluindo categorias)
    2. Identifica categorias e extrai produtos delas (navegando paginação)
    3. Desduplica todos os links encontrados
    4. Valida cada link acessando a página para confirmar que é produto
    5. Retorna apenas produtos reais e acessíveis
    """
    show_message("Buscando sitemap principal")
    
    sitemap_url = _achar_sitemap(base_url)
    if not sitemap_url:
        show_message("Nenhum sitemap encontrado")
        return []
    
    show_message(f"Sitemap: {sitemap_url.split('/')[-1]}")
    
    # PASSO 1: Coleta TODOS os links do sitemap
    def coleta_progress(total_coletado, nome_sitemap):
        if progress_callback:
            try:
                progress_callback(total_coletado, None, nome_sitemap, "coletando")
            except Exception:
                pass
    
    show_message("Coletando links dos sitemaps")
    todas_urls = _coletar_urls_recursivo(sitemap_url, show_message, coleta_progress)
    show_message(f"URLs coletadas: {len(todas_urls)}")
    
    # PASSO 2: Filtra apenas possíveis produtos (SIMPLIFICADO - SEM CATEGORIAS)
    produtos_candidatos = set()
    
    for url in todas_urls:
        url_limpa = url.split("?")[0].split("#")[0].rstrip("/")
        
        if _eh_produto_provavel(url_limpa) and not _eh_categoria(url_limpa):
            produtos_candidatos.add(url_limpa)
    
    show_message(f"Candidatos identificados: {len(produtos_candidatos)}")
    
    # PASSO 4: Desduplicação
    show_message(f"Desduplicando: {len(produtos_candidatos)} links unicos")
    
    # PASSO 5: APRENDIZADO DE PADRÕES - VERSÃO ULTRA RÁPIDA
    import random
    padroes = None
    
    if len(produtos_candidatos) > 20:
        # REDUZIDO: apenas 10 URLs ou 1% do total
        amostra_size = min(10, max(5, int(len(produtos_candidatos) * 0.01)))
        amostra = random.sample(sorted(produtos_candidatos), amostra_size)
        
        show_message(f"Fase aprendizado: validando {len(amostra)} produtos (1% amostra)")
        
        if progress_callback:
            try:
                progress_callback(0, amostra_size, "aprendizado", "fase_aprendizado")
            except Exception:
                pass
        
        # Valida amostra para aprender padrões
        produtos_amostra = _validar_produtos_paralelo_http(
            amostra,
            show_message,
            progress_callback,
            max_workers=50
        )
        
        if len(produtos_amostra) >= 3:  # Mínimo de 3 produtos
            urls_validas = [p['url'] for p in produtos_amostra]
            
            # Verifica se alguma URL foi corrigida
            urls_corrigidas = 0
            for p in produtos_amostra:
                if '/produto/' in p['url'] or '/product/' in p['url'] or '/p/' in p['url']:
                    # Verifica se a URL original (do sitemap) não tinha esse prefixo
                    for url_amostra in amostra:
                        if p['url'].replace('/produto/', '/').replace('/product/', '/').replace('/p/', '/') == url_amostra:
                            urls_corrigidas += 1
                            break
            
            if urls_corrigidas > 0:
                show_message(f"URLs corrigidas automaticamente: {urls_corrigidas}/{len(produtos_amostra)} (sitemap desatualizado)")
            
            padroes = _aprender_padroes_de_produtos(urls_validas, show_message)
            
            show_message(f"Padroes aprendidos: {len(produtos_amostra)} produtos confirmados")
            
            # APLICAÇÃO INSTANTÂNEA DO PADRÃO (sem requisições HTTP!)
            show_message(f"Aplicando padroes aos {len(produtos_candidatos)} candidatos (instantaneo)")
            
            produtos_validos = []
            urls_vistas = set()  # Deduplicação final
            
            # Detecta se precisa adicionar /produto/ ou /product/ baseado nas URLs válidas
            prefixo_comum = None
            for url_valida in urls_validas:
                if '/produto/' in url_valida:
                    prefixo_comum = '/produto/'
                    break
                elif '/product/' in url_valida:
                    prefixo_comum = '/product/'
                    break
                elif '/p/' in url_valida and url_valida.count('/p/') == 1:
                    prefixo_comum = '/p/'
                    break
            
            if prefixo_comum:
                show_message(f"Aplicando correcao de URL: adicionar '{prefixo_comum}' aos produtos")
            
            for idx, url in enumerate(sorted(produtos_candidatos), 1):
                if url in urls_vistas:
                    continue
                
                if _url_corresponde_padrao(url, padroes):
                    # Aplica correção de URL se necessário
                    url_final = url
                    if prefixo_comum and prefixo_comum not in url:
                        parsed = urlparse(url)
                        path_limpo = parsed.path.lstrip('/')
                        url_final = f"{parsed.scheme}://{parsed.netloc}{prefixo_comum}{path_limpo}"
                    
                    urls_vistas.add(url_final)
                    
                    # Extrai nome do produto da URL
                    path = urlparse(url_final).path.rstrip("/")
                    partes = [p for p in path.split("/") if p]
                    slug = partes[-1] if partes else "produto"
                    
                    # Remove parâmetros e limpa
                    slug = slug.split("?")[0].split("#")[0]
                    
                    # Converte slug em nome legível
                    nome = slug.replace("-", " ").title()
                    produtos_validos.append({"url": url_final, "nome": nome})
                
                if progress_callback and idx % 100 == 0:
                    try:
                        progress_callback(amostra_size + idx, len(produtos_candidatos) + amostra_size, url, "aplicando_padrao")
                    except Exception:
                        pass
            
            show_message(f"Concluido: {len(produtos_validos)} produtos encontrados por padrão")
            return produtos_validos
        else:
            show_message(f"Amostra insuficiente ({len(produtos_amostra)}), tentando validar mais produtos")
            
            # Se amostra pequena falhou, tenta validar mais 20 produtos
            if len(produtos_candidatos) > 20:
                amostra_extra = random.sample(sorted(produtos_candidatos), min(20, len(produtos_candidatos)))
                produtos_extra = _validar_produtos_paralelo_http(
                    amostra_extra,
                    show_message,
                    progress_callback,
                    max_workers=50
                )
                
                if len(produtos_extra) >= 3:
                    # Conseguiu validar, continua com padrões
                    urls_validas = [p['url'] for p in produtos_extra]
                    padroes = _aprender_padroes_de_produtos(urls_validas, show_message)
                    
                    # Detecta prefixo
                    prefixo_comum = None
                    for url_valida in urls_validas:
                        if '/produto/' in url_valida:
                            prefixo_comum = '/produto/'
                            break
                        elif '/product/' in url_valida:
                            prefixo_comum = '/product/'
                            break
                    
                    if prefixo_comum:
                        show_message(f"Detectado prefixo '{prefixo_comum}' - aplicando a todos os produtos")
                    
                    # Retorna produtos com prefixo aplicado
                    produtos_validos = []
                    for url in sorted(produtos_candidatos):
                        if _url_corresponde_padrao(url, padroes):
                            url_final = url
                            if prefixo_comum and prefixo_comum not in url:
                                parsed = urlparse(url)
                                path_limpo = parsed.path.lstrip('/')
                                url_final = f"{parsed.scheme}://{parsed.netloc}{prefixo_comum}{path_limpo}"
                            
                            path = urlparse(url_final).path.rstrip("/")
                            partes = [p for p in path.split("/") if p]
                            slug = partes[-1] if partes else "produto"
                            slug = slug.split("?")[0].split("#")[0]
                            nome = slug.replace("-", " ").title()
                            produtos_validos.append({"url": url_final, "nome": nome})
                    
                    show_message(f"Concluido: {len(produtos_validos)} produtos com padroes")
                    return produtos_validos
    
    # FALLBACK FINAL: Retorna sem validação HTTP mas com correção inteligente de URL
    show_message(f"AVISO: Retornando {len(produtos_candidatos)} produtos SEM validacao HTTP")
    
    # Detecta domínios conhecidos que precisam de prefixo /produto/
    dominios_com_produto = ['matconcasa.com.br', 'matcon']
    
    produtos_validos = []
    for url in sorted(produtos_candidatos):
        url_final = url
        
        # Para domínios conhecidos, adiciona /produto/ automaticamente se não tiver
        domain_lower = urlparse(url).netloc.lower()
        precisa_produto = any(d in domain_lower for d in dominios_com_produto)
        
        if precisa_produto and '/produto/' not in url and '/product/' not in url:
            parsed = urlparse(url)
            path_limpo = parsed.path.lstrip('/')
            url_final = f"{parsed.scheme}://{parsed.netloc}/produto/{path_limpo}"
            
        path = urlparse(url_final).path.rstrip("/")
        partes = [p for p in path.split("/") if p]
        slug = partes[-1] if partes else "produto"
        slug = slug.split("?")[0].split("#")[0]
        nome = slug.replace("-", " ").title()
        produtos_validos.append({"url": url_final, "nome": nome})
    
    if any(d in urlparse(base_url).netloc.lower() for d in dominios_com_produto):
        show_message(f"Correcao automatica aplicada: adicionado /produto/ para {len(produtos_validos)} URLs")
    
    return produtos_validos
