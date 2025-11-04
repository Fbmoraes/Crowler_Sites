"""
Teste diagnóstico: Sacada
"""
import httpx
import re
from bs4 import BeautifulSoup
import json

url = "https://www.sacada.com"

# 1. Testa sitemap
print("=" * 60)
print("TESTANDO SITEMAP")
print("=" * 60)

sitemap_url = f"{url}/sitemap.xml"
try:
    r = httpx.get(sitemap_url, follow_redirects=True, timeout=10)
    print(f"Status: {r.status_code}")
    
    if r.status_code == 200:
        urls = re.findall(r'<loc>(.*?)</loc>', r.text)
        print(f"Total URLs: {len(urls)}")
        
        print("\nPrimeiras 10 URLs:")
        for url_sitemap in urls[:10]:
            print(f"  - {url_sitemap}")
        
        # É índice?
        if any('.xml' in u for u in urls):
            print("\n⚠️ É um ÍNDICE de sitemaps!")
            print("Sitemaps filhos:")
            for u in urls:
                if '.xml' in u:
                    print(f"  - {u}")
            
            # Tenta expandir primeiro filho
            if urls:
                primeiro = urls[0]
                print(f"\nExpandindo primeiro sitemap: {primeiro}")
                r2 = httpx.get(primeiro, timeout=10)
                urls_filho = re.findall(r'<loc>(.*?)</loc>', r2.text)
                print(f"  URLs no filho: {len(urls_filho)}")
                print("  Exemplos:")
                for u in urls_filho[:5]:
                    print(f"    {u}")
        else:
            # Analisa estrutura
            niveis = {}
            for u in urls:
                nivel = u.count('/')
                niveis[nivel] = niveis.get(nivel, 0) + 1
            
            print("\nDistribuição por níveis:")
            for n in sorted(niveis.keys()):
                print(f"  Nível {n}: {niveis[n]} URLs")

except Exception as e:
    print(f"Erro: {e}")

# 2. Testa homepage
print("\n" + "=" * 60)
print("TESTANDO HOMEPAGE")
print("=" * 60)

try:
    r = httpx.get(url, follow_redirects=True, timeout=10)
    soup = BeautifulSoup(r.text, 'html.parser')
    
    print(f"Status: {r.status_code}")
    print(f"Total de links: {len(soup.find_all('a', href=True))}")
    
    # Busca produtos
    links = soup.find_all('a', href=True)
    produtos = []
    for link in links:
        href = link.get('href')
        if href.startswith('/') and href.count('/') >= 2:
            if 'produto' in href or href.count('/') >= 3:
                produtos.append(url + href)
        elif href.startswith('http') and 'sacada' in href:
            if href.count('/') >= 4:
                produtos.append(href)
    
    print(f"\nProdutos potenciais: {len(set(produtos))}")
    if produtos:
        print("Exemplos:")
        for p in list(set(produtos))[:10]:
            print(f"  {p}")

except Exception as e:
    print(f"Erro: {e}")

# 3. Testa produto específico
print("\n" + "=" * 60)
print("TESTANDO PRODUTO ESPECÍFICO")
print("=" * 60)

# Pega primeira URL de produto do sitemap ou homepage
produto_url = None

# Tenta do sitemap
try:
    r = httpx.get(f"{url}/sitemap.xml", follow_redirects=True, timeout=10)
    if r.status_code == 200:
        urls = re.findall(r'<loc>(.*?)</loc>', r.text)
        
        # Se é índice, pega primeiro sitemap filho
        if any('.xml' in u for u in urls):
            r2 = httpx.get(urls[0], timeout=10)
            urls = re.findall(r'<loc>(.*?)</loc>', r2.text)
        
        # Filtra produtos
        for u in urls:
            if u.count('/') >= 4 and 'categoria' not in u and 'collection' not in u:
                produto_url = u
                break
except:
    pass

if produto_url:
    print(f"URL: {produto_url}\n")
    
    try:
        r = httpx.get(produto_url, follow_redirects=True, timeout=15)
        print(f"Status: {r.status_code}")
        print(f"Tamanho: {len(r.content)} bytes")
        
        soup = BeautifulSoup(r.text, 'html.parser')
        
        # JSON-LD
        print("\n📦 JSON-LD:")
        json_ld = soup.find_all('script', type='application/ld+json')
        print(f"   Scripts: {len(json_ld)}")
        
        if json_ld:
            for i, script in enumerate(json_ld):
                try:
                    data = json.loads(script.string)
                    tipo = data.get('@type', 'Unknown')
                    print(f"   Script {i+1}: @type = {tipo}")
                    
                    if tipo == 'Product':
                        print(f"      ✅ Nome: {data.get('name', 'N/A')}")
                        print(f"      ✅ Preço: {data.get('offers', {}).get('price', 'N/A')}")
                        print(f"      ✅ Marca: {data.get('brand', {}).get('name', 'N/A')}")
                except Exception as e:
                    print(f"   ❌ Erro ao parsear: {e}")
        
        # OpenGraph
        print("\n🔖 OpenGraph:")
        og_title = soup.find('meta', property='og:title')
        og_price = soup.find('meta', property='og:price:amount')
        print(f"   og:title: {og_title['content'] if og_title else 'N/A'}")
        print(f"   og:price:amount: {og_price['content'] if og_price else 'N/A'}")
        
        # HTML direto
        print("\n📄 HTML direto:")
        h1 = soup.find('h1')
        print(f"   <h1>: {h1.text.strip()[:60] if h1 else 'N/A'}")
        
        # Busca preços no texto
        precos = re.findall(r'R\$\s*(\d{1,3}(?:\.\d{3})*(?:,\d{2}))', r.text)
        print(f"   Preços encontrados: {len(precos)}")
        if precos:
            print(f"   Exemplos: {precos[:3]}")
        
        # Salva HTML
        print(f"\n💾 Salvando HTML...")
        with open('sacada_produto_debug.html', 'w', encoding='utf-8') as f:
            f.write(r.text)
        print(f"   ✅ Salvo: sacada_produto_debug.html")
        
    except Exception as e:
        print(f"❌ Erro: {e}")
        import traceback
        traceback.print_exc()
else:
    print("❌ Nenhuma URL de produto encontrada")
