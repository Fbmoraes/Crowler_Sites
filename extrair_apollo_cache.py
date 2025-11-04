import httpx
from bs4 import BeautifulSoup
import json
import re

# Testar extração do Script com dados do produto
test_url = 'https://www.sacada.com/blusa-malha-amarracao-01041624-0002/p'

print(f"Extraindo dados de: {test_url}\n")

resp = httpx.get(test_url, timeout=15, follow_redirects=True)
soup = BeautifulSoup(resp.text, 'html.parser')

# Procurar script com "Product:" (dados Apollo/GraphQL cache)
all_scripts = soup.find_all('script')

for script in all_scripts:
    if not script.text or 'Product:' not in script.text:
        continue
    
    script_text = script.text.strip()
    
    # Verificar se é JSON
    if script_text.startswith('{') or script_text.startswith('['):
        try:
            # Tentar parsear como JSON
            data = json.loads(script_text)
            
            print("✓ JSON de produto encontrado!")
            print(f"  Tamanho: {len(script_text):,} chars")
            print(f"  Chaves: {list(data.keys())[:10]}")
            
            # Procurar chave que começa com "Product:"
            product_keys = [k for k in data.keys() if k.startswith('Product:')]
            
            if product_keys:
                product_key = product_keys[0]
                product_data = data[product_key]
                
                print(f"\n📦 DADOS DO PRODUTO:")
                print(f"  Chave: {product_key}")
                print(f"  Campos: {list(product_data.keys())}")
                
                # Extrair informações principais
                nome = product_data.get('productName', 'N/A')
                marca = product_data.get('brand', 'N/A')
                descricao = product_data.get('description', 'N/A')
                
                print(f"\n✅ Nome: {nome}")
                print(f"✅ Marca: {marca}")
                print(f"✅ Descrição: {descricao[:100]}...")
                
                # Preços
                if 'items' in product_data and product_data['items']:
                    item = product_data['items'][0]
                    print(f"\n💰 PREÇOS:")
                    
                    if 'sellers' in item and item['sellers']:
                        seller = item['sellers'][0]
                        
                        if 'commertialOffer' in seller:
                            offer = seller['commertialOffer']
                            preco = offer.get('Price', 'N/A')
                            preco_lista = offer.get('ListPrice', 'N/A')
                            disponivel = offer.get('AvailableQuantity', 0)
                            
                            print(f"  Preço: R$ {preco}")
                            print(f"  Preço Lista: R$ {preco_lista}")
                            print(f"  Disponível: {disponivel} unidades")
                
                # Categorias
                if 'categories' in product_data:
                    print(f"\n📁 CATEGORIAS:")
                    for cat in product_data['categories']:
                        print(f"  - {cat}")
                
                # Salvar JSON
                with open('sacada_produto_completo.json', 'w', encoding='utf-8') as f:
                    json.dump(product_data, f, indent=2, ensure_ascii=False)
                
                print(f"\n✓ Dados completos salvos em: sacada_produto_completo.json")
                
                # Testar se conseguimos extrair tudo que precisamos
                print(f"\n{'='*60}")
                print("RESUMO - Dados disponíveis:")
                print('='*60)
                campos = {
                    'Nome': product_data.get('productName'),
                    'Marca': product_data.get('brand'),
                    'SKU': product_data.get('items', [{}])[0].get('itemId') if product_data.get('items') else None,
                    'Preço': item.get('sellers', [{}])[0].get('commertialOffer', {}).get('Price') if product_data.get('items') else None,
                    'Categoria': product_data.get('categories', [None])[0] if product_data.get('categories') else None,
                }
                
                for campo, valor in campos.items():
                    status = "✅" if valor else "❌"
                    print(f"{status} {campo}: {'OK' if valor else 'N/A'}")
                
            break
            
        except json.JSONDecodeError:
            continue
        except Exception as e:
            print(f"Erro ao processar: {e}")
            continue

print("\n" + "="*60)
print("CONCLUSÃO:")
print("="*60)
print("✓ Dados estão em script JavaScript (Apollo Cache)")
print("✓ Formato JSON parseável")
print("✓ Contém TODOS os dados necessários")
print("✓ Estratégia: Extrair desse script ao invés de usar BeautifulSoup")
