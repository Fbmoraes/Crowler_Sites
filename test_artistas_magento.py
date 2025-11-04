"""
Teste: Artistas do Mundo é Magento - vamos tentar a API REST
"""
import requests
import json

base_url = "https://www.artistasdomundo.com.br"

print("="*60)
print("TESTE: ARTISTAS DO MUNDO (MAGENTO)")
print("="*60)

# Magento REST API endpoints comuns
endpoints = [
    "/rest/V1/products",
    "/rest/default/V1/products",
    "/rest/all/V1/products",
    "/api/rest/products",
    "/rest/V1/categories"
]

print("\n1️⃣ Testando API REST endpoints...")
for endpoint in endpoints:
    url = base_url + endpoint
    try:
        r = requests.get(url, timeout=10, params={'searchCriteria[pageSize]': 5})
        if r.status_code == 200:
            print(f"   ✅ {endpoint} - Status: {r.status_code}")
            try:
                data = r.json()
                print(f"      Resposta JSON: {len(str(data))} bytes")
                if 'items' in data:
                    print(f"      Produtos encontrados: {len(data['items'])}")
                    if data['items']:
                        prod = data['items'][0]
                        print(f"      Exemplo: {prod.get('name', 'N/A')} - R$ {prod.get('price', 'N/A')}")
                break
            except:
                print(f"      ⚠️  Resposta não é JSON válido")
        elif r.status_code == 401:
            print(f"   🔒 {endpoint} - Requer autenticação")
        else:
            print(f"   ❌ {endpoint} - Status: {r.status_code}")
    except Exception as e:
        print(f"   ❌ {endpoint} - Erro: {e}")

# Tentar buscar via search
print("\n2️⃣ Testando busca...")
try:
    r = requests.get(f"{base_url}/catalogsearch/result/", params={'q': 'tinta'}, timeout=10)
    if r.status_code == 200:
        print(f"   ✅ Página de busca funciona")
        with open('artistasdomundo_busca.html', 'w', encoding='utf-8') as f:
            f.write(r.text)
        print(f"   ✅ HTML salvo: artistasdomundo_busca.html")
        
        # Procurar produtos na página de busca
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(r.text, 'html.parser')
        
        # Magento geralmente usa class product-item
        produtos = soup.find_all('div', class_='product-item')
        print(f"   Produtos encontrados: {len(produtos)}")
        
        # Procurar links
        links = soup.find_all('a', class_='product-item-link')
        if links:
            print(f"   Links de produtos: {len(links)}")
            print(f"   Exemplo: {links[0].get('href')}")
except Exception as e:
    print(f"   ❌ Erro: {e}")

print("\n3️⃣ Tentando catálogo...")
try:
    r = requests.get(f"{base_url}/catalog/product/", timeout=10)
    print(f"   Status: {r.status_code}")
except:
    pass
