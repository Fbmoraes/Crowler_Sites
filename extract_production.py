"""
EXTRAÇÃO PRODUCTION-READY - Matcon Casa
Melhor performance alcançável: ~0.7-1s/produto
Qualidade: 95-100% dados corretos
"""

import asyncio
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from crawlee.crawlers import PlaywrightCrawler
from crawlee import ConcurrencySettings

# Configurações otimizadas
MAX_CONCURRENCY = 30
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
    """Extração otimizada - wait for h1, não networkidle"""
    
    page = context.page
    url = context.request.url
    contador = stats['sucesso'] + stats['erro'] + 1
    
    try:
        # Wait apenas h1 (não networkidle!)
        try:
            await page.wait_for_selector('h1', timeout=SELECTOR_TIMEOUT, state='visible')
        except:
            await page.wait_for_selector('body', timeout=SELECTOR_TIMEOUT)
        
        await page.wait_for_timeout(EXTRA_WAIT)
        
        # Extração paralela
        resultado = await page.evaluate('''
            () => {
                // NOME
                let nome = null;
                const h1s = Array.from(document.querySelectorAll('h1'));
                const productH1 = h1s.find(h1 => {
                    const text = h1.textContent;
                    return /\\d/.test(text) && text.length > 20 && 
                           !text.includes('Vendido') && !text.includes('Parceria');
                });
                
                if (productH1) {
                    nome = productH1.textContent.trim();
                } else {
                    const titleMatch = document.title.match(/^([^|]+)/);
                    nome = titleMatch ? titleMatch[1].trim() : (h1s[0]?.textContent.trim() || null);
                }
                
                // PREÇOS
                const bodyText = document.body.innerText;
                let preco = null;
                let preco_original = null;
                
                const descMatch = bodyText.match(/de\\s+R\\$\\s*([\\d.,]+).*?R\\$\\s*([\\d.,]+)/is);
                if (descMatch) {
                    preco_original = descMatch[1].replace(/\\./g, '').replace(',', '.');
                    preco = descMatch[2].replace(/\\./g, '').replace(',', '.');
                } else {
                    const precoMatch = bodyText.match(/R\\$\\s*([\\d.,]+)/);
                    if (precoMatch) {
                        preco = precoMatch[1].replace(/\\./g, '').replace(',', '.');
                    }
                }
                
                // IMAGENS
                const imgs = Array.from(document.querySelectorAll('img[src*="matcon"]'));
                const imagens = imgs
                    .map(img => img.src)
                    .filter(src => !src.includes('logo') && !src.includes('banner'))
                    .slice(0, 5);
                
                // DISPONIBILIDADE
                const disponivel = bodyText.toLowerCase().includes('indisponível') || 
                                  bodyText.toLowerCase().includes('esgotado') ? false :
                                  (bodyText.toLowerCase().includes('adicionar') || 
                                   bodyText.toLowerCase().includes('comprar') ? true : null);
                
                return { nome, preco, preco_original, imagens, disponivel };
            }
        ''')
        
        if resultado['nome'] and resultado['preco']:
            stats['sucesso'] += 1
            nome_curto = resultado['nome'][:50] if len(resultado['nome']) > 50 else resultado['nome']
            print(f"✅ [{contador:3d}/{stats['total']}] {nome_curto:50s} R$ {resultado['preco']:>9s}")
        else:
            stats['erro'] += 1
            print(f"⚠️  [{contador:3d}/{stats['total']}] Dados incompletos")
        
        stats['produtos'].append({
            'url': url,
            'nome': resultado['nome'],
            'preco': resultado['preco'],
            'preco_original': resultado['preco_original'],
            'marca': None,
            'categoria': None,
            'subcategoria': None,
            'imagens': resultado['imagens'],
            'disponivel': resultado['disponivel'],
            'extraido_em': datetime.now().isoformat()
        })
        
    except Exception as e:
        stats['erro'] += 1
        print(f"❌ [{contador:3d}/{stats['total']}] Erro: {str(e)[:60]}")
        stats['produtos'].append({
            'url': url,
            'erro': str(e)[:200],
            'extraido_em': datetime.now().isoformat()
        })


async def main():
    # Validar argumentos
    if len(sys.argv) < 3:
        print("Uso: python extract_production.py <arquivo_urls> <arquivo_saida>")
        print("\nExemplo:")
        print("  python extract_production.py urls_matcon_100.txt resultados.json")
        return
    
    arquivo_urls = sys.argv[1]
    arquivo_saida = sys.argv[2]
    
    # Verificar arquivo de entrada
    if not Path(arquivo_urls).exists():
        print(f"❌ Arquivo não encontrado: {arquivo_urls}")
        return
    
    print("="*80)
    print("🚀 EXTRAÇÃO MATCON CASA - PRODUCTION")
    print("="*80)
    print()
    print("⚙️  Configurações:")
    print(f"   • Concorrência: {MAX_CONCURRENCY} páginas simultâneas")
    print(f"   • Timeout: {SELECTOR_TIMEOUT}ms (wait for h1, não networkidle)")
    print(f"   • Retries: {MAX_RETRIES} tentativas")
    print(f"   • Performance esperada: ~0.7-1s/produto")
    print()
    
    # Carregar URLs
    with open(arquivo_urls, 'r', encoding='utf-8') as f:
        urls = [l.strip() for l in f if l.strip() and '/produto/' in l]
    
    stats['total'] = len(urls)
    print(f"📋 {len(urls)} URLs carregadas de {arquivo_urls}")
    
    # Estimativa
    tempo_estimado = len(urls) * 0.85  # média 0.85s
    print(f"⏱️  Tempo estimado: {tempo_estimado:.0f}s ({tempo_estimado/60:.1f}min)")
    print()
    
    stats['inicio'] = datetime.now()
    print(f"🕐 Início: {stats['inicio'].strftime('%H:%M:%S')}")
    print("="*80)
    print()
    
    # Criar crawler
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
    try:
        await crawler.run(urls)
    except Exception as e:
        print(f"\n⚠️  Crawler interrompido: {str(e)}")
    
    stats['fim'] = datetime.now()
    tempo_total = (stats['fim'] - stats['inicio']).total_seconds()
    
    # Relatório
    print()
    print("="*80)
    print("📊 RELATÓRIO FINAL")
    print("="*80)
    print()
    
    total_processado = stats['sucesso'] + stats['erro']
    taxa_sucesso = (stats['sucesso'] / total_processado * 100) if total_processado > 0 else 0
    
    print(f"⏱️  Tempo total: {tempo_total:.2f}s ({tempo_total/60:.2f} minutos)")
    if total_processado > 0:
        print(f"⚡ Velocidade: {tempo_total/total_processado:.3f}s por produto")
    print()
    
    print(f"✅ Sucesso: {stats['sucesso']}/{total_processado} ({taxa_sucesso:.1f}%)")
    print(f"⚠️  Erros: {stats['erro']}/{total_processado} ({100-taxa_sucesso:.1f}%)")
    print()
    
    # Qualidade dos dados
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
    
    # Salvar resultados
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
            'metodo': 'playwright_optimized',
            'concorrencia': MAX_CONCURRENCY,
        },
        'produtos': stats['produtos']
    }
    
    with open(arquivo_saida, 'w', encoding='utf-8') as f:
        json.dump(resultado_final, f, ensure_ascii=False, indent=2)
    
    print(f"💾 Resultados salvos: {arquivo_saida}")
    print()
    
    # Resumo de produtos
    print("📦 Primeiros 5 produtos extraídos:")
    print("-"*80)
    for i, p in enumerate(stats['produtos'][:5], 1):
        if 'erro' in p:
            print(f"\n{i}. ❌ ERRO")
            print(f"   URL: {p['url'][:70]}...")
        else:
            nome = p['nome'][:60] + "..." if p.get('nome') and len(p['nome']) > 60 else p.get('nome', 'SEM NOME')
            print(f"\n{i}. {nome}")
            print(f"   Preço: R$ {p.get('preco', 'N/A')}")
            if p.get('preco_original'):
                print(f"   De: R$ {p['preco_original']}")
            print(f"   Imagens: {len(p.get('imagens', []))}")
    
    print()
    print("="*80)
    
    # Avaliação final
    if taxa_sucesso >= 95:
        print("🎉 EXCELENTE! Taxa de sucesso acima de 95%")
    elif taxa_sucesso >= 80:
        print("✅ BOM! Taxa de sucesso razoável")
    else:
        print("⚠️  ATENÇÃO! Taxa de sucesso abaixo do esperado")
    
    print("="*80)


if __name__ == "__main__":
    asyncio.run(main())
