import httpx
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import re
from urllib.parse import urlparse

def extrair_produtos_da_categoria(categoria_url, base_netloc, show_message):
    """Extrai links de produtos de uma página de categoria"""
    try:
        show_message(f"  → Acessando: {categoria_url}")
        resp = httpx.get(categoria_url, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        
        produtos = []
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            abs_url = urljoin(categoria_url, href)
            
            # Apenas links internos
            if urlparse(abs_url).netloc != base_netloc:
                continue
                
            # Padrões que indicam produto (expandidos)
            href_l = href.lower()
            if any(p in href_l for p in ("/produto/", "/produtos/", "/p/", "/item/", "/product/")):
                produtos.append(abs_url)
        
        # Remove duplicados
        produtos_unicos = list(dict.fromkeys(produtos))
        show_message(f"  → Encontrados {len(produtos_unicos)} produtos em {categoria_url}")
        
        return produtos_unicos
        
    except Exception as e:
        show_message(f"  → Erro ao processar {categoria_url}: {e}")
        return []

def extrair_links_do_site(link_do_site, show_message):
    show_message("Iniciando a extração dos links...")
    resp = httpx.get(link_do_site, timeout=30)
    resp.raise_for_status()
    html = resp.text
    with open("agua.txt", "w", encoding="utf-8") as f:
        f.write(html)
    soup = BeautifulSoup(html, "html.parser")

    base_netloc = urlparse(link_do_site).netloc
    
    anchors = soup.find_all("a", href=True)
    found = []
    for a in anchors:
        href = a["href"].strip()
        href_l = href.lower()
        abs_url = urljoin(link_do_site, href)
        if urlparse(abs_url).netloc != base_netloc:
            continue

        text = (a.get_text() or "").strip().lower()
        in_nav = any(p.name in ("nav", "header", "aside", "footer") for p in a.parents)
        cls_id = " ".join(a.get("class", []) + [a.get("id") or ""])
        cls_match = bool(re.search(r"(nav|menu|categoria|category|cat|sidebar|list|menu__|menu-)", cls_id, re.I))
        
        # Critérios mais amplos - incluir links que podem ser categorias
        is_potential_category = (
            in_nav or cls_match or
            # URLs que terminam com / (típico de categorias)
            (href.endswith('/') and len(href.strip('/').split('/')) <= 2) or
            # Links com texto curto e descritivo (1-4 palavras)
            (len(text.split()) <= 4 and len(text) > 3) or
            # Padrões conhecidos
            any(p in href_l for p in ("/categoria", "/cat", "/c/", "category")) or
            any(p in text for p in ("categoria", "móveis", "decoração", "brinquedos", "beleza", "ferramentas", "utilidades"))
        )
        
        # Excluir claramente não-categorias
        is_not_category = (
            any(p in href_l for p in ("/login", "/register", "/account", "/cart", "/checkout", "/politica", "/termos", "/contato", "/sobre")) or
            # URLs com números (produtos específicos)
            bool(re.search(r'/\d+/', href)) or
            # URLs muito longas (produtos específicos)
            len(href.strip('/').split('/')) > 4
        )

        if is_potential_category and not is_not_category:
            found.append(abs_url)

    # Remove duplicados das categorias
    categorias = list(dict.fromkeys(found))
    show_message(f"Encontradas {len(categorias)} possíveis categorias:")
    
    # Log das categorias encontradas
    for i, cat in enumerate(categorias):
        show_message(f"  {i+1}. {cat}")
    
    # Extrai produtos organizados por categoria
    resultado_organizado = []
    total_produtos = 0
    
    for i, categoria in enumerate(categorias):
        show_message(f"\nProcessando categoria {i+1}/{len(categorias)}: {categoria}")
        produtos = extrair_produtos_da_categoria(categoria, base_netloc, show_message)
        
        if produtos:
            # Extrai nome da categoria da URL
            nome_categoria = categoria.rstrip('/').split('/')[-1].replace('-', ' ').title()
            
            resultado_organizado.append(f"\n=== {nome_categoria.upper()} ===")
            resultado_organizado.append(f"Categoria: {categoria}")
            resultado_organizado.append("")
            
            for produto in produtos:
                resultado_organizado.append(produto)
            
            total_produtos += len(produtos)
            show_message(f"  ✓ Adicionados {len(produtos)} produtos desta categoria")
        else:
            show_message(f"  ✗ Nenhum produto encontrado nesta categoria")

    # Junta tudo em uma string
    resultado = "\n".join(resultado_organizado)
    
    with open("links_extraidos.txt", "w", encoding="utf-8") as f:
        f.write(resultado)

    show_message(f"\n✅ Extração concluída! Total: {total_produtos} produtos em {len([r for r in resultado_organizado if r.startswith('===')])} categorias")
    return resultado
