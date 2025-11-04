"""
TENTATIVA FINAL: httpx puro (sem browser)
Se o HTML já vem com dados no source, não precisa de JS!
"""

import asyncio
import httpx
import json
import time
from datetime import datetime
from bs4 import BeautifulSoup
import re

# ============================================================================
# METAS
# ============================================================================
TARGET_TIME = 0.15
MAX_TIME = 0.30
ABORT_CHECK = 10

# ============================================================================
# CONFIGURAÇÃO HTTPX AGRESSIVA
# ============================================================================
MAX_CONNECTIONS = 50  # 50 conexões simultâneas
TIMEOUT = 10.0  # 10s timeout

stats = {
    'total': 0,
    'sucesso': 0,
    'erro': 0,
    'produtos': [],
    'inicio': None,
    'fim': None,
    'abortado': False,
    'razao_abort': None,
    'tempos': [],
}

class Watchdog:
    def __init__(self):
        self.start = time.time()
        self.count = 0
        self.last_check = 0
        self.should_abort = False
        
    def check(self):
        self.count += 1
        if self.count - self.last_check < ABORT_CHECK or self.count < 5:
            return False
        
        self.last_check = self.count
        elapsed = time.time() - self.start
        avg = elapsed / self.count
        
        print(f"\n⏱️  CHECKPOINT [{self.count}]: {avg:.3f}s/item (meta: {MAX_TIME:.3f}s)")
        
        if avg > MAX_TIME:
            print(f"🛑 ABORT: {avg:.3f}s > {MAX_TIME:.3f}s | 800 items: {avg*800/60:.1f}min")
            stats['abortado'] = True
            stats['razao_abort'] = f"httpx também lento: {avg:.3f}s/item"
            self.should_abort = True
            return True
        
        print(f"✅ OK: 800 items em ~{avg*800:.1f}s ({avg*800/60:.2f}min)")
        return False

watchdog = Watchdog()

async def extrair_produto_httpx(client, url, semaphore):
    """Extração com httpx puro (sem browser)"""
    
    async with semaphore:
        start = time.time()
        contador = stats['sucesso'] + stats['erro'] + 1
        
        try:
            # Request HTTP direto
            response = await client.get(url, follow_redirects=True)
            response.raise_for_status()
            
            # Parse HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # NOME
            nome = None
            h1s = soup.find_all('h1')
            for h1 in h1s:
                text = h1.get_text().strip()
                if len(text) > 20 and any(c.isdigit() for c in text):
                    if 'Vendido' not in text and 'Parceria' not in text:
                        nome = text
                        break
            
            if not nome and h1s:
                nome = h1s[0].get_text().strip()
            
            # PREÇOS
            body_text = soup.get_text()
            preco = None
            preco_original = None
            
            # Padrão desconto
            desc_match = re.search(r'de\s+R\$\s*([\d.,]+).*?R\$\s*([\d.,]+)', body_text, re.IGNORECASE | re.DOTALL)
            if desc_match:
                preco_original = desc_match.group(1).replace('.', '').replace(',', '.')
                preco = desc_match.group(2).replace('.', '').replace(',', '.')
            else:
                # Fallback
                preco_match = re.search(r'R\$\s*([\d.,]+)', body_text)
                if preco_match:
                    preco = preco_match.group(1).replace('.', '').replace(',', '.')
            
            # IMAGENS
            imgs = soup.find_all('img', src=re.compile('matcon'))
            imagens = len([img for img in imgs if 'logo' not in img.get('src', '').lower()])
            
            elapsed = time.time() - start
            stats['tempos'].append(elapsed)
            
            if nome and preco:
                stats['sucesso'] += 1
                nome_curto = nome[:40] if len(nome) > 40 else nome
                print(f"✅[{contador:2d}] {nome_curto:40s} R${preco:>8s} {elapsed:5.3f}s")
            else:
                stats['erro'] += 1
                print(f"⚠️ [{contador:2d}] Incompleto {elapsed:5.3f}s")
            
            stats['produtos'].append({
                'url': url,
                'nome': nome,
                'preco': preco,
                'preco_original': preco_original,
                'imagens': imagens,
                'tempo': elapsed,
                'metodo': 'httpx'
            })
            
            # Watchdog
            if watchdog.check():
                return True  # Sinal para abortar
            
            return False
            
        except Exception as e:
            elapsed = time.time() - start
            stats['erro'] += 1
            print(f"❌[{contador:2d}] {str(e)[:40]:40s} {elapsed:5.3f}s")
            stats['produtos'].append({
                'url': url,
                'erro': str(e)[:200],
                'tempo': elapsed,
                'metodo': 'httpx'
            })
            return False


async def main():
    print("="*80)
    print("🚀 TESTE HTTPX PURO (SEM BROWSER)")
    print("="*80)
    print(f"\n📊 Metas: {TARGET_TIME:.3f}s target | {MAX_TIME:.3f}s limite")
    print(f"\n⚙️  Config:")
    print(f"   • Conexões simultâneas: {MAX_CONNECTIONS}")
    print(f"   • Timeout: {TIMEOUT}s")
    print(f"   • Método: HTTP direto (sem JavaScript)")
    
    # Carregar URLs
    try:
        with open('urls_matcon_100.txt', 'r', encoding='utf-8') as f:
            urls = [l.strip() for l in f if l.strip() and '/produto/' in l]
        print(f"\n✅ {len(urls)} URLs carregadas")
        stats['total'] = len(urls)
    except:
        print("\n❌ Arquivo não encontrado!")
        return
    
    stats['inicio'] = datetime.now()
    print(f"⏱️  Início: {stats['inicio'].strftime('%H:%M:%S')}")
    print("="*80)
    print()
    
    # Cliente httpx com configurações agressivas
    limits = httpx.Limits(
        max_connections=MAX_CONNECTIONS,
        max_keepalive_connections=MAX_CONNECTIONS
    )
    
    timeout = httpx.Timeout(TIMEOUT, connect=5.0)
    
    async with httpx.AsyncClient(limits=limits, timeout=timeout) as client:
        semaphore = asyncio.Semaphore(MAX_CONNECTIONS)
        
        # Executar todas as URLs em paralelo
        tasks = []
        for url in urls:
            if watchdog.should_abort:
                break
            task = asyncio.create_task(extrair_produto_httpx(client, url, semaphore))
            tasks.append(task)
        
        # Aguardar todas (ou até abortar)
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Se alguma retornou True, foi abort
        if any(r is True for r in results if not isinstance(r, Exception)):
            print("\n🛑 Abort detectado, cancelando restantes...")
    
    stats['fim'] = datetime.now()
    tempo_total = (stats['fim'] - stats['inicio']).total_seconds()
    total = stats['sucesso'] + stats['erro']
    
    # Relatório
    print("\n" + "="*80)
    print("📊 RELATÓRIO FINAL - HTTPX PURO")
    print("="*80)
    
    if stats['abortado']:
        print(f"\n🛑 ABORTADO: {stats['razao_abort']}\n")
    
    print(f"\n⏱️  Tempo: {tempo_total:.2f}s ({tempo_total/60:.2f}min)")
    if total > 0:
        avg = tempo_total/total
        print(f"⚡ Média: {avg:.3f}s/produto")
        print(f"📈 800 produtos: {avg*800:.1f}s ({avg*800/60:.2f}min)")
        
        if avg <= TARGET_TIME:
            print("\n🎉 EXCELENTE! Atingiu meta!")
        elif avg <= MAX_TIME:
            print("\n✅ BOM! Dentro do limite")
        else:
            print("\n⚠️  INSUFICIENTE! Matcon Casa é muito lento")
    
    print(f"\n✅ Sucesso: {stats['sucesso']}/{total} ({stats['sucesso']/total*100:.1f}%)")
    print(f"⚠️  Erros: {stats['erro']}/{total}")
    
    if stats['tempos']:
        t = stats['tempos']
        print(f"\n⏱️  Tempos: Média {sum(t)/len(t):.3f}s | Min {min(t):.3f}s | Max {max(t):.3f}s")
    
    # Salvar
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'resultados_httpx_{timestamp}.json'
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump({
            'metadata': {
                'metodo': 'httpx_puro',
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
    
    # Conclusão
    if stats['abortado'] or (total > 0 and tempo_total/total > MAX_TIME):
        print("\n" + "="*80)
        print("💡 CONCLUSÃO FINAL")
        print("="*80)
        print("\n🔍 TODAS as otimizações testadas:")
        print("   1. ❌ Playwright com networkidle: ~7-10s/item")
        print("   2. ❌ Playwright sem networkidle: ~0.7-1s/item")
        print("   3. ❌ httpx puro: (testando agora...)")
        print("\n📊 ANÁLISE:")
        print("   • Matcon Casa é um site PESADO")
        print("   • Usa Next.js com Server Components")
        print("   • Dados vêm em chunks progressivos")
        print("   • Impossível atingir 0.15s/item com scraping")
        print("\n✅ RECOMENDAÇÕES:")
        print("   1. Ajustar expectativa: 800 items em 10-15min (não 2min)")
        print("   2. Verificar se Matcon tem API oficial")
        print("   3. Negociar acesso a feed/catálogo direto")
        print("   4. Aceitar scraping mais lento e rodar overnight")
        print("   5. Considerar sites alternativos mais rápidos")
    
    print("="*80)


if __name__ == "__main__":
    asyncio.run(main())
