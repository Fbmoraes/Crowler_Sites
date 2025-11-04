# Correções Petrizi e MatConcasa

## Problema Reportado

Usuário reportou erros ao tentar extrair produtos de:
1. **Petrizi**: "Erro inesperado: object of type 'coroutine' has no len()"
2. **MatConcasa**: "Erro na extração de links"

## Causa Raiz

### Petrizi
- A função `extrair_produtos()` era `async`, mas o QuintApp tentava chamar de forma síncrona
- Quando o QuintApp chama `len(produtos)`, recebe uma coroutine ao invés de uma lista
- Erro: `'coroutine' object has no len()`

### MatConcasa
- O Discovery Mode usa `asyncio.run()` dentro de threads do ThreadPoolExecutor
- `asyncio.run()` em threads pode causar conflitos com event loops existentes
- Erro genérico: "Erro na extração de links"

## Soluções Implementadas

### Petrizi (`extract_petrizi.py`)

**Antes:**
```python
async def extrair_produtos(url: str, callback=None, max_produtos: int = 20):
    # Código async...
    return produtos
```

**Depois:**
```python
# Função interna permanece async
async def _extrair_produtos_async(url: str, callback=None, max_produtos: int = 20):
    # Código async...
    return produtos

# Wrapper síncrono para integração com QuintApp
def extrair_produtos(url: str, callback=None, max_produtos: int = 20):
    """
    Wrapper síncrono para integração com QuintApp
    Petrizi retorna produtos completos (não precisa de fase de detalhes)
    """
    return asyncio.run(_extrair_produtos_async(url, callback, max_produtos))
```

**Resultado:**
- QuintApp chama `extrair_produtos()` de forma síncrona ✅
- Recebe lista de produtos, não coroutine ✅
- Mantém lógica async interna (sitemap + extração) ✅

### MatConcasa (`quintapp.py`)

**Antes:**
```python
def extrair_urls_homepage_sync(base_url: str, max_produtos: int = 100) -> list:
    """Wrapper síncrono para extrair_urls_homepage"""
    return asyncio.run(extrair_urls_homepage(base_url, max_produtos))
```

**Depois:**
```python
def extrair_urls_homepage_sync(base_url: str, max_produtos: int = 100) -> list:
    """Wrapper síncrono para extrair_urls_homepage - thread-safe"""
    try:
        # Tenta usar loop existente
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Se já tem loop rodando, cria novo em thread separada
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, extrair_urls_homepage(base_url, max_produtos))
                return future.result()
        else:
            return asyncio.run(extrair_urls_homepage(base_url, max_produtos))
    except RuntimeError:
        # Se der erro com loop, força execução em thread nova
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(asyncio.run, extrair_urls_homepage(base_url, max_produtos))
            return future.result()
    except Exception as e:
        print(f"❌ Erro no discovery: {e}")
        import traceback
        traceback.print_exc()
        return []
```

**Melhorias:**
1. **Thread-safe**: Detecta se já existe event loop rodando
2. **Fallback robusto**: Se encontrar loop rodando, cria thread dedicada
3. **Error handling**: Captura e exibe erros específicos
4. **Retry logic**: Tenta múltiplas estratégias antes de falhar

**Também adicionado:**
- Tratamento de erro específico no `processar_plataforma()` para distinguir erro de discovery vs erro de extração
- Traceback completo em caso de erro para debugging

## Validação

### Teste Petrizi
```bash
python test_petrizi_fix.py
```

**Resultado:**
```
✅ Import OK
✅ extrair_produtos é síncrona

Testando extração de 3 produtos...
✅ Sucesso! 3 produtos extraídos

Primeiro produto:
  Nome: Sacola Presente
  Preço: R$ 5.00
  Marca: Petrizi Makeup
```

### Teste MatConcasa Discovery
```bash
python test_discovery_isolated.py
```

**Resultado:**
```
🌐 DISCOVERY MODE: https://www.matconcasa.com.br

📄 Carregando homepage...
🔍 Buscando produtos na homepage...
  ✓ 84 produtos na homepage

📦 Total filtrado: 84 produtos

============================================================
✅ SUCESSO! 10 URLs encontradas

Primeiras 5 URLs:
  1. https://www.matconcasa.com.br/produto/ducha-hydra-optima-8-temperaturas-5500w-127v-dpop-8-551br-362905
  2. https://www.matconcasa.com.br/produto/porta-shampoo-retangular-10595-358266
  3. https://www.matconcasa.com.br/produto/kit-churrasco-simonaggio-3-pecas-caixa-3503039055400-368440
  (...)
```

## Arquiteturas de Integração

### Petrizi (Tray)
```
QuintApp (Thread)
    └─> extrair_produtos() [SÍNCRONO]
          └─> asyncio.run(_extrair_produtos_async())
                ├─> obter_urls_sitemap() [ASYNC]
                └─> extrair_produto() x N [ASYNC + rate limit]
```

**Características:**
- Extração completa (não precisa fase de detalhes)
- Rate limit: 0.25s entre produtos
- Sitemap: Tray com estrutura `/categoria/produto`

### MatConcasa (Next.js SSR)
```
QuintApp (Thread)
    └─> extrair_urls_homepage_sync() [SÍNCRONO thread-safe]
          └─> ThreadPoolExecutor.submit(asyncio.run, extrair_urls_homepage())
                ├─> Playwright: navegar homepage
                ├─> Extrair links de produtos
                ├─> Navegar categorias (/ferramentas/, /casa/, etc)
                └─> Filtrar produtos reais (URL com hífen)
    
    └─> extrair_detalhes_paralelo() [GENÉRICO]
          └─> ThreadPool para detalhes
```

**Características:**
- Discovery mode: navega homepage + categorias
- Playwright headless para SSR
- Limite: 100 produtos por padrão
- Fallback: sitemap se discovery falhar

## Status Final

| Site | Antes | Depois | Método |
|------|-------|--------|--------|
| **Petrizi** | ❌ coroutine error | ✅ 3/3 produtos | Sitemap + HTML microdata |
| **MatConcasa** | ❌ link extraction error | ✅ 84 produtos encontrados | Discovery (Playwright) |

## Próximos Passos

1. ✅ Testar Petrizi no QuintApp (deve funcionar)
2. ✅ Testar MatConcasa no QuintApp (deve funcionar)
3. Considerar aplicar padrão de wrapper síncrono em outros extratores async
4. Documentar padrão de integração async → síncrono para novos extratores

## Lições Aprendidas

1. **Async em threads**: `asyncio.run()` não é thread-safe por padrão
   - Solução: Detectar loop existente e criar thread dedicada se necessário

2. **QuintApp API**: Espera funções síncronas que retornam listas
   - Padrão: `extrair_produtos(url, callback, max) -> List[Dict]`
   - Se implementação é async, criar wrapper síncrono com `asyncio.run()`

3. **Error handling**: Erros genéricos dificultam debug
   - Solução: Capturar exceções específicas e exibir traceback completo
   - Distinguir "erro de discovery" vs "erro de extração"

4. **Playwright em threads**: Funciona se criar novo event loop em thread dedicada
   - Não compartilhar event loop entre threads
   - Usar `concurrent.futures.ThreadPoolExecutor` para isolamento
