import asyncio
import httpx
from bs4 import BeautifulSoup
from urllib.parse import urljoin

async def test():
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get('https://www.matconcasa.com.br/')
        soup = BeautifulSoup(r.text, 'html.parser')
        
        # Busca links de produtos
        produtos = []
        for a in soup.find_all('a', href=True):
            href = a.get('href')
            if '/produto/' in href:
                url = urljoin('https://www.matconcasa.com.br/', href)
                produtos.append(url)
        
        produtos_unicos = list(set(produtos))
        print(f"✅ Produtos na homepage: {len(produtos_unicos)}")
        print("\n📦 Primeiros 10:")
        for p in produtos_unicos[:10]:
            print(f"  - {p}")

asyncio.run(test())
