import asyncio
import httpx
from bs4 import BeautifulSoup
import json
from typing import Dict, Optional, List, Tuple
import re
from urllib.parse import urljoin
import time

async def detectar_tipo_site(url: str, client: httpx.AsyncClient) -> Tuple[str, int]:
    """
    Detecta se o site é estático (HTML pronto) ou dinâmico (hidratação JS)
    
    Returns:
        Tuple (tipo, workers_recomendados)
        - tipo: 'estatico' ou 'dinamico'
        - workers_recomendados: número de workers ideal
    """
    try:
        response = await client.get(url, timeout=10.0, follow_redirects=True)
        html = response.text
        soup = BeautifulSoup(html, 'lxml')
        
        # Indicadores de site dinâmico (hidratação JS)
        indicadores_dinamicos = 0
        
        # 1. Procura por frameworks JS que fazem hidratação
        scripts = soup.find_all('script')
        for script in scripts[:20]:  # Checa primeiros 20 scripts
            script_content = script.get('src', '') + str(script.string or '')
            if any(fw in script_content.lower() for fw in ['react', 'vue', 'angular', 'next', '__next', 'nuxt', 'gatsby']):
                indicadores_dinamicos += 2
            if 'hydrat' in script_content.lower():
                indicadores_dinamicos += 3
        
        # 2. Procura por root divs típicos de SPAs
        if soup.find('div', id=re.compile(r'root|app|__next', re.I)):
            indicadores_dinamicos += 2
        
        # 3. Checa se preço está no HTML inicial
        tem_preco_html = bool(
            soup.find(string=re.compile(r'R\$\s*[\d.,]+', re.I)) or
            soup.find(attrs={'itemprop': 'price'}) or
            soup.find('script', {'type': 'application/ld+json'})
        )
        
        if not tem_preco_html:
            indicadores_dinamicos += 3
        
        # 4. Checa tempo de resposta (sites dinâmicos costumam ser mais lentos)
        tempo_resposta = response.elapsed.total_seconds()
        if tempo_resposta > 1.5:
            indicadores_dinamicos += 1
        
        # Decisão
        if indicadores_dinamicos >= 4:
            return 'dinamico', 3  # Sites com hidratação: poucos workers
        else:
            return 'estatico', 25  # Sites estáticos: muitos workers
            
    except Exception as e:
        # Em caso de erro, assume estático (mais rápido)
        return 'estatico', 25

async def extrair_produto_turbo(produto: Dict, indice: int, client: httpx.AsyncClient, semaphore: asyncio.Semaphore, total: int, progress_callback=None, delay: float = 0) -> Optional[Dict]:
    """
    Extrai detalhes de um produto de forma rápida com retry em 429
    
    Args:
        produto: Dict com 'url' e 'nome'
        indice: Índice do produto (para log)
        client: Cliente HTTP assíncrono
        semaphore: Semáforo para controle de concorrência
        total: Total de produtos
        progress_callback: Função de callback para progresso
    
    Returns:
        Dict com detalhes do produto ou None se falhar
    """
    url = produto['url']
    
    async with semaphore:
        # Aplica delay se necessário (sites dinâmicos)
        if delay > 0:
            await asyncio.sleep(delay)
        
        for tentativa in range(3):
            try:
                response = await client.get(
                    url,
                    timeout=15.0,
                    follow_redirects=True
                )
                
                # Se recebeu 429, faz retry com backoff exponencial
                if response.status_code == 429:
                    if tentativa < 2:
                        await asyncio.sleep(2 ** tentativa)  # 1s, 2s
                        continue
                    else:
                        msg = f"❌ [{indice}/{total}] 429 após 3 tentativas: {url}"
                        if progress_callback:
                            progress_callback(msg)
                        else:
                            print(msg)
                        return None
                
                # Se não é 200, tenta novamente
                if response.status_code != 200:
                    if tentativa < 2:
                        await asyncio.sleep(0.5)
                        continue
                    else:
                        msg = f"❌ [{indice}/{total}] Status {response.status_code}: {url}"
                        if progress_callback:
                            progress_callback(msg)
                        else:
                            print(msg)
                        return None
                
                # Sucesso! Processa a resposta
                html = response.text
                soup = BeautifulSoup(html, 'lxml')
                
                # Tenta extrair dados com cascata: JSON-LD → OpenGraph → HTML
                detalhes = await extrair_dados_produto(soup, url, produto['nome'])
                
                if detalhes:
                    msg = f"✅ [{indice}/{total}] {detalhes.get('nome', 'Produto')[:50]}"
                    if progress_callback:
                        progress_callback(msg)
                    else:
                        print(msg)
                    return detalhes
                else:
                    msg = f"⚠️ [{indice}/{total}] Sem dados: {url}"
                    if progress_callback:
                        progress_callback(msg)
                    else:
                        print(msg)
                    return None
                    
            except httpx.TimeoutException:
                if tentativa < 2:
                    await asyncio.sleep(1)
                    continue
                else:
                    msg = f"⏱️ [{indice}/{total}] Timeout: {url}"
                    if progress_callback:
                        progress_callback(msg)
                    else:
                        print(msg)
                    return None
                    
            except Exception as e:
                if tentativa < 2:
                    await asyncio.sleep(0.5)
                    continue
                else:
                    msg = f"❌ [{indice}/{total}] Erro: {str(e)[:50]}"
                    if progress_callback:
                        progress_callback(msg)
                    else:
                        print(msg)
                    return None
    
    return None

async def extrair_dados_produto(soup: BeautifulSoup, url: str, nome_base: str) -> Optional[Dict]:
    """
    Extrai dados do produto usando cascata de métodos
    
    Prioridade:
    1. JSON-LD (schema.org)
    2. OpenGraph meta tags
    3. HTML direto
    
    Args:
        soup: BeautifulSoup do HTML
        url: URL do produto
        nome_base: Nome base do produto
    
    Returns:
        Dict com dados do produto ou None
    """
    detalhes = {'url': url}
    
    # 1. Tenta JSON-LD
    json_ld_data = extrair_json_ld(soup)
    if json_ld_data:
        detalhes.update(json_ld_data)
        if detalhes.get('nome') and detalhes.get('preco'):
            return detalhes
    
    # 2. Tenta OpenGraph
    og_data = extrair_opengraph(soup)
    if og_data:
        detalhes.update(og_data)
    
    # 3. Fallback: HTML direto
    html_data = extrair_html_generico(soup, url)
    if html_data:
        # Só adiciona campos que não existem
        for k, v in html_data.items():
            if k not in detalhes:
                detalhes[k] = v
    
    # Se não encontrou nome, usa o nome base
    if not detalhes.get('nome'):
        detalhes['nome'] = nome_base
    
    # Retorna se tem pelo menos nome
    if detalhes.get('nome'):
        return detalhes
    
    return None

def extrair_json_ld(soup: BeautifulSoup) -> Optional[Dict]:
    """Extrai dados de JSON-LD schema.org"""
    try:
        scripts = soup.find_all('script', {'type': 'application/ld+json'})
        
        for script in scripts:
            try:
                data = json.loads(script.string)
                
                # Pode ser um único objeto ou lista
                if isinstance(data, list):
                    for item in data:
                        if item.get('@type') == 'Product':
                            return processar_produto_json_ld(item)
                elif data.get('@type') == 'Product':
                    return processar_produto_json_ld(data)
                    
            except json.JSONDecodeError:
                continue
                
    except Exception:
        pass
    
    return None

def processar_produto_json_ld(data: Dict) -> Dict:
    """Processa dados de produto JSON-LD"""
    detalhes = {}
    
    # Nome
    if 'name' in data:
        detalhes['nome'] = data['name']
    
    # Descrição
    if 'description' in data:
        detalhes['descricao'] = data['description']
    
    # Imagem
    if 'image' in data:
        if isinstance(data['image'], list):
            detalhes['imagem'] = data['image'][0] if data['image'] else None
        elif isinstance(data['image'], dict):
            detalhes['imagem'] = data['image'].get('url')
        else:
            detalhes['imagem'] = data['image']
    
    # Preço (pode estar em offers)
    if 'offers' in data:
        offers = data['offers']
        if isinstance(offers, list):
            offers = offers[0] if offers else {}
        
        if isinstance(offers, dict):
            if 'price' in offers:
                detalhes['preco'] = limpar_preco(offers['price'])
            
            if 'priceCurrency' in offers:
                detalhes['moeda'] = offers['priceCurrency']
            
            if 'availability' in offers:
                detalhes['disponibilidade'] = offers['availability']
    
    # SKU
    if 'sku' in data:
        detalhes['sku'] = data['sku']
    
    # Marca
    if 'brand' in data:
        if isinstance(data['brand'], dict):
            detalhes['marca'] = data['brand'].get('name')
        else:
            detalhes['marca'] = data['brand']
    
    return detalhes

def extrair_opengraph(soup: BeautifulSoup) -> Optional[Dict]:
    """Extrai dados de meta tags OpenGraph"""
    detalhes = {}
    
    # Meta tags OG
    og_title = soup.find('meta', property='og:title')
    if og_title:
        detalhes['nome'] = og_title.get('content')
    
    og_description = soup.find('meta', property='og:description')
    if og_description:
        detalhes['descricao'] = og_description.get('content')
    
    og_image = soup.find('meta', property='og:image')
    if og_image:
        detalhes['imagem'] = og_image.get('content')
    
    og_price = soup.find('meta', property='og:price:amount')
    if og_price:
        detalhes['preco'] = limpar_preco(og_price.get('content'))
    
    og_currency = soup.find('meta', property='og:price:currency')
    if og_currency:
        detalhes['moeda'] = og_currency.get('content')
    
    return detalhes if detalhes else None

def extrair_html_generico(soup: BeautifulSoup, base_url: str) -> Optional[Dict]:
    """Extrai dados diretamente do HTML usando heurísticas"""
    detalhes = {}
    
    # Nome do produto (h1, title)
    h1 = soup.find('h1')
    if h1:
        detalhes['nome'] = h1.get_text(strip=True)
    elif soup.title:
        detalhes['nome'] = soup.title.get_text(strip=True)
    
    # Preço (procura por padrões)
    price_patterns = [
        r'R\$\s*[\d.,]+',
        r'BRL\s*[\d.,]+',
        r'[\d.,]+\s*reais?'
    ]
    
    # Procura em elementos comuns de preço
    price_selectors = [
        {'class': re.compile(r'price|preco|valor', re.I)},
        {'id': re.compile(r'price|preco|valor', re.I)},
        {'itemprop': 'price'}
    ]
    
    for selector in price_selectors:
        price_elem = soup.find(attrs=selector)
        if price_elem:
            text = price_elem.get_text(strip=True)
            for pattern in price_patterns:
                match = re.search(pattern, text, re.I)
                if match:
                    detalhes['preco'] = limpar_preco(match.group())
                    break
            if 'preco' in detalhes:
                break
    
    # Imagem (primeira imagem do produto)
    img = soup.find('img', {'class': re.compile(r'product|produto', re.I)})
    if not img:
        img = soup.find('img', {'itemprop': 'image'})
    if img:
        img_url = img.get('src') or img.get('data-src')
        if img_url:
            detalhes['imagem'] = urljoin(base_url, img_url)
    
    # Descrição
    desc = soup.find('meta', {'name': 'description'})
    if desc:
        detalhes['descricao'] = desc.get('content')
    
    return detalhes if detalhes else None

def limpar_preco(preco_str) -> Optional[str]:
    """Limpa e padroniza string de preço"""
    if not preco_str:
        return None
    
    # Converte para string se for número
    preco_str = str(preco_str)
    
    # Remove tudo exceto dígitos, vírgula e ponto
    preco_limpo = re.sub(r'[^\d.,]', '', preco_str)
    
    # Se tem vírgula e ponto, assume formato brasileiro (1.234,56)
    if ',' in preco_limpo and '.' in preco_limpo:
        preco_limpo = preco_limpo.replace('.', '').replace(',', '.')
    # Se só tem vírgula, assume que é decimal
    elif ',' in preco_limpo:
        preco_limpo = preco_limpo.replace(',', '.')
    
    try:
        # Valida se é um número
        float(preco_limpo)
        return preco_limpo
    except ValueError:
        return None

async def extrair_detalhes_turbo_async(produtos: List[Dict], progress_callback=None, max_produtos: int = None, max_workers: int = 5) -> List[Dict]:
    """
    Extrai detalhes de múltiplos produtos em paralelo (modo turbo)
    Detecta automaticamente o tipo de site e ajusta workers/delay
    
    Args:
        produtos: Lista de dicts com 'url' e 'nome'
        progress_callback: Função de callback para atualizar progresso
        max_produtos: Limite de produtos a processar (None = todos)
        max_workers: Número de workers simultâneos (padrão: 5, será ajustado automaticamente)
    
    Returns:
        Lista de dicts com detalhes dos produtos
    """
    # Limita produtos se necessário
    if max_produtos:
        produtos = produtos[:max_produtos]
    
    if not produtos:
        return []
    
    # Detecta tipo de site analisando primeiro produto
    if progress_callback:
        progress_callback("� Detectando tipo de site...")
    
    async with httpx.AsyncClient(
        headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        },
        timeout=15.0
    ) as client_teste:
        tipo_site, workers_recomendados = await detectar_tipo_site(produtos[0]['url'], client_teste)
    
    # Usa workers recomendados (ignora o parâmetro max_workers)
    workers_usar = workers_recomendados
    delay_entre_requests = 0.5 if tipo_site == 'dinamico' else 0
    
    if progress_callback:
        if tipo_site == 'dinamico':
            progress_callback(f"🐌 Site DINÂMICO detectado (hidratação JS): {workers_usar} workers, delay 0.5s")
        else:
            progress_callback(f"🚀 Site ESTÁTICO detectado (HTML pronto): {workers_usar} workers, SEM delay")
        progress_callback(f"📦 Processando {len(produtos)} produtos...")
    else:
        print(f"\n{'� Site DINÂMICO' if tipo_site == 'dinamico' else '🚀 Site ESTÁTICO'}")
        print(f"Workers: {workers_usar}, Delay: {delay_entre_requests}s")
        print(f"📦 Processando {len(produtos)} produtos...\n")
    
    semaphore = asyncio.Semaphore(workers_usar)
    start_time = time.time()
    
    async with httpx.AsyncClient(
        headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        },
        timeout=15.0
    ) as client:
        tasks = [
            extrair_produto_turbo(produto, i+1, client, semaphore, len(produtos), progress_callback, delay_entre_requests)
            for i, produto in enumerate(produtos)
        ]
        
        resultados = await asyncio.gather(*tasks, return_exceptions=True)
    
    elapsed = time.time() - start_time
    
    # Filtra resultados válidos
    detalhes_extraidos = [
        r for r in resultados 
        if r is not None and not isinstance(r, Exception)
    ]
    
    # Calcula estatísticas
    taxa_sucesso = len(detalhes_extraidos)/len(produtos)*100 if produtos else 0
    produtos_por_segundo = len(detalhes_extraidos) / elapsed if elapsed > 0 else 0
    
    if progress_callback:
        progress_callback(f"✅ Concluído em {elapsed:.1f}s: {len(detalhes_extraidos)}/{len(produtos)} produtos")
        progress_callback(f"📊 Taxa: {taxa_sucesso:.1f}% | Velocidade: {produtos_por_segundo:.1f} produtos/s")
    else:
        print(f"\n✅ Concluído em {elapsed:.1f}s: {len(detalhes_extraidos)}/{len(produtos)} produtos")
        print(f"📊 Taxa: {taxa_sucesso:.1f}% | Velocidade: {produtos_por_segundo:.1f} produtos/s")
    
    return detalhes_extraidos

# Função principal para ser chamada pelo Streamlit
def extrair_detalhes_turbo(produtos: List[Dict], progress_callback=None, max_produtos: int = None, max_workers: int = 5):
    """
    Wrapper síncrono para extrair_detalhes_turbo_async
    Retorna tupla (texto_resultado, lista_detalhes) para compatibilidade com Streamlit
    
    Args:
        produtos: Lista de dicts com 'url' e 'nome'
        progress_callback: Função de callback para atualizar progresso
        max_produtos: Limite de produtos a processar
        max_workers: Número de workers simultâneos
    
    Returns:
        Tupla (texto_resultado, lista_detalhes)
    """
    detalhes = asyncio.run(extrair_detalhes_turbo_async(produtos, progress_callback, max_produtos, max_workers))
    
    # Formata resultado como texto
    texto_resultado = f"Extraídos {len(detalhes)} produtos de {len(produtos[:max_produtos] if max_produtos else produtos)}"
    
    return texto_resultado, detalhes
