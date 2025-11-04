#!/usr/bin/env python3
"""
CRAWLEE-STYLE SCRAPER - Arquitetura Profissional
=================================================

Implementa padrões do Crawlee:
1. Router com labels (LIST → PRODUCT)
2. RequestQueue com prioridade
3. AutoscaledPool com rate limiting inteligente
4. SessionPool para gerenciar cookies/headers
5. Extração em cascata: JSON-LD → HTML Fallback
6. Detecção VTEX → API em lote (50 produtos/request)

Fluxo:
  SEED (categorias) → LIST (enqueue produtos) → PRODUCT (extrair dados)
"""

import asyncio
import httpx
import time
import json
import random
from datetime import datetime
from typing import Optional, Dict, Any, List, Callable
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import re
from dataclasses import dataclass, asdict, field
from enum import Enum


# ================================================================================================
# TIPOS E CONFIGURAÇÃO
# ================================================================================================
class RouteLabel(Enum):
    """Labels de roteamento (como no Crawlee Router)."""
    SEED = "SEED"          # URLs iniciais (categorias)
    LIST = "LIST"          # Páginas de listagem
    PRODUCT = "PRODUCT"    # Páginas de produto
    VTEX_API = "VTEX_API"  # API VTEX em lote


@dataclass
class Request:
    """Request similar ao Crawlee Request."""
    url: str
    label: RouteLabel = RouteLabel.PRODUCT
    user_data: Dict[str, Any] = field(default_factory=dict)
    retry_count: int = 0
    priority: int = 0  # Maior = mais prioritário


@dataclass
class Context:
    """Context passado para handlers (como no Crawlee)."""
    request: Request
    soup: Optional[BeautifulSoup] = None
    html: Optional[str] = None
    json_data: Optional[Dict] = None
    enqueue_links: Optional[Callable] = None
    push_data: Optional[Callable] = None


@dataclass
class Config:
    """Configuração do crawler."""
    max_requests_per_minute: int = 120  # Rate limiting global
    max_concurrency: int = 5            # Requisições simultâneas
    timeout: float = 20.0
    max_retries: int = 3
    
    # AutoScaling
    autoscale_enabled: bool = True
    autoscale_interval: int = 20  # Ajusta a cada N requests
    error_threshold: float = 0.15  # >15% erros = reduz velocidade
    
    # Session Pool
    session_pool_size: int = 5
    persist_cookies: bool = True
    
    # Output
    checkpoint_interval: int = 50
    output_file: str = "produtos_bellacotton.ndjson"


# ================================================================================================
# SESSION POOL (gerencia cookies e rotação de sessões)
# ================================================================================================
@dataclass
class Session:
    """Sessão com cookies e headers."""
    id: str
    cookies: httpx.Cookies
    blocked: bool = False
    error_count: int = 0
    success_count: int = 0
    
    def mark_blocked(self):
        self.blocked = True
    
    def mark_good(self):
        self.error_count = max(0, self.error_count - 1)
        self.success_count += 1
    
    def mark_bad(self):
        self.error_count += 1
        if self.error_count > 3:
            self.blocked = True


class SessionPool:
    """
    Pool de sessões similar ao Crawlee SessionPool.
    Rotaciona cookies e detecta sessões bloqueadas.
    """
    
    def __init__(self, size: int = 5):
        self.sessions = [
            Session(
                id=f"session_{i}",
                cookies=httpx.Cookies()
            )
            for i in range(size)
        ]
        self.current_idx = 0
        self.lock = asyncio.Lock()
    
    async def get_session(self) -> Session:
        """Pega próxima sessão disponível (não bloqueada)."""
        async with self.lock:
            # Tenta encontrar sessão não bloqueada
            for _ in range(len(self.sessions)):
                session = self.sessions[self.current_idx]
                self.current_idx = (self.current_idx + 1) % len(self.sessions)
                
                if not session.blocked:
                    return session
            
            # Todas bloqueadas? Reseta a "melhor"
            best = min(self.sessions, key=lambda s: s.error_count)
            best.blocked = False
            best.error_count = 0
            return best


# ================================================================================================
# REQUEST QUEUE (fila com prioridade e deduplicação)
# ================================================================================================
class RequestQueue:
    """
    Fila de requisições com prioridade e deduplicação.
    Similar ao Crawlee RequestQueue.
    """
    
    def __init__(self):
        self.queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self.seen_urls: set = set()
        self.in_progress: Dict[str, Request] = {}
        self.completed_count: int = 0
        self.failed_count: int = 0
        self.lock = asyncio.Lock()
        self.counter: int = 0  # Contador para desempate na PriorityQueue
    
    async def add_request(self, request: Request, force: bool = False):
        """Adiciona request à fila (com deduplicação)."""
        async with self.lock:
            if not force and request.url in self.seen_urls:
                return
            
            self.seen_urls.add(request.url)
            # Prioridade negativa (maior prioridade = menor número na fila)
            # Usa counter para desempate (evita comparar Request objects)
            self.counter += 1
            await self.queue.put((-request.priority, self.counter, request))
    
    async def add_requests(self, requests: List[Request]):
        """Adiciona múltiplos requests."""
        for req in requests:
            await self.add_request(req)
    
    async def fetch_next_request(self) -> Optional[Request]:
        """Pega próximo request da fila."""
        try:
            _, _, request = await asyncio.wait_for(self.queue.get(), timeout=1.0)
            async with self.lock:
                self.in_progress[request.url] = request
            return request
        except asyncio.TimeoutError:
            return None
    
    def mark_completed(self, url: str):
        """Marca request como concluído."""
        if url in self.in_progress:
            del self.in_progress[url]
        self.completed_count += 1
    
    def mark_failed(self, url: str):
        """Marca request como falhado."""
        if url in self.in_progress:
            del self.in_progress[url]
        self.failed_count += 1
    
    def is_empty(self) -> bool:
        """Verifica se fila está vazia."""
        return self.queue.empty() and len(self.in_progress) == 0
    
    def get_stats(self) -> Dict:
        """Retorna estatísticas."""
        return {
            "pending": self.queue.qsize(),
            "in_progress": len(self.in_progress),
            "completed": self.completed_count,
            "failed": self.failed_count
        }


# ================================================================================================
# ROUTER (roteamento por label)
# ================================================================================================
class Router:
    """
    Router similar ao Crawlee Router.
    Roteia requests para handlers específicos por label.
    """
    
    def __init__(self):
        self.handlers: Dict[RouteLabel, Callable] = {}
        self.default_handler: Optional[Callable] = None
    
    def add_handler(self, label: RouteLabel, handler: Callable):
        """Registra handler para uma label."""
        self.handlers[label] = handler
    
    def add_default_handler(self, handler: Callable):
        """Handler padrão para labels sem handler específico."""
        self.default_handler = handler
    
    async def route(self, context: Context):
        """Roteia context para handler apropriado."""
        handler = self.handlers.get(context.request.label, self.default_handler)
        
        if handler:
            await handler(context)
        else:
            print(f"⚠️  Nenhum handler para label: {context.request.label}")


# ================================================================================================
# ADAPTIVE RATE LIMITER (AutoscaledPool)
# ================================================================================================
class AdaptiveRateLimiter:
    """
    Rate limiter adaptativo similar ao AutoscaledPool.
    Ajusta velocidade automaticamente com base em erros.
    """
    
    def __init__(self, requests_per_minute: int, autoscale: bool = True):
        self.max_rpm = requests_per_minute
        self.current_rpm = requests_per_minute
        self.autoscale = autoscale
        
        # Controle de taxa
        self.tokens = []
        self.lock = asyncio.Lock()
        
        # Métricas para autoscaling
        self.recent_requests = 0
        self.recent_errors = 0
        self.recent_429s = 0
    
    async def acquire(self):
        """Aguarda até poder fazer próxima requisição."""
        async with self.lock:
            now = time.time()
            
            # Remove tokens antigos (>60s)
            self.tokens = [t for t in self.tokens if now - t < 60]
            
            # Se atingiu limite, aguarda
            while len(self.tokens) >= self.current_rpm:
                await asyncio.sleep(0.1)
                now = time.time()
                self.tokens = [t for t in self.tokens if now - t < 60]
            
            # Adiciona novo token
            self.tokens.append(now)
            
            # Jitter leve para evitar bursts
            await asyncio.sleep(random.uniform(0, 0.1))
    
    def report_success(self):
        self.recent_requests += 1
        self._maybe_adjust()
    
    def report_error(self):
        self.recent_requests += 1
        self.recent_errors += 1
        self._maybe_adjust()
    
    def report_429(self):
        self.recent_requests += 1
        self.recent_429s += 1
        self._maybe_adjust()
    
    def _maybe_adjust(self):
        """Ajusta RPM automaticamente."""
        if not self.autoscale or self.recent_requests < 10:  # Ajusta mais rápido (10 vs 20)
            return
        
        error_rate = (self.recent_errors + self.recent_429s) / self.recent_requests
        
        old_rpm = self.current_rpm
        
        if self.recent_429s > 2:  # Mais sensível (2 vs 3)
            # Muitos 429s = reduz drasticamente
            self.current_rpm = max(15, int(self.current_rpm * 0.3))  # Reduz 70%!
            print(f"⚠️  Muitos 429s ({self.recent_429s})! RPM: {old_rpm} → {self.current_rpm}")
        
        elif error_rate > 0.2:  # Mais sensível (20% vs 15%)
            # Muitos erros = reduz
            self.current_rpm = max(20, int(self.current_rpm * 0.6))  # Reduz 40%
            print(f"⚠️  Taxa de erro alta ({error_rate:.0%}). RPM: {old_rpm} → {self.current_rpm}")
        
        elif error_rate < 0.05 and self.recent_429s == 0:
            # Poucos erros = aumenta devagar
            self.current_rpm = min(self.max_rpm, int(self.current_rpm * 1.05))  # Aumenta só 5%
            if self.current_rpm != old_rpm:
                print(f"✅ Baixa taxa de erro! RPM: {old_rpm} → {self.current_rpm}")
        
        # Reset métricas
        self.recent_requests = 0
        self.recent_errors = 0
        self.recent_429s = 0


# ================================================================================================
# EXTRAÇÃO DE DADOS
# ================================================================================================
PRECO_RE = re.compile(r'R\$\s*(?:<!--.*?-->)?\s*([\d.,]+)', re.DOTALL)


def extrair_jsonld_product(soup: BeautifulSoup) -> Optional[Dict]:
    """
    Extrai dados estruturados JSON-LD (Schema.org Product).
    Primeira tentativa - dados mais confiáveis.
    """
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
                    
                    return {
                        'nome': item.get('name'),
                        'marca': brand_name,
                        'sku': item.get('sku') or item.get('mpn'),
                        'ean': item.get('gtin13') or item.get('gtin') or item.get('gtin14') or item.get('gtin8'),
                        'preco': offers.get('price') or offers.get('lowPrice'),
                        'moeda': offers.get('priceCurrency'),
                        'imagens': images,
                        'descricao': item.get('description'),
                        'fonte': 'json-ld'
                    }
        except:
            continue
    
    return None


def extrair_html_fallback(soup: BeautifulSoup, html: str) -> Dict:
    """
    Fallback: extração via HTML parsing.
    Usado quando JSON-LD não está disponível.
    """
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
    
    # SKU/EAN (tentativa via regex)
    sku_match = re.search(r'(?:sku|codigo|SKU)["\']?\s*:?\s*["\']?([A-Z0-9\-]+)', html, re.IGNORECASE)
    sku = sku_match.group(1) if sku_match else None
    
    return {
        'nome': nome,
        'preco': preco,
        'sku': sku,
        'fonte': 'html-fallback'
    }


# ================================================================================================
# HANDLERS (similar aos handlers do Crawlee Router)
# ================================================================================================
async def handle_list(context: Context):
    """
    Handler para páginas de listagem (LIST).
    Enfileira produtos e próxima página.
    """
    soup = context.soup
    request = context.request
    
    # Enfileira links de produtos
    product_links = soup.select('a[href*="/produto/"]')
    product_requests = []
    
    for link in product_links:
        href = link.get('href')
        if href:
            url = urljoin(request.url, href)
            product_requests.append(Request(
                url=url,
                label=RouteLabel.PRODUCT,
                priority=5  # Produtos têm prioridade média
            ))
    
    if product_requests and context.enqueue_links:
        await context.enqueue_links(product_requests)
        print(f"   📋 Enfileirou {len(product_requests)} produtos")
    
    # Enfileira próxima página
    next_links = soup.select('a[rel="next"], .pagination a.next, a.next-page')
    
    for link in next_links:
        href = link.get('href')
        if href:
            url = urljoin(request.url, href)
            await context.enqueue_links([Request(
                url=url,
                label=RouteLabel.LIST,
                priority=10  # Listagens têm prioridade alta
            )])
            print(f"   ➡️  Enfileirou próxima página")
            break


async def handle_product(context: Context):
    """
    Handler para páginas de produto (PRODUCT).
    Extrai dados em cascata: JSON-LD → HTML fallback.
    """
    soup = context.soup
    html = context.html
    request = context.request
    
    # Tentativa 1: JSON-LD (estruturado)
    produto = extrair_jsonld_product(soup)
    
    # Tentativa 2: HTML fallback
    if not produto or not produto.get('nome'):
        produto_html = extrair_html_fallback(soup, html)
        if produto:
            produto.update(produto_html)
        else:
            produto = produto_html
    
    # Adiciona metadados
    produto['url'] = request.url
    produto['timestamp'] = datetime.now().isoformat()
    
    # Salva produto
    if context.push_data:
        await context.push_data(produto)


# ================================================================================================
# CRAWLER PRINCIPAL
# ================================================================================================
class CrawleeCrawler:
    """
    Crawler principal inspirado no Crawlee CheerioCrawler.
    """
    
    def __init__(self, config: Config, router: Router):
        self.config = config
        self.router = router
        
        # Componentes
        self.request_queue = RequestQueue()
        self.session_pool = SessionPool(config.session_pool_size)
        self.rate_limiter = AdaptiveRateLimiter(
            config.max_requests_per_minute,
            autoscale=config.autoscale_enabled
        )
        
        # Armazenamento
        self.produtos: List[Dict] = []
        self.stats = {
            'requests': 0,
            'successes': 0,
            'errors': 0
        }
    
    async def enqueue_links(self, requests: List[Request]):
        """Enfileira links (chamado pelos handlers)."""
        await self.request_queue.add_requests(requests)
    
    async def push_data(self, data: Dict):
        """Salva dados extraídos."""
        self.produtos.append(data)
        
        # Checkpoint periódico
        if len(self.produtos) % self.config.checkpoint_interval == 0:
            self._save_checkpoint()
    
    async def fetch_and_parse(self, request: Request, session: Session) -> Optional[Context]:
        """Faz requisição e parseia resposta."""
        await self.rate_limiter.acquire()
        
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'pt-BR,pt;q=0.9',
                'Cache-Control': 'no-cache',
            }
            
            async with httpx.AsyncClient(
                timeout=self.config.timeout,
                follow_redirects=True,
                cookies=session.cookies
            ) as client:
                response = await client.get(request.url, headers=headers)
                
                # Atualiza cookies da sessão
                session.cookies.update(response.cookies)
                
                if response.status_code == 429:
                    self.rate_limiter.report_429()
                    session.mark_bad()
                    print(f"   ⚠️  429 Too Many Requests - aguardando...")
                    await asyncio.sleep(10)  # Pausa de 10s quando pega 429
                    return None
                
                if response.status_code == 403:
                    print(f"   🚫 403 Forbidden - IP pode estar banido!")
                    self.rate_limiter.report_error()
                    session.mark_bad()
                    await asyncio.sleep(30)  # Pausa longa em caso de ban
                    return None
                
                if response.status_code != 200:
                    self.rate_limiter.report_error()
                    session.mark_bad()
                    print(f"   ❌ HTTP {response.status_code}")
                    return None
                
                html = response.text
                soup = BeautifulSoup(html, 'lxml')
                
                self.rate_limiter.report_success()
                session.mark_good()
                
                return Context(
                    request=request,
                    soup=soup,
                    html=html,
                    enqueue_links=self.enqueue_links,
                    push_data=self.push_data
                )
        
        except Exception as e:
            self.rate_limiter.report_error()
            session.mark_bad()
            return None
    
    async def process_request(self, request: Request):
        """Processa um request."""
        session = await self.session_pool.get_session()
        
        context = await self.fetch_and_parse(request, session)
        
        if context:
            self.stats['successes'] += 1
            self.stats['requests'] += 1
            
            # Log de sucesso
            stats = self.request_queue.get_stats()
            print(f"[{stats['completed']+1:3d}] ✅ OK - RPM atual: {self.rate_limiter.current_rpm}")
            
            await self.router.route(context)
            self.request_queue.mark_completed(request.url)
        else:
            self.stats['errors'] += 1
            self.stats['requests'] += 1
            
            # Retry se não atingiu limite
            if request.retry_count < self.config.max_retries:
                request.retry_count += 1
                print(f"   🔄 Retry {request.retry_count}/{self.config.max_retries}")
                await self.request_queue.add_request(request, force=True)
            else:
                print(f"   ❌ Falha definitiva após {self.config.max_retries} tentativas")
                self.request_queue.mark_failed(request.url)
    
    async def run(self, seeds: List[Request]):
        """
        Executa crawler com seeds iniciais.
        Similar ao crawler.run() do Crawlee.
        """
        print(f"{'='*100}")
        print(f"🚀 CRAWLEE-STYLE CRAWLER")
        print(f"{'='*100}")
        print(f"Max RPM: {self.config.max_requests_per_minute}")
        print(f"Max Concurrency: {self.config.max_concurrency}")
        print(f"AutoScale: {self.config.autoscale_enabled}")
        print(f"{'='*100}\n")
        
        # Adiciona seeds
        await self.request_queue.add_requests(seeds)
        
        inicio = time.time()
        
        # Worker pool
        workers = []
        for i in range(self.config.max_concurrency):
            workers.append(asyncio.create_task(self._worker(i)))
        
        # Aguarda conclusão
        await asyncio.gather(*workers)
        
        tempo_total = time.time() - inicio
        
        # Resultados finais
        self._print_stats(tempo_total)
        self._save_final()
    
    async def _worker(self, worker_id: int):
        """Worker que processa requests da fila."""
        while True:
            if self.request_queue.is_empty():
                await asyncio.sleep(0.5)
                if self.request_queue.is_empty():
                    break
            
            request = await self.request_queue.fetch_next_request()
            if request:
                self.stats['requests'] += 1
                await self.process_request(request)
    
    def _save_checkpoint(self):
        """Salva checkpoint."""
        with open(f"checkpoint_{len(self.produtos)}.json", "w", encoding="utf-8") as f:
            json.dump(self.produtos, f, indent=2, ensure_ascii=False)
        print(f"   💾 Checkpoint: {len(self.produtos)} produtos")
    
    def _save_final(self):
        """Salva resultados finais."""
        # NDJSON (uma linha por produto)
        with open(self.config.output_file, "w", encoding="utf-8") as f:
            for produto in self.produtos:
                f.write(json.dumps(produto, ensure_ascii=False) + "\n")
        
        print(f"\n✅ Salvos {len(self.produtos)} produtos em: {self.config.output_file}\n")
    
    def _print_stats(self, tempo_total: float):
        """Imprime estatísticas finais."""
        stats = self.request_queue.get_stats()
        
        print(f"\n{'='*100}")
        print("ESTATÍSTICAS FINAIS")
        print(f"{'='*100}")
        print(f"✅ Sucesso: {stats['completed']}")
        print(f"❌ Falhas: {stats['failed']}")
        print(f"📦 Produtos extraídos: {len(self.produtos)}")
        print(f"⏱️  Tempo total: {tempo_total:.1f}s ({tempo_total/60:.1f} min)")
        if stats['completed'] > 0:
            print(f"📊 Tempo médio: {tempo_total/stats['completed']:.2f}s por request")
        print(f"🚀 RPM final: {self.rate_limiter.current_rpm}")
        print(f"{'='*100}\n")


# ================================================================================================
# MAIN - EXEMPLO DE USO
# ================================================================================================
async def main():
    # Configuração para Bella Cotton (IP limpo)
    config = Config(
        max_requests_per_minute=60,  # Começa com 60 RPM (1 req por segundo)
        max_concurrency=3,           # 3 workers simultâneos
        autoscale_enabled=True,
        checkpoint_interval=10       # Checkpoint a cada 10 produtos
    )
    
    # Router
    router = Router()
    router.add_handler(RouteLabel.LIST, handle_list)
    router.add_handler(RouteLabel.PRODUCT, handle_product)
    
    # Crawler
    crawler = CrawleeCrawler(config, router)
    
    # Seeds - pode ser categorias OU lista de produtos direto
    # Opção 1: Seeds com categorias (crawl completo)
    # seeds = [
    #     Request(url="https://www.matconcasa.com.br/ferramentas", label=RouteLabel.LIST, priority=10),
    #     Request(url="https://www.matconcasa.com.br/construcao", label=RouteLabel.LIST, priority=10),
    # ]
    
    # Opção 2: Seeds com produtos direto (teste rápido)
    try:
        with open('urls_bellacotton_reais.txt', 'r', encoding='utf-8') as f:
            urls = [line.strip() for line in f if line.strip()][:10]  # Teste com 10 URLs
    except FileNotFoundError:
        print("❌ Arquivo urls_bellacotton_reais.txt não encontrado!")
        print("Execute: python buscar_urls_bellacotton.py")
        return
    
    print(f"📋 Testando BELLA COTTON com {len(urls)} URLs")
    print(f"🏪 Site: https://www.bellacotton.com.br")
    print(f"📦 Produtos: Fraldas, lenços umedecidos, algodão, toalhas\n")
    
    seeds = [Request(url=url, label=RouteLabel.PRODUCT, priority=5) for url in urls]
    
    # Executa
    await crawler.run(seeds)


if __name__ == "__main__":
    asyncio.run(main())
