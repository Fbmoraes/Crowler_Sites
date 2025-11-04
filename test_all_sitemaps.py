import httpx
from bs4 import BeautifulSoup

# Testar cada sitemap de produto
for i in range(4):
    sitemap_url = f'https://www.sacada.com/sitemap/product-{i}.xml'
    print(f"\n{'='*60}")
    print(f"Sitemap product-{i}")
    print('='*60)
    
    try:
        resp = httpx.get(sitemap_url, timeout=20)
        print(f"Status: {resp.status_code}")
        
        if resp.status_code == 200:
            print(f"Size: {len(resp.text):,} bytes")
            soup = BeautifulSoup(resp.text, 'xml')
            urls = [loc.text for loc in soup.find_all('loc')]
            print(f"Total URLs: {len(urls)}")
            
            if urls:
                print(f"\nPrimeiras 3 URLs:")
                for url in urls[:3]:
                    print(f"  {url}")
                
                # Testar primeiro produto
                print(f"\nTestando primeiro produto:")
                test_url = urls[0]
                prod_resp = httpx.get(test_url, timeout=15, follow_redirects=True)
                print(f"  Status: {prod_resp.status_code}")
                print(f"  Size: {len(prod_resp.text):,} bytes")
                
                soup2 = BeautifulSoup(prod_resp.text, 'html.parser')
                title = soup2.find('title')
                print(f"  Title: {title.text if title else 'N/A'}")
                
                # Verificar __RUNTIME__
                runtime = [s for s in soup2.find_all('script') if '__RUNTIME__' in s.text]
                if runtime:
                    print(f"  ✓ Tem __RUNTIME__ com {len(runtime[0].text):,} chars")
                    
                    # Procurar productName
                    rt_text = runtime[0].text
                    if '"productName"' in rt_text:
                        try:
                            idx = rt_text.index('"productName"')
                            snippet = rt_text[idx:idx+200]
                            print(f"  ✓ productName encontrado: {snippet[:100]}...")
                        except:
                            pass
                else:
                    print(f"  ✗ Sem __RUNTIME__")
                
    except Exception as e:
        print(f"✗ Erro: {e}")
