# Extract Production v2 - Com Homepage SSR Discovery

## Novidades

Adicionei a lógica de **Homepage SSR Discovery** (estilo MatConcasa) no `extract_production_v2.py`.

### O que mudou?

1. **Dois modos de operação**:
   - **Modo Arquivo** (original): `python extract_production_v2.py urls.txt saida.json`
   - **Modo Discovery** (NOVO): `python extract_production_v2.py https://site.com/ saida.json --discovery`

2. **Homepage SSR Discovery**:
   - Abre a homepage do site
   - Extrai todos os links de produtos visíveis (`/produto/`, `/product/`)
   - Navega em categorias principais para encontrar mais produtos
   - Filtra produtos reais (remove categorias)
   - Retorna até 100 URLs

### Quando usar Discovery?

Use quando o site:
- ✅ Tem **sitemap com categorias** (não produtos diretos)
- ✅ Usa **Next.js SSR** (produtos visíveis no HTML)
- ✅ Tem **produtos na homepage** carregados por SSR

**Exemplo**: MatConcasa
- Sitemap tem 21K URLs (todas categorias)
- Homepage tem 81 produtos SSR
- Discovery encontra 100+ produtos navegando

### Velocidade

| Modo | Performance |
|------|-------------|
| **Arquivo** | ~0.7-1s/produto ⚡ |
| **Discovery** | Homepage: ~30-60s | Extração: ~0.7-1s/produto ⚡ |

**Total com Discovery**: ~2 min para 100 produtos

### Exemplos de Uso

#### 1. Modo tradicional (arquivo de URLs)
```bash
python extract_production_v2.py urls_matcon_100.txt resultados.json
```

#### 2. Modo discovery (extrai URLs automaticamente)
```bash
python extract_production_v2.py https://www.matconcasa.com.br/ resultados.json --discovery
```

#### 3. Teste com 5 produtos (discovery)
```bash
python extract_production_v2.py https://www.site.com/ teste.json --discovery
# Edita o código para max_produtos=5 na linha: urls = await extrair_urls_homepage(base_url, max_produtos=5)
```

### Lógica do Discovery

```python
1. Abre homepage
   └─ Extrai todos <a href="/produto/">
   
2. Se < 100 produtos:
   ├─ Tenta /ferramentas/
   ├─ Tenta /casa/
   ├─ Tenta /cozinha/
   ├─ Tenta /banheiro/
   ├─ Tenta /construcao/
   └─ Scroll + extrai mais links
   
3. Filtra produtos reais:
   ├─ Remove categorias (sem hífen no nome)
   ├─ Remove URLs curtas (<10 chars)
   └─ Retorna top 100
```

### Output

O arquivo JSON agora inclui metadata sobre o modo:

```json
{
  "metadata": {
    "site": "matconcasa.com.br",
    "modo_extracao": "discovery",  // ← NOVO
    "total_urls": 82,
    "sucesso": 78,
    "taxa_sucesso": "95.1%",
    "tempo_total_segundos": 68.4,
    "velocidade_media_segundos": 0.832
  },
  "produtos": [...]
}
```

### Vantagens

1. **Sem preparação**: Não precisa gerar arquivo de URLs
2. **Automático**: Encontra produtos sozinho
3. **Flexível**: Funciona com sites SSR (Next.js, Nuxt, etc)
4. **Rápido**: Discovery é paralelo (não bloqueia)

### Limitações

1. **Apenas SSR**: Não funciona com sites 100% JavaScript (precisa Selenium)
2. **Limitado**: Máximo ~100-150 produtos (homepage + algumas categorias)
3. **Heurístico**: Pode não encontrar todas categorias

### Quando usar cada modo?

| Situação | Modo Recomendado |
|----------|------------------|
| **Sitemap com produtos** | Arquivo (`extract_linksv8.py` → `extract_production_v2.py`) |
| **Sitemap com categorias + SSR** | Discovery (`extract_production_v2.py --discovery`) |
| **Site 100% JavaScript** | Criar extrator especializado (Selenium/Apollo Cache) |
| **Teste rápido de site novo** | Discovery (mais rápido para testar) |

### Comparação com extract_production.py

| Feature | v1 (original) | v2 (com discovery) |
|---------|---------------|---------------------|
| Entrada | Apenas arquivo | Arquivo OU URL |
| Discovery | ❌ Não | ✅ Sim (MatConcasa style) |
| Velocidade extração | ~0.7-1s | ~0.7-1s (igual) |
| Concorrência | 30 | 30 (igual) |
| Output | JSON | JSON + metadata de modo |

### Recomendação

1. **Use v2** para sites novos (permite testar rápido com discovery)
2. **Use v1** se já tem arquivo de URLs (mais simples)
3. **Discovery é ideal** para sites estilo MatConcasa (SSR + sitemap de categorias)

---

## Conclusão

A lógica do MatConcasa (homepage SSR + navegação) agora está integrada no `extract_production_v2.py` como **modo discovery**. Isso permite:

- ✅ Testar sites novos rapidamente
- ✅ Extrair sem preparar arquivo de URLs
- ✅ Funcionar com sites SSR que não têm sitemap de produtos
- ✅ Manter a mesma velocidade de extração (~0.7-1s/produto)

**Vale a pena implementar**: O overhead do discovery (~30-60s) é pequeno comparado ao tempo salvo por não precisar preparar URLs manualmente.
