#!/usr/bin/env python3
"""
Buscar URLs de produtos reais do Bella Cotton
"""

import asyncio
import httpx
from bs4 import BeautifulSoup
from urllib.parse import urljoin

async def buscar_produtos_bellacotton():
    """Busca produtos reais do site Bella Cotton."""
    
    base_url = "https://www.bellacotton.com.br"
    
    categorias_teste = [
        "/",
        "/produtos",
        "/papel-higienico",
        "/toalha-de-papel",
        "/lencos-de-papel",
        "/guardanapos",
    ]
    
    print("🔍 Buscando produtos no Bella Cotton...")
    print("="*80)
    
    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        
        for cat in categorias_teste:
            url = urljoin(base_url, cat)
            print(f"\n📋 Testando: {url}")
            
            try:
                response = await client.get(url)
                
                if response.status_code == 200:
                    html = response.text
                    soup = BeautifulSoup(html, 'lxml')
                    
                    # Procura links de produtos (vários padrões possíveis)
                    product_links = []
                    
                    # Padrão 1: Links com /produto/ ou /p/
                    for link in soup.find_all('a', href=True):
                        href = link['href']
                        if any(pattern in href for pattern in ['/produto/', '/p/', '-p-', '.html']):
                            full_url = urljoin(base_url, href)
                            if full_url not in product_links:
                                product_links.append(full_url)
                    
                    if product_links:
                        print(f"   ✅ Encontrou {len(product_links)} produtos!")
                        for i, link in enumerate(product_links[:5], 1):
                            print(f"      {i}. {link}")
                        
                        # Salvar URLs
                        with open('urls_bellacotton_reais.txt', 'w', encoding='utf-8') as f:
                            for link in product_links[:20]:
                                f.write(link + '\n')
                        
                        print(f"\n✅ Salvou {min(len(product_links), 20)} URLs em urls_bellacotton_reais.txt")
                        return product_links
                    else:
                        print(f"   ⚠️  Nenhum link de produto encontrado")
                
                else:
                    print(f"   ❌ HTTP {response.status_code}")
            
            except Exception as e:
                print(f"   ❌ Erro: {str(e)[:50]}")
    
    print("\n⚠️  Não foi possível encontrar produtos automaticamente.")
    print("Por favor, copie manualmente algumas URLs de produto do site.")

if __name__ == "__main__":
    asyncio.run(buscar_produtos_bellacotton())
