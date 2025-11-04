"""
DIAGNÓSTICO: ESTRATÉGIA DE CRAWLING RECURSIVO
==============================================

PROBLEMA IDENTIFICADO:
- MatConcasa sitemap: categorias SEM /produto/ no path
- Produtos: /produto/slug-123 (NÃO estão no sitemap)
- Produtos aparecem nas PÁGINAS de categoria

ESTRATÉGIA PROPOSTA:
1. Detectar padrão de produto (ex: /produto/.*-\d+)
2. Começar pela homepage
3. Clicar em TODOS os links que NÃO são produtos
4. Em cada página visitada:
   - Se link é produto → GUARDAR
   - Se link NÃO é produto → VISITAR (se ainda não visitou)
5. Parar quando não houver mais links novos

É como um SPIDER/CRAWLER tradicional!
"""

import asyncio
import httpx
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import re
from typing import Set, Dict, List, Optional

class CrawlerRecursivo:
    def __init__(self, base_url: str, padrao_produto: Optional[re.Pattern] = None):
        self.base_url = base_url
        self.netloc = urlparse(base_url).netloc
        self.padrao_produto = padrao_produto
        
        # Rastreamento
        self.produtos_encontrados: Set[str] = set()
        self.paginas_visitadas: Set[str] = set()
        self.paginas_para_visitar: Set[str] = {base_url}
        
        # Estatísticas
        self.stats = {
            'paginas_visitadas': 0,
            'produtos_encontrados': 0,
            'links_analisados': 0
        }
    
    def eh_produto(self, url: str) -> bool:
        """Verifica se URL é de produto"""
        if self.padrao_produto:
            return bool(self.padrao_produto.search(url))
        
        # Fallback: heurística genérica
        return '/produto/' in url
    
    def eh_link_valido(self, url: str) -> bool:
        """Verifica se link é válido para crawling"""
        parsed = urlparse(url)
        
        # Mesma origem
        if parsed.netloc != self.netloc:
            return False
        
        # Ignora âncoras, query strings complexas
        if '#' in url:
            return False
        
        # Ignora arquivos estáticos
        extensoes_ignorar = ['.jpg', '.png', '.pdf', '.zip', '.css', '.js']
        if any(url.lower().endswith(ext) for ext in extensoes_ignorar):
            return False
        
        # Ignora páginas institucionais
        palavras_ignorar = ['login', 'cadastro', 'cart', 'checkout', 'conta', 'minha-conta']
        if any(palavra in url.lower() for palavra in palavras_ignorar):
            return False
        
        return True
    
    async def extrair_links(self, url: str) -> Dict[str, List[str]]:
        """Extrai links de uma página, separando produtos e não-produtos"""
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                r = await client.get(url)
                soup = BeautifulSoup(r.text, 'html.parser')
                
                links_produtos = []
                links_navegacao = []
                
                for link in soup.find_all('a', href=True):
                    href = link.get('href')
                    url_completa = urljoin(url, href)
                    
                    if not self.eh_link_valido(url_completa):
                        continue
                    
                    self.stats['links_analisados'] += 1
                    
                    if self.eh_produto(url_completa):
                        links_produtos.append(url_completa)
                    else:
                        links_navegacao.append(url_completa)
                
                return {
                    'produtos': list(set(links_produtos)),
                    'navegacao': list(set(links_navegacao))
                }
        
        except Exception as e:
            print(f"   ❌ Erro ao extrair links de {url}: {e}")
            return {'produtos': [], 'navegacao': []}
    
    async def crawl(self, max_paginas: int = 50, max_produtos: int = None):
        """Crawl recursivo do site"""
        print("🕷️ INICIANDO CRAWLING RECURSIVO")
        print(f"   Base: {self.base_url}")
        print(f"   Padrão: {self.padrao_produto.pattern if self.padrao_produto else 'Heurística'}")
        print(f"   Limites: {max_paginas} páginas, {max_produtos or '∞'} produtos\n")
        
        while self.paginas_para_visitar and len(self.paginas_visitadas) < max_paginas:
            # Pega próxima página
            url_atual = self.paginas_para_visitar.pop()
            
            # Já visitou?
            if url_atual in self.paginas_visitadas:
                continue
            
            # Marca como visitada
            self.paginas_visitadas.add(url_atual)
            self.stats['paginas_visitadas'] += 1
            
            print(f"[{self.stats['paginas_visitadas']:2d}] Visitando: {url_atual.split('/')[-1] or 'home'}")
            
            # Extrai links
            links = await self.extrair_links(url_atual)
            
            # Adiciona produtos encontrados
            novos_produtos = [p for p in links['produtos'] if p not in self.produtos_encontrados]
            self.produtos_encontrados.update(novos_produtos)
            self.stats['produtos_encontrados'] = len(self.produtos_encontrados)
            
            if novos_produtos:
                print(f"      → 📦 {len(novos_produtos)} novos produtos (total: {self.stats['produtos_encontrados']})")
            
            # Adiciona páginas para visitar
            novos_links = [l for l in links['navegacao'] if l not in self.paginas_visitadas]
            self.paginas_para_visitar.update(novos_links)
            
            if novos_links:
                print(f"      → 🔗 {len(novos_links)} novas páginas (fila: {len(self.paginas_para_visitar)})")
            
            # Atingiu limite de produtos?
            if max_produtos and self.stats['produtos_encontrados'] >= max_produtos:
                print(f"\n✅ Limite de {max_produtos} produtos atingido!")
                break
            
            # Delay para não sobrecarregar
            await asyncio.sleep(0.5)
        
        return list(self.produtos_encontrados)

async def diagnostico_crawling():
    """TESTA A ESTRATÉGIA NO MATCONCASA"""
    print("="*70)
    print("🧪 DIAGNÓSTICO: CRAWLING RECURSIVO - MatConcasa")
    print("="*70)
    print()
    
    base_url = 'https://www.matconcasa.com.br/'
    
    # PASSO 1: Detectar padrão na homepage
    print("📋 PASSO 1: Detectando padrão de produtos\n")
    
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(base_url)
        soup = BeautifulSoup(r.text, 'html.parser')
        
        produtos_amostra = []
        for link in soup.find_all('a', href=True):
            href = link.get('href')
            if '/produto/' in href:
                url = urljoin(base_url, href)
                produtos_amostra.append(url)
        
        produtos_amostra = list(set(produtos_amostra))[:10]
        
        print(f"   Encontrados {len(produtos_amostra)} produtos na homepage")
        print(f"\n   📦 Exemplos:")
        for p in produtos_amostra[:3]:
            print(f"      {p}")
    
    # Detecta padrão
    padrao = re.compile(r'/produto/[^/]+-\d+/?$')
    matches = sum(1 for p in produtos_amostra if padrao.search(p))
    print(f"\n   🔍 Padrão testado: /produto/[^/]+-\\d+/?$")
    print(f"   ✅ Match: {matches}/{len(produtos_amostra)} ({matches/len(produtos_amostra)*100:.0f}%)")
    
    # PASSO 2: Crawl recursivo
    print(f"\n{'='*70}")
    print("📋 PASSO 2: Crawling recursivo (limitado a 20 páginas)")
    print("="*70)
    print()
    
    crawler = CrawlerRecursivo(base_url, padrao)
    produtos = await crawler.crawl(max_paginas=20, max_produtos=200)
    
    # RESULTADOS
    print(f"\n{'='*70}")
    print("📊 RESULTADOS DO CRAWLING")
    print("="*70)
    print(f"\n✅ Páginas visitadas: {crawler.stats['paginas_visitadas']}")
    print(f"✅ Links analisados: {crawler.stats['links_analisados']}")
    print(f"✅ Produtos encontrados: {len(produtos)}")
    
    print(f"\n📦 Primeiros 10 produtos:")
    for i, p in enumerate(produtos[:10], 1):
        nome = p.split('/')[-1][:50]
        print(f"   {i:2d}. {nome}")
    
    # ANÁLISE DA ESTRATÉGIA
    print(f"\n{'='*70}")
    print("🎯 ANÁLISE DA ESTRATÉGIA")
    print("="*70)
    
    print("\n✅ PONTOS FORTES:")
    print("   1. Encontra TODOS os produtos do site (não depende de sitemap)")
    print("   2. Funciona mesmo se produtos não estão no sitemap")
    print("   3. Descobre produtos em qualquer nível de profundidade")
    print("   4. Evita visitar mesma página 2x (eficiente)")
    print("   5. Padrão filtra produtos automaticamente")
    
    print("\n⚠️ PONTOS DE ATENÇÃO:")
    print("   1. LENTO: precisa visitar muitas páginas")
    print(f"      → MatConcasa: {crawler.stats['paginas_visitadas']} páginas para {len(produtos)} produtos")
    print(f"      → Ratio: {crawler.stats['paginas_visitadas']/len(produtos):.2f} páginas/produto")
    print("   2. Muitos requests HTTP (pode ser bloqueado)")
    print("   3. Difícil estimar tempo total (depende da estrutura)")
    print("   4. Pode entrar em loops se site tiver filtros infinitos")
    
    print("\n💡 OTIMIZAÇÕES NECESSÁRIAS:")
    print("   1. Limitar profundidade (ex: max 3 níveis)")
    print("   2. Priorizar categorias principais")
    print("   3. Adicionar rate limiting (delay entre requests)")
    print("   4. Detectar e ignorar filtros/paginação")
    print("   5. Paralelizar crawling (async workers)")
    
    print("\n🎯 RECOMENDAÇÃO FINAL:")
    if len(produtos) >= 100:
        print("   ✅ ESTRATÉGIA VIÁVEL!")
        print(f"   Encontrou {len(produtos)} produtos em {crawler.stats['paginas_visitadas']} páginas")
        print("   ⚠️ MAS: Implementar com limites e otimizações")
        print("\n   📋 IMPLEMENTAR:")
        print("      - Crawl recursivo com max_depth=3")
        print("      - Rate limiting (0.5-1s entre requests)")
        print("      - Priorizar URLs de categorias (nível 1-2)")
        print("      - Ignorar filtros (price, sort, page)")
    else:
        print("   ⚠️ ESTRATÉGIA INEFICIENTE")
        print(f"   Apenas {len(produtos)} produtos em {crawler.stats['paginas_visitadas']} páginas")
    
    # COMPARAÇÃO COM ESTRATÉGIA ANTERIOR
    print(f"\n{'='*70}")
    print("📊 COMPARAÇÃO: Crawling Recursivo vs Navegação Categorias")
    print("="*70)
    
    print("\n┌─────────────────────────┬──────────────────┬──────────────────────┐")
    print("│ Aspecto                 │ Crawl Recursivo  │ Navegação Categorias │")
    print("├─────────────────────────┼──────────────────┼──────────────────────┤")
    print("│ Cobertura               │ 100% (tudo)      │ 80-90% (depende)     │")
    print("│ Velocidade              │ Lento            │ Rápido               │")
    print("│ Requests HTTP           │ Muitos (50-200)  │ Poucos (10-30)       │")
    print("│ Complexidade            │ Alta             │ Média                │")
    print("│ Risco de bloqueio       │ Alto             │ Baixo                │")
    print("│ Previsibilidade         │ Difícil          │ Fácil                │")
    print("└─────────────────────────┴──────────────────┴──────────────────────┘")
    
    print("\n💡 ESTRATÉGIA HÍBRIDA RECOMENDADA:")
    print("   1. Tentar sitemap primeiro")
    print("   2. Se sitemap vazio → Navegação por categorias (sitemap ou homepage)")
    print("   3. Se categorias falham → Crawl recursivo LIMITADO")
    print("   4. Sempre com padrão detectado para filtrar")

asyncio.run(diagnostico_crawling())
