import httpx
import gzip
import io
import xml.etree.ElementTree as ET
from urllib.parse import urljoin, urlparse

def _get_robot_sitemaps(base_url):
    """Busca sitemaps no robots.txt"""
    try:
        robots = urljoin(base_url, "/robots.txt")
        r = httpx.get(robots, timeout=15)
        sitemaps = []
        if r.status_code == 200:
            for line in r.text.splitlines():
                if line.lower().startswith("sitemap:"):
                    sitemaps.append(line.split(":", 1)[1].strip())
        # fallback
        if not sitemaps:
            sitemaps.append(urljoin(base_url, "/sitemap.xml"))
        return sitemaps
    except Exception:
        return [urljoin(base_url, "/sitemap.xml")]

def _fetch_xml(url):
    """Baixa XML (suporta .gz)"""
    r = httpx.get(url, timeout=20)
    r.raise_for_status()
    content = r.content
    if url.endswith(".gz"):
        content = gzip.GzipFile(fileobj=io.BytesIO(content)).read()
    return content

def _parse_sitemap(url):
    """Parseia sitemap (recursivo para sitemapindex)"""
    xml_bytes = _fetch_xml(url)
    root = ET.fromstring(xml_bytes)
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    
    # sitemapindex?
    if root.tag.endswith("sitemapindex"):
        locs = [loc.text.strip() for loc in root.findall(".//sm:loc", ns)]
        urls = []
        for loc in locs:
            try:
                urls += _parse_sitemap(loc)
            except Exception:
                continue
        return urls
    
    # urlset
    return [loc.text.strip() for loc in root.findall(".//sm:loc", ns)]

def discover_by_sitemap(base_url, show_message):
    """Descobre produtos e categorias via sitemap"""
    show_message("Buscando sitemaps...")
    sitemaps = _get_robot_sitemaps(base_url)
    show_message(f"Descobri {len(sitemaps)} sitemap(s): {sitemaps}")
    
    urls = []
    seen = set()
    base_netloc = urlparse(base_url).netloc
    
    for sm in sitemaps:
        try:
            show_message(f"Processando sitemap: {sm}")
            for u in _parse_sitemap(sm):
                if urlparse(u).netloc == base_netloc and u not in seen:
                    seen.add(u)
                    urls.append(u)
        except Exception as e:
            show_message(f"Falha no sitemap {sm}: {e}")
    
    show_message(f"Total de URLs encontradas: {len(urls)}")
    
    # Classificação por path
    prod, cat = [], []
    for u in urls:
        p = u.lower()
        if any(x in p for x in ("/produto/", "/product/", "/produtos/", "/item/", "/p/")):
            prod.append(u)
        elif any(x in p for x in ("/categoria/", "/category/", "/collections/", "/colecao/", "/departamento/", "/c/")):
            cat.append(u)
    
    return list(dict.fromkeys(prod)), list(dict.fromkeys(cat))

def extrair_links_do_site(link_do_site, show_message):
    show_message("🎯 Iniciando extração via sitemap...")
    
    # Primeira tentativa: sitemap
    produtos, categorias = discover_by_sitemap(link_do_site, show_message)
    
    if produtos:
        show_message(f"✅ Produtos via sitemap: {len(produtos)}")
        
        # Organiza por categoria (se encontrou)
        if categorias:
            resultado_organizado = []
            resultado_organizado.append("=== PRODUTOS VIA SITEMAP ===")
            resultado_organizado.append("")
            
            for produto in produtos:
                resultado_organizado.append(produto)
            
            if categorias:
                resultado_organizado.append("")
                resultado_organizado.append("=== CATEGORIAS ENCONTRADAS ===")
                resultado_organizado.append("")
                for categoria in categorias:
                    resultado_organizado.append(categoria)
            
            resultado = "\n".join(resultado_organizado)
        else:
            resultado = "\n".join(produtos)
        
        # Salva resultado
        with open("links_extraidos.txt", "w", encoding="utf-8") as f:
            f.write(resultado)
        
        show_message(f"✅ Extração concluída! {len(produtos)} produtos encontrados")
        return resultado
    
    else:
        show_message("⚠️ Nenhum produto encontrado via sitemap")
        
        # Fallback: lista as categorias encontradas
        if categorias:
            show_message(f"Encontradas {len(categorias)} categorias via sitemap")
            resultado = "=== CATEGORIAS ENCONTRADAS VIA SITEMAP ===\n\n" + "\n".join(categorias)
            
            with open("links_extraidos.txt", "w", encoding="utf-8") as f:
                f.write(resultado)
                
            return resultado
        else:
            show_message("❌ Nenhum produto ou categoria encontrado via sitemap")
            return "Nenhum resultado encontrado via sitemap"