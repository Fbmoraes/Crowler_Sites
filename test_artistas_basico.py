"""
Teste rápido: conseguimos extrair produtos do Artistas do Mundo?
"""
import requests
from bs4 import BeautifulSoup
import json

url = "https://www.artistasdomundo.com.br"

print("="*60)
print("TESTE BÁSICO: ARTISTAS DO MUNDO (VTEX)")
print("="*60)

# 1. Buscar produtos na homepage
print(f"\n1️⃣ Buscando produtos na homepage...")
r = requests.get(url, timeout=15)
soup = BeautifulSoup(r.text, 'html.parser')

# Procurar links de produtos
produto_links = []
for a in soup.find_all('a', href=True):
    href = a['href']
    # VTEX geralmente usa /p/ para produtos
    if '/p/' in href or '/produto' in href.lower():
        if href.startswith('http'):
            produto_links.append(href)
        elif href.startswith('/'):
            produto_links.append(url + href)

print(f"   Links encontrados: {len(produto_links)}")
if produto_links:
    print(f"   Exemplos:")
    for link in produto_links[:5]:
        print(f"      {link}")
else:
    print("   ⚠️  Nenhum link de produto encontrado")

# 2. Procurar JSON com produtos
print(f"\n2️⃣ Procurando JSON com produtos...")
scripts = soup.find_all('script')
for script in scripts:
    if script.string and 'product' in script.string.lower():
        # Tentar extrair JSON
        try:
            # VTEX às vezes tem window.__RUNTIME__ ou window.__STATE__
            if '__RUNTIME__' in script.string or '__STATE__' in script.string:
                print(f"   ✅ VTEX Runtime encontrado!")
                break
        except:
            pass

# 3. Testar um produto
if produto_links:
    print(f"\n3️⃣ Testando produto: {produto_links[0]}")
    try:
        r = requests.get(produto_links[0], timeout=15)
        soup = BeautifulSoup(r.text, 'html.parser')
        
        # Procurar JSON-LD
        json_lds = soup.find_all('script', type='application/ld+json')
        print(f"   JSON-LD scripts: {len(json_lds)}")
        
        for script in json_lds:
            try:
                data = json.loads(script.string)
                if data.get('@type') == 'Product':
                    print(f"   ✅ Product JSON-LD encontrado!")
                    print(f"      Nome: {data.get('name', 'N/A')}")
                    offers = data.get('offers', {})
                    if isinstance(offers, dict):
                        print(f"      Preço: {offers.get('price', 'N/A')}")
            except:
                pass
        
        # Salvar HTML
        with open('artistasdomundo_produto_real.html', 'w', encoding='utf-8') as f:
            f.write(r.text)
        print(f"   ✅ HTML salvo: artistasdomundo_produto_real.html")
        
    except Exception as e:
        print(f"   ❌ Erro: {e}")
