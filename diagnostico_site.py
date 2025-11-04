"""
🔬 DIAGNÓSTICO COMPLETO DE SITE - MATCON CASA
Analisa toda a estrutura técnica do site para planejar estratégias de scraping

ANÁLISES INCLUÍDAS:
1. Arquitetura (Framework, SSR vs CSR, tecnologias)
2. Network (Todas requests, APIs, endpoints, headers)
3. Dados estruturados (JSON-LD, OpenGraph, metadados)
4. Proteções anti-bot (Cloudflare, rate limit, fingerprinting)
5. Seletores DOM (HTML structure, classes úteis)
6. Performance (Tempos de carregamento, recursos bloqueantes)
7. Storage (Cookies, localStorage, session)
8. JavaScript (Scripts carregados, frameworks frontend)
9. Recomendações de abordagem (API-first, DOM, híbrido)
"""

import asyncio
import json
import re
from datetime import datetime
from typing import Dict, List, Set, Any
from urllib.parse import urlparse, parse_qs
from collections import defaultdict

from playwright.async_api import async_playwright, Page, Response, Request
from bs4 import BeautifulSoup
import httpx


class DiagnosticoSite:
    """Diagnóstico completo de um site para planejamento de scraping"""
    
    def __init__(self, url: str):
        self.url = url
        self.diagnostico = {
            "url": url,
            "timestamp": datetime.now().isoformat(),
            "arquitetura": {},
            "network": {
                "requests": [],
                "apis": [],
                "endpoints_json": [],
                "headers_importantes": {},
                "cookies": [],
                "dominios": set(),
            },
            "dados_estruturados": {
                "jsonld": [],
                "opengraph": {},
                "meta_tags": {},
                "microdata": [],
            },
            "protecoes": {
                "cloudflare": False,
                "captcha": False,
                "fingerprinting": [],
                "rate_limit_headers": [],
                "user_agent_check": False,
            },
            "dom": {
                "seletores_produto": {},
                "seletores_preco": [],
                "seletores_imagem": [],
                "estrutura_html": {},
            },
            "performance": {
                "tempo_first_paint": 0,
                "tempo_dom_ready": 0,
                "tempo_load": 0,
                "recursos_bloqueantes": [],
                "scripts_pesados": [],
            },
            "javascript": {
                "frameworks": [],
                "scripts_externos": [],
                "window_objects": [],
            },
            "storage": {
                "cookies": [],
                "localStorage": {},
                "sessionStorage": {},
            },
            "recomendacoes": []
        }
        
        # Coletores de dados durante navegação
        self.all_requests: List[Dict] = []
        self.all_responses: List[Dict] = []
        self.console_logs: List[str] = []
    
    async def analisar(self):
        """Executa análise completa do site"""
        print("=" * 100)
        print("🔬 DIAGNÓSTICO COMPLETO DE SITE")
        print("=" * 100)
        print(f"🎯 URL: {self.url}")
        print()
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)  # Headless para velocidade
            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            )
            page = await context.new_page()
            
            # Configurar interceptadores
            await self._setup_interceptors(page)
            
            print("🌐 Carregando página...")
            inicio = datetime.now()
            
            try:
                # Navegar para a página (domcontentloaded é mais rápido que networkidle)
                response = await page.goto(self.url, wait_until="domcontentloaded", timeout=20000)
                
                fim_load = datetime.now()
                self.diagnostico["performance"]["tempo_load"] = (fim_load - inicio).total_seconds()
                
                print(f"✅ Página carregada em {self.diagnostico['performance']['tempo_load']:.2f}s")
                print()
                
                # Aguardar um pouco para capturar requisições assíncronas (reduzido)
                await asyncio.sleep(2)
                
                # Executar todas as análises
                await self._analisar_arquitetura(page)
                await self._analisar_network()
                await self._analisar_dados_estruturados(page)
                await self._analisar_protecoes(page, response)
                await self._analisar_dom(page)
                await self._analisar_performance(page)
                await self._analisar_javascript(page)
                await self._analisar_storage(page)
                
                # Gerar recomendações
                self._gerar_recomendacoes()
                
            except Exception as e:
                print(f"❌ Erro durante análise: {e}")
            
            finally:
                await browser.close()
        
        # Converter sets para listas para JSON
        self._converter_sets()
        
        # Salvar relatório
        self._salvar_relatorio()
        
        # Exibir resumo
        self._exibir_resumo()
    
    async def _setup_interceptors(self, page: Page):
        """Configura interceptadores de network, console, etc."""
        
        # Interceptar requests
        async def handle_request(request: Request):
            try:
                post_data = request.post_data
            except:
                post_data = None
            
            self.all_requests.append({
                "url": request.url,
                "method": request.method,
                "resource_type": request.resource_type,
                "headers": dict(request.headers),
                "post_data": post_data,
            })
        
        # Interceptar responses
        async def handle_response(response: Response):
            try:
                content_type = response.headers.get("content-type", "")
                self.all_responses.append({
                    "url": response.url,
                    "status": response.status,
                    "content_type": content_type,
                    "headers": dict(response.headers),
                    "size": len(await response.body()) if response.ok else 0,
                })
            except:
                pass
        
        # Interceptar console
        def handle_console(msg):
            self.console_logs.append(f"[{msg.type}] {msg.text}")
        
        page.on("request", handle_request)
        page.on("response", handle_response)
        page.on("console", handle_console)
    
    async def _analisar_arquitetura(self, page: Page):
        """Analisa framework, SSR/CSR, tecnologias"""
        print("📐 Analisando arquitetura...")
        
        # Detectar frameworks
        frameworks = await page.evaluate('''
            () => {
                const detected = [];
                
                // Next.js
                if (window.__NEXT_DATA__) detected.push("Next.js");
                
                // React
                if (document.querySelector('[data-reactroot]') || 
                    document.querySelector('[data-reactid]') ||
                    window.React) detected.push("React");
                
                // Vue
                if (window.Vue || document.querySelector('[data-v-]')) detected.push("Vue.js");
                
                // Angular
                if (window.ng || document.querySelector('[ng-version]')) detected.push("Angular");
                
                // jQuery
                if (window.jQuery) detected.push("jQuery");
                
                // Gatsby
                if (window.___gatsby) detected.push("Gatsby");
                
                // Nuxt
                if (window.__NUXT__) detected.push("Nuxt.js");
                
                return detected;
            }
        ''')
        
        # Detectar SSR vs CSR
        html = await page.content()
        tem_conteudo_inicial = len(BeautifulSoup(html, 'html.parser').get_text().strip()) > 1000
        
        # Detectar plataforma e-commerce
        plataforma = "Desconhecida"
        if "vtex" in html.lower():
            plataforma = "VTEX"
        elif "shopify" in html.lower():
            plataforma = "Shopify"
        elif "woocommerce" in html.lower():
            plataforma = "WooCommerce"
        elif "magento" in html.lower():
            plataforma = "Magento"
        
        self.diagnostico["arquitetura"] = {
            "frameworks": frameworks,
            "rendering": "SSR" if tem_conteudo_inicial else "CSR",
            "plataforma_ecommerce": plataforma,
            "tem_next_data": "window.__NEXT_DATA__" in html,
            "tem_hydration": "react" in html.lower() or "vue" in html.lower(),
        }
        
        print(f"   Framework: {', '.join(frameworks) if frameworks else 'Nenhum detectado'}")
        print(f"   Rendering: {self.diagnostico['arquitetura']['rendering']}")
        print(f"   Plataforma: {plataforma}")
        print()
    
    async def _analisar_network(self):
        """Analisa todas as requisições de rede"""
        print("🌐 Analisando requisições de rede...")
        
        # Categorizar requests
        apis = []
        json_endpoints = []
        dominios = set()
        
        for req in self.all_requests:
            url = req["url"]
            parsed = urlparse(url)
            dominios.add(parsed.netloc)
            
            # Detectar APIs
            if any(keyword in url.lower() for keyword in ['api', 'graphql', 'rest', '_next/data']):
                apis.append({
                    "url": url,
                    "method": req["method"],
                    "type": req["resource_type"],
                })
            
            # Detectar endpoints JSON
            if req["resource_type"] in ["xhr", "fetch"]:
                json_endpoints.append(url)
        
        # Analisar responses para encontrar headers importantes
        headers_importantes = defaultdict(set)
        for resp in self.all_responses:
            for header, value in resp["headers"].items():
                if any(keyword in header.lower() for keyword in 
                       ['rate', 'limit', 'retry', 'token', 'auth', 'api', 'cors', 'csrf']):
                    headers_importantes[header].add(value)
        
        self.diagnostico["network"] = {
            "total_requests": len(self.all_requests),
            "total_responses": len(self.all_responses),
            "apis": apis[:20],  # Limitar para não ficar muito grande
            "endpoints_json": json_endpoints[:20],
            "headers_importantes": {k: list(v) for k, v in headers_importantes.items()},
            "dominios": dominios,
            "por_tipo": self._agrupar_por_tipo(self.all_requests),
        }
        
        print(f"   Total requests: {len(self.all_requests)}")
        print(f"   APIs encontradas: {len(apis)}")
        print(f"   JSON endpoints: {len(json_endpoints)}")
        print(f"   Domínios: {len(dominios)}")
        print()
    
    def _agrupar_por_tipo(self, requests: List[Dict]) -> Dict[str, int]:
        """Agrupa requests por tipo de recurso"""
        grupos = defaultdict(int)
        for req in requests:
            grupos[req["resource_type"]] += 1
        return dict(grupos)
    
    async def _analisar_dados_estruturados(self, page: Page):
        """Analisa JSON-LD, OpenGraph, metadados"""
        print("📊 Analisando dados estruturados...")
        
        dados = await page.evaluate('''
            () => {
                // JSON-LD
                const jsonldScripts = Array.from(document.querySelectorAll('script[type="application/ld+json"]'));
                const jsonld = jsonldScripts.map(script => {
                    try {
                        return JSON.parse(script.textContent);
                    } catch {
                        return null;
                    }
                }).filter(Boolean);
                
                // OpenGraph
                const ogTags = {};
                document.querySelectorAll('meta[property^="og:"]').forEach(meta => {
                    ogTags[meta.getAttribute('property')] = meta.content;
                });
                
                // Meta tags importantes
                const metaTags = {};
                document.querySelectorAll('meta[name]').forEach(meta => {
                    metaTags[meta.name] = meta.content;
                });
                
                return { jsonld, ogTags, metaTags };
            }
        ''')
        
        self.diagnostico["dados_estruturados"] = dados
        
        print(f"   JSON-LD schemas: {len(dados['jsonld'])}")
        print(f"   OpenGraph tags: {len(dados['ogTags'])}")
        print(f"   Meta tags: {len(dados['metaTags'])}")
        
        # Detectar se tem Product schema
        tem_product = any(
            (isinstance(item.get("@type"), str) and item["@type"] == "Product") or
            (isinstance(item.get("@type"), list) and "Product" in item["@type"])
            for item in dados['jsonld']
        )
        print(f"   Product schema: {'✅ SIM' if tem_product else '❌ NÃO'}")
        print()
    
    async def _analisar_protecoes(self, page: Page, response):
        """Detecta proteções anti-bot"""
        print("🛡️  Analisando proteções anti-bot...")
        
        html = await page.content()
        
        # Cloudflare
        cloudflare = any([
            "cloudflare" in html.lower(),
            "cf-ray" in str(response.headers).lower(),
            "__cf_bm" in await page.evaluate("() => document.cookie"),
        ])
        
        # CAPTCHA
        captcha = any([
            "recaptcha" in html.lower(),
            "hcaptcha" in html.lower(),
            "captcha" in html.lower(),
        ])
        
        # Fingerprinting scripts
        fingerprinting = []
        scripts = await page.evaluate('''
            () => Array.from(document.querySelectorAll('script[src]')).map(s => s.src)
        ''')
        
        fingerprint_keywords = ['fingerprint', 'datadome', 'perimeterx', 'distil', 'incapsula']
        fingerprinting = [s for s in scripts if any(kw in s.lower() for kw in fingerprint_keywords)]
        
        # Rate limit headers
        rate_limit_headers = []
        for resp in self.all_responses:
            for header in resp["headers"]:
                if any(kw in header.lower() for kw in ['rate', 'limit', 'retry-after']):
                    rate_limit_headers.append({
                        "header": header,
                        "value": resp["headers"][header],
                        "url": resp["url"][:80]
                    })
        
        self.diagnostico["protecoes"] = {
            "cloudflare": cloudflare,
            "captcha": captcha,
            "fingerprinting": fingerprinting,
            "rate_limit_headers": rate_limit_headers[:10],
            "user_agent_check": "user-agent" in str(response.headers).lower(),
        }
        
        print(f"   Cloudflare: {'✅ SIM' if cloudflare else '❌ NÃO'}")
        print(f"   CAPTCHA: {'⚠️  SIM' if captcha else '✅ NÃO'}")
        print(f"   Fingerprinting: {len(fingerprinting)} scripts detectados")
        print(f"   Rate limit headers: {len(rate_limit_headers)}")
        print()
    
    async def _analisar_dom(self, page: Page):
        """Analisa estrutura DOM e seletores úteis"""
        print("🏗️  Analisando estrutura DOM...")
        
        seletores = await page.evaluate('''
            () => {
                // Produto
                const h1s = Array.from(document.querySelectorAll('h1')).map(h => ({
                    text: h.textContent.trim().substring(0, 100),
                    classes: h.className,
                    id: h.id,
                }));
                
                // Preços (procurar textos com R$)
                const bodyText = document.body.innerText;
                const precoRegex = /R\\$\\s*([\\d.,]+)/g;
                const precos = [...bodyText.matchAll(precoRegex)].slice(0, 5).map(m => m[0]);
                
                // Imagens de produto
                const imgs = Array.from(document.querySelectorAll('img'))
                    .filter(img => img.src && img.width > 100 && img.height > 100)
                    .map(img => ({
                        src: img.src.substring(0, 100),
                        alt: img.alt,
                        classes: img.className,
                    }))
                    .slice(0, 10);
                
                // Botões importantes
                const botoes = Array.from(document.querySelectorAll('button'))
                    .map(btn => ({
                        text: btn.textContent.trim().substring(0, 50),
                        classes: btn.className,
                    }))
                    .slice(0, 10);
                
                return { h1s, precos, imgs, botoes };
            }
        ''')
        
        self.diagnostico["dom"]["seletores_produto"] = seletores
        
        print(f"   H1 tags: {len(seletores['h1s'])}")
        print(f"   Preços encontrados: {len(seletores['precos'])}")
        print(f"   Imagens: {len(seletores['imgs'])}")
        print(f"   Botões: {len(seletores['botoes'])}")
        print()
    
    async def _analisar_performance(self, page: Page):
        """Analisa métricas de performance"""
        print("⚡ Analisando performance...")
        
        metrics = await page.evaluate('''
            () => {
                const timing = performance.timing;
                const entries = performance.getEntriesByType('resource');
                
                // Scripts pesados (> 100KB)
                const scriptsPesados = entries
                    .filter(e => e.initiatorType === 'script' && e.transferSize > 100000)
                    .map(e => ({
                        url: e.name.substring(0, 100),
                        size: e.transferSize,
                        duration: e.duration,
                    }))
                    .slice(0, 10);
                
                return {
                    domContentLoaded: timing.domContentLoadedEventEnd - timing.navigationStart,
                    loadComplete: timing.loadEventEnd - timing.navigationStart,
                    scriptsPesados,
                };
            }
        ''')
        
        self.diagnostico["performance"].update({
            "tempo_dom_ready": metrics["domContentLoaded"] / 1000,
            "tempo_load_complete": metrics["loadComplete"] / 1000,
            "scripts_pesados": metrics["scriptsPesados"],
        })
        
        print(f"   DOM ready: {metrics['domContentLoaded']/1000:.2f}s")
        print(f"   Load complete: {metrics['loadComplete']/1000:.2f}s")
        print(f"   Scripts pesados: {len(metrics['scriptsPesados'])}")
        print()
    
    async def _analisar_javascript(self, page: Page):
        """Analisa JavaScript no site"""
        print("📜 Analisando JavaScript...")
        
        js_info = await page.evaluate('''
            () => {
                // Scripts externos
                const scripts = Array.from(document.querySelectorAll('script[src]'))
                    .map(s => s.src)
                    .slice(0, 20);
                
                // Window objects importantes
                const windowObjects = [];
                const importantKeys = ['__NEXT_DATA__', '__NUXT__', 'dataLayer', 'gtag', 'fbq'];
                for (const key of importantKeys) {
                    if (window[key]) {
                        windowObjects.push(key);
                    }
                }
                
                return { scripts, windowObjects };
            }
        ''')
        
        self.diagnostico["javascript"] = js_info
        
        print(f"   Scripts externos: {len(js_info['scripts'])}")
        print(f"   Window objects: {len(js_info['windowObjects'])}")
        if js_info['windowObjects']:
            print(f"      {', '.join(js_info['windowObjects'])}")
        print()
    
    async def _analisar_storage(self, page: Page):
        """Analisa cookies e storage"""
        print("💾 Analisando storage...")
        
        storage = await page.evaluate('''
            () => {
                // Cookies
                const cookies = document.cookie.split(';').map(c => c.trim());
                
                // LocalStorage
                const localStorage = {};
                for (let i = 0; i < window.localStorage.length; i++) {
                    const key = window.localStorage.key(i);
                    localStorage[key] = window.localStorage.getItem(key)?.substring(0, 100);
                }
                
                // SessionStorage
                const sessionStorage = {};
                for (let i = 0; i < window.sessionStorage.length; i++) {
                    const key = window.sessionStorage.key(i);
                    sessionStorage[key] = window.sessionStorage.getItem(key)?.substring(0, 100);
                }
                
                return { cookies, localStorage, sessionStorage };
            }
        ''')
        
        self.diagnostico["storage"] = storage
        
        print(f"   Cookies: {len(storage['cookies'])}")
        print(f"   localStorage items: {len(storage['localStorage'])}")
        print(f"   sessionStorage items: {len(storage['sessionStorage'])}")
        print()
    
    def _gerar_recomendacoes(self):
        """Gera recomendações de estratégia de scraping"""
        print("💡 Gerando recomendações...")
        
        recomendacoes = []
        
        # Análise de dados estruturados
        tem_jsonld_product = any(
            (isinstance(item.get("@type"), str) and item["@type"] == "Product") or
            (isinstance(item.get("@type"), list) and "Product" in item["@type"])
            for item in self.diagnostico["dados_estruturados"]["jsonld"]
        )
        
        if tem_jsonld_product:
            recomendacoes.append({
                "prioridade": "ALTA",
                "estrategia": "JSON-LD Schema.org",
                "descricao": "Site possui Product schema completo via JSON-LD",
                "implementacao": "Usar extruct ou BeautifulSoup para extrair <script type='application/ld+json'>",
                "velocidade": "⚡⚡⚡ Ultra rápido (~100-200ms/produto)",
                "codigo": "extruct.extract(html)['json-ld']"
            })
        
        # Análise de APIs
        apis_produto = [api for api in self.diagnostico["network"]["apis"] 
                       if any(kw in api["url"].lower() for kw in ['product', 'catalog', 'item'])]
        
        if apis_produto:
            recomendacoes.append({
                "prioridade": "ALTA",
                "estrategia": "API Direta",
                "descricao": f"Encontradas {len(apis_produto)} APIs de produto",
                "exemplos": [api["url"] for api in apis_produto[:3]],
                "implementacao": "httpx.AsyncClient() para chamadas HTTP diretas",
                "velocidade": "⚡⚡⚡ Ultra rápido (~100-300ms/produto)",
                "codigo": "await client.get(api_url)"
            })
        
        # Next.js data
        if self.diagnostico["arquitetura"]["tem_next_data"]:
            recomendacoes.append({
                "prioridade": "ALTA",
                "estrategia": "Next.js __NEXT_DATA__",
                "descricao": "Site usa Next.js com dados no __NEXT_DATA__",
                "implementacao": "Extrair JSON do <script id='__NEXT_DATA__'>",
                "velocidade": "⚡⚡⚡ Ultra rápido (~150-250ms/produto)",
                "codigo": "json.loads(soup.find('script', id='__NEXT_DATA__').string)"
            })
        
        # Análise de proteções
        if self.diagnostico["protecoes"]["cloudflare"]:
            recomendacoes.append({
                "prioridade": "MÉDIA",
                "estrategia": "Bypass Cloudflare",
                "descricao": "Site protegido por Cloudflare",
                "implementacao": "User-Agent rotation + delays + cloudscraper library",
                "codigo": "cloudscraper.create_scraper()"
            })
        
        if self.diagnostico["protecoes"]["rate_limit_headers"]:
            recomendacoes.append({
                "prioridade": "ALTA",
                "estrategia": "Rate Limiting Inteligente",
                "descricao": "Site implementa rate limiting via headers",
                "implementacao": "TokenBucket + Retry com exponential backoff + respeitar Retry-After",
                "codigo": "asyncio.Semaphore(max_concurrent) + await rate_limiter.acquire()"
            })
        
        # Fallback DOM sempre
        recomendacoes.append({
            "prioridade": "BAIXA (Fallback)",
            "estrategia": "Extração via DOM",
            "descricao": "Última opção: usar Playwright para renderizar e extrair",
            "implementacao": "Playwright + seletores específicos",
            "velocidade": "⚡ Lento (~2-5s/produto)",
            "codigo": "await page.evaluate('() => { ... }')"
        })
        
        # Estratégia híbrida recomendada
        recomendacoes.append({
            "prioridade": "⭐ RECOMENDADO",
            "estrategia": "Híbrido com Fallback",
            "descricao": "Combinar múltiplas estratégias com ordem de prioridade",
            "ordem": "1. JSON-LD → 2. API → 3. Next.js Data → 4. DOM",
            "implementacao": "Tentar métodos rápidos primeiro, DOM como fallback",
            "velocidade": "⚡⚡ Rápido (média 500ms-1s/produto)"
        })
        
        self.diagnostico["recomendacoes"] = recomendacoes
        print(f"   {len(recomendacoes)} estratégias identificadas")
        print()
    
    def _converter_sets(self):
        """Converte sets para listas para serialização JSON"""
        if isinstance(self.diagnostico["network"]["dominios"], set):
            self.diagnostico["network"]["dominios"] = list(self.diagnostico["network"]["dominios"])
    
    def _salvar_relatorio(self):
        """Salva relatório completo em JSON"""
        arquivo = f"diagnostico_site_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        with open(arquivo, 'w', encoding='utf-8') as f:
            json.dump(self.diagnostico, f, ensure_ascii=False, indent=2)
        
        print(f"💾 Relatório salvo: {arquivo}")
        print()
    
    def _exibir_resumo(self):
        """Exibe resumo executivo do diagnóstico"""
        print()
        print("=" * 100)
        print("📋 RESUMO EXECUTIVO")
        print("=" * 100)
        print()
        
        # Arquitetura
        print("📐 ARQUITETURA:")
        arq = self.diagnostico["arquitetura"]
        print(f"   • Framework: {', '.join(arq['frameworks']) if arq['frameworks'] else 'Nenhum'}")
        print(f"   • Rendering: {arq['rendering']}")
        print(f"   • Plataforma: {arq['plataforma_ecommerce']}")
        print()
        
        # Network
        print("🌐 NETWORK:")
        net = self.diagnostico["network"]
        print(f"   • Total requests: {net['total_requests']}")
        print(f"   • APIs encontradas: {len(net['apis'])}")
        print(f"   • Domínios: {len(net['dominios'])}")
        print()
        
        # Dados estruturados
        print("📊 DADOS ESTRUTURADOS:")
        dados = self.diagnostico["dados_estruturados"]
        print(f"   • JSON-LD schemas: {len(dados['jsonld'])}")
        tem_product = any(
            (isinstance(item.get("@type"), str) and item["@type"] == "Product") or
            (isinstance(item.get("@type"), list) and "Product" in item["@type"])
            for item in dados['jsonld']
        )
        print(f"   • Product schema: {'✅ SIM' if tem_product else '❌ NÃO'}")
        print()
        
        # Proteções
        print("🛡️  PROTEÇÕES:")
        prot = self.diagnostico["protecoes"]
        print(f"   • Cloudflare: {'⚠️  SIM' if prot['cloudflare'] else '✅ NÃO'}")
        print(f"   • CAPTCHA: {'⚠️  SIM' if prot['captcha'] else '✅ NÃO'}")
        print(f"   • Fingerprinting: {len(prot['fingerprinting'])} scripts")
        print(f"   • Rate limiting: {'⚠️  SIM' if prot['rate_limit_headers'] else '✅ NÃO'}")
        print()
        
        # Recomendações TOP 3
        print("💡 TOP 3 ESTRATÉGIAS RECOMENDADAS:")
        for i, rec in enumerate(self.diagnostico["recomendacoes"][:3], 1):
            print(f"\n   {i}. [{rec['prioridade']}] {rec['estrategia']}")
            print(f"      {rec['descricao']}")
            if 'velocidade' in rec:
                print(f"      Velocidade: {rec['velocidade']}")
        
        print()
        print("=" * 100)
        print("✅ Diagnóstico completo! Consulte o arquivo JSON para detalhes.")
        print("=" * 100)


# ============================================================================
# MAIN
# ============================================================================
async def main():
    # URL de exemplo do Matcon Casa
    url = "https://www.matconcasa.com.br/produto/furadeira-makita-de-impacto-1-2-1010w-220v-hp2070-220v-281700"
    
    diagnostico = DiagnosticoSite(url)
    await diagnostico.analisar()


if __name__ == "__main__":
    asyncio.run(main())
