import streamlit as st
from extract_linksv3 import extrair_links_do_site  # Certifique-se de importar corretamente
from extract_price import extrair_precos_produtos  # Importa nova funcionalidade de preços

# Configuração da página Streamlit
st.set_page_config(page_title='Chat_Gemini V2')
st.header('Chat_Gemini V2')

# Função para exibir mensagens em tempo real
def show_message(message):
    message_placeholder.write(message)

# Input da URL pelo usuário
link_do_site = st.text_input(label='URL do Site', value='https://www.gigabarato.com.br')

# Primeira seção - Extrair links de categorias
st.subheader('1. Extração de Produtos')
if st.button("Extrair links de categorias"):
    # Placeholder para mensagens
    message_placeholder = st.empty()
    
    # Executa a extração
    resultado = extrair_links_do_site(link_do_site, show_message)
    
    # Salva resultado na sessão para usar depois
    st.session_state['produtos_extraidos'] = resultado
    
    # Exibe resultado na área de texto
    if resultado:
        st.text_area(label='Links extraídos', value=resultado, height=300)
        st.success("✅ Extração de produtos concluída!")
    else:
        st.error("❌ Nenhum produto encontrado")

# Segunda seção - Extrair preços
st.subheader('2. Extração de Preços')

# Verifica se já tem produtos extraídos
if 'produtos_extraidos' in st.session_state and st.session_state['produtos_extraidos']:
    st.info(f"📦 Produtos disponíveis para extração de preços")
    
    if st.button("Extrair preços dos produtos"):
        # Placeholder para mensagens
        message_placeholder2 = st.empty()
        
        def show_message_precos(message):
            message_placeholder2.write(message)
        
        # Executa extração de preços
        resultado_precos = extrair_precos_produtos(st.session_state['produtos_extraidos'], show_message_precos)
        
        # Exibe resultado na área de texto
        st.text_area(label='Preços extraídos', value=resultado_precos, height=400)
        st.success("✅ Extração de preços concluída!")
        
else:
    st.warning("⚠️ Execute primeiro a extração de produtos para poder extrair preços")

# Informações adicionais
st.sidebar.markdown("""
## Como usar:
1. **Digite a URL** do site que deseja analisar
2. **Clique em "Extrair links de categorias"** para encontrar todos os produtos
3. **Clique em "Extrair preços dos produtos"** para obter os preços dos produtos encontrados

## Status:
- ✅ Extração de produtos (via sitemap)
- 🔄 Extração de preços (em desenvolvimento)
""")