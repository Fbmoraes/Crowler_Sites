"""
Diagnóstico rápido: CEB Modas e Acessórios
"""
import requests
from bs4 import BeautifulSoup

url = "https://www.cebmodaseacessorios.com.br"
print("="*60)
print("DIAGNÓSTICO: CEB MODAS E ACESSÓRIOS")
print("="*60)

try:
    print(f"\n1️⃣ Homepage: {url}")
    r = requests.get(url, timeout=15)
    print(f"   Status: {r.status_code}")
    print(f"   Tamanho: {len(r.text)} bytes")
    
    # Detectar plataforma
    text = r.text.lower()
    plataformas = {
        'vtex': 'VTEX',
        'shopify': 'Shopify', 
        'tray': 'Tray',
        'woocommerce': 'WooCommerce',
        'nuvemshop': 'Nuvemshop',
        'loja integrada': 'Loja Integrada',
        'magento': 'Magento'
    }
    
    for key, name in plataformas.items():
        if key in text:
            print(f"   ✅ Plataforma: {name}")
            break
    else:
        print(f"   ⚠️  Plataforma não identificada")
    
    # Testar sitemap
    print(f"\n2️⃣ Sitemap:")
    sitemaps = ['/sitemap.xml', '/sitemap_index.xml']
    sitemap_ok = False
    
    for sm in sitemaps:
        try:
            r2 = requests.get(f"{url}{sm}", timeout=10)
            if r2.status_code == 200:
                urls_count = r2.text.count('<loc>')
                print(f"   ✅ {sm} - {urls_count} URLs")
                sitemap_ok = True
                break
        except:
            pass
    
    if not sitemap_ok:
        print(f"   ❌ Nenhum sitemap encontrado")
    
    # Buscar produtos na homepage
    print(f"\n3️⃣ Produtos na homepage:")
    soup = BeautifulSoup(r.text, 'html.parser')
    
    links = []
    for a in soup.find_all('a', href=True):
        href = a['href']
        # Padrões comuns
        if any(x in href.lower() for x in ['/produto/', '/product/', '/p/', '/item/']):
            if href.startswith('http'):
                links.append(href)
            elif href.startswith('/'):
                links.append(url + href)
    
    print(f"   Links de produtos: {len(links)}")
    
    if links:
        # Remover duplicatas
        links = list(set(links))
        print(f"   Links únicos: {len(links)}")
        
        # Testar primeiro produto
        print(f"\n4️⃣ Testando produto: {links[0][:80]}...")
        r3 = requests.get(links[0], timeout=10)
        print(f"   Status: {r3.status_code}")
        
        soup2 = BeautifulSoup(r3.text, 'html.parser')
        
        # JSON-LD
        jsons = soup2.find_all('script', type='application/ld+json')
        print(f"   JSON-LD scripts: {len(jsons)}")
        
        if jsons:
            import json
            for s in jsons:
                if s.string:
                    try:
                        data = json.loads(s.string)
                        tipo = data.get('@type', 'Unknown')
                        
                        if tipo == 'Product':
                            print(f"   ✅ Product JSON-LD encontrado!")
                            print(f"      Nome: {data.get('name', 'N/A')[:60]}")
                            offers = data.get('offers', {})
                            if isinstance(offers, dict):
                                preco = offers.get('price', 'N/A')
                            elif isinstance(offers, list) and offers:
                                preco = offers[0].get('price', 'N/A')
                            else:
                                preco = 'N/A'
                            print(f"      Preço: R$ {preco}")
                    except Exception as e:
                        pass
        
        # Verificar preço no HTML
        price_count = r3.text.count('R$')
        print(f"   Ocorrências de 'R$': {price_count}")
        
        # Salvar para análise
        with open('cebmodas_produto.html', 'w', encoding='utf-8') as f:
            f.write(r3.text)
        print(f"   ✅ HTML salvo: cebmodas_produto.html")
    else:
        print(f"   ⚠️  Nenhum produto encontrado na homepage")
        # Salvar homepage
        with open('cebmodas_home.html', 'w', encoding='utf-8') as f:
            f.write(r.text)
        print(f"   ✅ Homepage salva: cebmodas_home.html")
    
except Exception as e:
    print(f"❌ Erro: {e}")
