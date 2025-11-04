"""
Testar um produto específico do Dermomanipulações
"""

import asyncio
import httpx
from bs4 import BeautifulSoup
import json

async def testar_produto_especifico():
    # Produto que provavelmente é real
    url = "https://www.dermomanipulacoes.com.br/minoxidil"
    
    print(f"🔍 Testando produto: {url}\n")
    
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        resp = await client.get(url)
        
        print(f"Status: {resp.status_code}")
        print(f"Content-Type: {resp.headers.get('content-type')}\n")
        
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # Salvar HTML
        with open("dermo_minoxidil.html", "w", encoding="utf-8") as f:
            f.write(resp.text)
        print("✅ HTML salvo em dermo_minoxidil.html\n")
        
        # Buscar JSON-LD
        print("=" * 60)
        print("JSON-LD")
        print("=" * 60)
        json_lds = soup.find_all('script', type='application/ld+json')
        for i, script in enumerate(json_lds, 1):
            try:
                data = json.loads(script.string)
                print(f"\nScript #{i}:")
                print(json.dumps(data, indent=2, ensure_ascii=False))
            except:
                print(f"\nScript #{i}: Erro ao parsear")
        
        # Buscar Open Graph
        print("\n" + "=" * 60)
        print("OPEN GRAPH")
        print("=" * 60)
        og_tags = soup.find_all('meta', property=lambda x: x and x.startswith('og:'))
        for tag in og_tags[:15]:
            prop = tag.get('property')
            content = tag.get('content')
            print(f"{prop}: {content}")
        
        # Buscar preços no HTML
        print("\n" + "=" * 60)
        print("BUSCANDO PREÇOS NO HTML")
        print("=" * 60)
        
        # Classes e IDs comuns de preço
        price_selectors = [
            ('class="price"', soup.find_all(class_='price')),
            ('class="product-price"', soup.find_all(class_='product-price')),
            ('class="valor"', soup.find_all(class_='valor')),
            ('itemprop="price"', soup.find_all(attrs={'itemprop': 'price'})),
            ('data-price', soup.find_all(attrs={'data-price': True}))
        ]
        
        for selector, elements in price_selectors:
            if elements:
                print(f"\n{selector}:")
                for elem in elements[:3]:
                    print(f"  {elem}")
        
        # Buscar qualquer texto com R$
        print("\n" + "=" * 60)
        print("TEXTOS COM R$")
        print("=" * 60)
        
        # Procura por R$ no texto
        all_text = soup.get_text()
        lines_with_real = [line.strip() for line in all_text.split('\n') if 'R$' in line]
        
        if lines_with_real:
            print(f"Encontradas {len(lines_with_real)} linhas com R$:")
            for line in lines_with_real[:10]:
                if line:
                    print(f"  {line[:80]}")
        else:
            print("❌ Nenhuma linha com R$ encontrada")
        
        # Buscar botões/formulários
        print("\n" + "=" * 60)
        print("BOTÕES E AÇÕES")
        print("=" * 60)
        
        buttons = soup.find_all(['button', 'input'], type=['submit', 'button'])
        for btn in buttons[:5]:
            text = btn.get_text(strip=True) or btn.get('value') or btn.get('title')
            print(f"  {text}")

asyncio.run(testar_produto_especifico())
