import httpx
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import re
from urllib.parse import urlparse

def extrair_links_do_site(link_do_site, show_message):
    show_message("Iniciando a extração dos links...")
    resp = httpx.get(link_do_site, timeout=30)
    resp.raise_for_status()
    html = resp.text
    with open("agua.txt", "w", encoding="utf-8") as f:
        f.write(html)
    soup = BeautifulSoup(html, "html.parser")

    base_netloc = urlparse(link_do_site).netloc
    patterns = ("categoria", "categorias", "/c/", "/cat/", "category", "produto", "produtos", "ver-tudo", "ver%20mais")

    anchors = soup.find_all("a", href=True)
    found = []
    for a in anchors:
        href = a["href"].strip()
        href_l = href.lower()
        abs_url = urljoin(link_do_site, href)
        if urlparse(abs_url).netloc != base_netloc:
            continue  # apenas links internos

        text = (a.get_text() or "").strip().lower()

        # condição: está dentro de nav/header/aside/footer?
        in_nav = any(p.name in ("nav", "header", "aside", "footer") for p in a.parents)

        # condição: classes/ids com palavras-chave
        cls_id = " ".join(a.get("class", []) + [a.get("id") or ""])
        cls_match = bool(re.search(r"(nav|menu|categoria|category|cat|sidebar|list|menu__|menu-)", cls_id, re.I))

        # condição: href/text contem padrões de categoria
        pattern_match = any(p in href_l or p in text for p in patterns)

        if in_nav or cls_match or pattern_match:
            found.append(abs_url)

    # remove duplicados preservando ordem
    seen = set()
    out = []
    for u in found:
        if u not in seen:
            seen.add(u)
            out.append(u)

    resultado = "\n".join(out)
    with open("links_extraidos.txt", "w", encoding="utf-8") as f:
        f.write(resultado)

    show_message("✅ Extração concluída!")
    return resultado
