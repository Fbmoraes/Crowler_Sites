"""
Extração com ABORT AUTOMÁTICO se performance não atingir meta
Meta: 800 produtos em 2 minutos = 0.15s/produto
Tolerância: Até 0.3s/produto (400 produtos em 2min)
"""

import asyncio
import json
import time
from datetime import datetime, timedelta
from crawlee.crawlers import PlaywrightCrawler
from crawlee import ConcurrencySettings

# ============================================================================
# METAS DE PERFORMANCE - ABORT SE NÃO ATINGIR
# ============================================================================
TARGET_TIME_PER_ITEM = 0.15  # Meta: 800 itens em 120s = 0.15s cada
MAX_TIME_PER_ITEM = 0.30     # Limite: 400 itens em 120s = 0.30s cada
ABORT_CHECK_INTERVAL = 10    # Checar a cada 10 produtos
MIN_SAMPLES = 5              # Mínimo de amostras antes de abortar

# ============================================================================
# CONFIGURAÇÕES AGRESSIVAS - MÁXIMA VELOCIDADE
# ============================================================================
MAX_CONCURRENCY = 20  # 20 páginas simultâneas
NETWORK_TIMEOUT = 10000  # 10s - Rápido
EXTRA_WAIT = 1000  # 1s - Mínimo necessário
REQUEST_TIMEOUT = timedelta(seconds=20)
NO_DELAY = True  # SEM delays entre requests

# ============================================================================
# ESTATÍSTICAS + WATCHDOG
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
    """Monitora performance e aborta se não atingir meta"""
    
    def __init__(self, crawler):
        self.crawler = crawler
        self.start_time = None
        self.item_count = 0
        self.last_check = 0
        
    def start(self):
        self.start_time = time.time()
        
    def check_and_abort_if_slow(self):
        """Verifica se está lento demais e aborta se necessário"""
        self.item_count += 1
        
        # Só checa a cada N produtos
        if self.item_count - self.last_check < ABORT_CHECK_INTERVAL:
            return False
            
        # Precisa de mínimo de amostras
        if self.item_count < MIN_SAMPLES:
            return False
            
        self.last_check = self.item_count
        
        # Calcular tempo médio
        elapsed = time.time() - self.start_time
        avg_time = elapsed / self.item_count
        
        print()
        print(f"⏱️  CHECKPOINT [{self.item_count} produtos]:")
        print(f"   Tempo médio atual: {avg_time:.3f}s/produto")
        print(f"   Meta: {TARGET_TIME_PER_ITEM:.3f}s/produto")
        print(f"   Limite: {MAX_TIME_PER_ITEM:.3f}s/produto")
        
        # Verificar se ultrapassou o limite
        if avg_time > MAX_TIME_PER_ITEM:
            razao = (
                f"Performance insuficiente: {avg_time:.3f}s/produto > {MAX_TIME_PER_ITEM:.3f}s limite.\n"
                f"Com essa velocidade, 800 produtos levariam {avg_time * 800 / 60:.1f} minutos.\n"
                f"Meta era 2 minutos máximo.\n"
                f"ABORTANDO para permitir otimizações."
            )
            print()
            print("=" * 80)
            print("🛑 ABORT AUTOMÁTICO ACIONADO")
            print("=" * 80)
            print(razao)
            print("=" * 80)
            print()
            
            stats['abortado'] = True
            stats['razao_abort'] = razao
            
            # Parar o crawler
            self.crawler.stop(reason=razao)
            return True
        
        # Se estiver OK
        estimativa_800 = avg_time * 800
        print(f"   ✅ Performance OK - 800 produtos em ~{estimativa_800:.1f}s ({estimativa_800/60:.2f}min)")
        print()
        
        return False

# Watchdog global
watchdog = None

# ============================================================================
# FUNÇÃO DE EXTRAÇÃO ULTRA-RÁPIDA
# ============================================================================
async def extrair_produto(context) -> None:
    """Extração com timeout agressivo e abort automático"""
    
    page = context.page
    url = context.request.url
    
    item_start = time.time()
    contador = stats['sucesso'] + stats['erro'] + 1
    
    try:
        # Networkidle com timeout agressivo
        await page.wait_for_load_state('networkidle', timeout=NETWORK_TIMEOUT)
        await page.wait_for_timeout(EXTRA_WAIT)
        
        # Extração paralela de todos os dados
        resultado = await page.evaluate('''
            () => {
                // NOME
                const h1s = Array.from(document.querySelectorAll('h1'));
                const productH1s = h1s.filter(h1 => {
                    const text = h1.textContent;
                    return /\\d/.test(text) && text.length > 20 && 
                           !text.includes('Vendido e Entregue') &&
                           !text.includes('Parceria');
                });
                const nome = productH1s.length > 0 ? productH1s[0].textContent.trim() : 
                             (document.title.match(/^([^|]+)/) ? document.title.match(/^([^|]+)/)[1].trim() : null);
                
                // PREÇOS
                const bodyText = document.body.innerText;
                const precoMatch = bodyText.match(/de\\s+R\\$\\s*([\\d.,]+).*?R\\$\\s*([\\d.,]+)/is);
                const preco_original = precoMatch ? precoMatch[1].replace('.', '').replace(',', '.') : null;
                const preco = precoMatch ? precoMatch[2].replace('.', '').replace(',', '.') : 
                             (bodyText.match(/R\\$\\s*([\\d.,]+)/) ? bodyText.match(/R\\$\\s*([\\d.,]+)/)[1].replace('.', '').replace(',', '.') : null);
                
                // IMAGENS
                const imgs = Array.from(document.querySelectorAll('img[src*="matcon"]'));
                const imagens = imgs
                    .map(img => img.src)
                    .filter(src => !src.includes('logo') && !src.includes('banner'))
                    .slice(0, 5);
                
                return { nome, preco, preco_original, imagens };
            }
        ''')
        
        item_time = time.time() - item_start
        stats['tempos_individuais'].append(item_time)
        
        # Validar
        if resultado['nome'] and resultado['preco']:
            stats['sucesso'] += 1
            print(f"✅ [{contador}] {resultado['nome'][:50]}... | R$ {resultado['preco']} | {item_time:.2f}s")
        else:
            stats['erro'] += 1
            print(f"⚠️  [{contador}] Dados incompletos | {item_time:.2f}s")
        
        stats['produtos'].append({
            'url': url,
            'tempo_extracao': item_time,
            **resultado,
            'extraido_em': datetime.now().isoformat()
        })
        
        # WATCHDOG: Checar performance
        if watchdog:
            watchdog.check_and_abort_if_slow()
        
    except Exception as e:
        stats['erro'] += 1
        item_time = time.time() - item_start
        print(f"❌ [{contador}] Erro: {str(e)[:60]}... | {item_time:.2f}s")
        stats['produtos'].append({
            'url': url,
            'erro': str(e)[:200],
            'tempo_extracao': item_time,
        })


# ============================================================================
# MAIN
# ============================================================================
async def main():
    global watchdog
    
    print("=" * 80)
    print("🚀 EXTRAÇÃO COM ABORT AUTOMÁTICO")
    print("=" * 80)
    print()
    print("📊 Metas de Performance:")
    print(f"   🎯 Target: {TARGET_TIME_PER_ITEM:.3f}s/produto (800 em 2min)")
    print(f"   🚨 Limite: {MAX_TIME_PER_ITEM:.3f}s/produto (400 em 2min)")
    print(f"   ⏱️  Check: A cada {ABORT_CHECK_INTERVAL} produtos")
    print()
    print("⚙️  Configurações AGRESSIVAS:")
    print(f"   • Concorrência: {MAX_CONCURRENCY} páginas simultâneas")
    print(f"   • Network timeout: {NETWORK_TIMEOUT}ms")
    print(f"   • Wait extra: {EXTRA_WAIT}ms")
    print(f"   • Delays: {'Desabilitados' if NO_DELAY else 'Habilitados'}")
    print()
    
    # Carregar URLs
    print("📋 Carregando URLs...")
    try:
        with open('urls_matcon_100.txt', 'r', encoding='utf-8') as f:
            urls = [linha.strip() for linha in f if linha.strip() and '/produto/' in linha]
        
        print(f"✅ {len(urls)} URLs carregadas")
        stats['total'] = len(urls)
        
    except FileNotFoundError:
        print("❌ Arquivo não encontrado!")
        return
    
    stats['inicio'] = datetime.now()
    print(f"⏱️  Início: {stats['inicio'].strftime('%H:%M:%S')}")
    print("=" * 80)
    print()
    
    # Criar crawler
    crawler = PlaywrightCrawler(
        request_handler=extrair_produto,
        headless=True,
        browser_type='chromium',
        max_request_retries=0,  # SEM retries - velocidade máxima
        max_requests_per_crawl=len(urls),
        max_crawl_depth=0,
        request_handler_timeout=REQUEST_TIMEOUT,
        
        concurrency_settings=ConcurrencySettings(
            max_concurrency=MAX_CONCURRENCY,
            desired_concurrency=MAX_CONCURRENCY,
            min_concurrency=5,
        ),
    )
    
    # Iniciar watchdog
    watchdog = PerformanceWatchdog(crawler)
    watchdog.start()
    
    # Executar
    try:
        await crawler.run(urls)
    except Exception as e:
        print(f"\n⚠️  Crawler interrompido: {str(e)[:100]}")
    
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
    
    if stats['abortado']:
        print("🛑 EXECUÇÃO ABORTADA AUTOMATICAMENTE")
        print()
        print("Razão:")
        print(stats['razao_abort'])
        print()
    
    total_processado = stats['sucesso'] + stats['erro']
    
    print(f"⏱️  Tempo total: {tempo_total:.2f}s ({tempo_total/60:.2f}min)")
    if total_processado > 0:
        print(f"⚡ Velocidade média: {tempo_total/total_processado:.3f}s/produto")
        print(f"📈 Estimativa para 800 produtos: {tempo_total/total_processado*800:.1f}s ({tempo_total/total_processado*800/60:.2f}min)")
    print()
    
    print(f"✅ Sucesso: {stats['sucesso']}/{total_processado}")
    print(f"⚠️  Erros: {stats['erro']}/{total_processado}")
    print()
    
    # Análise de performance
    if stats['tempos_individuais']:
        tempos = stats['tempos_individuais']
        avg = sum(tempos) / len(tempos)
        min_t = min(tempos)
        max_t = max(tempos)
        
        print("⏱️  Tempos Individuais:")
        print(f"   Média: {avg:.3f}s")
        print(f"   Mínimo: {min_t:.3f}s")
        print(f"   Máximo: {max_t:.3f}s")
        print()
    
    # Salvar
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'resultados_abort_{timestamp}.json'
    
    resultado_final = {
        'metadata': {
            'abortado': stats['abortado'],
            'razao_abort': stats['razao_abort'],
            'total_processado': total_processado,
            'sucesso': stats['sucesso'],
            'erro': stats['erro'],
            'tempo_total_segundos': tempo_total,
            'velocidade_media': f"{tempo_total/total_processado:.3f}s" if total_processado > 0 else None,
            'meta_target': f"{TARGET_TIME_PER_ITEM:.3f}s",
            'meta_limite': f"{MAX_TIME_PER_ITEM:.3f}s",
        },
        'produtos': stats['produtos']
    }
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(resultado_final, f, ensure_ascii=False, indent=2)
    
    print(f"💾 Resultados: {filename}")
    print()
    
    # Avaliação
    if stats['abortado']:
        print("🔧 PRÓXIMOS PASSOS:")
        print("   1. Reduzir concorrência se houver 429 errors")
        print("   2. Aumentar concorrência se não houver erros")
        print("   3. Otimizar seletores JavaScript")
        print("   4. Considerar usar API direta se disponível")
        print("   5. Testar com httpx puro (sem browser) se possível")
    else:
        if total_processado > 0:
            avg_time = tempo_total / total_processado
            if avg_time <= TARGET_TIME_PER_ITEM:
                print("🎉 PERFORMANCE EXCELENTE! Atingiu a meta!")
            elif avg_time <= MAX_TIME_PER_ITEM:
                print("✅ PERFORMANCE BOA! Dentro do limite aceitável")
            else:
                print("⚠️  PERFORMANCE RUIM! Precisa otimizar")
    
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
