"""
DEBUG: Testa cada método de extração isoladamente
"""
import asyncio
import httpx
from playwright.async_api import async_playwright
from extract_fast import extrair_via_jsonld, extrair_via_api_json, extrair_via_dom, descobrir_endpoints

URL_TESTE = "https://www.matconcasa.com.br/produto/furadeira-makita-de-impacto-1-2-127v-760w-hp1640-127v"


async def testar_jsonld():
    print("\n" + "="*80)
    print("TESTE 1: JSON-LD")
    print("="*80)
    
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        resultado = await extrair_via_jsonld(client, URL_TESTE)
        
        print(f"\nResultado: {resultado}")
        
        if resultado:
            print(f"\n✅ JSON-LD FUNCIONOU!")
            print(f"Nome: {resultado.get('nome')}")
            print(f"Preço: {resultado.get('preco')}")
            print(f"Disponível: {resultado.get('disponivel')}")
            return True
        else:
            print(f"\n❌ JSON-LD FALHOU (retornou None ou vazio)")
            return False


async def testar_api():
    print("\n" + "="*80)
    print("TESTE 2: API JSON")
    print("="*80)
    
    # Primeiro descobre endpoints
    print("\n🔍 Descobrindo endpoints...")
    endpoints = await descobrir_endpoints(URL_TESTE)
    print(f"Endpoints descobertos: {endpoints}")
    
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        resultado = await extrair_via_api_json(client, URL_TESTE, endpoints)
        
        print(f"\nResultado: {resultado}")
        
        if resultado and resultado.get('nome'):
            print(f"\n✅ API JSON FUNCIONOU!")
            print(f"Nome: {resultado.get('nome')}")
            print(f"Preço: {resultado.get('preco')}")
            return True
        else:
            print(f"\n❌ API JSON FALHOU")
            return False


async def testar_dom():
    print("\n" + "="*80)
    print("TESTE 3: DOM (Playwright)")
    print("="*80)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)  # headless=False para ver o que acontece
        context = await browser.new_context()
        page = await context.new_page()
        
        resultado = await extrair_via_dom(page, URL_TESTE)
        
        print(f"\nResultado: {resultado}")
        
        if resultado and resultado.get('nome'):
            print(f"\n✅ DOM FUNCIONOU!")
            print(f"Nome: {resultado.get('nome')}")
            print(f"Preço: {resultado.get('preco')}")
            await browser.close()
            return True
        else:
            print(f"\n❌ DOM FALHOU")
            await browser.close()
            return False


async def main():
    print("\n" + "="*80)
    print("🔬 DEBUG: Testando cada método isoladamente")
    print("="*80)
    print(f"URL: {URL_TESTE}")
    
    # Testa os 3 métodos
    jsonld_ok = await testar_jsonld()
    await asyncio.sleep(2)
    
    api_ok = await testar_api()
    await asyncio.sleep(2)
    
    dom_ok = await testar_dom()
    
    # Resumo
    print("\n" + "="*80)
    print("RESUMO")
    print("="*80)
    print(f"JSON-LD: {'✅ OK' if jsonld_ok else '❌ FALHOU'}")
    print(f"API JSON: {'✅ OK' if api_ok else '❌ FALHOU'}")
    print(f"DOM: {'✅ OK' if dom_ok else '❌ FALHOU'}")
    
    if not (jsonld_ok or api_ok or dom_ok):
        print("\n⚠️ PROBLEMA CRÍTICO: NENHUM MÉTODO FUNCIONOU!")
        print("Isso explica por que extract_fast.py está falhando 100%")


if __name__ == "__main__":
    asyncio.run(main())
