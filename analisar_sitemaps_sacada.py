import httpx
from bs4 import BeautifulSoup
import json

print("=== ANÁLISE SITEMAPS SACADA ===\n")

# Testar todos os sitemaps de produto
sitemaps = [
    'https://www.sacada.com/sitemap/sitemap-product-1.xml',
    'https://www.sacada.com/sitemap/sitemap-product-2.xml',
    'https://www.sacada.com/sitemap/sitemap-product-3.xml',
]

for sitemap_url in sitemaps:
    print(f"\n{'='*60}")
    print(f"SITEMAP: {sitemap_url.split('/')[-1]}")
    print('='*60)
    
    try:
        resp = httpx.get(sitemap_url, timeout=15)
        
        if resp.status_code != 200:
            print(f"✗ Status: {resp.status_code}")
            continue
            
        soup = BeautifulSoup(resp.text, 'xml')
        urls = [loc.text for loc in soup.find_all('loc')]
        
        print(f"✓ Status: {resp.status_code}")
        print(f"✓ Total URLs: {len(urls)}")
        
        if urls:
            print(f"\n📋 Primeiras 5 URLs:")
            for url in urls[:5]:
                print(f"  {url}")
            
            # Testar primeiro produto
            print(f"\n🔍 Testando primeiro produto:")
            test_url = urls[0]
            print(f"  URL: {test_url}")
            
            try:
                prod_resp = httpx.get(test_url, timeout=15, follow_redirects=True)
                print(f"  ✓ Status: {prod_resp.status_code}")
                print(f"  ✓ Final URL: {prod_resp.url}")
                print(f"  ✓ Tamanho: {len(prod_resp.text):,} bytes")
                
                # Verificar se tem conteúdo
                prod_soup = BeautifulSoup(prod_resp.text, 'html.parser')
                
                # Procurar indicadores de produto ativo
                title = prod_soup.find('title')
                h1 = prod_soup.find('h1')
                price = prod_soup.find(class_=lambda x: x and 'price' in x.lower() if x else False)
                
                print(f"  ✓ <title>: {title.text[:50] if title else 'N/A'}...")
                print(f"  ✓ <h1>: {h1.text[:50] if h1 else 'N/A'}...")
                print(f"  ✓ Elemento preço: {'Sim' if price else 'Não'}")
                
                # Verificar se tem __RUNTIME__ (dados hidratados)
                runtime = [s for s in prod_soup.find_all('script') if '__RUNTIME__' in s.text]
                if runtime:
                    print(f"  ✓ __RUNTIME__ encontrado: {len(runtime[0].text):,} chars")
                    
                    # Tentar extrair dados básicos do __RUNTIME__
                    runtime_text = runtime[0].text
                    if '"productName"' in runtime_text:
                        start = runtime_text.index('"productName"') + 14
                        end = runtime_text.index('"', start + 1)
                        name = runtime_text[start:end]
                        print(f"  ✓ Nome no __RUNTIME__: {name[:50]}...")
                    
                    if '"price":' in runtime_text:
                        print(f"  ✓ Preço encontrado no __RUNTIME__")
                else:
                    print(f"  ✗ __RUNTIME__ NÃO encontrado")
                    
            except Exception as e:
                print(f"  ✗ Erro ao testar produto: {e}")
        
    except Exception as e:
        print(f"✗ Erro: {e}")

print("\n" + "="*60)
print("CONCLUSÃO:")
print("="*60)
print("Verificar qual sitemap tem produtos ATIVOS com dados completos.")
