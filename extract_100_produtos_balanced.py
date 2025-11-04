"""
Extração BALANCEADA de 100 produtos Matcon Casa
Estratégia: Menos concorrência + Delays = Mais qualidade
"""

import asyncio
import json
import time
from datetime import datetime, timedelta
from crawlee.crawlers import PlaywrightCrawler
from crawlee import ConcurrencySettings

# ============================================================================
# CONFIGURAÇÕES BALANCEADAS - Qualidade > Velocidade
# ============================================================================
MAX_CONCURRENCY = 2  # REDUZIDO: Apenas 2 páginas simultâneas (evita 429)
NETWORK_TIMEOUT = 20000  # 20s - Aumentado para garantir carregamento
EXTRA_WAIT = 3000  # 3s - Tempo extra para React hydration
REQUEST_TIMEOUT = timedelta(seconds=45)  # 45s por request
MIN_DELAY_BETWEEN_REQUESTS = 2  # 2s de delay mínimo entre requests

# ============================================================================
# ESTATÍSTICAS
# ============================================================================
stats = {
    'total': 0,
    'sucesso': 0,
    'erro': 0,
    'produtos': [],
    'inicio': None,
    'fim': None,
}

# ============================================================================
# FUNÇÃO DE EXTRAÇÃO (MESMO CÓDIGO QUE FUNCIONA NO V7)
# ============================================================================
async def extrair_produto(context) -> None:
    """Extrai dados de um produto usando a estratégia comprovada do v7"""
    
    page = context.page
    url = context.request.url
    
    # Emoji do contador
    contador = stats['sucesso'] + stats['erro'] + 1
    print(f"⚡ [{contador}] {url[:80]}...")
    
    try:
        # =================================================================
        # ESTRATÉGIA COMPROVADA: Networkidle + Wait Extra
        # =================================================================
        await page.wait_for_load_state('networkidle', timeout=NETWORK_TIMEOUT)
        await page.wait_for_timeout(EXTRA_WAIT)
        
        # =================================================================
        # EXTRAÇÃO DE DADOS (CÓDIGO EXATO DO V7 QUE FUNCIONA)
        # =================================================================
        
        # 1. NOME DO PRODUTO
        nome = await page.evaluate('''
            () => {
                const h1s = Array.from(document.querySelectorAll('h1'));
                
                // Estratégia 1: Filtrar h1s que parecem nome de produto
                const productH1s = h1s.filter(h1 => {
                    const text = h1.textContent;
                    // Nome de produto geralmente tem:
                    // - Números (código/modelo)
                    // - Mais de 20 caracteres
                    // - NÃO contém texto de vendedor
                    return /\\d/.test(text) && 
                           text.length > 20 && 
                           !text.includes('Vendido e Entregue') &&
                           !text.includes('Parceria');
                });
                
                if (productH1s.length > 0) {
                    return productH1s[0].textContent.trim();
                }
                
                // Estratégia 2: Pegar do title da página
                const titleMatch = document.title.match(/^([^|]+)/);
                if (titleMatch) {
                    return titleMatch[1].trim();
                }
                
                // Estratégia 3: Pegar maior h1
                if (h1s.length > 0) {
                    return h1s.reduce((longest, h1) => 
                        h1.textContent.length > longest.textContent.length ? h1 : longest
                    ).textContent.trim();
                }
                
                return null;
            }
        ''')
        
        # 2. PREÇOS (Original + Atual) - Context-aware
        precos = await page.evaluate(r'''
            () => {
                const bodyText = document.body.innerText;
                
                // Padrão: "de R$ XXX ... R$ YYY"
                const precoComDesconto = bodyText.match(/de\\s+R\\$\\s*([\\d.,]+).*?R\\$\\s*([\\d.,]+)/is);
                if (precoComDesconto) {
                    return {
                        original: precoComDesconto[1].replace('.', '').replace(',', '.'),
                        atual: precoComDesconto[2].replace('.', '').replace(',', '.')
                    };
                }
                
                // Fallback: Procurar qualquer preço
                const precoMatch = bodyText.match(/R\\$\\s*([\\d.,]+)/);
                if (precoMatch) {
                    return {
                        original: null,
                        atual: precoMatch[1].replace('.', '').replace(',', '.')
                    };
                }
                
                return { original: null, atual: null };
            }
        ''')
        
        # 3. IMAGENS
        imagens = await page.evaluate('''
            () => {
                const imgs = Array.from(document.querySelectorAll('img[src*="matcon"]'));
                return imgs
                    .map(img => img.src)
                    .filter(src => !src.includes('logo') && !src.includes('banner'))
                    .slice(0, 10);
            }
        ''')
        
        # 4. DISPONIBILIDADE
        disponivel = await page.evaluate('''
            () => {
                const bodyText = document.body.innerText.toLowerCase();
                if (bodyText.includes('indisponível') || bodyText.includes('esgotado')) {
                    return false;
                }
                if (bodyText.includes('adicionar') || bodyText.includes('comprar')) {
                    return true;
                }
                return null;
            }
        ''')
        
        # =================================================================
        # VALIDAÇÃO E REGISTRO
        # =================================================================
        produto = {
            'url': url,
            'nome': nome,
            'preco': precos['atual'],
            'preco_original': precos['original'],
            'marca': None,
            'categoria': None,
            'subcategoria': None,
            'imagens': imagens,
            'disponivel': disponivel,
            'extraido_em': datetime.now().isoformat()
        }
        
        # Verificar se tem dados mínimos
        if nome and precos['atual']:
            stats['sucesso'] += 1
            print(f"  ✅ {nome[:60]}... | R$ {precos['atual']}")
        else:
            stats['erro'] += 1
            print(f"  ⚠️  Dados incompletos (nome={bool(nome)}, preco={bool(precos['atual'])})")
        
        stats['produtos'].append(produto)
        
        # DELAY entre requests para evitar 429
        await asyncio.sleep(MIN_DELAY_BETWEEN_REQUESTS)
        
    except Exception as e:
        stats['erro'] += 1
        erro_msg = str(e)[:100]
        print(f"  ❌ Erro: {erro_msg}")
        stats['produtos'].append({
            'url': url,
            'erro': erro_msg,
            'extraido_em': datetime.now().isoformat()
        })


# ============================================================================
# MAIN
# ============================================================================
async def main():
    print("=" * 80)
    print("🎯 EXTRAÇÃO BALANCEADA - MATCON CASA")
    print("Estratégia: Qualidade > Velocidade")
    print("=" * 80)
    print()
    
    print("⚙️  Configurações BALANCEADAS:")
    print(f"   • Concorrência: {MAX_CONCURRENCY} páginas (evita bloqueio)")
    print(f"   • Network timeout: {NETWORK_TIMEOUT}ms")
    print(f"   • Wait extra: {EXTRA_WAIT}ms")
    print(f"   • Delay entre requests: {MIN_DELAY_BETWEEN_REQUESTS}s")
    print(f"   • Request timeout: {REQUEST_TIMEOUT.total_seconds()}s")
    print()
    
    # Carregar URLs
    print("📋 Carregando URLs...")
    try:
        with open('urls_matcon_100.txt', 'r', encoding='utf-8') as f:
            todas_urls = [linha.strip() for linha in f if linha.strip()]
        
        urls = [url for url in todas_urls if '/produto/' in url]
        
        print(f"✅ {len(urls)} URLs carregadas")
        
        if len(urls) == 0:
            print("❌ ERRO: Nenhuma URL encontrada!")
            return
        
        stats['total'] = len(urls)
        
    except FileNotFoundError:
        print("❌ Arquivo urls_matcon_100.txt não encontrado!")
        print("Execute: python extrair_urls_navegacao.py")
        return
    
    stats['inicio'] = datetime.now()
    print(f"⏱️  Início: {stats['inicio'].strftime('%H:%M:%S')}")
    print("=" * 80)
    print()
    
    # Criar crawler BALANCEADO
    from crawlee import ConcurrencySettings
    
    crawler = PlaywrightCrawler(
        request_handler=extrair_produto,
        headless=True,
        browser_type='chromium',
        max_request_retries=2,  # 2 retries em caso de erro
        max_requests_per_crawl=len(urls),
        max_crawl_depth=0,
        request_handler_timeout=REQUEST_TIMEOUT,
        
        # CONFIGURAÇÃO BALANCEADA DE CONCORRÊNCIA
        concurrency_settings=ConcurrencySettings(
            max_concurrency=MAX_CONCURRENCY,
            desired_concurrency=MAX_CONCURRENCY,
            min_concurrency=1,
        ),
    )
    
    # Executar
    await crawler.run(urls)
    
    # Finalizar
    stats['fim'] = datetime.now()
    tempo_total = (stats['fim'] - stats['inicio']).total_seconds()
    
    # =========================================================================
    # RELATÓRIO FINAL
    # =========================================================================
    print()
    print("=" * 80)
    print("📊 RELATÓRIO FINAL")
    print("=" * 80)
    print()
    print(f"⏱️  Tempo total: {tempo_total:.2f} segundos ({tempo_total/60:.2f} minutos)")
    print(f"⚡ Velocidade média: {tempo_total/stats['total']:.2f}s por produto")
    print()
    
    taxa_sucesso = (stats['sucesso'] / stats['total'] * 100) if stats['total'] > 0 else 0
    taxa_erro = (stats['erro'] / stats['total'] * 100) if stats['total'] > 0 else 0
    
    print(f"✅ Sucesso: {stats['sucesso']}/{stats['total']} ({taxa_sucesso:.1f}%)")
    print(f"⚠️  Erros: {stats['erro']}/{stats['total']} ({taxa_erro:.1f}%)")
    print()
    
    # Qualidade por campo
    produtos_validos = [p for p in stats['produtos'] if 'erro' not in p]
    if produtos_validos:
        nome_ok = sum(1 for p in produtos_validos if p.get('nome'))
        preco_ok = sum(1 for p in produtos_validos if p.get('preco'))
        preco_orig_ok = sum(1 for p in produtos_validos if p.get('preco_original'))
        imagens_ok = sum(1 for p in produtos_validos if p.get('imagens') and len(p['imagens']) > 0)
        
        print("📈 Qualidade dos Dados:")
        print(f"   • Nome: {nome_ok}/{len(produtos_validos)} ({nome_ok/len(produtos_validos)*100:.1f}%)")
        print(f"   • Preço: {preco_ok}/{len(produtos_validos)} ({preco_ok/len(produtos_validos)*100:.1f}%)")
        print(f"   • Preço original: {preco_orig_ok}/{len(produtos_validos)} ({preco_orig_ok/len(produtos_validos)*100:.1f}%)")
        print(f"   • Imagens: {imagens_ok}/{len(produtos_validos)} ({imagens_ok/len(produtos_validos)*100:.1f}%)")
    print()
    
    # Salvar resultados
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'resultados_balanced_{timestamp}.json'
    
    resultado_final = {
        'metadata': {
            'total_produtos': stats['total'],
            'sucesso': stats['sucesso'],
            'erro': stats['erro'],
            'taxa_sucesso': f"{taxa_sucesso:.1f}%",
            'tempo_total_segundos': tempo_total,
            'velocidade_media': f"{tempo_total/stats['total']:.2f}s/produto",
            'inicio': stats['inicio'].isoformat(),
            'fim': stats['fim'].isoformat(),
        },
        'produtos': stats['produtos']
    }
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(resultado_final, f, ensure_ascii=False, indent=2)
    
    print(f"💾 Resultados salvos: {filename}")
    print()
    
    # Exemplos
    print("📦 Exemplos de produtos extraídos:")
    print("-" * 80)
    print()
    
    for i, produto in enumerate(stats['produtos'][:5], 1):
        if 'erro' in produto:
            print(f"{i}. ❌ ERRO: {produto['url'][:70]}...")
            print(f"   {produto['erro']}")
        else:
            nome_curto = produto['nome'][:60] + "..." if produto.get('nome') and len(produto['nome']) > 60 else produto.get('nome', 'SEM NOME')
            print(f"{i}. {nome_curto}")
            print(f"   Preço: R$ {produto.get('preco', 'N/A')}")
            if produto.get('preco_original'):
                print(f"   De: R$ {produto['preco_original']}")
            print(f"   Imagens: {len(produto.get('imagens', []))}")
            if not produto.get('preco'):
                print(f"   ⚠️  Sem preço")
        print()
    
    print("=" * 80)
    
    # Avaliação final
    if taxa_sucesso >= 90:
        print("🎉 EXCELENTE! Taxa de sucesso acima de 90%")
    elif taxa_sucesso >= 70:
        print("✅ BOM! Taxa de sucesso razoável, mas pode melhorar")
    else:
        print("⚠️  PRECISA MELHORAR - Taxa de sucesso baixa")
    
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
