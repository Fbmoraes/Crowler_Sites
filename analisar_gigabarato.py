#!/usr/bin/env python3
"""
Analisar padrão de URLs do Gigabarato
"""

import httpx
import xml.etree.ElementTree as ET
import re

base_url = "https://www.gigabarato.com.br"

print("=" * 80)
print("ANALISANDO PADRÃO DE URLs - GIGABARATO")
print("=" * 80)

# 1. Buscar sitemap
print("\n1. Buscando sitemap...")
r = httpx.get(f"{base_url}/sitemap.xml", timeout=10)

if r.status_code == 200:
    root = ET.fromstring(r.content)
    ns = {'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
    
    # Buscar URLs
    urls = []
    for url_elem in root.findall('.//sm:url', ns):
        loc = url_elem.find('sm:loc', ns)
        if loc is not None:
            urls.append(loc.text)
    
    # Se é sitemap index, buscar sub-sitemaps
    sitemaps = []
    for sitemap_elem in root.findall('.//sm:sitemap', ns):
        loc = sitemap_elem.find('sm:loc', ns)
        if loc is not None:
            sitemaps.append(loc.text)
    
    if sitemaps:
        print(f"   Encontrados {len(sitemaps)} sub-sitemaps")
        # Busca primeiro sub-sitemap
        r2 = httpx.get(sitemaps[0], timeout=10)
        if r2.status_code == 200:
            root2 = ET.fromstring(r2.content)
            for url_elem in root2.findall('.//sm:url', ns):
                loc = url_elem.find('sm:loc', ns)
                if loc is not None:
                    urls.append(loc.text)
    
    print(f"   Total de URLs coletadas: {len(urls)}")
    
    # Analisar primeiras 20 URLs
    print("\n2. Primeiras 20 URLs:")
    for i, url in enumerate(urls[:20], 1):
        print(f"   {i}. {url}")
    
    # Detectar padrões
    print("\n3. Análise de padrões:")
    
    padroes = {
        '/p/': sum(1 for u in urls if '/p/' in u),
        '/produto/': sum(1 for u in urls if '/produto/' in u),
        '-p-': sum(1 for u in urls if '-p-' in u),
        '/pd/': sum(1 for u in urls if '/pd/' in u),
        'Contém dígitos': sum(1 for u in urls if re.search(r'/\d+', u)),
        'Termina com número': sum(1 for u in urls if re.search(r'/\d+/?$', u)),
    }
    
    for padrao, count in padroes.items():
        percentual = (count / len(urls) * 100) if urls else 0
        print(f"   {padrao}: {count}/{len(urls)} ({percentual:.1f}%)")
    
    # Testar regex atual
    print("\n4. Testando padrões do código atual:")
    
    padroes_codigo = [
        (r'/p(roduto)?/[^/]+/(\d+)', '/produto/nome/123 ou /p/nome/123'),
        (r'/[^/]+-p-(\d+)', '/nome-p-123'),
        (r'/produto/[^/]+\.html', '/produto/nome.html'),
        (r'/[^/]+/p/\d+', '/categoria/p/123'),
        (r'\.com\.br/[^/]+-\d+/', '.com.br/produto-123/'),
    ]
    
    for padrao_str, desc in padroes_codigo:
        padrao = re.compile(padrao_str)
        matches = sum(1 for u in urls if padrao.search(u))
        percentual = (matches / len(urls) * 100) if urls else 0
        print(f"   {desc}: {matches}/{len(urls)} ({percentual:.1f}%)")
    
    # Propor novo padrão
    print("\n5. Novo padrão sugerido:")
    
    # Analisar estrutura comum
    if urls:
        exemplo = urls[0]
        print(f"   Exemplo: {exemplo}")
        
        # Extrair estrutura
        partes = exemplo.replace(base_url, '').split('/')
        print(f"   Partes: {partes}")

print("\n" + "=" * 80)
