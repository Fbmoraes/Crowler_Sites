"""
Teste de integração do extrator Petrizi no QuintApp
"""
import asyncio
from extract_petrizi import extrair_produtos

print("="*60)
print("TESTE DE INTEGRAÇÃO - PETRIZI")
print("="*60)

# Testa extração rápida
produtos = asyncio.run(extrair_produtos("https://www.petrizi.com.br", max_produtos=5))

print(f"\n✅ Teste concluído!")
print(f"📊 Total: {len(produtos)} produtos")

if produtos:
    print(f"\n💰 Exemplo de produto:")
    p = produtos[0]
    print(f"   Nome: {p['nome']}")
    print(f"   Preço: R$ {p['preco']:.2f}")
    print(f"   Marca: {p['marca']}")
    print(f"   URL: {p['url']}")
    
    # Verifica estrutura
    print(f"\n🔍 Campos presentes:")
    for campo in p.keys():
        print(f"   - {campo}")
