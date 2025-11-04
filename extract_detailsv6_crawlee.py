"""
Extração de detalhes de produtos usando Crawlee (v6)
Usa a biblioteca Crawlee oficial com PlaywrightCrawler
Resolve sites JavaScript-heavy como Next.js App Router
"""

import asyncio
import re
import json
from typing import Dict, List, Optional
from urllib.parse import urlparse
from crawlee.crawlers import PlaywrightCrawler, PlaywrightCrawlingContext
from crawlee.storages import Dataset


class ExtractDetailsV6:
    def __init__(self):
        self.cache_produtos = {}
        self.produtos_extraidos = []
        
    def _limpar_preco(self, texto: str) -> Optional[str]:
        """Extrai e formata preço de texto"""
        if not texto:
            return None
        
        # Remove tudo exceto números, vírgula e ponto
        limpo = re.sub(r'[^\d,.]', '', texto)
        
        if not limpo:
            return None
        
        # Padroniza formato brasileiro (1.234,56)
        if ',' in limpo and '.' in limpo:
            # Já está no formato brasileiro
            return limpo
        elif ',' in limpo:
            # Formato: 1234,56 -> mantém
            return limpo
        elif '.' in limpo:
            # Formato: 1234.56 -> converte para 1234,56
            partes = limpo.split('.')
            if len(partes[-1]) == 2:  # É decimal
                return limpo.replace('.', ',')
        
        return limpo
    
    async def extrair_produto_async(self, url: str, index: int = 0, total: int = 1) -> Dict:
        """
        Extrai informações detalhadas de um produto usando Crawlee
        
        Args:
            url: URL do produto
            index: Índice do produto atual
            total: Total de produtos
        
        Returns:
            Dicionário com dados do produto
        """
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
        
        # Handler para o Crawlee
        async def request_handler(context: PlaywrightCrawlingContext) -> None:
            nonlocal dados_finais
            
            page = context.page
            
            print(f"  🌐 Página carregada: {context.request.url}")
            
            # ========== AGUARDAR NETWORK IDLE (SEM REQUISIÇÕES ATIVAS) ==========
            print(f"  ⏳ Aguardando networkidle...")
            try:
                await page.wait_for_load_state('networkidle', timeout=30000)
                print(f"  ✅ Network idle alcançado!")
            except Exception as e:
                print(f"  ⚠️  Timeout networkidle: {e}")
            
            # Aguardar um pouco mais para garantir React hydration
            print(f"  ⏳ Aguardando React hidratar...")
            await page.wait_for_timeout(5000)  # 5 segundos adicionais
            
            try:
                # ========== MÉTODO 1: JSON-LD ==========
                print(f"  🔍 Tentando JSON-LD...")
                json_ld_data = await page.evaluate('''
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
                
                produto_json_ld = None
                if json_ld_data:
                    for item in json_ld_data:
                        if isinstance(item, dict):
                            if item.get('@type') == 'Product':
                                produto_json_ld = item
                                break
                            if '@graph' in item:
                                for graph_item in item['@graph']:
                                    if isinstance(graph_item, dict) and graph_item.get('@type') == 'Product':
                                        produto_json_ld = graph_item
                                        break
                
                if produto_json_ld:
                    print(f"  ✅ JSON-LD encontrado!")
                    dados_finais['metodo_extracao'] = 'JSON-LD'
                    
                    # Nome
                    dados_finais['nome'] = produto_json_ld.get('name', dados_finais['nome'])
                    
                    # Descrição
                    dados_finais['descricao'] = produto_json_ld.get('description')
                    
                    # Categoria
                    if 'category' in produto_json_ld:
                        dados_finais['categoria'] = produto_json_ld['category']
                    
                    # Ofertas e preços
                    if 'offers' in produto_json_ld:
                        offers = produto_json_ld['offers']
                        if isinstance(offers, dict):
                            preco = offers.get('lowPrice') or offers.get('price')
                            if preco:
                                dados_finais['preco'] = str(preco)
                            
                            preco_alto = offers.get('highPrice')
                            if preco_alto and preco_alto != preco:
                                try:
                                    if float(preco_alto) > float(preco):
                                        dados_finais['preco_original'] = str(preco_alto)
                                except:
                                    pass
                            
                            if offers.get('priceCurrency'):
                                dados_finais['moeda'] = offers['priceCurrency']
                            
                            availability = offers.get('availability', '').lower()
                            if availability:
                                status = availability.rsplit('/', 1)[-1]
                                dados_finais['estoque'] = status
                                if 'instock' in availability:
                                    dados_finais['disponivel'] = True
                                elif 'outofstock' in availability or 'discontinued' in availability:
                                    dados_finais['disponivel'] = False
                        
                        elif isinstance(offers, list) and offers:
                            primeira = offers[0]
                            if primeira.get('price'):
                                dados_finais['preco'] = str(primeira['price'])
                            if primeira.get('priceCurrency'):
                                dados_finais['moeda'] = primeira['priceCurrency']
                    
                    # Marca
                    if 'brand' in produto_json_ld:
                        brand = produto_json_ld['brand']
                        dados_finais['marca'] = brand.get('name') if isinstance(brand, dict) else str(brand)
                    
                    # SKU
                    dados_finais['sku'] = produto_json_ld.get('sku')
                    
                    # Imagens
                    if 'image' in produto_json_ld:
                        images = produto_json_ld['image']
                        if isinstance(images, str):
                            dados_finais['imagens'] = [images]
                        elif isinstance(images, list):
                            dados_finais['imagens'] = images[:10]
                
                # ========== MÉTODO 2: EXTRAÇÃO VISUAL (DOM) ==========
                if not dados_finais['preco'] or dados_finais['nome'] == 'Desconhecido':
                    print(f"  🔍 Tentando extração visual (DOM)...")
                    
                    # Nome do produto
                    if dados_finais['nome'] == 'Desconhecido':
                        nome = await page.evaluate(r'''
                            () => {
                                // Prioriza seletores mais específicos primeiro
                                const selectors = [
                                    'h1[data-testid="product-title"]',
                                    'h1[class*="product" i][class*="name" i]',
                                    'h1[class*="product" i][class*="title" i]',
                                    '[data-product-name]',
                                    'h1:not([class*="header" i]):not([class*="banner" i])',
                                    'h1',
                                ];
                                
                                for (const sel of selectors) {
                                    const el = document.querySelector(sel);
                                    if (el) {
                                        let text = el.textContent.trim();
                                        // Filtra textos genéricos
                                        if (text && 
                                            text.length > 3 && 
                                            !text.startsWith('Vendido e') &&
                                            !text.startsWith('Parceria') &&
                                            !text.includes('MATCON.CASA')) {
                                            return text;
                                        }
                                    }
                                }
                                
                                // Fallback: título da página limpo
                                const title = document.title;
                                if (title) {
                                    // Remove nome da loja e caracteres especiais do final
                                    let cleaned = title.replace(/\s*\|\s*Matcon\.casa.*$/i, '');
                                    cleaned = cleaned.replace(/^\s*Matcon\.casa\s*\|\s*/i, '');
                                    cleaned = cleaned.replace(/\s*\|\s*.*$/,'');
                                    return cleaned.trim();
                                }
                                
                                return null;
                            }
                        ''')
                        if nome:
                            dados_finais['nome'] = nome
                    
                    # Preço
                    if not dados_finais['preco']:
                        precos = await page.evaluate(r'''
                            () => {
                                const result = {
                                    preco: null,
                                    preco_original: null
                                };
                                
                                // Seletores para preço atual
                                const seletoresPreco = [
                                    '[data-testid="price"]',
                                    '[data-price]',
                                    '[class*="selling" i]',
                                    '[class*="price" i]:not([class*="original" i]):not([class*="old" i])',
                                    '[itemprop="price"]',
                                    '.price:not(.old-price):not(.original-price)',
                                    'span[class*="price" i]',
                                ];
                                
                                for (const sel of seletoresPreco) {
                                    const elements = document.querySelectorAll(sel);
                                    for (const el of elements) {
                                        const text = el.textContent;
                                        const match = text.match(/R\$\s*(\d{1,3}(?:\.\d{3})*(?:,\d{2})?)/);
                                        if (match) {
                                            result.preco = match[1];
                                            break;
                                        }
                                    }
                                    if (result.preco) break;
                                }
                                
                                // Seletores para preço original
                                const seletoresOriginal = [
                                    '[class*="original-price" i]',
                                    '[class*="old-price" i]',
                                    '[class*="list-price" i]',
                                    'del',
                                    's',
                                ];
                                
                                for (const sel of seletoresOriginal) {
                                    const el = document.querySelector(sel);
                                    if (el) {
                                        const text = el.textContent;
                                        const match = text.match(/R\$\s*(\d{1,3}(?:\.\d{3})*(?:,\d{2})?)/);
                                        if (match) {
                                            result.preco_original = match[1];
                                            break;
                                        }
                                    }
                                }
                                
                                return result;
                            }
                        ''')
                        
                        if precos.get('preco'):
                            dados_finais['preco'] = precos['preco']
                        if precos.get('preco_original'):
                            dados_finais['preco_original'] = precos['preco_original']
                    
                    # Marca
                    if not dados_finais['marca']:
                        marca = await page.evaluate('''
                            () => {
                                const selectors = [
                                    '[itemprop="brand"]',
                                    '[class*="brand" i]',
                                    '[data-testid="brand"]',
                                ];
                                
                                for (const sel of selectors) {
                                    const el = document.querySelector(sel);
                                    if (el) {
                                        const text = el.textContent.trim();
                                        if (text) return text;
                                    }
                                }
                                return null;
                            }
                        ''')
                        if marca:
                            dados_finais['marca'] = marca
                    
                    # Imagens
                    if not dados_finais['imagens']:
                        imagens = await page.evaluate('''
                            () => {
                                const imgs = [];
                                const selectors = [
                                    'img[class*="product" i]',
                                    'img[itemprop="image"]',
                                    '.product-image img',
                                ];
                                
                                selectors.forEach(selector => {
                                    document.querySelectorAll(selector).forEach(img => {
                                        const src = img.src || img.dataset.src;
                                        if (src && !src.includes('icon') && !src.includes('logo')) {
                                            imgs.push(src);
                                        }
                                    });
                                });
                                
                                return [...new Set(imgs)];
                            }
                        ''')
                        if imagens:
                            dados_finais['imagens'] = imagens[:10]
                    
                    # Categorias (breadcrumb)
                    if not dados_finais['categoria']:
                        categorias = await page.evaluate('''
                            () => {
                                const items = [];
                                const selectors = [
                                    '.breadcrumb a',
                                    '[itemtype*="BreadcrumbList"] a',
                                    'nav[aria-label*="breadcrumb" i] a',
                                ];
                                
                                for (const sel of selectors) {
                                    const links = document.querySelectorAll(sel);
                                    if (links.length > 0) {
                                        links.forEach(link => {
                                            const text = link.textContent.trim();
                                            if (text && text !== 'Home' && text !== 'Início') {
                                                items.push(text);
                                            }
                                        });
                                        break;
                                    }
                                }
                                
                                return items;
                            }
                        ''')
                        
                        if categorias and len(categorias) > 0:
                            dados_finais['categorias_completas'] = ' | '.join(categorias)
                            dados_finais['categoria'] = categorias[-1] if categorias else None
                            dados_finais['subcategoria'] = categorias[-2] if len(categorias) >= 2 else None
                    
                    # Disponibilidade
                    if dados_finais['disponivel'] is None:
                        html_lower = await page.content()
                        html_lower = html_lower.lower()
                        
                        if any(x in html_lower for x in ['indisponível', 'esgotado', 'out of stock']):
                            dados_finais['disponivel'] = False
                            dados_finais['estoque'] = 'OutOfStock'
                        elif any(x in html_lower for x in ['em estoque', 'in stock', 'disponível', 'comprar']):
                            dados_finais['disponivel'] = True
                            dados_finais['estoque'] = 'InStock'
                    
                    if dados_finais['metodo_extracao']:
                        dados_finais['metodo_extracao'] += ' + Visual (DOM)'
                    else:
                        dados_finais['metodo_extracao'] = 'Visual (DOM)'
                
                # Salva dados no dataset do Crawlee
                await context.push_data(dados_finais)
                
                # Log de sucesso
                if dados_finais['nome'] != 'Desconhecido' or dados_finais['preco']:
                    print(f"  ✅ Extraído: {dados_finais['nome'][:60]}...")
                    if dados_finais['preco']:
                        print(f"     Preço: R$ {dados_finais['preco']}")
                    print(f"  📊 Método: {dados_finais['metodo_extracao']}")
                else:
                    print(f"  ⚠️  Dados insuficientes")
                    dados_finais['erro'] = "Dados não encontrados"
                
            except Exception as e:
                dados_finais['erro'] = str(e)
                print(f"  ❌ Erro: {str(e)}")
                await context.push_data(dados_finais)
        
        # Cria e executa crawler
        crawler = PlaywrightCrawler(
            max_requests_per_crawl=1,
            headless=True,
            browser_type='chromium',
        )
        
        crawler.router.default_handler(request_handler)
        
        await crawler.run([url])
        
        # Pega dados do dataset
        dataset = await Dataset.open()
        data = await dataset.get_data()
        
        if data.items:
            dados_finais = data.items[-1]  # Pega último item
        
        return dados_finais
    
    async def extrair_detalhes_paralelo_async(
        self,
        produtos_input,
        show_message=None,
        max_produtos: int = None,
        max_workers: int = 1
    ) -> tuple[str, List[Dict]]:
        """
        Extrai detalhes de múltiplos produtos usando Crawlee
        
        Args:
            produtos_input: Lista de URLs ou texto
            show_message: Callback para mensagens
            max_produtos: Limite de produtos
            max_workers: Não usado (Crawlee gerencia internamente)
        
        Returns:
            (texto_formatado, lista_dados)
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
            show_message(f"🤖 Iniciando extração de {total} produtos com Crawlee...")
        
        # Processa produtos sequencialmente
        resultados = []
        texto_resultado = ""
        
        for i, url in enumerate(urls, 1):
            dados = await self.extrair_produto_async(url, i, total)
            resultados.append(dados)
            
            # Formata texto
            texto_resultado += f"\n{'='*80}\n"
            texto_resultado += f"Produto {i}/{total}\n"
            texto_resultado += f"URL: {dados['url']}\n"
            texto_resultado += f"Nome: {dados['nome']}\n"
            
            if dados['preco']:
                texto_resultado += f"Preço: R$ {dados['preco']}\n"
            else:
                texto_resultado += "Preço: Não encontrado\n"
            
            if dados['preco_original']:
                texto_resultado += f"Preço Original: R$ {dados['preco_original']}\n"
            
            if dados['disponivel'] is True:
                texto_resultado += "Disponível: Sim\n"
            elif dados['disponivel'] is False:
                texto_resultado += "Disponível: Não\n"
            else:
                texto_resultado += "Disponível: Desconhecido\n"
            
            if dados['estoque']:
                texto_resultado += f"Status Estoque: {dados['estoque']}\n"
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
                desc = dados['descricao'][:100] + '...' if len(dados['descricao']) > 100 else dados['descricao']
                texto_resultado += f"Descrição: {desc}\n"
            
            texto_resultado += f"Moeda: {dados['moeda']}\n"
            texto_resultado += f"Método: {dados['metodo_extracao']}\n"
            if dados['erro']:
                texto_resultado += f"⚠️  Erro: {dados['erro']}\n"
        
        if show_message:
            show_message(f"✅ Extração concluída! {total} produtos processados")
        
        return texto_resultado, resultados
    
    def extrair_detalhes_paralelo(
        self,
        produtos_input,
        show_message=None,
        max_produtos: int = None,
        max_workers: int = 1
    ) -> tuple[str, List[Dict]]:
        """Versão síncrona (wrapper)"""
        return asyncio.run(
            self.extrair_detalhes_paralelo_async(
                produtos_input, show_message, max_produtos, max_workers
            )
        )


# Função de conveniência
def extrair_detalhes_paralelo(
    produtos_input,
    show_message=None,
    max_produtos: int = None,
    max_workers: int = 1
) -> tuple[str, List[Dict]]:
    """
    Extrai detalhes de produtos usando Crawlee
    """
    extractor = ExtractDetailsV6()
    return extractor.extrair_detalhes_paralelo(
        produtos_input, show_message, max_produtos, max_workers
    )


# Teste
if __name__ == "__main__":
    print("=== Teste Extract Details V6 (Crawlee) ===\n")
    
    urls_teste = [
        "https://www.matconcasa.com.br/produto/ducha-hydra-optima-8-temperaturas-5500w-127v-dpop-8-551br-362905",
    ]
    
    texto, dados = extrair_detalhes_paralelo(
        urls_teste,
        show_message=print,
        max_produtos=1
    )
    
    print("\n" + "="*80)
    print("RESULTADO:")
    print(texto)
    
    print("\n" + "="*80)
    print("DADOS JSON:")
    print(json.dumps(dados[0], indent=2, ensure_ascii=False))
