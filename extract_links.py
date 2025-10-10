import httpx
from langchain_google_genai import GoogleGenerativeAI
from dotenv import load_dotenv
from bs4 import BeautifulSoup

# Carregar variáveis de ambiente
load_dotenv()

# Inicializar o modelo Gemini Flash
llm = GoogleGenerativeAI(model="gemini-2.5-flash")

# Função principal para extrair links
def extrair_links_do_site(link_do_site, show_message):
    # Exibindo a mensagem de início
    show_message("Iniciando a extração dos links...")

    # Obter o HTML do site
    try:
        response = httpx.get(link_do_site, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
    except Exception as e:
        show_message(f"Erro ao acessar o site: {e}")
        return f"Erro ao acessar o site: {e}"

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
    show_message(f"🔹 Total de partes a serem processadas: {len(html_chunks)}")

    # Lista para armazenar os resultados de cada parte
    resultados = []

    # Loop sobre cada parte e chamar o modelo
    for i, chunk in enumerate(html_chunks, start=1):
        show_message(f"🚀 Processando parte {i}/{len(html_chunks)}...")

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
            show_message(f"⚠️ Erro ao processar parte {i}: {e}")
            continue

    # Concatenar os resultados finais
    resultado_final = "\n".join([r for r in resultados if r])

    # Exibir e salvar resultado
    with open("links_extraidos.txt", "w", encoding="utf-8") as f:
        f.write(resultado_final)

    show_message("✅ Extração concluída!")
    return resultado_final
