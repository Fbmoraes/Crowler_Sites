"""
Extrator específico para Petrizi (Plataforma Tray)
Estratégia: Sitemap → HTML microdata parsing

IMPORTANTE: Tray não usa JSON-LD para produtos, usa microdata HTML (itemprop)
"""
import asyncio
import httpx
from bs4 import BeautifulSoup
from datetime import datetime
import re
from typing import List, Dict, Optional
import xml.etree.ElementTree as ET

BASE_URL = "https://www.petrizi.com.br"
SITEMAP_URL = f"{BASE_URL}/sitemap.xml"
RATE_LIMIT = 0.25  # 250ms entre requests

class PetriziExtractor:
    def __init__(self):
        self.client = None
        
    async def __aenter__(self):
        self.client = httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
        )
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.client:
            await self.client.aclose()
    
    def extrair_preco(self, soup: BeautifulSoup) -> Optional[float]:
        """Extrai preço do microdata HTML"""
        try:
            # Método 1: span com itemprop="price"
            price_span = soup.find('span', {'itemprop': 'price'})
            if price_span:
                # Pegar do atributo content primeiro
                content = price_span.get('content')
                if content:
                    return float(content.replace(',', '.'))
                
                # Se não tem content, pegar do texto
                text = price_span.get_text().strip()
                # Remove "R$" e espaços, troca vírgula por ponto
                text = re.sub(r'[R$\s]', '', text).replace(',', '.')
                if text:
                    return float(text)
            
            # Método 2: div class preco-por com itemprop offers
            preco_div = soup.find('div', class_='preco-por')
            if preco_div:
                price_span = preco_div.find('span', {'itemprop': 'price'})
                if price_span:
                    content = price_span.get('content')
                    if content:
                        return float(content.replace(',', '.'))
            
            return None
            
        except Exception as e:
            print(f"   ⚠️  Erro ao extrair preço: {e}")
            return None
    
    def extrair_nome(self, soup: BeautifulSoup) -> Optional[str]:
        """Extrai nome do produto"""
        try:
            # Método 1: h1 com itemprop="name"
            name_h1 = soup.find('h1', {'itemprop': 'name'})
            if name_h1:
                return name_h1.get_text().strip()
            
            # Método 2: span com itemprop="name" dentro de article
            article = soup.find('article')
            if article:
                name_span = article.find('span', {'itemprop': 'name'})
                if name_span:
                    return name_span.get_text().strip()
            
            # Método 3: meta og:title
            og_title = soup.find('meta', {'property': 'og:title'})
            if og_title:
                title = og_title.get('content', '')
                # Remove " - Petrizi Makeup" do final
                return title.split(' - ')[0].strip()
            
            return None
            
        except Exception as e:
            print(f"   ⚠️  Erro ao extrair nome: {e}")
            return None
    
    def extrair_imagem(self, soup: BeautifulSoup) -> Optional[str]:
        """Extrai URL da imagem"""
        try:
            # Método 1: img com itemprop="image"
            img = soup.find('img', {'itemprop': 'image'})
            if img:
                src = img.get('data-original') or img.get('src')
                if src:
                    return src
            
            # Método 2: meta og:image
            og_image = soup.find('meta', {'property': 'og:image'})
            if og_image:
                return og_image.get('content')
            
            return None
            
        except Exception as e:
            print(f"   ⚠️  Erro ao extrair imagem: {e}")
            return None
    
    def extrair_marca(self, soup: BeautifulSoup) -> str:
        """Extrai marca do produto"""
        try:
            # Método 1: span com itemprop="brand"
            brand_span = soup.find('span', {'itemprop': 'brand'})
            if brand_span:
                return brand_span.get_text().strip()
            
            # Método 2: meta com property="og:brand"
            og_brand = soup.find('meta', {'property': 'og:brand'})
            if og_brand:
                return og_brand.get('content', '')
            
            # Fallback: Petrizi Makeup
            return "Petrizi Makeup"
            
        except Exception:
            return "Petrizi Makeup"
    
    async def extrair_produto(self, url: str) -> Optional[Dict]:
        """Extrai dados de um produto"""
        try:
            response = await self.client.get(url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            nome = self.extrair_nome(soup)
            preco = self.extrair_preco(soup)
            imagem = self.extrair_imagem(soup)
            marca = self.extrair_marca(soup)
            
            if not nome:
                print(f"   ⚠️  Nome não encontrado em {url}")
                return None
            
            produto = {
                'nome': nome,
                'preco': preco if preco else 0.0,
                'preco_original': preco if preco else 0.0,
                'url': url,
                'imagem': imagem or '',
                'marca': marca,
                'disponivel': preco is not None,
                'plataforma': 'Tray',
                'extraido_em': datetime.now().isoformat()
            }
            
            return produto
            
        except Exception as e:
            print(f"   ❌ Erro ao extrair {url}: {e}")
            return None
    
    async def obter_urls_sitemap(self) -> List[str]:
        """Obtém URLs de produtos do sitemap"""
        try:
            print(f"\n📄 Buscando sitemap: {SITEMAP_URL}")
            
            # Primeiro, pegar o sitemap index
            response = await self.client.get(SITEMAP_URL)
            response.raise_for_status()
            
            # Parse do sitemap index
            root = ET.fromstring(response.content)
            ns = {'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
            
            # Pegar URL do sitemap filho
            sitemap_locs = root.findall('.//sm:loc', ns)
            
            if not sitemap_locs:
                print("   ⚠️  Nenhum sitemap filho encontrado")
                return []
            
            child_sitemap_url = sitemap_locs[0].text
            print(f"   ✅ Sitemap filho: {child_sitemap_url}")
            
            # Buscar sitemap filho
            response = await self.client.get(child_sitemap_url)
            response.raise_for_status()
            
            # Parse do sitemap filho
            root = ET.fromstring(response.content)
            urls = []
            
            for url_elem in root.findall('.//sm:url', ns):
                loc = url_elem.find('sm:loc', ns)
                if loc is not None and loc.text:
                    url = loc.text
                    # Filtrar apenas URLs de produtos
                    # URLs de produtos Tray geralmente têm estrutura: /categoria/produto
                    if url.count('/') >= 4:  # https://www.petrizi.com.br/categoria/produto
                        urls.append(url)
            
            print(f"   ✅ {len(urls)} produtos encontrados no sitemap")
            return urls
            
        except Exception as e:
            print(f"   ❌ Erro ao obter sitemap: {e}")
            return []


async def _extrair_produtos_async(url: str, callback=None, max_produtos: int = 20):
    """
    Extrai produtos da Petrizi (versão async interna)
    
    Args:
        url: URL base do site
        callback: Função para callback de progresso
        max_produtos: Número máximo de produtos para extrair
    """
    print(f"\n{'='*60}")
    print(f"🎯 EXTRATOR PETRIZI (Tray)")
    print(f"{'='*60}")
    print(f"📦 Máximo de produtos: {max_produtos}")
    print(f"⏱️  Rate limit: {RATE_LIMIT}s entre requests")
    
    async with PetriziExtractor() as extractor:
        # 1. Obter URLs do sitemap
        urls = await extractor.obter_urls_sitemap()
        
        if not urls:
            print("\n❌ Nenhuma URL encontrada no sitemap")
            return []
        
        # Limitar quantidade
        urls = urls[:max_produtos]
        print(f"\n🔄 Processando {len(urls)} produtos...")
        
        # 2. Extrair produtos
        produtos = []
        for i, url in enumerate(urls, 1):
            print(f"\n[{i}/{len(urls)}] {url}")
            
            produto = await extractor.extrair_produto(url)
            
            if produto:
                produtos.append(produto)
                print(f"   ✅ {produto['nome']} - R$ {produto['preco']:.2f}")
                
                if callback:
                    callback({
                        'tipo': 'produto_extraido',
                        'produto': produto,
                        'progresso': i / len(urls)
                    })
            
            # Rate limit
            if i < len(urls):
                await asyncio.sleep(RATE_LIMIT)
        
        print(f"\n{'='*60}")
        print(f"✅ EXTRAÇÃO CONCLUÍDA")
        print(f"{'='*60}")
        print(f"📊 Produtos extraídos: {len(produtos)}")
        if produtos:
            total_preco = sum(p['preco'] for p in produtos)
            print(f"💰 Valor total: R$ {total_preco:.2f}")
        
        return produtos


def extrair_produtos(url: str, callback=None, max_produtos: int = 20):
    """
    Wrapper síncrono para integração com QuintApp
    Petrizi retorna produtos completos (não precisa de fase de detalhes)
    """
    return asyncio.run(_extrair_produtos_async(url, callback, max_produtos))


# Para testes diretos
if __name__ == "__main__":
    produtos = extrair_produtos(BASE_URL, max_produtos=20)
    
    print(f"\n\n📋 RESUMO:")
    print(f"Total: {len(produtos)} produtos")
    
    for p in produtos[:5]:
        print(f"\n• {p['nome']}")
        print(f"  Preço: R$ {p['preco']:.2f}")
        print(f"  Marca: {p['marca']}")
        print(f"  URL: {p['url']}")
