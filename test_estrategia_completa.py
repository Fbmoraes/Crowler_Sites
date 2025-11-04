"""
DIAGNÓSTICO DA ESTRATÉGIA PROPOSTA
===================================

FLUXO:
1. Tenta extrair produtos da HOMEPAGE
2. Se encontrou produtos → detecta PADRÃO nas URLs
3. Se NÃO encontrou → navega CATEGORIAS para encontrar produtos
4. Com produtos de categorias → detecta PADRÃO
5. Com padrão detectado → aplica em TODAS URLs do sitemap/categorias

VANTAGENS:
- Rápido: começa pela homepage (1 request)
- Inteligente: aprende o padrão com poucos exemplos
- Completo: se homepage falhar, usa categorias
- Escalável: padrão aplicado a todas URLs sem validar 1 por 1

CASOS DE USO:
"""

import asyncio
import httpx
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from typing import List, Set, Optional, Dict

async def passo1_homepage(base_url: str) -> List[str]:
    """PASSO 1: Extrai produtos da homepage"""
    print("\n🏠 PASSO 1: Tentando extrair produtos da HOMEPAGE")
    produtos = set()
    
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(base_url, follow_redirects=True)
            soup = BeautifulSoup(r.text, 'html.parser')
            
            for link in soup.find_all('a', href=True):
                href = link.get('href')
                url = urljoin(base_url, href)
                
                if urlparse(url).netloc != urlparse(base_url).netloc:
                    continue
                
                # Detecta produtos (ajustar heurística por site)
                if '/produto/' in url:
                    produtos.add(url)
            
            print(f"   ✅ {len(produtos)} produtos na homepage")
            return list(produtos)
    except Exception as e:
        print(f"   ❌ Erro: {e}")
        return []

def passo2_detectar_padrao(urls: List[str]) -> Optional[re.Pattern]:
    """PASSO 2: Detecta padrão nas URLs de produtos"""
    print(f"\n🔍 PASSO 2: Detectando PADRÃO em {len(urls)} URLs")
    
    if len(urls) < 5:
        print("   ⚠️ Poucas URLs para detectar padrão")
        return None
    
    # Padrões conhecidos
    padroes_teste = [
        (r'/produto/[^/]+-\d+/?$', 'WordPress: /produto/slug-123'),
        (r'/produto/[^/]+/?$', 'Genérico: /produto/slug'),
        (r'/p/[^/]+/\d+', 'VTEX: /p/slug/123'),
        (r'/[^/]+/[^/]+-\d+/?$', 'Nível 2: /cat/produto-123'),
    ]
    
    for padrao_str, descricao in padroes_teste:
        padrao = re.compile(padrao_str)
        matches = sum(1 for url in urls if padrao.search(url))
        percentual = (matches / len(urls)) * 100
        
        print(f"   Testando: {descricao}")
        print(f"   → {matches}/{len(urls)} matches ({percentual:.1f}%)")
        
        if percentual >= 70:  # 70% threshold
            print(f"   ✅ PADRÃO DETECTADO: {descricao}")
            return padrao
    
    print("   ⚠️ Nenhum padrão com >70% match")
    return None

async def passo3_buscar_categorias(base_url: str, sitemap_urls: List[str] = None) -> List[str]:
    """PASSO 3: Busca categorias (sitemap ou homepage)"""
    print("\n📂 PASSO 3: Buscando CATEGORIAS")
    
    categorias = set()
    
    # Opção A: Do sitemap
    if sitemap_urls:
        print(f"   Analisando {len(sitemap_urls)} URLs do sitemap...")
        for url in sitemap_urls:
            niveis = len([p for p in urlparse(url).path.split('/') if p])
            # Categorias geralmente tem 1-2 níveis
            if 1 <= niveis <= 2 and '/produto/' not in url:
                categorias.add(url)
        print(f"   ✅ {len(categorias)} categorias do sitemap")
    
    # Opção B: Da homepage
    if len(categorias) < 5:
        print("   Buscando categorias na homepage...")
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                r = await client.get(base_url, follow_redirects=True)
                soup = BeautifulSoup(r.text, 'html.parser')
                
                for link in soup.find_all('a', href=True):
                    texto = link.get_text(strip=True)
                    href = link.get('href')
                    
                    if not texto or len(texto) < 3:
                        continue
                    
                    if any(x in texto.lower() for x in ['contato', 'sobre', 'login', 'cart']):
                        continue
                    
                    url = urljoin(base_url, href)
                    
                    if urlparse(url).netloc != urlparse(base_url).netloc:
                        continue
                    
                    niveis = len([p for p in urlparse(url).path.split('/') if p])
                    if 1 <= niveis <= 2:
                        categorias.add(url)
                
                print(f"   ✅ {len(categorias)} categorias da homepage")
        except Exception as e:
            print(f"   ❌ Erro: {e}")
    
    return list(categorias)[:20]  # Limita a 20 categorias

async def passo4_produtos_categorias(categorias: List[str], max_por_cat: int = 10) -> List[str]:
    """PASSO 4: Extrai produtos das categorias"""
    print(f"\n🛒 PASSO 4: Extraindo produtos de {len(categorias)} categorias")
    
    todos_produtos = set()
    
    for i, cat_url in enumerate(categorias[:10], 1):  # Limita a 10 categorias
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                r = await client.get(cat_url, follow_redirects=True)
                soup = BeautifulSoup(r.text, 'html.parser')
                
                produtos_cat = []
                for link in soup.find_all('a', href=True):
                    href = link.get('href')
                    url = urljoin(cat_url, href)
                    
                    if urlparse(url).netloc != urlparse(cat_url).netloc:
                        continue
                    
                    # Heurística: produto tem mais níveis que categoria
                    niveis = len([p for p in urlparse(url).path.split('/') if p])
                    if niveis >= 3 or '/produto/' in url:
                        produtos_cat.append(url)
                        if len(produtos_cat) >= max_por_cat:
                            break
                
                if produtos_cat:
                    print(f"   [{i}] {len(produtos_cat)} produtos → {cat_url.split('/')[-1] or 'home'}")
                    todos_produtos.update(produtos_cat)
                
        except Exception as e:
            print(f"   [{i}] ❌ Erro: {e}")
    
    print(f"   ✅ Total: {len(todos_produtos)} produtos únicos")
    return list(todos_produtos)

def passo5_aplicar_padrao(padrao: re.Pattern, todas_urls: List[str]) -> List[str]:
    """PASSO 5: Aplica padrão a todas URLs"""
    print(f"\n🎯 PASSO 5: Aplicando PADRÃO a {len(todas_urls)} URLs")
    
    produtos = [u for u in todas_urls if padrao.search(u)]
    
    print(f"   ✅ {len(produtos)} produtos encontrados pelo padrão")
    return produtos

async def diagnostico_completo(base_url: str):
    """DIAGNÓSTICO COMPLETO DA ESTRATÉGIA"""
    print("="*60)
    print("🧪 DIAGNÓSTICO: ESTRATÉGIA PROPOSTA")
    print("="*60)
    print(f"\n🌐 Site: {base_url}")
    
    # CENÁRIO 1: Homepage TEM produtos
    print("\n" + "="*60)
    print("CENÁRIO 1: Homepage com produtos")
    print("="*60)
    
    produtos_homepage = await passo1_homepage(base_url)
    
    if len(produtos_homepage) >= 5:
        print("\n✅ SUCESSO: Encontrou produtos na homepage!")
        
        # Detecta padrão
        padrao = passo2_detectar_padrao(produtos_homepage[:50])
        
        if padrao:
            print("\n✅ PADRÃO DETECTADO!")
            
            # Busca sitemap para aplicar padrão
            print("\n📄 Buscando sitemap para aplicar padrão...")
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    sitemap_url = f"{urlparse(base_url).scheme}://{urlparse(base_url).netloc}/sitemap.xml"
                    r = await client.get(sitemap_url, follow_redirects=True)
                    urls_sitemap = re.findall(r'<loc>(.*?)</loc>', r.text)
                    
                    if urls_sitemap:
                        produtos_finais = passo5_aplicar_padrao(padrao, urls_sitemap)
                        
                        print("\n" + "="*60)
                        print("🎉 RESULTADO FINAL (Cenário 1)")
                        print("="*60)
                        print(f"✅ {len(produtos_finais)} produtos descobertos")
                        print("\n📦 Primeiros 5:")
                        for p in produtos_finais[:5]:
                            print(f"   - {p}")
                        
                        return produtos_finais
            except:
                print("   ⚠️ Sitemap não disponível")
                print("\n" + "="*60)
                print("🎉 RESULTADO FINAL (Cenário 1 - sem sitemap)")
                print("="*60)
                print(f"✅ {len(produtos_homepage)} produtos da homepage")
                return produtos_homepage
    
    # CENÁRIO 2: Homepage NÃO tem produtos
    print("\n" + "="*60)
    print("CENÁRIO 2: Homepage sem produtos - navegando categorias")
    print("="*60)
    
    # Busca categorias
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            sitemap_url = f"{urlparse(base_url).scheme}://{urlparse(base_url).netloc}/sitemap.xml"
            r = await client.get(sitemap_url, follow_redirects=True)
            urls_sitemap = re.findall(r'<loc>(.*?)</loc>', r.text)
    except:
        urls_sitemap = []
    
    categorias = await passo3_buscar_categorias(base_url, urls_sitemap)
    
    if not categorias:
        print("\n❌ FALHA: Não encontrou categorias")
        return []
    
    # Extrai produtos das categorias
    produtos_categorias = await passo4_produtos_categorias(categorias)
    
    if not produtos_categorias:
        print("\n❌ FALHA: Não encontrou produtos nas categorias")
        return []
    
    # Detecta padrão dos produtos encontrados
    padrao = passo2_detectar_padrao(produtos_categorias)
    
    if not padrao:
        print("\n⚠️ Não detectou padrão, retornando produtos encontrados")
        print("\n" + "="*60)
        print("🎉 RESULTADO FINAL (Cenário 2 - sem padrão)")
        print("="*60)
        print(f"✅ {len(produtos_categorias)} produtos das categorias")
        return produtos_categorias
    
    # Aplica padrão ao sitemap
    if urls_sitemap:
        produtos_finais = passo5_aplicar_padrao(padrao, urls_sitemap)
        
        print("\n" + "="*60)
        print("🎉 RESULTADO FINAL (Cenário 2)")
        print("="*60)
        print(f"✅ {len(produtos_finais)} produtos descobertos via padrão")
        print("\n📦 Primeiros 5:")
        for p in produtos_finais[:5]:
            print(f"   - {p}")
        
        return produtos_finais
    
    return produtos_categorias

# TESTA COM MATCONCASA
async def main():
    base_url = 'https://www.matconcasa.com.br/'
    produtos = await diagnostico_completo(base_url)
    
    print("\n\n" + "="*60)
    print("📊 ANÁLISE DA ESTRATÉGIA")
    print("="*60)
    
    print("\n✅ PONTOS FORTES:")
    print("   1. Rápida: começa pela homepage (1 HTTP)")
    print("   2. Inteligente: aprende padrão com poucos exemplos")
    print("   3. Resiliente: fallback para categorias")
    print("   4. Escalável: padrão evita validar 21k URLs")
    
    print("\n⚠️ PONTOS DE ATENÇÃO:")
    print("   1. Depende de ter produtos na home OU categorias")
    print("   2. Padrão precisa ter >70% match")
    print("   3. Categorias precisam ter produtos listados")
    
    print("\n🎯 RECOMENDAÇÃO:")
    if len(produtos) > 50:
        print("   ✅ APROVAR E IMPLEMENTAR!")
        print(f"   Conseguiu {len(produtos)} produtos com sucesso")
    else:
        print("   ⚠️ REVISAR ESTRATÉGIA")
        print(f"   Encontrou apenas {len(produtos)} produtos")

asyncio.run(main())
