import httpx
import xml.etree.ElementTree as ET
from urllib.parse import urljoin, urlparse

class _OllamaLLM:
    def __init__(self, model="reader-lm"):
        self.url = "http://localhost:11434/api/generate"
        self.model = model
    def invoke(self, prompt):
        payload = {"model": self.model, "prompt": prompt, "maxTokens": 512, "temperature": 0.0, "topP": 1.0}
        r = httpx.post(self.url, json=payload, timeout=120.0)
        r.raise_for_status()
        data = r.json()
        if isinstance(data, dict):
            if "text" in data: return data["text"]
            choices = data.get("choices") or data.get("generations") or []
            if choices and isinstance(choices, list):
                c0 = choices[0]
                if isinstance(c0, dict):
                    return c0.get("text") or c0.get("message") or str(c0)
                return str(c0)
        return str(data)

llm = _OllamaLLM("reader-lm")

def _get_robot_sitemaps(base_url):
    """Busca sitemaps no robots.txt com fallbacks"""
    sitemaps = []
    
    # Tenta robots.txt primeiro
    try:
        robots = urljoin(base_url, "/robots.txt")
        r = httpx.get(robots, timeout=15)
        if r.status_code == 200:
            for line in r.text.splitlines():
                if line.lower().startswith("sitemap:"):
                    sitemap_url = line.split(":", 1)[1].strip()
                    sitemaps.append(sitemap_url)
                    
                    # Se termina com .gz, tenta versão sem .gz também
                    if sitemap_url.endswith('.gz'):
                        sitemap_no_gz = sitemap_url[:-3]  # remove .gz
                        sitemaps.append(sitemap_no_gz)
    except Exception:
        pass
    
    # Fallbacks comuns se não encontrou nada
    if not sitemaps:
        fallbacks = [
            urljoin(base_url, "/sitemap.xml"),
            urljoin(base_url, "/sitemap_index.xml"),
            urljoin(base_url, "/sitemaps.xml"),
            urljoin(base_url, "/sitemap/sitemap.xml")
        ]
        sitemaps.extend(fallbacks)
    
    return sitemaps

def _parse_sitemap(url):
    """Parseia sitemap XML simples com fallbacks"""
    try:
        r = httpx.get(url, timeout=20)
        r.raise_for_status()
        content = r.content
        
        root = ET.fromstring(content)
        
        # Diferentes namespaces possíveis
        namespaces = [
            {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"},
            {"": "http://www.sitemaps.org/schemas/sitemap/0.9"},
            {}  # sem namespace
        ]
        
        urls = []
        
        for ns in namespaces:
            try:
                # sitemapindex?
                if root.tag.endswith("sitemapindex") or "sitemapindex" in root.tag:
                    if ns:
                        locs = [loc.text.strip() for loc in root.findall(".//sm:loc", ns) if loc.text]
                    else:
                        locs = [loc.text.strip() for loc in root.findall(".//loc") if loc.text]
                    
                    for loc in locs:
                        try:
                            # Se for .gz, tenta sem .gz primeiro
                            if loc.endswith('.gz'):
                                try:
                                    urls += _parse_sitemap(loc[:-3])
                                    continue
                                except:
                                    pass
                            urls += _parse_sitemap(loc)
                        except Exception:
                            continue
                    break
                
                # urlset
                else:
                    if ns:
                        locs = [loc.text.strip() for loc in root.findall(".//sm:loc", ns) if loc.text]
                    else:
                        locs = [loc.text.strip() for loc in root.findall(".//loc") if loc.text]
                    urls = locs
                    break
                    
            except Exception:
                continue
        
        return urls
        
    except Exception as e:
        return []

def categorize_products_with_ollama(produtos, show_message):
    """Usa Ollama para categorizar produtos por URL"""
    if not produtos:
        return {}
    
    show_message(f"Categorizando {len(produtos)} produtos com Ollama...")
    
    # Pega uma amostra para categorizar
    sample = produtos[:50] if len(produtos) > 50 else produtos
    
    prompt = f"""Analise essas URLs de produtos e organize por categorias.
Retorne APENAS um JSON no formato:
{{"Casa e Decoração": ["url1", "url2"], "Brinquedos": ["url3"], "Beleza": ["url4"]}}

URLs:
{chr(10).join(sample)}
"""
    
    try:
        response = llm.invoke(prompt)
        show_message(f"Resposta do Ollama: {response[:200]}...")
        
        # Tenta extrair JSON da resposta
        import json
        # Remove possível texto antes/depois do JSON
        start = response.find('{')
        end = response.rfind('}') + 1
        if start >= 0 and end > start:
            json_str = response[start:end]
            categorias = json.loads(json_str)
            return categorias
    except Exception as e:
        show_message(f"Erro ao categorizar: {e}")
    
    # Fallback: categorização simples por palavra-chave
    categorias = {}
    for produto in produtos:
        url_lower = produto.lower()
        if any(x in url_lower for x in ["brinquedo", "jogo", "boneca", "carrinho"]):
            categorias.setdefault("Brinquedos", []).append(produto)
        elif any(x in url_lower for x in ["beleza", "cabelo", "unha", "cuidado"]):
            categorias.setdefault("Beleza e Cuidado Pessoal", []).append(produto)
        elif any(x in url_lower for x in ["casa", "cozinha", "decoracao", "movel"]):
            categorias.setdefault("Casa e Decoração", []).append(produto)
        elif any(x in url_lower for x in ["ferramenta", "chave", "martelo"]):
            categorias.setdefault("Ferramentas", []).append(produto)
        else:
            categorias.setdefault("Utilidades Domésticas", []).append(produto)
    
    return categorias

def discover_by_sitemap(base_url, show_message):
    """Descobre produtos via sitemap com múltiplos fallbacks"""
    show_message("Buscando sitemaps...")
    sitemaps = _get_robot_sitemaps(base_url)
    show_message(f"Testando {len(sitemaps)} possíveis sitemaps")
    
    urls = []
    seen = set()
    base_netloc = urlparse(base_url).netloc
    
    for i, sm in enumerate(sitemaps):
        try:
            show_message(f"  {i+1}. Tentando: {sm}")
            sitemap_urls = _parse_sitemap(sm)
            
            if sitemap_urls:
                show_message(f"    ✓ Encontradas {len(sitemap_urls)} URLs")
                for u in sitemap_urls:
                    if urlparse(u).netloc == base_netloc and u not in seen:
                        seen.add(u)
                        urls.append(u)
                break  # Para no primeiro sitemap que funcionar
            else:
                show_message(f"    ✗ Vazio ou erro")
                
        except Exception as e:
            show_message(f"    ✗ Erro: {str(e)[:50]}...")
            continue
    
    show_message(f"Total de URLs únicas encontradas: {len(urls)}")
    
    # Filtra apenas produtos
    produtos = []
    for u in urls:
        p = u.lower()
        if any(x in p for x in ("/produto/", "/product/", "/produtos/", "/item/", "/p/")):
            produtos.append(u)
    
    show_message(f"URLs de produtos filtradas: {len(produtos)}")
    return list(dict.fromkeys(produtos))

def extrair_links_do_site(link_do_site, show_message):
    show_message("🎯 Iniciando extração via sitemap...")
    
    # Descobre produtos via sitemap
    produtos = discover_by_sitemap(link_do_site, show_message)
    
    if produtos:
        show_message(f"✅ Encontrados {len(produtos)} produtos via sitemap")
        
        # Categoriza produtos com Ollama
        categorias = categorize_products_with_ollama(produtos, show_message)
        
        # Organiza resultado
        resultado_organizado = []
        total_produtos = 0
        
        for categoria, produtos_cat in categorias.items():
            resultado_organizado.append(f"\n=== {categoria.upper()} ===")
            resultado_organizado.append("")
            
            for produto in produtos_cat:
                resultado_organizado.append(produto)
            
            total_produtos += len(produtos_cat)
            show_message(f"📦 {categoria}: {len(produtos_cat)} produtos")
        
        # Adiciona produtos não categorizados
        produtos_categorizados = set()
        for produtos_cat in categorias.values():
            produtos_categorizados.update(produtos_cat)
        
        produtos_nao_categorizados = [p for p in produtos if p not in produtos_categorizados]
        if produtos_nao_categorizados:
            resultado_organizado.append(f"\n=== OUTROS PRODUTOS ===")
            resultado_organizado.append("")
            for produto in produtos_nao_categorizados:
                resultado_organizado.append(produto)
            show_message(f"📦 Outros: {len(produtos_nao_categorizados)} produtos")
        
        resultado = "\n".join(resultado_organizado)
        
        # Salva resultado
        with open("links_extraidos.txt", "w", encoding="utf-8") as f:
            f.write(resultado)
        
        show_message(f"✅ Extração concluída! {len(produtos)} produtos organizados em {len(categorias)} categorias")
        return resultado
    
    else:
        show_message("❌ Nenhum produto encontrado via sitemap")
        return "Nenhum produto encontrado via sitemap"