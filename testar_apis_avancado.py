#!/usr/bin/env python3
"""
TESTE DE APIS MAGENTO E FALLBACK PARA CASAS BAHIA
==================================================
Testa APIs REST do Magento e busca endpoints alternativos para sites custom.
"""

import asyncio
import httpx
import json
from urllib.parse import urlparse, urljoin

async def testar_apis_magento(url_base: str):
    """
    Testa diversas APIs do Magento 2 (REST API pública).
    """
    print(f"\n{'='*100}")
    print(f"TESTANDO APIs MAGENTO: {url_base}")
    print(f"{'='*100}\n")
    
    endpoints_magento = [
        # Magento 2 REST API (sem auth - dados públicos)
        "/rest/V1/products?searchCriteria[pageSize]=10&searchCriteria[currentPage]=1",
        "/rest/default/V1/products?searchCriteria[pageSize]=10&searchCriteria[currentPage]=1",
        "/rest/all/V1/products?searchCriteria[pageSize]=10&searchCriteria[currentPage]=1",
        
        # GraphQL (Magento 2.3+)
        "/graphql",
        
        # Endpoints alternativos
        "/api/rest/products?limit=10",
        "/api/products.json?limit=10",
    ]
    
    resultados = []
    
    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        for endpoint in endpoints_magento:
            url = urljoin(url_base, endpoint)
            print(f"🔍 Testando: {endpoint}")
            
            try:
                if endpoint == "/graphql":
                    # Teste GraphQL
                    query = {
                        "query": """
                        {
                          products(pageSize: 1) {
                            items {
                              name
                              sku
                              price_range {
                                minimum_price {
                                  final_price { value currency }
                                }
                              }
                            }
                          }
                        }
                        """
                    }
                    response = await client.post(url, json=query)
                else:
                    response = await client.get(url)
                
                print(f"   Status: {response.status_code}")
                
                if response.status_code == 200:
                    try:
                        data = response.json()
                        print(f"   ✅ JSON válido retornado!")
                        
                        # Verificar estrutura
                        if isinstance(data, dict):
                            if 'items' in data:
                                print(f"      Produtos encontrados: {len(data['items'])}")
                                resultados.append({
                                    "endpoint": endpoint,
                                    "funciona": True,
                                    "tipo": "Magento REST API",
                                    "exemplo": data['items'][0] if data['items'] else None
                                })
                            elif 'data' in data and 'products' in data.get('data', {}):
                                print(f"      GraphQL funciona!")
                                resultados.append({
                                    "endpoint": endpoint,
                                    "funciona": True,
                                    "tipo": "Magento GraphQL",
                                    "exemplo": data['data']['products']
                                })
                    except json.JSONDecodeError:
                        print(f"   ⚠️  Resposta não é JSON válido")
                
            except Exception as e:
                print(f"   ❌ Erro: {str(e)[:50]}")
            
            print()
    
    return resultados


async def testar_endpoints_alternativos(url_base: str):
    """
    Testa endpoints alternativos comuns em sites e-commerce custom.
    """
    print(f"\n{'='*100}")
    print(f"TESTANDO ENDPOINTS ALTERNATIVOS: {url_base}")
    print(f"{'='*100}\n")
    
    endpoints_alternativos = [
        # APIs REST comuns
        "/api/products",
        "/api/v1/products",
        "/api/v2/products",
        "/api/catalog/products",
        
        # APIs de busca
        "/busca/produtos",
        "/search/api",
        "/api/search",
        
        # Next.js / React APIs
        "/_next/data/",
        "/api/listing",
        
        # Outros padrões
        "/produto/api",
        "/catalogo/api",
    ]
    
    resultados = []
    
    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        for endpoint in endpoints_alternativos:
            url = urljoin(url_base, endpoint)
            print(f"🔍 Testando: {endpoint}")
            
            try:
                response = await client.get(url, params={"limit": 1, "page": 1})
                print(f"   Status: {response.status_code}")
                
                if response.status_code == 200:
                    content_type = response.headers.get('content-type', '')
                    
                    if 'json' in content_type.lower():
                        try:
                            data = response.json()
                            print(f"   ✅ JSON encontrado!")
                            print(f"   Chaves: {list(data.keys())[:5]}")
                            
                            resultados.append({
                                "endpoint": endpoint,
                                "funciona": True,
                                "tipo": "API REST Custom",
                                "exemplo": data
                            })
                        except:
                            pass
                    
            except Exception as e:
                print(f"   ❌ Erro: {str(e)[:50]}")
            
            print()
    
    return resultados


async def analisar_network_requests(url_produto: str):
    """
    Analisa requisições XHR/Fetch que a página faz (simula DevTools Network).
    """
    print(f"\n{'='*100}")
    print(f"ANALISANDO REQUISIÇÕES DA PÁGINA: {url_produto}")
    print(f"{'='*100}\n")
    
    print("📝 INSTRUÇÕES MANUAIS:")
    print("   1. Abra DevTools (F12) na página do produto")
    print("   2. Vá em Network > XHR ou Fetch")
    print("   3. Recarregue a página")
    print("   4. Procure por requisições JSON com dados do produto")
    print("   5. Anote os endpoints que aparecem\n")
    
    # Tentar capturar via scraping
    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        try:
            response = await client.get(url_produto)
            html = response.text
            
            # Buscar por endpoints de API no HTML
            import re
            
            # Padrões comuns de endpoints de API no HTML/JS
            padroes = [
                r'["\'](\/api\/[^"\']+)["\']',
                r'["\'](\/rest\/[^"\']+)["\']',
                r'["\'](\/graphql)["\']',
                r'apiUrl\s*[:=]\s*["\']([^"\']+)["\']',
                r'endpoint\s*[:=]\s*["\']([^"\']+)["\']',
            ]
            
            endpoints_encontrados = set()
            
            for padrao in padroes:
                matches = re.findall(padrao, html)
                endpoints_encontrados.update(matches)
            
            if endpoints_encontrados:
                print("🎯 Endpoints de API encontrados no HTML/JS:")
                for endpoint in sorted(endpoints_encontrados)[:10]:
                    print(f"   • {endpoint}")
            else:
                print("⚠️  Nenhum endpoint de API óbvio encontrado no HTML")
            
        except Exception as e:
            print(f"❌ Erro ao analisar: {e}")


async def main():
    print("="*100)
    print("DETECTOR AVANÇADO DE APIs E-COMMERCE")
    print("="*100)
    
    # Matcon Casa (Magento)
    print("\n\n🏪 SITE 1: MATCON CASA (Magento detectado)")
    matcon_apis_magento = await testar_apis_magento("https://www.matconcasa.com.br")
    matcon_apis_alt = await testar_endpoints_alternativos("https://www.matconcasa.com.br")
    
    # Casas Bahia (Custom)
    print("\n\n🏪 SITE 2: CASAS BAHIA (Plataforma custom)")
    cb_apis_alt = await testar_endpoints_alternativos("https://www.casasbahia.com.br")
    
    # Analisar uma página de produto específica
    await analisar_network_requests("https://www.matconcasa.com.br/produto/exemplo")
    await analisar_network_requests("https://www.casasbahia.com.br/geladeira-refrigerador-electrolux-frost-free-duplex-427l-prata-dw48x-1567087316/p/1567087316")
    
    # RESUMO FINAL
    print(f"\n{'='*100}")
    print("RESUMO FINAL")
    print(f"{'='*100}\n")
    
    total_apis = len(matcon_apis_magento) + len(matcon_apis_alt) + len(cb_apis_alt)
    
    if total_apis > 0:
        print(f"✅ {total_apis} APIs funcionais encontradas!\n")
        
        for api in matcon_apis_magento + matcon_apis_alt + cb_apis_alt:
            print(f"   🚀 {api['tipo']}: {api['endpoint']}")
    else:
        print("⚠️  Nenhuma API pública encontrada.")
        print("\n🎯 OPÇÕES RESTANTES:")
        print("   1. Usar Zyte API (extração automática com AI)")
        print("   2. Usar Oxylabs/ZenRows (e-commerce scraper API)")
        print("   3. Continuar com scraping HTML + LeakyBucket rate limiting")
        print("   4. Usar Crawlee (open-source com AutoscaledPool)")
    
    print(f"\n{'='*100}\n")


if __name__ == "__main__":
    asyncio.run(main())
