import asyncio
import httpx
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin

async def testar_niveis():
    """Testa categorias de nível 2 e 3"""
    print("🔍 TESTANDO CATEGORIAS NÍVEL 2 E 3\n")
    
    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        # Busca sitemap
        r = await client.get('https://www.matconcasa.com.br/sitemap.xml')
        urls = re.findall(r'<loc>(.*?)</loc>', r.text)
        
        # Separa por nível
        nivel2 = []
        nivel3 = []
        
        for url in urls:
            from urllib.parse import urlparse
            path = urlparse(url).path
            segmentos = [s for s in path.split('/') if s]
            
            if len(segmentos) == 2:
                nivel2.append(url)
            elif len(segmentos) == 3:
                nivel3.append(url)
        
        print(f"📂 Nível 2: {len(nivel2)} categorias")
        print(f"📂 Nível 3: {len(nivel3)} categorias\n")
        
        # Testa nível 2
        print("="*70)
        print("🧪 TESTANDO 5 CATEGORIAS NÍVEL 2:")
        print("="*70 + "\n")
        
        total_produtos_n2 = 0
        for i, cat_url in enumerate(nivel2[:5], 1):
            print(f"[{i}] {cat_url}")
            
            try:
                r = await client.get(cat_url)
                soup = BeautifulSoup(r.text, 'html.parser')
                
                produtos = []
                for link in soup.find_all('a', href=True):
                    href = link.get('href')
                    if '/produto/' in href:
                        url = urljoin(cat_url, href)
                        produtos.append(url)
                
                produtos = list(set(produtos))
                total_produtos_n2 += len(produtos)
                
                print(f"   ✅ {len(produtos)} produtos")
                if len(produtos) > 0:
                    for p in produtos[:3]:
                        print(f"      • {p.split('/')[-1][:60]}")
                
            except Exception as e:
                print(f"   ❌ Erro: {e}")
            
            print()
        
        # Testa nível 3
        print("="*70)
        print("🧪 TESTANDO 5 CATEGORIAS NÍVEL 3:")
        print("="*70 + "\n")
        
        total_produtos_n3 = 0
        for i, cat_url in enumerate(nivel3[:5], 1):
            print(f"[{i}] {cat_url}")
            
            try:
                r = await client.get(cat_url)
                soup = BeautifulSoup(r.text, 'html.parser')
                
                produtos = []
                for link in soup.find_all('a', href=True):
                    href = link.get('href')
                    if '/produto/' in href:
                        url = urljoin(cat_url, href)
                        produtos.append(url)
                
                produtos = list(set(produtos))
                total_produtos_n3 += len(produtos)
                
                print(f"   ✅ {len(produtos)} produtos")
                if len(produtos) > 0:
                    for p in produtos[:3]:
                        print(f"      • {p.split('/')[-1][:60]}")
                
            except Exception as e:
                print(f"   ❌ Erro: {e}")
            
            print()
        
        # Conclusão
        print("="*70)
        print("📊 CONCLUSÃO")
        print("="*70)
        print(f"\n✅ Nível 2: {total_produtos_n2} produtos em 5 categorias (média {total_produtos_n2/5:.1f}/cat)")
        print(f"✅ Nível 3: {total_produtos_n3} produtos em 5 categorias (média {total_produtos_n3/5:.1f}/cat)")
        
        print(f"\n💡 PROJEÇÃO TOTAL:")
        print(f"   • Nível 2: {len(nivel2)} categorias × {total_produtos_n2/5:.0f} = ~{len(nivel2) * (total_produtos_n2/5):.0f} produtos")
        print(f"   • Nível 3: {len(nivel3)} categorias × {total_produtos_n3/5:.0f} = ~{len(nivel3) * (total_produtos_n3/5):.0f} produtos")
        print(f"   • TOTAL estimado: ~{len(nivel2) * (total_produtos_n2/5) + len(nivel3) * (total_produtos_n3/5):.0f} produtos")
        
        print(f"\n🎯 ESTRATÉGIA RECOMENDADA:")
        if total_produtos_n2 > total_produtos_n3:
            print(f"   ✅ Usar NÍVEL 2 ({len(nivel2)} categorias)")
            print(f"   Mais produtos por categoria ({total_produtos_n2/5:.1f} vs {total_produtos_n3/5:.1f})")
        else:
            print(f"   ✅ Usar NÍVEL 3 ({len(nivel3)} categorias)")
            print(f"   Mais produtos por categoria ({total_produtos_n3/5:.1f} vs {total_produtos_n2/5:.1f})")

asyncio.run(testar_niveis())
