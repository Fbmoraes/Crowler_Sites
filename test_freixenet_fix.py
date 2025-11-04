"""
Teste da correção do AggregateOffer para Freixenet
"""
import sys
sys.path.insert(0, r'c:\Users\adria\OneDrive\Documents\projetometa\Crowler_Sites')

from extract_detailsv8 import extrair_json_ld
from bs4 import BeautifulSoup
import httpx

print("Testando extração de preço do Freixenet (AggregateOffer)\n")
print("="*60)

# Testa produto Freixenet
url = 'https://www.freixenet.com.br/italian-rose-750ml-8410036806934/p'
print(f"URL: {url}\n")

try:
    response = httpx.get(url, timeout=15, follow_redirects=True)
    soup = BeautifulSoup(response.text, 'html.parser')
    
    dados = extrair_json_ld(soup)
    
    print("Dados extraídos:")
    print(f"  Nome: {dados.get('nome', 'N/A')}")
    print(f"  Preço: {dados.get('preco', 'N/A')}")
    print(f"  Marca: {dados.get('marca', 'N/A')}")
    print(f"  Imagem: {dados.get('imagem', 'N/A')[:80] if dados.get('imagem') else 'N/A'}...")
    
    print("\n" + "="*60)
    
    if dados.get('preco') and dados.get('preco') != '':
        print("✅ SUCESSO! Preço extraído corretamente")
        print(f"   Preço: R$ {dados['preco']}")
    else:
        print("❌ FALHOU! Preço não foi extraído")
        
except Exception as e:
    print(f"❌ Erro: {e}")
    import traceback
    traceback.print_exc()
