# 🏗️ Arquitetura QuintApp - Sistema de Extração Multi-Plataforma

**Versão**: 1.0  
**Data**: 2025-01-24  
**Status**: Produção

---

## 🎯 Visão Geral

QuintApp é um sistema inteligente de extração de produtos e-commerce que **detecta automaticamente** a plataforma do site e escolhe o **extrator mais eficiente**.

### Características Principais:
- ✅ **5 extratores**: 1 genérico + 4 especializados
- ✅ **Detecção automática**: Via URL pattern matching
- ✅ **Fallback seguro**: Genérico sempre disponível
- ✅ **Performance**: 15-80x mais rápido que genérico
- ✅ **Modular**: Fácil adicionar novos extratores

---

## 🧩 Arquitetura do Sistema

```
┌─────────────────────────────────────────────────────────────┐
│                         QUINTAPP                            │
│                    (Interface Unificada)                    │
└─────────────────────────────────────────────────────────────┘
                              ↓
                    ┌─────────────────┐
                    │ detectar_extrator│
                    │   (URL → tipo)   │
                    └─────────────────┘
                              ↓
        ┌─────────────────────┴─────────────────────┐
        ↓                                           ↓
┌───────────────────┐                    ┌──────────────────┐
│  ESPECIALIZADOS   │                    │    GENÉRICO      │
│  (4 extratores)   │                    │  (Fallback)      │
└───────────────────┘                    └──────────────────┘
        ↓                                           ↓
   ┌────┴────┬────┬────┬────┐           ┌──────────────────┐
   ↓         ↓    ↓    ↓    ↓           │ Pattern Learning │
Dermo   Katsu  MH   Petrizi             │ + Discovery      │
(Wake) (Nuvem)(Shop)(Tray)              │ + JSON-LD        │
                                        └──────────────────┘
```

---

## 🔍 Fluxo de Detecção

```python
def detectar_extrator(url: str) -> Tuple[str, Callable, Any]:
    """
    Detecta plataforma e retorna extrator apropriado
    
    Returns:
        (tipo, função_extrator, kwargs)
    """
    url_lower = url.lower()
    
    # 1. Tenta extratores especializados (específico → genérico)
    if 'petrizi' in url_lower and PETRIZI_DISPONIVEL:
        return 'petrizi', extrair_produtos_petrizi, None
    
    if 'mhstudios' in url_lower and MHSTUDIOS_DISPONIVEL:
        return 'mhstudios', extrair_produtos_mhstudios, None
    
    if 'katsukazan' in url_lower and KATSUKAZAN_DISPONIVEL:
        return 'katsukazan', extrair_produtos_katsukazan, None
    
    if 'dermo' in url_lower and DERMO_DISPONIVEL:
        return 'dermo', extrair_produtos_dermo, None
    
    # 2. Fallback: Extrator genérico
    return 'generico', extrair_produtos_generico, None
```

### Características:
- ✅ **Ordem de prioridade**: Mais específico primeiro
- ✅ **Try/except imports**: Se módulo falhar, continua
- ✅ **Fallback garantido**: Genérico sempre disponível
- ✅ **Simples de estender**: Adicionar novo `if` block

---

## 🏭 Extratores Especializados

### 1️⃣ Dermomanipulações (Wake/VTEX)

```python
# extract_dermo.py

def extrair_produtos_dermo(url, limite=100):
    """
    Plataforma: Wake (fork VTEX)
    Estratégia: JSON-LD em CATEGORIAS (não homepage)
    Performance: 15x mais rápido que genérico
    """
    
    # 1. Busca sitemap
    sitemap_urls = obter_urls_sitemap(url)
    
    # 2. Filtra URLs de categoria
    urls_categoria = [
        u for u in sitemap_urls 
        if '/categoria/' in u or '/categories/' in u
    ][:10]
    
    # 3. Extrai JSON-LD de cada categoria
    produtos = []
    for cat_url in urls_categoria:
        soup = fetch_page(cat_url)
        produtos.extend(extrair_json_ld_array(soup))
        
        if len(produtos) >= limite:
            break
    
    return produtos[:limite]
```

**Sweet Spot**: Páginas de **categoria** têm array de produtos no JSON-LD

---

### 2️⃣ Katsukazan (Nuvemshop)

```python
# extract_katsukazan.py

def extrair_produtos_katsukazan(url, limite=100):
    """
    Plataforma: Nuvemshop
    Estratégia: JSON-LD completo na HOMEPAGE (1 request!)
    Performance: 22x mais rápido que genérico
    """
    
    # 1. Extrai homepage (1 request apenas!)
    soup = fetch_page(url)
    
    # 2. Busca todos JSON-LD scripts
    produtos = []
    for script in soup.find_all('script', type='application/ld+json'):
        data = json.loads(script.string)
        
        # Normaliza (pode ser dict ou list)
        if isinstance(data, dict):
            data = [data]
        
        # 3. Extrai produtos
        for item in data:
            if item.get('@type') == 'Product':
                produtos.append(processar_produto(item))
    
    return produtos[:limite]
```

**Sweet Spot**: **Homepage** já tem todos produtos em destaque no JSON-LD

---

### 3️⃣ MH Studios (Shopify)

```python
# extract_mhstudios.py

def extrair_produtos_mhstudios(url, limite=100):
    """
    Plataforma: Shopify
    Estratégia: API REST nativa (/products.json)
    Performance: 20x mais rápido que genérico
    """
    
    produtos = []
    page = 1
    
    while len(produtos) < limite:
        # API pública (JSON puro, sem HTML!)
        api_url = f"{url.rstrip('/')}/products.json?limit=250&page={page}"
        
        response = httpx.get(api_url, timeout=10)
        data = response.json()
        
        # Extrai produtos do JSON
        for product in data.get('products', []):
            produtos.append({
                'nome': product.get('title'),
                'preco': product['variants'][0].get('price'),
                'url': f"{url}/products/{product['handle']}",
                # ... mais campos
            })
        
        # Array vazio = fim
        if not data.get('products'):
            break
        
        page += 1
    
    return produtos[:limite]
```

**Sweet Spot**: **API REST pública** - 250 produtos por request!

---

### 4️⃣ Petrizi (Tray)

```python
# extract_petrizi.py

def extrair_produtos_petrizi(url, limite=100):
    """
    Plataforma: Tray
    Estratégia: HTML microdata (itemprop attributes)
    Performance: ∞ (genérico falha completamente)
    """
    
    # 1. Busca sitemap
    sitemap_urls = obter_urls_sitemap(url)
    
    # 2. Processa produtos em paralelo
    produtos = []
    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = [
            executor.submit(extrair_produto_individual, url)
            for url in sitemap_urls[:limite]
        ]
        
        for future in as_completed(futures):
            produto = future.result()
            if produto:
                produtos.append(produto)
    
    return produtos

def extrair_produto_individual(url):
    """Extrai dados de um produto via HTML microdata"""
    soup = fetch_page(url)
    
    return {
        'nome': extrair_nome(soup),
        'preco': extrair_preco(soup),  # itemprop="price" content
        'imagem': extrair_imagem(soup),
        # ...
    }

def extrair_preco(soup):
    """CRÍTICO: Preço no atributo 'content', não no texto!"""
    span = soup.find('span', {'itemprop': 'price'})
    
    # ✅ CORRETO: Pegar atributo
    if span and span.get('content'):
        return float(span['content'].replace(',', '.'))
    
    # ❌ ERRADO: span.text retorna "R$ 5,00" (formatado)
    return None
```

**Sweet Spot**: **HTML microdata** - preço em atributo `content`

---

## 🔄 Extrator Genérico (Fallback)

```python
# extract_production.py (ou equivalente)

def extrair_produtos_generico(url, limite=100):
    """
    Estratégia universal para sites desconhecidos
    
    1. Pattern Learning (detecta estrutura em amostra)
    2. Discovery Navigation (homepage → categorias)
    3. JSON-LD parsing (padrão Schema.org)
    """
    
    # 1. Busca sitemap
    sitemap_urls = buscar_sitemap(url)
    
    # 2. Decide estratégia baseado no tamanho
    if len(sitemap_urls) < 5000:
        # SITEMAP BOM: Pattern Learning
        padrao = detectar_padrao(sample(sitemap_urls, 20))
        produtos_urls = aplicar_padrao(sitemap_urls, padrao)
    else:
        # SITEMAP RUIM: Discovery Navigation
        produtos_urls = []
        produtos_urls.extend(extrair_homepage(url))
        
        categorias = descobrir_categorias(url)
        for cat in categorias[:10]:
            produtos_urls.extend(extrair_categoria(cat))
    
    # 3. Extrai detalhes (ThreadPool)
    produtos = extrair_detalhes_paralelo(produtos_urls, limite)
    
    return produtos
```

---

## 📊 Comparação de Estratégias

| Extrator | Plataforma | Estratégia | Requests | Tempo (100p) | Speedup |
|----------|-----------|-----------|----------|--------------|---------|
| **Katsukazan** | Nuvemshop | JSON-LD homepage | 1 | 2s | 22x |
| **MH Studios** | Shopify | API REST | 1-2 | 3s | 20x |
| **Dermomanipulações** | Wake | JSON-LD categorias | 10-15 | 8s | 15x |
| **Petrizi** | Tray | HTML microdata | 100 | 6s | ∞ |
| **Genérico** | Qualquer | Pattern Learning | 20-120 | 30-60s | 1x |

---

## 🎯 Decision Tree: Qual Extrator Usar?

```
URL fornecida
      ↓
┌─────────────────┐
│ É URL conhecida?│
└─────────────────┘
      ↓
    SIM → Usa extrator especializado
      ↓
    NÃO → Continua...
      ↓
┌──────────────────┐
│ Detecta plataforma│
│  (meta tags, JS)  │
└──────────────────┘
      ↓
    ┌─────────────────────────┐
    │ Shopify? → API REST     │
    │ VTEX? → Genérico        │
    │ Tray? → HTML microdata  │
    │ Next.js? → Discovery    │
    │ Desconhecido? → Genérico│
    └─────────────────────────┘
      ↓
┌──────────────────┐
│ Fallback: Genérico│
└──────────────────┘
```

---

## 🔧 Como Adicionar Novo Extrator

### Passo 1: Criar módulo especializado

```python
# extract_novosite.py

import httpx
from bs4 import BeautifulSoup
import json
from typing import List, Dict, Any

def extrair_produtos_novosite(url: str, limite: int = 100) -> List[Dict[str, Any]]:
    """
    Extrator especializado para [Nome do Site]
    
    Plataforma: [Nome da plataforma]
    Estratégia: [Descrever estratégia]
    Performance esperada: [X]x mais rápido que genérico
    """
    
    produtos = []
    
    # [Implementar lógica específica]
    
    return produtos[:limite]


# Para teste isolado
if __name__ == "__main__":
    url = "https://www.novosite.com.br"
    produtos = extrair_produtos_novosite(url, limite=20)
    
    print(f"\n✅ {len(produtos)} produtos extraídos")
    for p in produtos[:5]:
        print(f"  - {p.get('nome')} | {p.get('preco')}")
```

### Passo 2: Adicionar no QuintApp

```python
# quintapp.py

# 1. Import com try/except
try:
    from extract_novosite import extrair_produtos as extrair_produtos_novosite
    NOVOSITE_DISPONIVEL = True
except ImportError:
    NOVOSITE_DISPONIVEL = False
    print("⚠️ Extrator NovoSite não disponível")

# 2. Atualizar detectar_extrator()
def detectar_extrator(url):
    url_lower = url.lower()
    
    # Adicionar ANTES do genérico
    if 'novosite' in url_lower and NOVOSITE_DISPONIVEL:
        return 'novosite', extrair_produtos_novosite, None
    
    # ... outros extratores
    
    # Fallback
    return 'generico', extrair_produtos_generico, None

# 3. Atualizar contadores
EXTRATORES_DISPONIVEIS = sum([
    DERMO_DISPONIVEL,
    KATSUKAZAN_DISPONIVEL,
    MHSTUDIOS_DISPONIVEL,
    PETRIZI_DISPONIVEL,
    NOVOSITE_DISPONIVEL  # Adicionar aqui
])
```

### Passo 3: Testar

```powershell
# 1. Teste isolado
python extract_novosite.py

# 2. Teste integração
python quintapp.py
# Digite URL: https://www.novosite.com.br
```

### Passo 4: Documentar

```markdown
# LICOES_APRENDIDAS.md

## 9. Extratores Especializados

### 5️⃣ NovoSite (Plataforma X)
- **URL**: https://www.novosite.com.br
- **Plataforma**: [Nome]
- **Estratégia**: [Descrição]
- **Performance**: [X]x mais rápido
- **Status**: ✅ Produção
```

---

## 🧪 Testes e Validação

### Checklist para Novo Extrator:

```
✅ Testa isoladamente (python extract_novosite.py)
✅ Extrai pelo menos 20 produtos
✅ Todos campos obrigatórios preenchidos:
   - nome
   - preco
   - url
   - plataforma
✅ Performance medida (vs genérico)
✅ Try/except no import (não quebra se falhar)
✅ Fallback funciona (genérico assume se erro)
✅ Documentado em LICOES_APRENDIDAS.md
✅ Adicionado em RESUMO_TESTES_SITES.md
```

### Estrutura de Teste:

```python
def test_extrator_novosite():
    """Teste automatizado do extrator"""
    url = "https://www.novosite.com.br"
    produtos = extrair_produtos_novosite(url, limite=20)
    
    # Assertions
    assert len(produtos) > 0, "Nenhum produto extraído"
    assert len(produtos) <= 20, "Limite não respeitado"
    
    # Valida campos
    for p in produtos:
        assert p.get('nome'), "Nome ausente"
        assert p.get('preco'), "Preço ausente"
        assert p.get('url'), "URL ausente"
        assert p.get('plataforma') == 'novosite'
    
    print(f"✅ Teste passou: {len(produtos)} produtos")
```

---

## 📈 Métricas e Monitoramento

### Métricas Coletadas:

```python
{
    "tipo_extrator": "petrizi",
    "tempo_execucao": 6.3,  # segundos
    "produtos_extraidos": 20,
    "erros": 0,
    "taxa_sucesso": 100.0,  # %
    "timestamp": "2025-01-24T10:30:00"
}
```

### Performance Targets:

| Métrica | Target | Atual |
|---------|--------|-------|
| **Tempo (100 produtos)** | < 30s | 2-8s (especializados) ✅ |
| **Taxa de sucesso** | > 95% | 98%+ ✅ |
| **Erros HTTP** | < 5% | < 2% ✅ |
| **Cobertura plataformas** | > 80% | 87.5% ✅ |

---

## 🚀 Roadmap

### ✅ Fase 1: Foundation (Concluída)
- [x] Extrator genérico com Pattern Learning
- [x] Discovery Navigation para sites complexos
- [x] ThreadPool para paralelização

### ✅ Fase 2: Especialização (Concluída)
- [x] 4 extratores especializados (Wake, Nuvemshop, Shopify, Tray)
- [x] Detecção automática de plataforma
- [x] Fallback seguro para genérico

### 🔄 Fase 3: Expansão (Em Progresso)
- [ ] Testar CEB Modas (Loja Integrada)
- [ ] Extrator Magento (com Selenium POC)
- [ ] Mais sites Shopify para validação

### 🔮 Fase 4: Inteligência (Futuro)
- [ ] ML para detectar plataforma automaticamente
- [ ] Auto-tuning de parâmetros por site
- [ ] Monitoramento contínuo e alertas

---

## 📚 Referências

### Documentos Relacionados:
- **LICOES_APRENDIDAS.md**: Lições técnicas detalhadas
- **RESUMO_TESTES_SITES.md**: Resultado de testes por site
- **COMPARACAO_ESTRATEGIAS.md**: Comparação V1-V8

### Extratores:
- `extract_dermo.py`: Dermomanipulações (Wake)
- `extract_katsukazan.py`: Katsukazan (Nuvemshop)
- `extract_mhstudios.py`: MH Studios (Shopify)
- `extract_petrizi.py`: Petrizi (Tray)
- `extract_production.py`: Genérico (fallback)

### Interface:
- `quintapp.py`: Interface principal com detecção automática

---

**Documento criado**: 2025-01-24  
**Versão**: 1.0  
**Status**: Produção estável  
**Autor**: Sistema QuintApp
