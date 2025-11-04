"""
🧪 TESTE DIRETO DA API - Com payload correto descoberto
Usando o formato searchCriteria que o site usa
"""

import asyncio
import httpx
import json


async def testar_api_com_payload_correto():
    """Testa API usando o formato searchCriteria descoberto"""
    
    # SKU de exemplo
    sku = "281700"
    
    api_url = "https://www.matconcasa.com.br/api/product/basic"
    
    # TESTE 1: Filtro por SKU (adaptando o formato descoberto)
    print("=" * 80)
    print("🧪 TESTE 1: Filtro por SKU usando searchCriteria")
    print("=" * 80)
    print()
    
    payload = {
        "params": {
            "searchCriteria": {
                "filter_groups": [
                    {
                        "filters": [
                            {
                                "condition_type": "eq",  # equal
                                "field": "sku",
                                "value": sku
                            }
                        ]
                    }
                ],
                "pageSize": 1,
                "currentPage": 1
            }
        },
        "tags": ["product"]
    }
    
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Origin": "https://www.matconcasa.com.br",
        "Referer": f"https://www.matconcasa.com.br/produto/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    async with httpx.AsyncClient(timeout=15) as client:
        try:
            print(f"📦 Payload:")
            print(json.dumps(payload, indent=2, ensure_ascii=False))
            print()
            
            response = await client.post(api_url, json=payload, headers=headers)
            
            print(f"📥 Status: {response.status_code}")
            print()
            
            if response.status_code == 200:
                data = response.json()
                print("✅ SUCESSO!")
                print()
                print("📦 Resposta:")
                print(json.dumps(data, indent=2, ensure_ascii=False)[:2000])
                print()
                
                # Salvar para análise
                with open("api_product_response.json", "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                print("💾 Resposta completa salva em: api_product_response.json")
                
            else:
                print(f"❌ Falhou!")
                print(f"Erro: {response.text[:500]}")
        except Exception as e:
            print(f"❌ Exceção: {e}")
    
    print()
    print("=" * 80)
    print()
    
    # TESTE 2: Tentar outros campos
    print("=" * 80)
    print("🧪 TESTE 2: Tentando campo 'entity_id'")
    print("=" * 80)
    print()
    
    payload2 = {
        "params": {
            "searchCriteria": {
                "filter_groups": [
                    {
                        "filters": [
                            {
                                "condition_type": "eq",
                                "field": "entity_id",
                                "value": sku
                            }
                        ]
                    }
                ],
                "pageSize": 1,
                "currentPage": 1
            }
        },
        "tags": ["product"]
    }
    
    async with httpx.AsyncClient(timeout=15) as client:
        try:
            response = await client.post(api_url, json=payload2, headers=headers)
            print(f"📥 Status: {response.status_code}")
            
            if response.status_code == 200:
                print("✅ SUCESSO com entity_id!")
                data = response.json()
                print(json.dumps(data, indent=2, ensure_ascii=False)[:500])
            else:
                print(f"❌ Falhou: {response.text[:200]}")
        except Exception as e:
            print(f"❌ Exceção: {e}")
    
    print()
    print("=" * 80)
    print()
    
    # TESTE 3: URL slug
    print("=" * 80)
    print("🧪 TESTE 3: Tentando campo 'url_key' (slug da URL)")
    print("=" * 80)
    print()
    
    url_slug = "furadeira-makita-de-impacto-1-2-1010w-220v-hp2070-220v-281700"
    
    payload3 = {
        "params": {
            "searchCriteria": {
                "filter_groups": [
                    {
                        "filters": [
                            {
                                "condition_type": "eq",
                                "field": "url_key",
                                "value": url_slug
                            }
                        ]
                    }
                ],
                "pageSize": 1,
                "currentPage": 1
            }
        },
        "tags": ["product"]
    }
    
    async with httpx.AsyncClient(timeout=15) as client:
        try:
            response = await client.post(api_url, json=payload3, headers=headers)
            print(f"📥 Status: {response.status_code}")
            
            if response.status_code == 200:
                print("✅ SUCESSO com url_key!")
                data = response.json()
                print(json.dumps(data, indent=2, ensure_ascii=False)[:500])
            else:
                print(f"❌ Falhou: {response.text[:200]}")
        except Exception as e:
            print(f"❌ Exceção: {e}")
    
    print()
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(testar_api_com_payload_correto())
