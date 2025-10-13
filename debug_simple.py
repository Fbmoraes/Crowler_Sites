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

def safe_print(msg):
    """Print com tratamento de encoding"""
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode('ascii', 'ignore').decode('ascii'))

def test_single_product():
    """Testa um produto específico"""
    url = "https://www.gigabarato.com.br/produtos/mop-giratorio-fit-balde-8-litros-mop5010-flash-limp-15786/"
    
    safe_print("=== TESTE DE PRODUTO ESPECÍFICO ===")
    safe_print(f"URL: {url}")
    
    # 1. Faz request
    safe_print("1. Fazendo request...")
    try:
        response = httpx.get(url, timeout=15)
        response.raise_for_status()
        html = response.text
        safe_print("   Request OK")
    except Exception as e:
        safe_print(f"   Erro no request: {e}")
        return
    
    # 2. Parse HTML
    safe_print("2. Fazendo parse HTML...")
    soup = BeautifulSoup(html, "html.parser")
    
    # 3. Extrai título
    safe_print("3. Extraindo título...")
    title = soup.title.get_text() if soup.title else "Sem título"
    safe_print(f"   Título: {title}")
    
    # 4. Extrai texto da página (primeiros 500 chars)
    safe_print("4. Extraindo texto...")
    page_text = soup.get_text()[:500]
    safe_print(f"   Texto (500 chars): {page_text}")
    
    # 5. Testa Ollama
    safe_print("5. Testando Ollama...")
    prompt = f"""O produto é: Mop Giratório Fit, Balde 8 litros, MOP5010, Flash Limp ( 15786 )

Qual é a marca? Flash Limp
Qual é a categoria? Utilidades Domésticas
Qual é o resumo? Mop giratório com balde para limpeza
Qual é o nome limpo? Mop Giratório Fit, Balde 8 litros

O produto é: {title}

Qual é a marca?"""
    
    try:
        resposta = llm.invoke(prompt)
        safe_print(f"   Resposta Ollama: {resposta}")
        
        # Extrai a marca (primeira linha da resposta)
        linhas = resposta.strip().split('\n')
        if linhas:
            marca_resposta = linhas[0].strip()
            safe_print(f"   Marca identificada: {marca_resposta}")
        else:
            safe_print("   Nenhuma resposta válida")
            
    except Exception as e:
        safe_print(f"   Erro no Ollama: {e}")

if __name__ == "__main__":
    test_single_product()