"""
Versão 5 - Ultra Simplificada: acha XML do sitemap e extrai URLs de produto.
Lógica: robots.txt → busca sitemap → baixa XML → extrai <loc> → filtra produtos
"""

import httpx
import xml.etree.ElementTree as ET
import gzip
from io import BytesIO
from urllib.parse import urljoin

# Headers básicos de navegador
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

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
    # Tenta robots.txt
    r = _baixar(urljoin(base_url, "/robots.txt"), timeout=10)
    if r and r.text:
        for linha in r.text.splitlines():
            if linha.strip().lower().startswith("sitemap:"):
                sitemap_url = linha.split(":", 1)[1].strip()
                if sitemap_url.startswith("/"):
                    sitemap_url = urljoin(base_url, sitemap_url)
                return sitemap_url
    
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

def _eh_produto(url):
    """Verifica se URL parece ser de produto."""
    url_lower = url.lower()
    
    # Deve conter indicadores de produto (ajustado para pegar /p no final também)
    tem_indicador = any(x in url_lower for x in ["/produto", "/product", "/p/", "/p", "/item"])
    
    # Não deve ser página de categoria/sistema
    nao_eh_sistema = not any(x in url_lower for x in [
        "/categoria", "/category", "/collection",
        "/busca", "/search", 
        "/carrinho", "/cart",
        "/conta", "/account",
        "/blog", "/contato", "/contact"
    ])
    
    # Não deve terminar apenas com domínio
    nao_eh_home = url.rstrip("/").count("/") > 2
    
    return tem_indicador and nao_eh_sistema and nao_eh_home

def extrair_produtos_rapido(base_url, show_message, max_produtos=None):
    """
    V5: Extração ultra-simplificada de produtos do sitemap.
    
    Fluxo:
    1. Acha sitemap (robots.txt ou URLs comuns)
    2. Baixa e parseia XML
    3. Filtra URLs de produto
    4. Retorna lista de dicts com url e nome
    """
    show_message("Buscando sitemap...")
    
    sitemap_url = _achar_sitemap(base_url)
    if not sitemap_url:
        show_message("Nenhum sitemap encontrado")
        return []
    
    show_message(f"Sitemap: {sitemap_url}")
    
    urls = _extrair_urls_do_xml(sitemap_url)
    show_message(f"Total de URLs no sitemap: {len(urls)}")
    
    # Se encontrou outros sitemaps (sitemap index), procura o de produtos
    sitemaps_aninhados = [u for u in urls if u.lower().endswith((".xml", ".xml.gz"))]
    if sitemaps_aninhados and len(urls) < 50:  # Provavelmente é um índice
        show_message(f"Sitemap index detectado com {len(sitemaps_aninhados)} filhos")
        
        # Procura sitemap de produtos (product/produto)
        sitemap_produtos = None
        for s in sitemaps_aninhados:
            if "product" in s.lower() or "produto" in s.lower():
                sitemap_produtos = s
                break
        
        # Se não achou sitemap específico de produtos, pega o primeiro
        if not sitemap_produtos:
            sitemap_produtos = sitemaps_aninhados[0]
        
        show_message(f"Expandindo sitemap: {sitemap_produtos}")
        urls = _extrair_urls_do_xml(sitemap_produtos)
        show_message(f"URLs encontradas: {len(urls)}")
    
    # Filtra produtos
    produtos = []
    vistos = set()
    
    for url in urls:
        url_limpa = url.split("?")[0].rstrip("/")
        
        if url_limpa in vistos:
            continue
        vistos.add(url_limpa)
        
        if _eh_produto(url_limpa):
            # Extrai nome do slug da URL (antes do /p ou último segmento)
            partes = url_limpa.rstrip("/").split("/")
            # Se termina com /p, pega o penúltimo; senão pega o último
            if partes[-1].lower() == "p":
                slug = partes[-2] if len(partes) > 1 else partes[-1]
            else:
                slug = partes[-1]
            nome = slug.replace("-", " ").title()
            produtos.append({"url": url_limpa, "nome": nome})
            
            if max_produtos and len(produtos) >= max_produtos:
                break
    
    show_message(f"Produtos encontrados: {len(produtos)}")
    return produtos