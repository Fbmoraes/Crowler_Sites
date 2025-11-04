import asyncio
import httpx
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

async def estrategia_homepage(base_url: str):
    """Extrai produtos diretamente da homepage ou página de listagem"""
    produtos = set()
    
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(base_url, follow_redirects=True)
        soup = BeautifulSoup(r.text, 'html.parser')
        
        # Busca TODOS os links
        for link in soup.find_all('a', href=True):
            href = link.get('href')
            url = urljoin(base_url, href)
            
            # Valida origem
            if urlparse(url).netloc != urlparse(base_url).netloc:
                continue
            
            # Produtos tem "/produto/" E são nível 3
            if '/produto/' in url:
                niveis = len([p for p in urlparse(url).path.split('/') if p])
                if niveis >= 2:  # /produto/slug
                    produtos.add(url)
    
    return list(produtos)

async def test():
    print("🧪 Testando estratégia: Extração direta da homepage\n")
    
    base_url = 'https://www.matconcasa.com.br/'
    produtos = await estrategia_homepage(base_url)
    
    print(f"✅ {len(produtos)} produtos encontrados")
    print("\n📦 Primeiros 10:")
    for p in produtos[:10]:
        nome = p.split('/')[-1].replace('-', ' ').title()
        print(f"  - {nome}")
        print(f"    {p}")

asyncio.run(test())
