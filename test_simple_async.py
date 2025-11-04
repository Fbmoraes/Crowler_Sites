"""
Teste básico para ver o que está sendo extraído
"""
import asyncio
import httpx
from bs4 import BeautifulSoup

async def test():
    url = "https://www.matconcasa.com.br/produto/furadeira-makita-de-impacto-1-2-1010w-220v-hp2070-220v-281700"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html",
    }
    
    async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
        response = await client.get(url, headers=headers)
        
        print(f"Status: {response.status_code}")
        print(f"URL Final: {response.url}")
        print(f"HTML Length: {len(response.text)}")
        print()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # H1s
        h1s = soup.find_all('h1')
        print(f"H1s encontrados: {len(h1s)}")
        for i, h1 in enumerate(h1s):
            print(f"  [{i}] {h1.get_text(strip=True)[:80]}")
        
        # Title
        title = soup.find('title')
        if title:
            print(f"\nTitle: {title.get_text()}")
        
        # Imagens
        imgs = soup.find_all('img')
        print(f"\nImagens: {len(imgs)}")
        for i, img in enumerate(imgs[:3]):
            print(f"  [{i}] {img.get('src', '')[:60]}")

asyncio.run(test())
