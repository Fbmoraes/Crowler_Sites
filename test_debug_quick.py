"""
Teste rápido com debug
"""
import asyncio
import httpx
from test_html_ssr_refinado import extrair_produto_via_html_refinado, TokenBucket

async def test():
    rate_limiter = TokenBucket(3.0)  # 3 requests per second
    
    url = "https://www.matconcasa.com.br/produto/furadeira-makita-de-impacto-1-2-1010w-220v-hp2070-220v-281700"
    
    async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
        result = await extrair_produto_via_html_refinado(client, url, rate_limiter)
        
        print("\n" + "="*80)
        print("RESULTADO:")
        print("="*80)
        print(f"Nome: {result.get('nome')}")
        print(f"Preço: {result.get('preco', 'N/A')}")
        print(f"Preço Original: {result.get('preco_original', 'N/A')}")
        print(f"Imagens: {len(result.get('imagens', []))}")
        print(f"SKU: {result.get('sku', 'N/A')}")

asyncio.run(test())
