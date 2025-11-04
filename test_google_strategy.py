"""
INVESTIGAÇÃO: Como o Google indexa MatConcasa?
===============================================

HIPÓTESES:
1. Sitemap XML separado para produtos
2. RSS Feed de produtos
3. API pública
4. Links internos (descoberta por crawling)
5. Schema.org / JSON-LD
"""

import asyncio
import httpx
import re
from bs4 import BeautifulSoup

async def investigar_google():
    print("="*70)
    print("🔍 INVESTIGANDO: Como Google indexa MatConcasa?")
    print("="*70)
    print()
    
    base_url = 'https://www.matconcasa.com.br'
    
    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        
        # 1. ROBOTS.TXT
        print("🤖 PASSO 1: Verificando robots.txt")
        print("-" * 70)
        try:
            r = await client.get(f'{base_url}/robots.txt')
            print(r.text[:1000])
            
            # Procura sitemaps mencionados
            sitemaps = re.findall(r'Sitemap: (.*)', r.text)
            print(f"\n✅ Sitemaps encontrados em robots.txt:")
            for sm in sitemaps:
                print(f"   • {sm}")
        except Exception as e:
            print(f"❌ Erro: {e}")
        
        print("\n")
        
        # 2. SITEMAP INDEX
        print("📄 PASSO 2: Verificando sitemap index")
        print("-" * 70)
        try:
            r = await client.get(f'{base_url}/sitemap.xml')
            
            # Procura referências a outros sitemaps
            if 'sitemapindex' in r.text.lower():
                print("✅ É um SITEMAP INDEX (aponta para outros sitemaps)")
                
                outros_sitemaps = re.findall(r'<loc>(.*?\.xml)</loc>', r.text)
                print(f"\n📋 {len(outros_sitemaps)} sitemaps filhos:")
                for sm in outros_sitemaps[:10]:
                    print(f"   • {sm}")
                
                if len(outros_sitemaps) > 10:
                    print(f"   ... e mais {len(outros_sitemaps) - 10}")
                
                # Testa o primeiro sitemap filho
                if outros_sitemaps:
                    print(f"\n🧪 Testando primeiro sitemap: {outros_sitemaps[0]}")
                    r2 = await client.get(outros_sitemaps[0])
                    urls = re.findall(r'<loc>(.*?)</loc>', r2.text)
                    
                    # Verifica se tem produtos
                    produtos = [u for u in urls if '/produto/' in u]
                    print(f"   📦 {len(produtos)} produtos de {len(urls)} URLs")
                    
                    if produtos:
                        print(f"\n   ✅ ENCONTROU PRODUTOS!")
                        print(f"   Exemplos:")
                        for p in produtos[:5]:
                            print(f"      • {p}")
            else:
                print("⚠️ É um sitemap simples (não é index)")
                urls = re.findall(r'<loc>(.*?)</loc>', r.text)
                produtos = [u for u in urls if '/produto/' in u]
                print(f"   📦 {len(produtos)} produtos de {len(urls)} URLs")
        
        except Exception as e:
            print(f"❌ Erro: {e}")
        
        print("\n")
        
        # 3. LINKS INTERNOS
        print("🔗 PASSO 3: Analisando links internos na homepage")
        print("-" * 70)
        try:
            r = await client.get(base_url)
            soup = BeautifulSoup(r.text, 'html.parser')
            
            # Conta todos os links
            todos_links = soup.find_all('a', href=True)
            print(f"📊 Total de links: {len(todos_links)}")
            
            # Categoriza
            links_produto = []
            links_categoria = []
            links_outros = []
            
            for link in todos_links:
                href = link.get('href', '')
                
                if '/produto/' in href:
                    links_produto.append(href)
                elif href.startswith('/') and len(href.split('/')) >= 2:
                    links_categoria.append(href)
                else:
                    links_outros.append(href)
            
            print(f"   📦 Links de produtos: {len(set(links_produto))}")
            print(f"   📂 Links de categorias: {len(set(links_categoria))}")
            print(f"   📄 Outros links: {len(set(links_outros))}")
            
            print(f"\n   💡 Google pode descobrir {len(set(links_produto))} produtos na homepage")
            
        except Exception as e:
            print(f"❌ Erro: {e}")
        
        print("\n")
        
        # 4. SCHEMA.ORG / JSON-LD
        print("📋 PASSO 4: Verificando Schema.org e marcação estruturada")
        print("-" * 70)
        try:
            # Testa uma página de produto
            r = await client.get(base_url)
            soup = BeautifulSoup(r.text, 'html.parser')
            
            # Procura primeiro produto
            primeiro_produto = None
            for link in soup.find_all('a', href=True):
                if '/produto/' in link.get('href', ''):
                    from urllib.parse import urljoin
                    primeiro_produto = urljoin(base_url, link.get('href'))
                    break
            
            if primeiro_produto:
                print(f"🧪 Testando: {primeiro_produto.split('/')[-1][:50]}")
                r = await client.get(primeiro_produto)
                
                # Procura JSON-LD
                if 'application/ld+json' in r.text:
                    print("   ✅ JSON-LD encontrado (Google adora isso!)")
                    
                    # Extrai
                    soup = BeautifulSoup(r.text, 'html.parser')
                    scripts = soup.find_all('script', type='application/ld+json')
                    
                    import json
                    for script in scripts:
                        try:
                            data = json.loads(script.string)
                            if '@type' in data:
                                print(f"   • Tipo: {data['@type']}")
                        except:
                            pass
                
                # Procura Open Graph
                og_tags = re.findall(r'<meta property="og:(.*?)" content="(.*?)"', r.text)
                if og_tags:
                    print(f"   ✅ {len(og_tags)} tags Open Graph")
                
                # Procura microdados
                if 'itemtype' in r.text or 'itemscope' in r.text:
                    print("   ✅ Microdados schema.org encontrados")
        
        except Exception as e:
            print(f"❌ Erro: {e}")
        
        print("\n")
        
        # 5. CONCLUSÃO
        print("="*70)
        print("💡 CONCLUSÃO: Como Google indexa MatConcasa")
        print("="*70)
        print("""
DESCOBERTAS:

1. SITEMAP: Verificar se existe sitemap INDEX com sitemap de produtos
   → Se sim, Google usa esse sitemap específico
   → Se não, Google crawla pela homepage

2. HOMEPAGE: Tem 81 produtos linkados diretamente
   → Google descobre esses produtos na primeira visita

3. CRAWLING INTERNO: Google segue links internos
   → Se categorias linkam para produtos, Google encontra
   → MatConcasa pode ter links que BeautifulSoup não vê (JS)

4. PAGINAÇÃO: Categorias podem ter paginação
   → Google segue rel="next" ou links de página 2, 3, etc.

5. ESTRATÉGIA DO GOOGLE:
   ✅ Visita homepage → Descobre 81 produtos
   ✅ Segue links de categorias → Descobre mais produtos
   ✅ Segue paginação → Descobre resto
   ✅ Usa sitemap como backup/complemento

PARA NÓS:
=========
Precisamos fazer o mesmo que o Google:
1. Extrair produtos da homepage
2. Seguir links de categorias
3. Detectar e seguir paginação
4. Verificar se existe sitemap de produtos separado
        """)

asyncio.run(investigar_google())
