"""
Teste simplificado do extrator MatConcasa
Testa apenas 2 produtos para validação rápida
"""

import asyncio
from extract_matcon import extrair_produtos, extrair_detalhes_paralelo

async def main():
    print("=== Teste MatConcasa (Simplificado) ===\n")
    
    # 1. Descobrir URLs (apenas 2 para teste rápido)
    print("1. Descobrindo URLs (max 2)...\n")
    urls = extrair_produtos("https://www.matconcasa.com.br", max_produtos=2)
    print(f"\n✓ {len(urls)} URLs encontradas")
    
    if not urls:
        print("❌ Nenhuma URL encontrada!")
        return
    
    for i, url in enumerate(urls, 1):
        print(f"  {i}. {url['url']}")
    
    # 2. Extrair detalhes (apenas 2 produtos)
    print(f"\n2. Extraindo detalhes (2 produtos)...\n")
    tipo, produtos = extrair_detalhes_paralelo(urls, max_produtos=2, max_workers=2)
    
    print(f"\n=== Resultados ===")
    print(f"Tipo: {tipo}")
    print(f"Produtos processados: {len(produtos)}")
    
    com_dados = [p for p in produtos if p.get('nome') and p.get('preco')]
    print(f"Com nome e preço: {len(com_dados)}")
    
    print(f"\n=== Detalhes ===")
    for i, p in enumerate(produtos, 1):
        print(f"\nProduto {i}:")
        print(f"  URL: {p.get('url', 'N/A')[:80]}")
        print(f"  Nome: {p.get('nome', 'N/A')[:80]}")
        print(f"  Preço: R$ {p.get('preco', 'N/A')}")
        print(f"  Marca: {p.get('marca', 'N/A')}")
        print(f"  Imagem: {'✓' if p.get('imagem') else '✗'}")

if __name__ == "__main__":
    asyncio.run(main())
