"""
Gera arquivo com 100 URLs de produtos Matcon Casa para teste
"""

from extract_linksv6 import extrair_produtos_rapido

print("🔍 Extraindo URLs do sitemap Matcon Casa...")

url_sitemap = "https://www.matconcasa.com.br/sitemap.xml"
texto, produtos = extrair_produtos_rapido(url_sitemap, modo='sitemap')

print(f"✅ Total encontrado: {len(produtos)} URLs")

# Filtra apenas URLs que parecem ser produtos reais
# Produtos têm formato: /produto/slug-do-produto-com-codigo
produtos_reais = []
for url in produtos:
    if '/produto/' in url:
        partes = url.split('/produto/')
        if len(partes) > 1:
            slug = partes[1].strip('/')
            # Produto real tem:
            # - Múltiplas partes separadas por - (ex: ducha-hydra-optima-8-temp)
            # - OU contém números (códigos de produto)
            # - Slug com mais de 15 caracteres
            if '-' in slug and (any(c.isdigit() for c in slug) or len(slug) > 15):
                # NÃO termina com categoria simples de 1 palavra
                partes_slug = slug.split('/')
                ultima_parte = partes_slug[-1]
                if len(ultima_parte.split('-')) > 1:  # Múltiplas palavras no nome
                    produtos_reais.append(url)

print(f"📦 URLs de produtos reais: {len(produtos_reais)}")

# Pega primeiras 100
urls_teste = produtos_reais[:100]

# Salva em arquivo
with open('urls_matcon_100.txt', 'w', encoding='utf-8') as f:
    for url in urls_teste:
        f.write(url + '\n')

print(f"💾 Salvou {len(urls_teste)} URLs em urls_matcon_100.txt")
print("\nPrimeiras 5 URLs:")
for i, url in enumerate(urls_teste[:5], 1):
    print(f"  {i}. {url}")
