#!/usr/bin/env python3
"""
Buscar sitemaps de produtos da Sacada
"""

import httpx
import xml.etree.ElementTree as ET

base_url = "https://www.sacada.com"

print("=" * 80)
print("SITEMAPS DA SACADA")
print("=" * 80)

# 1. Buscar sitemap index
print("\n1. Buscando sitemap index...")
r = httpx.get(f"{base_url}/sitemap.xml", timeout=10)

if r.status_code == 200:
    root = ET.fromstring(r.content)
    ns = {'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
    
    sitemaps = []
    for sitemap in root.findall('.//sm:sitemap', ns):
        loc = sitemap.find('sm:loc', ns)
        if loc is not None:
            sitemaps.append(loc.text)
    
    print(f"Encontrados {len(sitemaps)} sitemaps:")
    for sm in sitemaps:
        print(f"  - {sm}")
    
    # 2. Buscar sitemap de produtos
    print("\n2. Buscando produtos em cada sitemap...")
    
    total_produtos = 0
    urls_produtos = []
    
    for sitemap_url in sitemaps[:5]:  # Limita a 5 primeiros
        print(f"\n   Processando: {sitemap_url}")
        
        try:
            r2 = httpx.get(sitemap_url, timeout=10)
            if r2.status_code == 200:
                root2 = ET.fromstring(r2.content)
                
                urls = []
                for url_elem in root2.findall('.//sm:url', ns):
                    loc = url_elem.find('sm:loc', ns)
                    if loc is not None:
                        url = loc.text
                        # Filtra URLs de produto (normalmente contém /p/ ou /produto/)
                        if '/p/' in url or '/produto/' in url or url.count('/') > 3:
                            urls.append(url)
                
                print(f"   Encontradas {len(urls)} URLs")
                urls_produtos.extend(urls[:20])  # Pega 20 de cada
                total_produtos += len(urls)
        
        except Exception as e:
            print(f"   Erro: {e}")
    
    print(f"\n3. RESUMO:")
    print(f"   Total de produtos: {total_produtos}")
    print(f"   Coletados para teste: {len(urls_produtos)}")
    
    if urls_produtos:
        print(f"\n4. Primeiros 10 produtos:")
        for i, url in enumerate(urls_produtos[:10], 1):
            print(f"   {i}. {url}")
        
        # Salvar
        with open('urls_sacada_20.txt', 'w', encoding='utf-8') as f:
            for url in urls_produtos:
                f.write(url + '\n')
        
        print(f"\n   Salvos em: urls_sacada_20.txt")

print("\n" + "=" * 80)
