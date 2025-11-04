"""
🧪 TESTE 4: Tentando identificar o campo correto
Vamos testar com diferentes variações do identificador
"""

import asyncio
import httpx
import json


async def testar_variacoes():
    """Testa diferentes campos e valores"""
    
    api_url = "https://www.matconcasa.com.br/api/product/basic"
    
    # Diferentes IDs da mesma URL
    # https://www.matconcasa.com.br/produto/furadeira-makita-de-impacto-1-2-1010w-220v-hp2070-220v-281700
    url_completa = "https://www.matconcasa.com.br/produto/furadeira-makita-de-impacto-1-2-1010w-220v-hp2070-220v-281700"
    url_slug = "furadeira-makita-de-impacto-1-2-1010w-220v-hp2070-220v-281700"
    sku_final = "281700"
    sku_alternativo = "HP2070-220V"  # Da URL
    sku_produto = "hp2070-220v-281700"  # Última parte
    
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Origin": "https://www.matconcasa.com.br",
        "Referer": url_completa,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    testes = [
        ("SKU numérico", "sku", sku_final),
        ("SKU com código", "sku", sku_alternativo),
        ("SKU completo", "sku", sku_produto),
        ("SKU uppercase", "sku", sku_final.upper()),
        ("ID", "id", sku_final),
        ("Product ID", "product_id", sku_final),
        ("URL path", "url_path", url_slug),
        ("Request path", "request_path", f"produto/{url_slug}"),
    ]
    
    async with httpx.AsyncClient(timeout=15) as client:
        for nome, campo, valor in testes:
            print("=" * 80)
            print(f"🧪 Testando: {nome} | Campo: '{campo}' | Valor: '{valor}'")
            print("=" * 80)
            
            payload = {
                "params": {
                    "searchCriteria": {
                        "filter_groups": [
                            {
                                "filters": [
                                    {
                                        "condition_type": "eq",
                                        "field": campo,
                                        "value": valor
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
            
            try:
                response = await client.post(api_url, json=payload, headers=headers)
                
                if response.status_code == 200:
                    data = response.json()
                    total = data.get("total_count", 0)
                    items = data.get("items", [])
                    
                    if total > 0 and items:
                        print(f"✅ ✅ ✅ SUCESSO! Encontrou {total} produto(s)!")
                        print()
                        print("📦 PRODUTO RETORNADO:")
                        print(json.dumps(items[0], indent=2, ensure_ascii=False)[:1000])
                        print()
                        
                        # Salvar
                        with open(f"api_success_{campo}_{valor}.json", "w", encoding="utf-8") as f:
                            json.dump(data, f, ensure_ascii=False, indent=2)
                        
                        print(f"💾 Salvo em: api_success_{campo}_{valor}.json")
                        print()
                        print("🎯 CAMPO CORRETO IDENTIFICADO!")
                        return campo, valor
                    else:
                        print(f"❌ Retornou vazio (total_count: {total})")
                else:
                    print(f"❌ Status {response.status_code}: {response.text[:150]}")
                    
            except Exception as e:
                print(f"❌ Erro: {e}")
            
            print()
            await asyncio.sleep(0.5)  # Pequeno delay entre requests
    
    print("=" * 80)
    print("😞 Nenhum campo funcionou. Vamos tentar abordagem diferente...")
    print("=" * 80)
    return None, None


async def testar_busca_textual():
    """Tenta busca por termo textual"""
    print()
    print("=" * 80)
    print("🔍 TESTE: Busca por termo textual (searchTerm)")
    print("=" * 80)
    print()
    
    api_url = "https://www.matconcasa.com.br/api/product/basic"
    
    # Tentar com termo de busca
    payload = {
        "params": {
            "searchCriteria": {
                "filter_groups": [
                    {
                        "filters": [
                            {
                                "condition_type": "like",
                                "field": "name",
                                "value": "%makita%"
                            }
                        ]
                    }
                ],
                "pageSize": 5,
                "currentPage": 1
            }
        },
        "tags": ["search"]
    }
    
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0"
    }
    
    async with httpx.AsyncClient(timeout=15) as client:
        try:
            response = await client.post(api_url, json=payload, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                total = data.get("total_count", 0)
                print(f"✅ Encontrou {total} produtos com 'makita'")
                
                if total > 0:
                    print()
                    print("📦 Exemplo de produto:")
                    items = data.get("items", [])
                    if items:
                        produto = items[0]
                        print(json.dumps(produto, indent=2, ensure_ascii=False)[:800])
            else:
                print(f"❌ Status {response.status_code}: {response.text[:200]}")
                
        except Exception as e:
            print(f"❌ Erro: {e}")


async def main():
    # Tentar encontrar o campo correto
    campo, valor = await testar_variacoes()
    
    if not campo:
        # Se não encontrou, tentar busca textual
        await testar_busca_textual()


if __name__ == "__main__":
    asyncio.run(main())
