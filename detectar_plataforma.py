#!/usr/bin/env python3
"""
DETECTOR DE PLATAFORMA E-COMMERCE
==================================
Identifica se o site usa VTEX, Shopify, WooCommerce, Magento, etc.
e testa APIs nativas para extração em lote (50-250 produtos por request).
"""

import asyncio
import httpx
import json
from urllib.parse import urlparse, urljoin

async def detectar_plataforma(url_base: str):
    """
    Detecta a plataforma e-commerce do site.
    Retorna: {plataforma, api_disponivel, endpoint_sugerido}
    """
    print(f"\n{'='*100}")
    print(f"DETECTANDO PLATAFORMA: {url_base}")
    print(f"{'='*100}\n")
    
    resultados = {
        "url_base": url_base,
        "plataforma": "DESCONHECIDA",
        "evidencias": [],
        "apis_disponiveis": []
    }
    
    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        
        # ========== TESTE 1: Headers e HTML da página principal ==========
        print("📋 Analisando headers e HTML...")
        try:
            response = await client.get(url_base)
            headers = response.headers
            html = response.text.lower()
            
            # VTEX
            if 'vtex' in html or 'vtex' in str(headers).lower():
                resultados["plataforma"] = "VTEX"
                resultados["evidencias"].append("✓ Detectado 'vtex' no HTML/headers")
            
            # Shopify
            if 'shopify' in html or 'myshopify.com' in html or 'cdn.shopify.com' in html:
                resultados["plataforma"] = "SHOPIFY"
                resultados["evidencias"].append("✓ Detectado 'shopify' no HTML")
            
            # WooCommerce
            if 'woocommerce' in html or 'wp-content' in html:
                resultados["plataforma"] = "WOOCOMMERCE"
                resultados["evidencias"].append("✓ Detectado 'woocommerce' no HTML")
            
            # Magento
            if 'magento' in html or 'mage' in html:
                resultados["plataforma"] = "MAGENTO"
                resultados["evidencias"].append("✓ Detectado 'magento' no HTML")
            
            # Outros
            if 'nuvemshop' in html:
                resultados["plataforma"] = "NUVEMSHOP"
                resultados["evidencias"].append("✓ Detectado 'nuvemshop' no HTML")
            
            print(f"   Plataforma detectada: {resultados['plataforma']}")
            for evidencia in resultados["evidencias"]:
                print(f"   {evidencia}")
        
        except Exception as e:
            print(f"   ❌ Erro ao analisar página: {e}")
        
        # ========== TESTE 2: APIs nativas (VTEX, Shopify, WooCommerce) ==========
        print(f"\n🔍 Testando APIs nativas...")
        
        domain = urlparse(url_base).netloc
        
        # --- VTEX Intelligent Search API ---
        vtex_api_urls = [
            f"{url_base}/api/io/_v/api/intelligent-search/product_search/?_from=0&_to=1",
            f"https://{domain}/api/io/_v/api/intelligent-search/product_search/?_from=0&_to=1",
            f"{url_base}/api/catalog_system/pub/products/search?_from=0&_to=1",
        ]
        
        for api_url in vtex_api_urls:
            try:
                resp = await client.get(api_url, timeout=10.0)
                if resp.status_code == 200:
                    data = resp.json()
                    if isinstance(data, dict) and 'products' in data:
                        produtos = data.get('products', [])
                        resultados["apis_disponiveis"].append({
                            "tipo": "VTEX Intelligent Search",
                            "endpoint": api_url,
                            "funciona": True,
                            "limite_por_request": 50,
                            "exemplo_produto": produtos[0] if produtos else None
                        })
                        print(f"   ✅ VTEX Intelligent Search API FUNCIONA!")
                        print(f"      Endpoint: {api_url}")
                        print(f"      Limite: 50 produtos por request (_from=0&_to=49)")
                        break
                    elif isinstance(data, list) and len(data) > 0:
                        resultados["apis_disponiveis"].append({
                            "tipo": "VTEX Catalog API",
                            "endpoint": api_url,
                            "funciona": True,
                            "limite_por_request": 50,
                            "exemplo_produto": data[0]
                        })
                        print(f"   ✅ VTEX Catalog API FUNCIONA!")
                        print(f"      Endpoint: {api_url}")
                        break
            except:
                continue
        
        # --- Shopify Products JSON ---
        shopify_urls = [
            f"{url_base}/products.json?limit=1",
            f"{url_base}/collections/all/products.json?limit=1",
        ]
        
        for api_url in shopify_urls:
            try:
                resp = await client.get(api_url, timeout=10.0)
                if resp.status_code == 200:
                    data = resp.json()
                    if 'products' in data and isinstance(data['products'], list):
                        resultados["apis_disponiveis"].append({
                            "tipo": "SHOPIFY Products JSON",
                            "endpoint": api_url.replace('limit=1', 'limit=250'),
                            "funciona": True,
                            "limite_por_request": 250,
                            "exemplo_produto": data['products'][0] if data['products'] else None
                        })
                        print(f"   ✅ SHOPIFY Products JSON API FUNCIONA!")
                        print(f"      Endpoint: {api_url.replace('limit=1', 'limit=250&page=1')}")
                        print(f"      Limite: 250 produtos por request (limit=250&page=N)")
                        break
            except:
                continue
        
        # --- WooCommerce Store API ---
        woo_urls = [
            f"{url_base}/wp-json/wc/store/products?per_page=1",
            f"{url_base}/wp-json/wc/v3/products?per_page=1",
        ]
        
        for api_url in woo_urls:
            try:
                resp = await client.get(api_url, timeout=10.0)
                if resp.status_code == 200:
                    data = resp.json()
                    if isinstance(data, list) and len(data) > 0:
                        resultados["apis_disponiveis"].append({
                            "tipo": "WOOCOMMERCE Store API",
                            "endpoint": api_url.replace('per_page=1', 'per_page=100'),
                            "funciona": True,
                            "limite_por_request": 100,
                            "exemplo_produto": data[0]
                        })
                        print(f"   ✅ WOOCOMMERCE Store API FUNCIONA!")
                        print(f"      Endpoint: {api_url.replace('per_page=1', 'per_page=100&page=1')}")
                        print(f"      Limite: 100 produtos por request (per_page=100&page=N)")
                        break
            except:
                continue
    
    # ========== RESULTADO FINAL ==========
    print(f"\n{'='*100}")
    print("RESULTADO FINAL")
    print(f"{'='*100}\n")
    
    print(f"🏪 PLATAFORMA: {resultados['plataforma']}")
    print(f"📊 APIs DISPONÍVEIS: {len(resultados['apis_disponiveis'])}")
    
    if resultados["apis_disponiveis"]:
        print(f"\n✨ ÓTIMA NOTÍCIA! Você pode usar APIs nativas para extração em LOTE:\n")
        
        for api in resultados["apis_disponiveis"]:
            print(f"   🚀 {api['tipo']}")
            print(f"      Endpoint: {api['endpoint']}")
            print(f"      Limite: {api['limite_por_request']} produtos por request")
            
            # Calcular estimativa para 800 produtos
            total_requests = (800 + api['limite_por_request'] - 1) // api['limite_por_request']
            tempo_estimado = total_requests * 1.5  # ~1.5s por request
            
            print(f"      Para 800 produtos: {total_requests} requests (~{tempo_estimado/60:.1f} minutos)")
            
            if api.get('exemplo_produto'):
                print(f"\n      Exemplo de campos disponíveis:")
                campos = list(api['exemplo_produto'].keys())[:10]
                print(f"      {', '.join(campos)}")
            print()
    else:
        print(f"\n⚠️  Nenhuma API nativa detectada.")
        print(f"   Você precisará usar scraping tradicional ou APIs SaaS (Zyte, Oxylabs).")
    
    print(f"{'='*100}\n")
    
    # Salvar resultados
    with open("plataforma_detectada.json", "w", encoding="utf-8") as f:
        json.dump(resultados, f, indent=2, ensure_ascii=False)
    
    print("✅ Resultados salvos em: plataforma_detectada.json\n")
    
    return resultados


async def main():
    # Testar com as URLs que você está usando
    urls_teste = [
        "https://www.bellacotton.com.br",
    ]
    
    for url in urls_teste:
        resultado = await detectar_plataforma(url)
        
        # Se encontrar API, sugerir próximo passo
        if resultado["apis_disponiveis"]:
            print(f"🎯 PRÓXIMO PASSO para {url}:")
            api = resultado["apis_disponiveis"][0]
            
            if api["tipo"].startswith("VTEX"):
                print(f"   1. Use extract_vtex_api.py (vou criar agora)")
                print(f"   2. Será ~{(800 // api['limite_por_request']) * 1.5 / 60:.1f} min para 800 produtos")
            
            elif api["tipo"].startswith("SHOPIFY"):
                print(f"   1. Use extract_shopify_api.py (vou criar agora)")
                print(f"   2. Será ~{(800 // api['limite_por_request']) * 1.5 / 60:.1f} min para 800 produtos")
            
            elif api["tipo"].startswith("WOOCOMMERCE"):
                print(f"   1. Use extract_woo_api.py (vou criar agora)")
                print(f"   2. Será ~{(800 // api['limite_por_request']) * 1.5 / 60:.1f} min para 800 produtos")
            
            print()


if __name__ == "__main__":
    asyncio.run(main())
