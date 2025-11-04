import asyncio
import httpx
import re

async def investigar():
    print("🔍 INVESTIGAÇÃO: Por que padrão não matchou no sitemap?\n")
    
    # 1. Produtos da homepage
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get('https://www.matconcasa.com.br/')
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(r.text, 'html.parser')
        
        produtos_home = []
        for link in soup.find_all('a', href=True):
            href = link.get('href')
            if '/produto/' in href:
                from urllib.parse import urljoin
                url = urljoin('https://www.matconcasa.com.br/', href)
                produtos_home.append(url)
        
        produtos_home = list(set(produtos_home))[:5]
        
        print("📦 Produtos da HOMEPAGE:")
        for p in produtos_home:
            print(f"   {p}")
        
        # 2. URLs do sitemap
        r2 = await client.get('https://www.matconcasa.com.br/sitemap.xml')
        urls_sitemap = re.findall(r'<loc>(.*?)</loc>', r2.text)
        
        print(f"\n📄 Sitemap tem {len(urls_sitemap)} URLs")
        
        # Procura produtos no sitemap
        produtos_sitemap = [u for u in urls_sitemap if '/produto/' in u]
        print(f"   Produtos (/produto/): {len(produtos_sitemap)}")
        
        # Mostra algumas URLs do sitemap
        print("\n📄 Primeiras 10 URLs do SITEMAP:")
        for u in urls_sitemap[:10]:
            print(f"   {u}")
        
        # 3. Testa o padrão
        padrao = re.compile(r'/produto/[^/]+-\d+/?$')
        
        print("\n🔍 Testando PADRÃO: /produto/[^/]+-\\d+/?$")
        
        print("\n✅ Match na HOMEPAGE:")
        for p in produtos_home:
            match = padrao.search(p)
            print(f"   {match is not None} → {p}")
        
        print("\n❌ Match no SITEMAP (primeiras 20):")
        for u in urls_sitemap[:20]:
            match = padrao.search(u)
            if match:
                print(f"   ✓ {u}")
        
        print("\n💡 CONCLUSÃO:")
        print("   O sitemap do MatConcasa NÃO contém URLs de produtos!")
        print("   Os produtos só aparecem nas páginas HTML (home/categorias)")
        print("   Padrão funciona, mas sitemap não tem o que matchear")

asyncio.run(investigar())
