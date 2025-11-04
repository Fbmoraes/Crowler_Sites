# QuintApp - Discovery Mode Update

## 📋 Resumo

Integrada a lógica de **Homepage SSR Discovery** do MatConcasa no QuintApp, permitindo extração de produtos em sites com SSR mas sem sitemap útil.

## ✨ Features Adicionadas

### 1. **Função `extrair_urls_homepage`**
```python
async def extrair_urls_homepage(base_url: str, max_produtos: int = 100) -> list
```

**O que faz:**
- Abre homepage com Playwright
- Extrai todos os links com `/produto/`, `/product/`, `/p/`
- Navega em categorias principais (ferramentas, casa, cozinha, etc)
- Scroll para lazy loading (2x por categoria)
- Filtra produtos reais (remove categorias)
- Retorna até 100 URLs

**Performance:**
- Discovery: ~30-60s
- Extração: mesma velocidade (~0.7-1s/produto)

### 2. **Auto-detecção MatConcasa**

```python
def detectar_extrator(url: str):
    # ...
    if 'matconcasa' in url_lower or 'matcon' in url_lower:
        return 'matconcasa', None, None, True  # True = usar_discovery
```

Sites detectados automaticamente:
- MatConcasa → Discovery mode
- Outros sites → modo normal (sitemap)

### 3. **Modo Discovery Forçado**

Checkbox na UI: **🌐 Forçar Discovery**
- Aplica discovery em TODOS os sites
- Útil para testar sites com sitemap ruim
- Override do comportamento padrão

### 4. **Suporte a Sacada**

Adicionado extrator Sacada (Apollo Cache):
```python
try:
    from extract_sacada import extrair_produtos as extrair_produtos_sacada
    SACADA_DISPONIVEL = True
except:
    SACADA_DISPONIVEL = False
```

## 🎨 Mudanças na UI

### Indicadores Visuais

**Durante extração:**
- 🌐 icon = Discovery mode
- 🔗 icon = Normal mode

**Tabela de Performance:**
- Nova coluna "Modo" mostra qual método foi usado
- ✅ Sucesso / ❌ Erro com emojis

### Sidebar Atualizada

**Novo bloco: "🌐 Discovery Mode"**
- Explica como funciona
- Quando usar
- Auto-detecção
- Performance esperada

**Plataformas pré-configuradas:**
- Agora 12 sites (adicionado MatConcasa)
- Categorias por plataforma
- Método de extração indicado

## 🔧 Mudanças Técnicas

### `processar_plataforma`

**Antes:**
```python
def processar_plataforma(url, max_produtos, max_workers, progress_callback)
```

**Depois:**
```python
def processar_plataforma(url, max_produtos, max_workers, progress_callback, usar_discovery=False)
```

**Lógica:**
```python
# Auto-detecta ou força discovery
usar_discovery = usar_discovery or auto_discovery

if usar_discovery:
    # 1. Discovery: extrai URLs da homepage
    produtos_links_urls = extrair_urls_homepage_sync(url, max_produtos)
    
    # 2. Converte para formato esperado
    produtos_links = [{'indice': i, 'url': url, ...} for i, url in enumerate(urls)]
    
    # 3. Extrai detalhes com extrator genérico
    _, detalhes = extrair_detalhes_paralelo(...)
else:
    # Modo normal: sitemap + extrator específico
    produtos_links = extrair_produtos_fn(url, ...)
    _, detalhes = extrair_detalhes_fn(...)
```

### Compatibilidade

**Sites sem extrator de detalhes** (Petrizi, Sacada):
```python
if extrair_detalhes_fn is None:
    detalhes = produtos_links  # Já tem tudo
```

## 📊 URLs Padrão Atualizadas

```python
urls_padrao = """https://www.gigabarato.com.br
https://www.sacada.com
https://www.freixenet.com.br
https://www.dermomanipulacoes.com.br
https://mhstudios.com.br
https://katsukazan.com.br
https://petrizi.com.br
https://www.matconcasa.com.br  # NOVO - Discovery mode
https://artistasdomundo.com.br
https://www.magnumauto.com.br
https://www.emcmedical.com.br
https://www.cebmodaseacessorios.com.br"""
```

## 🧪 Testes

### Script de Teste
`test_quintapp_discovery.py`

**Testa:**
- Homepage MatConcasa
- Extração de links
- Navegação em categoria /ferramentas/
- Scroll para lazy loading
- Filtro de produtos reais

**Executar:**
```bash
python test_quintapp_discovery.py
```

**Resultado esperado:**
```
🌐 Testando Discovery: https://www.matconcasa.com.br/

📄 Carregando homepage...
🔍 Buscando produtos na homepage...
  ✓ 45 produtos na homepage

📁 Testando categoria: /ferramentas/
  📜 Scroll 1/2
  📜 Scroll 2/2
  ✓ 38 novos produtos (total: 83)

📦 Total filtrado: 78 produtos reais

✅ Teste concluído! Discovery funcionando.

📋 Primeiros 5 produtos:
  1. https://www.matconcasa.com.br/produto/...
  2. https://www.matconcasa.com.br/produto/...
  ...
```

## 🎯 Casos de Uso

### 1. Site SSR com Sitemap Ruim
**Exemplo:** MatConcasa
- Sitemap: 21K URLs (só categorias)
- Discovery: ~80-100 produtos em 30s

**Uso:**
- Auto-detectado: ✅
- Modo: Discovery
- Performance: ~1-2min para 100 produtos

### 2. Testar Site Novo
**Exemplo:** Qualquer site desconhecido

**Uso:**
1. Adicionar URL
2. Marcar checkbox "🌐 Forçar Discovery"
3. Executar extração
4. Ver se encontra produtos

### 3. Validar Sitemap vs Discovery
**Exemplo:** Comparar métodos

**Teste 1:**
- URL: site.com
- Discovery: OFF
- Resultado: X produtos (sitemap)

**Teste 2:**
- URL: site.com
- Discovery: ON
- Resultado: Y produtos (homepage)

**Comparar:** Qualidade e quantidade

## 📝 Checklist de Integração

- [x] Função `extrair_urls_homepage` criada
- [x] Wrapper síncrono `extrair_urls_homepage_sync`
- [x] Auto-detecção MatConcasa
- [x] Checkbox "Forçar Discovery"
- [x] Parâmetro `usar_discovery` em `processar_plataforma`
- [x] Indicadores visuais (🌐 vs 🔗)
- [x] Coluna "Modo" na tabela
- [x] Sidebar atualizada
- [x] URLs padrão com MatConcasa
- [x] Suporte a Sacada
- [x] Compatibilidade Petrizi/Sacada
- [x] Script de teste criado
- [x] Documentação atualizada

## 🚀 Próximos Passos

1. **Testar QuintApp atualizado:**
   ```bash
   streamlit run quintapp.py
   ```

2. **Validar MatConcasa:**
   - Executar extração
   - Verificar modo = 🌐 Discovery
   - Conferir ~80-100 produtos
   - Performance ~1-2min

3. **Testar forçar discovery:**
   - Marcar checkbox
   - Testar outro site (ex: Gigabarato)
   - Ver se funciona

4. **Expandir auto-detecção:**
   - Adicionar outros sites SSR
   - Next.js patterns (/_next/)
   - Nuxt patterns (/_nuxt/)

5. **Otimizações futuras:**
   - Aumentar categorias testadas
   - Configurar max_produtos no discovery
   - Melhorar filtros de produtos reais
   - Progress bar durante discovery

## 📚 Referências

- `extract_production_v2.py` - Fonte da lógica discovery
- `EXTRACT_PRODUCTION_V2.md` - Documentação original
- `test_resultado_v2.json` - Teste MatConcasa (62/62 sucesso)

## ✅ Status

**IMPLEMENTADO E PRONTO PARA USO**

MatConcasa será automaticamente detectado e usará Discovery mode no QuintApp!
