import httpx

urls_teste = [
    "https://sacada.com.br",
    "https://www.sacada.com.br",
    "http://sacada.com.br",
    "http://www.sacada.com.br",
]

for url in urls_teste:
    try:
        print(f"Testando: {url}")
        r = httpx.get(url, follow_redirects=True, timeout=10)
        print(f"  ✅ Status: {r.status_code}")
        print(f"  URL final: {r.url}")
        break
    except Exception as e:
        print(f"  ❌ Erro: {e}")
