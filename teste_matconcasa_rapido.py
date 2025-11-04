#!/usr/bin/env python3
"""
Teste rápido: Detecta padrão do MatConcasa
"""
import re

# URLs do sitemap do MatConcasa (nível 3)
urls_exemplo = [
    "https://www.matconcasa.com.br/automotivo/limpeza-automotiva/cera",
    "https://www.matconcasa.com.br/automotivo/limpeza-automotiva/desengraxante",
    "https://www.matconcasa.com.br/automotivo/limpeza-automotiva/estopa",
    "https://www.matconcasa.com.br/automotivo/acessorios-automotivos/cavalete",
    "https://www.matconcasa.com.br/automotivo/acessorios-automotivos/cinta-para-anel",
    "https://www.matconcasa.com.br/ferramentas/ferramentas-manuais/alicate",
    "https://www.matconcasa.com.br/ferramentas/ferramentas-manuais/chave-de-fenda",
    "https://www.matconcasa.com.br/construcao/material-eletrico/fio",
    "https://www.matconcasa.com.br/construcao/material-eletrico/tomada",
    "https://www.matconcasa.com.br/casa/decoracao/quadro",
]

# Testa padrão nível 3
padrao_nivel3 = re.compile(r'^https?://[^/]+/[^/]+/[^/]+/[^/]+/?$')

print("🔍 Testando padrão nível 3: /cat1/cat2/produto")
print(f"Padrão: {padrao_nivel3.pattern}\n")

matches = 0
for url in urls_exemplo:
    if padrao_nivel3.search(url):
        print(f"✅ MATCH: {url}")
        matches += 1
    else:
        print(f"❌ NO MATCH: {url}")

print(f"\n📊 Taxa de match: {matches}/{len(urls_exemplo)} = {matches/len(urls_exemplo)*100:.1f}%")
print(f"🎯 Threshold: 15% (padrão será aceito!)" if matches/len(urls_exemplo) >= 0.15 else "❌ Abaixo do threshold")
