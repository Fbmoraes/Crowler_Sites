"""
EXTRATOR MH STUDIOS - SHOPIFY API
Usa API JSON nativa do Shopify para máxima confiabilidade
"""

import asyncio
import httpx
from bs4 import BeautifulSoup
from typing import List, Dict, Callable


def extrair_produtos(url_base: str, callback: Callable = None, max_produtos: int = None) -> List[Dict]:
    """
    Interface compatível com QuintApp
    Extrai produtos do MH Studios usando Shopify API
    """
    return asyncio.run(_extrair_mhstudios(url_base, callback, max_produtos))


async def _extrair_mhstudios(url_base: str, callback: Callable = None, max_produtos: int = None) -> List[Dict]:
    """
    Extrai produtos do MH Studios usando:
    1. Sitemap para listar URLs
    2. API Shopify para obter detalhes (mais rápido e confiável)
    """
    def log(msg):
        if callback:
            callback(msg)
        print(f"[MHSTUDIOS] {msg}")
    
    log("Buscando sitemap...")
    
    produtos = []
    
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        try:
            # 1. Busca sitemap index
            resp = await client.get(f"{url_base}/sitemap.xml")
            
            if resp.status_code != 200:
                log(f"Erro ao buscar sitemap: {resp.status_code}")
                return []
            
            soup = BeautifulSoup(resp.text, 'xml')
            
            # 2. Encontra sitemap de produtos
            sitemaps = soup.find_all('sitemap')
            sitemap_produtos_url = None
            
            for sm in sitemaps:
                loc = sm.find('loc')
                if loc and 'sitemap_products' in loc.text:
                    sitemap_produtos_url = loc.text
                    break
            
            if not sitemap_produtos_url:
                log("❌ Sitemap de produtos não encontrado")
                return []
            
            log(f"Sitemap de produtos: {sitemap_produtos_url}")
            
            # 3. Busca URLs de produtos
            resp = await client.get(sitemap_produtos_url)
            soup = BeautifulSoup(resp.text, 'xml')
            urls = soup.find_all('url')
            
            # Filtra apenas produtos (não homepage)
            product_urls = []
            for url_tag in urls:
                loc = url_tag.find('loc')
                if loc and '/products/' in loc.text:
                    product_urls.append(loc.text)
            
            log(f"URLs de produtos encontradas: {len(product_urls)}")
            
            if not product_urls:
                log("❌ Nenhum produto encontrado")
                return []
            
            # Limita quantidade
            if max_produtos:
                product_urls = product_urls[:max_produtos]
                log(f"Limitado a {len(product_urls)} produtos")
            
            # 4. Extrai detalhes via API Shopify
            log("Extraindo detalhes via Shopify API...")
            
            for i, product_url in enumerate(product_urls, 1):
                try:
                    # Extrai handle do produto
                    product_handle = product_url.split('/products/')[-1].split('?')[0]
                    api_url = f"{url_base}/products/{product_handle}.json"
                    
                    resp = await client.get(api_url)
                    
                    if resp.status_code == 200:
                        data = resp.json()
                        product = data.get('product', {})
                        
                        # Pega primeira variante para preço
                        variants = product.get('variants', [])
                        if variants:
                            variant = variants[0]
                            preco = variant.get('price')
                            
                            if preco:
                                produto = {
                                    'nome': product.get('title'),
                                    'preco': f"R$ {float(preco):.2f}",
                                    'marca': product.get('vendor') or 'MHSTUDIOS',
                                    'url': product_url,
                                    'imagem': product.get('images', [{}])[0].get('src') if product.get('images') else None
                                }
                                
                                produtos.append(produto)
                                
                                if i % 10 == 0:
                                    log(f"[{i}/{len(product_urls)}] {produto['nome'][:40]}")
                    
                    # Rate limit
                    await asyncio.sleep(0.2)
                
                except Exception as e:
                    log(f"Erro no produto {product_url}: {str(e)[:50]}")
                    continue
            
            log(f"Total de produtos extraídos: {len(produtos)}")
            return produtos
        
        except Exception as e:
            log(f"Erro na extração: {e}")
            return []


def extrair_detalhes_paralelo(produtos: List[Dict], callback: Callable = None, 
                              max_produtos: int = None, max_workers: int = 20):
    """
    Interface compatível com QuintApp
    Produtos do MH Studios já vêm com detalhes da API, apenas retorna
    """
    if callback:
        callback(f"Produtos já extraídos via API: {len(produtos)}")
    
    if max_produtos:
        produtos = produtos[:max_produtos]
    
    return len(produtos), produtos


# Teste standalone
if __name__ == "__main__":
    print("🧪 Teste do extrator MH Studios\n")
    
    def callback_test(msg):
        print(f"  {msg}")
    
    produtos = extrair_produtos(
        "https://mhstudios.com.br",
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
