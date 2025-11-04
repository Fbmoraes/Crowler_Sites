"""
QUINTAPP - Orquestrador Multi-Plataforma
Extrai produtos de múltiplas plataformas simultaneamente
Usa ThreadPoolExecutor para atualização em tempo real

FEATURES v2:
- Homepage SSR Discovery (MatConcasa style) - via httpx/BeautifulSoup
- Detecta automaticamente melhor método
"""
import streamlit as st
import csv
import time
from io import StringIO
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import List, Dict, Any
import multiprocessing
import threading
import asyncio

# Importa extratores V8 (mais eficientes)
from extract_linksv8 import extrair_produtos as extrair_produtos_generico
from extract_detailsv8 import extrair_detalhes_paralelo

# Importa extratores específicos
try:
    from extract_dermo_quintapp import extrair_produtos as extrair_produtos_dermo
    from extract_dermo_quintapp import extrair_detalhes_paralelo as extrair_detalhes_dermo
    DERMO_DISPONIVEL = True
except:
    DERMO_DISPONIVEL = False
    print("⚠️ Extrator Dermomanipulações não disponível")

try:
    from extract_katsukazan import extrair_produtos as extrair_produtos_katsukazan
    from extract_katsukazan import extrair_detalhes_paralelo as extrair_detalhes_katsukazan
    KATSUKAZAN_DISPONIVEL = True
except:
    KATSUKAZAN_DISPONIVEL = False
    print("⚠️ Extrator Katsukazan não disponível")

try:
    from extract_mhstudios import extrair_produtos as extrair_produtos_mhstudios
    from extract_mhstudios import extrair_detalhes_paralelo as extrair_detalhes_mhstudios
    MHSTUDIOS_DISPONIVEL = True
except:
    MHSTUDIOS_DISPONIVEL = False
    print("⚠️ Extrator MH Studios não disponível")

try:
    from extract_petrizi import extrair_produtos as extrair_produtos_petrizi
    PETRIZI_DISPONIVEL = True
except:
    PETRIZI_DISPONIVEL = False
    print("⚠️ Extrator Petrizi não disponível")

try:
    from extract_sacada import (
        extrair_produtos as extrair_produtos_sacada,
        extrair_detalhes_paralelo as extrair_detalhes_sacada,
    )
    SACADA_DISPONIVEL = True
except Exception as e:
    SACADA_DISPONIVEL = False
    print(f"⚠️ Extrator Sacada não disponível: {e}")

try:
    from extract_matcon_final import (
        extrair_produtos as extrair_produtos_matcon,
        extrair_detalhes_paralelo as extrair_detalhes_matcon,
    )
    MATCON_DISPONIVEL = True
except Exception as e:
    MATCON_DISPONIVEL = False
    print(f"⚠️ Extrator MatConcasa não disponível: {e}")


async def extrair_urls_homepage(base_url: str, max_produtos: int = 100) -> list:
    """
    Extrai URLs de produtos navegando pela homepage (MatConcasa style)
    Usado para sites SSR sem sitemap útil
    VERSÃO SIMPLIFICADA: usa httpx ao invés de Playwright para ser thread-safe
    """
    print(f"\n🌐 DISCOVERY MODE: {base_url}")
    
    import httpx
    from bs4 import BeautifulSoup
    from urllib.parse import urljoin
    
    produtos_urls = set()
    
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            # 1. Carregar homepage
            print("📄 Carregando homepage...")
            response = await client.get(base_url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 2. Extrair links da homepage
            print("🔍 Buscando produtos na homepage...")
            
            # Busca links que parecem ser de produtos
            for link in soup.find_all('a', href=True):
                href = link.get('href')
                if not href:
                    continue
                
                # Verifica se parece URL de produto
                if '/produto/' in href or '/product/' in href or '/p/' in href.lower():
                    url_completa = urljoin(base_url, href)
                    url_limpa = url_completa.split('?')[0].split('#')[0].rstrip('/')
                    produtos_urls.add(url_limpa)
            
            print(f"  ✓ {len(produtos_urls)} produtos na homepage")
            
            # 3. Tentar categorias principais se precisar de mais
            if len(produtos_urls) < max_produtos:
                print(f"📁 Buscando em categorias...")
                
                categorias_padrao = [
                    "/ferramentas/", "/casa/", "/cozinha/", "/banheiro/",
                    "/construcao/", "/eletrica/", "/hidraulica/",
                ]
                
                for cat in categorias_padrao:
                    if len(produtos_urls) >= max_produtos:
                        break
                    
                    cat_url = base_url.rstrip('/') + cat
                    
                    try:
                        print(f"  Tentando: {cat}")
                        response = await client.get(cat_url, timeout=15.0)
                        
                        if response.status_code == 200:
                            soup_cat = BeautifulSoup(response.text, 'html.parser')
                            
                            novos = 0
                            for link in soup_cat.find_all('a', href=True):
                                href = link.get('href')
                                if not href:
                                    continue
                                
                                if '/produto/' in href or '/product/' in href or '/p/' in href.lower():
                                    url_completa = urljoin(base_url, href)
                                    url_limpa = url_completa.split('?')[0].split('#')[0].rstrip('/')
                                    
                                    if url_limpa not in produtos_urls:
                                        produtos_urls.add(url_limpa)
                                        novos += 1
                            
                            if novos > 0:
                                print(f"    ✓ +{novos} produtos (total: {len(produtos_urls)})")
                        
                    except Exception as e:
                        print(f"    ✗ Erro em {cat}: {str(e)[:50]}")
                        pass
        
    except Exception as e:
        print(f"❌ Erro no discovery: {e}")
        import traceback
        traceback.print_exc()
        return []
    
    # Filtrar produtos reais (remover categorias)
    produtos_reais = []
    for url in produtos_urls:
        partes = url.split('/')
        # Deve ter nome de produto (última parte com hífen e razoável)
        if len(partes) >= 5:
            ultima_parte = partes[-1]
            if '-' in ultima_parte and len(ultima_parte) > 10:
                produtos_reais.append(url)
    
    print(f"📦 Total filtrado: {len(produtos_reais)} produtos\n")
    
    return produtos_reais[:max_produtos]


def extrair_urls_homepage_sync(base_url: str, max_produtos: int = 100) -> list:
    """Wrapper síncrono para extrair_urls_homepage - thread-safe"""
    try:
        # Tenta usar loop existente
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Se já tem loop rodando, cria novo em thread separada
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, extrair_urls_homepage(base_url, max_produtos))
                return future.result()
        else:
            return asyncio.run(extrair_urls_homepage(base_url, max_produtos))
    except RuntimeError:
        # Se der erro com loop, força execução em thread nova
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(asyncio.run, extrair_urls_homepage(base_url, max_produtos))
            return future.result()
    except Exception as e:
        print(f"❌ Erro no discovery: {e}")
        import traceback
        traceback.print_exc()
        return []

def detectar_extrator(url: str):
    """
    Detecta qual extrator usar baseado na URL
    Retorna: (tipo, fn_extrair_produtos, fn_extrair_detalhes, usar_discovery)
    """
    url_lower = url.lower()
    
    # Dermomanipulações
    if 'dermomanipulacoes' in url_lower and DERMO_DISPONIVEL:
        return 'dermo', extrair_produtos_dermo, extrair_detalhes_dermo, False
    
    # Katsukazan
    if 'katsukazan' in url_lower and KATSUKAZAN_DISPONIVEL:
        return 'katsukazan', extrair_produtos_katsukazan, extrair_detalhes_katsukazan, False
    
    # MH Studios
    if 'mhstudios' in url_lower and MHSTUDIOS_DISPONIVEL:
        return 'mhstudios', extrair_produtos_mhstudios, extrair_detalhes_mhstudios, False
    
    # Petrizi
    if 'petrizi' in url_lower and PETRIZI_DISPONIVEL:
        return 'petrizi', extrair_produtos_petrizi, None, False
    
    # Sacada (VTEX + Apollo Cache)
    if 'sacada' in url_lower and SACADA_DISPONIVEL:
        return 'sacada', extrair_produtos_sacada, extrair_detalhes_sacada, False
    
    # MatConcasa - Next.js/React SPA (requer Playwright)
    if ('matconcasa' in url_lower or 'matcon' in url_lower) and MATCON_DISPONIVEL:
        return 'matcon', extrair_produtos_matcon, extrair_detalhes_matcon, False
    
    # Genérico (padrão)
    return 'generico', extrair_produtos_generico, extrair_detalhes_paralelo, False


def processar_plataforma(url: str, max_produtos: int = None, max_workers: int = 20, progress_callback=None, usar_discovery: bool = False) -> Dict[str, Any]:
    """
    Processa uma plataforma completa (links + detalhes)
    Executa em thread - callbacks desabilitados para evitar problemas com Streamlit
    
    usar_discovery: Se True, usa Homepage SSR Discovery (MatConcasa style)
    """
    try:
        inicio = time.time()
        
        # Detecta extrator apropriado
        tipo_extrator, extrair_produtos_fn, extrair_detalhes_fn, auto_discovery = detectar_extrator(url)
        
        # Usa discovery se auto-detectado OU forçado pelo parâmetro
        usar_discovery = usar_discovery or auto_discovery
        
        # Callback silencioso
        def callback_dummy(msg):
            print(f"[{url}] [{tipo_extrator.upper()}] {msg}")
        
        # Fase 1: Extração de links
        try:
            if usar_discovery:
                # Modo Discovery: extrai URLs navegando na homepage
                print(f"\n🌐 [{tipo_extrator.upper()}] Usando DISCOVERY MODE")
                try:
                    produtos_links_urls = extrair_urls_homepage_sync(url, max_produtos or 100)
                except Exception as e_discovery:
                    return {
                        'url': url,
                        'sucesso': False,
                        'erro': f'Discovery mode falhou: {str(e_discovery)}',
                        'produtos': [],
                        'tempo_links': time.time() - inicio,
                        'tempo_detalhes': 0,
                        'tempo_total': time.time() - inicio
                    }
                
                # Converte URLs para formato esperado pelo extrator de detalhes
                produtos_links = []
                for i, prod_url in enumerate(produtos_links_urls, 1):
                    produtos_links.append({
                        'indice': i,
                        'url': prod_url,
                        'nome': f"Produto {i}",  # Placeholder, será extraído depois
                    })
                
                if not produtos_links:
                    return {
                        'url': url,
                        'sucesso': False,
                        'erro': 'Discovery mode não encontrou produtos',
                        'produtos': [],
                        'tempo_links': time.time() - inicio,
                        'tempo_detalhes': 0,
                        'tempo_total': time.time() - inicio
                    }
                
            else:
                # Modo Normal: usa sitemap/extrator específico
                produtos_links = extrair_produtos_fn(url, callback_dummy, max_produtos)
        
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {
                'url': url,
                'sucesso': False,
                'erro': f'Erro na extração de links: {str(e)[:100]}',
                'produtos': [],
                'tempo_links': time.time() - inicio,
                'tempo_detalhes': 0,
                'tempo_total': time.time() - inicio
            }
        
        if not produtos_links:
            return {
                'url': url,
                'sucesso': False,
                'erro': 'Nenhum produto encontrado',
                'produtos': [],
                'tempo_links': time.time() - inicio,
                'tempo_detalhes': 0,
                'tempo_total': time.time() - inicio
            }
        
        tempo_links = time.time() - inicio
        
        # Fase 2: Extração de detalhes
        inicio_detalhes = time.time()
        produtos_para_detalhar = max_produtos if max_produtos else len(produtos_links)
        
        try:
            # Petrizi e Sacada já extraem tudo junto (sem fase de detalhes)
            if extrair_detalhes_fn is None:
                detalhes = produtos_links
            elif usar_discovery:
                # Para discovery, usar extrator genérico de detalhes
                _, detalhes = extrair_detalhes_paralelo(
                    produtos_links,
                    callback_dummy,
                    produtos_para_detalhar,
                    max_workers
                )
            else:
                # Usa o extrator específico
                _, detalhes = extrair_detalhes_fn(
                    produtos_links,
                    callback_dummy,
                    produtos_para_detalhar,
                    max_workers
                )
        except Exception as e:
            return {
                'url': url,
                'sucesso': False,
                'erro': f'Erro na extração de detalhes: {str(e)}',
                'produtos': [],
                'tempo_links': tempo_links,
                'tempo_detalhes': 0,
                'tempo_total': time.time() - inicio
            }
        
        tempo_detalhes = time.time() - inicio_detalhes
        tempo_total = time.time() - inicio
        
        return {
            'url': url,
            'sucesso': True,
            'erro': None,
            'produtos': detalhes,
            'total_produtos': len(detalhes),
            'tempo_links': tempo_links,
            'tempo_detalhes': tempo_detalhes,
            'tempo_total': tempo_total,
            'produtos_por_segundo': len(detalhes) / tempo_total if tempo_total > 0 else 0,
            'modo': 'discovery' if usar_discovery else 'normal'
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            'url': url,
            'sucesso': False,
            'erro': f'Erro inesperado: {str(e)}',
            'produtos': [],
            'tempo_links': 0,
            'tempo_detalhes': 0,
            'tempo_total': 0
        }

def main():
    st.set_page_config(
        page_title="QuintApp - Multi-Plataforma",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    st.title("QuintApp - Extração Multi-Plataforma Paralela")
    st.markdown("**Processa múltiplas plataformas simultaneamente usando todos os núcleos da CPU**")
    
    # Mostra extratores disponíveis
    st.info(f"""
    **Extratores Disponíveis:**
    - ✅ Genérico (VTEX, Shopify, WordPress, etc)
    {f"- ✅ Dermomanipulações (otimizado - JSON-LD categorias)" if DERMO_DISPONIVEL else "- ⚠️ Dermomanipulações (não disponível)"}
    {f"- ✅ Katsukazan (otimizado - JSON-LD homepage)" if KATSUKAZAN_DISPONIVEL else "- ⚠️ Katsukazan (não disponível)"}
    {f"- ✅ MH Studios (otimizado - Shopify API)" if MHSTUDIOS_DISPONIVEL else "- ⚠️ MH Studios (não disponível)"}
    {f"- ✅ Petrizi (otimizado - Tray HTML microdata)" if PETRIZI_DISPONIVEL else "- ⚠️ Petrizi (não disponível)"}
    {f"- ✅ Sacada (otimizado - Apollo Cache GraphQL)" if SACADA_DISPONIVEL else "- ⚠️ Sacada (não disponível)"}
    - 🌐 **Homepage SSR Discovery** (MatConcasa, sites SSR sem sitemap útil)
    
    O QuintApp detecta automaticamente qual extrator usar!
    """)
    
    # Info do sistema
    cpus = multiprocessing.cpu_count()
    col_info1, col_info2, col_info3 = st.columns(3)
    with col_info1:
        st.metric("CPUs Disponíveis", cpus)
    with col_info2:
        st.metric("Processos Paralelos", f"Até {cpus}")
    with col_info3:
        usar_discovery_global = st.checkbox(
            "🌐 Forçar Discovery", 
            value=False,
            help="Força uso do Homepage Discovery em TODOS os sites (útil para testar sites com sitemap ruim)"
        )
    
    # Input de URLs
    st.header("1. Configurar Plataformas")
    
    # URLs padrão para teste
    urls_padrao = """https://www.gigabarato.com.br
https://www.sacada.com
https://www.freixenet.com.br
https://www.dermomanipulacoes.com.br
https://mhstudios.com.br
https://katsukazan.com.br
https://petrizi.com.br
https://www.matconcasa.com.br
https://artistasdomundo.com.br
https://www.magnumauto.com.br
https://www.emcmedical.com.br
https://www.cebmodaseacessorios.com.br"""
    
    urls_input = st.text_area(
        "URLs das plataformas (uma por linha):",
        value=urls_padrao,
        height=200,
        help="Lista de e-commerces brasileiros em diferentes plataformas (VTEX, Shopify, Nuvemshop, Tray, Magento, WooCommerce, Wix, Loja Integrada)"
    )
    
    # Configurações globais
    st.header("2. Configurações")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        max_produtos = st.number_input(
            "Produtos por plataforma (0 = todos)",
            min_value=0,
            max_value=10000,
            value=0,
            step=50,
            help="0 significa sem limite"
        )
    
    with col2:
        max_workers_detalhes = st.number_input(
            "Threads por plataforma",
            min_value=1,
            max_value=40,
            value=20,
            step=5,
            help="Threads para extração de detalhes em cada plataforma"
        )
    
    with col3:
        max_threads = st.number_input(
            "Plataformas simultâneas",
            min_value=1,
            max_value=cpus * 2,
            value=min(4, cpus),
            step=1,
            help=f"Recomendado: {cpus}-{cpus*2} (CPUs x2)"
        )
    
    # Converte 0 para None
    max_produtos = None if max_produtos == 0 else max_produtos
    
    st.info(f"Estratégia: {max_threads} plataformas em paralelo, cada uma usando {max_workers_detalhes} threads")
    
    # Botão de extração
    st.header("3. Executar Extração")
    
    if st.button("EXTRAIR TODAS AS PLATAFORMAS", type="primary", use_container_width=True):
        # Processa URLs
        urls = [url.strip() for url in urls_input.split('\n') if url.strip()]
        
        if not urls:
            st.error("Adicione pelo menos uma URL")
            return
        
        st.success(f"{len(urls)} plataforma(s) detectada(s)")
        
        # Containers para progresso
        progress_container = st.container()
        resultados_container = st.container()
        
        with progress_container:
            st.markdown("### Progresso em Tempo Real")
            
            # Métricas de progresso
            col_prog1, col_prog2, col_prog3, col_prog4 = st.columns(4)
            metric_concluidas = col_prog1.empty()
            metric_processando = col_prog2.empty()
            metric_pendentes = col_prog3.empty()
            metric_tempo = col_prog4.empty()
            
            # Barra de progresso geral
            st.markdown("**Progresso Geral**")
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            st.markdown("---")
            
            # Container para cards de plataforma
            plataforma_progress = {}
            plataforma_containers = {}
        
        # Inicia processamento paralelo
        inicio_geral = time.time()
        resultados = []
        status_plataformas = {}
        lock = threading.Lock()
        
        # Cria cards de progresso para cada plataforma
        cols_per_row = 2
        for i in range(0, len(urls), cols_per_row):
            cols = st.columns(cols_per_row)
            for j, url in enumerate(urls[i:i+cols_per_row]):
                with cols[j]:
                    nome_curto = url.replace('https://www.', '').replace('https://', '').replace('http://www.', '').replace('http://', '')
                    
                    # Card container com borda
                    with st.container(border=True):
                        st.markdown(f"### {nome_curto}")
                        
                        # Métricas lado a lado
                        col_metric1, col_metric2 = st.columns(2)
                        with col_metric1:
                            metric_produtos = st.empty()
                        with col_metric2:
                            metric_tempo = st.empty()
                        
                        # Progresso
                        progress_bar_plat = st.progress(0)
                        status_text_plat = st.empty()
                        
                        st.markdown("---")
                        
                        # Placeholder para tabela de produtos
                        st.markdown("**Produtos Extraídos (Prévia)**")
                        table_container = st.empty()
                    
                    plataforma_containers[url] = None  # Não precisa mais guardar o container
                    plataforma_progress[url] = {
                        'progress_bar': progress_bar_plat,
                        'status_text': status_text_plat,
                        'metric_produtos': metric_produtos,
                        'metric_tempo': metric_tempo,
                        'table_container': table_container,
                        'nome_curto': nome_curto,
                        'inicio': None
                    }
                    status_plataformas[url] = {'estado': 'aguardando', 'atual': 0, 'total': 0}
        
        with ThreadPoolExecutor(max_workers=max_threads) as executor:
            # Submit todas as tarefas SEM callbacks (Streamlit não suporta atualização em threads)
            futures = {}
            for url in urls:
                plataforma_progress[url]['inicio'] = time.time()
                plataforma_progress[url]['status_text'].info("Processando...")
                plataforma_progress[url]['progress_bar'].progress(0.1)
                future = executor.submit(processar_plataforma, url, max_produtos, max_workers_detalhes, None, usar_discovery_global)
                futures[future] = url
            
            concluidas = 0
            processando = len(futures)
            
            # Processa conforme completam e atualiza UI
            for future in as_completed(futures):
                url = futures[future]
                
                try:
                    resultado = future.result()
                    resultados.append(resultado)
                    
                    # Atualiza card da plataforma COM OS RESULTADOS
                    if resultado['sucesso']:
                        total_prod = resultado['total_produtos']
                        tempo = resultado['tempo_total']
                        modo = resultado.get('modo', 'normal')
                        modo_icon = "🌐" if modo == 'discovery' else "🔗"
                        
                        plataforma_progress[url]['progress_bar'].progress(1.0)
                        plataforma_progress[url]['status_text'].success(f"✅ Concluído em {tempo:.1f}s {modo_icon}")
                        plataforma_progress[url]['metric_produtos'].metric("Produtos Encontrados", total_prod)
                        plataforma_progress[url]['metric_tempo'].metric("Tempo Total", f"{tempo:.1f}s")
                        
                        # Mostra prévia dos produtos
                        if resultado.get('produtos'):
                            df_preview = []
                            for prod in resultado['produtos'][:5]:  # Mostra só 5
                                df_preview.append({
                                    'Nome': prod.get('nome', 'N/A')[:40] + '...' if len(prod.get('nome', '')) > 40 else prod.get('nome', 'N/A'),
                                    'Preço': prod.get('preco', 'N/A'),
                                    'Marca': prod.get('marca', 'N/A')
                                })
                            
                            if df_preview:
                                plataforma_progress[url]['table_container'].dataframe(
                                    df_preview, 
                                    use_container_width=True,
                                    hide_index=True
                                )
                    else:
                        plataforma_progress[url]['progress_bar'].progress(1.0)
                        plataforma_progress[url]['status_text'].error(f"❌ {resultado['erro'][:100]}")
                        plataforma_progress[url]['metric_produtos'].metric("Produtos", "0")
                        plataforma_progress[url]['metric_tempo'].metric("Tempo", "0.0s")
                    
                except Exception as e:
                    resultados.append({
                        'url': url,
                        'sucesso': False,
                        'erro': str(e),
                        'produtos': []
                    })
                    plataforma_progress[url]['progress_bar'].progress(1.0)
                    plataforma_progress[url]['status_text'].error(f"❌ Exceção: {str(e)[:100]}")
                    plataforma_progress[url]['metric_produtos'].metric("Produtos", "0")
                    plataforma_progress[url]['metric_tempo'].metric("Tempo", "0.0s")
                
                # Atualiza métricas gerais
                concluidas += 1
                processando = len(futures) - concluidas
                pendentes = len(urls) - concluidas - processando
                tempo_decorrido = time.time() - inicio_geral
                
                metric_concluidas.metric("Concluídas", concluidas)
                metric_processando.metric("Processando", processando)
                metric_pendentes.metric("Pendentes", pendentes)
                metric_tempo.metric("Tempo", f"{tempo_decorrido:.1f}s")
                
                progress_bar.progress(concluidas / len(urls))
                status_text.text(f"Processando... {concluidas}/{len(urls)} plataformas")
        
        tempo_total_geral = time.time() - inicio_geral
        
        progress_bar.progress(1.0)
        status_text.text(f"Processamento concluído em {tempo_total_geral:.2f} segundos!")
        
        # Armazena resultados na sessão
        st.session_state.resultados = resultados
        st.session_state.tempo_total = tempo_total_geral
    
    # Mostra resultados
    if 'resultados' in st.session_state:
        st.header("4. Resultados")
        
        resultados = st.session_state.resultados
        tempo_total = st.session_state.tempo_total
        
        # Métricas gerais
        sucesso_count = sum(1 for r in resultados if r['sucesso'])
        erro_count = len(resultados) - sucesso_count
        total_produtos = sum(r.get('total_produtos', 0) for r in resultados if r['sucesso'])
        
        col_res1, col_res2, col_res3, col_res4 = st.columns(4)
        
        with col_res1:
            st.metric("Plataformas OK", f"{sucesso_count}/{len(resultados)}")
        
        with col_res2:
            st.metric("Com Erros", erro_count)
        
        with col_res3:
            st.metric("Total de Produtos", total_produtos)
        
        with col_res4:
            produtos_por_segundo = total_produtos / tempo_total if tempo_total > 0 else 0
            st.metric("Produtos/segundo", f"{produtos_por_segundo:.2f}")
        
        # Tabela de performance por plataforma
        st.subheader("Performance por Plataforma")
        
        performance_data = []
        for resultado in resultados:
            if resultado['sucesso']:
                modo = resultado.get('modo', 'normal')
                modo_display = "🌐 Discovery" if modo == 'discovery' else "🔗 Normal"
                
                performance_data.append({
                    'URL': resultado['url'],
                    'Modo': modo_display,
                    'Produtos': resultado.get('total_produtos', 0),
                    'Tempo Links (s)': f"{resultado.get('tempo_links', 0):.2f}",
                    'Tempo Detalhes (s)': f"{resultado.get('tempo_detalhes', 0):.2f}",
                    'Tempo Total (s)': f"{resultado.get('tempo_total', 0):.2f}",
                    'Produtos/s': f"{resultado.get('produtos_por_segundo', 0):.2f}",
                    'Status': '✅ Sucesso'
                })
            else:
                performance_data.append({
                    'URL': resultado['url'],
                    'Modo': '-',
                    'Produtos': 0,
                    'Tempo Links (s)': '-',
                    'Tempo Detalhes (s)': '-',
                    'Tempo Total (s)': '-',
                    'Produtos/s': '-',
                    'Status': f'❌ {resultado.get("erro", "Erro")[:50]}'
                })
        
        st.dataframe(performance_data, use_container_width=True)
        
        # Consolidação de todos os produtos
        st.subheader("Produtos Consolidados")
        
        todos_produtos = []
        for resultado in resultados:
            if resultado['sucesso']:
                for produto in resultado.get('produtos', []):
                    # Adiciona origem
                    produto_com_origem = produto.copy()
                    produto_com_origem['plataforma'] = resultado['url']
                    todos_produtos.append(produto_com_origem)
        
        if todos_produtos:
            st.dataframe(todos_produtos, use_container_width=True)
            
            # Download CSV consolidado
            csv_buffer = StringIO()
            
            # Pega todos os campos únicos
            fieldnames = list(set().union(*(produto.keys() for produto in todos_produtos)))
            
            # Prioriza ordem dos campos
            campos_prioritarios = ['plataforma', 'indice', 'nome', 'preco', 'preco_original', 'marca', 'categoria', 'url']
            fieldnames_ordenados = [c for c in campos_prioritarios if c in fieldnames]
            fieldnames_ordenados += [c for c in fieldnames if c not in campos_prioritarios]
            
            writer = csv.DictWriter(csv_buffer, fieldnames=fieldnames_ordenados, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(todos_produtos)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            st.download_button(
                label=f"Baixar Todos os Produtos CSV ({len(todos_produtos)} produtos)",
                data=csv_buffer.getvalue(),
                file_name=f"quintapp_produtos_{timestamp}.csv",
                mime="text/csv",
                use_container_width=True
            )
            
            # Download por plataforma
            with st.expander("Download Individual por Plataforma"):
                for resultado in resultados:
                    if resultado['sucesso'] and resultado.get('produtos'):
                        csv_buffer_individual = StringIO()
                        
                        fieldnames_individual = list(set().union(*(p.keys() for p in resultado['produtos'])))
                        writer_individual = csv.DictWriter(csv_buffer_individual, fieldnames=fieldnames_individual, extrasaction='ignore')
                        writer_individual.writeheader()
                        writer_individual.writerows(resultado['produtos'])
                        
                        nome_plataforma = resultado['url'].replace('https://', '').replace('http://', '').replace('/', '_').replace('.', '_')
                        
                        st.download_button(
                            label=f"{resultado['url']} ({len(resultado['produtos'])} produtos)",
                            data=csv_buffer_individual.getvalue(),
                            file_name=f"{nome_plataforma}_{timestamp}.csv",
                            mime="text/csv",
                            key=f"download_{nome_plataforma}"
                        )
        else:
            st.warning("Nenhum produto foi extraído de nenhuma plataforma")
    
    # Sidebar com informações
    with st.sidebar:
        st.markdown("### QuintApp")
        st.markdown("""
        **Extração Multi-Plataforma**
        
        Processa várias plataformas ao mesmo tempo usando:
        - ThreadPoolExecutor para paralelismo
        - Atualização em tempo real no Streamlit
        - ThreadPool para detalhes dentro de cada plataforma
        
        **Arquitetura:**
        ```
        QuintApp (Main Thread)
        ├─ Thread 1: Plataforma A
        │  ├─ Thread 1-20: Detalhes
        ├─ Thread 2: Plataforma B
        │  ├─ Thread 1-20: Detalhes
        ├─ Thread 3: Plataforma C
        │  ├─ Thread 1-20: Detalhes
        └─ Thread 4: Plataforma D
           ├─ Thread 1-20: Detalhes
        ```
        
        **Performance:**
        - 1 plataforma: ~1-5 min
        - 4 plataformas: ~1-5 min (paralelo!)
        - UI atualizada em tempo real
        """)
        
        st.markdown("---")
        
        st.markdown("### 🌐 Discovery Mode")
        st.markdown("""
        **Homepage SSR Discovery (MatConcasa style)**
        
        Para sites com SSR mas sitemap ruim:
        1. Abre homepage com Playwright
        2. Extrai links de produtos
        3. Navega categorias principais
        4. Scroll para lazy loading
        5. Filtra produtos reais
        
        **Quando usar:**
        - Sitemap só tem categorias
        - Site usa Next.js/Nuxt (SSR)
        - Homepage tem produtos
        
        **Auto-detecção:**
        - MatConcasa (auto)
        - Outros: force com checkbox
        
        **Performance:**
        - +30-60s para descobrir URLs
        - Mesma velocidade de extração
        - Limite: 100 produtos
        """)
        
        st.markdown("---")
        
        st.markdown("### Dicas")
        st.markdown("""
        1. **Plataformas simultâneas**: 
           - CPU básico: 2-4
           - CPU potente: 4-8
        
        2. **Threads por plataforma**:
           - Conservador: 10-20
           - Agressivo: 30-40
        
        3. **Limite de produtos**:
           - Teste: 50-100
           - Produção: 0 (todos)
        
        4. **Diferentes domínios**:
           - Sem problemas de rate limit
           - Cada site tem seu limite próprio
        """)
        
        st.markdown("---")
        
        st.markdown("### Plataformas Pré-configuradas")
        st.markdown("""
        **12 e-commerces brasileiros:**
        
        **VTEX**
        - Gigabarato (733 produtos)
        - Sacada (3.305 produtos - Apollo Cache)
        - Freixenet (101 produtos)
        - Dermomanipulações (JSON-LD)
        
        **Shopify**
        - MH Studios (Shopify API)
        
        **Nuvemshop**
        - Katsukazan (JSON-LD)
        
        **Tray**
        - Petrizi Makeup (HTML microdata)
        
        **Next.js/SSR** 🌐
        - MatConcasa (Discovery mode)
        
        **Magento**
        - Artistas do Mundo
        
        **WooCommerce**
        - Magnum Auto
        
        **Wix**
        - EMC Medical
        
        **Loja Integrada**
        - C&B Modas
        """)
        
        st.markdown("---")
        
        st.markdown("### Configuração do PC")
        
        st.markdown("---")
        
        st.markdown("### Configuração do PC")
        st.code(f"CPUs: {multiprocessing.cpu_count()}")
        st.code(f"Memória: Recomendado 4GB+")

if __name__ == "__main__":
    main()
