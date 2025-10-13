"""
Versão 4 - Simplificada: encontra 1 sitemap XML (ou .gz), parseia e retorna URLs de produto.
Objetivo: simples e rápido — procurar um xml e ir atrás do que tá naquele .xml.
"""

import httpx
import xml.etree.ElementTree as ET
import re
import gzip
import random
import time
from io import BytesIO
from urllib.parse import urljoin, urlparse

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}

RETRY_STATUS_CODES = {408, 425, 429, 500, 502, 503, 504}


def _http_get(url, *, timeout=15, referer=None, max_retries=3):
    headers = DEFAULT_HEADERS.copy()
    if referer:
        headers["Referer"] = referer

    for attempt in range(1, max_retries + 1):
        try:
            resp = httpx.get(url, headers=headers, timeout=timeout, follow_redirects=True)
            if resp.status_code in RETRY_STATUS_CODES:
                time.sleep(min(2.0 * attempt, 6) + random.random() * 0.2)
                continue
            resp.raise_for_status()
            return resp
        except Exception:
            time.sleep(min(1.0 * attempt, 4) + random.random() * 0.2)
    return None


def _get_first_sitemap(base_url):
    """Retorna a primeira URL de sitemap válida (robots.txt ou candidatos comuns)."""
    try:
        robots_url = urljoin(base_url, "/robots.txt")
        r = _http_get(robots_url, timeout=8)
        if r and r.status_code == 200 and r.text:
            for line in r.text.splitlines():
                line_s = line.strip()
                if not line_s or line_s.startswith("#"):
                    continue
                m = re.search(r'sitemap:\s*(\S+)', line_s, re.IGNORECASE)
                if m:
                    sitemap = m.group(1).strip()
                    # se for relativo, converte
                    if sitemap.startswith("/"):
                        sitemap = urljoin(base_url, sitemap)
                    return sitemap
    except Exception:
        pass

    # candidatos comuns
    candidates = [
        urljoin(base_url, "/sitemap.xml"),
        urljoin(base_url, "/sitemap_index.xml"),
        urljoin(base_url, "/sitemap.xml.gz"),
        urljoin(base_url, "/sitemap-index.xml"),
    ]
    for cand in candidates:
        r = _http_get(cand, timeout=8)
        if r and r.status_code == 200 and r.content:
            return cand

    return None


def _parse_single_sitemap(sitemap_url):
    """Faz download e retorna lista de URLs encontradas no sitemap (apenas esse sitemap)."""
    r = _http_get(sitemap_url, timeout=20)
    if not r or r.status_code != 200 or not r.content:
        return []

    content = r.content

    # detecta gzip por headers ou magic bytes
    content_encoding = (r.headers.get("Content-Encoding") or "").lower()
    is_gz = "gzip" in content_encoding or (len(content) >= 2 and content[0:2] == b"\x1f\x8b")
    if is_gz:
        try:
            content = gzip.decompress(content)
        except Exception:
            try:
                with gzip.GzipFile(fileobj=BytesIO(content)) as gz:
                    content = gz.read()
            except Exception:
                return []

    # tenta parse XML (bytes ok)
    try:
        root = ET.fromstring(content)
    except Exception:
        try:
            text = content.decode("utf-8", errors="replace")
            root = ET.fromstring(text)
        except Exception:
            return []

    urls = []
    # namespace-aware first
    ns = {"ns": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    for loc in root.findall(".//ns:loc", ns):
        if loc.text:
            urls.append(loc.text.strip())

    if not urls:
        for loc in root.findall(".//loc"):
            if loc.text:
                urls.append(loc.text.strip())

    # if this is a sitemap index (contains other sitemaps), try to expand first level only
    sitemap_entries = [u for u in urls if u.lower().endswith((".xml", ".xml.gz")) and ("sitemap" in u.lower() or "/sitemap" in u.lower())]
    if sitemap_entries:
        # prefer first child sitemap: parse it and return its locs
        child = sitemap_entries[0]
        child_urls = _parse_single_sitemap(child)
        if child_urls:
            return child_urls

    return urls


def _is_product_url(url):
    """Identificador simples de URL de produto (mantido como heurística)."""
    url_lower = url.lower()
    if re.search(r'/produtos?/|/product[s]?/|/p/|-\d{3,}', url_lower):
        # filter out obvious non-product end-points
        if re.search(r'/(categoria|category|blog|contato|contact|carrinho|cart|busca|search|login|account)/', url_lower):
            return False
        # ignore root-only
        if re.match(r'^https?://[^/]+/?$', url_lower):
            return False
        return True
    return False


def extrair_produtos_rapido(base_url, show_message, max_produtos=None):
    """
    Versão simples: encontra o primeiro sitemap XML e retorna as URLs de produto encontradas nele.
    """
    show_message("Localizando sitemap...")
    sitemap = _get_first_sitemap(base_url)
    if not sitemap:
        show_message("Nenhum sitemap encontrado via robots ou candidatos. Abortando.")
        return []

    show_message(f"Sitemap encontrado: {sitemap}")
    urls = _parse_single_sitemap(sitemap)
    show_message(f"URLs no sitemap: {len(urls)}")

    produtos = []
    seen = set()
    for u in urls:
        u_clean = u.split('?')[0].rstrip('/')
        if u_clean in seen:
            continue
        seen.add(u_clean)
        if _is_product_url(u_clean):
            produtos.append(u_clean)
            if max_produtos and len(produtos) >= max_produtos:
                break

    show_message(f"Produtos detectados: {len(produtos)}")
    # formata retorno simples
    return [{"url": p, "nome": p.rstrip('/').split('/')[-1].replace('-', ' ').title()} for p in produtos]
