"""
🔬 DIAGNÓSTICO AVANÇADO - INTERCEPTAÇÃO DE PAYLOAD API
Captura o payload EXATO que o site envia para /api/product/basic

OBJETIVO:
- Interceptar requisições POST para /api/product/basic
- Capturar headers completos
- Capturar payload JSON exato
- Analisar cookies necessários
- Replicar chamada manualmente
"""

import asyncio
import json
from datetime import datetime
from playwright.async_api import async_playwright, Page, Route, Request
import httpx


class InterceptadorAPI:
    """Intercepta e captura requisições para APIs"""
    
    def __init__(self, url: str):
        self.url = url
        self.api_calls = []
        self.headers_capturados = {}
        self.cookies_capturados = []
    
    async def analisar(self):
        """Carrega página e intercepta todas as chamadas à API"""
        print("=" * 100)
        print("🔬 INTERCEPTADOR DE PAYLOAD API - /api/product/basic")
        print("=" * 100)
        print(f"🎯 URL: {self.url}")
        print()
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)  # Visível para debug
            
            # Criar contexto com configurações realistas
            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                locale="pt-BR",
                timezone_id="America/Sao_Paulo",
            )
            
            page = await context.new_page()
            
            # Interceptar requests
            async def handle_request(route: Route, request: Request):
                """Intercepta e captura requests para APIs"""
                url = request.url
                
                # Detectar chamadas para /api/product/basic
                if "/api/product/basic" in url:
                    print()
                    print("🎯" * 40)
                    print("✅ CAPTURADO: Requisição para /api/product/basic!")
                    print("🎯" * 40)
                    
                    # Capturar tudo
                    captura = {
                        "url": url,
                        "method": request.method,
                        "headers": dict(request.headers),
                        "post_data": None,
                        "post_data_json": None,
                    }
                    
                    # Tentar capturar POST data
                    try:
                        post_data = request.post_data
                        if post_data:
                            captura["post_data"] = post_data
                            try:
                                captura["post_data_json"] = json.loads(post_data)
                            except:
                                pass
                    except Exception as e:
                        print(f"⚠️  Não conseguiu capturar POST data: {e}")
                    
                    self.api_calls.append(captura)
                    
                    # Exibir imediatamente
                    print()
                    print("📋 DETALHES DA REQUISIÇÃO:")
                    print(f"   URL: {url}")
                    print(f"   Método: {request.method}")
                    print()
                    print("📨 HEADERS:")
                    for key, value in captura["headers"].items():
                        if key.lower() in ['content-type', 'accept', 'referer', 'origin', 'cookie', 'authorization']:
                            print(f"   {key}: {value}")
                    print()
                    print("📦 POST DATA (RAW):")
                    print(f"   {captura['post_data']}")
                    print()
                    print("📦 POST DATA (JSON):")
                    if captura["post_data_json"]:
                        print(json.dumps(captura["post_data_json"], indent=4, ensure_ascii=False))
                    print()
                    print("=" * 100)
                
                # Continuar requisição normalmente
                await route.continue_()
            
            # Registrar interceptador
            await page.route("**/*", handle_request)
            
            print("🌐 Carregando página...")
            print("⏳ Aguardando requisições para /api/product/basic...")
            print()
            
            try:
                # Navegar para a página
                await page.goto(self.url, wait_until="networkidle", timeout=30000)
                
                print("✅ Página carregada!")
                print()
                
                # Aguardar mais para garantir que todas as requisições foram feitas
                print("⏳ Aguardando 5s para capturar todas as requisições...")
                await asyncio.sleep(5)
                
                # Capturar cookies finais
                cookies = await context.cookies()
                self.cookies_capturados = cookies
                
                print(f"🍪 Cookies capturados: {len(cookies)}")
                for cookie in cookies:
                    if cookie['name'] in ['@matcon:store', '@matcon:cart', '_gcl_au', '_fbp']:
                        print(f"   {cookie['name']}: {cookie['value'][:100]}...")
                print()
                
            except Exception as e:
                print(f"❌ Erro: {e}")
            
            finally:
                await browser.close()
        
        # Salvar resultados
        self._salvar_relatorio()
        
        # Exibir resumo
        self._exibir_resumo()
        
        # Testar replicação
        if self.api_calls:
            await self._tentar_replicar()
    
    def _salvar_relatorio(self):
        """Salva relatório de interceptação"""
        arquivo = f"api_intercept_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        with open(arquivo, 'w', encoding='utf-8') as f:
            json.dump({
                "url": self.url,
                "timestamp": datetime.now().isoformat(),
                "api_calls": self.api_calls,
                "cookies": [
                    {k: v for k, v in cookie.items() if k in ['name', 'value', 'domain', 'path']}
                    for cookie in self.cookies_capturados
                ],
            }, f, ensure_ascii=False, indent=2)
        
        print(f"💾 Relatório salvo: {arquivo}")
        print()
    
    def _exibir_resumo(self):
        """Exibe resumo das capturas"""
        print()
        print("=" * 100)
        print("📊 RESUMO DA INTERCEPTAÇÃO")
        print("=" * 100)
        print()
        
        if not self.api_calls:
            print("❌ NENHUMA chamada para /api/product/basic foi detectada!")
            print()
            print("💡 Possíveis motivos:")
            print("   1. A API não é chamada nesta página específica")
            print("   2. A API é chamada de forma diferente (GET, outro endpoint)")
            print("   3. A página carrega dados via SSR (Server-Side Rendering)")
            print()
            print("🔍 PRÓXIMOS PASSOS:")
            print("   - Verificar DevTools do navegador (Network tab)")
            print("   - Tentar URL de listagem de produtos")
            print("   - Tentar adicionar produto ao carrinho")
        else:
            print(f"✅ {len(self.api_calls)} chamada(s) interceptada(s)!")
            print()
            
            for i, call in enumerate(self.api_calls, 1):
                print(f"📋 CHAMADA #{i}:")
                print(f"   Método: {call['method']}")
                print(f"   URL: {call['url']}")
                if call['post_data_json']:
                    print(f"   Payload: {json.dumps(call['post_data_json'], ensure_ascii=False)}")
                print()
        
        print("=" * 100)
    
    async def _tentar_replicar(self):
        """Tenta replicar a chamada capturada com httpx"""
        print()
        print("=" * 100)
        print("🧪 TESTANDO REPLICAÇÃO DA CHAMADA")
        print("=" * 100)
        print()
        
        if not self.api_calls:
            return
        
        call = self.api_calls[0]  # Primeira chamada
        
        async with httpx.AsyncClient(timeout=15) as client:
            # Preparar headers (remover alguns que httpx adiciona automaticamente)
            headers = {k: v for k, v in call['headers'].items() 
                      if k.lower() not in ['content-length', 'host', 'connection']}
            
            # Preparar cookies
            cookies = {cookie['name']: cookie['value'] for cookie in self.cookies_capturados}
            
            print("📨 Enviando requisição replicada...")
            print(f"   Método: {call['method']}")
            print(f"   Headers: {len(headers)} headers")
            print(f"   Cookies: {len(cookies)} cookies")
            if call['post_data_json']:
                print(f"   Payload: {json.dumps(call['post_data_json'], ensure_ascii=False)}")
            print()
            
            try:
                if call['method'] == 'POST':
                    response = await client.post(
                        call['url'],
                        json=call['post_data_json'],
                        headers=headers,
                        cookies=cookies
                    )
                else:
                    response = await client.get(
                        call['url'],
                        headers=headers,
                        cookies=cookies
                    )
                
                print(f"📥 Resposta: {response.status_code}")
                print()
                
                if response.status_code == 200:
                    print("✅ SUCESSO! A replicação funcionou!")
                    print()
                    print("📦 DADOS RETORNADOS:")
                    data = response.json()
                    print(json.dumps(data, indent=2, ensure_ascii=False)[:1000])
                    print()
                    
                    # Salvar resposta de exemplo
                    with open("api_response_example.json", "w", encoding="utf-8") as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
                    print("💾 Resposta salva em: api_response_example.json")
                else:
                    print(f"❌ Falhou com status {response.status_code}")
                    print(f"   Resposta: {response.text[:500]}")
                    
            except Exception as e:
                print(f"❌ Erro ao replicar: {e}")
        
        print()
        print("=" * 100)


# ============================================================================
# MAIN
# ============================================================================
async def main():
    # Testar diferentes URLs
    urls_teste = [
        # ("Produto individual", "https://www.matconcasa.com.br/produto/furadeira-makita-de-impacto-1-2-1010w-220v-hp2070-220v-281700"),
        ("Listagem de categoria", "https://www.matconcasa.com.br/ferramentas/ferramentas-eletricas/furadeiras"),
    ]
    
    for nome, url in urls_teste:
        print()
        print(f"🔍 Testando: {nome}")
        print()
        
        interceptador = InterceptadorAPI(url)
        await interceptador.analisar()
        
        if interceptador.api_calls:
            print(f"✅ Encontrado! Parando aqui.")
            break
    
    print()
    print("💡 DICA: Se não capturou nada, tente:")
    print("   1. URL de listagem de produtos")
    print("   2. Adicionar produto ao carrinho")
    print("   3. Verificar se a API é chamada em outra página")


if __name__ == "__main__":
    asyncio.run(main())
