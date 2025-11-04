"""
EXTRAÇÃO COM CONCORRÊNCIA MÁXIMA
Baseado no extract_production.py que FUNCIONA (1.35s/produto, 100% sucesso)
Única mudança: MAX_CONCURRENCY de 30 para 60
"""

import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path
from crawlee.crawlers import PlaywrightCrawler
from crawlee import ConcurrencySettings

# CONFIGURAÇÕES - só aumentar concorrência
MAX_CONCURRENCY = 60  # ERA 30, agora 60
SELECTOR_TIMEOUT = 8000
EXTRA_WAIT = 500
REQUEST_TIMEOUT = timedelta(seconds=15)
MAX_RETRIES = 2

stats = {
    'total': 0,
    'sucesso': 0,
    'erro': 0,
    'produtos': [],
    'inicio': None,
    'fim': None,
}

async def extrair_produto(context) -> None:
    """Extração otimizada (EXATAMENTE como production.py que funciona)"""
    page = context.page
    url = context.request.url
    
    try:
        # Wait for h1 (NÃO networkidle!)
        await page.wait_for_selector('h1', timeout=SELECTOR_TIMEOUT, state='visible')
        
        # Extra wait for React hydration
        await page.wait_for_timeout(EXTRA_WAIT)
        
        # Extração em 1 evaluate (mais rápido)
        resultado = await page.evaluate('''() => {
            // NOME
            const h1s = Array.from(document.querySelectorAll('h1'));
            const nome = h1s.find(h => {
                const text = h.innerText.trim();
                return text.length > 20 && 
                       !text.includes('Vendido') && 
                       !text.includes('Parceria') &&
                       /\\d/.test(text);
            })?.innerText.trim() || '';
            
            // PREÇOS - context-aware regex
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
                const simplePriceMatch = html.match(/R\\$\\s*([\\d.,]+)/);
                if (simplePriceMatch) {
                    preco = simplePriceMatch[1].replace(/\\./g, '').replace(',', '.');
                }
            }
            
            // IMAGENS
            const imgs = Array.from(document.querySelectorAll('img'))
                .map(img => img.src || img.getAttribute('data-src'))
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
        
        # Validar e registrar
        if resultado['nome'] and resultado['preco']:
            stats['produtos'].append({
                **resultado,
                'url': url
            })
            stats['sucesso'] += 1
            count = stats['sucesso']
            total = stats['total']
            print(f"✅ [{count:3d}/{total:3d}] {resultado['nome'][:55]:55s} R$ {resultado['preco']:>8s}")
        else:
            stats['erro'] += 1
            stats['produtos'].append({
                'url': url,
                'erro': 'Dados incompletos'
            })
            print(f"❌ [{stats['erro']:3d}] {url[:70]} - Dados incompletos")
    
    except Exception as e:
        stats['erro'] += 1
        stats['produtos'].append({
            'url': url,
            'erro': str(e)
        })
        print(f"❌ ERRO: {str(e)[:50]}")

async def main():
    arquivo_urls = 'urls_matcon_100.txt'
    arquivo_saida = 'resultados_max_concurrency.json'
    
    if not Path(arquivo_urls).exists():
        print(f"❌ Arquivo não encontrado: {arquivo_urls}")
        return
    
    print("="*80)
    print("🚀 EXTRAÇÃO MÁXIMA CONCORRÊNCIA - 60 páginas paralelas")
    print("="*80)
    print()
    print("⚙️  Configurações:")
    print(f"   • Concorrência: {MAX_CONCURRENCY} páginas (ERA 30, agora 60)")
    print(f"   • Timeout: {SELECTOR_TIMEOUT}ms (wait for h1, não networkidle)")
    print(f"   • Retries: {MAX_RETRIES} tentativas")
    print(f"   • Performance esperada: ~0.6-0.8s/produto (melhor que 1.35s)")
    print()
    
    # Carregar URLs
    with open(arquivo_urls, 'r', encoding='utf-8') as f:
        urls = [l.strip() for l in f if l.strip() and '/produto/' in l]
    
    stats['total'] = len(urls)
    print(f"📋 {len(urls)} URLs carregadas")
    
    # Estimativa
    tempo_estimado = len(urls) * 0.7  # média 0.7s
    print(f"⏱️  Tempo estimado: {tempo_estimado:.0f}s ({tempo_estimado/60:.1f}min)")
    print()
    
    stats['inicio'] = datetime.now()
    print(f"🕐 Início: {stats['inicio'].strftime('%H:%M:%S')}")
    print("="*80)
    print()
    
    # Crawler (EXATO como production, só MAX_CONCURRENCY diferente)
    crawler = PlaywrightCrawler(
        request_handler=extrair_produto,
        headless=True,
        browser_type='chromium',
        max_request_retries=MAX_RETRIES,
        max_requests_per_crawl=len(urls),
        max_crawl_depth=0,
        request_handler_timeout=REQUEST_TIMEOUT,
        concurrency_settings=ConcurrencySettings(
            max_concurrency=MAX_CONCURRENCY,
            desired_concurrency=MAX_CONCURRENCY,
            min_concurrency=10,
        ),
    )
    
    # Executar
    await crawler.run(urls)
    
    stats['fim'] = datetime.now()
    tempo_total = (stats['fim'] - stats['inicio']).total_seconds()
    
    # RELATÓRIO
    print()
    print("="*80)
    print("📊 RELATÓRIO FINAL")
    print("="*80)
    print(f"\n⏱️  Tempo total: {tempo_total:.2f}s ({tempo_total/60:.2f} minutos)")
    
    total_processado = stats['sucesso'] + stats['erro']
    taxa_sucesso = (stats['sucesso'] / total_processado * 100) if total_processado > 0 else 0
    
    if total_processado > 0:
        print(f"⚡ Velocidade: {tempo_total/total_processado:.3f}s por produto")
    print()
    
    print(f"✅ Sucesso: {stats['sucesso']}/{total_processado} ({taxa_sucesso:.1f}%)")
    print(f"⚠️  Erros: {stats['erro']}/{total_processado} ({100-taxa_sucesso:.1f}%)")
    print()
    
    # Qualidade
    produtos_ok = [p for p in stats['produtos'] if 'erro' not in p]
    if produtos_ok:
        nome_ok = sum(1 for p in produtos_ok if p.get('nome'))
        preco_ok = sum(1 for p in produtos_ok if p.get('preco'))
        preco_orig_ok = sum(1 for p in produtos_ok if p.get('preco_original'))
        imgs_ok = sum(1 for p in produtos_ok if p.get('imagens') and len(p['imagens']) > 0)
        
        print("📈 Qualidade dos Dados:")
        print(f"   • Nome: {nome_ok}/{len(produtos_ok)} ({nome_ok/len(produtos_ok)*100:.1f}%)")
        print(f"   • Preço: {preco_ok}/{len(produtos_ok)} ({preco_ok/len(produtos_ok)*100:.1f}%)")
        print(f"   • Preço original: {preco_orig_ok}/{len(produtos_ok)} ({preco_orig_ok/len(produtos_ok)*100:.1f}%)")
        print(f"   • Imagens: {imgs_ok}/{len(produtos_ok)} ({imgs_ok/len(produtos_ok)*100:.1f}%)")
        print()
    
    # Estimativa 800
    if total_processado > 0:
        vel_media = tempo_total / total_processado
        est_800 = vel_media * 800
        print(f"🎯 Estimativa para 800 produtos:")
        print(f"   Tempo: {est_800:.1f}s ({est_800/60:.2f} minutos)")
        print(f"   Meta: 120s (2 minutos)")
        if est_800 <= 120:
            print(f"   ✅ ATINGIU A META!")
        else:
            print(f"   ❌ Diferença: {est_800 - 120:.1f}s ({(est_800/120):.1f}x mais lento)")
        print()
    
    # Salvar
    resultado_final = {
        'metadata': {
            'site': 'matconcasa.com.br',
            'total_urls': stats['total'],
            'total_processado': total_processado,
            'sucesso': stats['sucesso'],
            'erro': stats['erro'],
            'taxa_sucesso': f"{taxa_sucesso:.1f}%",
            'tempo_total_segundos': tempo_total,
            'tempo_total_minutos': round(tempo_total/60, 2),
            'velocidade_media_segundos': round(tempo_total/total_processado, 3) if total_processado > 0 else None,
            'inicio': stats['inicio'].isoformat(),
            'fim': stats['fim'].isoformat(),
            'metodo': 'max_concurrency_60',
            'concorrencia': MAX_CONCURRENCY,
        },
        'produtos': stats['produtos']
    }
    
    with open(arquivo_saida, 'w', encoding='utf-8') as f:
        json.dump(resultado_final, f, ensure_ascii=False, indent=2)
    
    print(f"💾 Resultados salvos: {arquivo_saida}")
    print()
    
    # Primeiros 3
    if produtos_ok:
        print("📦 Primeiros 3 produtos extraídos:")
        print("-"*80)
        for i, p in enumerate(produtos_ok[:3], 1):
            print(f"\n{i}. {p['nome']}")
            print(f"   Preço: R$ {p['preco']}")
            if p.get('preco_original'):
                print(f"   De: R$ {p['preco_original']}")
            print(f"   Imagens: {len(p.get('imagens', []))}")
    
    print()
    print("="*80)
    if taxa_sucesso >= 95:
        print("🎉 EXCELENTE! Taxa de sucesso acima de 95%")
    elif taxa_sucesso >= 80:
        print("✅ BOM! Taxa de sucesso razoável")
    else:
        print("⚠️  ATENÇÃO! Taxa de sucesso abaixo do esperado")
    print("="*80)

if __name__ == "__main__":
    asyncio.run(main())
