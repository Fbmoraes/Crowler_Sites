"""
MatConcasa - Tentar interceptar chamadas de API
"""

import asyncio
from playwright.async_api import async_playwright
import json

async def intercept_api():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        api_calls = []
        
        # Interceptar todas as requisições
        async def handle_response(response):
            if any(word in response.url for word in ['api', 'product', 'produto', 'graphql', 'data', 'json']):
                try:
                    if 'json' in response.headers.get('content-type', '').lower():
                        data = await response.json()
                        api_calls.append({
                            'url': response.url,
                            'status': response.status,
                            'data': data
                        })
                        print(f"\n✓ API Call: {response.url}")
                        print(f"  Status: {response.status}")
                        print(f"  Data keys: {list(data.keys()) if isinstance(data, dict) else 'list'}")
                except:
                    pass
        
        page.on('response', handle_response)
        
        url = "https://www.matconcasa.com.br/produto/ducha-hydra-optima-8-temperaturas-5500w-127v-dpop-8-551br-362905"
        
        print(f"Navegando para: {url}\n")
        print("Interceptando requisições...\n")
        
        await page.goto(url, wait_until='networkidle', timeout=30000)
        await page.wait_for_timeout(3000)
        
        print(f"\n\n=== Resumo ===")
        print(f"API Calls capturadas: {len(api_calls)}")
        
        if api_calls:
            print("\n=== Detalhes das APIs ===")
            for i, call in enumerate(api_calls, 1):
                print(f"\n{i}. {call['url']}")
                print(f"   Status: {call['status']}")
                # Salvar dados
                with open(f'api_matcon_{i}.json', 'w', encoding='utf-8') as f:
                    json.dump(call['data'], f, indent=2, ensure_ascii=False)
                print(f"   ✓ Dados salvos em: api_matcon_{i}.json")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(intercept_api())
