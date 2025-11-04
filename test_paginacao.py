import asyncio
import httpx
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import re

async def testar_paginacao():
    """Verifica se categorias têm paginação"""
    print("="*70)
    print("🔍 TESTANDO PAGINAÇÃO EM CATEGORIAS")
    print("="*70)
    print()
    
    # Testa uma categoria
    categorias_teste = [
        'https://www.matconcasa.com.br/ferramentas',
        'https://www.matconcasa.com.br/banheiro',
        'https://www.matconcasa.com.br/materiais-de-construcao'
    ]
    
    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        
        for cat_url in categorias_teste:
            print(f"📂 Categoria: {cat_url.split('/')[-1]}")
            print("-" * 70)
            
            try:
                r = await client.get(cat_url)
                soup = BeautifulSoup(r.text, 'html.parser')
                html = r.text
                
                # 1. Conta produtos na página 1
                produtos = []
                for link in soup.find_all('a', href=True):
                    href = link.get('href')
                    if '/produto/' in href:
                        url = urljoin(cat_url, href)
                        produtos.append(url)
                
                produtos = list(set(produtos))
                print(f"   📦 Produtos na página 1: {len(produtos)}")
                
                # 2. Procura links de paginação
                paginacao_patterns = [
                    r'[?&]page=(\d+)',
                    r'[?&]p=(\d+)',
                    r'/page/(\d+)',
                    r'/p/(\d+)',
                    r'[?&]pagina=(\d+)'
                ]
                
                paginas_encontradas = set()
                for pattern in paginacao_patterns:
                    matches = re.findall(pattern, html)
                    paginas_encontradas.update(matches)
                
                if paginas_encontradas:
                    print(f"   📄 Paginação detectada: páginas {sorted(paginas_encontradas)[:10]}")
                else:
                    print(f"   ⚠️  Paginação não detectada no HTML")
                
                # 3. Procura botões/links com texto "próxima", "next", "2", etc
                links_proxima = []
                for link in soup.find_all('a', href=True):
                    texto = link.get_text(strip=True).lower()
                    if any(palavra in texto for palavra in ['próxim', 'next', 'seguinte', '2', '→', '>']):
                        if len(texto) < 20:  # Não é texto longo
                            links_proxima.append({
                                'texto': texto,
                                'href': link.get('href')
                            })
                
                if links_proxima:
                    print(f"   🔗 Links de navegação encontrados:")
                    for lnk in links_proxima[:5]:
                        print(f"      • '{lnk['texto']}' → {lnk['href']}")
                
                # 4. Verifica se há indicação de total de produtos
                if 'produto' in html.lower() and 'resultado' in html.lower():
                    # Procura padrões como "120 produtos" ou "mostrando 1-20 de 120"
                    matches = re.findall(r'(\d+)\s*produtos?', html, re.IGNORECASE)
                    if matches:
                        total = max(int(m) for m in matches)
                        print(f"   📊 Total indicado: ~{total} produtos")
                
                # 5. Tenta acessar página 2 diretamente
                print(f"\n   🧪 Testando página 2...")
                tentativas_p2 = [
                    f"{cat_url}?page=2",
                    f"{cat_url}?p=2",
                    f"{cat_url}/page/2"
                ]
                
                for url_p2 in tentativas_p2:
                    try:
                        r2 = await client.get(url_p2)
                        if r2.status_code == 200:
                            soup2 = BeautifulSoup(r2.text, 'html.parser')
                            
                            produtos_p2 = []
                            for link in soup2.find_all('a', href=True):
                                href = link.get('href')
                                if '/produto/' in href:
                                    url = urljoin(url_p2, href)
                                    produtos_p2.append(url)
                            
                            produtos_p2 = list(set(produtos_p2))
                            
                            if len(produtos_p2) > 0:
                                print(f"      ✅ {url_p2}")
                                print(f"         📦 {len(produtos_p2)} produtos na página 2")
                                
                                # Mostra exemplos
                                if produtos_p2:
                                    print(f"         Exemplos:")
                                    for p in produtos_p2[:3]:
                                        print(f"            • {p.split('/')[-1][:50]}")
                                
                                break
                    except:
                        pass
                
                print()
                
            except Exception as e:
                print(f"   ❌ Erro: {e}\n")
        
        print("="*70)
        print("💡 CONCLUSÃO")
        print("="*70)
        print("""
Se categorias têm paginação:
✅ Google descobre produtos seguindo links "próxima página"
✅ Precisamos implementar detecção de paginação
✅ Estratégia: seguir até página N ou até não haver mais produtos

Se categorias NÃO têm produtos:
⚠️ Produtos podem estar em subcategorias mais profundas
⚠️ Ou produtos são adicionados via JavaScript/API
⚠️ Precisamos de estratégia diferente
        """)

asyncio.run(testar_paginacao())
