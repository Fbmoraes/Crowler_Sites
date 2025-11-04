import asyncio
import httpx
import re

async def test():
    sitemap_url = 'https://www.matconcasa.com.br/sitemap.xml'
    
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(sitemap_url, follow_redirects=True)
        if r.status_code == 200:
            urls = re.findall(r'<loc>(.*?)</loc>', r.text)
            
            print(f"📄 Total URLs no sitemap: {len(urls)}")
            
            # Filtra por tipo
            produtos = [u for u in urls if '/produto/' in u]
            categorias = [u for u in urls if u.count('/') == 3 and '/produto/' not in u]
            outros = [u for u in urls if u not in produtos and u not in categorias]
            
            print(f"\n📦 Produtos (/produto/): {len(produtos)}")
            print(f"📂 Categorias (nível 1): {len(categorias)}")
            print(f"📄 Outros: {len(outros)}")
            
            print("\n📦 Primeiros 5 produtos:")
            for p in produtos[:5]:
                print(f"  - {p}")
            
            print("\n📂 Primeiras 5 categorias:")
            for c in categorias[:5]:
                print(f"  - {c}")

asyncio.run(test())
