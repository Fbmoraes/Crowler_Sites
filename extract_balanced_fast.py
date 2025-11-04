"""
EXTRAÇÃO BALANCEADA - Otimização sem quebrar funcionalidade
Meta: ~0.4-0.6s por produto (melhor possível sem quebrar)

Otimizações aplicadas:
1. Resource blocking SELETIVO (só analytics/fonts, não CSS/images)
2. Concorrência alta (50 páginas)
3. domcontentloaded ao invés de load (mais rápido)
4. Wait mínimo após h1 (200ms)
5. 1 evaluate só para tudo
"""

import asyncio
import json
import time
from datetime import datetime, timedelta
from crawlee.crawlers import PlaywrightCrawler, PlaywrightCrawlingContext
from crawlee import ConcurrencySettings

# ============================================================================
# CONFIGURAÇÕES BALANCEADAS
# ============================================================================
MAX_CONCURRENCY = 50
SELECTOR_TIMEOUT = 5000        # 5s para achar h1
WAIT_AFTER_H1 = 200           # 200ms após h1 (mínimo para hydration)
MAX_RETRIES = 1

# Bloquear SÓ o que realmente não precisa (analytics e fonts)
BLOCKED_URL_PATTERNS = [
    '*google-analytics*',
    '*googletagmanager*',
    '*facebook.com*',
    '*hotjar*',
    '*clarity.ms*',
    '*doubleclick*',
    '*.woff2*',
    '*.woff*',
    '*.ttf*',
]

stats = {
    'inicio': None,
    'fim': None,
    'produtos': [],
    'erros': [],
    'tempos': [],
}

# ============================================================================
# FUNÇÃO DE EXTRAÇÃO BALANCEADA
# ============================================================================
async def extrair_produto_balanced(context: PlaywrightCrawlingContext) -> None:
    """Extração rápida mas segura"""
    page = context.page
    url = context.request.url
    tempo_inicio = time.time()
    
    try:
        # Bloquear apenas analytics e fonts (CSS e imagens precisamos!)
        async def block_unnecessary(route):
            request = route.request
            url_lower = request.url.lower()
            
            for pattern in BLOCKED_URL_PATTERNS:
                if pattern.replace('*', '') in url_lower:
                    await route.abort()
                    return
            
            await route.continue_()
        
        await page.route('**/*', block_unnecessary)
        
        # Navegar e esperar load (domcontentloaded estava abortando)
        await page.goto(url, wait_until='load', timeout=10000)
        
        # Esperar h1 aparecer
        await page.wait_for_selector('h1', timeout=SELECTOR_TIMEOUT, state='visible')
        
        # Wait mínimo para React hidratar
        await page.wait_for_timeout(WAIT_AFTER_H1)
        
        # Extração em 1 evaluate
        resultado = await page.evaluate('''() => {
            // NOME - primeira h1 válida
            const h1s = Array.from(document.querySelectorAll('h1'));
            const nome = h1s.find(h => {
                const text = h.innerText.trim();
                return text.length > 20 && 
                       !text.includes('Vendido') && 
                       !text.includes('Parceria') &&
                       /\\d/.test(text);
            })?.innerText.trim() || '';
            
            // PREÇOS - regex context-aware
            const html = document.body.innerHTML;
            const precoMatch = html.match(/de\\s+R\\$\\s*([\\d.,]+).*?por.*?R\\$\\s*([\\d.,]+)/is) ||
                              html.match(/de\\s+R\\$\\s*([\\d.,]+).*?R\\$\\s*([\\d.,]+)/is);
            
            let preco = '';
            let preco_original = '';
            
            if (precoMatch) {
                if (precoMatch[2]) {
                    preco_original = precoMatch[1].replace(/\\./g, '').replace(',', '.');
                    preco = precoMatch[2].replace(/\\./g, '').replace(',', '.');
                } else {
                    preco = precoMatch[1].replace(/\\./g, '').replace(',', '.');
                }
            } else {
                // Fallback: primeiro preço
                const simplePriceMatch = html.match(/R\\$\\s*([\\d.,]+)/);
                if (simplePriceMatch) {
                    preco = simplePriceMatch[1].replace(/\\./g, '').replace(',', '.');
                }
            }
            
            // IMAGENS
            const imgs = Array.from(document.querySelectorAll('img'))
                .map(img => img.src || img.getAttribute('data-src') || img.getAttribute('srcset')?.split(' ')[0])
                .filter(src => src && 
                              src.includes('matconcasa') && 
                              !src.includes('logo') &&
                              !src.includes('banner'));
            
            const imagens = [...new Set(imgs)].slice(0, 5);
            
            // DISPONIBILIDADE
            const bodyText = document.body.innerText.toLowerCase();
            const disponivel = !bodyText.includes('indisponível') && 
                             !bodyText.includes('esgotado');
            
            return {
                nome,
                preco,
                preco_original,
                imagens,
                disponivel
            };
        }''')
        
        # Estatísticas
        tempo_total = time.time() - tempo_inicio
        stats['tempos'].append(tempo_total)
        
        if resultado['nome'] and resultado['preco']:
            stats['produtos'].append({
                **resultado,
                'url': url,
                'tempo': round(tempo_total, 3)
            })
            
            count = len(stats['produtos'])
            avg_time = sum(stats['tempos']) / len(stats['tempos'])
            print(f"✅ [{count:3d}] {resultado['nome'][:55]:55s} R$ {resultado['preco']:>8s} ({tempo_total:.2f}s | avg:{avg_time:.3f}s)")
        else:
            erro = f"Dados incompletos: nome={bool(resultado['nome'])} preco={bool(resultado['preco'])}"
            stats['erros'].append({'url': url, 'erro': erro, 'tempo': tempo_total})
            print(f"❌ [{len(stats['erros']):3d}] {url[:70]} - {erro}")
            
    except Exception as e:
        tempo_total = time.time() - tempo_inicio
        stats['erros'].append({'url': url, 'erro': str(e), 'tempo': tempo_total})
        stats['tempos'].append(tempo_total)
        print(f"❌ ERRO {url[:50]}: {str(e)[:40]}")

# ============================================================================
# MAIN
# ============================================================================
async def main():
    print("\n" + "="*80)
    print("🚀 EXTRAÇÃO BALANCEADA - Rápida mas Segura")
    print("="*80)
    print(f"⚙️  Configurações:")
    print(f"   • Concorrência: {MAX_CONCURRENCY} páginas paralelas")
    print(f"   • Wait until: domcontentloaded (não load completo)")
    print(f"   • Timeout seletor: {SELECTOR_TIMEOUT}ms")
    print(f"   • Wait após h1: {WAIT_AFTER_H1}ms")
    print(f"   • Resource blocking: {len(BLOCKED_URL_PATTERNS)} patterns (só analytics/fonts)")
    print(f"   • Retries: {MAX_RETRIES}")
    print("="*80 + "\n")
    
    # Ler URLs
    with open('urls_matcon_100.txt', 'r', encoding='utf-8') as f:
        urls = [line.strip() for line in f if line.strip()]
    
    print(f"📦 Total de URLs: {len(urls)}\n")
    
    stats['inicio'] = time.time()
    
    # Crawler balanceado
    crawler = PlaywrightCrawler(
        request_handler=extrair_produto_balanced,
        concurrency_settings=ConcurrencySettings(
            max_concurrency=MAX_CONCURRENCY,
            min_concurrency=10,
            desired_concurrency=MAX_CONCURRENCY,
        ),
        max_requests_per_crawl=len(urls),
        max_request_retries=MAX_RETRIES,
        max_crawl_depth=0,
        request_handler_timeout=timedelta(seconds=15),
        headless=True,
        browser_type='chromium',
    )
    
    # Executar
    await crawler.run(urls)
    
    stats['fim'] = time.time()
    
    # ========================================
    # RELATÓRIO FINAL
    # ========================================
    tempo_total = stats['fim'] - stats['inicio']
    total_items = len(stats['produtos']) + len(stats['erros'])
    tempo_medio = sum(stats['tempos']) / len(stats['tempos']) if stats['tempos'] else 0
    
    print("\n" + "="*80)
    print("📊 RELATÓRIO FINAL - BALANCED")
    print("="*80)
    print(f"\n⏱️  Tempo total: {tempo_total:.2f}s ({tempo_total/60:.2f} minutos)")
    print(f"⚡ Velocidade MÉDIA: {tempo_medio:.3f}s por produto")
    if total_items > 0:
        print(f"⚡ Velocidade REAL: {tempo_total/total_items:.3f}s por produto (com overhead)")
    
    print(f"\n✅ Sucesso: {len(stats['produtos'])}/{total_items} ({len(stats['produtos'])/total_items*100:.1f}%)" if total_items > 0 else "\n✅ Sucesso: 0/0 (0.0%)")
    print(f"❌ Erros: {len(stats['erros'])}/{total_items} ({len(stats['erros'])/total_items*100:.1f}%)" if total_items > 0 else "❌ Erros: 0/0 (0.0%)")
    
    # Qualidade
    if stats['produtos']:
        with_nome = sum(1 for p in stats['produtos'] if p['nome'])
        with_preco = sum(1 for p in stats['produtos'] if p['preco'])
        with_preco_orig = sum(1 for p in stats['produtos'] if p['preco_original'])
        with_imgs = sum(1 for p in stats['produtos'] if p['imagens'])
        
        print(f"\n📈 Qualidade dos Dados:")
        print(f"   • Nome: {with_nome}/{len(stats['produtos'])} ({with_nome/len(stats['produtos'])*100:.1f}%)")
        print(f"   • Preço: {with_preco}/{len(stats['produtos'])} ({with_preco/len(stats['produtos'])*100:.1f}%)")
        print(f"   • Preço original: {with_preco_orig}/{len(stats['produtos'])} ({with_preco_orig/len(stats['produtos'])*100:.1f}%)")
        print(f"   • Imagens: {with_imgs}/{len(stats['produtos'])} ({with_imgs/len(stats['produtos'])*100:.1f}%)")
    
    # Estimativa 800
    if tempo_medio > 0:
        est_800 = tempo_medio * 800
        print(f"\n🎯 Estimativa para 800 produtos:")
        print(f"   Tempo: {est_800:.1f}s ({est_800/60:.2f} minutos)")
        print(f"   Meta: 120s (2 minutos)")
        if est_800 <= 120:
            print(f"   ✅ ATINGIU A META!")
        else:
            print(f"   ❌ Diferença: {est_800 - 120:.1f}s ({(est_800/120):.1f}x mais lento)")
    
    # Salvar
    output_file = 'resultados_balanced.json'
    output = {
        'metadata': {
            'data_extracao': datetime.now().isoformat(),
            'tempo_total_segundos': round(tempo_total, 2),
            'tempo_medio_por_produto': round(tempo_medio, 3),
            'total_produtos': len(stats['produtos']),
            'total_erros': len(stats['erros']),
            'taxa_sucesso': round(len(stats['produtos'])/total_items*100, 1) if total_items > 0 else 0,
            'metodo': 'balanced_fast',
        },
        'produtos': stats['produtos'],
        'erros': stats['erros']
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print(f"\n💾 Resultados salvos: {output_file}")
    
    # Primeiros 3
    if stats['produtos']:
        print(f"\n📦 Primeiros 3 produtos:")
        print("-"*80)
        for i, p in enumerate(stats['produtos'][:3], 1):
            print(f"\n{i}. {p['nome']}")
            print(f"   Preço: R$ {p['preco']}")
            if p['preco_original']:
                print(f"   De: R$ {p['preco_original']}")
            print(f"   Imagens: {len(p['imagens'])}")
            print(f"   Tempo: {p['tempo']}s")
    
    print("\n" + "="*80)
    if len(stats['produtos'])/total_items >= 0.95:
        print("🎉 EXCELENTE! Taxa de sucesso acima de 95%")
    elif len(stats['produtos'])/total_items >= 0.80:
        print("✅ BOM! Taxa de sucesso acima de 80%")
    else:
        print("⚠️  ATENÇÃO! Taxa de sucesso abaixo de 80%")
    print("="*80 + "\n")

if __name__ == '__main__':
    asyncio.run(main())
