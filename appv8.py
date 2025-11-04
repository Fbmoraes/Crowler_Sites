"""
CROWLER V8 - Ultra-Simplificado
Foco: Código mínimo, máxima funcionalidade
"""
import streamlit as st
import csv
from io import StringIO
from extract_linksv8 import extrair_produtos
from extract_detailsv8 import extrair_detalhes_paralelo

def main():
    st.set_page_config(page_title="Crowler V8", layout="wide")
    
    st.title("🚀 Crowler V8 - Simplificado")
    st.markdown("**Discovery por navegação + Pattern Learning + Extração paralela**")
    
    # Input
    url = st.text_input("URL do site:", placeholder="https://exemplo.com.br")
    
    # Configurações
    col1, col2 = st.columns(2)
    with col1:
        max_produtos = st.number_input("Produtos para extrair (0 = todos)", 0, 10000, 0, 50)
    with col2:
        max_workers = st.number_input("Threads paralelas", 1, 40, 20, 5)
    
    # Converte 0 para None (sem limite)
    max_produtos = None if max_produtos == 0 else max_produtos
    
    # Fase 1: Links
    st.header("Fase 1: Extração de Links")
    
    if st.button("🔍 Extrair Produtos", type="primary", use_container_width=True):
        if not url:
            st.error("Digite uma URL válida")
            return
        
        status = st.empty()
        def mostrar(msg):
            status.text(msg)
        
        with st.spinner("Extraindo..."):
            produtos = extrair_produtos(url, mostrar, max_produtos)
        
        if produtos:
            st.session_state.produtos = produtos
            st.success(f"✅ {len(produtos)} produtos encontrados!")
            st.dataframe(produtos, use_container_width=True)
            
            # Download
            csv_buffer = StringIO()
            writer = csv.DictWriter(csv_buffer, fieldnames=['nome', 'url'])
            writer.writeheader()
            writer.writerows(produtos)
            
            st.download_button(
                "📥 Baixar CSV",
                csv_buffer.getvalue(),
                "produtos.csv",
                "text/csv"
            )
        else:
            st.warning("Nenhum produto encontrado")
    
    # Fase 2: Detalhes
    if 'produtos' in st.session_state:
        st.header("Fase 2: Extração de Detalhes")
        
        total_produtos = len(st.session_state.produtos)
        produtos_processar = max_produtos if max_produtos else total_produtos
        
        st.info(f"💪 ThreadPool: {max_workers} threads | {produtos_processar} produtos | JSON-LD + OpenGraph + HTML")
        
        if st.button("📊 Extrair Detalhes", use_container_width=True):
            status = st.empty()
            def mostrar(msg):
                status.text(msg)
            
            with st.spinner("Processando..."):
                texto, detalhes = extrair_detalhes_paralelo(
                    st.session_state.produtos,
                    mostrar,
                    produtos_processar,
                    max_workers
                )
            
            st.session_state.detalhes = detalhes
            st.session_state.texto = texto
            
            st.success(f"✅ {len(detalhes)} produtos processados!")
            
            # Mostra resultados
            st.dataframe(detalhes, use_container_width=True)
            
            # Download
            if detalhes:
                csv_buffer = StringIO()
                fieldnames = list(set().union(*(d.keys() for d in detalhes)))
                writer = csv.DictWriter(csv_buffer, fieldnames=fieldnames, extrasaction='ignore')
                writer.writeheader()
                writer.writerows(detalhes)
                
                st.download_button(
                    "📥 Baixar Detalhes CSV",
                    csv_buffer.getvalue(),
                    "detalhes.csv",
                    "text/csv"
                )
            
            with st.expander("Ver texto completo"):
                st.text_area("Resultado:", texto, height=400)
    
    # Sidebar
    with st.sidebar:
        st.markdown("### V8: Simplificado")
        st.markdown("""
        **Fase 1: Links**
        - Sitemap (< 5k URLs): Pattern Learning
        - Sitemap (> 5k URLs): Navegação por categorias
        - Sem sitemap: Navegação por categorias
        
        **Fase 2: Detalhes**
        - ThreadPool (20-40 threads)
        - JSON-LD → OpenGraph → HTML
        - Retry automático (3x)
        
        **Performance:**
        - Sites pequenos: ~10-30s
        - Sites médios: ~1-2min
        - Sites grandes: ~2-5min
        """)
        
        st.markdown("---")
        st.markdown("**Testado:**")
        st.code("gigabarato.com.br")
        st.code("matconcasa.com.br")

if __name__ == "__main__":
    main()
