"""
🚀 EXTRAÇÃO ULTRA-RÁPIDA VIA SSR
O site tem Server-Side Rendering - dados já vêm no HTML!
Podemos extrair com httpx + BeautifulSoup (SEM Playwright!)

Velocidade esperada: ~200-500ms por produto
"""

import asyncio
import httpx
from bs4 import BeautifulSoup
import re
import json
import time


async def extrair_produto_via_html(client: httpx.AsyncClient, url: str) -> dict:
    """Extrai produto direto do HTML SSR (sem browser!)"""
    inicio = time.time()
    
    try:
        # Simular navegador real
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            "Referer": "https://www.matconcasa.com.br/",
        }
        
        response = await client.get(url, headers=headers, timeout=10, follow_redirects=True)
        
        if response.status_code != 200:
            return {"erro": f"HTTP {response.status_code}"}
        
        html = response.text
        soup = BeautifulSoup(html, 'html.parser')
        
        # Extrair dados
        produto = {}
        
        # 1. Nome - tentar H1
        h1 = soup.find('h1')
        if h1:
            produto['nome'] = h1.get_text(strip=True)
        
        # 2. Preços - buscar no texto
        texto = soup.get_text()
        preco_match = re.search(r'de\s+R\$\s*([\d.,]+).*?R\$\s*([\d.,]+)', texto, re.DOTALL | re.IGNORECASE)
        if preco_match:
            produto['preco_original'] = preco_match.group(1)
            produto['preco'] = preco_match.group(2)
        else:
            # Tentar apenas um preço
            preco_simples = re.search(r'R\$\s*([\d.,]+)', texto)
            if preco_simples:
                produto['preco'] = preco_simples.group(1)
        
        # 3. Imagens
        imagens = []
        for img in soup.find_all('img'):
            src = img.get('src') or img.get('data-src')
            if src and 'http' in src and 'logo' not in src.lower():
                imagens.append(src)
        produto['imagens'] = imagens[:5]
        
        # 4. Disponibilidade
        produto['disponivel'] = 'indisponível' not in texto.lower()
        
        # 5. SKU
        sku_match = re.search(r'-(\d+)$', url)
        if sku_match:
            produto['sku'] = sku_match.group(1)
        
        produto['metodo'] = 'HTML-SSR'
        produto['tempo'] = time.time() - inicio
        
        return produto
        
    except Exception as e:
        return {"erro": str(e)}


async def testar_velocidade():
    """Testa velocidade em múltiplas URLs"""
    
    urls = [
        "https://www.matconcasa.com.br/produto/furadeira-makita-de-impacto-1-2-1010w-220v-hp2070-220v-281700",
        "https://www.matconcasa.com.br/produto/tupia-laminadora-makita-1-4-530w-127v-3709127v-250228",
        "https://www.matconcasa.com.br/produto/furadeira-parafusadeira-black-decker-3-8-12v-bateria-com-13-acessorios-ld12s-br-403644",
        "https://www.matconcasa.com.br/produto/inversora-de-solda-intech-compacta-com-acessorios-160a-bivolt-7898632332698-405435",
        "https://www.matconcasa.com.br/produto/martelete-dewalt-sds-plus-rompedor-220v-800w-d25133kb2-412615",
    ]
    
    print("=" * 100)
    print("🚀 TESTE DE VELOCIDADE - EXTRAÇÃO VIA HTML SSR")
    print("=" * 100)
    print()
    
    async with httpx.AsyncClient() as client:
        inicio_total = time.time()
        
        # Processar sequencialmente para medir tempo individual
        for i, url in enumerate(urls, 1):
            print(f"[{i}/{len(urls)}] Extraindo...")
            
            produto = await extrair_produto_via_html(client, url)
            
            if 'erro' in produto:
                print(f"   ❌ Erro: {produto['erro']}")
            else:
                print(f"   ✅ {produto.get('nome', 'SEM NOME')[:60]}...")
                print(f"      Preço: R$ {produto.get('preco', 'N/A')}")
                print(f"      Imagens: {len(produto.get('imagens', []))}")
                print(f"      ⚡ Tempo: {produto.get('tempo', 0):.3f}s")
            print()
        
        tempo_total = time.time() - inicio_total
        tempo_medio = tempo_total / len(urls)
        
        print("=" * 100)
        print("📊 RESULTADOS")
        print("=" * 100)
        print(f"⏱️  Tempo total: {tempo_total:.2f}s")
        print(f"⚡ Tempo médio: {tempo_medio:.3f}s por produto")
        print(f"🚀 Velocidade: {1/tempo_medio:.1f} produtos/segundo")
        print(f"📈 Estimativa 800 produtos: {tempo_medio * 800:.1f}s ({tempo_medio * 800 / 60:.1f}min)")
        print()
        print("💡 COMPARAÇÃO:")
        print(f"   • HTML SSR: ~{tempo_medio:.2f}s/produto")
        print(f"   • DOM Playwright: ~2-3s/produto")
        print(f"   • Ganho: {(2.5/tempo_medio):.1f}x mais rápido! 🎯")
        print("=" * 100)


if __name__ == "__main__":
    asyncio.run(testar_velocidade())
