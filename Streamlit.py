import httpx
from langchain_google_genai import GoogleGenerativeAI
from dotenv import load_dotenv
from bs4 import BeautifulSoup
import streamlit as st

# Configuração da página Streamlit
st.set_page_config(page_title='Chat_Gemini')
st.header('Chat_Gemini')

# Input da URL pelo usuário
link_do_site = st.text_input(label='URL do Site', value='https://www.gigabarato.com.br')

# Botão para iniciar a extração
if st.button("Extrair links de categorias"):

    # Verificar se a URL foi inserida
    if not link_do_site:
        st.warning("Por favor, insira uma URL válida!")
    else:
        # Carregar variáveis de ambiente
        load_dotenv()

        # Inicializar o modelo Gemini Flash
        llm = GoogleGenerativeAI(model="gemini-2.5-flash")

        # Obter o HTML do site
        try:
            response = httpx.get(link_do_site, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
        except Exception as e:
            st.error(f"Erro ao acessar o site: {e}")
            st.stop()

        # Salvar HTML em arquivo (opcional)
        with open("agua.txt", "w", encoding="utf-8") as arq:
            arq.write(soup.prettify())

        # Converter HTML em string
        lista_links = soup.prettify()

        # Definir tamanho máximo por chunk (aprox. limite seguro)
        MAX_CHARS = 245000

        # Função para dividir o HTML em partes menores
        def dividir_html_em_chunks(texto, tamanho_chunk):
            return [texto[i : i + tamanho_chunk] for i in range(0, len(texto), tamanho_chunk)]

        # Dividir HTML em partes se for muito grande
        html_chunks = dividir_html_em_chunks(lista_links, MAX_CHARS)
        st.write(f"🔹 Total de partes a serem processadas: {len(html_chunks)}")

        # Lista para armazenar os resultados de cada parte
        resultados = []

        # Loop sobre cada parte e chamar o modelo
        for i, chunk in enumerate(html_chunks, start=1):
            st.write(f"🚀 Processando parte {i}/{len(html_chunks)}...")

            prompt = f"""
Analise esse HTML e localize o menu de navegação.
Retorne **somente os links** das páginas de categoria e subcategoria de produtos.
Os links podem estar nos formatos:
- https://sitedecompra.com.br/categoria
- https://sitedecompra.com.br/categoria/
- https://sitedecompra.com.br/categoria/subcategoria
- Ou relativos como /categoria/ ou /categoria/subcategoria

Quando o link for relativo, converta para URL completa usando o domínio base:
{link_do_site}

HTML:
{chunk}
"""

            try:
                response = llm.invoke(prompt)
                resultados.append(response)
            except Exception as e:
                st.warning(f"⚠️ Erro ao processar parte {i}: {e}")

        # Concatenar os resultados finais
        resultado_final = "\n".join([r for r in resultados if r])

        # Exibir e salvar resultado
        st.success("✅ Extração concluída!")
        st.text_area("Links extraídos", resultado_final, height=400)

        with open("links_extraidos.txt", "w", encoding="utf-8") as f:
            f.write(resultado_final)
