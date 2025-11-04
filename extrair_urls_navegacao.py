"""
Extrai URLs de produtos navegando pela homepage do Matcon Casa
"""
from playwright.sync_api import sync_playwright
import time

print("🌐 Abrindo Matcon Casa e extraindo produtos...")

produtos_urls = set()

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    
    # Navega para homepage
    print("📄 Carregando homepage...")
    page.goto("https://www.matconcasa.com.br/", wait_until='networkidle', timeout=30000)
    page.wait_for_timeout(3000)
    
    # Extrai todos os links que parecem produtos
    print("🔍 Extraindo links de produtos...")
    links = page.evaluate('''
        () => {
            const links = document.querySelectorAll('a[href*="/produto/"]');
            return Array.from(links).map(a => a.href);
        }
    ''')
    
    for link in links:
        if link and 'matconcasa.com.br' in link:
            produtos_urls.add(link)
    
    print(f"✅ Encontrados {len(produtos_urls)} URLs na homepage")
    
    # Tenta navegar para algumas categorias principais
    categorias = [
        "https://www.matconcasa.com.br/produto/",
        "https://www.matconcasa.com.br/produto/casa",
        "https://www.matconcasa.com.br/produto/cozinha",
        "https://www.matconcasa.com.br/produto/banheiro",
    ]
    
    for i, cat_url in enumerate(categorias, 1):
        try:
            print(f"\n📁 Categoria {i}/{len(categorias)}: {cat_url}")
            page.goto(cat_url, wait_until='networkidle', timeout=30000)
            page.wait_for_timeout(2000)
            
            # Scroll para carregar lazy loading
            for _ in range(3):
                page.evaluate('window.scrollBy(0, window.innerHeight)')
                page.wait_for_timeout(1000)
            
            links_cat = page.evaluate('''
                () => {
                    const links = document.querySelectorAll('a[href*="/produto/"]');
                    return Array.from(links).map(a => a.href);
                }
            ''')
            
            novos = 0
            for link in links_cat:
                if link and 'matconcasa.com.br' in link and link not in produtos_urls:
                    produtos_urls.add(link)
                    novos += 1
            
            print(f"  ✓ {novos} novos produtos encontrados (total: {len(produtos_urls)})")
            
            if len(produtos_urls) >= 150:  # Queremos 100, mas pegamos mais para filtrar
                print(f"  🎯 Atingiu {len(produtos_urls)} URLs, parando...")
                break
                
        except Exception as e:
            print(f"  ⚠️ Erro na categoria: {str(e)[:100]}")
            continue
    
    browser.close()

# Filtra produtos reais (com nome de produto, não só categoria)
print(f"\n🔧 Filtrando {len(produtos_urls)} URLs...")
produtos_reais = []
for url in produtos_urls:
    # Remove query params
    url_limpa = url.split('?')[0].rstrip('/')
    
    # Deve ter mais que só /produto/ ou /produto/categoria
    partes = url_limpa.split('/')
    if len(partes) >= 5:  # https://www.matconcasa.com.br/produto/algo
        ultima_parte = partes[-1]
        # Nome de produto tem hífen e é razoavelmente longo
        if '-' in ultima_parte and len(ultima_parte) > 10:
            produtos_reais.append(url_limpa)

print(f"📦 Produtos reais filtrados: {len(produtos_reais)}")

# Pega 100 primeiros
urls_finais = produtos_reais[:100]

# Salva
with open('urls_matcon_100.txt', 'w', encoding='utf-8') as f:
    for url in urls_finais:
        f.write(url + '\n')

print(f"💾 Salvou {len(urls_finais)} URLs em urls_matcon_100.txt\n")
print("Primeiras 10 URLs:")
for i, url in enumerate(urls_finais[:10], 1):
    print(f"  {i}. {url}")
