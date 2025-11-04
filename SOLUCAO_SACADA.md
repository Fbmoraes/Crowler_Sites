# Sacada - Solução Encontrada

## Resumo
**Site**: https://www.sacada.com  
**Plataforma**: VTEX + React/Apollo (JavaScript-heavy SPA)  
**Solução**: Extração via Apollo Cache (GraphQL normalizado)  
**Status**: ✅ **FUNCIONANDO** - 5/5 produtos testados com sucesso

---

## Problema Identificado

### 1. Site JavaScript-Heavy
- HTML inicial retorna apenas **placeholder**: "Loading interface..."
- Conteúdo real carregado por **React após renderização**
- **BeautifulSoup não consegue** ver dados (requer JavaScript)

### 2. Sem JSON-LD
- Diferente de sites VTEX tradicionais
- **0 scripts `application/ld+json`**
- Dados não estão em formato estruturado padrão

### 3. Sitemaps com Produtos Inativos
- **product-0.xml**: 1000 URLs, mas produtos **ANTIGOS/INATIVOS** ❌
  - Título genérico: "Sacada"
  - Sem dados de preço/categoria
  - Apollo Cache vazio ou incompleto
  
- **product-1.xml**: 1000 URLs, produtos **ATIVOS** ✅
- **product-2.xml**: 1000 URLs, produtos **ATIVOS** ✅
- **product-3.xml**: 268 URLs, produtos **ATIVOS** ✅

**Total**: ~2268 produtos ATIVOS (sitemaps 1, 2, 3)

---

## Solução: Apollo Cache

### Como Funciona

1. **Apollo Cache** = Cache do cliente GraphQL (React Apollo)
2. Formato: **GraphQL normalizado** (referências entre objetos)
3. Localização: Script JavaScript no HTML (não tem `type=`)
4. Contém **TODOS os dados** do produto

### Estrutura do Cache

```javascript
{
  // Produto principal
  "Product:blusa-malha-amarracao-01041624-0002": {
    "productName": "Blusa Malha Amarração - Preto",
    "productId": "724515",
    "brand": "Sacada",
    "description": "...",
    "priceRange": {
      "type": "id",
      "id": "$Product:blusa-malha-amarracao-01041624-0002.priceRange"  // Referência
    },
    "items": [
      { "type": "id", "id": "Product:blusa-malha-amarracao-01041624-0002.items.0" }
    ]
  },
  
  // Preços (referenciados)
  "$Product:blusa-malha-amarracao-01041624-0002.priceRange": {
    "sellingPrice": { "id": "...", ... },
    "listPrice": { "id": "...", ... }
  },
  
  "$Product:blusa-malha-amarracao-01041624-0002.priceRange.sellingPrice": {
    "highPrice": 98,
    "lowPrice": 98
  },
  
  "$Product:blusa-malha-amarracao-01041624-0002.priceRange.listPrice": {
    "highPrice": 248,
    "lowPrice": 248
  }
}
```

### Processo de Extração

1. **Localizar script** com Apollo Cache (contém `"Product:"`)
2. **Parse JSON** do script
3. **Encontrar chave** do produto (`Product:slug-do-produto`)
4. **Resolver referências** GraphQL (seguir `id` para outras chaves)
5. **Extrair dados**:
   - Nome: direto
   - Marca: direto
   - Preço: resolver `priceRange → sellingPrice → lowPrice`
   - Preço Original: resolver `priceRange → listPrice → lowPrice`
   - Categoria: parsear `categories.json`
   - SKU: resolver `items[0] → itemId`

---

## Implementação

### Arquivo: `extract_sacada.py`

```python
def extrair_apollo_cache(html: str) -> Optional[Dict]:
    """Extrai dados do Apollo Cache no HTML"""
    soup = BeautifulSoup(html, 'html.parser')
    scripts = [s for s in soup.find_all('script') if s.text and 'Product:' in s.text]
    if scripts:
        return json.loads(scripts[0].text)
    return None

def resolver_referencia(cache: Dict, ref: any) -> any:
    """Resolve referências do GraphQL normalizado"""
    if isinstance(ref, dict) and 'id' in ref:
        return cache.get(ref['id'], ref)
    return ref

def extrair_produto_sacada(url: str) -> Dict:
    # 1. Fazer requisição
    resp = httpx.get(url, timeout=15, follow_redirects=True)
    
    # 2. Extrair Apollo Cache
    cache = extrair_apollo_cache(resp.text)
    
    # 3. Encontrar produto
    product_key = [k for k in cache.keys() if k.startswith('Product:') and '.' not in k][0]
    product = cache[product_key]
    
    # 4. Extrair dados
    nome = product.get('productName')
    marca = product.get('brand')
    
    # 5. Resolver referências de preço
    price_range = resolver_referencia(cache, product['priceRange'])
    selling_data = resolver_referencia(cache, price_range['sellingPrice'])
    preco = selling_data['lowPrice']
    
    return {'nome': nome, 'preco': preco, 'marca': marca, ...}
```

### Uso

```python
from extract_sacada import extrair_produto_sacada

resultado = extrair_produto_sacada('https://www.sacada.com/produto/p')
print(resultado)
# {
#   'nome': 'Blusa Malha Amarração - Preto',
#   'preco': 'R$ 98',
#   'preco_original': 'R$ 248',
#   'marca': 'Sacada',
#   'categoria': 'Blusas e Camisas',
#   'sku': '4078401'
# }
```

---

## Resultados dos Testes

### Teste Individual
```
URL: https://www.sacada.com/blusa-malha-amarracao-01041624-0002/p
✓ Nome: Blusa Malha Amarração - Preto
✓ Preço: R$ 98
✓ Preço Original: R$ 248
✓ Marca: Sacada
✓ Categoria: Blusas e Camisas
✓ SKU: 4078401
```

### Teste em Lote (Sitemap product-1)
```
1. blusa-malha-amarracao      ✓ R$ 98
2. regata-malha-canelada      ✓ R$ 98
3. blusa-malha-ombro-so       ✓ R$ 88
4. vestido-malha-alcas        ✓ R$ 218
5. regata-malha-recorte-alto  ✓ R$ 58

Taxa de sucesso: 5/5 (100%)
```

---

## Lições Aprendidas

### 1. VTEX Pode Ser JavaScript-Heavy
- **Nem todo site VTEX é igual**
- Alguns usam **React/SSR** (Server-Side Rendering) → BeautifulSoup funciona
- Outros usam **React/SPA** (Single Page App) → Precisa Apollo Cache

### 2. Apollo Cache = Tesouro Escondido
- **Alternativa ao Selenium/Playwright**
- Dados **já estão no HTML** (só precisam ser extraídos)
- Muito **mais rápido** que renderizar JavaScript
- Formato **GraphQL normalizado** (requer resolver referências)

### 3. Sitemaps Podem Ter Produtos Inativos
- **Validar qualidade** dos produtos por sitemap
- Sitemap 0 geralmente tem produtos **antigos**
- Focar em sitemaps **1, 2, 3** para produtos ativos
- Verificar:
  - Título específico (não genérico)
  - Apollo Cache com dados completos
  - Preços válidos

### 4. GraphQL Normalizado
- Objetos **referenciados por ID** (`{ type: "id", id: "..." }`)
- Precisa **seguir referências** para acessar dados
- Cache tem **estrutura flat** (todas chaves no mesmo nível)
- Vantagem: **sem duplicação** de dados

---

## Comparação com Outros Sites

| Site | Plataforma | Método |
|------|-----------|--------|
| **Magnumauto** | Custom | BeautifulSoup (SSR) |
| **Shopee** | Custom | JSON API + Selenium |
| **MatConcasa** | Next.js | BeautifulSoup (SSR) |
| **Artistas do Mundo** | Magento | ❌ JavaScript (não extraído) |
| **Sacada** | VTEX React | ✅ **Apollo Cache** |

**Sacada é o 5º extrator especializado** e mostra uma nova técnica: **Apollo Cache extraction**.

---

## Próximos Passos

1. ✅ Extrator `extract_sacada.py` criado e testado
2. ⏳ Integrar no QuintApp (`quintapp.py`)
3. ⏳ Adicionar detecção automática (URL contém `/p`)
4. ⏳ Extrair ~2268 produtos (sitemaps 1, 2, 3)
5. ⏳ Documentar em `RESUMO_TESTES_SITES.md`
6. ⏳ Atualizar `LICOES_APRENDIDAS.md`

---

## Conclusão

**Sacada agora está funcionando!** 🎉

O problema não era o QuintApp - era a arquitetura do site (JavaScript SPA). A solução usando **Apollo Cache** permite extrair dados sem precisar de Selenium, mantendo a velocidade de extração.

Este caso demonstra a importância de **analisar profundamente** cada site antes de concluir que algo "não funciona". Muitas vezes a solução está escondida no HTML, só precisa ser encontrada.
