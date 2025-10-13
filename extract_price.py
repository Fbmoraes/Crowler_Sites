import httpx
from bs4 import BeautifulSoup
import re

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

def extrair_preco_produto(url_produto, show_message):
    """Extrai o preço de um produto usando Ollama"""
    try:
        show_message(f"  → Extraindo preço de: {url_produto}")
        
        # Faz request da página do produto
        response = httpx.get(url_produto, timeout=15)
        response.raise_for_status()
        html = response.text
        
        soup = BeautifulSoup(html, "html.parser")
        
        # Debug: salva HTML para inspeção
        with open("debug_produto.html", "w", encoding="utf-8") as f:
            f.write(html)
        show_message(f"    💾 HTML salvo em debug_produto.html")
        
        # Tenta encontrar preço com heurísticas simples primeiro
        price_patterns = [
            r'R\$\s*\d+[.,]\d{2}',
            r'\$\s*\d+[.,]\d{2}',
            r'€\s*\d+[.,]\d{2}',
            r'\d+[.,]\d{2}\s*R\$'
        ]
        
        # Busca em todo o texto da página
        page_text = soup.get_text()
        show_message(f"    🔍 Buscando preços no texto da página...")
        
        all_prices = []
        for pattern in price_patterns:
            matches = re.findall(pattern, page_text)
            all_prices.extend(matches)
        
        if all_prices:
            show_message(f"    💰 Preços encontrados por heurística: {all_prices}")
            # Filtra preços que não sejam R$0,00
            valid_prices = [p for p in all_prices if not re.search(r'0[.,]00', p)]
            if valid_prices:
                preco_final = valid_prices[0].strip()
                show_message(f"    ✓ Preço escolhido: {preco_final}")
                return preco_final
            else:
                show_message(f"    ⚠️ Todos os preços encontrados são R$0,00")
        
        # Se não encontrou com heurística, usa Ollama
        show_message(f"    🤖 Usando Ollama para encontrar preço...")
        
        # Estratégias mais específicas para encontrar elementos de preço
        price_elements = []
        
        # Busca por elementos com texto que contém R$
        elements_with_price = soup.find_all(string=re.compile(r'R\$|€|\$'))
        for elem in elements_with_price:
            if elem.parent:
                price_elements.append(elem.parent)
        
        # Busca por classes/IDs comuns de preço
        price_selectors = [
            {"class": re.compile(r"price|preco|valor|cost|amount", re.I)},
            {"id": re.compile(r"price|preco|valor|cost|amount", re.I)},
            {"data-product-price": True},
            {"data-price": True}
        ]
        
        for selector in price_selectors:
            price_elements.extend(soup.find_all(attrs=selector))
        
        # Remove duplicatas
        price_elements = list(set(price_elements))
        
        relevant_html = ""
        for elem in price_elements[:10]:  # Limita a 10 elementos
            relevant_html += f"<!-- Elemento: {elem.name} -->\n"
            relevant_html += str(elem) + "\n\n"
        
        show_message(f"    📝 Encontrados {len(price_elements)} elementos relevantes")
        
        # Se não encontrou elementos específicos, pega um trecho maior
        if not relevant_html:
            show_message(f"    ⚠️ Nenhum elemento específico encontrado, usando trecho do HTML")
            relevant_html = str(soup)[:3000]  # Primeiros 3000 chars
        
        # Salva HTML relevante para debug
        with open("debug_relevant.html", "w", encoding="utf-8") as f:
            f.write(relevant_html)
        
        prompt = f"""Você é um extrator de preços de produtos em páginas web.
Analise este HTML e encontre o PREÇO PRINCIPAL do produto à venda.

INSTRUÇÕES:
- Procure por valores em Real (R$), Dólar ($) ou Euro (€)
- Ignore preços R$0,00 ou $0.00
- Retorne APENAS o preço no formato: R$XX,XX
- Se não encontrar, retorne: PREÇO NÃO ENCONTRADO

HTML para análise:
{relevant_html}
"""
        
        try:
            resposta = llm.invoke(prompt).strip()
            show_message(f"    🤖 Resposta Ollama: '{resposta}'")
            
            # Valida se parece com um preço válido
            if re.search(r'R\$\s*[1-9]\d*[.,]\d{2}|\$\s*[1-9]\d*[.,]\d{2}|€\s*[1-9]\d*[.,]\d{2}', resposta):
                show_message(f"    ✓ Preço válido encontrado pelo Ollama!")
                return resposta
            elif "NÃO ENCONTRADO" in resposta.upper():
                show_message(f"    ⚠️ Ollama não encontrou preço")
                return "PREÇO NÃO ENCONTRADO"
            else:
                show_message(f"    ❌ Resposta Ollama inválida")
                return f"RESPOSTA INVÁLIDA: {resposta}"
                
        except Exception as e:
            show_message(f"    💥 Erro no Ollama: {e}")
            return "ERRO NO OLLAMA"
            
    except Exception as e:
        show_message(f"    💥 Erro ao acessar URL: {e}")
        return "ERRO DE ACESSO"

def extrair_precos_produtos(produtos_text, show_message, max_produtos=3):
    """Extrai preços de uma lista de produtos"""
    show_message("🔄 Iniciando extração de preços...")
    
    # Parse da lista de produtos
    linhas = produtos_text.strip().split('\n')
    urls_produtos = []
    
    for linha in linhas:
        linha = linha.strip()
        if linha.startswith('http') and '/produto' in linha:
            # Filtra URLs que não sejam apenas diretórios
            if not linha.endswith('/produtos/') and not linha.endswith('/br/produtos/'):
                urls_produtos.append(linha)
    
    show_message(f"📦 Encontrados {len(urls_produtos)} produtos válidos para extrair preços")
    
    # Limita quantidade para teste
    if len(urls_produtos) > max_produtos:
        urls_produtos = urls_produtos[:max_produtos]
        show_message(f"⚠️ Limitando a {max_produtos} produtos para teste detalhado")
    
    resultados = []
    resultados.append("=== PREÇOS EXTRAÍDOS ===\n")
    
    for i, url in enumerate(urls_produtos):
        show_message(f"🔍 Processando {i+1}/{len(urls_produtos)}: {url}")
        preco = extrair_preco_produto(url, show_message)
        
        # Extrai nome do produto da URL
        nome_produto = url.split('/')[-1].replace('-', ' ').title()
        if len(nome_produto) > 60:
            nome_produto = nome_produto[:60] + "..."
        
        resultados.append(f"Produto: {nome_produto}")
        resultados.append(f"URL: {url}")
        resultados.append(f"Preço: {preco}")
        resultados.append("")
        
        show_message(f"✅ Produto {i+1} concluído: {preco}")
    
    resultado_final = "\n".join(resultados)
    
    # Salva resultado
    with open("precos_extraidos.txt", "w", encoding="utf-8") as f:
        f.write(resultado_final)
    
    show_message(f"✅ Extração de preços concluída! {len(urls_produtos)} produtos processados")
    show_message(f"💾 Arquivos de debug salvos: debug_produto.html, debug_relevant.html")
    return resultado_final