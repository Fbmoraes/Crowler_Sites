import httpx
from bs4 import BeautifulSoup
import json

url = 'https://www.sacada.com/blusa-malha-amarracao-01041624-0002/p'
resp = httpx.get(url, timeout=15)
soup = BeautifulSoup(resp.text, 'html.parser')

# Encontrar script com Apollo Cache
scripts = [s for s in soup.find_all('script') if 'Product:' in s.text]
data = json.loads(scripts[0].text)

print(f"Total de chaves no Apollo Cache: {len(data.keys())}\n")

# Procurar chaves de preço
price_keys = [k for k in data.keys() if 'price' in k.lower()]
print(f"Chaves com 'price': {len(price_keys)}")
for key in price_keys[:10]:
    print(f"  - {key}")
    print(f"    Valor: {data[key]}")

# Procurar chave do produto principal
product_key = 'Product:blusa-malha-amarracao-01041624-0002'
if product_key in data:
    product = data[product_key]
    print(f"\n📦 PRODUTO PRINCIPAL:")
    print(f"  Nome: {product.get('productName')}")
    print(f"  Marca: {product.get('brand')}")
    print(f"  ID: {product.get('productId')}")
    
    # Ver estrutura de priceRange
    price_range = product.get('priceRange')
    print(f"\n  priceRange: {price_range}")
    
    # Buscar a chave referenciada
    if isinstance(price_range, dict) and 'id' in price_range:
        price_key = price_range['id']
        print(f"\n  Buscando chave: {price_key}")
        
        if price_key in data:
            price_data = data[price_key]
            print(f"  ✓ Encontrado: {price_data}")
            
            # Navegar pelas sub-chaves
            if 'sellingPrice' in price_data and isinstance(price_data['sellingPrice'], dict):
                selling_key = price_data['sellingPrice']['id']
                if selling_key in data:
                    print(f"\n  💰 Preço de Venda: {data[selling_key]}")
            
            if 'listPrice' in price_data and isinstance(price_data['listPrice'], dict):
                list_key = price_data['listPrice']['id']
                if list_key in data:
                    print(f"  💵 Preço de Lista: {data[list_key]}")

# Ver estrutura de items
if product_key in data:
    product = data[product_key]
    items = product.get('items', [])
    print(f"\n📋 ITEMS: {len(items)}")
    
    if items:
        for idx, item in enumerate(items):
            print(f"\n  Item {idx+1}:")
            if isinstance(item, dict) and 'id' in item:
                item_key = item['id']
                if item_key in data:
                    item_data = data[item_key]
                    print(f"    Chave: {item_key}")
                    print(f"    Dados: {json.dumps(item_data, indent=6, ensure_ascii=False)[:300]}")
