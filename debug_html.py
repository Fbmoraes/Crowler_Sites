"""
🔍 DEBUG - Verificar o que está no HTML retornado
"""

import asyncio
import httpx
from bs4 import BeautifulSoup


async def debug_html():
    url = "https://www.matconcasa.com.br/produto/furadeira-makita-de-impacto-1-2-1010w-220v-hp2070-220v-281700"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers, timeout=15)
        
        print(f"Status: {response.status_code}")
        print(f"Content-Length: {len(response.text)}")
        print()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Verificar H1s
        print("=" * 80)
        print("H1 TAGS:")
        print("=" * 80)
        for i, h1 in enumerate(soup.find_all('h1'), 1):
            print(f"{i}. {h1.get_text(strip=True)}")
        print()
        
        # Verificar se tem Next.js data
        print("=" * 80)
        print("NEXT.JS DATA:")
        print("=" * 80)
        next_data = soup.find('script', id='__NEXT_DATA__')
        if next_data:
            print("✅ Encontrado __NEXT_DATA__!")
            import json
            data = json.loads(next_data.string)
            print(json.dumps(data, indent=2, ensure_ascii=False)[:2000])
            
            # Salvar completo
            with open("next_data.json", "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print()
            print("💾 Dados completos salvos em: next_data.json")
        else:
            print("❌ __NEXT_DATA__ não encontrado")
        print()
        
        # Verificar scripts
        print("=" * 80)
        print("SCRIPTS:")
        print("=" * 80)
        for script in soup.find_all('script')[:5]:
            if script.get('id'):
                print(f"ID: {script.get('id')}")
            if script.get('src'):
                print(f"SRC: {script.get('src')[:80]}")
            else:
                content = script.string or ""
                if content:
                    print(f"Content: {content[:200]}...")
            print()
        
        # Salvar HTML completo para análise
        with open("debug_html.html", "w", encoding="utf-8") as f:
            f.write(response.text)
        print("💾 HTML completo salvo em: debug_html.html")


if __name__ == "__main__":
    asyncio.run(debug_html())
