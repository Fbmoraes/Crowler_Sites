"""
Extrator específico para Dermomanipulações
Site usa plataforma Wake Commerce com estrutura diferente
"""

import asyncio
import httpx
from bs4 import BeautifulSoup
import json
from urllib.parse import urljoin, urlparse
from typing import List, Dict, Callable
import time

async def buscar_produtos_dermo(callback: Callable = None) -> List[Dict]:
    """
    Busca produtos do Dermomanipulações
    Estratégia: Extrai produtos direto das categorias no sitemap
    """
    url_base = "https://www.dermomanipulacoes.com.br"
    produtos = []
    categorias_processadas = set()
    
    def log(msg):
        if callback:
            callback(msg)
        print(msg)
    
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        # Buscar sitemap
        log("🔍 Buscando sitemap...")
        
        try:
            resp = await client.get(f"{url_base}/sitemap.xml")
            
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'xml')
                urls = soup.find_all('url')
                
                log(f"📋 Sitemap com {len(urls)} URLs")
                
                # Filtrar URLs que são categorias (não têm /produto/)
                # Excluir páginas institucionais
                excluir_patterns = [
                    '/atendimento', '/quemsomos', '/contato', '/politica',
                    '/termos', '/duvidas', '/trocas', '/entrega', '/compra',
                    '/pagamento', '/receita', '/carrinho', '/checkout',
                    '/login', '/cadastro', '/conta', '/pedidos', '/favoritos',
                    '/home-', '/dia-', '/outlet', '/frete', '/formas'
                ]
                
                categorias_urls = []
                
                for url_tag in urls:
                    loc = url_tag.find('loc')
                    if loc:
                        url = loc.text.strip()
                        
                        # Pular homepage
                        if url == f"{url_base}/" or url == url_base:
                            continue
                        
                        # Pular se já é produto individual
                        if '/produto/' in url:
                            continue
                        
                        # Pular se contém padrões institucionais
                        path = urlparse(url).path.lower()
                        if any(excluir in path for excluir in excluir_patterns):
                            continue
                        
                        # URLs curtas sem / no meio geralmente são categorias
                        # Ex: /minoxidil, /anastrozol
                        path_limpo = path.strip('/')
                        if path_limpo and '/' not in path_limpo:
                            categorias_urls.append(url)
                
                log(f"📂 {len(categorias_urls)} categorias encontradas")
                
                # Processa cada categoria e extrai produtos do JSON-LD
                log("🔍 Extraindo produtos das categorias...")
                
                for i, cat_url in enumerate(categorias_urls, 1):
                    try:
                        resp = await client.get(cat_url)
                        
                        if resp.status_code == 200:
                            soup = BeautifulSoup(resp.text, 'html.parser')
                            
                            # Busca JSON-LD do tipo ItemList
                            json_lds = soup.find_all('script', type='application/ld+json')
                            
                            for script in json_lds:
                                try:
                                    data = json.loads(script.string)
                                    
                                    # Se é ItemList, tem produtos
                                    if data.get('@type') == 'ItemList':
                                        items = data.get('itemListElement', [])
                                        
                                        for item in items:
                                            if item.get('@type') == 'Product':
                                                produto = {
                                                    'nome': item.get('name'),
                                                    'url': item.get('url'),
                                                    'imagem': item.get('image')
                                                }
                                                
                                                # Extrai preço
                                                offers = item.get('offers', {})
                                                if isinstance(offers, dict):
                                                    produto['preco'] = offers.get('price')
                                                
                                                # Adiciona se tem dados válidos
                                                if produto['nome'] and produto['url']:
                                                    produtos.append(produto)
                                        
                                        if items:
                                            log(f"✅ [{i}/{len(categorias_urls)}] {cat_url}: {len(items)} produtos")
                                
                                except:
                                    continue
                        
                        # Rate limit
                        await asyncio.sleep(0.3)
                    
                    except Exception as e:
                        log(f"⚠️ Erro em {cat_url}: {e}")
                        continue
                
                log(f"✅ Total: {len(produtos)} produtos extraídos")
        
        except Exception as e:
            log(f"⚠️ Erro no sitemap: {e}")
    
    return produtos


async def extrair_dermo_completo(max_produtos: int = 50, callback: Callable = None):
    """
    Extração completa do Dermomanipulações
    """
    def log(msg):
        if callback:
            callback(msg)
        print(msg)
    
    inicio = time.time()
    
    # Busca produtos (já com detalhes) das categorias
    log("=" * 60)
    log("EXTRAÇÃO DERMOMANIPULAÇÕES")
    log("=" * 60)
    
    produtos = await buscar_produtos_dermo(callback)
    
    if not produtos:
        log("❌ Nenhum produto encontrado")
        return []
    
    # Limita quantidade
    produtos = produtos[:max_produtos]
    
    log(f"\n⏱️ Tempo total: {time.time() - inicio:.1f}s")
    log(f"✅ {len(produtos)} produtos extraídos")
    
    return produtos


async def main():
    print("🚀 Iniciando extração do Dermomanipulações\n")
    
    produtos = await extrair_dermo_completo(max_produtos=50)
    
    if produtos:
        print("\n" + "=" * 60)
        print("RESULTADOS")
        print("=" * 60)
        
        # Salvar JSON
        with open("dermo_produtos.json", "w", encoding="utf-8") as f:
            json.dump(produtos, f, ensure_ascii=False, indent=2)
        
        print(f"✅ {len(produtos)} produtos salvos em dermo_produtos.json")
        
        # Mostrar primeiros 5
        print("\n📦 Primeiros 5 produtos:")
        for i, prod in enumerate(produtos[:5], 1):
            print(f"\n{i}. {prod.get('nome', 'N/A')}")
            print(f"   Preço: {prod.get('preco', 'N/A')}")
            print(f"   Marca: {prod.get('marca', 'N/A')}")
            print(f"   URL: {prod.get('url', 'N/A')}")


if __name__ == "__main__":
    asyncio.run(main())
