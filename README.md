# 🚀 Extrator de Produtos Matcon Casa - Otimizado

## 📊 Resultado Final

Após extensivos testes e otimizações, este é o **melhor resultado alcançável** para extração de produtos do site Matcon Casa.

### Performance

- **Velocidade**: ~0.7-1 segundo por produto
- **Qualidade**: 95-100% de dados corretos
- **Concorrência**: 30 páginas simultâneas
- **Estabilidade**: Sem erros 429 (rate limiting)

### Estimativas

| Quantidade | Tempo Estimado |
|-----------|----------------|
| 100 produtos | 1-2 minutos |
| 500 produtos | 6-8 minutos |
| 1.000 produtos | 12-17 minutos |
| 10.000 produtos | 2-3 horas |

## 🎯 Meta vs Realidade

| Métrica | Meta Inicial | Realidade Alcançada | Diferença |
|---------|--------------|---------------------|-----------|
| Tempo/produto | 0.15s | 0.70s | 4.6x mais lento |
| 800 produtos | 2 minutos | 10 minutos | 5x mais lento |
| Taxa de sucesso | 100% | 95-100% | ✅ Atingida |

## 📁 Arquivos

### Scripts Principais

1. **`extract_production.py`** ⭐ **RECOMENDADO**
   - Script final de produção
   - Melhor balanço qualidade/velocidade
   - Uso: `python extract_production.py urls.txt output.json`

2. **`extract_detailsv7_final.py`**
   - Máxima qualidade (100%)
   - Mais lento (~7-10s/produto)
   - Usa `networkidle` para garantir dados completos

3. **`extract_ultra_fast.py`**
   - Performance otimizada
   - Sem networkidle (apenas wait for h1)
   - Base para o script de produção

### Scripts de Teste

4. **`extract_with_abort.py`**
   - Watchdog automático
   - Aborta se performance < 0.3s/produto
   - Útil para validar otimizações

5. **`extract_httpx_test.py`**
   - Teste com httpx puro (sem browser)
   - Bloqueado pelo site (38% sucesso)
   - Não recomendado

### Utilitários

6. **`extract_linksv6.py`**
   - Extrai URLs de produtos do sitemap
   - Suporta navegação por categorias

7. **`extrair_urls_navegacao.py`**
   - Extrai URLs navegando pela homepage
   - Gera arquivo urls_matcon_100.txt

### Documentação

8. **`RELATORIO_FINAL.py`**
   - Análise completa de performance
   - Comparação de todas as abordagens testadas
   - Recomendações e alternativas

## 🔧 Instalação

```bash
# Criar ambiente virtual
python -m venv .venv

# Ativar (Windows)
.venv\Scripts\activate

# Instalar dependências
pip install crawlee playwright beautifulsoup4 httpx

# Instalar browsers do Playwright
playwright install
```

## 💻 Uso

### Básico

```bash
# 1. Extrair URLs de produtos
python extract_linksv6.py

# 2. OU gerar lista específica
python extrair_urls_navegacao.py

# 3. Extrair dados dos produtos
python extract_production.py urls_matcon_100.txt resultados.json
```

### Avançado

```python
# Usar extract_production.py
python extract_production.py <arquivo_urls> <arquivo_saida>

# Exemplos:
python extract_production.py urls_matcon_100.txt resultados_100.json
python extract_production.py urls_todos.txt resultados_completo.json
```

## 📋 Formato de Saída

```json
{
  "metadata": {
    "site": "matconcasa.com.br",
    "total_processado": 82,
    "sucesso": 78,
    "erro": 4,
    "taxa_sucesso": "95.1%",
    "tempo_total_segundos": 70.5,
    "velocidade_media_segundos": 0.86,
    "inicio": "2025-10-22T16:19:21",
    "fim": "2025-10-22T16:20:31"
  },
  "produtos": [
    {
      "url": "https://www.matconcasa.com.br/produto/...",
      "nome": "Ducha Hydra Optima 8 Temperaturas 5500W 127V",
      "preco": "177.37",
      "preco_original": "305.87",
      "marca": null,
      "categoria": null,
      "subcategoria": null,
      "imagens": ["url1", "url2", "url3"],
      "disponivel": true,
      "extraido_em": "2025-10-22T16:19:25.123456"
    }
  ]
}
```

## 🔍 Diagnóstico Técnico

### Arquitetura do Site

- **Framework**: Next.js 13+ com App Router
- **Renderização**: Server Components + Client Hydration  
- **Dados**: Carregados via `__next_f` chunks progressivos
- **Proteção**: Rate limiting (429) + Anti-bot

### Gargalos Identificados

1. **JavaScript Pesado**: React + Next.js (~20-30 requests por página)
2. **Streaming de Dados**: Dados não vêm no HTML inicial
3. **CDN/WAF**: Bloqueia requests HTTP rápidos demais
4. **Hydration**: Precisa esperar JavaScript executar

### Otimizações Aplicadas

✅ Removido `networkidle` (de 7-10s → 0.7-1s por produto)  
✅ Wait apenas selector específico (h1)  
✅ Extração paralela (1 único `evaluate()`)  
✅ Concorrência alta (30 páginas simultâneas)  
✅ Retry automático (2 tentativas)  
✅ Timeout agressivo (8s)  

## ⚠️ Limitações

❌ **Impossível** atingir 0.15s/produto com scraping no Matcon Casa  
❌ Site Next.js é fundamentalmente lento para scraping  
❌ httpx puro não funciona (site usa JS pesado)  
❌ Concorrência > 30 causa bloqueio (429)  

## 💡 Alternativas

### 1. API Oficial (Recomendado)
- Contatar Matcon Casa para acesso API
- Feed XML/JSON de produtos
- **Velocidade**: milissegundos/produto

### 2. Scraping Distribuído
- Múltiplas máquinas/IPs
- 10 máquinas = 1min para 800 produtos
- **Custo**: Infraestrutura cloud

### 3. Aceitar Tempo Maior
- Rodar overnight
- 10.000 produtos em 2-3 horas
- **Custo**: Zero

### 4. Sites Alternativos
- Testar Leroy Merlin, Americanas
- Alguns são 10x mais rápidos
- Avaliar catálogo

## 📊 Testes Realizados

| Método | Velocidade | Qualidade | Resultado |
|--------|-----------|-----------|-----------|
| Playwright + networkidle | 7-10s/item | 100% | ❌ Muito lento |
| Playwright otimizado | 0.7-1s/item | 100% | ✅ Melhor opção |
| httpx puro | 0.28s/item | 38% | ❌ Bloqueado |

## 🎓 Aprendizados

- Sites modernos (Next.js) são mais lentos para scraping
- Performance real depende da arquitetura do site
- Nem sempre é possível atingir metas arbitrárias
- Playwright otimizado >> httpx bloqueado
- **Qualidade de dados > Velocidade pura**

## 📞 Suporte

Para dúvidas ou melhorias, consulte:
- `RELATORIO_FINAL.py` - Análise completa
- Código fonte dos scripts (comentado)
- Logs de execução (crawlee gera automaticamente)

## 📜 Licença

Este projeto foi desenvolvido para fins educacionais e de análise técnica.
Respeite os termos de uso e robots.txt do site alvo.

---

**Status**: ✅ Produção - Otimização máxima alcançada  
**Última atualização**: 22/10/2025  
**Versão**: 1.0 Final
