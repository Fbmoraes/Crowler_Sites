"""
Teste isolado da API /api/product/basic
Para entender o formato correto de requisição
"""

import asyncio
import httpx
import json


async def testar_api():
    """Testa diferentes abordagens para chamar a API"""
    
    # URL de exemplo
    url_exemplo = "https://www.matconcasa.com.br/produto/furadeira-makita-de-impacto-1-2-1010w-220v-hp2070-220v-281700"
    sku = "281700"  # Extraído da URL
    
    api_url = "https://www.matconcasa.com.br/api/product/basic"
    
    async with httpx.AsyncClient(timeout=15) as client:
        print("=" * 80)
        print("🧪 TESTANDO API /api/product/basic")
        print("=" * 80)
        print(f"SKU: {sku}")
        print()
        
        # TESTE 1: POST com JSON
        print("📝 Teste 1: POST com JSON (storeId=7)")
        try:
            response = await client.post(
                api_url,
                json={"sku": sku, "storeId": 7},
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                }
            )
            print(f"   Status: {response.status_code}")
            print(f"   Headers: {dict(response.headers)}")
            if response.status_code == 200:
                print(f"   ✅ Resposta: {json.dumps(response.json(), indent=2, ensure_ascii=False)[:500]}...")
            else:
                print(f"   ❌ Texto: {response.text[:200]}")
        except Exception as e:
            print(f"   ❌ Erro: {e}")
        print()
        
        # TESTE 2: GET com query params
        print("📝 Teste 2: GET com query params")
        try:
            response = await client.get(
                f"{api_url}?sku={sku}&storeId=7",
                headers={
                    "Accept": "application/json",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                }
            )
            print(f"   Status: {response.status_code}")
            if response.status_code == 200:
                print(f"   ✅ Resposta: {json.dumps(response.json(), indent=2, ensure_ascii=False)[:500]}...")
            else:
                print(f"   ❌ Texto: {response.text[:200]}")
        except Exception as e:
            print(f"   ❌ Erro: {e}")
        print()
        
        # TESTE 3: POST com diferentes storeIds
        print("📝 Teste 3: Tentando diferentes storeIds")
        for store_id in [1, 2, 7]:
            try:
                response = await client.post(
                    api_url,
                    json={"sku": sku, "storeId": store_id},
                    headers={"Content-Type": "application/json"}
                )
                print(f"   storeId={store_id}: {response.status_code}")
                if response.status_code == 200:
                    data = response.json()
                    print(f"      ✅ Dados retornados: {list(data.keys())}")
                    break
            except Exception as e:
                print(f"   storeId={store_id}: Erro - {e}")
        print()
        
        # TESTE 4: Primeiro carregar a página para pegar cookies
        print("📝 Teste 4: Carregando página primeiro (para cookies)")
        try:
            # Carregar página principal
            response = await client.get(url_exemplo)
            print(f"   Página carregada: {response.status_code}")
            print(f"   Cookies recebidos: {len(client.cookies)}")
            
            # Agora tentar API com cookies
            response = await client.post(
                api_url,
                json={"sku": sku, "storeId": 7},
                headers={
                    "Content-Type": "application/json",
                    "Referer": url_exemplo,
                }
            )
            print(f"   API com cookies: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"   ✅ Sucesso! Dados: {json.dumps(data, indent=2, ensure_ascii=False)[:500]}...")
            else:
                print(f"   ❌ Texto: {response.text[:200]}")
        except Exception as e:
            print(f"   ❌ Erro: {e}")
        print()
        
        print("=" * 80)


if __name__ == "__main__":
    asyncio.run(testar_api())
