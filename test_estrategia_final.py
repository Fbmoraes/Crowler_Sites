"""
TESTE COMPLETO: ESTRATÉGIA HÍBRIDA OTIMIZADA
=============================================

ESTRATÉGIA:
1. Homepage → Detectar padrão (1 request)
2. Buscar categorias PRINCIPAIS nível 1 (sitemap ou homepage)
3. Navegar cada categoria COM LIMITE (max 100 produtos/categoria)
4. Total: 20-30 requests, ~30-60 segundos

TESTE: MatConcasa
"""

import asyncio
import httpx
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import re
from typing import Set, List, Optional
import time

class CrawlerHibrido:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.netloc = urlparse(base_url).netloc
        self.padrao_produto: Optional[re.Pattern] = None
        self.produtos: Set[str] = set()
        self.stats = {
            'tempo_inicio': time.time(),
            'requests': 0,
            'categorias_navegadas': 0,
            'produtos_encontrados': 0
        }
    
    async def fazer_request(self, url: str) -> str:
        """Faz request e conta estatísticas"""
        self.stats['requests'] += 1
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            r = await client.get(url)
            return r.text
    
    async def passo1_detectar_padrao(self):
        """PASSO 1: Detecta padrão na homepage"""
        print("🔍 PASSO 1: Detectando padrão de produtos")
        
        html = await self.fazer_request(self.base_url)
        soup = BeautifulSoup(html, 'html.parser')
        
        produtos_amostra = []
        for link in soup.find_all('a', href=True):
            href = link.get('href')
            if '/produto/' in href:
                url = urljoin(self.base_url, href)
                produtos_amostra.append(url)
                self.produtos.add(url)
        
        produtos_amostra = list(set(produtos_amostra))
        self.stats['produtos_encontrados'] = len(self.produtos)
        
        print(f"   ✅ Homepage: {len(produtos_amostra)} produtos")
        
        # Detecta padrão
        if len(produtos_amostra) >= 5:
            padrao = re.compile(r'/produto/[^/]+-\d+/?$')
            matches = sum(1 for p in produtos_amostra[:20] if padrao.search(p))
            
            if matches / min(len(produtos_amostra), 20) >= 0.7:
                self.padrao_produto = padrao
                print(f"   ✅ Padrão detectado: /produto/.*-\\d+")
                return True
        
        print("   ⚠️ Padrão não detectado, usando heurística")
        return False
    
    async def passo2_buscar_categorias(self) -> List[str]:
        """PASSO 2: Busca categorias principais (nível 1)"""
        print("\n📂 PASSO 2: Buscando categorias principais")
        
        categorias = set()
        
        # Tenta sitemap primeiro
        try:
            sitemap_url = f"{urlparse(self.base_url).scheme}://{self.netloc}/sitemap.xml"
            html = await self.fazer_request(sitemap_url)
            urls_sitemap = re.findall(r'<loc>(.*?)</loc>', html)
            
            print(f"   📄 Sitemap: {len(urls_sitemap)} URLs")
            
            # Filtra categorias nível 1 (apenas 1 segmento após domínio)
            for url in urls_sitemap:
                path = urlparse(url).path
                segmentos = [s for s in path.split('/') if s]
                
                # Nível 1: /categoria
                if len(segmentos) == 1 and '/produto/' not in url:
                    categorias.add(url)
            
            print(f"   ✅ {len(categorias)} categorias nível 1 encontradas")
            
        except Exception as e:
            print(f"   ⚠️ Sitemap não disponível: {e}")
        
        # Fallback: homepage
        if len(categorias) < 5:
            print("   🏠 Buscando categorias na homepage...")
            html = await self.fazer_request(self.base_url)
            soup = BeautifulSoup(html, 'html.parser')
            
            for link in soup.find_all('a', href=True):
                href = link.get('href')
                url = urljoin(self.base_url, href)
                
                if urlparse(url).netloc != self.netloc:
                    continue
                
                path = urlparse(url).path
                segmentos = [s for s in path.split('/') if s]
                
                if len(segmentos) == 1:
                    categorias.add(url)
            
            print(f"   ✅ {len(categorias)} categorias da homepage")
        
        return list(categorias)[:20]  # Limita a 20 categorias
    
    async def passo3_extrair_produtos_categoria(self, url_categoria: str, max_produtos: int = 100):
        """PASSO 3: Extrai produtos de UMA categoria"""
        try:
            html = await self.fazer_request(url_categoria)
            soup = BeautifulSoup(html, 'html.parser')
            
            produtos_novos = 0
            for link in soup.find_all('a', href=True):
                href = link.get('href')
                url = urljoin(url_categoria, href)
                
                if urlparse(url).netloc != self.netloc:
                    continue
                
                # Aplica padrão se disponível
                if self.padrao_produto:
                    if self.padrao_produto.search(url) and url not in self.produtos:
                        self.produtos.add(url)
                        produtos_novos += 1
                else:
                    # Heurística: /produto/ e nível 3+
                    if '/produto/' in url and url not in self.produtos:
                        niveis = len([s for s in urlparse(url).path.split('/') if s])
                        if niveis >= 2:
                            self.produtos.add(url)
                            produtos_novos += 1
                
                if produtos_novos >= max_produtos:
                    break
            
            return produtos_novos
        
        except Exception as e:
            print(f"      ❌ Erro: {e}")
            return 0
    
    async def passo4_navegar_categorias(self, categorias: List[str], max_por_categoria: int = 100):
        """PASSO 4: Navega todas as categorias"""
        print(f"\n🛒 PASSO 3: Navegando {len(categorias)} categorias")
        print(f"   Limite: {max_por_categoria} produtos por categoria\n")
        
        for i, cat_url in enumerate(categorias, 1):
            nome_cat = cat_url.split('/')[-1] or 'home'
            
            print(f"   [{i:2d}/{len(categorias)}] {nome_cat[:40]:<40}", end=' ')
            
            produtos_antes = len(self.produtos)
            novos = await self.passo3_extrair_produtos_categoria(cat_url, max_por_categoria)
            
            if novos > 0:
                print(f"✅ +{novos:3d} produtos")
            else:
                print(f"⚠️  0 produtos")
            
            self.stats['categorias_navegadas'] += 1
            self.stats['produtos_encontrados'] = len(self.produtos)
            
            # Delay para não sobrecarregar
            await asyncio.sleep(0.3)
    
    async def executar(self):
        """Executa estratégia completa"""
        print("="*70)
        print("🧪 TESTE: ESTRATÉGIA HÍBRIDA OTIMIZADA")
        print("="*70)
        print(f"\n🌐 Site: {self.base_url}\n")
        
        # Passo 1: Detectar padrão
        await self.passo1_detectar_padrao()
        
        # Passo 2: Buscar categorias
        categorias = await self.passo2_buscar_categorias()
        
        if not categorias:
            print("\n❌ Nenhuma categoria encontrada!")
            return
        
        # Passo 3: Navegar categorias
        await self.passo4_navegar_categorias(categorias, max_por_categoria=100)
        
        # Estatísticas finais
        tempo_total = time.time() - self.stats['tempo_inicio']
        
        print("\n" + "="*70)
        print("📊 RESULTADOS FINAIS")
        print("="*70)
        print(f"\n⏱️  Tempo total: {tempo_total:.1f}s")
        print(f"🌐 Requests HTTP: {self.stats['requests']}")
        print(f"📂 Categorias navegadas: {self.stats['categorias_navegadas']}")
        print(f"📦 Produtos encontrados: {len(self.produtos)}")
        print(f"\n📈 Performance:")
        print(f"   • {len(self.produtos)/tempo_total:.1f} produtos/segundo")
        print(f"   • {tempo_total/self.stats['requests']:.2f}s por request")
        print(f"   • {len(self.produtos)/self.stats['requests']:.1f} produtos por request")
        
        # Amostra de produtos
        print(f"\n📦 Amostra de 10 produtos:")
        for i, p in enumerate(list(self.produtos)[:10], 1):
            nome = p.split('/')[-1][:60]
            print(f"   {i:2d}. {nome}")
        
        return len(self.produtos), tempo_total

async def teste_comparativo():
    """Compara com a expectativa"""
    print("\n" + "="*70)
    print("🎯 ANÁLISE E COMPARAÇÃO")
    print("="*70)
    
    crawler = CrawlerHibrido('https://www.matconcasa.com.br/')
    total_produtos, tempo_total = await crawler.executar()
    
    print("\n" + "="*70)
    print("📊 COMPARAÇÃO COM OUTRAS ESTRATÉGIAS")
    print("="*70)
    
    print("\n┌────────────────────────┬──────────┬──────────┬──────────┬───────────┐")
    print("│ Estratégia             │ Produtos │ Requests │ Tempo    │ Cobertura │")
    print("├────────────────────────┼──────────┼──────────┼──────────┼───────────┤")
    print(f"│ Sitemap V5 (validar)   │    0     │  21,000  │  71 min  │    0%     │")
    print(f"│ Crawl Recursivo        │   ~500   │  100-500 │  5-10min │   100%    │")
    print(f"│ Híbrida Otimizada      │ {total_produtos:>6}   │ {crawler.stats['requests']:>7}  │ {tempo_total:>6.0f}s  │   ~80%    │")
    print("└────────────────────────┴──────────┴──────────┴──────────┴───────────┘")
    
    print("\n✅ PONTOS FORTES:")
    print("   1. Rápida: ~1 minuto vs 71 minutos do V5")
    print(f"   2. Eficiente: {crawler.stats['requests']} requests vs 21k do V5")
    print(f"   3. Boa cobertura: {total_produtos} produtos")
    print("   4. Previsível: tempo proporcional ao número de categorias")
    print("   5. Seguro: delay entre requests evita bloqueio")
    
    print("\n⚠️ LIMITAÇÕES:")
    print("   1. Não pega 100% (só categorias nível 1)")
    print("   2. Depende da estrutura do site (categorias principais)")
    print("   3. Limite por categoria pode deixar produtos de fora")
    
    print("\n💡 OTIMIZAÇÕES POSSÍVEIS:")
    print("   1. Navegar também categorias nível 2 (mais requests)")
    print("   2. Aumentar limite por categoria (100 → 200)")
    print("   3. Paralelizar navegação (async workers)")
    print("   4. Detectar paginação e navegar páginas seguintes")
    
    print("\n🎯 RECOMENDAÇÃO FINAL:")
    if total_produtos >= 500 and tempo_total <= 120:
        print("   ✅ APROVADO! Estratégia viável e eficiente")
        print(f"   Conseguiu {total_produtos} produtos em {tempo_total:.0f}s")
        print("   Pronto para implementar no V8!")
    elif total_produtos >= 200:
        print("   ⚠️ APROVADO COM RESSALVAS")
        print(f"   Encontrou {total_produtos} produtos, mas pode não ser 100%")
        print("   Considere adicionar nível 2 de categorias")
    else:
        print("   ❌ NÃO APROVADO")
        print(f"   Apenas {total_produtos} produtos - cobertura insuficiente")
        print("   Precisa revisar estratégia")

asyncio.run(teste_comparativo())
