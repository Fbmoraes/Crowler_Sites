#!/usr/bin/env python3
"""
Teste com URLs REAIS do Gigabarato
"""

import re
import httpx
import xml.etree.ElementTree as ET

# Buscar URLs reais do sitemap
base_url = "https://www.gigabarato.com.br"
r = httpx.get(f"{base_url}/sitemap.xml", timeout=10)

urls = []
if r.status_code == 200:
    root = ET.fromstring(r.content)
    ns = {'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
    
    for url_elem in root.findall('.//sm:url', ns):
        loc = url_elem.find('sm:loc', ns)
        if loc is not None:
            urls.append(loc.text)

print(f"Total de URLs do sitemap: {len(urls)}")
print(f"\nPrimeiras 10 URLs:")
for i, url in enumerate(urls[:10], 1):
    print(f"{i}. {url}")

# Testar padrão
padrao = re.compile(r'/produtos?/[^/]+-\d+/?$')

matches = 0
produtos = []
nao_produtos = []

for url in urls:
    if padrao.search(url):
        matches += 1
        if len(produtos) < 5:
            produtos.append(url)
    else:
        if len(nao_produtos) < 5:
            nao_produtos.append(url)

score = (matches / len(urls) * 100) if urls else 0

print(f"\n{'='*80}")
print(f"RESULTADO:")
print(f"{'='*80}")
print(f"Total de URLs: {len(urls)}")
print(f"Matches: {matches}")
print(f"Score: {score:.1f}%")
print(f"Threshold necessário: >=30%")
print(f"Status: {'✓ PADRÃO DETECTADO' if score >= 30 else '✗ PADRÃO NÃO DETECTADO'}")

print(f"\nExemplos de PRODUTOS (match):")
for p in produtos:
    print(f"  ✓ {p}")

print(f"\nExemplos de NÃO PRODUTOS (no match):")
for np in nao_produtos:
    print(f"  ✗ {np}")
