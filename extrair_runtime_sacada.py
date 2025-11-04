import httpx
from bs4 import BeautifulSoup
import json
import re

# Testar extração de __RUNTIME__
test_url = 'https://www.sacada.com/blusa-malha-amarracao-01041624-0002/p'

print(f"Testando: {test_url}\n")

resp = httpx.get(test_url, timeout=15, follow_redirects=True)
soup = BeautifulSoup(resp.text, 'html.parser')

# Encontrar __RUNTIME__
runtime_scripts = [s for s in soup.find_all('script') if '__RUNTIME__' in s.text]

if runtime_scripts:
    runtime_text = runtime_scripts[0].text
    print(f"✓ __RUNTIME__ encontrado: {len(runtime_text):,} chars\n")
    
    # Tentar extrair JSON do __RUNTIME__
    # Padrão VTEX: window.__RUNTIME__ = {...}
    try:
        # Remover "window.__RUNTIME__ = " e pegar o JSON
        start = runtime_text.index('=') + 1
        json_text = runtime_text[start:].strip()
        
        # Remover possível ; no final
        if json_text.endswith(';'):
            json_text = json_text[:-1]
        
        # Parse JSON
        runtime_data = json.loads(json_text)
        
        print("✓ JSON parseado com sucesso!")
        print(f"\nChaves principais: {list(runtime_data.keys())}")
        
        # Procurar dados do produto
        if 'page' in runtime_data:
            print(f"\n📦 Dados em 'page': {list(runtime_data['page'].keys())}")
        
        if 'query' in runtime_data:
            print(f"\n🔍 Dados em 'query': {list(runtime_data['query'].keys())}")
        
        # Procurar productName/price em qualquer lugar
        runtime_str = json.dumps(runtime_data)
        
        if 'productName' in runtime_str:
            print(f"\n✓ 'productName' encontrado no JSON")
            # Tentar extrair
            match = re.search(r'"productName"\s*:\s*"([^"]+)"', runtime_str)
            if match:
                print(f"  Nome: {match.group(1)}")
        
        if 'price' in runtime_str:
            print(f"\n✓ 'price' encontrado no JSON")
            # Tentar extrair preço
            match = re.search(r'"price"\s*:\s*([0-9.]+)', runtime_str)
            if match:
                print(f"  Preço: {match.group(1)}")
        
        # Salvar JSON completo
        with open('sacada_runtime.json', 'w', encoding='utf-8') as f:
            json.dump(runtime_data, f, indent=2, ensure_ascii=False)
        print(f"\n✓ JSON salvo em: sacada_runtime.json")
        
    except json.JSONDecodeError as e:
        print(f"✗ Erro ao parsear JSON: {e}")
        print(f"\nPrimeiros 500 chars:")
        print(json_text[:500])
    except Exception as e:
        print(f"✗ Erro: {e}")
else:
    print("✗ __RUNTIME__ não encontrado")

# Testar também se tem dados em outros scripts
print("\n" + "="*60)
print("Procurando dados em outros scripts...")
print("="*60)

all_scripts = soup.find_all('script')
for i, script in enumerate(all_scripts):
    if not script.text:
        continue
    
    if 'productName' in script.text or 'productId' in script.text:
        print(f"\n✓ Script #{i} contém dados de produto")
        print(f"  Tamanho: {len(script.text):,} chars")
        
        # Ver se é JSON-LD ou outro formato
        if script.get('type') == 'application/ld+json':
            print(f"  Tipo: JSON-LD")
        elif '__RUNTIME__' in script.text:
            print(f"  Tipo: __RUNTIME__")
        else:
            print(f"  Tipo: JavaScript genérico")
        
        # Snippet
        snippet = script.text[:200]
        print(f"  Snippet: {snippet}...")
