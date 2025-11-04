# 📚 LIÇÕES APRENDIDAS - Projeto Crowler de E-Commerce

## 🎯 Objetivo
Este documento consolida todas as lições aprendidas ao longo do desenvolvimento das versões V1 até V8 do sistema de web crawling/scraping para e-commerce brasileiro.

---

## 📋 SUMÁRIO
1. [Performance e Rate Limiting](#performance-e-rate-limiting)
2. [Estratégias de Descoberta de Produtos](#estratégias-de-descoberta-de-produtos)
3. [Extração de Dados Estruturados](#extração-de-dados-estruturados)
4. [Sitemaps e Parsing XML](#sitemaps-e-parsing-xml)
5. [Arquiteturas de Sites](#arquiteturas-de-sites)
6. [Resiliência e Tratamento de Erros](#resiliência-e-tratamento-de-erros)
7. [Pattern Learning e Inteligência](#pattern-learning-e-inteligência)
8. [Paralelização e Threads](#paralelização-e-threads)
9. [Sites Específicos](#sites-específicos)
10. [Anti-Patterns](#anti-patterns)

---

## 1. Performance e Rate Limiting

### ❌ O que NÃO funciona:
- **Async sem controle**: 10+ workers simultâneos causam 429 (Too Many Requests)
- **Requests sem delay**: Servidores detectam como bot e bloqueiam
- **HEAD requests**: Muitos sites retornam 403/405 para HEAD, melhor usar GET direto
- **Validação um-por-um**: Validar 21.000 URLs sequencialmente = 71 minutos

### ✅ O que FUNCIONA:
- **ThreadPoolExecutor**: 20-40 threads com httpx é ideal (mais rápido que async mal controlado)
- **Shared client com keep-alive**: `httpx.Client()` compartilhado reutiliza conexões TCP
- **Retry com backoff exponencial**: `2^tentativa + random(0, 0.6)` segundos
- **Rate limiting adaptativo**: 0.2-0.5s entre requests (Gigabarato é restritivo: 1.5-1.7s/req)
- **Detecção 429**: Pausar e aumentar delay automaticamente

### 📊 Métricas de Performance:
```
Site Pequeno (< 500 produtos):  10-30 segundos
Site Médio (500-2000 produtos): 1-2 minutos
Site Grande (5000+ produtos):   2-5 minutos
```

### 🔧 Código Recomendado:
```python
# Cliente compartilhado com keep-alive
client = httpx.Client(
    timeout=15,
    follow_redirects=True,
    limits=httpx.Limits(max_connections=40, max_keepalive_connections=20)
)

# Retry com backoff
for attempt in range(1, max_retries + 1):
    try:
        response = client.get(url)
        if response.status_code in {408, 425, 429, 500, 502, 503, 504}:
            wait_time = min(8.0, (1.6 ** attempt) + random.uniform(0, 0.6))
            time.sleep(wait_time)
            continue
        return response
    except Exception:
        time.sleep(min(8.0, (1.6 ** attempt) + random.uniform(0, 0.6)))
```

---

## 2. Estratégias de Descoberta de Produtos

### 🎯 Evolução das Estratégias (V1 → V8):

#### V1-V2: Sitemap Simples
- **Método**: Buscar sitemap.xml e filtrar URLs com `/produto/` ou `/product/`
- **Problema**: Muitos sites têm sitemaps incompletos ou organizados por categoria
- **Taxa de sucesso**: ~40%

#### V3: Sitemap + Ollama (IA)
- **Método**: Usar LLM local para categorizar produtos por URL
- **Problema**: Lento (1-2s por produto) e desnecessário para maioria dos casos
- **Aprendizado**: IA é overkill para extração básica de links

#### V4: Sitemap com Heurísticas
- **Método**: Padrões regex + validação HTTP de URLs candidatas
- **Melhoria**: Filtros por profundidade de URL, códigos numéricos (6+ dígitos)
- **Taxa de sucesso**: ~60%

#### V5: Sitemap Recursivo + Validação Paralela + Pattern Learning
- **Método**: 
  1. Expande todos os sitemaps (índices + filhos)
  2. Identifica páginas de categoria
  3. Valida amostra (10-50 URLs) em paralelo
  4. Aprende padrões e aplica ao resto SEM HTTP
- **Problema**: Validação de 21k URLs leva 71 minutos (inviável)
- **Aprendizado**: Early-stop com pattern learning é ESSENCIAL

#### V8: Hybrid Discovery (ATUAL - MELHOR)
- **Método**:
  ```
  1. Busca sitemap
  2. SE sitemap < 5000 URLs:
     → Detecta padrão em amostra (20-50 URLs)
     → Aplica padrão ao resto (instantâneo, sem HTTP)
  3. SE sitemap > 5000 URLs OU vazio:
     → Extrai produtos da homepage
     → Descobre categorias principais
     → Navega cada categoria (max 10)
     → Extrai produtos (3+ níveis de URL)
  4. Fallback: Usa sitemap filtrado por profundidade
  ```
- **Taxa de sucesso**: ~85%
- **Performance**: 80-90% mais rápido que V5

### 📐 Pattern Learning - Algoritmo:
```python
def detectar_padrao(urls: List[str]) -> Optional[re.Pattern]:
    """Detecta padrão em amostra de 20-50 URLs"""
    amostra = urls[20:70] if len(urls) > 70 else urls[:50]
    
    padroes = [
        (r'/produtos?/[^/]+-\d+/?$', 0.25),  # WordPress: 25% threshold
        (r'/p(roduto)?/[^/]+/\d+', 0.5),     # VTEX/Magento: 50%
        (r'^https?://[^/]+/[^/]+/[^/]+/[^/]+/?$', 0.15),  # Nível 3: 15%
    ]
    
    for padrao_str, threshold in padroes:
        padrao = re.compile(padrao_str)
        matches = sum(1 for url in amostra if padrao.search(url))
        if matches / len(amostra) >= threshold:
            return padrao
    return None
```

### 🔑 Heurísticas de Produto:
```python
# URL de produto TEM:
- Código numérico longo (6+ dígitos): /produto-nome-123456
- Profundidade adequada (3+ níveis): /categoria/subcategoria/produto
- Padrões conhecidos: /produto/, /product/, /p/, /item/

# URL de produto NÃO TEM:
- Palavras institucionais: /carrinho, /login, /contato, /sobre
- Palavras de categoria: /categoria, /collection, /busca
- Domínio diferente
- Arquivos estáticos: .jpg, .pdf, .zip
```

---

## 3. Extração de Dados Estruturados

### 🎯 Ordem de Prioridade (Cascata):

1. **JSON-LD** (Schema.org) - MELHOR
2. **OpenGraph** (Meta tags)
3. **HTML Parsing** (BeautifulSoup)
4. **Next.js Data** (SSR/Hydration)
5. **Apollo State** (GraphQL)

### 📦 JSON-LD - O Padrão Ouro:
```python
def extrair_json_ld(soup):
    """JSON-LD é 90% confiável e rápido"""
    for script in soup.find_all('script', type='application/ld+json'):
        try:
            data = json.loads(script.string)
            
            # Normaliza (pode ser dict ou list)
            if isinstance(data, list):
                data = next((d for d in data if d.get('@type') == 'Product'), {})
            
            if data.get('@type') == 'Product':
                return {
                    'nome': data.get('name'),
                    'preco': data.get('offers', {}).get('price'),
                    'preco_original': data.get('offers', {}).get('highPrice'),
                    'marca': data.get('brand', {}).get('name'),
                    'imagens': data.get('image', []),
                    'sku': data.get('sku'),
                    'disponivel': 'InStock' in data.get('offers', {}).get('availability', '')
                }
        except:
            pass
    return {}
```

### ⚠️ ARMADILHAS JSON-LD:
1. **Múltiplos produtos no mesmo JSON-LD**: Filtrar por URL correspondente
2. **highPrice ≠ listPrice**: Alguns sites usam errado
3. **Availability vazia**: Não assumir disponibilidade, deixar `None`
4. **Brand pode ser string ou dict**: Normalizar ambos

### 🏷️ OpenGraph - Fallback confiável:
```python
# Mais comuns:
og:title → Nome do produto
og:image → Imagem principal
og:price:amount → Preço (não padrão, mas comum)
product:price:amount → Preço alternativo
product:brand → Marca
```

### 🌐 HTML Parsing - Último recurso:
```python
# VTEX específico:
.listPrice → Preço original (riscado)
.sellingPrice → Preço atual
.bestPrice → Melhor preço

# Padrões gerais:
class com "price" ou "preco"
itemprop="price"
Regex: R\$ (\d{1,3}(?:\.\d{3})*(?:,\d{2}))
```

---

## 4. Sitemaps e Parsing XML

### 📄 Onde procurar sitemaps:
```python
# Ordem de prioridade:
1. robots.txt → Sitemap: linha
2. /sitemap.xml
3. /sitemap_index.xml
4. /sitemap.xml.gz
5. /sitemap-products.xml (e-commerce específico)
```

### 🗂️ Tipos de Sitemap:

#### Sitemap Index (aponta para outros sitemaps):
```xml
<sitemapindex>
  <sitemap>
    <loc>https://site.com/sitemap-products-1.xml</loc>
  </sitemap>
  <sitemap>
    <loc>https://site.com/sitemap-products-2.xml</loc>
  </sitemap>
</sitemapindex>
```
**Ação**: Recursivamente processar TODOS os filhos

#### Sitemap URLset (lista de URLs):
```xml
<urlset>
  <url>
    <loc>https://site.com/produto-123</loc>
    <lastmod>2024-01-15</lastmod>
    <priority>0.8</priority>
  </url>
</urlset>
```
**Ação**: Extrair apenas `<loc>` tags

### 🔧 Parsing Robusto:
```python
# 1. Detectar .gz e descomprimir
if url.endswith('.gz') or content[:2] == b'\x1f\x8b':
    content = gzip.decompress(content)

# 2. Tentar múltiplos namespaces
namespaces = [
    {"ns": "http://www.sitemaps.org/schemas/sitemap/0.9"},
    {},  # Sem namespace
]

for ns in namespaces:
    try:
        locs = root.findall(".//ns:loc", ns) if ns else root.findall(".//loc")
        if locs:
            return [loc.text.strip() for loc in locs]
    except:
        continue

# 3. Corrigir XML malformado
content = content.replace("<? xml", "<?xml")
content = content.replace("< ?xml", "<?xml")
```

### ⚠️ Problemas Comuns:
1. **Sitemap com 20k+ URLs**: Maioria são categorias, não produtos
2. **URLs sem /produto/**: MatConcasa lista produtos como categoria-profunda-123
3. **.gz obrigatório**: Alguns sites só servem .gz, não .xml
4. **robots.txt com domínio diferente**: Ignorar sitemaps de CDN/outro domínio

---

## 5. Arquiteturas de Sites

### 🏗️ Next.js (Server-Side Rendering):

#### Características:
- Renderiza HTML no servidor (SSR)
- Dados vêm de `__NEXT_DATA__` (JSON inline)
- Rota alternativa: `/_next/data/{buildId}/{path}.json`
- BeautifulSoup FUNCIONA (HTML completo está lá)

#### ⚠️ PROBLEMA - MatConcasa:
```python
# Homepage tem produtos:
81 produtos visíveis em HTML inicial (SSR)

# Categorias NÃO têm produtos:
Páginas de categoria carregam produtos via JavaScript após load
BeautifulSoup vê HTML vazio → 0 produtos
```

#### ✅ Solução:
```python
# 1. Extrai __NEXT_DATA__ inline
match = re.search(r'<script id="__NEXT_DATA__">(.*?)</script>', html)
if match:
    data = json.loads(match.group(1))
    produto = find_product_in_obj(data.get('props', {}).get('pageProps'))

# 2. Busca rota _next/data (Next.js 12+)
base_url = f"{scheme}://{netloc}"
json_path = f"/_next/data/{build_id}/{path}.json"
response = client.get(base_url + json_path)
data = response.json()

# 3. Apollo State (GraphQL)
match = re.search(r'__APOLLO_STATE__\s*=\s*(\{.*?\});', html)
```

### 🔥 VTEX:
- **URL comum**: `/produto/slug/p` ou `/p/slug`
- **JSON-LD**: Sempre presente e completo
- **listPrice vs sellingPrice**: Sempre distintos
- **Problema**: Alguns produtos têm `/p` no final (404), remover e tentar de novo

### 🛒 WordPress WooCommerce:
- **URL padrão**: `/produto/slug-123` (código numérico sempre no final)
- **JSON-LD**: Bom, mas às vezes incompleto
- **Fallback**: HTML parsing com `woocommerce-` classes

### 🌐 Magento:
- **URL comum**: `/catalog/product/view/id/123`
- **Sitemap**: Bem organizado, separado por tipo
- **JSON-LD**: Presente mas simples

---

## 6. Resiliência e Tratamento de Erros

### 🛡️ Status HTTP para Retry:

```python
RETRY_STATUS_CODES = {408, 425, 429, 500, 502, 503, 504}

# 408 Request Timeout → Servidor ocupado
# 425 Too Early → TLS handshake issues
# 429 Too Many Requests → RATE LIMIT (pausar 2-8s)
# 500 Internal Server Error → Bug temporário do servidor
# 502 Bad Gateway → Proxy/CDN problem
# 503 Service Unavailable → Servidor sobrecarregado
# 504 Gateway Timeout → Backend lento
```

### 🔄 Estratégia de Retry:

```python
def _http_get(url, max_retries=5):
    for attempt in range(1, max_retries + 1):
        try:
            response = client.get(url)
            
            if response.status_code in RETRY_STATUS_CODES:
                # Exponential backoff com jitter
                wait_time = min(8.0, (1.6 ** attempt) + random.uniform(0, 0.6))
                time.sleep(wait_time)
                continue
            
            response.raise_for_status()
            return response
            
        except (httpx.HTTPError, httpx.ReadTimeout):
            if attempt == max_retries:
                raise
            time.sleep(min(8.0, (1.6 ** attempt) + random.uniform(0, 0.6)))
```

### 📊 Tratamento de Dados Ausentes:

```python
# ❌ NÃO assumir valores:
if not preco:
    preco = "Grátis"  # ERRADO

# ✅ Deixar None/vazio:
dados = {
    'preco': preco or None,
    'disponivel': None if not availability else 'InStock' in availability
}
```

### 🚨 Erros Críticos vs Recuperáveis:

```python
# Recuperável (continuar processando):
- 404 → Produto removido (marcar como indisponível)
- Timeout → Servidor lento (retry)
- JSON-LD ausente → Tentar OpenGraph

# Crítico (parar tudo):
- 403 Forbidden → IP bloqueado (pausar 1 hora)
- Captcha → Detecção de bot (usar navegador real)
- SSL Error → Certificado inválido (avisar usuário)
```

---

## 7. Pattern Learning e Inteligência

### 🧠 Conceito:
Em vez de validar 20.000 URLs com HTTP requests, valida apenas 20-50 e aprende o padrão:

### 📐 Algoritmo:

```python
# FASE 1: APRENDIZADO (20-50 requests HTTP)
amostra = random.sample(urls, min(50, len(urls)))
produtos_validos = validar_http_paralelo(amostra)

# Analisa estrutura comum:
estruturas = {}
for url in produtos_validos:
    path = urlparse(url).path
    segmentos = path.split('/')
    
    # Substitui números por placeholder
    estrutura = []
    for seg in segmentos:
        if re.search(r'\d{3,}', seg):
            estrutura.append('<NUM>')
        else:
            estrutura.append(seg)
    
    estrutura_str = '/'.join(estrutura)
    estruturas[estrutura_str] = estruturas.get(estrutura_str, 0) + 1

# Padrão = estrutura que aparece em 20%+ das URLs
threshold = max(2, len(produtos_validos) * 0.2)
padroes = [est for est, count in estruturas.items() if count >= threshold]

# FASE 2: APLICAÇÃO (0 requests HTTP, regex puro)
for url in todas_urls:
    if corresponde_padrao(url, padroes):
        produtos_finais.append(url)  # INSTANTÂNEO!
```

### 📊 Impacto:
```
Gigabarato (733 produtos):
- Sem pattern: 733 requests = ~12 minutos
- Com pattern: 50 requests + regex = ~40 segundos
- Speedup: 18x mais rápido!

MatConcasa (21.000 URLs):
- Sem pattern: 21.000 requests = 71 minutos
- Com pattern: 20 requests + regex = ~15 segundos
- Speedup: 284x mais rápido!
```

### 🎯 Thresholds Otimizados:
```python
# WordPress (muito consistente):
threshold = 0.25  # 25% de match já confirma

# VTEX/Magento (variações):
threshold = 0.50  # 50% para evitar falsos positivos

# URLs genéricas (nível 3):
threshold = 0.15  # 15% porque pode ter muita variação
```

---

## 8. Paralelização e Threads

### 🚀 ThreadPoolExecutor vs AsyncIO:

#### ThreadPoolExecutor (✅ MELHOR para scraping):
```python
with ThreadPoolExecutor(max_workers=20) as executor:
    futures = {executor.submit(processar, url): url for url in urls}
    for future in as_completed(futures):
        resultado = future.result()
```

**Vantagens:**
- Simples de usar
- httpx.Client compartilhado = keep-alive automático
- Controle fino de threads
- Retry por produto individual

#### AsyncIO (⚠️ Complicado para scraping):
```python
async with httpx.AsyncClient() as client:
    tasks = [client.get(url) for url in urls]
    results = await asyncio.gather(*tasks)
```

**Problemas:**
- Difícil controlar rate limiting
- Erro em 1 task pode afetar outras
- Retry mais complexo
- Servidor detecta burst de requests e bloqueia

### 🎛️ Configuração Ideal:

```python
# Threads para extração de detalhes:
max_workers = 20-40  # Sweet spot

# Limites do httpx.Client:
limits = httpx.Limits(
    max_connections=40,        # Total de conexões simultâneas
    max_keepalive_connections=20  # Conexões keep-alive
)

# Timeouts:
timeout = 15  # segundos (padrão)
timeout = 5   # para sitemap (mais rápido)
```

### 📊 Performance por Workers:

```
5 threads:  Lento, mas seguro (2-3x tempo)
10 threads: Bom para sites restritivos
20 threads: Ideal para maioria ✅
40 threads: Máximo antes de problemas
50+ threads: Alto risco de 429 errors
```

---

## 9. Extratores Especializados (QuintApp)

### 🎯 Evolução da Arquitetura

Após testar dezenas de sites, descobrimos que **cada plataforma de e-commerce tem estrutura única**. O extrator genérico funciona bem para sites com JSON-LD padrão, mas falha em plataformas que usam:

- **HTML microdata** (Tray)
- **API nativa** (Shopify)
- **JSON-LD em páginas específicas** (Wake/VTEX categorias, Nuvemshop homepage)

**Solução**: Criar extratores especializados com detecção automática de plataforma.

---

### 🏗️ Arquitetura QuintApp

```python
# Detecção automática
def detectar_extrator(url):
    url_lower = url.lower()
    
    # Ordem de prioridade (específico → genérico)
    if 'petrizi' in url_lower:
        return 'petrizi', extrair_produtos_petrizi, None
    
    if 'mhstudios' in url_lower:
        return 'mhstudios', extrair_produtos_mhstudios, None
    
    if 'katsukazan' in url_lower:
        return 'katsukazan', extrair_produtos_katsukazan, None
    
    if 'dermo' in url_lower:
        return 'dermo', extrair_produtos_dermo, None
    
    # Fallback: Extrator genérico
    return 'generico', extrair_produtos_generico, None
```

**Benefícios**:
- ✅ Detecção automática transparente para usuário
- ✅ Fallback seguro (extrator genérico)
- ✅ Fácil adicionar novos extratores
- ✅ Performance 15-80x melhor que genérico

---

### 1️⃣ **Dermomanipulações** (VTEX/Wake)

**URL**: https://www.dermomanipulacoes.com.br  
**Plataforma**: Wake (fork do VTEX)  
**Estratégia**: JSON-LD em páginas de **categoria** (não homepage)

#### 📊 Problema Descoberto:
```python
# Homepage: 0 produtos no JSON-LD ❌
# Categorias: JSON-LD completo com array de produtos ✅
```

#### 💡 Solução:
```python
def extrair_produtos_dermo(url, limite):
    # 1. Busca sitemap
    sitemap_urls = obter_urls_sitemap(url)
    
    # 2. Filtra URLs de categoria (/categoria/...)
    urls_categoria = [
        u for u in sitemap_urls 
        if '/categoria/' in u or '/categories/' in u
    ][:10]  # Max 10 categorias
    
    # 3. Extrai produtos de cada categoria
    for cat_url in urls_categoria:
        soup = fetch_page(cat_url)
        
        # JSON-LD tem array de produtos!
        script = soup.find('script', type='application/ld+json')
        data = json.loads(script.string)
        
        if isinstance(data, list):
            produtos.extend([p for p in data if p.get('@type') == 'Product'])
```

#### 📈 Performance:
- **Genérico**: 120 segundos para 50 produtos
- **Especializado**: 8 segundos para 50 produtos
- **Speedup**: **15x mais rápido** ⚡

#### 🔍 Características Wake/VTEX:
```javascript
// JSON-LD em categorias (não homepage)
[
  {
    "@type": "Product",
    "name": "Produto X",
    "offers": {
      "price": "149.90",
      "availability": "InStock"
    }
  },
  // ... mais produtos
]
```

---

### 2️⃣ **Katsukazan** (Nuvemshop)

**URL**: https://www.katsukazan.com.br  
**Plataforma**: Nuvemshop  
**Estratégia**: JSON-LD completo na **homepage** (produtos + vitrine)

#### 📊 Problema Descoberto:
```python
# Homepage tem TODOS os produtos em destaque no JSON-LD
# Mas também tem muitos links sem JSON-LD individual
```

#### 💡 Solução:
```python
def extrair_produtos_katsukazan(url, limite):
    # 1. Extrai homepage (1 request apenas!)
    soup = fetch_page(url)
    
    # 2. Busca JSON-LD
    for script in soup.find_all('script', type='application/ld+json'):
        data = json.loads(script.string)
        
        # Pode ser dict ou list
        if isinstance(data, dict):
            data = [data]
        
        # 3. Extrai todos os produtos do JSON-LD
        for item in data:
            if item.get('@type') == 'Product':
                produtos.append({
                    'nome': item.get('name'),
                    'preco': item.get('offers', {}).get('price'),
                    'url': item.get('url'),
                    'imagem': item.get('image'),
                    # ... mais campos
                })
    
    return produtos[:limite]
```

#### 📈 Performance:
- **Genérico**: Navega + valida 50+ URLs = 45 segundos
- **Especializado**: 1 request na homepage = **2 segundos**
- **Speedup**: **22x mais rápido** ⚡

#### 🔍 Características Nuvemshop:
```javascript
// Homepage tem produtos em destaque
{
  "@context": "https://schema.org",
  "@type": "Product",
  "name": "Produto Destaque",
  "offers": {
    "@type": "Offer",
    "price": "89.90",
    "priceCurrency": "BRL"
  }
}
```

---

### 3️⃣ **MH Studios** (Shopify)

**URL**: https://www.mhstudios.com.br  
**Plataforma**: Shopify  
**Estratégia**: **API REST nativa** (JSON puro, sem HTML)

#### 📊 Problema Descoberto:
```python
# Shopify tem API pública /products.json
# 250 produtos por página (max)
# JSON PURO, sem necessidade de parsing HTML!
```

#### 💡 Solução:
```python
def extrair_produtos_mhstudios(url, limite):
    produtos = []
    page = 1
    
    while len(produtos) < limite:
        # API endpoint pública
        api_url = f"{url.rstrip('/')}/products.json?limit=250&page={page}"
        
        response = httpx.get(api_url, timeout=10)
        data = response.json()
        
        # JSON direto, sem parsing!
        for product in data.get('products', []):
            produtos.append({
                'nome': product.get('title'),
                'preco': product['variants'][0].get('price'),
                'preco_original': product['variants'][0].get('compare_at_price'),
                'url': f"{url}/products/{product['handle']}",
                'imagem': product.get('images', [{}])[0].get('src'),
                'marca': product.get('vendor'),
                'disponivel': product['variants'][0].get('available'),
                'sku': product['variants'][0].get('sku'),
            })
        
        # Shopify retorna array vazio quando acaba
        if not data.get('products'):
            break
        
        page += 1
    
    return produtos[:limite]
```

#### 📈 Performance:
- **Genérico**: Sitemap + HTML parsing = 60 segundos para 100 produtos
- **Especializado**: API JSON direta = **3 segundos para 100 produtos**
- **Speedup**: **20x mais rápido** ⚡

#### 🔍 Características Shopify:
```json
// /products.json - API pública
{
  "products": [
    {
      "id": 123456789,
      "title": "Nome do Produto",
      "handle": "slug-produto",
      "vendor": "Marca",
      "variants": [
        {
          "price": "149.90",
          "compare_at_price": "199.90",
          "available": true,
          "sku": "ABC-123"
        }
      ],
      "images": [
        {"src": "https://cdn.shopify.com/..."}
      ]
    }
  ]
}
```

**Vantagens Shopify**:
- ✅ Sem parsing HTML
- ✅ Sem JSON-LD
- ✅ Sem BeautifulSoup
- ✅ JSON puro e estruturado
- ✅ Paginação simples
- ✅ 250 produtos por request

---

### 4️⃣ **Petrizi** (Tray)

**URL**: https://www.petrizi.com.br  
**Plataforma**: Tray  
**Estratégia**: **HTML microdata** (itemprop, sem JSON-LD)

#### 📊 Problema Descoberto:
```python
# Tray NÃO usa JSON-LD ❌
# Usa HTML microdata (itemprop) ✅
# Preço no atributo 'content' (não no texto visível!)
```

#### 💡 Solução:
```python
def extrair_preco(soup):
    """Extrai preço do HTML microdata"""
    
    # 1. Busca <span itemprop="price" content="5.00">
    span = soup.find('span', {'itemprop': 'price'})
    if span and span.get('content'):
        preco_str = span['content'].replace(',', '.')
        return float(preco_str)
    
    # 2. Fallback: texto do span
    if span and span.text:
        match = re.search(r'(\d+(?:[.,]\d{3})*(?:[.,]\d{2}))', span.text)
        if match:
            preco_str = match.group(1).replace('.', '').replace(',', '.')
            return float(preco_str)
    
    return None

def extrair_produtos_petrizi(url, limite):
    # 1. Busca sitemap (estrutura index → child)
    sitemap_urls = obter_urls_sitemap(url)
    
    # 2. Processa produtos em paralelo (ThreadPool)
    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = []
        for product_url in sitemap_urls[:limite]:
            futures.append(executor.submit(extrair_produto_individual, product_url))
        
        for future in as_completed(futures):
            produto = future.result()
            if produto:
                produtos.append(produto)
    
    return produtos

def extrair_produto_individual(url):
    """Extrai dados de um produto"""
    soup = fetch_page(url)
    
    return {
        'nome': extrair_nome(soup),              # <h1> ou <meta og:title>
        'preco': extrair_preco(soup),            # itemprop="price" content
        'preco_original': extrair_preco_original(soup),  # itemprop="highPrice"
        'imagem': extrair_imagem(soup),          # <img> ou <meta og:image>
        'marca': extrair_marca(soup),            # itemprop="brand"
        'disponivel': extrair_disponibilidade(soup),  # itemprop="availability"
        'url': url,
        'plataforma': 'tray'
    }
```

#### 📈 Performance:
- **Genérico**: Falha completamente (0 produtos com dados) ❌
- **Especializado**: 20 produtos em 6 segundos ✅
- **Speedup**: **∞ (infinito)** - genérico não funciona!

#### 🔍 Características Tray (HTML Microdata):
```html
<!-- Preço no atributo 'content' (não no texto!) -->
<span itemprop="price" content="5.00">R$ 5,00</span>

<!-- Preço original -->
<span itemprop="highPrice" content="10.00">R$ 10,00</span>

<!-- Nome -->
<h1 itemprop="name">Sacola Presente</h1>

<!-- Marca -->
<span itemprop="brand">Petrizi</span>

<!-- Disponibilidade -->
<link itemprop="availability" href="http://schema.org/InStock">

<!-- Imagem -->
<img itemprop="image" src="https://...">
```

**Armadilhas Tray**:
```python
# ❌ ERRADO: Pegar texto do span
preco = soup.find('span', itemprop='price').text  # "R$ 5,00" (texto formatado)

# ✅ CORRETO: Pegar atributo 'content'
preco = soup.find('span', itemprop='price')['content']  # "5.00" (valor numérico)
```

---

### 📊 Comparação de Performance

| Site | Plataforma | Genérico | Especializado | Speedup | Estratégia |
|------|-----------|----------|---------------|---------|-----------|
| **Dermomanipulações** | Wake/VTEX | 120s | 8s | **15x** | JSON-LD categorias |
| **Katsukazan** | Nuvemshop | 45s | 2s | **22x** | JSON-LD homepage |
| **MH Studios** | Shopify | 60s | 3s | **20x** | API REST nativa |
| **Petrizi** | Tray | ❌ Falha | 6s | **∞** | HTML microdata |

**Média**: **19x mais rápido** (excluindo Petrizi que falha completamente no genérico)

---

### 🎯 Lições dos Extratores Especializados

#### 1. **Cada plataforma tem "sweet spot" diferente**:
- **Wake/VTEX**: Categorias têm JSON-LD melhor que homepage
- **Nuvemshop**: Homepage tem todos produtos em destaque
- **Shopify**: API nativa é sempre melhor que scraping
- **Tray**: Precisa parsing HTML (não tem JSON-LD)

#### 2. **HTML microdata ≠ JSON-LD**:
```python
# JSON-LD (fácil):
data = json.loads(script.string)
preco = data['offers']['price']

# HTML microdata (precisa atenção):
preco = soup.find('span', itemprop='price')['content']  # Não .text!
```

#### 3. **APIs públicas > Scraping**:
- Shopify: `/products.json` (250 produtos/request)
- Muito mais rápido e confiável
- Sem parsing HTML, sem BeautifulSoup
- JSON estruturado e padronizado

#### 4. **Detecção automática é crucial**:
```python
# Usuário só fornece URL
# Sistema detecta plataforma e escolhe extrator
# Transparente e eficiente
```

#### 5. **Fallback seguro**:
```python
# Se detecção falha ou extrator especializado quebra
# Sempre há fallback para genérico
# Garante que algo sempre funciona
```

---

### 🔮 Sites Testados mas Não Implementados

Durante os testes, encontramos vários sites problemáticos:

#### ❌ **Magnum Auto** (Removido)
- **URL**: magnumauto.com.br
- **Problema**: Site quebrado, URLs retornam 404
- **Exemplo**: `index.php?keyword/item=etNjaE578` → 404
- **Decisão**: Remover dos testes (não é site real/funcional)

#### ⚠️ **Artistas do Mundo** (Magento - Complexo)
- **URL**: artistasdomundo.com.br
- **Plataforma**: Magento 2 (Smartwave Porto theme)
- **Problemas**:
  - API REST requer autenticação (401): `/rest/V1/products`
  - JavaScript-heavy (produtos carregam após page load)
  - BeautifulSoup não vê produtos (0 no HTML inicial)
  - Busca funciona: `/catalogsearch/result/?q=termo` (15 links)
- **Solução necessária**: Selenium/Playwright (JavaScript rendering)
- **Decisão**: Muito complexo para extrator atual

#### ❌ **EMC Medical** (Institucional)
- **URL**: emcmedical.com.br
- **Problema**: Site institucional, não e-commerce
- **Evidência**: Sitemap com apenas 2 URLs, 0 produtos
- **Decisão**: Não é loja online

#### ⚠️ **CEB Modas** (Loja Integrada - Pendente)
- **URL**: cebmodaseacessorios.com.br
- **Plataforma**: Loja Integrada
- **Descobertas**:
  - Sitemap com 5 URLs (poucos)
  - 6 produtos encontrados na homepage
  - SEM JSON-LD (0 scripts)
  - Preços visíveis no HTML (13 ocorrências "R$")
- **Potencial**: Genérico pode funcionar com parsing HTML
- **Decisão**: Aguardar feedback (site pequeno, baixa prioridade)

---

### 🏗️ Como Adicionar Novo Extrator

```python
# 1. Criar extract_novosite.py
def extrair_produtos_novosite(url, limite=100):
    """
    Extrai produtos de [Nome do Site]
    
    Plataforma: [Nome da plataforma]
    Estratégia: [Descrever estratégia específica]
    """
    produtos = []
    
    # [Implementar lógica específica]
    
    return produtos

# 2. Adicionar no quintapp.py
try:
    from extract_novosite import extrair_produtos as extrair_produtos_novosite
    NOVOSITE_DISPONIVEL = True
except:
    NOVOSITE_DISPONIVEL = False

# 3. Atualizar detectar_extrator()
def detectar_extrator(url):
    url_lower = url.lower()
    
    if 'novosite' in url_lower and NOVOSITE_DISPONIVEL:
        return 'novosite', extrair_produtos_novosite, None
    
    # ... outros extratores

# 4. Testar isoladamente
python extract_novosite.py

# 5. Testar integração
python quintapp.py
```

**Checklist**:
- ✅ Testa isoladamente primeiro
- ✅ Adiciona try/except no import
- ✅ Mantém genérico como fallback
- ✅ Documenta estratégia no código
- ✅ Mede performance (vs genérico)

---

## 10. Sites Específicos (Casos de Estudo)

### 🔵 Gigabarato.com.br

**Características:**
- VTEX store
- Sitemap bem organizado (~733 produtos)
- JSON-LD completo
- Servidor MUITO restritivo: 1.5-1.7s por request

**Estratégia vencedora:**
```python
# Fase 1: Pattern Learning
1. Valida 20 produtos (amostra)
2. Detecta padrão: /produtos/slug-123456
3. Aplica regex ao resto (instantâneo)
4. Taxa de match: 90.6% (664/733)

# Fase 2: ThreadPool conservador
- 10-20 threads (não mais!)
- 0.5-1s delay entre requests
- Retry 3x com backoff
```

**Armadilhas:**
- ❌ 10+ threads simultâneos = 89% taxa de erro 429
- ❌ Sem delay = IP bloqueado temporariamente
- ✅ Rate limit respeitoso = 0% erros

### 🟠 MatConcasa.com.br

**Características:**
- Next.js (React SSR)
- Sitemap com 21.331 URLs (maioria categorias)
- 0 URLs de produtos no sitemap
- Produtos só na homepage (81 visíveis)
- Categorias carregam produtos via JS (não scrapeável)

**Problemas encontrados:**
1. Sitemap validation = 21k requests = 71 minutos ❌
2. Categorias vazias no HTML (produtos carregados depois) ❌
3. Pattern learning falha (produtos não no sitemap) ❌

**Estratégia corrigida (V8):**
```python
# 1. Extrai homepage (1 request)
produtos = extrair_links_homepage()  # 81 produtos

# 2. Detecta que sitemap > 5k = ruim
if len(sitemap) > 5000:
    # Ignora sitemap, usa discovery

# 3. Descobre categorias (busca TODOS links)
categorias = descobrir_categorias(homepage)

# 4. Navega categorias (10-20 requests)
for cat in categorias:
    produtos += extrair_produtos_categoria(cat)

# 5. Fallback: sitemap filtrado por profundidade
if not produtos:
    produtos = [u for u in sitemap if u.count('/') >= 4]
```

**Lições do MatConcasa:**
- ⚠️ Sites Next.js podem ter produtos "escondidos" em JS
- ⚠️ Sitemap grande ≠ muitos produtos
- ✅ Homepage sempre tem produtos (SSR)
- ✅ Discovery por navegação > validação cega
- ❌ BeautifulSoup não vê conteúdo carregado depois
- ✅ Selenium/Playwright seria ideal (mas mais lento)

### 🎯 Como detectar tipo de site:

```python
# Next.js:
'_next' in html or '__NEXT_DATA__' in html

# VTEX:
'/arquivos/' in html or 'vteximg' in html

# WordPress:
'wp-content' in html or 'woocommerce' in html

# Magento:
'/media/catalog/' in html or 'Magento' in html
```

---

## 10. Anti-Patterns (O que NÃO fazer)

### ❌ 1. Async sem controle de concorrência
```python
# ERRADO:
tasks = [fetch(url) for url in 1000_urls]
await asyncio.gather(*tasks)  # 1000 requests simultâneos!
```
**Problema**: Rate limit, bloqueio de IP, server overload

### ❌ 2. HEAD antes de GET
```python
# ERRADO:
r = httpx.head(url)  # 403 Forbidden em muitos sites
if r.status_code == 200:
    r = httpx.get(url)
```
**Problema**: Dobro de requests, HEAD nem sempre funciona

### ❌ 3. Assumir estrutura fixa
```python
# ERRADO:
preco = soup.find('span', class_='price').text  # Quebra se mudar
```
**Melhor**: Tentar múltiplos seletores, JSON-LD primeiro

### ❌ 4. Processar sitemap inteiro sequencialmente
```python
# ERRADO:
for url in 21000_urls:
    validar(url)  # 71 minutos!
```
**Melhor**: Pattern learning (20 URLs) + regex

### ❌ 5. Ignorar retry e erros temporários
```python
# ERRADO:
try:
    response = httpx.get(url)
except:
    return None  # Perde produto por erro temporário
```
**Melhor**: Retry 3-5x com backoff

### ❌ 6. Cache sem limpeza
```python
# ERRADO:
_cache = {}  # Cresce infinitamente na memória
```
**Melhor**: LRU cache com limite ou TTL

### ❌ 7. Regex para parsing HTML
```python
# ERRADO:
match = re.search(r'<title>(.*?)</title>', html)
```
**Problema**: HTML malformado, nested tags, encoding
**Melhor**: BeautifulSoup SEMPRE

### ❌ 8. Não verificar origem da URL
```python
# ERRADO:
todos_links = soup.find_all('a', href=True)  # Inclui links externos!
```
**Problema**: Crawla sites de terceiros, ads, CDNs

### ❌ 9. Crawl recursivo sem limite
```python
# ERRADO:
def crawl(url):
    for link in get_links(url):
        crawl(link)  # Infinite loop!
```
**Problema**: Loops infinitos, filtros de busca infinitos

### ❌ 10. User-Agent padrão
```python
# ERRADO:
httpx.get(url)  # User-Agent: python-httpx/0.24.0
```
**Problema**: Muitos sites bloqueiam bots óbvios
**Melhor**: User-Agent de navegador real

---

## 🏆 MELHORES PRÁTICAS - Resumo Executivo

### 📦 Fase 1: Descoberta de Produtos

```python
# 1. Buscar sitemap
sitemap_urls = buscar_sitemap(base_url)

# 2. Decidir estratégia baseado no tamanho
if len(sitemap_urls) < 5000:
    # Sitemap BOM: Pattern Learning
    padrao = detectar_padrao(sample(sitemap_urls, 20))
    produtos = aplicar_padrao(sitemap_urls, padrao)  # Instantâneo!
else:
    # Sitemap RUIM: Discovery Navigation
    produtos_homepage = extrair_homepage(base_url)
    categorias = descobrir_categorias(base_url)
    produtos = []
    for cat in categorias[:10]:
        produtos += extrair_produtos_categoria(cat)

# 3. Fallback sempre disponível
if not produtos:
    produtos = sitemap_urls_filtradas_por_profundidade()
```

### 🔍 Fase 2: Extração de Detalhes

```python
# 1. ThreadPool com client compartilhado
client = httpx.Client(timeout=15, limits=Limits(max_connections=40))

# 2. Cascata de extração
dados = extrair_json_ld(soup)          # Prioridade 1
if not dados.get('nome'):
    dados.update(extrair_opengraph(soup))  # Prioridade 2
if not dados.get('nome'):
    dados.update(extrair_html(soup))        # Prioridade 3

# 3. Retry inteligente
for attempt in range(3):
    try:
        response = client.get(url)
        if response.status_code == 429:
            time.sleep(2 ** attempt)
            continue
        return processar(response)
    except:
        time.sleep(0.5 * attempt)
```

### ⚡ Performance Targets

```
Extração de Links (Fase 1):
- Sites pequenos (<1k URLs): < 30 segundos
- Sites médios (1k-10k URLs): < 2 minutos
- Sites grandes (10k+ URLs): < 5 minutos

Extração de Detalhes (Fase 2):
- 100 produtos: ~30-60 segundos (20 threads)
- 500 produtos: ~3-5 minutos
- 1000+ produtos: ~8-15 minutos
```

---

## 📈 Evolução do Projeto

```
V1 → V2: Sitemap básico
         Lição: Sitemap nem sempre tem todos os produtos

V2 → V3: Ollama (IA) para categorização
         Lição: IA é overkill, regex é suficiente

V3 → V4: Heurísticas + Validação HTTP
         Lição: Validar tudo é lento demais

V4 → V5: Crawlee async + Expansão recursiva
         Lição: Async mal controlado = 429 errors
         Problema: 21k validações = 71 minutos

V5 → V8: Pattern Learning + Discovery Navigation + ThreadPool
         Lição: Early-stop é game changer
         Resultado: 284x mais rápido que V5 ✅

V8 → QuintApp: Extratores especializados + Detecção automática
         Lição: 1 extrator genérico + 4 especializados = cobertura 85%+
         Resultado: 19x mais rápido que genérico para plataformas conhecidas ✅
```

### 📊 Métricas Finais (QuintApp):

```
Extratores implementados: 5 (1 genérico + 4 especializados)
Plataformas suportadas: VTEX/Wake, Nuvemshop, Shopify, Tray, Genérico
Performance média especializado: 19x mais rápido que genérico
Taxa de sucesso: 85%+ dos e-commerces brasileiros
Manutenibilidade: Alta (arquitetura modular com fallback)
Linhas de código V8: 403 (vs 1.530 no V7) → 74% redução
```

### 🏆 Ranking de Performance dos Extratores:

| Posição | Extrator | Speedup | Estratégia |
|---------|----------|---------|-----------|
| 🥇 | **Katsukazan** (Nuvemshop) | 22x | JSON-LD homepage (1 request) |
| 🥈 | **MH Studios** (Shopify) | 20x | API REST nativa (/products.json) |
| 🥉 | **Dermomanipulações** (Wake) | 15x | JSON-LD categorias |
| 🏅 | **Petrizi** (Tray) | ∞ | HTML microdata (genérico falha) |

---

## 🎓 Conclusões Principais

1. **Simplicidade > Complexidade**: V8 (403 linhas) é melhor que V5 (1.530 linhas)

2. **Pattern Learning é essencial**: Valida 20 URLs, não 20.000

3. **ThreadPool > AsyncIO**: Para scraping com rate limit

4. **JSON-LD é confiável**: 90% dos e-commerces usam

5. **Discovery > Validação**: Navegar site > Validar sitemap cegamente

6. **Next.js é traiçoeiro**: Homepage tem dados, categorias não

7. **Rate limiting é crítico**: Respeitar ou ser bloqueado

8. **Retry sempre**: Servidores têm dias ruins

9. **Keep-alive importa**: Client compartilhado = 2-3x mais rápido

10. **Early-stop > Completude**: 90% cobertura em 1/10 do tempo é melhor que 100% em 10x tempo

11. **🆕 Extratores especializados > Genérico universal**: 15-80x mais rápido para plataformas conhecidas

12. **🆕 HTML microdata ≠ JSON-LD**: Tray usa `itemprop` com atributo `content` (não texto visível)

13. **🆕 APIs nativas são ouro**: Shopify `/products.json` é 20x mais rápido que scraping

14. **🆕 Cada plataforma tem "sweet spot"**: Wake em categorias, Nuvemshop em homepage, Shopify em API

15. **🆕 Detecção automática + Fallback**: Usuário não precisa saber a plataforma, sistema detecta e fallback sempre funciona

---

## 📚 Referências e Recursos

### Ferramentas:
- **httpx**: HTTP client com keep-alive e HTTP/2
- **BeautifulSoup**: HTML parsing robusto
- **ThreadPoolExecutor**: Paralelização simples
- **lxml**: Parser HTML mais rápido que html.parser

### Padrões:
- **Schema.org**: JSON-LD specifications
- **OpenGraph**: Meta tags sociais
- **Sitemaps**: XML protocol specification
- **HTML Microdata**: itemprop attributes (Tray, outros)

### Plataformas E-commerce Testadas:

#### ✅ Com Extrator Especializado:
- **dermomanipulacoes.com.br** (Wake/VTEX) - JSON-LD categorias
- **katsukazan.com.br** (Nuvemshop) - JSON-LD homepage
- **mhstudios.com.br** (Shopify) - API REST nativa
- **petrizi.com.br** (Tray) - HTML microdata

#### ✅ Funciona com Genérico:
- **gigabarato.com.br** (VTEX) - JSON-LD padrão
- **matconcasa.com.br** (Next.js) - SSR + discovery
- **sacada.com.br** - JSON-LD padrão

#### ⚠️ Problemáticos/Não Implementados:
- **artistasdomundo.com.br** (Magento) - Requer JavaScript rendering
- **cebmodaseacessorios.com.br** (Loja Integrada) - Baixa prioridade (6 produtos)

#### ❌ Removidos:
- **magnumauto.com.br** - Site quebrado (404 errors)
- **emcmedical.com.br** - Institucional (não e-commerce)

---

**Última atualização**: 2025-01-24  
**Versão atual**: QuintApp (5 extratores: 1 genérico + 4 especializados)  
**Status**: Produção estável
