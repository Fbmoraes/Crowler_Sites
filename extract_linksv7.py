#!/usr/bin/env python3
"""
EXTRACT LINKS V7 - Crawlee-Style Architecture
==============================================

Implementa extração de links de produtos usando padrões do Crawlee:
- RequestQueue com prioridade
- AdaptiveRateLimiter (AutoscaledPool)
- SessionPool para gerenciar cookies
- Extração inteligente de sitemaps e listagens
- Validação paralela com rate limiting

Fluxo:
  1. Busca sitemaps (XML, robots.txt)
  2. Aprende padrões de URLs de produto
  3. Filtra e valida produtos
  4. Retorna lista estruturada
"""

import asyncio
import httpx
import re
import time
from typing import List, Dict, Callable, Optional
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET


# ================================================================================================
# ADAPTIVE RATE LIMITER (AutoscaledPool)
# ================================================================================================
class AdaptiveRateLimiter:
    """Rate limiter adaptativo similar ao AutoscaledPool do Crawlee."""
    
    def __init__(self, requests_per_minute: int = 60, autoscale: bool = True):
        self.max_rpm = requests_per_minute
        self.current_rpm = requests_per_minute
        self.autoscale = autoscale
        
        # Controle de taxa
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
            
            # Remove tokens antigos (>60s)
            self.tokens = [t for t in self.tokens if now - t < 60]
            
            # Se atingiu limite, aguarda
            while len(self.tokens) >= self.current_rpm:
                await asyncio.sleep(0.1)
                now = time.time()
                self.tokens = [t for t in self.tokens if now - t < 60]
            
            # Adiciona novo token
            self.tokens.append(now)
            
            # Jitter leve
            import random
            await asyncio.sleep(random.uniform(0, 0.05))
    
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
        if not self.autoscale or self.recent_requests < 10:
            return
        
        error_rate = (self.recent_errors + self.recent_429s) / self.recent_requests
        
        if self.recent_429s > 2:
            self.current_rpm = max(20, int(self.current_rpm * 0.5))
        elif error_rate > 0.2:
            self.current_rpm = max(30, int(self.current_rpm * 0.7))
        elif error_rate < 0.05 and self.recent_429s == 0:
            self.current_rpm = min(self.max_rpm, int(self.current_rpm * 1.1))
        
        # Reset
        self.recent_requests = 0
        self.recent_errors = 0
        self.recent_429s = 0


# ================================================================================================
# EXTRAÇÃO DE SITEMAPS
# ================================================================================================
async def buscar_sitemaps(base_url: str, rate_limiter: AdaptiveRateLimiter, progress_callback: Optional[Callable] = None) -> List[str]:
    """
    Busca URLs de produtos nos sitemaps.
    Processa sitemap index recursivamente.
    """
    domain = urlparse(base_url).netloc
    urls_produto = set()
    sitemaps_para_processar = []
    
    # URLs de sitemap para testar
    sitemap_iniciais = [
        urljoin(base_url, "/sitemap.xml"),
        urljoin(base_url, "/sitemap_index.xml"),
        urljoin(base_url, "/sitemap-products.xml"),
        urljoin(base_url, "/product-sitemap.xml"),
        urljoin(base_url, "/robots.txt"),  # Pode ter referência a sitemaps
    ]
    
    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
        # Fase 1: Buscar sitemaps iniciais
        for sitemap_url in sitemap_iniciais:
            await rate_limiter.acquire()
            
            try:
                if progress_callback:
                    progress_callback(len(urls_produto), 0, sitemap_url, "coletando")
                
                response = await client.get(sitemap_url)
                
                if response.status_code == 200:
                    rate_limiter.report_success()
                    content = response.text
                    
                    # Se é robots.txt, procura por sitemaps
                    if sitemap_url.endswith('robots.txt'):
                        sitemap_refs = re.findall(r'Sitemap:\s*(.+)', content, re.IGNORECASE)
                        sitemaps_para_processar.extend([ref.strip() for ref in sitemap_refs])
                    else:
                        # Parseia XML do sitemap
                        urls, sitemaps = extrair_urls_do_sitemap(content, domain)
                        urls_produto.update(urls)
                        sitemaps_para_processar.extend(sitemaps)
                else:
                    rate_limiter.report_error()
            
            except Exception:
                rate_limiter.report_error()
        
        # Fase 2: Processar sitemaps encontrados (sitemap index)
        for sitemap_url in sitemaps_para_processar:
            await rate_limiter.acquire()
            
            try:
                if progress_callback:
                    progress_callback(len(urls_produto), 0, f"Sub-sitemap: {sitemap_url}", "coletando")
                
                response = await client.get(sitemap_url)
                
                if response.status_code == 200:
                    rate_limiter.report_success()
                    urls, _ = extrair_urls_do_sitemap(response.text, domain)
                    urls_produto.update(urls)
                else:
                    rate_limiter.report_error()
            
            except Exception:
                rate_limiter.report_error()
    
    return list(urls_produto)


def extrair_urls_do_sitemap(xml_content: str, domain: str) -> tuple[set, set]:
    """
    Extrai URLs de um sitemap XML.
    Retorna: (urls_de_produtos, urls_de_sitemaps)
    """
    urls = set()
    sitemaps = set()
    
    try:
        # Remove namespaces para facilitar parsing
        xml_clean = re.sub(r' xmlns[^>]*', '', xml_content)
        root = ET.fromstring(xml_clean)
        
        # Verifica se é sitemap index (<sitemapindex>)
        if 'sitemapindex' in root.tag.lower():
            # É um index de sitemaps - procura <sitemap><loc>
            for sitemap_elem in root.findall('.//sitemap'):
                loc = sitemap_elem.find('loc')
                if loc is not None and loc.text:
                    url = loc.text.strip()
                    if domain in url:
                        sitemaps.add(url)
        else:
            # É sitemap normal - procura <url><loc>
            for url_elem in root.findall('.//url'):
                loc = url_elem.find('loc')
                if loc is not None and loc.text:
                    url = loc.text.strip()
                    if domain in url:
                        urls.add(url)
    
    except:
        # Fallback: regex
        urls_regex = re.findall(r'<loc>(https?://[^<]+)</loc>', xml_content)
        for u in urls_regex:
            if domain in u:
                # Se contém 'sitemap' no nome, é sitemap
                if 'sitemap' in u.lower() and u.endswith('.xml'):
                    sitemaps.add(u)
                else:
                    urls.add(u)
    
    return urls, sitemaps


# ================================================================================================
# APRENDIZADO DE PADRÕES
# ================================================================================================
def aprender_padrao_urls(urls_amostra: List[str], max_amostra: int = 100) -> Optional[re.Pattern]:
    """
    Aprende padrão de URLs de produto analisando uma amostra.
    Retorna regex para filtrar produtos rapidamente.
    """
    if not urls_amostra:
        return None
    
    # Pega amostra maior e mais distribuída
    # Ignora as primeiras 20 URLs (geralmente são institucionais)
    urls_skip = urls_amostra[20:] if len(urls_amostra) > 20 else urls_amostra
    amostra = urls_skip[:max_amostra]
    
    # Analisa padrões comuns (com threshold dinâmico)
    padroes_comuns = [
        # Padrões tradicionais de e-commerce
        (r'/produtos?/[^/]+-\d+/?$', 'Gigabarato/WordPress: /produtos/nome-123/', 0.25),
        (r'/p(roduto)?/[^/]+/\d+', 'Magento/VTEX: /produto/nome/123 ou /p/nome/123', 0.5),
        (r'/[^/]+-p-\d+', 'VTEX: /nome-do-produto-p-123', 0.5),
        (r'/produto/[^/]+\.html', 'PrestaShop: /produto/nome.html', 0.5),
        (r'/[^/]+/p/\d+', 'VTEX: /categoria/p/123', 0.5),
        (r'\.com\.br/[^/]+-\d+/', 'WordPress: .com.br/produto-123/', 0.5),
        
        # Padrões para sites com estrutura profunda (MatConcasa, similares)
        # Aceita URLs com exatamente 4 segmentos: /cat1/cat2/cat3/produto-final
        (r'^https?://[^/]+/[^/]+/[^/]+/[^/]+/?$', 'Categoria nível 3 (produtos finais)', 0.15),
        # Aceita URLs com 5+ segmentos (muito específicas)
        (r'^https?://[^/]+/[^/]+/[^/]+/[^/]+/[^/]+/?', 'Categoria profunda 4+ (produtos)', 0.10),
    ]
    
    # Testa qual padrão melhor se aplica
    melhor_padrao = None
    melhor_score = 0
    melhor_nome = ''
    
    for padrao_str, nome, threshold in padroes_comuns:
        padrao = re.compile(padrao_str)
        matches = sum(1 for url in amostra if padrao.search(url))
        score = matches / len(amostra)
        
        if score >= threshold and score > melhor_score:
            melhor_score = score
            melhor_padrao = padrao
            melhor_nome = nome
    
    # Se encontrou padrão acima do threshold, retorna
    if melhor_padrao:
        return melhor_padrao
    
    return None


# ================================================================================================
# VALIDAÇÃO DE PRODUTOS
# ================================================================================================
async def validar_produto(url: str, client: httpx.AsyncClient, rate_limiter: AdaptiveRateLimiter) -> bool:
    """
    Valida se URL é realmente um produto fazendo requisição HTTP.
    Retorna True se for produto válido.
    """
    await rate_limiter.acquire()
    
    try:
        response = await client.get(url, timeout=10.0)
        
        if response.status_code == 429:
            rate_limiter.report_429()
            await asyncio.sleep(2)  # Reduzido de 5s para 2s
            return False
        
        if response.status_code != 200:
            rate_limiter.report_error()
            return False
        
        rate_limiter.report_success()
        
        # Verifica se tem indicadores de produto na página
        html = response.text.lower()
        
        indicadores_produto = [
            'application/ld+json',  # JSON-LD
            'og:type',              # Open Graph
            'product',              # Palavra produto
            'price',                # Preço
            'add to cart',          # Botão comprar
            'buy now',
            'comprar',
        ]
        
        score = sum(1 for ind in indicadores_produto if ind in html)
        
        return score >= 2  # Pelo menos 2 indicadores
    
    except:
        rate_limiter.report_error()
        return False


# ================================================================================================
# VALIDAÇÃO ADAPTATIVA INTELIGENTE
# ================================================================================================
async def validacao_adaptativa(
    urls: List[str],
    rate_limiter: AdaptiveRateLimiter,
    show_message: Callable,
    progress_callback: Optional[Callable],
    max_produtos: Optional[int] = None
) -> List[str]:
    """
    Validação adaptativa com DETECÇÃO DE PADRÃO EARLY-STOP:
    - Valida 10-20 URLs
    - Tenta detectar padrão
    - Se encontrar padrão: PARA e usa padrão no resto!
    - Se não encontrar: continua validação adaptativa
    """
    total_urls = len(urls)
    
    # Heurística: Prioriza URLs por profundidade
    # Nível 3 (4 barras): /cat1/cat2/produto - PRIORIDADE MÁXIMA (MatConcasa, etc)
    # Nível 4+ (5+ barras): /cat1/cat2/cat3/produto - PRIORIDADE ALTA
    # Nível 2 (3 barras): /categoria/produto - PRIORIDADE MÉDIA
    urls_nivel3 = [url for url in urls if url.count('/') == 4]  # /a/b/c
    urls_nivel4plus = [url for url in urls if url.count('/') >= 5]  # /a/b/c/d/e
    urls_nivel2 = [url for url in urls if url.count('/') == 3]  # /a/b
    urls_resto = [url for url in urls if url.count('/') < 3 or url.count('/') > 5]
    
    # Reordena: nível 3 primeiro, depois 4+, depois 2, depois resto
    urls_reordenadas = urls_nivel3 + urls_nivel4plus + urls_nivel2 + urls_resto
    
    if len(urls_nivel3) >= 20:
        show_message(f"🎯 Detectou {len(urls_nivel3)} URLs nível 3 (formato: /cat/sub/produto). Priorizando...")
        urls = urls_reordenadas
    elif len(urls_nivel4plus) >= 20:
        show_message(f"🎯 Detectou {len(urls_nivel4plus)} URLs profundas (4+ níveis). Priorizando...")
        urls = urls_reordenadas
    
    # FASE 1: Valida APENAS 20 URLs e tenta detectar padrão
    amostra_minima = 20
    show_message(f"🔍 Validando {amostra_minima} URLs e procurando padrão...")
    
    urls_validas = []
    
    async with httpx.AsyncClient(
        headers={'User-Agent': 'Mozilla/5.0'},
        timeout=10.0,
        follow_redirects=True
    ) as client:
        
        # Valida primeira amostra mínima
        for i, url in enumerate(urls[:amostra_minima]):
            if progress_callback:
                progress_callback(i + 1, amostra_minima, "", "validando")
            
            if await validar_produto(url, client, rate_limiter):
                urls_validas.append(url)
        
        # TENTA DETECTAR PADRÃO logo após 20 validações
        if len(urls_validas) >= 10:  # Precisa de pelo menos 10 válidas
            show_message(f"🧠 Tentando detectar padrão com {len(urls_validas)} URLs válidas...")
            padrao = aprender_padrao_urls(urls_validas, max_amostra=len(urls_validas))
            
            if padrao:
                # 🎉 ACHOU PADRÃO! Para de validar e usa padrão no resto!
                show_message(f"✅ PADRÃO DETECTADO: {padrao.pattern}")
                show_message(f"🚀 Aplicando padrão no resto (SEM validação HTTP)!")
                
                # Aplica padrão em TODAS as URLs restantes (sem HTTP)
                urls_com_padrao = [url for url in urls[amostra_minima:] if padrao.search(url)]
                urls_validas.extend(urls_com_padrao)
                
                if max_produtos and len(urls_validas) > max_produtos:
                    urls_validas = urls_validas[:max_produtos]
                
                show_message(f"✅ Total: {len(urls_validas)} produtos (padrão aplicado em {len(urls_com_padrao)})")
                return urls_validas
        
        # Se não achou padrão, continua validação adaptativa
        show_message(f"⚠️ Padrão não detectado. Continuando validação adaptativa...")
        
        # FASE 2: Valida mais 30 URLs (total 50)
        amostra_extra = 30
        for i, url in enumerate(urls[amostra_minima:amostra_minima + amostra_extra]):
            if progress_callback:
                progress_callback(amostra_minima + i + 1, amostra_minima + amostra_extra, "", "validando")
            
            if await validar_produto(url, client, rate_limiter):
                urls_validas.append(url)
        
        taxa_sucesso = len(urls_validas) / (amostra_minima + amostra_extra)
        show_message(f"📊 Taxa de sucesso: {taxa_sucesso*100:.1f}% ({len(urls_validas)}/{amostra_minima + amostra_extra})")
        
        # Decisão inteligente
        if taxa_sucesso >= 0.80:
            # Alta taxa = assume que resto é válido
            show_message(f"✅ Alta taxa! Assumindo resto como válido")
            urls_validas.extend(urls[amostra_minima + amostra_extra:max_produtos] if max_produtos else urls[amostra_minima + amostra_extra:])
        
        elif taxa_sucesso >= 0.50:
            # Taxa média = valida mais 100 URLs
            show_message(f"⚠️ Taxa média. Validando mais 100 URLs...")
            amostra_adicional = 100
            
            for i, url in enumerate(urls[amostra_minima + amostra_extra:amostra_minima + amostra_extra + amostra_adicional]):
                if progress_callback:
                    progress_callback(amostra_minima + amostra_extra + i + 1, amostra_minima + amostra_extra + amostra_adicional, "", "validando")
                
                if await validar_produto(url, client, rate_limiter):
                    urls_validas.append(url)
            
            # Recalcula taxa
            taxa_final = len(urls_validas) / (amostra_minima + amostra_extra + amostra_adicional)
            show_message(f"📊 Taxa final: {taxa_final*100:.1f}%")
            
            if taxa_final >= 0.70:
                show_message(f"✅ Taxa aceitável. Assumindo resto como válido")
                urls_validas.extend(urls[amostra_minima + amostra_extra + amostra_adicional:max_produtos] if max_produtos else urls[amostra_minima + amostra_extra + amostra_adicional:])
        
        else:
            # Taxa baixa < 50% = valida até 500
            show_message(f"❌ Taxa baixa! Validando até 500 URLs...")
            limite = min(500, len(urls)) if not max_produtos else min(max_produtos, len(urls))
            
            for i, url in enumerate(urls[amostra_minima + amostra_extra:limite]):
                if progress_callback:
                    progress_callback(amostra_minima + amostra_extra + i + 1, limite, "", "validando")
                
                if await validar_produto(url, client, rate_limiter):
                    urls_validas.append(url)
    
    show_message(f"✅ Validação concluída: {len(urls_validas)} produtos de {total_urls} URLs")
    return urls_validas


# ================================================================================================
# FUNÇÃO PRINCIPAL
# ================================================================================================
async def extrair_produtos_async(
    base_url: str,
    show_message: Callable,
    max_produtos: Optional[int] = None,
    progress_callback: Optional[Callable] = None
) -> List[Dict]:
    """
    Extrai produtos usando arquitetura Crawlee.
    
    Args:
        base_url: URL base do site
        show_message: Função para exibir mensagens
        max_produtos: Limite de produtos (None = sem limite)
        progress_callback: Callback de progresso
    
    Returns:
        Lista de dicionários com {nome, url}
    """
    show_message("🚀 Iniciando extração Crawlee-style...")
    
    # Rate limiter adaptativo - AUMENTADO para 300 RPM (validação rápida)
    rate_limiter = AdaptiveRateLimiter(requests_per_minute=300, autoscale=True)
    
    # 1. Busca sitemaps
    show_message("📋 Buscando sitemaps...")
    urls_sitemap = await buscar_sitemaps(base_url, rate_limiter, progress_callback)
    
    if not urls_sitemap:
        show_message("⚠️ Nenhum sitemap encontrado")
        return []
    
    show_message(f"✅ Encontrou {len(urls_sitemap)} URLs no sitemap")
    
    # 2. Aprende padrão de URLs
    if progress_callback:
        progress_callback(0, min(100, len(urls_sitemap)), "", "fase_aprendizado")
    
    show_message("🧠 Aprendendo padrões de URLs...")
    padrao = aprender_padrao_urls(urls_sitemap, max_amostra=100)
    
    if padrao:
        show_message(f"✅ Padrão identificado: {padrao.pattern}")
        
        # Filtra URLs usando padrão (sem HTTP)
        urls_filtradas = []
        for i, url in enumerate(urls_sitemap):
            if progress_callback:
                progress_callback(i + 1, len(urls_sitemap), "", "aplicando_padrao")
            
            if padrao.search(url):
                urls_filtradas.append(url)
                
                if max_produtos and len(urls_filtradas) >= max_produtos:
                    break
        
        show_message(f"✅ Filtrou {len(urls_filtradas)} produtos usando padrão")
    else:
        show_message("⚠️ Padrão não identificado, validando amostra adaptativa...")
        # Validação adaptativa inteligente
        urls_filtradas = await validacao_adaptativa(
            urls_sitemap, 
            rate_limiter, 
            show_message, 
            progress_callback,
            max_produtos
        )
    
    # 3. Validação (se necessário)
    produtos = []
    
    if padrao and len(urls_filtradas) >= 10:
        # Padrão confiável, não precisa validar
        show_message(f"✅ Usando padrão confiável, sem validação HTTP")
        
        for url in urls_filtradas:
            nome = url.split('/')[-2].replace('-', ' ').title()
            if not nome or len(nome) < 3:
                nome = url.split('/')[-1].replace('-', ' ').title()
            
            produtos.append({
                'nome': nome,
                'url': url
            })
    else:
        # Precisa validar com HTTP
        show_message(f"🔍 Validando {len(urls_filtradas)} URLs com HTTP...")
        
        async with httpx.AsyncClient(follow_redirects=True) as client:
            for i, url in enumerate(urls_filtradas):
                if progress_callback:
                    progress_callback(i + 1, len(urls_filtradas), "", "validando")
                
                if await validar_produto(url, client, rate_limiter):
                    # Extrai nome da URL
                    nome = url.split('/')[-2].replace('-', ' ').title()
                    if not nome or len(nome) < 3:
                        nome = url.split('/')[-1].replace('-', ' ').title()
                    
                    produtos.append({
                        'nome': nome,
                        'url': url
                    })
                    
                    if progress_callback:
                        progress_callback(len(produtos), 0, "", "produto_validado")
                    
                    if max_produtos and len(produtos) >= max_produtos:
                        break
    
    show_message(f"✅ Extração concluída: {len(produtos)} produtos")
    
    return produtos


def extrair_produtos_rapido(
    base_url: str,
    show_message: Callable,
    max_produtos: Optional[int] = None,
    progress_callback: Optional[Callable] = None
) -> List[Dict]:
    """
    Wrapper síncrono para extrair_produtos_async.
    Compatível com a interface do appv4.py.
    """
    return asyncio.run(extrair_produtos_async(
        base_url, 
        show_message, 
        max_produtos, 
        progress_callback
    ))


# ================================================================================================
# TESTE
# ================================================================================================
if __name__ == "__main__":
    def dummy_message(msg):
        print(f"[INFO] {msg}")
    
    def dummy_progress(atual, total, info, tipo):
        if tipo == "coletando":
            print(f"[SITEMAP] {info}")
        elif tipo == "aplicando_padrao":
            print(f"[FILTRO] {atual}/{total}")
        elif tipo == "validando":
            print(f"[VALIDAÇÃO] {atual}/{total}")
        elif tipo == "produto_validado":
            print(f"[PRODUTOS] {atual}")
    
    # Teste com Bella Cotton
    produtos = extrair_produtos_rapido(
        "https://www.bellacotton.com.br",
        dummy_message,
        max_produtos=20,
        progress_callback=dummy_progress
    )
    
    print(f"\n✅ {len(produtos)} produtos extraídos:")
    for p in produtos[:5]:
        print(f"  - {p['nome']}")
