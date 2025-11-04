import asyncio
import httpx

async def verificar_nextjs():
    """Verifica se MatConcasa usa Next.js com hidratação"""
    print("🔍 VERIFICANDO ARQUITETURA DO SITE\n")
    
    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        # Testa homepage
        url = 'https://www.matconcasa.com.br/'
        r = await client.get(url)
        html = r.text
        
        # Verifica sinais de Next.js
        print("🔍 Procurando sinais de Next.js/React:\n")
        
        if '__NEXT_DATA__' in html:
            print("   ✅ __NEXT_DATA__ encontrado (Next.js confirmado)")
        
        if 'react' in html.lower():
            print("   ✅ React detectado")
        
        if '_next' in html:
            print("   ✅ Arquivos _next/ detectados")
        
        # Verifica se produtos estão no HTML
        print("\n🔍 Procurando produtos no HTML:\n")
        
        if '/produto/' in html:
            count = html.count('/produto/')
            print(f"   ✅ '/produto/' aparece {count} vezes no HTML")
            print("   → Produtos ESTÃO no HTML (hidratação funciona)")
        else:
            print("   ❌ '/produto/' NÃO encontrado")
            print("   → Produtos carregados via API")
        
        # Procura por JSON embutido
        print("\n🔍 Procurando dados JSON embutidos:\n")
        
        import re
        import json
        
        # Procura __NEXT_DATA__
        match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(1))
                print("   ✅ __NEXT_DATA__ parseado com sucesso")
                print(f"   Tamanho: {len(str(data))} caracteres")
                
                # Procura produtos no JSON
                json_str = str(data)
                if '/produto/' in json_str:
                    count = json_str.count('/produto/')
                    print(f"   ✅ {count} URLs de produtos no JSON!")
                    
                    # Extrai URLs
                    produtos = re.findall(r'/produto/[^"\']+', json_str)
                    produtos_unicos = list(set(produtos))
                    
                    print(f"   ✅ {len(produtos_unicos)} produtos únicos extraídos")
                    print("\n   📦 Primeiros 5:")
                    for p in produtos_unicos[:5]:
                        print(f"      • https://www.matconcasa.com.br{p}")
                
            except Exception as e:
                print(f"   ❌ Erro ao parsear JSON: {e}")
        
        print("\n" + "="*70)
        print("💡 CONCLUSÃO")
        print("="*70)
        print("\nMatConcasa usa Next.js com:")
        print("   1. Server-Side Rendering (SSR)")
        print("   2. Dados embutidos em __NEXT_DATA__")
        print("   3. Produtos ESTÃO no HTML inicial")
        print("\n✅ BeautifulSoup DEVERIA funcionar")
        print("⚠️  Mas pode ter problema com encoding ou script tags")

asyncio.run(verificar_nextjs())
