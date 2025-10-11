import streamlit as st
from extract_linksv3 import extrair_links_do_site  # Certifique-se de importar corretamente

# Configuração da página Streamlit
st.set_page_config(page_title='Chat_Gemini')
st.header('Chat_Gemini')

# Função para exibir mensagens em tempo real
def show_message(message):
    message_placeholder.write(message)

# Input da URL pelo usuário
link_do_site = st.text_input(label='URL do Site', value='https://www.gigabarato.com.br')

# Botão para iniciar a extração
if st.button("Extrair links de categorias"):

    if not link_do_site:
        st.warning("Por favor, insira uma URL válida!")
    else:
        # Cria um placeholder para mensagens dinâmicas
        message_placeholder = st.empty()

        # Chamar a função para extrair os links do site e passar o show_message para exibir as mensagens
        try:
            resultado_final = extrair_links_do_site(link_do_site, show_message)

            # Exibir o resultado final
            st.success("✅ Extração concluída!")
            st.text_area("Links extraídos", resultado_final, height=400)

            # Salvar o resultado no arquivo
            with open("links_extraidos.txt", "w", encoding="utf-8") as f:
                f.write(resultado_final)

        except Exception as e:
            st.error(f"Erro durante a extração: {e}")
