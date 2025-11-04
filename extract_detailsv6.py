"""
Extração de detalhes de produtos usando Playwright (v6)
Resolve sites JavaScript-heavy como Next.js App Router
Usa browser real para renderizar conteúdo dinâmico
"""

import re
import json
from typing import Dict, List, Optional
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright, Page, Browser, TimeoutError as PlaywrightTimeout
import time


class ExtractDetailsV6:
    def __init__(self):
        self.cache_produtos = {}
        self.timeout = 30000  # 30 segundos
        
    def _limpar_preco(self, texto: str) -> Optional[float]:
        """Extrai e converte preço de texto"""
        if not texto:
            return None
        
        # Remove tudo exceto números, vírgula e ponto
        limpo = re.sub(r'[^\d,.]', '', texto)
        
        # Converte para float
        if ',' in limpo and '.' in limpo:
            # Formato: 1.234,56
            limpo = limpo.replace('.', '').replace(',', '.')
        elif ',' in limpo:
            # Formato: 1234,56
            limpo = limpo.replace(',', '.')
        
        try:
            return float(limpo)
        except:
            return None
    
    def _extrair_json_ld(self, page: Page) -> Optional[Dict]:
        """Extrai dados de JSON-LD se disponível"""
        try:
            json_ld_data = page.evaluate('''
                () => {
                    const scripts = document.querySelectorAll('script[type="application/ld+json"]');
                    const data = [];
                    scripts.forEach(script => {
                        try {
                            data.push(JSON.parse(script.textContent));
                        } catch (e) {}
                    });
                    return data;
                }
            ''')
            
            if json_ld_data:
                # Procura por Product schema
                for item in json_ld_data:
                    if isinstance(item, dict):
                        if item.get('@type') == 'Product':
                            return item
                        # Às vezes está em @graph
                        if '@graph' in item:
                            for graph_item in item['@graph']:
                                if isinstance(graph_item, dict) and graph_item.get('@type') == 'Product':
                                    return graph_item
            return None
        except Exception as e:
            return None
    
    def _extrair_meta_tags(self, page: Page) -> Dict:
        """Extrai dados de meta tags"""
        try:
            meta_data = page.evaluate('''
                () => {
                    const data = {};
                    
                    // Open Graph tags
                    const ogTitle = document.querySelector('meta[property="og:title"]');
                    if (ogTitle) data.og_title = ogTitle.content;
                    
                    const ogImage = document.querySelector('meta[property="og:image"]');
                    if (ogImage) data.og_image = ogImage.content;
                    
                    const ogDescription = document.querySelector('meta[property="og:description"]');
                    if (ogDescription) data.og_description = ogDescription.content;
                    
                    // Product tags
                    const productPrice = document.querySelector('meta[property="product:price:amount"]');
                    if (productPrice) data.product_price = productPrice.content;
                    
                    const productBrand = document.querySelector('meta[property="product:brand"]');
                    if (productBrand) data.product_brand = productBrand.content;
                    
                    // Twitter tags
                    const twitterTitle = document.querySelector('meta[name="twitter:title"]');
                    if (twitterTitle) data.twitter_title = twitterTitle.content;
                    
                    return data;
                }
            ''')
            return meta_data
        except:
            return {}
    
    def _extrair_dados_visualizacao(self, page: Page, url: str) -> Dict:
        """Extrai dados visíveis na página usando seletores inteligentes"""
        dados = {
            'nome': None,
            'preco': None,
            'preco_original': None,
            'disponivel': None,
            'marca': None,
            'sku': None,
            'categoria': None,
            'subcategoria': None,
            'categorias_completas': None,
            'imagens': [],
            'descricao': None,
            'estoque': None,
            'estoque_quantidade': None,
            'moeda': 'BRL',
        }
        
        try:
            # ========== NOME DO PRODUTO ==========
            # Tenta vários seletores comuns para nome
            seletores_nome = [
                'h1',
                '[data-testid="product-name"]',
                '[class*="product-name" i]',
                '[class*="product-title" i]',
                '[itemprop="name"]',
                '.product-name',
                '.product-title',
                'h1.title',
            ]
            
            for seletor in seletores_nome:
                try:
                    element = page.query_selector(seletor)
                    if element:
                        texto = element.inner_text().strip()
                        if texto and len(texto) > 3:  # Nome válido
                            dados['nome'] = texto
                            break
                except:
                    continue
            
            # Fallback: título da página
            if not dados['nome']:
                title = page.title()
                if title:
                    # Remove nome da loja
                    dados['nome'] = re.sub(r'\s*\|\s*.*$', '', title).strip()
            
            # ========== PREÇO ==========
            # Tenta extrair preço de várias formas
            seletores_preco = [
                '[data-testid="price"]',
                '[class*="price" i]:not([class*="original" i]):not([class*="old" i])',
                '[itemprop="price"]',
                '[class*="selling" i]',
                '[class*="current" i]',
                '.price',
                '.selling-price',
                'span[class*="price"]',
            ]
            
            for seletor in seletores_preco:
                try:
                    elements = page.query_selector_all(seletor)
                    for element in elements:
                        texto = element.inner_text().strip()
                        preco = self._limpar_preco(texto)
                        if preco and preco > 0:
                            # Pega o menor preço válido (geralmente é o preço de venda)
                            if not dados['preco'] or preco < dados['preco']:
                                dados['preco'] = preco
                except:
                    continue
            
            # ========== PREÇO ORIGINAL ==========
            seletores_preco_original = [
                '[class*="original-price" i]',
                '[class*="old-price" i]',
                '[class*="list-price" i]',
                '[class*="de:" i]',
                'del',
                's',
            ]
            
            for seletor in seletores_preco_original:
                try:
                    element = page.query_selector(seletor)
                    if element:
                        texto = element.inner_text().strip()
                        preco = self._limpar_preco(texto)
                        if preco and preco > 0:
                            dados['preco_original'] = preco
                            break
                except:
                    continue
            
            # ========== DISPONIBILIDADE / ESTOQUE ==========
            # Procura por informações de estoque
            page_content_lower = page.content().lower()
            
            # Sinais claros de indisponibilidade
            sinais_indisponivel = [
                'indisponível',
                'esgotado',
                'out of stock',
                'sem estoque',
                'produto esgotado',
                'unavailable',
                'discontinued',
                'descontinuado'
            ]
            
            # Sinais claros de disponibilidade
            sinais_disponivel = [
                'in stock',
                'em estoque',
                'disponível',
                'available',
                'comprar',
                'adicionar ao carrinho',
                'add to cart'
            ]
            
            # Verifica indisponibilidade primeiro (prioridade)
            disponivel_detectado = None
            for sinal in sinais_indisponivel:
                if sinal in page_content_lower:
                    disponivel_detectado = False
                    dados['estoque'] = 'OutOfStock'
                    break
            
            # Se não encontrou indisponível, verifica disponível
            if disponivel_detectado is None:
                for sinal in sinais_disponivel:
                    if sinal in page_content_lower:
                        disponivel_detectado = True
                        dados['estoque'] = 'InStock'
                        break
            
            # Só marca disponível/indisponível se tiver certeza
            dados['disponivel'] = disponivel_detectado
            
            # Tenta extrair quantidade em estoque
            try:
                estoque_texto = page.evaluate(r'''
                    () => {
                        const selectors = [
                            '[class*="stock" i]',
                            '[class*="estoque" i]',
                            '[class*="quantity" i]',
                            '[class*="quantidade" i]',
                        ];
                        
                        for (const selector of selectors) {
                            const el = document.querySelector(selector);
                            if (el) {
                                const text = el.textContent;
                                const match = text.match(/(\d+)\s*(unidade|unit|peça|pç|disponível|available|em estoque|in stock)/i);
                                if (match) return match[1];
                            }
                        }
                        return null;
                    }
                ''')
                
                if estoque_texto:
                    dados['estoque_quantidade'] = int(estoque_texto)
            except:
                pass
            
            # ========== MARCA ==========
            seletores_marca = [
                '[itemprop="brand"]',
                '[class*="brand" i]',
                '[data-testid="brand"]',
                '.product-brand',
            ]
            
            for seletor in seletores_marca:
                try:
                    element = page.query_selector(seletor)
                    if element:
                        texto = element.inner_text().strip()
                        if texto:
                            dados['marca'] = texto
                            break
                except:
                    continue
            
            # ========== IMAGENS ==========
            try:
                imagens = page.evaluate('''
                    () => {
                        const imgs = [];
                        
                        // Imagens principais do produto
                        const selectors = [
                            'img[class*="product" i]',
                            'img[itemprop="image"]',
                            'img[data-testid*="product" i]',
                            '.product-image img',
                            '.gallery img',
                        ];
                        
                        selectors.forEach(selector => {
                            document.querySelectorAll(selector).forEach(img => {
                                const src = img.src || img.dataset.src;
                                if (src && !src.includes('icon') && !src.includes('logo')) {
                                    imgs.push(src);
                                }
                            });
                        });
                        
                        // Remove duplicatas
                        return [...new Set(imgs)];
                    }
                ''')
                
                dados['imagens'] = imagens[:10]  # Limita a 10 imagens
            except:
                pass
            
            # ========== SKU ==========
            seletores_sku = [
                '[itemprop="sku"]',
                '[class*="sku" i]',
                '[data-testid="sku"]',
            ]
            
            for seletor in seletores_sku:
                try:
                    element = page.query_selector(seletor)
                    if element:
                        texto = element.inner_text().strip()
                        if texto:
                            dados['sku'] = texto
                            break
                except:
                    continue
            
            # ========== CATEGORIA / BREADCRUMB ==========
            try:
                # Breadcrumb - extrai categorias hierárquicas
                categorias_lista = page.evaluate('''
                    () => {
                        const items = [];
                        const selectors = [
                            '.breadcrumb a',
                            '.breadcrumb span',
                            '.breadcrumb li',
                            '[itemtype*="BreadcrumbList"] a',
                            '[itemtype*="BreadcrumbList"] span',
                            'nav[aria-label*="breadcrumb" i] a',
                            'nav[aria-label*="breadcrumb" i] span',
                            '[class*="breadcrumb" i] a',
                            '[class*="breadcrumb" i] span',
                        ];
                        
                        for (const selector of selectors) {
                            const elements = document.querySelectorAll(selector);
                            if (elements.length > 0) {
                                elements.forEach(el => {
                                    const text = el.textContent.trim();
                                    // Filtra palavras que não são categorias
                                    if (text && 
                                        text !== 'Home' && 
                                        text !== 'Início' && 
                                        text !== 'OFF' &&
                                        text !== 'Shop' &&
                                        text !== '>' &&
                                        text !== '»' &&
                                        text !== '/' &&
                                        text.length > 0) {
                                        items.push(text);
                                    }
                                });
                                break;
                            }
                        }
                        
                        return items;
                    }
                ''')
                
                if categorias_lista and len(categorias_lista) > 0:
                    # Categorias completas: todas as tags separadas por |
                    dados['categorias_completas'] = ' | '.join(categorias_lista)
                    
                    # Categoria: última tag (mais específica)
                    dados['categoria'] = categorias_lista[-1] if len(categorias_lista) >= 1 else None
                    
                    # Subcategoria: penúltima tag
                    dados['subcategoria'] = categorias_lista[-2] if len(categorias_lista) >= 2 else None
            except:
                pass
            
            # ========== DESCRIÇÃO ==========
            seletores_descricao = [
                '[itemprop="description"]',
                '[class*="description" i]',
                '[class*="details" i]',
                '.product-description',
            ]
            
            for seletor in seletores_descricao:
                try:
                    element = page.query_selector(seletor)
                    if element:
                        texto = element.inner_text().strip()
                        if texto and len(texto) > 20:
                            dados['descricao'] = texto[:500]  # Limita a 500 caracteres
                            break
                except:
                    continue
            
        except Exception as e:
            print(f"  ⚠️  Erro ao extrair dados visuais: {str(e)}")
        
        return dados
    
    def extrair_produto(self, url: str, index: int = 0, total: int = 1) -> Dict:
        """
        Extrai informações detalhadas de um produto usando Playwright
        
        Args:
            url: URL do produto
            index: Índice do produto atual (para mensagens)
            total: Total de produtos (para mensagens)
        
        Returns:
            Dicionário com dados do produto
        """
        # Verifica cache
        if url in self.cache_produtos:
            return self.cache_produtos[url]
        
        print(f"\n[{index}/{total}] Processando: {url}")
        
        dados_finais = {
            'url': url,
            'nome': 'Desconhecido',
            'preco': None,
            'preco_original': None,
            'disponivel': None,
            'marca': None,
            'sku': None,
            'categoria': None,
            'subcategoria': None,
            'categorias_completas': None,
            'imagens': [],
            'descricao': None,
            'estoque': None,
            'estoque_quantidade': None,
            'moeda': 'BRL',
            'metodo_extracao': None,
            'erro': None,
        }
        
        try:
            with sync_playwright() as p:
                # Inicia browser
                browser: Browser = p.chromium.launch(headless=True)
                page: Page = browser.new_page()
                
                # Navega para a página
                print(f"  🌐 Carregando página...")
                try:
                    response = page.goto(url, wait_until='networkidle', timeout=self.timeout)
                    
                    if not response or response.status >= 400:
                        dados_finais['erro'] = f"HTTP {response.status if response else 'sem resposta'}"
                        browser.close()
                        return dados_finais
                    
                except PlaywrightTimeout:
                    print(f"  ⏱️  Timeout no networkidle, tentando domcontentloaded...")
                    try:
                        page.goto(url, wait_until='domcontentloaded', timeout=self.timeout)
                    except Exception as e:
                        dados_finais['erro'] = f"Timeout: {str(e)}"
                        browser.close()
                        return dados_finais
                
                # Aguarda um pouco para JavaScript carregar
                page.wait_for_timeout(2000)
                
                # ========== MÉTODO 1: JSON-LD ==========
                print(f"  🔍 Tentando JSON-LD...")
                json_ld = self._extrair_json_ld(page)
                
                if json_ld:
                    print(f"  ✅ JSON-LD encontrado!")
                    dados_finais['metodo_extracao'] = 'JSON-LD'
                    
                    # Extrai dados do JSON-LD
                    dados_finais['nome'] = json_ld.get('name', dados_finais['nome'])
                    dados_finais['descricao'] = json_ld.get('description')
                    
                    # Categoria do JSON-LD
                    if 'category' in json_ld:
                        dados_finais['categoria'] = json_ld['category']
                    
                    # Preço e ofertas
                    if 'offers' in json_ld:
                        offers = json_ld['offers']
                        if isinstance(offers, dict):
                            # Preço atual
                            preco = offers.get('lowPrice') or offers.get('price')
                            if preco:
                                dados_finais['preco'] = str(preco)
                            
                            # Preço alto (pode ser o original)
                            preco_alto = offers.get('highPrice')
                            if preco_alto and preco_alto != preco:
                                try:
                                    if float(preco_alto) > float(preco):
                                        dados_finais['preco_original'] = str(preco_alto)
                                except:
                                    pass
                            
                            # Moeda
                            if offers.get('priceCurrency'):
                                dados_finais['moeda'] = offers['priceCurrency']
                            
                            # Disponibilidade
                            availability = offers.get('availability', '').lower()
                            if availability:
                                status = availability.rsplit('/', 1)[-1]
                                dados_finais['estoque'] = status
                                
                                if 'instock' in availability:
                                    dados_finais['disponivel'] = True
                                elif 'outofstock' in availability or 'discontinued' in availability:
                                    dados_finais['disponivel'] = False
                            
                            # Quantidade em estoque
                            inventario = offers.get('inventoryLevel')
                            if inventario:
                                if isinstance(inventario, dict):
                                    quantidade = inventario.get('value')
                                else:
                                    quantidade = inventario
                                
                                if quantidade is not None:
                                    try:
                                        dados_finais['estoque_quantidade'] = int(float(str(quantidade)))
                                    except:
                                        dados_finais['estoque_quantidade'] = str(quantidade)
                        
                        elif isinstance(offers, list) and len(offers) > 0:
                            primeira_oferta = offers[0]
                            preco = primeira_oferta.get('price')
                            if preco:
                                dados_finais['preco'] = str(preco)
                            
                            if primeira_oferta.get('priceCurrency'):
                                dados_finais['moeda'] = primeira_oferta['priceCurrency']
                            
                            availability = primeira_oferta.get('availability', '').lower()
                            if 'instock' in availability:
                                dados_finais['disponivel'] = True
                            elif 'outofstock' in availability:
                                dados_finais['disponivel'] = False
                    
                    # Marca
                    if 'brand' in json_ld:
                        brand = json_ld['brand']
                        if isinstance(brand, dict):
                            dados_finais['marca'] = brand.get('name')
                        else:
                            dados_finais['marca'] = str(brand)
                    
                    # SKU
                    dados_finais['sku'] = json_ld.get('sku')
                    
                    # Imagens
                    if 'image' in json_ld:
                        images = json_ld['image']
                        if isinstance(images, str):
                            dados_finais['imagens'] = [images]
                        elif isinstance(images, list):
                            dados_finais['imagens'] = images[:10]
                
                # ========== MÉTODO 2: META TAGS ==========
                if not dados_finais['preco'] or dados_finais['nome'] == 'Desconhecido':
                    print(f"  🔍 Tentando Meta Tags...")
                    meta_data = self._extrair_meta_tags(page)
                    
                    if meta_data:
                        if not dados_finais['nome'] or dados_finais['nome'] == 'Desconhecido':
                            dados_finais['nome'] = meta_data.get('og_title') or meta_data.get('twitter_title') or dados_finais['nome']
                        
                        if not dados_finais['preco'] and meta_data.get('product_price'):
                            dados_finais['preco'] = self._limpar_preco(meta_data['product_price'])
                        
                        if not dados_finais['marca'] and meta_data.get('product_brand'):
                            dados_finais['marca'] = meta_data['product_brand']
                        
                        if not dados_finais['imagens'] and meta_data.get('og_image'):
                            dados_finais['imagens'] = [meta_data['og_image']]
                        
                        if not dados_finais['descricao'] and meta_data.get('og_description'):
                            dados_finais['descricao'] = meta_data['og_description']
                        
                        if dados_finais['metodo_extracao']:
                            dados_finais['metodo_extracao'] += ' + Meta Tags'
                        else:
                            dados_finais['metodo_extracao'] = 'Meta Tags'
                
                # ========== MÉTODO 3: EXTRAÇÃO VISUAL ==========
                if not dados_finais['preco'] or dados_finais['nome'] == 'Desconhecido':
                    print(f"  🔍 Tentando extração visual (seletores DOM)...")
                    dados_visual = self._extrair_dados_visualizacao(page, url)
                    
                    # Mescla dados, preferindo os já existentes
                    for key, value in dados_visual.items():
                        if value and not dados_finais.get(key):
                            dados_finais[key] = value
                    
                    if dados_finais['metodo_extracao']:
                        dados_finais['metodo_extracao'] += ' + Visual'
                    else:
                        dados_finais['metodo_extracao'] = 'Visual (DOM)'
                
                browser.close()
                
                # Verifica se conseguiu extrair dados essenciais
                if dados_finais['nome'] != 'Desconhecido' or dados_finais['preco']:
                    print(f"  ✅ Extraído: {dados_finais['nome'][:50]}... - R$ {dados_finais['preco']}")
                    print(f"  📊 Método: {dados_finais['metodo_extracao']}")
                    dados_finais['disponivel'] = True  # Se conseguiu extrair, considera disponível
                else:
                    print(f"  ⚠️  Dados insuficientes extraídos")
                    dados_finais['erro'] = "Dados não encontrados na página"
                
        except Exception as e:
            dados_finais['erro'] = str(e)
            print(f"  ❌ Erro: {str(e)}")
        
        # Cache
        self.cache_produtos[url] = dados_finais
        
        return dados_finais
    
    def extrair_detalhes_paralelo(
        self,
        produtos_input,
        show_message=None,
        max_produtos: int = None,
        max_workers: int = 1  # Playwright não suporta muito paralelismo
    ) -> tuple[str, List[Dict]]:
        """
        Extrai detalhes de múltiplos produtos
        
        Args:
            produtos_input: Lista de URLs ou texto com URLs
            show_message: Função para mostrar mensagens
            max_produtos: Limite de produtos a processar
            max_workers: Número de workers (Playwright funciona melhor com 1)
        
        Returns:
            (texto_formatado, lista_dados_estruturados)
        """
        # Parse input
        if isinstance(produtos_input, str):
            urls = [line.strip() for line in produtos_input.split('\n') 
                   if line.strip() and line.strip().startswith('http')]
        else:
            urls = produtos_input
        
        if max_produtos:
            urls = urls[:max_produtos]
        
        total = len(urls)
        
        if show_message:
            show_message(f"🤖 Iniciando extração de {total} produtos com Playwright...")
        
        # Processa produtos sequencialmente (Playwright é pesado)
        resultados = []
        texto_resultado = ""
        
        for i, url in enumerate(urls, 1):
            dados = self.extrair_produto(url, i, total)
            resultados.append(dados)
            
            # Formata texto
            texto_resultado += f"\n{'='*80}\n"
            texto_resultado += f"Produto {i}/{total}\n"
            texto_resultado += f"URL: {dados['url']}\n"
            texto_resultado += f"Nome: {dados['nome']}\n"
            texto_resultado += f"Preço: R$ {dados['preco']}\n" if dados['preco'] else "Preço: Não encontrado\n"
            if dados['preco_original']:
                texto_resultado += f"Preço Original: R$ {dados['preco_original']}\n"
            
            # Disponibilidade com estoque
            if dados['disponivel'] is True:
                texto_resultado += "Disponível: Sim\n"
            elif dados['disponivel'] is False:
                texto_resultado += "Disponível: Não\n"
            else:
                texto_resultado += "Disponível: Desconhecido\n"
            
            if dados['estoque']:
                texto_resultado += f"Status Estoque: {dados['estoque']}\n"
            if dados['estoque_quantidade']:
                texto_resultado += f"Quantidade: {dados['estoque_quantidade']} unidades\n"
            
            if dados['marca']:
                texto_resultado += f"Marca: {dados['marca']}\n"
            if dados['sku']:
                texto_resultado += f"SKU: {dados['sku']}\n"
            if dados['categoria']:
                texto_resultado += f"Categoria: {dados['categoria']}\n"
            if dados['subcategoria']:
                texto_resultado += f"Subcategoria: {dados['subcategoria']}\n"
            if dados['categorias_completas']:
                texto_resultado += f"Caminho: {dados['categorias_completas']}\n"
            if dados['imagens']:
                texto_resultado += f"Imagens: {len(dados['imagens'])} encontradas\n"
            if dados['descricao']:
                desc_preview = dados['descricao'][:100] + '...' if len(dados['descricao']) > 100 else dados['descricao']
                texto_resultado += f"Descrição: {desc_preview}\n"
            
            texto_resultado += f"Moeda: {dados['moeda']}\n"
            texto_resultado += f"Método: {dados['metodo_extracao']}\n"
            if dados['erro']:
                texto_resultado += f"⚠️  Erro: {dados['erro']}\n"
            
            if show_message and i % 5 == 0:
                show_message(f"Processados {i}/{total} produtos...")
        
        if show_message:
            show_message(f"✅ Extração concluída! {total} produtos processados")
        
        return texto_resultado, resultados


# Função de conveniência
def extrair_detalhes_paralelo(
    produtos_input,
    show_message=None,
    max_produtos: int = None,
    max_workers: int = 1
) -> tuple[str, List[Dict]]:
    """
    Extrai detalhes de produtos usando Playwright
    
    Args:
        produtos_input: Lista de URLs ou texto
        show_message: Callback para mensagens
        max_produtos: Limite de produtos
        max_workers: Threads (default 1 para Playwright)
    
    Returns:
        (texto_formatado, lista_dados)
    """
    extractor = ExtractDetailsV6()
    return extractor.extrair_detalhes_paralelo(
        produtos_input, show_message, max_produtos, max_workers
    )


# Teste
if __name__ == "__main__":
    print("=== Teste Extract Details V6 (Playwright) ===\n")
    
    # URLs de teste
    urls_teste = [
        "https://www.matconcasa.com.br/produto/abracadeira-nylon-perkon-branca-2-5x200-100-pecas-1250",
    ]
    
    texto, dados = extrair_detalhes_paralelo(
        urls_teste,
        show_message=print,
        max_produtos=1
    )
    
    print("\n" + "="*80)
    print("RESULTADO:")
    print(texto)
