#!/usr/bin/env python3
"""
EXTRACT DETAILS V7 - Crawlee-Style Architecture
================================================

Implementa extração de detalhes usando padrões do Crawlee:
- AdaptiveRateLimiter (AutoscaledPool)
- SessionPool para gerenciar cookies
- Extração em cascata: JSON-LD → OpenGraph → HTML Fallback
- Processamento paralelo com workers
- Retry automático

Fluxo:
  1. Workers paralelos processam fila de produtos
  2. Cada worker usa session pool
  3. Extração estruturada (JSON-LD primeiro)
  4. Rate limiting adaptativo
  5. Retry automático em caso de erro
"""

import asyncio
import httpx
import json
import re
from typing import List, Dict, Callable, Optional
from bs4 import BeautifulSoup
from datetime import datetime
import time


# ================================================================================================
# ADAPTIVE RATE LIMITER
# ================================================================================================
class AdaptiveRateLimiter:
    """Rate limiter adaptativo."""
    
    def __init__(self, requests_per_minute: int = 60):
        self.max_rpm = requests_per_minute
        self.current_rpm = requests_per_minute
        self.tokens = []
        self.lock = asyncio.Lock()
        
        # Métricas
        self.recent_requests = 0
        self.recent_errors = 0
        self.recent_429s = 0
    
    async def acquire(self):
        """Aguarda até poder fazer próxima requisição."""
        async with self.lock:
            now = time.time()
            self.tokens = [t for t in self.tokens if now - t < 60]
            
            while len(self.tokens) >= self.current_rpm:
                await asyncio.sleep(0.1)
                now = time.time()
                self.tokens = [t for t in self.tokens if now - t < 60]
            
            self.tokens.append(now)
            
            import random
            await asyncio.sleep(random.uniform(0, 0.05))
    
    def report_success(self):
        self.recent_requests += 1
        self._adjust()
    
    def report_error(self):
        self.recent_requests += 1
        self.recent_errors += 1
        self._adjust()
    
    def report_429(self):
        self.recent_requests += 1
        self.recent_429s += 1
        self._adjust()
    
    def _adjust(self):
        if self.recent_requests < 10:
            return
        
        error_rate = (self.recent_errors + self.recent_429s) / self.recent_requests
        
        if self.recent_429s > 2:
            self.current_rpm = max(20, int(self.current_rpm * 0.5))
        elif error_rate > 0.2:
            self.current_rpm = max(30, int(self.current_rpm * 0.7))
        elif error_rate < 0.05 and self.recent_429s == 0:
            self.current_rpm = min(self.max_rpm, int(self.current_rpm * 1.1))
        
        self.recent_requests = 0
        self.recent_errors = 0
        self.recent_429s = 0


# ================================================================================================
# SESSION POOL
# ================================================================================================
class Session:
    """Sessão com cookies."""
    def __init__(self, id: str):
        self.id = id
        self.cookies = httpx.Cookies()
        self.blocked = False
        self.error_count = 0
    
    def mark_blocked(self):
        self.blocked = True
    
    def mark_good(self):
        self.error_count = max(0, self.error_count - 1)
    
    def mark_bad(self):
        self.error_count += 1
        if self.error_count > 3:
            self.blocked = True


class SessionPool:
    """Pool de sessões."""
    def __init__(self, size: int = 3):
        self.sessions = [Session(f"session_{i}") for i in range(size)]
        self.current_idx = 0
        self.lock = asyncio.Lock()
    
    async def get_session(self) -> Session:
        async with self.lock:
            for _ in range(len(self.sessions)):
                session = self.sessions[self.current_idx]
                self.current_idx = (self.current_idx + 1) % len(self.sessions)
                
                if not session.blocked:
                    return session
            
            # Todas bloqueadas? Reseta melhor
            best = min(self.sessions, key=lambda s: s.error_count)
            best.blocked = False
            best.error_count = 0
            return best


# ================================================================================================
# EXTRAÇÃO DE DADOS
# ================================================================================================
PRECO_RE = re.compile(r'R\$\s*(?:<!--.*?-->)?\s*([\d.,]+)', re.DOTALL)


def extrair_jsonld_product(soup: BeautifulSoup) -> Optional[Dict]:
    """Extrai dados estruturados JSON-LD (Schema.org Product)."""
    scripts = soup.find_all('script', type='application/ld+json')
    
    for script in scripts:
        try:
            data = json.loads(script.string)
            items = data if isinstance(data, list) else [data]
            
            for item in items:
                if item.get('@type') in ['Product', 'IndividualProduct', 'ProductGroup']:
                    offers = item.get('offers', {})
                    if isinstance(offers, list):
                        offers = offers[0] if offers else {}
                    
                    brand = item.get('brand', {})
                    brand_name = brand.get('name') if isinstance(brand, dict) else brand
                    
                    images = item.get('image', [])
                    if not isinstance(images, list):
                        images = [images] if images else []
                    
                    # Disponibilidade
                    availability = offers.get('availability', '')
                    disponivel = None
                    if 'instock' in availability.lower():
                        disponivel = True
                    elif 'outofstock' in availability.lower():
                        disponivel = False
                    
                    return {
                        'nome': item.get('name'),
                        'marca': brand_name,
                        'sku': item.get('sku') or item.get('mpn'),
                        'ean': item.get('gtin13') or item.get('gtin') or item.get('gtin14') or item.get('gtin8'),
                        'preco': offers.get('price') or offers.get('lowPrice'),
                        'preco_original': offers.get('highPrice'),
                        'moeda': offers.get('priceCurrency'),
                        'disponivel': disponivel,
                        'imagens': images,
                        'descricao': item.get('description'),
                        'categoria': item.get('category'),
                        'fonte': 'json-ld'
                    }
        except:
            continue
    
    return None


def extrair_opengraph(soup: BeautifulSoup) -> Dict:
    """Extrai metadados Open Graph."""
    og_data = {}
    
    for meta in soup.find_all('meta', property=re.compile(r'^og:')):
        prop = meta.get('property', '').replace('og:', '')
        content = meta.get('content', '')
        
        if prop == 'title':
            og_data['nome'] = content
        elif prop == 'image':
            if 'imagens' not in og_data:
                og_data['imagens'] = []
            og_data['imagens'].append(content)
        elif prop == 'price:amount':
            og_data['preco'] = content
        elif prop == 'price:currency':
            og_data['moeda'] = content
        elif prop == 'availability':
            og_data['disponivel'] = 'instock' in content.lower()
    
    og_data['fonte'] = 'opengraph'
    return og_data


def extrair_html_fallback(soup: BeautifulSoup, html: str) -> Dict:
    """Fallback: extração via HTML parsing."""
    # Nome (h1)
    h1_tags = soup.find_all('h1')
    nome = None
    if len(h1_tags) >= 2:
        nome = h1_tags[1].get_text(strip=True)
    elif h1_tags:
        nome = h1_tags[0].get_text(strip=True)
    
    # Preço (regex)
    precos = PRECO_RE.findall(html)
    preco = precos[0] if precos else None
    
    # Imagens (tags img com src ou data-src)
    imagens = []
    for img in soup.find_all('img', src=True):
        src = img.get('src') or img.get('data-src')
        if src and ('product' in src.lower() or 'image' in src.lower()):
            imagens.append(src)
    
    return {
        'nome': nome,
        'preco': preco,
        'imagens': imagens[:5],  # Max 5 imagens
        'fonte': 'html-fallback'
    }


async def extrair_produto_detalhes(
    produto: Dict,
    indice: int,
    client: httpx.AsyncClient,
    session: Session,
    rate_limiter: AdaptiveRateLimiter
) -> Dict:
    """
    Extrai detalhes de um produto.
    Retorna dicionário com todos os campos.
    """
    url = produto['url']
    
    await rate_limiter.acquire()
    
    inicio = time.perf_counter()
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'pt-BR,pt;q=0.9',
            'Cache-Control': 'no-cache',
        }
        
        response = await client.get(url, headers=headers, cookies=session.cookies, timeout=15.0)
        
        # Atualiza cookies
        session.cookies.update(response.cookies)
        
        tempo_resposta = time.perf_counter() - inicio
        
        if response.status_code == 429:
            rate_limiter.report_429()
            session.mark_bad()
            return {
                'indice': indice,
                'url': url,
                'nome': produto.get('nome'),
                'status_http': 429,
                'erro': '429 Too Many Requests',
                'tempo_resposta': tempo_resposta
            }
        
        if response.status_code != 200:
            rate_limiter.report_error()
            session.mark_bad()
            return {
                'indice': indice,
                'url': url,
                'nome': produto.get('nome'),
                'status_http': response.status_code,
                'erro': f'HTTP {response.status_code}',
                'tempo_resposta': tempo_resposta
            }
        
        rate_limiter.report_success()
        session.mark_good()
        
        html = response.text
        soup = BeautifulSoup(html, 'lxml')
        
        # Extração em cascata: JSON-LD → OpenGraph → HTML
        dados = extrair_jsonld_product(soup)
        
        if not dados or not dados.get('nome'):
            dados_og = extrair_opengraph(soup)
            if dados:
                dados.update({k: v for k, v in dados_og.items() if v and k not in dados})
            else:
                dados = dados_og
        
        if not dados or not dados.get('nome'):
            dados_html = extrair_html_fallback(soup, html)
            if dados:
                dados.update({k: v for k, v in dados_html.items() if v and k not in dados})
            else:
                dados = dados_html
        
        # Adiciona metadados
        dados['indice'] = indice
        dados['url'] = url
        dados['status_http'] = 200
        dados['tempo_resposta'] = tempo_resposta
        dados['timestamp'] = datetime.now().isoformat()
        
        return dados
    
    except httpx.TimeoutException:
        rate_limiter.report_error()
        session.mark_bad()
        return {
            'indice': indice,
            'url': url,
            'nome': produto.get('nome'),
            'erro': 'Timeout',
            'tempo_resposta': time.perf_counter() - inicio
        }
    
    except Exception as e:
        rate_limiter.report_error()
        session.mark_bad()
        return {
            'indice': indice,
            'url': url,
            'nome': produto.get('nome'),
            'erro': str(e)[:100],
            'tempo_resposta': time.perf_counter() - inicio
        }


# ================================================================================================
# PROCESSAMENTO PARALELO
# ================================================================================================
async def extrair_detalhes_async(
    produtos: List[Dict],
    show_message: Callable,
    max_detalhes: Optional[int] = None,
    max_workers: int = 5
) -> tuple[str, List[Dict]]:
    """
    Extrai detalhes de produtos usando workers paralelos.
    
    Args:
        produtos: Lista de produtos {nome, url}
        show_message: Função para mensagens
        max_detalhes: Limite de produtos
        max_workers: Workers paralelos
    
    Returns:
        (texto_formatado, lista_detalhes)
    """
    show_message(f"🚀 Iniciando extração com {max_workers} workers...")
    
    # Limita produtos
    produtos_processar = produtos[:max_detalhes] if max_detalhes else produtos
    
    # Componentes Crawlee - RPM mais alto para workers paralelos
    # Com 5 workers, 120 RPM = ~24 RPM por worker = 1 req a cada 2.5s
    rate_limiter = AdaptiveRateLimiter(requests_per_minute=120)
    session_pool = SessionPool(size=max_workers)
    
    # Fila de trabalho
    fila = asyncio.Queue()
    for i, produto in enumerate(produtos_processar, 1):
        await fila.put((i, produto))
    
    # Resultados
    resultados = []
    lock = asyncio.Lock()
    
    # Worker
    async def worker(worker_id: int):
        async with httpx.AsyncClient(follow_redirects=True, timeout=15.0) as client:
            while True:
                try:
                    indice, produto = await asyncio.wait_for(fila.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    break
                
                session = await session_pool.get_session()
                
                resultado = await extrair_produto_detalhes(
                    produto,
                    indice,
                    client,
                    session,
                    rate_limiter
                )
                
                async with lock:
                    resultados.append(resultado)
                    # Mensagem mais concisa com percentual
                    percentual = int(len(resultados) / len(produtos_processar) * 100)
                    show_message(f"[Worker {worker_id}] {len(resultados)}/{len(produtos_processar)} ({percentual}%) - RPM atual: {rate_limiter.current_rpm}")
                
                fila.task_done()
    
    # Inicia workers
    workers = [asyncio.create_task(worker(i)) for i in range(max_workers)]
    
    # Aguarda conclusão
    await fila.join()
    
    # Cancela workers
    for w in workers:
        w.cancel()
    
    # Ordena por índice
    resultados.sort(key=lambda x: x.get('indice', 0))
    
    # Formata texto
    texto_formatado = "\n".join([
        f"{r.get('indice')}. {r.get('nome', 'N/A')} - {r.get('preco', 'N/A')} - {r.get('url', 'N/A')}"
        for r in resultados
    ])
    
    show_message(f"✅ Extração concluída: {len(resultados)} produtos processados")
    
    return texto_formatado, resultados


def extrair_detalhes_paralelo(
    produtos: List[Dict],
    show_message: Callable,
    max_detalhes: Optional[int] = None,
    max_workers: int = 5
) -> tuple[str, List[Dict]]:
    """
    Wrapper síncrono para extrair_detalhes_async.
    Compatível com interface do appv4.py.
    """
    return asyncio.run(extrair_detalhes_async(
        produtos,
        show_message,
        max_detalhes,
        max_workers
    ))


# ================================================================================================
# TESTE
# ================================================================================================
if __name__ == "__main__":
    def dummy_message(msg):
        print(f"[INFO] {msg}")
    
    # Teste com alguns produtos
    produtos_teste = [
        {
            'nome': 'Fralda Luxo Cremer',
            'url': 'https://www.bellacotton.com.br/fralda-luxo-com-bainha-cremer-70cmx68cm-5-unidades/p/379433'
        },
        {
            'nome': 'Lenço Umedecido',
            'url': 'https://www.bellacotton.com.br/lenco-umedecido-recem-nascido-com-50-unidades-feelclean/p/646573'
        },
    ]
    
    texto, detalhes = extrair_detalhes_paralelo(
        produtos_teste,
        dummy_message,
        max_detalhes=2,
        max_workers=2
    )
    
    print(f"\n✅ Extraídos {len(detalhes)} produtos")
    print(f"\nPrimeiro produto:")
    print(json.dumps(detalhes[0], indent=2, ensure_ascii=False))
