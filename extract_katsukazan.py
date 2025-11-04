"""
EXTRATOR KATSUKAZAN - NUVEMSHOP
Extrai produtos direto dos JSON-LD da homepage
"""

import asyncio
import httpx
from bs4 import BeautifulSoup
import json
from typing import List, Dict, Callable


def extrair_produtos(url_base: str, callback: Callable = None, max_produtos: int = None) -> List[Dict]:
    """
    Interface compatível com QuintApp
    Extrai produtos do Katsukazan (Nuvemshop)
    """
    return asyncio.run(_extrair_katsukazan(url_base, callback, max_produtos))


async def _extrair_katsukazan(url_base: str, callback: Callable = None, max_produtos: int = None) -> List[Dict]:
    """
    Extrai produtos do Katsukazan usando JSON-LD da homepage
    Nuvemshop lista todos os produtos na homepage com dados completos
    """
    def log(msg):
        if callback:
            callback(msg)
        print(f"[KATSUKAZAN] {msg}")
    
    log("Buscando produtos na homepage...")
    
    produtos = []
    
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        try:
            # Busca homepage
            resp = await client.get(url_base)
            
            if resp.status_code != 200:
                log(f"Erro ao acessar homepage: status {resp.status_code}")
                return []
            
            log(f"Homepage acessada: {len(resp.text)} bytes")
            
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # Busca todos os JSON-LD do tipo Product
            json_lds = soup.find_all('script', type='application/ld+json')
            log(f"Scripts JSON-LD encontrados: {len(json_lds)}")
            
            produtos_encontrados = 0
            
            for script in json_lds:
                try:
                    data = json.loads(script.string)
                    
                    # Se for Product, extrai
                    if data.get('@type') == 'Product':
                        nome = data.get('name')
                        
                        # Extrai marca
                        marca = None
                        brand_data = data.get('brand')
                        if isinstance(brand_data, dict):
                            marca = brand_data.get('name')
                        elif isinstance(brand_data, str):
                            marca = brand_data
                        
                        # Extrai preço
                        preco = None
                        offers = data.get('offers', {})
                        if isinstance(offers, dict):
                            preco_raw = offers.get('price')
                            if preco_raw and float(preco_raw) > 0:  # Ignora preço 0
                                preco = f"R$ {float(preco_raw):.2f}"
                        
                        # Extrai URL
                        url = data.get('url')
                        if not url and isinstance(data.get('mainEntityOfPage'), dict):
                            url = data['mainEntityOfPage'].get('@id')
                        
                        # Extrai imagem
                        imagem = data.get('image')
                        if isinstance(imagem, list):
                            imagem = imagem[0] if imagem else None
                        
                        # Verifica disponibilidade
                        availability = offers.get('availability', '')
                        em_estoque = 'InStock' in availability
                        
                        # Adiciona se tem nome e preço válido
                        if nome and preco and em_estoque:
                            produto = {
                                'nome': nome,
                                'preco': preco,
                                'marca': marca or 'Katsukazan',
                                'url': url,
                                'imagem': imagem
                            }
                            produtos.append(produto)
                            produtos_encontrados += 1
                            
                            # Se atingiu limite, para
                            if max_produtos and produtos_encontrados >= max_produtos:
                                log(f"Limite de {max_produtos} produtos atingido")
                                break
                
                except Exception as e:
                    continue
            
            log(f"Total de produtos extraídos: {len(produtos)}")
            
            if not produtos:
                log("⚠️ Nenhum produto válido encontrado")
            
            return produtos
        
        except Exception as e:
            log(f"Erro na extração: {e}")
            return []


def extrair_detalhes_paralelo(produtos: List[Dict], callback: Callable = None, 
                              max_produtos: int = None, max_workers: int = 20):
    """
    Interface compatível com QuintApp
    Produtos do Katsukazan já vêm com detalhes, apenas retorna
    """
    if callback:
        callback(f"Produtos já extraídos com detalhes: {len(produtos)}")
    
    if max_produtos:
        produtos = produtos[:max_produtos]
    
    return len(produtos), produtos


# Teste standalone
if __name__ == "__main__":
    print("🧪 Teste do extrator Katsukazan\n")
    
    def callback_test(msg):
        print(f"  {msg}")
    
    produtos = extrair_produtos(
        "https://katsukazan.com.br",
        callback=callback_test,
        max_produtos=20
    )
    
    print(f"\n✅ {len(produtos)} produtos extraídos\n")
    
    if produtos:
        print("📦 Primeiros 5 produtos:")
        for i, prod in enumerate(produtos[:5], 1):
            print(f"\n{i}. {prod.get('nome', 'N/A')}")
            print(f"   Preço: {prod.get('preco', 'N/A')}")
            print(f"   Marca: {prod.get('marca', 'N/A')}")
            print(f"   URL: {prod.get('url', 'N/A')[:60]}...")
        
        # Estatísticas
        print(f"\n📊 Estatísticas:")
        print(f"   Total: {len(produtos)} produtos")
        com_preco = sum(1 for p in produtos if p.get('preco'))
        print(f"   Com preço: {com_preco}")
        com_marca = sum(1 for p in produtos if p.get('marca') != 'Katsukazan')
        print(f"   Com marca específica: {com_marca}")
