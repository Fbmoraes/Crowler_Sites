"""
EXTRAÇÃO ULTRA-RÁPIDA - Sem networkidle, com seletores específicos
Estratégia: Esperar apenas o elemento necessário, não toda a rede
"""

import asyncio
import json
import time
from datetime import datetime, timedelta
from crawlee.crawlers import PlaywrightCrawler
from crawlee import ConcurrencySettings

# ============================================================================
# METAS DE PERFORMANCE
# ============================================================================
TARGET_TIME_PER_ITEM = 0.15  # 800 em 2min
MAX_TIME_PER_ITEM = 0.30     # 400 em 2min
ABORT_CHECK_INTERVAL = 10
MIN_SAMPLES = 5

# ============================================================================
# CONFIGURAÇÕES ULTRA-RÁPIDAS
# ============================================================================
MAX_CONCURRENCY = 30  # 30 páginas simultâneas
SELECTOR_TIMEOUT = 8000  # 8s esperando seletor específico (não networkidle!)
EXTRA_WAIT = 500  # 0.5s apenas
REQUEST_TIMEOUT = timedelta(seconds=15)

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
    'abortado': False,
    'razao_abort': None,
    'tempos_individuais': [],
}

class PerformanceWatchdog:
    def __init__(self, crawler):
        self.crawler = crawler
        self.start_time = None
        self.item_count = 0
        self.last_check = 0
        
    def start(self):
        self.start_time = time.time()
        
    def check_and_abort_if_slow(self):
        self.item_count += 1
        
        if self.item_count - self.last_check < ABORT_CHECK_INTERVAL:
            return False
            
        if self.item_count < MIN_SAMPLES:
            return False
            
        self.last_check = self.item_count
        elapsed = time.time() - self.start_time
        avg_time = elapsed / self.item_count
        
        print()
        print(f"⏱️  CHECKPOINT [{self.item_count} produtos]:")
        print(f"   Tempo médio: {avg_time:.3f}s/produto")
        print(f"   Meta: {TARGET_TIME_PER_ITEM:.3f}s | Limite: {MAX_TIME_PER_ITEM:.3f}s")
        
        if avg_time > MAX_TIME_PER_ITEM:
            razao = (
                f"Performance: {avg_time:.3f}s/produto > {MAX_TIME_PER_ITEM:.3f}s.\n"
                f"800 produtos: {avg_time * 800 / 60:.1f}min (meta: 2min).\n"
                f"ABORTANDO para otimizar."
            )
            print(f"\n{'='*80}\n🛑 ABORT: {razao}\n{'='*80}\n")
            stats['abortado'] = True
            stats['razao_abort'] = razao
            self.crawler.stop(reason=razao)
            return True
        
        estimativa = avg_time * 800
        print(f"   ✅ OK - 800 produtos: ~{estimativa:.1f}s ({estimativa/60:.2f}min)")
        print()
        return False

watchdog = None

# ============================================================================
# EXTRAÇÃO OTIMIZADA - SEM NETWORKIDLE
# ============================================================================
async def extrair_produto(context) -> None:
    """
    OTIMIZAÇÃO CRÍTICA:
    - Não usa networkidle (muito lento - espera TUDO carregar)
    - Espera apenas h1 aparecer (o mínimo necessário)
    - Extração paralela de dados
    """
    
    page = context.page
    url = context.request.url
    item_start = time.time()
    contador = stats['sucesso'] + stats['erro'] + 1
    
    try:
        # ====================================================================
        # OTIMIZAÇÃO 1: Wait for selector específico (não networkidle!)
        # ====================================================================
        # Espera APENAS o h1 aparecer, não toda a rede terminar
        try:
            await page.wait_for_selector('h1', timeout=SELECTOR_TIMEOUT, state='visible')
        except:
            # Se não encontrar h1, tenta body
            await page.wait_for_selector('body', timeout=SELECTOR_TIMEOUT)
        
        # Pequena espera para JS executar
        await page.wait_for_timeout(EXTRA_WAIT)
        
        # ====================================================================
        # OTIMIZAÇÃO 2: Extração paralela de TODOS os dados em 1 evaluate
        # ====================================================================
        resultado = await page.evaluate('''
            () => {
                // NOME - Estratégia rápida
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
                
                // PREÇOS - Regex otimizado
                const bodyText = document.body.innerText;
                let preco = null;
                let preco_original = null;
                
                // Tenta padrão "de R$ X ... R$ Y"
                const descMatch = bodyText.match(/de\\s+R\\$\\s*([\\d.,]+).*?R\\$\\s*([\\d.,]+)/is);
                if (descMatch) {
                    preco_original = descMatch[1].replace(/\\./g, '').replace(',', '.');
                    preco = descMatch[2].replace(/\\./g, '').replace(',', '.');
                } else {
                    // Fallback: primeiro R$ encontrado
                    const precoMatch = bodyText.match(/R\\$\\s*([\\d.,]+)/);
                    if (precoMatch) {
                        preco = precoMatch[1].replace(/\\./g, '').replace(',', '.');
                    }
                }
                
                // IMAGENS - Top 3 apenas (performance)
                const imgs = Array.from(document.querySelectorAll('img[src*="matcon"]'));
                const imagens = imgs
                    .map(img => img.src)
                    .filter(src => !src.includes('logo') && !src.includes('banner'))
                    .slice(0, 3);  // Apenas 3 primeiras
                
                return { nome, preco, preco_original, imagens: imagens.length };
            }
        ''')
        
        item_time = time.time() - item_start
        stats['tempos_individuais'].append(item_time)
        
        # Validar
        if resultado['nome'] and resultado['preco']:
            stats['sucesso'] += 1
            nome_curto = resultado['nome'][:40] if len(resultado['nome']) > 40 else resultado['nome']
            print(f"✅[{contador:2d}] {nome_curto:40s} R${resultado['preco']:>8s} {item_time:5.2f}s")
        else:
            stats['erro'] += 1
            print(f"⚠️ [{contador:2d}] Incompleto: nome={bool(resultado['nome'])} preco={bool(resultado['preco'])} {item_time:5.2f}s")
        
        stats['produtos'].append({
            'url': url,
            'tempo': item_time,
            **resultado,
        })
        
        # Watchdog
        if watchdog:
            watchdog.check_and_abort_if_slow()
        
    except Exception as e:
        stats['erro'] += 1
        item_time = time.time() - item_start
        erro_curto = str(e)[:50]
        print(f"❌[{contador:2d}] {erro_curto:50s} {item_time:5.2f}s")
        stats['produtos'].append({'url': url, 'erro': str(e)[:200], 'tempo': item_time})


# ============================================================================
# MAIN
# ============================================================================
async def main():
    global watchdog
    
    print("="*80)
    print("⚡ EXTRAÇÃO ULTRA-RÁPIDA - Otimizada")
    print("="*80)
    print(f"\n📊 Metas: Target {TARGET_TIME_PER_ITEM:.3f}s | Limite {MAX_TIME_PER_ITEM:.3f}s")
    print(f"\n⚙️  Config:")
    print(f"   • Concorrência: {MAX_CONCURRENCY} páginas")
    print(f"   • Seletor timeout: {SELECTOR_TIMEOUT}ms (SEM networkidle!)")
    print(f"   • Extra wait: {EXTRA_WAIT}ms")
    print(f"   • Request timeout: {REQUEST_TIMEOUT.total_seconds()}s")
    
    # Carregar URLs
    try:
        with open('urls_matcon_100.txt', 'r', encoding='utf-8') as f:
            urls = [l.strip() for l in f if l.strip() and '/produto/' in l]
        print(f"\n✅ {len(urls)} URLs carregadas")
        stats['total'] = len(urls)
    except:
        print("\n❌ Arquivo urls_matcon_100.txt não encontrado!")
        return
    
    stats['inicio'] = datetime.now()
    print(f"⏱️  Início: {stats['inicio'].strftime('%H:%M:%S')}")
    print("="*80)
    print()
    
    # Crawler ultra-rápido
    crawler = PlaywrightCrawler(
        request_handler=extrair_produto,
        headless=True,
        browser_type='chromium',
        max_request_retries=0,
        max_requests_per_crawl=len(urls),
        max_crawl_depth=0,
        request_handler_timeout=REQUEST_TIMEOUT,
        concurrency_settings=ConcurrencySettings(
            max_concurrency=MAX_CONCURRENCY,
            desired_concurrency=MAX_CONCURRENCY,
            min_concurrency=10,
        ),
    )
    
    watchdog = PerformanceWatchdog(crawler)
    watchdog.start()
    
    try:
        await crawler.run(urls)
    except Exception as e:
        print(f"\n⚠️  Interrompido: {str(e)[:100]}")
    
    stats['fim'] = datetime.now()
    tempo_total = (stats['fim'] - stats['inicio']).total_seconds()
    total = stats['sucesso'] + stats['erro']
    
    # Relatório
    print("\n" + "="*80)
    print("📊 RELATÓRIO FINAL")
    print("="*80)
    
    if stats['abortado']:
        print(f"\n🛑 ABORTADO: {stats['razao_abort']}\n")
    
    print(f"\n⏱️  Tempo: {tempo_total:.2f}s ({tempo_total/60:.2f}min)")
    if total > 0:
        avg = tempo_total/total
        print(f"⚡ Média: {avg:.3f}s/produto")
        print(f"📈 800 produtos: {avg*800:.1f}s ({avg*800/60:.2f}min)")
        
        # Avaliação
        if avg <= TARGET_TIME_PER_ITEM:
            print("\n🎉 EXCELENTE! Atingiu meta!")
        elif avg <= MAX_TIME_PER_ITEM:
            print("\n✅ BOM! Dentro do limite")
        else:
            print("\n⚠️  INSUFICIENTE! Precisa otimizar mais")
    
    print(f"\n✅ Sucesso: {stats['sucesso']}/{total} ({stats['sucesso']/total*100:.1f}%)")
    print(f"⚠️  Erros: {stats['erro']}/{total}")
    
    if stats['tempos_individuais']:
        t = stats['tempos_individuais']
        print(f"\n⏱️  Tempos: Média {sum(t)/len(t):.3f}s | Min {min(t):.3f}s | Max {max(t):.3f}s")
    
    # Salvar
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'resultados_fast_{timestamp}.json'
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump({
            'metadata': {
                'abortado': stats['abortado'],
                'razao_abort': stats['razao_abort'],
                'total': total,
                'sucesso': stats['sucesso'],
                'tempo_total': tempo_total,
                'avg_tempo': tempo_total/total if total > 0 else None,
            },
            'produtos': stats['produtos']
        }, f, ensure_ascii=False, indent=2)
    
    print(f"\n💾 Salvo: {filename}")
    
    if stats['abortado']:
        print("\n🔧 OTIMIZAÇÕES TESTADAS:")
        print("   ✅ Removido networkidle (de 20s → 8s)")
        print("   ✅ Wait apenas h1 (não toda rede)")
        print("   ✅ Extração paralela (1 evaluate)")
        print("   ✅ Concorrência 30 páginas")
        print("\n💡 PRÓXIMAS TENTATIVAS:")
        print("   1. Testar httpx puro (sem browser)")
        print("   2. Verificar se tem API REST disponível")
        print("   3. Scrapy com concorrência 100+")
        print("   4. Aceitar que site é lento e ajustar expectativa")
    
    print("="*80)


if __name__ == "__main__":
    asyncio.run(main())
