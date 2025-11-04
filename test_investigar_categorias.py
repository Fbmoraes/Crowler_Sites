import asyncio
import httpx
import re
from urllib.parse import urlparse

async def investigar_sitemap():
    """Investiga a estrutura real do sitemap"""
    print("🔍 INVESTIGANDO ESTRUTURA DO SITEMAP\n")
    
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get('https://www.matconcasa.com.br/sitemap.xml')
        urls = re.findall(r'<loc>(.*?)</loc>', r.text)
        
        print(f"📄 Total: {len(urls)} URLs\n")
        
        # Analisa por número de segmentos
        por_niveis = {}
        exemplos_por_nivel = {}
        
        for url in urls:
            path = urlparse(url).path
            segmentos = [s for s in path.split('/') if s]
            nivel = len(segmentos)
            
            por_niveis[nivel] = por_niveis.get(nivel, 0) + 1
            
            # Guarda exemplos
            if nivel not in exemplos_por_nivel:
                exemplos_por_nivel[nivel] = []
            if len(exemplos_por_nivel[nivel]) < 5:
                exemplos_por_nivel[nivel].append(url)
        
        print("📊 DISTRIBUIÇÃO POR NÍVEIS:\n")
        for nivel in sorted(por_niveis.keys()):
            count = por_niveis[nivel]
            print(f"   Nível {nivel}: {count:>6} URLs")
            print(f"   Exemplos:")
            for exemplo in exemplos_por_nivel[nivel][:3]:
                print(f"      • {exemplo}")
            print()
        
        # Procura padrões comuns de categoria
        print("\n🔍 PROCURANDO CATEGORIAS REAIS:\n")
        
        categorias_candidatas = []
        
        for url in urls:
            path = urlparse(url).path
            segmentos = [s for s in path.split('/') if s]
            
            # Categorias geralmente:
            # - Não têm números
            # - São curtas
            # - Não têm hífens com números
            if len(segmentos) == 1:
                seg = segmentos[0]
                # Não tem números no final
                if not re.search(r'-\d+$', seg):
                    # Não é muito longa (categorias são curtas)
                    if len(seg) < 30:
                        categorias_candidatas.append(url)
        
        print(f"✅ Encontradas {len(categorias_candidatas)} categorias candidatas\n")
        print("📂 Primeiras 20 categorias:")
        for cat in categorias_candidatas[:20]:
            print(f"   • {cat}")
        
        # Testa se categorias têm produtos
        print(f"\n\n🧪 TESTANDO 3 CATEGORIAS:\n")
        
        from bs4 import BeautifulSoup
        from urllib.parse import urljoin
        
        for i, cat_url in enumerate(categorias_candidatas[:3], 1):
            print(f"[{i}] {cat_url}")
            
            try:
                r = await client.get(cat_url, follow_redirects=True)
                soup = BeautifulSoup(r.text, 'html.parser')
                
                # Conta produtos
                produtos = []
                for link in soup.find_all('a', href=True):
                    href = link.get('href')
                    if '/produto/' in href:
                        url = urljoin(cat_url, href)
                        produtos.append(url)
                
                produtos = list(set(produtos))
                print(f"   ✅ {len(produtos)} produtos encontrados")
                
                if len(produtos) > 0:
                    print(f"   📦 Exemplos:")
                    for p in produtos[:3]:
                        print(f"      • {p.split('/')[-1][:60]}")
                
            except Exception as e:
                print(f"   ❌ Erro: {e}")
            
            print()

asyncio.run(investigar_sitemap())
