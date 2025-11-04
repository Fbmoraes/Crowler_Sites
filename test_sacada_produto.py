"""
Teste completo de produto Sacada
"""
import httpx
from bs4 import BeautifulSoup
import json

produto_url = "https://www.sacada.com/look-13-inverno-17/p"

print("="*60)
print(f"TESTANDO PRODUTO: {produto_url}")
print("="*60)

response = httpx.get(produto_url, timeout=15, follow_redirects=True)
print(f"\nStatus: {response.status_code}")
print(f"URL final: {response.url}")
print(f"Tamanho: {len(response.content)} bytes")

soup = BeautifulSoup(response.text, 'html.parser')

# 1. JSON-LD
print("\n" + "="*60)
print("1. JSON-LD")
print("="*60)

json_ld_scripts = soup.find_all('script', type='application/ld+json')
print(f"Scripts encontrados: {len(json_ld_scripts)}")

if json_ld_scripts:
    for i, script in enumerate(json_ld_scripts):
        try:
            data = json.loads(script.string)
            print(f"\nScript {i+1}:")
            print(f"  @type: {data.get('@type', 'N/A')}")
            
            if data.get('@type') == 'Product':
                print(f"  ✅ PRODUTO ENCONTRADO!")
                print(f"  Nome: {data.get('name', 'N/A')}")
                print(f"  Preço: {data.get('offers', {}).get('price', 'N/A')}")
                print(f"  Preço Alto: {data.get('offers', {}).get('highPrice', 'N/A')}")
                print(f"  Marca: {data.get('brand', 'N/A')}")
                print(f"  SKU: {data.get('sku', 'N/A')}")
                print(f"  Disponível: {data.get('offers', {}).get('availability', 'N/A')}")
                
                # Mostra JSON completo
                print(f"\n  JSON completo:")
                print(json.dumps(data, indent=2, ensure_ascii=False)[:500])
        except Exception as e:
            print(f"  ❌ Erro ao parsear script {i+1}: {e}")

# 2. OpenGraph
print("\n" + "="*60)
print("2. OpenGraph")
print("="*60)

og_tags = soup.find_all('meta', property=lambda x: x and x.startswith('og:'))
for tag in og_tags[:10]:
    print(f"  {tag.get('property')}: {tag.get('content', 'N/A')[:60]}")

# 3. HTML direto
print("\n" + "="*60)
print("3. HTML Direto")
print("="*60)

h1 = soup.find('h1')
print(f"<h1>: {h1.text.strip() if h1 else 'N/A'}")

title = soup.find('title')
print(f"<title>: {title.text.strip() if title else 'N/A'}")

# Procura por classes de preço comuns
price_selectors = [
    'span.sellingPrice',
    'span.bestPrice',
    'div.product-price',
    '[class*="price"]',
]

print(f"\nBuscando preços:")
for selector in price_selectors:
    elementos = soup.select(selector)
    if elementos:
        print(f"  {selector}: {len(elementos)} elementos")
        for el in elementos[:2]:
            print(f"    - {el.text.strip()[:60]}")

# 4. Salva HTML
print("\n" + "="*60)
print("4. Salvando HTML")
print("="*60)

with open('sacada_produto_debug.html', 'w', encoding='utf-8') as f:
    f.write(response.text)
print("✅ HTML salvo: sacada_produto_debug.html")

print("\n" + "="*60)
print("DIAGNÓSTICO CONCLUÍDO")
print("="*60)
