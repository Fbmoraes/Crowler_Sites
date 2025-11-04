"""
Extract Details V7 - VERSÃO FINAL COM NETWORKIDLE
Extração de detalhes de produtos usando Crawlee + Playwright
Estratégia: networkidle + wait extra para React Server Components hidratar
"""

import asyncio
import json
from crawlee.crawlers import PlaywrightCrawler, PlaywrightCrawlingContext

# URL de teste
urls_teste = [
    "https://www.matconcasa.com.br/produto/ducha-hydra-optima-8-temperaturas-5500w-127v-dpop-8-551br-362905"
]

# Armazenamento global dos resultados
resultados = []


async def router_handler(context: PlaywrightCrawlingContext):
    """Handler principal que extrai detalhes do produto"""
    
    page = context.page
    url = context.request.url
    
    print(f"Carregando: {url}")
    
    # ========== AGUARDAR NETWORK IDLE + REACT HYDRATION ==========
    try:
        await page.wait_for_load_state('networkidle', timeout=30000)
        print(f"  ✅ Network idle")
    except:
        print(f"  ⚠️  Timeout networkidle")
    
    # Aguardar React hidratar
    await page.wait_for_timeout(3000)
    
    # ========== EXTRAIR DADOS USANDO SELETORES SIMPLES ==========
    dados = {
        'url': url,
        'nome': None,
        'preco': None,
        'preco_original': None,
        'marca': None,
        'imagens': [],
        'disponivel': None
    }
    
    try:
        # Nome do produto (procurar h1 que contenha o nome real do produto)
        nome_elem = await page.evaluate('''
            () => {
                // Estratégia 1: Procurar h1 que contenha características de produto
                // (números, voltagem, modelo, etc)
                const h1s = Array.from(document.querySelectorAll('h1'));
                
                // Filtrar h1s que parecem ser nome de produto (contém números, modelo, etc)
                const productH1s = h1s.filter(h1 => {
                    const text = h1.textContent;
                    // Deve ter números E ser maior que 20 caracteres
                    return /\d/.test(text) && text.length > 20 && 
                           // Não deve ser texto genérico de vendedor/parceria
                           !text.includes('Vendido e Entregue') &&
                           !text.includes('Parceria');
                });
                
                if (productH1s.length > 0) {
                    // Pegar o mais longo
                    return productH1s.reduce((longest, current) => {
                        return current.textContent.length > longest.textContent.length ? 
                               current : longest;
                    }).textContent.trim();
                }
                
                // Estratégia 2: Se não encontrou, pegar do title da página
                const title = document.title;
                // Remover parte genérica do site
                const cleaned = title.split('|').pop().trim();
                if (cleaned && cleaned.length > 10) {
                    return cleaned;
                }
                
                // Estratégia 3: Última tentativa - pegar o h1 mais longo mesmo
                if (h1s.length > 0) {
                    return h1s.reduce((longest, current) => {
                        return current.textContent.length > longest.textContent.length ? 
                               current : longest;
                    }, h1s[0]).textContent.trim();
                }
                
                return null;
            }
        ''')
        if nome_elem:
            dados['nome'] = nome_elem
            print(f"  Nome: {dados['nome']}")
        
        # Preço principal e original (procurar em contexto específico)
        precos = await page.evaluate(r'''
            () => {
                const bodyText = document.body.innerText;
                
                // Procurar padrão: "de R$ XXX,XX" seguido de "R$ YYY,YY"
                // Isso indica preço original e preço atual
                const precoComDesconto = bodyText.match(/de\s+R\$\s*([\d.,]+).*?R\$\s*([\d.,]+)/is);
                if (precoComDesconto) {
                    return {
                        original: precoComDesconto[1],
                        atual: precoComDesconto[2]
                    };
                }
                
                // Se não encontrou desconto, procurar apenas "R$ XXX,XX" mais próximo do título
                // Pegar o maior valor (geralmente o preço principal)
                const todosPrecos = Array.from(bodyText.matchAll(/R\$\s*([\d.,]+)/g))
                    .map(m => m[1])
                    .filter(p => {
                        // Filtrar valores muito pequenos (centavos) ou muito grandes (fora do comum)
                        const valor = parseFloat(p.replace('.', '').replace(',', '.'));
                        return valor >= 10 && valor <= 100000;
                    });
                
                if (todosPrecos.length > 0) {
                    // Pegar o primeiro preço válido (geralmente é o do produto)
                    return {
                        original: null,
                        atual: todosPrecos[0]
                    };
                }
                
                return { original: null, atual: null };
            }
        ''')
        
        if precos['atual']:
            dados['preco'] = precos['atual']
            print(f"  Preço: R$ {precos['atual']}")
        
        if precos['original']:
            dados['preco_original'] = precos['original']
            print(f"  De: R$ {precos['original']}")
        
        # Imagens
        imagens = await page.evaluate('''
            () => {
                const imgs = Array.from(document.querySelectorAll('img'));
                return imgs
                    .map(img => img.src)
                    .filter(src => src && src.includes('http'))
                    .slice(0, 5);  // Primeiras 5
            }
        ''')
        dados['imagens'] = imagens
        print(f"  Imagens: {len(imagens)} encontradas")
        
        # Disponibilidade
        disponivel_text = await page.evaluate('''
            () => {
                const text = document.body.innerText.toLowerCase();
                if (text.includes('indisponível') || text.includes('out of stock')) return false;
                if (text.includes('disponível') || text.includes('in stock') || text.includes('em estoque')) return true;
                return null;
            }
        ''')
        dados['disponivel'] = disponivel_text
        print(f"  Disponível: {disponivel_text}")
        
    except Exception as e:
        print(f"  ❌ Erro na extração: {e}")
        dados['erro'] = str(e)
    
    # Armazenar resultado
    resultados.append(dados)
    print(f"  ✅ Extração concluída!")


async def main():
    """Função principal"""
    print("=" * 80)
    print("=== Extract Details V7 - FINAL ===")
    print("=" * 80)
    print()
    
    print(f"🤖 Extraindo {len(urls_teste)} produto(s)...\n")
    
    # Criar crawler
    from datetime import timedelta
    crawler = PlaywrightCrawler(
        request_handler=router_handler,
        headless=True,
        browser_type='chromium',
        max_request_retries=1,
        request_handler_timeout=timedelta(seconds=60)  # 60 segundos de timeout
    )
    
    # Executar
    await crawler.run(urls_teste)
    
    # Exibir resultados
    print()
    print("=" * 80)
    print("RESULTADOS:")
    print("=" * 80)
    
    for idx, resultado in enumerate(resultados, 1):
        print(f"\nProduto {idx}/{len(resultados)}")
        print(f"URL: {resultado['url']}")
        print(f"Nome: {resultado.get('nome', 'N/A')}")
        print(f"Preço: R$ {resultado.get('preco', 'N/A')}")
        if resultado.get('preco_original'):
            print(f"De: R$ {resultado['preco_original']}")
        print(f"Disponível: {resultado.get('disponivel', 'N/A')}")
        print(f"Imagens: {len(resultado.get('imagens', []))} encontradas")
    
    # Salvar JSON
    with open('resultados_v7.json', 'w', encoding='utf-8') as f:
        json.dump(resultados, f, ensure_ascii=False, indent=2)
    
    print()
    print(f"💾 Resultados salvos em: resultados_v7.json")
    print("=" * 80)


if __name__ == '__main__':
    asyncio.run(main())
