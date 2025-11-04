# Correções Aplicadas - QuintApp

## Problema Identificado

**Freixenet**: Encontrava apenas 4 produtos dos 101 reais  
**Sacada**: Não encontrava nenhum produto  
**Gigabarato**: Funcionava perfeitamente (733 produtos)

---

## Diagnóstico

### Freixenet
- **Problema**: Sitemap tem estrutura de **índice** (sitemap.xml aponta para outros XMLs)
- **Estrutura encontrada**:
  ```
  sitemap.xml
  ├── brand-0.xml (14 URLs - marcas)
  ├── category-0.xml (8 URLs - categorias)
  ├── custom-user-routes-1.xml (72 URLs - receitas/institucional)
  └── product-0.xml (101 URLs - PRODUTOS) ✅
  ```
- **Causa**: V8 não expandia sitemaps recursivamente
- **URLs dos produtos**: Todas terminam em `/p` (padrão VTEX)

### Sacada
- **Problema**: DNS não resolve (site offline ou domínio inválido)
- **Tentativas**:
  - `https://www.sacada.com.br` ❌
  - `https://sacada.com.br` ❌
  - `http://www.sacada.com.br` ❌
  - `http://sacada.com.br` ❌
- **Resultado**: `[Errno 11001] getaddrinfo failed`
- **Ação**: Removido da lista padrão

---

## Solução Implementada

### 1. Expansão Recursiva de Sitemaps

**Arquivo**: `extract_linksv8.py`

**Mudança**:
```python
async def buscar_sitemap(base_url: str) -> List[str]:
    # Detecta se sitemap.xml é um ÍNDICE
    if urls and any('.xml' in u for u in urls):
        # Expande recursivamente cada sitemap filho
        for sitemap_filho in urls:
            if '.xml' in sitemap_filho:
                # Busca URLs do sitemap filho
                urls_filho = ...
                
                # PRIORIZA sitemap de produtos
                if 'product' in sitemap_filho.lower():
                    # Pega TODAS as URLs do sitemap de produtos
                    urls_produto = [u for u in urls_filho if '.xml' not in u]
                else:
                    # Outros sitemaps: filtra apenas URLs de produto
                    urls_produto = [u for u in urls_filho 
                                   if u.endswith('/p') or '/produto' in u]
```

**Resultado**:
- ✅ Freixenet: **101 produtos** (100% correto!)
- ✅ Gigabarato: **733 produtos** (mantido)

---

## Testes Realizados

### Freixenet (ANTES da correção)
```
Sitemap: 195 URLs
Produtos: 149 (inclui receitas, marcas, páginas institucionais)
```

### Freixenet (DEPOIS da correção)
```
Sitemap index detectado: 4 sitemaps filhos
  → product-0.xml: 101 URLs ✅
Produtos: 101 (apenas produtos reais!)
```

---

## Sites Atualizados no QuintApp

**Lista padrão** (10 plataformas):

1. ✅ **Gigabarato** (VTEX) - 733 produtos
2. ✅ **Freixenet** (VTEX) - 101 produtos
3. ⏳ **Dermomanipulações** (VTEX)
4. ⏳ **MH Studios** (Shopify)
5. ⏳ **Katsukazan** (Nuvemshop)
6. ⏳ **Petrizi** (Tray)
7. ⏳ **Artistas do Mundo** (Magento)
8. ⏳ **Magnum Auto** (WooCommerce)
9. ⏳ **EMC Medical** (Wix)
10. ⏳ **C&B Modas** (Loja Integrada)

**Removido**:
- ❌ **Sacada** (DNS não resolve)

---

## Próximos Passos

Para garantir que TODOS os sites funcionem, seria ideal testar um por um:

1. **Dermomanipulações** - Verificar estrutura do sitemap
2. **MH Studios** (Shopify) - Pode precisar lógica específica
3. **Katsukazan** (Nuvemshop) - Verificar padrões de URL
4. **Petrizi** (Tray) - Testar sitemap
5. **Artistas do Mundo** (Magento) - Verificar estrutura
6. **Magnum Auto** (WooCommerce) - Padrões WordPress
7. **EMC Medical** (Wix) - Pode precisar JavaScript rendering
8. **C&B Modas** (Loja Integrada) - Verificar sitemap

**Comando para testar um por um**:
```python
from extract_linksv8 import extrair_produtos

def callback(msg):
    print(msg)

produtos = extrair_produtos("https://url-do-site.com.br", callback)
print(f"Total: {len(produtos)} produtos")
```

---

## Lições Aprendidas

1. **Sitemaps podem ser índices**: Sempre verificar se tem `.xml` nas URLs
2. **Expansão recursiva é essencial**: Muitos sites grandes usam índices
3. **Priorizar sitemap de produtos**: `product.xml` > outros XMLs
4. **Filtros inteligentes**: Sites com índice têm sitemaps específicos (brand, category, product)
5. **DNS pode falhar**: Sempre validar que o domínio está acessível

---

## Performance Esperada

Com a correção:
- **Gigabarato**: ~45s (733 produtos)
- **Freixenet**: ~30s (101 produtos)
- **Total 10 sites**: ~3-5 minutos em paralelo (4 CPUs)
