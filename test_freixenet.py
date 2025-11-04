"""
Teste diagnóstico: Freixenet
"""
import httpx
import re
from bs4 import BeautifulSoup

url = "https://www.freixenet.com.br"

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
        
        # Analisa estrutura
        print("\nPrimeiras 10 URLs:")
        for url_sitemap in urls[:10]:
            print(f"  - {url_sitemap}")
        
        # Conta níveis
        niveis = {}
        for u in urls:
            nivel = u.count('/')
            niveis[nivel] = niveis.get(nivel, 0) + 1
        
        print("\nDistribuição por níveis:")
        for n in sorted(niveis.keys()):
            print(f"  Nível {n}: {niveis[n]} URLs")
        
        # Testa padrões
        print("\nTestando padrões:")
        
        # WordPress
        padrao_wp = re.compile(r'/produtos?/[^/]+-\d+/?$')
        matches_wp = [u for u in urls if padrao_wp.search(u)]
        print(f"  WordPress (/produto/nome-123): {len(matches_wp)} matches")
        
        # VTEX
        padrao_vtex = re.compile(r'/p(roduto)?/[^/]+/\d+')
        matches_vtex = [u for u in urls if padrao_vtex.search(u)]
        print(f"  VTEX (/p/nome/123): {len(matches_vtex)} matches")
        
        # Nível 3
        padrao_n3 = re.compile(r'^https?://[^/]+/[^/]+/[^/]+/[^/]+/?$')
        matches_n3 = [u for u in urls if padrao_n3.search(u)]
        print(f"  Nível 3 (dominio/a/b/c): {len(matches_n3)} matches")
        
        # Busca padrões customizados
        print("\nBuscando padrões customizados:")
        paths = [u.split('/')[-1] for u in urls if u.count('/') >= 4]
        
        # Padrão código numérico
        with_numbers = [p for p in paths if re.search(r'\d{3,}', p)]
        print(f"  Com códigos numéricos (3+ dígitos): {len(with_numbers)}")
        if with_numbers:
            print(f"    Exemplos: {with_numbers[:3]}")
        
        # Padrão /loja/ ou /shop/
        with_loja = [u for u in urls if '/loja/' in u or '/shop/' in u or '/produto/' in u]
        print(f"  Com /loja/ ou /shop/ ou /produto/: {len(with_loja)}")
        if with_loja:
            print(f"    Exemplos:")
            for ex in with_loja[:3]:
                print(f"      {ex}")

except Exception as e:
    print(f"Erro: {e}")

# 2. Testa navegação na homepage
print("\n" + "=" * 60)
print("TESTANDO HOMEPAGE")
print("=" * 60)

try:
    r = httpx.get(url, follow_redirects=True, timeout=10)
    soup = BeautifulSoup(r.text, 'html.parser')
    
    # Busca produtos na homepage
    print("\nBuscando produtos na homepage...")
    links = soup.find_all('a', href=True)
    print(f"Total de links: {len(links)}")
    
    # Filtra por níveis
    produtos_potenciais = []
    for link in links:
        href = link.get('href')
        if href.startswith('http') and 'freixenet' in href:
            niveis = href.count('/')
            if niveis >= 4:
                produtos_potenciais.append(href)
        elif href.startswith('/'):
            full_url = url + href
            niveis = full_url.count('/')
            if niveis >= 4:
                produtos_potenciais.append(full_url)
    
    print(f"\nURLs com 4+ níveis (produtos potenciais): {len(produtos_potenciais)}")
    if produtos_potenciais:
        print("Exemplos:")
        for p in list(set(produtos_potenciais))[:10]:
            print(f"  {p}")
    
    # Busca categorias
    print("\nBuscando categorias...")
    categorias = []
    for link in links:
        texto = link.get_text(strip=True)
        href = link.get('href')
        
        if not texto or len(texto) < 3:
            continue
        
        if any(x in texto.lower() for x in ['contato', 'sobre', 'login', 'cart', 'conta']):
            continue
        
        if href.startswith('/'):
            full_url = url + href
            niveis = full_url.count('/')
            if niveis == 4:  # Nível de categoria
                categorias.append({
                    'nome': texto,
                    'url': full_url
                })
    
    # Remove duplicatas
    cats_unicas = []
    urls_vistas = set()
    for cat in categorias:
        if cat['url'] not in urls_vistas:
            urls_vistas.add(cat['url'])
            cats_unicas.append(cat)
    
    print(f"Categorias encontradas: {len(cats_unicas)}")
    for cat in cats_unicas[:10]:
        print(f"  - {cat['nome']}: {cat['url']}")

except Exception as e:
    print(f"Erro: {e}")

# 3. Testa uma categoria específica
print("\n" + "=" * 60)
print("TESTANDO CATEGORIA ESPECÍFICA")
print("=" * 60)

# Tenta categoria comum de vinhos
categorias_teste = [
    f"{url}/espumantes",
    f"{url}/vinhos",
    f"{url}/loja",
    f"{url}/produtos",
]

for cat_url in categorias_teste:
    try:
        print(f"\nTestando: {cat_url}")
        r = httpx.get(cat_url, follow_redirects=True, timeout=10)
        print(f"Status: {r.status_code}")
        
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, 'html.parser')
            links = soup.find_all('a', href=True)
            
            produtos = []
            for link in links:
                href = link.get('href')
                if href.startswith('/') and href.count('/') >= 3:
                    produtos.append(url + href)
                elif href.startswith('http') and 'freixenet' in href and href.count('/') >= 4:
                    produtos.append(href)
            
            print(f"  Produtos encontrados: {len(set(produtos))}")
            if produtos:
                print("  Exemplos:")
                for p in list(set(produtos))[:5]:
                    print(f"    {p}")
    except:
        print(f"  Erro ao acessar")
