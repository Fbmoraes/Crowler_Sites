"""
EXTRACT LINKS V8 - Ultra-Simplificado
Estratégia: Discovery por navegação + Pattern Learning
"""
import asyncio
import httpx
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from typing import List, Dict, Set, Optional

async def buscar_sitemap(base_url: str) -> List[str]:
    """Busca URLs do sitemap (com expansão recursiva)"""
    parsed = urlparse(base_url)
    sitemap_url = f"{parsed.scheme}://{parsed.netloc}/sitemap.xml"
    
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(sitemap_url, follow_redirects=True)
            if r.status_code == 200:
                urls = re.findall(r'<loc>(.*?)</loc>', r.text)
                
                # Verifica se é índice de sitemaps (contém .xml)
                if urls and any('.xml' in u for u in urls):
                    print(f"  → Sitemap index detectado: {len(urls)} sitemaps filhos")
                    
                    # Expande recursivamente
                    todas_urls = []
                    for sitemap_filho in urls:
                        if '.xml' in sitemap_filho:
                            try:
                                r2 = await client.get(sitemap_filho, timeout=10)
                                if r2.status_code == 200:
                                    urls_filho = re.findall(r'<loc>(.*?)</loc>', r2.text)
                                    # Filtra apenas URLs de produtos (não .xml)
                                    # Prioriza URLs com /p no final (produtos VTEX) ou com "product" no sitemap
                                    if 'product' in sitemap_filho.lower():
                                        # Sitemap de produtos: pega tudo
                                        urls_produto = [u for u in urls_filho if '.xml' not in u and u.startswith('http')]
                                    else:
                                        # Outros sitemaps: filtra apenas URLs de produto
                                        urls_produto = [u for u in urls_filho 
                                                       if '.xml' not in u 
                                                       and u.startswith('http')
                                                       and (u.endswith('/p') or '/produto' in u or '/p/' in u)]
                                    
                                    todas_urls.extend(urls_produto)
                                    if urls_produto:
                                        print(f"    → {sitemap_filho.split('/')[-1]}: {len(urls_produto)} URLs")
                            except:
                                pass
                    
                    return todas_urls
                else:
                    # Sitemap simples
                    return [u for u in urls if u.startswith('http')]
    except:
        pass
    return []

def detectar_padrao(urls: List[str]) -> Optional[re.Pattern]:
    """Detecta padrão em URLs (threshold 15%)"""
    if len(urls) < 10:
        return None
    
    amostra = urls[20:70] if len(urls) > 70 else urls[:50]
    
    padroes = [
        (r'/produtos?/[^/]+-\d+/?$', 0.25),  # WordPress
        (r'/p(roduto)?/[^/]+/\d+', 0.5),     # VTEX/Magento
        (r'^https?://[^/]+/[^/]+/[^/]+/[^/]+/?$', 0.15),  # Nível 3
    ]
    
    for padrao_str, threshold in padroes:
        padrao = re.compile(padrao_str)
        matches = sum(1 for url in amostra if padrao.search(url))
        if matches / len(amostra) >= threshold:
            return padrao
    
    return None

async def descobrir_categorias(base_url: str) -> List[Dict]:
    """Descobre categorias na home"""
    categorias = []
    
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(base_url, follow_redirects=True)
            soup = BeautifulSoup(r.text, 'html.parser')
            
            # Busca TODOS os links (não só nav)
            todos_links = soup.find_all('a', href=True)[:100]
            
            for link in todos_links:
                texto = link.get_text(strip=True)
                href = link.get('href')
                
                # Ignora links institucionais e vazios
                if not texto or len(texto) < 3:
                    continue
                    
                if any(x in texto.lower() for x in ['contato', 'sobre', 'login', 'cart', 'conta', 'ajuda']):
                    continue
                
                url_completa = urljoin(base_url, href)
                
                # Só aceita URLs da mesma origem
                if urlparse(url_completa).netloc != urlparse(base_url).netloc:
                    continue
                
                # Conta níveis (categorias tem 1-2 níveis)
                niveis = len([p for p in urlparse(url_completa).path.split('/') if p])
                
                if 1 <= niveis <= 2:
                    categorias.append({
                        'nome': texto,
                        'url': url_completa
                    })
    except:
        pass
    
    # Remove duplicatas por URL
    categorias_unicas = []
    urls_vistas = set()
    for cat in categorias:
        if cat['url'] not in urls_vistas:
            urls_vistas.add(cat['url'])
            categorias_unicas.append(cat)
    
    return categorias_unicas[:10]  # Max 10 categorias

async def extrair_produtos_categoria(url_cat: str, max_prods: int = 50) -> Set[str]:
    """Extrai produtos de uma categoria"""
    produtos = set()
    
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(url_cat, follow_redirects=True)
            soup = BeautifulSoup(r.text, 'html.parser')
            
            # Busca links de produtos (mais flexível)
            for link in soup.find_all('a', href=True):
                href = link.get('href')
                url = urljoin(url_cat, href)
                
                # Só aceita URLs da mesma origem
                if urlparse(url).netloc != urlparse(url_cat).netloc:
                    continue
                
                # Heurística: URL de produto tem 3+ níveis
                niveis = len([p for p in urlparse(url).path.split('/') if p])
                if niveis >= 3:
                    produtos.add(url)
                    if len(produtos) >= max_prods:
                        break
    except:
        pass
    
    return produtos

async def extrair_produtos_rapido(
    base_url: str,
    show_message,
    max_produtos: int = None,
    progress_callback=None
):
    """Extração inteligente: Sitemap ou Navegação"""
    
    show_message("🔍 Buscando sitemap...")
    urls_sitemap = await buscar_sitemap(base_url)
    
    # Sitemap BOM: < 5000 URLs
    if urls_sitemap and len(urls_sitemap) < 5000:
        show_message(f"✅ Sitemap: {len(urls_sitemap)} URLs")
        
        # Detecta padrão
        padrao = detectar_padrao(urls_sitemap)
        if padrao:
            show_message(f"✅ Padrão detectado!")
            urls_filtradas = [u for u in urls_sitemap if padrao.search(u)]
        else:
            # Prioriza URLs nível 3-4
            urls_nivel3 = [u for u in urls_sitemap if u.count('/') >= 4]
            urls_filtradas = urls_nivel3 if urls_nivel3 else urls_sitemap
        
        # Limita se necessário
        if max_produtos:
            urls_filtradas = urls_filtradas[:max_produtos]
        
        produtos = [{'nome': u.split('/')[-1].replace('-', ' ').title(), 'url': u} 
                   for u in urls_filtradas]
        
        show_message(f"✅ {len(produtos)} produtos encontrados")
        return produtos
    
    # Sitemap RUIM/inexistente: Navegação
    show_message("⚠️ Sitemap ruim/inexistente. Navegando por categorias...")
    
    categorias = await descobrir_categorias(base_url)
    if not categorias:
        show_message("❌ Nenhuma categoria encontrada. Usando sitemap como fallback...")
        
        # Fallback: usa sitemap mesmo sendo ruim
        if urls_sitemap:
            show_message(f"⚠️ Usando {len(urls_sitemap)} URLs do sitemap")
            urls_filtradas = [u for u in urls_sitemap if u.count('/') >= 4][:max_produtos or 500]
            produtos = [{'nome': u.split('/')[-1].replace('-', ' ').title(), 'url': u} 
                       for u in urls_filtradas]
            show_message(f"✅ {len(produtos)} produtos do sitemap")
            return produtos
        
        return []
    
    show_message(f"✅ {len(categorias)} categorias encontradas")
    
    # Navega por categorias
    todos_produtos = set()
    for i, cat in enumerate(categorias, 1):
        show_message(f"[{i}/{len(categorias)}] Navegando: {cat['nome']}")
        prods = await extrair_produtos_categoria(cat['url'], max_prods=100)
        
        if prods:
            show_message(f"   → {len(prods)} produtos")
            todos_produtos.update(prods)
        
        if max_produtos and len(todos_produtos) >= max_produtos:
            break
    
    urls_finais = list(todos_produtos)[:max_produtos] if max_produtos else list(todos_produtos)
    produtos = [{'nome': u.split('/')[-1].replace('-', ' ').title(), 'url': u} 
               for u in urls_finais]
    
    show_message(f"✅ {len(produtos)} produtos descobertos")
    return produtos

# Wrapper síncrono
def extrair_produtos(base_url, show_message, max_produtos=None, progress_callback=None):
    return asyncio.run(extrair_produtos_rapido(base_url, show_message, max_produtos, progress_callback))
