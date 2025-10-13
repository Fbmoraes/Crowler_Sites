import httpx
from bs4 import BeautifulSoup
import re
import json

class _OllamaLLM:
    def __init__(self, model="reader-lm"):
        self.url = "http://localhost:11434/api/generate"
        self.model = model
    def invoke(self, prompt):
        payload = {"model": self.model, "prompt": prompt, "stream": False, "temperature": 0.0}
        r = httpx.post(self.url, json=payload, timeout=120.0)
        r.raise_for_status()
        data = r.json()
        if isinstance(data, dict):
            # Ollama usa o campo 'response'
            if "response" in data: 
                return data["response"]
            # Fallbacks para outros tipos de resposta
            if "text" in data: 
                return data["text"]
            choices = data.get("choices") or data.get("generations") or []
            if choices and isinstance(choices, list):
                c0 = choices[0]
                if isinstance(c0, dict):
                    return c0.get("text") or c0.get("message") or str(c0)
                return str(c0)
        return str(data)

llm = _OllamaLLM("reader-lm")

def extrair_detalhes_produto(url_produto, show_message):
    """Extrai todos os detalhes possíveis de um produto"""
    try:
        show_message(f"Extraindo detalhes de: {url_produto}")
        
        # Faz request da página do produto
        response = httpx.get(url_produto, timeout=15)
        response.raise_for_status()
        html = response.text
        
        soup = BeautifulSoup(html, "html.parser")
        
        # Salva HTML para debug
        with open("debug_detalhes.html", "w", encoding="utf-8") as f:
            f.write(html)
        
        detalhes = {}
        
        # 1. NOME DO PRODUTO
        show_message(f"    Extraindo nome do produto...")
        nome = extrair_nome_produto(soup, show_message)
        detalhes['nome'] = nome
        
        # 2. PREÇO
        show_message(f"    Extraindo preco...")
        preco = extrair_preco_produto_detalhes(soup, show_message)
        detalhes['preco'] = preco
        
        # 3. CATEGORIA/BREADCRUMB
        show_message(f"    Extraindo categoria...")
        categoria = extrair_categoria_produto(soup, show_message)
        detalhes['categoria'] = categoria
        
        # 4. DESCRIÇÃO
        show_message(f"    Extraindo descricao...")
        descricao = extrair_descricao_produto(soup, show_message)
        detalhes['descricao'] = descricao
        
        # 5. IMAGENS
        show_message(f"    Extraindo imagens...")
        imagens = extrair_imagens_produto(soup, url_produto, show_message)
        detalhes['imagens'] = imagens
        
        # 6. ESTOQUE/DISPONIBILIDADE
        show_message(f"    Extraindo informacoes de estoque...")
        estoque = extrair_estoque_produto(soup, show_message)
        detalhes['estoque'] = estoque
        
        # 7. ESPECIFICAÇÕES TÉCNICAS (se houver)
        show_message(f"    Extraindo especificacoes...")
        specs = extrair_especificacoes_produto(soup, show_message)
        detalhes['especificacoes'] = specs
        
        # 8. USAR OLLAMA PARA COMPLETAR DADOS FALTANTES
        show_message(f"    Usando Ollama para refinar dados...")
        detalhes_refinados = refinar_com_ollama(soup, detalhes, show_message)
        
        show_message(f"    Extracao de detalhes concluida!")
        return detalhes_refinados
        
    except Exception as e:
        show_message(f"    Erro ao extrair detalhes: {e}")
        return {"erro": str(e)}

def extrair_nome_produto(soup, show_message):
    """Extrai o nome do produto"""
    # Estratégias múltiplas para nome
    strategies = [
        lambda: soup.find("h1").get_text(strip=True) if soup.find("h1") else None,
        lambda: soup.find(attrs={"class": re.compile(r"product.*title|title.*product", re.I)}).get_text(strip=True) if soup.find(attrs={"class": re.compile(r"product.*title|title.*product", re.I)}) else None,
        lambda: soup.find(attrs={"id": re.compile(r"product.*title|title.*product", re.I)}).get_text(strip=True) if soup.find(attrs={"id": re.compile(r"product.*title|title.*product", re.I)}) else None,
        lambda: soup.title.get_text(strip=True) if soup.title else None
    ]
    
    for strategy in strategies:
        try:
            nome = strategy()
            if nome and len(nome) > 5:
                # Remove caracteres problemáticos
                nome_limpo = nome.encode('ascii', 'ignore').decode('ascii')
                if not nome_limpo:
                    nome_limpo = nome
                show_message(f"      Nome encontrado: {nome_limpo[:50]}...")
                return nome
        except:
            continue
    
    show_message(f"      Nome nao encontrado")
    return "Nome não encontrado"

def extrair_preco_produto_detalhes(soup, show_message):
    """Extrai preço do produto"""
    # Busca por padrões de preço no texto
    page_text = soup.get_text()
    price_patterns = [
        r'R\$\s*\d+[.,]\d{2}',
        r'\$\s*\d+[.,]\d{2}',
        r'€\s*\d+[.,]\d{2}'
    ]
    
    all_prices = []
    for pattern in price_patterns:
        matches = re.findall(pattern, page_text)
        all_prices.extend(matches)
    
    # Filtra preços válidos (não zero)
    valid_prices = [p for p in all_prices if not re.search(r'0[.,]00', p)]
    if valid_prices:
        preco = valid_prices[0].strip()
        show_message(f"      Preco encontrado: {preco}")
        return preco
    
    show_message(f"      Preco nao encontrado")
    return "Preço não encontrado"

def extrair_categoria_produto(soup, show_message):
    """Extrai categoria via breadcrumb ou navegação"""
    # Busca breadcrumb
    breadcrumb_selectors = [
        {"class": re.compile(r"breadcrumb", re.I)},
        {"id": re.compile(r"breadcrumb", re.I)},
        {"class": re.compile(r"navigation|nav", re.I)}
    ]
    
    for selector in breadcrumb_selectors:
        breadcrumb = soup.find(attrs=selector)
        if breadcrumb:
            # Extrai links do breadcrumb
            links = breadcrumb.find_all("a")
            if links:
                categorias = []
                for link in links:
                    text = link.get_text(strip=True)
                    # Ignora links vazios ou "Início"
                    if text and text not in ["Início", "Home", ""]:
                        categorias.append(text)
                
                if categorias:
                    categoria_text = " > ".join(categorias)
                    show_message(f"      ✓ Categoria (breadcrumb links): {categoria_text}")
                    return categoria_text
            
            # Se não tem links, pega texto geral do breadcrumb
            breadcrumb_text = breadcrumb.get_text(separator=" > ", strip=True)
            if breadcrumb_text and len(breadcrumb_text) > 5:
                # Limpa texto duplicado
                partes = breadcrumb_text.split(" > ")
                partes_limpas = []
                for parte in partes:
                    parte = parte.strip()
                    if parte and parte not in ["Início", "Home", ""] and parte not in partes_limpas:
                        partes_limpas.append(parte)
                
                if partes_limpas:
                    categoria_final = " > ".join(partes_limpas)
                    show_message(f"      ✓ Categoria (breadcrumb text): {categoria_final}")
                    return categoria_final
    
    # Fallback: busca em meta tags
    meta_category = soup.find("meta", attrs={"name": re.compile(r"category", re.I)})
    if meta_category and meta_category.get("content"):
        show_message(f"      ✓ Categoria (meta): {meta_category['content']}")
        return meta_category["content"]
    
    # Fallback: busca em links de categoria no header
    nav_links = soup.find_all("a", href=re.compile(r"categoria|category", re.I))
    if nav_links:
        categorias = [link.get_text(strip=True) for link in nav_links[:3] if link.get_text(strip=True)]
        if categorias:
            categoria_text = " | ".join(categorias)
            show_message(f"      ✓ Categorias do menu: {categoria_text}")
            return categoria_text
    
    show_message(f"      ⚠️ Categoria não encontrada")
    return "Categoria não encontrada"

def extrair_descricao_produto(soup, show_message):
    """Extrai descrição do produto"""
    # Busca por elementos comuns de descrição
    desc_selectors = [
        {"class": re.compile(r"description|desc|details|sobre", re.I)},
        {"id": re.compile(r"description|desc|details|sobre", re.I)}
    ]
    
    for selector in desc_selectors:
        desc_elem = soup.find(attrs=selector)
        if desc_elem:
            desc_text = desc_elem.get_text(strip=True)
            if desc_text and len(desc_text) > 20:
                show_message(f"      ✓ Descrição encontrada: {desc_text[:100]}...")
                return desc_text
    
    # Fallback: busca por parágrafos longos
    paragraphs = soup.find_all("p")
    for p in paragraphs:
        text = p.get_text(strip=True)
        if len(text) > 100:  # Parágrafo substancial
            show_message(f"      ✓ Descrição (parágrafo): {text[:100]}...")
            return text
    
    show_message(f"      ⚠️ Descrição não encontrada")
    return "Descrição não encontrada"

def extrair_imagens_produto(soup, base_url, show_message):
    """Extrai URLs das imagens do produto"""
    from urllib.parse import urljoin
    
    imagens = []
    
    # Busca imagens comuns de produto
    img_selectors = [
        soup.find_all("img", attrs={"class": re.compile(r"product|main|primary", re.I)}),
        soup.find_all("img", attrs={"id": re.compile(r"product|main|primary", re.I)}),
        soup.find_all("img", src=re.compile(r"product|thumb|gallery", re.I))
    ]
    
    for img_list in img_selectors:
        for img in img_list:
            src = img.get("src") or img.get("data-src")
            if src:
                full_url = urljoin(base_url, src)
                if full_url not in imagens:
                    imagens.append(full_url)
    
    # Remove imagens muito pequenas (ícones)
    imagens_filtradas = []
    for img_url in imagens[:5]:  # Limita a 5 imagens
        if not re.search(r'icon|logo|btn|button', img_url, re.I):
            imagens_filtradas.append(img_url)
    
    if imagens_filtradas:
        show_message(f"      ✓ {len(imagens_filtradas)} imagens encontradas")
    else:
        show_message(f"      ⚠️ Nenhuma imagem encontrada")
    
    return imagens_filtradas

def extrair_estoque_produto(soup, show_message):
    """Extrai informações de estoque"""
    # Busca por indicadores de estoque
    estoque_patterns = [
        r'\d+\s*em\s*estoque',
        r'\d+\s*disponível',
        r'estoque:\s*\d+',
        r'\d+\s*unidades'
    ]
    
    page_text = soup.get_text()
    for pattern in estoque_patterns:
        match = re.search(pattern, page_text, re.I)
        if match:
            show_message(f"      ✓ Estoque: {match.group()}")
            return match.group()
    
    # Busca por elementos com classes de estoque
    estoque_elem = soup.find(attrs={"class": re.compile(r"stock|estoque|disponib", re.I)})
    if estoque_elem:
        estoque_text = estoque_elem.get_text(strip=True)
        show_message(f"      ✓ Info estoque: {estoque_text}")
        return estoque_text
    
    show_message(f"      ⚠️ Informação de estoque não encontrada")
    return "Estoque não informado"

def extrair_especificacoes_produto(soup, show_message):
    """Extrai especificações técnicas"""
    specs = {}
    
    # Busca por tabelas de especificações
    tables = soup.find_all("table")
    for table in tables:
        rows = table.find_all("tr")
        for row in rows:
            cells = row.find_all(["td", "th"])
            if len(cells) == 2:
                key = cells[0].get_text(strip=True)
                value = cells[1].get_text(strip=True)
                if key and value and len(key) < 50:
                    specs[key] = value
    
    # Busca por listas de especificações
    spec_lists = soup.find_all(attrs={"class": re.compile(r"spec|feature|detail", re.I)})
    for spec_list in spec_lists:
        items = spec_list.find_all("li")
        for item in items:
            text = item.get_text(strip=True)
            if ":" in text:
                key, value = text.split(":", 1)
                specs[key.strip()] = value.strip()
    
    if specs:
        show_message(f"      ✓ {len(specs)} especificações encontradas")
    else:
        show_message(f"      ⚠️ Especificações não encontradas")
    
    return specs

def refinar_com_ollama(soup, detalhes, show_message):
    """Usa Ollama para refinar e completar dados"""
    # Pega texto relevante da página
    page_text = soup.get_text()[:1000]  # Primeiros 1000 chars
    
    # Extrai título da página para ajudar
    title = soup.title.get_text() if soup.title else ""
    
    show_message(f"      Debug: Titulo = {title[:100]}...")
    
    # Prompt com exemplo para treinar o modelo
    prompt = f"""O produto é: Kit Jarra com 4 Copos em Vidro Maracatú Nadir ( 16561 )
Qual é a marca? Nadir
Qual é a categoria? Utilidades Domésticas
Qual é o resumo? Kit de jarra e copos em vidro
Qual é o nome limpo? Kit Jarra com 4 Copos em Vidro Maracatú Nadir

O produto é: {title}
Qual é a marca?"""
    
    try:
        show_message(f"      Chamando Ollama...")
        resposta = llm.invoke(prompt).strip()
        show_message(f"      Resposta Ollama: {resposta[:100]}...")
        
        # Extrai marca (busca por padrão após "Qual é a marca?")
        marca_match = re.search(r'Qual é a marca\?\s*([^\n\r]+)', resposta, re.I)
        if marca_match:
            marca = marca_match.group(1).strip()
            # Remove texto extra
            marca = re.sub(r'Qual é a categoria.*', '', marca, flags=re.I).strip()
            if marca and marca.lower() not in ['n/a', 'não encontrada', 'não informado', '']:
                detalhes['marca'] = marca
                show_message(f"      Marca extraida via Ollama: {marca}")
        
        # Agora pergunta sobre categoria
        prompt_cat = f"""O produto é: {title}
Qual é a categoria principal? (ex: Utilidades Domésticas, Eletrônicos, Casa e Jardim)"""
        
        resposta_cat = llm.invoke(prompt_cat).strip()
        show_message(f"      Resposta categoria: {resposta_cat[:50]}...")
        
        # Busca categoria na resposta
        if resposta_cat and len(resposta_cat) < 100:  # Resposta curta indica categoria
            categoria_clean = resposta_cat.strip()
            if categoria_clean.lower() not in ['n/a', 'não encontrada', 'categoria']:
                detalhes['categoria_principal'] = categoria_clean
                show_message(f"      Categoria extraida via Ollama: {categoria_clean}")
        
        # Pergunta sobre resumo
        prompt_resumo = f"""Produto: {title}
Descrição: {page_text[:300]}
        
Faça um resumo específico de 1 linha sobre o que é este produto exatamente:"""
        
        resposta_resumo = llm.invoke(prompt_resumo).strip()
        if resposta_resumo and len(resposta_resumo) < 200:  # Resumo não muito longo
            resumo_clean = resposta_resumo.strip()
            if resumo_clean.lower() not in ['n/a', 'não encontrado', 'resumo']:
                detalhes['resumo'] = resumo_clean
                show_message(f"      Resumo extraido via Ollama: {resumo_clean[:50]}...")
        
        # Nome limpo - remove códigos
        nome_original = detalhes.get('nome', title)
        if nome_original:
            # Remove códigos entre parênteses
            nome_limpo = re.sub(r'\s*\(\s*\d+\s*\)', '', nome_original).strip()
            if nome_limpo != nome_original:
                detalhes['nome_limpo'] = nome_limpo
                show_message(f"      Nome limpo: {nome_limpo}")
        
        # Fallback: extração manual básica do título
        if not detalhes.get('marca') and title:
            # Busca marcas conhecidas no título
            marcas_conhecidas = ['nadir', 'samsung', 'apple', 'flash limp', 'philips', 'electrolux', 'brastemp']
            title_lower = title.lower()
            for marca in marcas_conhecidas:
                if marca in title_lower:
                    detalhes['marca'] = marca.title()
                    show_message(f"      Marca encontrada no titulo: {marca.title()}")
                    break
        
        if not detalhes.get('categoria_principal'):
            # Se categoria breadcrumb contém info útil
            categoria_atual = detalhes.get('categoria', '')
            if 'utilidades domésticas' in categoria_atual.lower():
                detalhes['categoria_principal'] = 'Utilidades Domésticas'
                show_message(f"      Categoria inferida: Utilidades Domésticas")
            elif 'eletrônicos' in categoria_atual.lower():
                detalhes['categoria_principal'] = 'Eletrônicos'
            elif 'casa' in categoria_atual.lower() and 'jardim' in categoria_atual.lower():
                detalhes['categoria_principal'] = 'Casa e Jardim'
        
    except Exception as e:
        show_message(f"      Erro no Ollama: {e}")
        import traceback
        show_message(f"      Traceback: {traceback.format_exc()}")
    
    return detalhes

def extrair_detalhes_produtos(produtos_text, show_message, max_produtos=2):
    """Extrai detalhes de uma lista de produtos"""
    show_message("📋 Iniciando extração de detalhes...")
    
    # Parse da lista de produtos
    linhas = produtos_text.strip().split('\n')
    urls_produtos = []
    
    for linha in linhas:
        linha = linha.strip()
        if linha.startswith('http') and '/produto' in linha:
            if not linha.endswith('/produtos/') and not linha.endswith('/br/produtos/'):
                urls_produtos.append(linha)
    
    show_message(f"📦 Encontrados {len(urls_produtos)} produtos válidos")
    
    # Limita para teste
    if len(urls_produtos) > max_produtos:
        urls_produtos = urls_produtos[:max_produtos]
        show_message(f"⚠️ Limitando a {max_produtos} produtos para análise detalhada")
    
    resultados = []
    resultados.append("=== DETALHES DOS PRODUTOS ===\n")
    
    for i, url in enumerate(urls_produtos):
        show_message(f"🔍 Analisando produto {i+1}/{len(urls_produtos)}")
        detalhes = extrair_detalhes_produto(url, show_message)
        
        # Formata resultado
        resultados.append(f"--- PRODUTO {i+1} ---")
        resultados.append(f"URL: {url}")
        resultados.append(f"Nome Original: {detalhes.get('nome', 'N/A')}")
        resultados.append(f"Nome Limpo: {detalhes.get('nome_limpo', 'N/A')}")
        resultados.append(f"Preço: {detalhes.get('preco', 'N/A')}")
        resultados.append(f"Marca: {detalhes.get('marca', 'N/A')}")
        resultados.append(f"Categoria Breadcrumb: {detalhes.get('categoria', 'N/A')}")
        resultados.append(f"Categoria Principal: {detalhes.get('categoria_principal', 'N/A')}")
        resultados.append(f"Resumo: {detalhes.get('resumo', 'N/A')}")
        resultados.append(f"Estoque: {detalhes.get('estoque', 'N/A')}")
        
        if detalhes.get('imagens'):
            resultados.append(f"Imagens ({len(detalhes['imagens'])}):")
            for img in detalhes['imagens'][:3]:
                resultados.append(f"  - {img}")
        
        if detalhes.get('especificacoes'):
            resultados.append(f"Especificações:")
            for key, value in list(detalhes['especificacoes'].items())[:5]:
                resultados.append(f"  - {key}: {value}")
        
        resultados.append(f"Descrição: {detalhes.get('descricao', 'N/A')[:200]}...")
        resultados.append("")
        
        show_message(f"✅ Produto {i+1} analisado completamente")
    
    resultado_final = "\n".join(resultados)
    
    # Salva resultado
    with open("detalhes_extraidos.txt", "w", encoding="utf-8") as f:
        f.write(resultado_final)
    
    show_message(f"✅ Extração de detalhes concluída! {len(urls_produtos)} produtos analisados")
    return resultado_final