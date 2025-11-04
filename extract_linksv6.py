"""
Extração de links de produtos usando Playwright (v6)
Usa headless browser para sites JavaScript-heavy
Versão simplificada e otimizada
"""

import re
import httpx
from urllib.parse import urlparse
from typing import List, Set, Optional
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, Page, Browser


class ExtractLinksV6:
    def __init__(self):
        self.produtos_encontrados: Set[str] = set()
        self.erros: List[str] = []
        self.dominios_js_heavy = [
            'matconcasa.com.br',
            'matcon',
        ]
        self.http_client = httpx.Client(timeout=15.0, follow_redirects=True)
    
    def _precisa_browser(self, url: str) -> bool:
        """Determina se a URL precisa de browser JavaScript"""
        url_lower = url.lower()
        return any(dominio in url_lower for dominio in self.dominios_js_heavy)
    
    def _eh_url_produto_valida(self, url: str, base_domain: str) -> bool:
        """Verifica se a URL é de um produto válido"""
        if not url or url.startswith(('#', 'javascript:', 'mailto:', 'tel:')):
            return False
        
        parsed = urlparse(url)
        
        # Deve ser do mesmo domínio
        if base_domain not in parsed.netloc:
            return False
        
        # Padrões comuns de produtos
        padroes_produto = [
            r'/produto/',
            r'/product/',
            r'/p/',
            r'/item/',
            r'/pd/',
            r'/dp/',
            r'-p-\d+',
            r'/[a-z0-9\-]+/p$',
        ]
        
        url_lower = url.lower()
        for padrao in padroes_produto:
            if re.search(padrao, url_lower):
                return True
        
        # Padrões a evitar
        padroes_evitar = [
            '/categoria', '/category', '/busca', '/search',
            '/institucional', '/sobre', '/contato', '/ajuda',
            '/carrinho', '/cart', '/checkout', '/login',
            '/account', '/conta', '/perfil', '/wishlist',
            '.pdf', '.jpg', '.png', '.gif', '.css', '.js'
        ]
        
        return not any(padrao in url_lower for padrao in padroes_evitar)
    
    def _extrair_sitemap_httpx(self, url: str) -> List[str]:
        """Extrai URLs do sitemap usando httpx (mais rápido)"""
        produtos = []
        
        try:
            resp = self.http_client.get(url)
            resp.raise_for_status()
            
            soup = BeautifulSoup(resp.text, 'html.parser')
            parsed_base = urlparse(url)
            base_domain = parsed_base.netloc
            
            # Procura por URLs no sitemap
            locs = soup.find_all('loc')
            for loc in locs:
                url_produto = loc.get_text().strip()
                if self._eh_url_produto_valida(url_produto, base_domain):
                    # Correção automática para domínios conhecidos
                    if 'matconcasa.com.br' in url_produto or 'matcon' in url_produto.lower():
                        parsed = urlparse(url_produto)
                        if '/produto/' not in parsed.path and not parsed.path.startswith('/produto/'):
                            # Remove barra inicial se existir
                            path_limpo = parsed.path.lstrip('/')
                            # Reconstrói URL com /produto/
                            url_produto = f"{parsed.scheme}://{parsed.netloc}/produto/{path_limpo}"
                            if parsed.query:
                                url_produto += f"?{parsed.query}"
                    
                    produtos.append(url_produto)
            
            return produtos
            
        except Exception as e:
            self.erros.append(f"Erro ao extrair sitemap: {str(e)}")
            return []
    
    def _extrair_pagina_playwright(self, url: str, max_produtos: int = 100) -> List[str]:
        """Extrai URLs de produtos usando Playwright"""
        produtos = []
        
        try:
            with sync_playwright() as p:
                # Inicia browser
                browser: Browser = p.chromium.launch(headless=True)
                page: Page = browser.new_page()
                
                # Navega para a página
                page.goto(url, wait_until='networkidle', timeout=30000)
                
                # Aguarda um pouco para garantir que o JavaScript carregou
                page.wait_for_timeout(2000)
                
                # Pega todos os links da página
                links = page.evaluate('''
                    () => {
                        const anchors = document.querySelectorAll('a[href]');
                        return Array.from(anchors).map(a => a.href);
                    }
                ''')
                
                parsed_base = urlparse(url)
                base_domain = parsed_base.netloc
                
                for link in links:
                    if self._eh_url_produto_valida(link, base_domain):
                        produtos.append(link)
                        if len(produtos) >= max_produtos:
                            break
                
                browser.close()
                
            return produtos
            
        except Exception as e:
            self.erros.append(f"Erro ao extrair página com Playwright: {str(e)}")
            return []
    
    def _extrair_com_navegacao(self, url: str, max_paginas: int = 5) -> List[str]:
        """Extrai produtos navegando por páginas de categoria"""
        produtos = []
        
        try:
            with sync_playwright() as p:
                browser: Browser = p.chromium.launch(headless=True)
                page: Page = browser.new_page()
                
                # Navega para primeira página
                page.goto(url, wait_until='networkidle', timeout=30000)
                
                parsed_base = urlparse(url)
                base_domain = parsed_base.netloc
                
                for pagina_num in range(1, max_paginas + 1):
                    print(f"  Processando página {pagina_num}/{max_paginas}...")
                    
                    # Aguarda carregamento
                    page.wait_for_timeout(2000)
                    
                    # Extrai links da página atual
                    links = page.evaluate('''
                        () => {
                            const anchors = document.querySelectorAll('a[href]');
                            return Array.from(anchors).map(a => a.href);
                        }
                    ''')
                    
                    produtos_pagina = 0
                    for link in links:
                        if self._eh_url_produto_valida(link, base_domain):
                            if link not in produtos:  # Evita duplicatas
                                produtos.append(link)
                                produtos_pagina += 1
                    
                    print(f"    Encontrados {produtos_pagina} produtos nesta página")
                    
                    # Tenta encontrar botão "próxima página"
                    botoes_proxima = [
                        'button:has-text("Próxima")',
                        'a:has-text("Próxima")',
                        'button:has-text("Next")',
                        'a:has-text("Next")',
                        'a[rel="next"]',
                        'button[aria-label*="next" i]',
                        '.pagination-next',
                        '.next-page',
                    ]
                    
                    navegou = False
                    for seletor in botoes_proxima:
                        try:
                            botao = page.query_selector(seletor)
                            if botao and botao.is_visible():
                                is_disabled = botao.get_attribute('disabled')
                                if not is_disabled:
                                    botao.click()
                                    page.wait_for_timeout(2000)
                                    navegou = True
                                    break
                        except Exception:
                            continue
                    
                    if not navegou:
                        print("  Não há mais páginas para navegar")
                        break
                
                browser.close()
                
            return produtos
            
        except Exception as e:
            self.erros.append(f"Erro ao navegar páginas: {str(e)}")
            return []
    
    def extrair_produtos_rapido(
        self,
        url: str,
        modo: str = 'auto',
        max_paginas: int = 5,
        show_message=None
    ) -> tuple[str, List[str]]:
        """
        Extrai produtos de uma URL
        
        Args:
            url: URL do sitemap ou página de categoria
            modo: 'sitemap', 'categoria', 'navegacao', ou 'auto'
            max_paginas: Número máximo de páginas a navegar (modo navegacao)
            show_message: Função callback para mostrar mensagens
        
        Returns:
            (texto_formatado, lista_urls)
        """
        self.produtos_encontrados.clear()
        self.erros.clear()
        
        if show_message:
            show_message("🤖 Iniciando extração com Playwright...")
        
        try:
            # Determina o modo automaticamente
            if modo == 'auto':
                if 'sitemap' in url.lower() or url.endswith('.xml'):
                    modo = 'sitemap'
                else:
                    modo = 'categoria'
            
            # Executa extração baseada no modo
            if modo == 'sitemap':
                if show_message:
                    show_message("📄 Processando sitemap XML (httpx)...")
                produtos = self._extrair_sitemap_httpx(url)
            
            elif modo == 'categoria':
                if show_message:
                    show_message("🌐 Extraindo produtos da página (Playwright)...")
                produtos = self._extrair_pagina_playwright(url)
            
            elif modo == 'navegacao':
                if show_message:
                    show_message(f"🔄 Navegando por até {max_paginas} páginas (Playwright)...")
                produtos = self._extrair_com_navegacao(url, max_paginas)
            
            else:
                raise ValueError(f"Modo inválido: {modo}")
            
            # Remove duplicatas mantendo ordem
            produtos_unicos = list(dict.fromkeys(produtos))
            self.produtos_encontrados = set(produtos_unicos)
            
            # Formata resultado
            texto_resultado = f"\n{'='*80}\n"
            texto_resultado += f"EXTRAÇÃO CONCLUÍDA - {len(produtos_unicos)} produtos encontrados\n"
            texto_resultado += f"{'='*80}\n\n"
            
            for i, produto_url in enumerate(produtos_unicos, 1):
                texto_resultado += f"{i}. {produto_url}\n"
            
            if show_message:
                show_message(f"✅ Extração concluída! {len(produtos_unicos)} produtos encontrados")
            
            return texto_resultado, produtos_unicos
        
        except Exception as e:
            erro_msg = f"❌ Erro na extração: {str(e)}"
            self.erros.append(erro_msg)
            if show_message:
                show_message(erro_msg)
            return erro_msg, []
    
    def __del__(self):
        """Fecha cliente HTTP ao destruir objeto"""
        try:
            self.http_client.close()
        except:
            pass


# Função de conveniência para compatibilidade
def extrair_produtos_rapido(
    url: str,
    modo: str = 'auto',
    max_paginas: int = 5,
    show_message=None
) -> tuple[str, List[str]]:
    """
    Extrai produtos de uma URL usando Playwright
    
    Args:
        url: URL do sitemap ou página de categoria
        modo: 'sitemap', 'categoria', 'navegacao', ou 'auto'
        max_paginas: Número máximo de páginas a navegar
        show_message: Função callback para mensagens
    
    Returns:
        (texto_formatado, lista_urls)
    """
    extractor = ExtractLinksV6()
    return extractor.extrair_produtos_rapido(url, modo, max_paginas, show_message)


# Exemplo de uso
if __name__ == "__main__":
    print("=== Teste Extract Links V6 (Playwright) ===\n")
    
    # Teste com sitemap (httpx - rápido)
    print("1. Testando com sitemap Matcon Casa (httpx):")
    url_sitemap = "https://www.matconcasa.com.br/sitemap.xml"
    texto, produtos = extrair_produtos_rapido(
        url_sitemap,
        modo='sitemap',
        show_message=print
    )
    print(f"\nEncontrados: {len(produtos)} produtos")
    if produtos:
        print("\nPrimeiros 5 produtos:")
        for i, p in enumerate(produtos[:5], 1):
            print(f"  {i}. {p}")
    
    print("\n" + "="*80 + "\n")
    
    # Teste com página de produto individual (Playwright)
    print("2. Testando com página de produto (Playwright):")
    if produtos:
        url_produto = produtos[0]  # Pega primeiro produto
        print(f"Testando URL: {url_produto}")
        texto, resultado = extrair_produtos_rapido(
            url_produto,
            modo='categoria',
            show_message=print
        )
        print(f"\nProdutos similares encontrados: {len(resultado)}")
