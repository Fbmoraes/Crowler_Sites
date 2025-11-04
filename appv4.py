import csv
from io import StringIO

import streamlit as st
from extract_linksv7 import extrair_produtos_rapido
from extract_detailsv4 import extrair_detalhes_paralelo

def main():
    st.set_page_config(
        page_title="Crowler V5",
        layout="wide"
    )

    st.title("Crowler V5")
    st.markdown("**Extração inteligente com aprendizado de padrões + validação paralela ultra-rápida**")
    # URL input
    url = st.text_input("Digite a URL do site:", placeholder="https://exemplo.com")
    
    # Configurações avançadas
    with st.expander("Configurações"):
        col1, col2 = st.columns(2)
        with col1:
            max_detalhes = st.number_input(
                "Produtos para análise detalhada",
                min_value=1,
                value=10,
                step=1,
                help="Quantidade a enviar para a etapa de detalhes (sem limite máximo)."
            )
        with col2:
            max_workers = st.number_input(
                "Threads paralelas",
                min_value=1,
                value=5,
                step=1,
                help="Define quantas requisições simultâneas serão feitas."
            )

    max_detalhes = int(max_detalhes)
    max_workers = int(max_workers)
    
    # Container para mensagens
    message_container = st.empty()
    def show_message(msg):
        message_container.text(msg)
    
    # Seção 1: Extração de Produtos
    st.header("Extração de Produtos")
    
    col_btn1, col_info1 = st.columns([1, 3])
    
    with col_btn1:
        btn_extrair = st.button("Extrair Produtos", type="primary", use_container_width=True)
    
    with col_info1:
        st.info("Extração rápida usando apenas parsing de XML e regex - sem IA")
    
    if btn_extrair:
        if not url:
            st.error("Por favor, digite uma URL válida")
            return
        
        import time
        start_time = time.time()
        
        # UI de progresso
        progress_text = st.empty()
        progress_bar = st.progress(0)
        status_info = st.empty()

        def progress_callback(atual, total, info, tipo):
            if tipo == "coletando":
                status_info.text(f"Sitemap: {info} | {atual} URLs")
                progress_bar.progress(min(0.10, atual / 5000))  # Até 10%
            
            elif tipo == "fase_aprendizado":
                progress_text.text(f"Aprendendo padroes: {atual}/{total}")
                progress_bar.progress(0.10)  # 10%
            
            elif tipo == "aplicando_padrao":
                # Aplicação instantânea do padrão (SEM HTTP)
                progress_text.text(f"Filtrando: {atual}/{total} ({int(atual/total*100)}%)")
                if total and total > 0:
                    frac = 0.10 + (atual / float(total) * 0.90)  # 10-100%
                    progress_bar.progress(frac)
            
            elif tipo == "validando":
                # Validação HTTP (fase de aprendizado ou sem padrão)
                progress_text.text(f"Validando: {atual}/{total} ({int(atual/total*100) if total > 0 else 0}%)")
                if total and total > 0:
                    frac = 0.10 + (atual / float(total) * 0.90)  # 10-100%
                    progress_bar.progress(frac)
            
            elif tipo == "produto_validado":
                status_info.text(f"Produtos: {atual}")

        with st.spinner("Extraindo e validando produtos"):
            resultado_produtos = extrair_produtos_rapido(
                url, show_message, max_produtos=None, progress_callback=progress_callback
            )
        
        progress_bar.progress(1.0)
        status_info.empty()
        progress_text.empty()
        
        elapsed = time.time() - start_time
        
        # Armazena resultado na sessão
        st.session_state.produtos_extraidos = resultado_produtos
        st.session_state.tempo_extracao = elapsed
        st.session_state.pop('detalhes_extraidos', None)
        st.session_state.pop('detalhes_lista', None)
        st.session_state.pop('tempo_detalhes', None)

        st.success(f"Extração concluída em {elapsed:.2f} segundos!")
    
    # Mostra produtos extraídos
    if 'produtos_extraidos' in st.session_state:
        st.subheader("Produtos Encontrados")
        
        produtos = st.session_state.produtos_extraidos
        
        col_result1, col_result2 = st.columns(2)
        with col_result1:
            st.metric("Produtos encontrados", len(produtos))
        with col_result2:
            if 'tempo_extracao' in st.session_state:
                taxa = len(produtos) / st.session_state.tempo_extracao if st.session_state.tempo_extracao > 0 else 0
                st.metric("Produtos/segundo", f"{taxa:.2f}")
        
        if produtos:
            st.dataframe(produtos, use_container_width=True)

            csv_buffer = StringIO()
            fieldnames = sorted(produtos[0].keys())
            writer = csv.DictWriter(csv_buffer, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(produtos)

            st.download_button(
                label="Baixar produtos em CSV",
                data=csv_buffer.getvalue(),
                file_name="produtos_extraidos.csv",
                mime="text/csv"
            )
    
    # Seção 2: Análise Detalhada
    st.header("Análise Detalhada")
    
    col_btn2, col_info2 = st.columns([1, 3])
    
    with col_btn2:
        btn_detalhes = st.button(
            "Extrair Detalhes", 
            type="secondary", 
            use_container_width=True,
            disabled='produtos_extraidos' not in st.session_state
        )
    
    with col_info2:
        if 'produtos_extraidos' in st.session_state:
            st.info(f"Processamento paralelo com {max_workers} threads - extração estruturada sem IA")
        else:
            st.warning("Primeiro extraia os produtos do sitemap")
    
    if btn_detalhes and 'produtos_extraidos' in st.session_state:
        import time
        start_time = time.time()
        
        with st.spinner(f"Analisando produtos com {max_workers} threads..."):
            resultado_detalhes_texto, detalhes_lista = extrair_detalhes_paralelo(
                st.session_state.produtos_extraidos, 
                show_message, 
                max_detalhes,
                max_workers
            )
        
        elapsed = time.time() - start_time
        
        # Armazena resultado na sessão
        st.session_state.detalhes_extraidos = resultado_detalhes_texto
        st.session_state.detalhes_lista = detalhes_lista
        st.session_state.tempo_detalhes = elapsed
        
        st.success(f"Análise concluída em {elapsed:.2f} segundos!")
    
    # Mostra detalhes extraídos
    if 'detalhes_extraidos' in st.session_state:
        st.subheader("Detalhes dos Produtos")
        detalhes_lista = st.session_state.get('detalhes_lista', [])
        
        # Métricas de performance
        col_perf1, col_perf2, col_perf3 = st.columns(3)
        with col_perf1:
            if 'tempo_detalhes' in st.session_state:
                st.metric("Tempo de análise", f"{st.session_state.tempo_detalhes:.2f}s")
        with col_perf2:
            processados = len(detalhes_lista)
            tempo_total = st.session_state.get('tempo_detalhes', 0.0)
            tempo_por_produto = (tempo_total / processados) if processados and tempo_total else 0
            st.metric("Tempo por produto", f"{tempo_por_produto:.2f}s")
        with col_perf3:
            st.metric("Threads utilizadas", max_workers)
        
        if detalhes_lista:
            tabela_detalhes = []
            for item in detalhes_lista:
                estoque_status = item.get('estoque') or item.get('estoque_status')
                if isinstance(estoque_status, str) and estoque_status.startswith('http'):
                    estoque_status = estoque_status.rsplit('/', 1)[-1]
                estoque_qtd = item.get('estoque_quantidade')
                if isinstance(estoque_qtd, float) and estoque_qtd.is_integer():
                    estoque_qtd = int(estoque_qtd)
                
                # Formatação do campo disponível
                disponivel = item.get('disponivel')
                if disponivel is None:
                    disponivel_texto = "Desconhecido"
                elif disponivel is True:
                    disponivel_texto = "Sim"
                elif disponivel is False:
                    disponivel_texto = "Não"
                else:
                    disponivel_texto = str(disponivel)
                
                tabela_detalhes.append({
                    "indice": item.get('indice'),
                    "nome": item.get('nome'),
                    "preco": item.get('preco'),
                    "preco_original": item.get('preco_original'),
                    "moeda": item.get('moeda'),
                    "disponivel": disponivel_texto,
                    "marca": item.get('marca'),
                    "categoria": item.get('categoria'),
                    "subcategoria": item.get('subcategoria'),
                    "categorias_completas": item.get('categorias_completas'),
                    "estoque_status": estoque_status,
                    "estoque_qtd": estoque_qtd,
                    "status_http": item.get('status_http'),
                    "erro": item.get('erro'),
                    "url": item.get('url'),
                    "imagens": ", ".join(item.get('imagens', [])[:3]) if item.get('imagens') else ""
                })

            st.dataframe(tabela_detalhes, use_container_width=True)

            csv_buffer = StringIO()
            fieldnames = list(tabela_detalhes[0].keys())
            writer = csv.DictWriter(csv_buffer, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(tabela_detalhes)

            st.download_button(
                label="Baixar detalhes em CSV",
                data=csv_buffer.getvalue(),
                file_name="detalhes_produtos_v4.csv",
                mime="text/csv"
            )

        with st.expander("Ver texto completo"):
            st.text_area(
                "Detalhes completos dos produtos:", 
                st.session_state.detalhes_extraidos, 
                height=400
            )
    
    # Sidebar com informações
    with st.sidebar:
        st.markdown("### O que mudou na V4:")
        st.markdown("""
        ✅ **Extração rápida**
        - Parsing direto do sitemap
        - Sem categorização por IA
        - Regex otimizado
        
        ✅ **Processamento paralelo**
        - Múltiplas threads simultâneas
        - 5x mais rápido que V3
        - Uso eficiente de CPU
        
        ✅ **Extração estruturada**
        - JSON-LD (schema.org)
        - Meta tags Open Graph
        - Dados estruturados primeiro
        - IA apenas se necessário
        """)
        
        st.markdown("---")
        
        st.markdown("### Como usar:")
        st.markdown("""
        1. Digite a URL do e-commerce
        2. Configure threads (mais = mais rápido)
        3. Extraia produtos rapidamente
        4. Analise detalhes em paralelo
        """)
        
        st.markdown("---")
        
        st.markdown("### Performance:")
        st.markdown("""
        - **V3**: ~2-3s por produto
        - **V4**: ~0.5-1s por produto
        - **Ganho**: 3-5x mais rápido
        """)
        
        st.markdown("---")
        
        st.markdown("### Exemplo de URL:")
        st.code("https://www.gigabarato.com.br")

if __name__ == "__main__":
    main()
