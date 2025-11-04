#!/usr/bin/env python3
"""
Teste rápido no site Sacada Shop para diagnosticar problemas
"""

import asyncio
import httpx
from extract_linksv7 import extrair_produtos_rapido

def dummy_message(msg):
    print(f"[INFO] {msg}")

def dummy_progress(atual, total, info, tipo):
    if tipo == "coletando":
        print(f"[SITEMAP] {info} | {atual} URLs")
    elif tipo == "fase_aprendizado":
        print(f"[APRENDIZADO] {atual}/{total}")
    elif tipo == "aplicando_padrao":
        print(f"[FILTRANDO] {atual}/{total}")
    elif tipo == "validando":
        print(f"[VALIDANDO] {atual}/{total}")
    elif tipo == "produto_validado":
        print(f"[PRODUTOS] {atual}")

# Teste
print("=" * 80)
print("TESTE SACADA SHOP")
print("=" * 80)

url = "https://www.sacada.com"
print(f"\nURL: {url}\n")

try:
    produtos = extrair_produtos_rapido(
        url,
        dummy_message,
        max_produtos=20,  # Limita para teste rápido
        progress_callback=dummy_progress
    )
    
    print("\n" + "=" * 80)
    print(f"RESULTADO: {len(produtos)} produtos encontrados")
    print("=" * 80)
    
    if produtos:
        print("\nPrimeiros 5 produtos:")
        for i, p in enumerate(produtos[:5], 1):
            print(f"{i}. {p.get('nome', 'N/A')}")
            print(f"   URL: {p.get('url', 'N/A')}")
    else:
        print("\nNENHUM PRODUTO ENCONTRADO!")
        print("\nPossíveis causas:")
        print("1. Site não tem sitemap.xml")
        print("2. Robots.txt bloqueia acesso")
        print("3. URLs de produto têm padrão diferente")
        print("4. Site usa JavaScript para carregar produtos")

except Exception as e:
    print(f"\nERRO: {e}")
    import traceback
    traceback.print_exc()
