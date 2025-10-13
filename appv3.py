import streamlit as st
from extract_linksv3 import extrair_links_do_site
from extract_details import extrair_detalhes_produtos

def main():
    st.set_page_config(
        page_title="Crowler de Sites - Extração Completa", 
        page_icon="�",
        layout="wide"
    )
    
    st.title("Crowler de Sites - Extração Completa de Produtos")
    st.markdown("**Extrai produtos de sitemaps e obtém todos os detalhes de cada produto**")
    
    # URL input
    url = st.text_input("Digite a URL do site:", placeholder="https://exemplo.com")
    
    # Configurações
    col1, col2 = st.columns(2)
    with col1:
        max_produtos_extrair = st.number_input("Máximo de produtos para extrair", min_value=1, max_value=50, value=10)
    with col2:
        max_detalhes = st.number_input("Máximo de produtos para análise detalhada", min_value=1, max_value=10, value=3)
    
    # Container para mensagens
    message_container = st.empty()
    def show_message(msg):
        message_container.text(msg)
    
    # Seção 1: Extração de Produtos
    st.header("Passo 1: Extração de Produtos do Sitemap")
    
    if st.button("Extrair Produtos do Sitemap", type="primary"):
        if not url:
            st.error("Por favor, digite uma URL válida")
            return
        
        with st.spinner("Extraindo produtos..."):
            resultado_produtos = extrair_links_do_site(url, show_message)
        
        # Armazena resultado na sessão
        st.session_state.produtos_extraidos = resultado_produtos
        st.success("Extração de produtos concluída!")
    
    # Mostra produtos extraídos
    if 'produtos_extraidos' in st.session_state:
        st.subheader("Produtos Encontrados")
        
        # Conta produtos
        linhas = st.session_state.produtos_extraidos.strip().split('\n')
        urls_produtos = [linha for linha in linhas if linha.strip().startswith('http') and '/produto' in linha]
        
        st.info(f"**{len(urls_produtos)} produtos encontrados**")
        
        # Mostra preview dos produtos
        with st.expander("Visualizar Lista de Produtos"):
            st.text_area("Produtos extraídos:", st.session_state.produtos_extraidos, height=200)
    
    # Seção 2: Extração de Detalhes
    st.header("Passo 2: Análise Detalhada dos Produtos")
    
    if 'produtos_extraidos' in st.session_state:
        if st.button("Extrair Detalhes Completos", type="secondary"):
            with st.spinner("Analisando produtos em detalhes..."):
                resultado_detalhes = extrair_detalhes_produtos(
                    st.session_state.produtos_extraidos, 
                    show_message, 
                    max_detalhes
                )
            
            # Armazena resultado na sessão
            st.session_state.detalhes_extraidos = resultado_detalhes
            st.success("Análise detalhada concluída!")
    else:
        st.info("Primeiro extraia os produtos do sitemap")
    
    # Mostra detalhes extraídos
    if 'detalhes_extraidos' in st.session_state:
        st.subheader("Detalhes dos Produtos")
        
        # Área de resultado com scroll
        st.text_area(
            "Detalhes completos dos produtos:", 
            st.session_state.detalhes_extraidos, 
            height=400
        )
        
        # Botão de download
        st.download_button(
            label="Baixar Detalhes Completos",
            data=st.session_state.detalhes_extraidos,
            file_name="detalhes_produtos_completos.txt",
            mime="text/plain"
        )
    
    # Sidebar com informações
    with st.sidebar:
        st.markdown("### Como usar:")
        st.markdown("""
        1. **Digite a URL** do site de e-commerce
        2. **Configure os limites** de extração
        3. **Extraia produtos** do sitemap
        4. **Analise detalhes** dos produtos encontrados
        """)
        
        st.markdown("### Dados extraídos:")
        st.markdown("""
        - **Nome** do produto
        - **Preço** atual
        - **Categoria** e breadcrumb
        - **Descrição** completa
        - **Imagens** do produto
        - **Estoque** disponível
        - **Especificações** técnicas
        - **Marca** (via Ollama)
        - **Resumo** (via Ollama)
        """)
        
        st.markdown("### Exemplo de URL:")
        st.code("https://www.gigabarato.com.br")
        
        # Status do Ollama
        st.markdown("### Status do Ollama:")
        try:
            import httpx
            response = httpx.get("http://localhost:11434/api/tags", timeout=5)
            if response.status_code == 200:
                st.success("Ollama ativo")
            else:
                st.error("Ollama inativo")
        except:
            st.error("Ollama não encontrado")

if __name__ == "__main__":
    main()