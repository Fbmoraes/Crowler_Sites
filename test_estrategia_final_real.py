"""
CONCLUSÃO FINAL: MatConcasa
============================

DESCOBERTA:
- Sitemap tem 21k URLs (categorias + subcategorias)
- Homepage TEM 81 produtos
- Categorias NÃO têm produtos listados (ou tem paginação)
- Produtos só estão em /produto/slug-123

ESTRATÉGIA FINAL SIMPLES:
==========================
Já que categorias não listam produtos, a melhor estratégia é:

1. Buscar sitemap (1 request)
2. Detectar padrão na homepage (já temos: /produto/.*-\d+)
3. Filtrar sitemap pelo padrão
4. PROBLEMA: Sitemap não tem /produto/ URLs!

SOLUÇÃO REAL:
=============
Como o sitemap NÃO tem produtos, só temos 2 opções:

OPÇÃO A (SIMPLES): 
   - Extrair apenas da homepage (81 produtos)
   - Rápido, mas limitado

OPÇÃO B (COMPLETA):
   - Crawl recursivo com limite de profundidade
   - Lento, mas pega tudo
   
OPÇÃO C (HÍBRIDA - RECOMENDADA):
   - Extrair homepage (81 produtos)
   - Navegar categorias principais buscando MAIS produtos
   - Se categoria não tem, ignorar
   - Limite: 50 categorias × 1 request = 50 requests total
"""

import asyncio
import httpx
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import re
import time

async def estrategia_hibrida_real():
    """Estratégia que REALMENTE funciona no MatConcasa"""
    
    print("="*70)
    print("🧪 ESTRATÉGIA FINAL HÍBRIDA - MatConcasa")
    print("="*70)
    print("\n📋 PLANO:")
    print("   1. Homepage → extrair produtos")
    print("   2. Sitemap → pegar todas URLs")
    print("   3. Visitar URLs do sitemap buscando produtos")
    print("   4. Parar quando: encontrar N produtos OU visitar M páginas\n")
    
    inicio = time.time()
    base_url = 'https://www.matconcasa.com.br/'
    produtos = set()
    paginas_visitadas = 0
    max_paginas = 30
    max_produtos = 500
    
    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        # PASSO 1: Homepage
        print("🏠 PASSO 1: Extraindo produtos da homepage...")
        r = await client.get(base_url)
        paginas_visitadas += 1
        soup = BeautifulSoup(r.text, 'html.parser')
        
        for link in soup.find_all('a', href=True):
            href = link.get('href')
            if '/produto/' in href:
                url = urljoin(base_url, href)
                produtos.add(url)
        
        print(f"   ✅ {len(produtos)} produtos na homepage\n")
        
        # PASSO 2: Buscar sitemap
        print("📄 PASSO 2: Buscando URLs do sitemap...")
        r = await client.get(f'{base_url}sitemap.xml')
        paginas_visitadas += 1
        urls_sitemap = re.findall(r'<loc>(.*?)</loc>', r.text)
        
        # Filtra URLs candidatas (não muito longas, não produtos)
        urls_candidatas = []
        for url in urls_sitemap:
            path = urlparse(url).path
            segmentos = [s for s in path.split('/') if s]
            
            # Pega URLs de nível 1-3, que não sejam produtos
            if 1 <= len(segmentos) <= 3 and '/produto/' not in url:
                # Ignora URLs muito longas (provavelmente produtos disfarçados)
                if len(path) < 100:
                    urls_candidatas.append(url)
        
        print(f"   ✅ {len(urls_candidatas)} URLs candidatas\n")
        
        # PASSO 3: Navegar URLs candidatas
        print(f"🔍 PASSO 3: Navegando até {max_paginas} páginas...\n")
        
        for i, url in enumerate(urls_candidatas[:max_paginas], 1):
            if len(produtos) >= max_produtos:
                print(f"\n✅ Limite de {max_produtos} produtos atingido!")
                break
            
            nome_pag = url.split('/')[-1] or 'home'
            print(f"   [{i:2d}] {nome_pag[:50]:<50}", end=' ')
            
            try:
                r = await client.get(url)
                paginas_visitadas += 1
                soup = BeautifulSoup(r.text, 'html.parser')
                
                novos = 0
                for link in soup.find_all('a', href=True):
                    href = link.get('href')
                    if '/produto/' in href:
                        produto_url = urljoin(url, href)
                        if produto_url not in produtos:
                            produtos.add(produto_url)
                            novos += 1
                
                if novos > 0:
                    print(f"✅ +{novos:3d} ({len(produtos):4d} total)")
                else:
                    print(f"⚠️   0")
                
                await asyncio.sleep(0.2)  # Delay
                
            except Exception as e:
                print(f"❌ Erro")
    
    tempo_total = time.time() - inicio
    
    # RESULTADOS
    print("\n" + "="*70)
    print("📊 RESULTADOS FINAIS")
    print("="*70)
    print(f"\n⏱️  Tempo: {tempo_total:.1f}s")
    print(f"🌐 Páginas visitadas: {paginas_visitadas}")
    print(f"📦 Produtos encontrados: {len(produtos)}")
    print(f"\n📈 Performance:")
    print(f"   • {len(produtos)/tempo_total:.1f} produtos/segundo")
    print(f"   • {tempo_total/paginas_visitadas:.2f}s por página")
    print(f"   • {len(produtos)/paginas_visitadas:.1f} produtos por página")
    
    print(f"\n📦 Amostra (10 produtos):")
    for i, p in enumerate(list(produtos)[:10], 1):
        print(f"   {i:2d}. {p.split('/')[-1][:70]}")
    
    print("\n" + "="*70)
    print("🎯 AVALIAÇÃO DA ESTRATÉGIA")
    print("="*70)
    
    if len(produtos) >= 400:
        print("\n✅ EXCELENTE! Estratégia viável")
        print(f"   • {len(produtos)} produtos em {tempo_total:.0f}s")
        print("   • Boa cobertura do catálogo")
        print("   • Tempo aceitável")
    elif len(produtos) >= 200:
        print("\n⚠️ BOM, mas pode melhorar")
        print(f"   • {len(produtos)} produtos em {tempo_total:.0f}s")
        print("   • Cobertura parcial")
        print("   • Considere aumentar max_paginas")
    else:
        print("\n❌ INSUFICIENTE")
        print(f"   • Apenas {len(produtos)} produtos")
        print("   • Estratégia não funciona bem neste site")
    
    return len(produtos), tempo_total

asyncio.run(estrategia_hibrida_real())
