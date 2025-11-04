import requests
from bs4 import BeautifulSoup
import json

url = "https://artistasdomundo.com.br/kit-tempera-profissional-nevskaya-palitra-master-class-12-cores-18ml-ekaterina.html"

print(f"Testando produto: {url[:80]}...")
r = requests.get(url)
soup = BeautifulSoup(r.text, 'html.parser')

# JSON-LD
jsons = soup.find_all('script', type='application/ld+json')
print(f"\nJSON-LD scripts: {len(jsons)}")

for i, s in enumerate(jsons):
    if s.string:
        try:
            data = json.loads(s.string)
            tipo = data.get('@type', 'Unknown')
            print(f"\n{i+1}. {tipo}")
            
            if tipo == 'Product':
                print(f"   ✅ PRODUTO ENCONTRADO!")
                print(f"   Nome: {data.get('name', 'N/A')}")
                offers = data.get('offers', {})
                if isinstance(offers, dict):
                    print(f"   Preço: R$ {offers.get('price', 'N/A')}")
                print(f"   Marca: {data.get('brand', {}).get('name', 'N/A')}")
        except Exception as e:
            print(f"   Erro: {e}")

# Salvar HTML
with open('artistasdomundo_produto_kit.html', 'w', encoding='utf-8') as f:
    f.write(r.text)
print(f"\n✅ HTML salvo: artistasdomundo_produto_kit.html")
