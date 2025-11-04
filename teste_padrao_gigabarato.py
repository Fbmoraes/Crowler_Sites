#!/usr/bin/env python3
"""
Teste rápido do pattern learning no Gigabarato
"""

import re

# URLs de exemplo do Gigabarato
urls = [
    "https://www.gigabarato.com.br/produtos/mop-giratorio-fit-balde-8-litros-mop5010-flash-limp-15786/",
    "https://www.gigabarato.com.br/produtos/kit-com-5-potes-de-plastico-color-240ml-a-1500ml-25100/",
    "https://www.gigabarato.com.br/produtos/kit-jarra-com-4-copos-em-vidro-maracatu-nadir-16561/",
    "https://www.gigabarato.com.br/",
    "https://www.gigabarato.com.br/br/contato/",
    "https://www.gigabarato.com.br/br/produtos/",
]

# Testar padrão
padrao = re.compile(r'/produtos?/[^/]+-\d+/?$')

print("=" * 80)
print("TESTE DE PATTERN LEARNING - GIGABARATO")
print("=" * 80)

matches = 0
for url in urls:
    match = padrao.search(url)
    if match:
        matches += 1
        print(f"✓ MATCH: {url}")
    else:
        print(f"✗ NO MATCH: {url}")

score = matches / len(urls) * 100
print(f"\nScore: {matches}/{len(urls)} ({score:.1f}%)")
print(f"Confiança: {'SIM' if score > 50 else 'NÃO'} (>50% = aplica filtro sem HTTP)")

print("=" * 80)
