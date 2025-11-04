import httpx
from bs4 import BeautifulSoup
import re

url = "https://www.matcon.casa/furadeira-makita-de-impacto-1-2-1010w-220v-hp2070-220v-3421-104085"

# Headers
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
}

print(f"🔍 Testando: {url}\n")

response = httpx.get(url, headers=headers, follow_redirects=True, timeout=30)
print(f"Status: {response.status_code}")
print(f"Content-Length: {len(response.text)}\n")

soup = BeautifulSoup(response.text, 'html.parser')

# 1. H1s
print("="*80)
print("H1 TAGS:")
print("="*80)
h1_tags = soup.find_all('h1')
print(f"Total de H1s: {len(h1_tags)}\n")
for i, h1 in enumerate(h1_tags, 1):
    texto = h1.get_text(strip=True)
    print(f"{i}. {texto[:100]}")

# Testar extração
if len(h1_tags) >= 2:
    nome = h1_tags[1].get_text(strip=True)
    print(f"\n✅ Nome extraído (H1[1]): {nome}")
else:
    print("\n❌ Menos de 2 H1s encontrados")

# 2. Preços
print("\n" + "="*80)
print("PREÇOS:")
print("="*80)
html_str = str(soup)
preco_pattern = r'R\$\s*(?:<!--.*?-->)?\s*([\d.,]+)'
precos_encontrados = re.findall(preco_pattern, html_str)

print(f"Total de preços encontrados: {len(precos_encontrados)}")
print("Primeiros 10 preços:")
for i, p in enumerate(precos_encontrados[:10], 1):
    try:
        valor = float(p.replace('.', '').replace(',', '.'))
        print(f"{i}. R$ {p} = {valor:.2f}")
    except:
        print(f"{i}. R$ {p} = ERRO")

# Filtrar e ordenar
precos_num = []
for p in precos_encontrados:
    try:
        valor = float(p.replace('.', '').replace(',', '.'))
        if valor > 10:
            precos_num.append((valor, p))
    except:
        pass

if len(precos_num) >= 2:
    precos_num.sort(key=lambda x: x[0], reverse=True)
    print(f"\n✅ Preço Original: R$ {precos_num[0][1]} ({precos_num[0][0]:.2f})")
    print(f"✅ Preço Final: R$ {precos_num[1][1]} ({precos_num[1][0]:.2f})")
elif precos_num:
    print(f"\n✅ Preço Único: R$ {precos_num[0][1]} ({precos_num[0][0]:.2f})")
else:
    print("\n❌ Nenhum preço válido encontrado")

# 3. Imagens
print("\n" + "="*80)
print("IMAGENS:")
print("="*80)
imgs = soup.find_all('img')
print(f"Total de imgs: {len(imgs)}")
print("\nPrimeiras 5 imagens:")
for i, img in enumerate(imgs[:5], 1):
    src = img.get('src', '')
    alt = img.get('alt', '')
    print(f"{i}. {src[:80]} | ALT: {alt[:40]}")
