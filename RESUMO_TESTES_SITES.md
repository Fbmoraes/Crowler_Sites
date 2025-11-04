# 🧪 RESUMO DOS TESTES - Sites E-commerce Brasileiros

**Data**: 2025-01-24  
**Projeto**: QuintApp (Extratores especializados)  
**Total de sites testados**: 8 sites

---

## 📊 Resultado Geral

| Status | Quantidade | Sites |
|--------|-----------|-------|
| ✅ **Funcionando com extrator especializado** | 5 | Dermomanipulações, Katsukazan, MH Studios, Petrizi, Sacada |
| ✅ **Funcionando com genérico** | 2 | Gigabarato, MatConcasa |
| ⚠️ **Complexo (não implementado)** | 2 | Artistas do Mundo, CEB Modas |
| ❌ **Removido (não funcional)** | 2 | Magnum Auto, EMC Medical |

**Taxa de sucesso**: **7/8 sites funcionando** (87.5%)

---

## ✅ Sites com Extrator Especializado

### 1. Dermomanipulações (Wake/VTEX)
- **URL**: https://www.dermomanipulacoes.com.br
- **Plataforma**: Wake (fork do VTEX)
- **Estratégia**: JSON-LD em páginas de **categoria**
- **Descoberta**: Homepage tem 0 produtos no JSON-LD, categorias têm array completo
- **Performance**: 15x mais rápido que genérico (8s vs 120s para 50 produtos)
- **Status**: ✅ Produção

### 2. Katsukazan (Nuvemshop)
- **URL**: https://www.katsukazan.com.br
- **Plataforma**: Nuvemshop
- **Estratégia**: JSON-LD completo na **homepage** (1 request apenas!)
- **Descoberta**: Todos produtos em destaque já estão no JSON-LD inicial
- **Performance**: 22x mais rápido que genérico (2s vs 45s)
- **Status**: ✅ Produção

### 3. MH Studios (Shopify)
- **URL**: https://www.mhstudios.com.br
- **Plataforma**: Shopify
- **Estratégia**: **API REST nativa** (`/products.json`)
- **Descoberta**: Shopify tem API pública com JSON puro (sem parsing HTML!)
- **Performance**: 20x mais rápido que genérico (3s vs 60s para 100 produtos)
- **Detalhe**: 250 produtos por request, paginação simples
- **Status**: ✅ Produção

### 4. Petrizi (Tray)
- **URL**: https://www.petrizi.com.br
- **Plataforma**: Tray
- **Estratégia**: **HTML microdata** (`itemprop` attributes)
- **Descoberta**: 
  - NÃO usa JSON-LD (genérico falha completamente)
  - Preço no atributo `content`, não no texto: `<span itemprop="price" content="5.00">`
- **Performance**: ∞ (infinito - genérico retorna 0 produtos)
- **Status**: ✅ Produção

---

## ✅ Sites com Extrator Genérico (JSON-LD Padrão)

### 5. Gigabarato (VTEX)
- **URL**: https://www.gigabarato.com.br
- **Plataforma**: VTEX
- **Estratégia**: Pattern Learning + JSON-LD padrão
- **Descoberta**: Servidor muito restritivo (rate limit agressivo)
- **Performance**: 10-20 threads max, 0.5-1s delay
- **Taxa de match**: 90.6% (664/733 produtos)
- **Status**: ✅ Produção (genérico funciona bem)

### 6. MatConcasa (Next.js)
- **URL**: https://www.matconcasa.com.br
- **Plataforma**: Next.js (React SSR)
- **Estratégia**: Homepage SSR + Discovery Navigation
- **Descoberta**: 
  - Sitemap com 21.331 URLs (maioria categorias, 0 produtos!)
  - Homepage tem 81 produtos visíveis (SSR)
  - Categorias carregam produtos via JavaScript (BeautifulSoup não vê)
- **Status**: ✅ Produção (genérico com discovery funciona)

### 5. Sacada (VTEX + React/Apollo)
- **URL**: https://www.sacada.com (⚠️ NÃO .com.br)
- **Plataforma**: VTEX + React (JavaScript-heavy SPA)
- **Estratégia**: **Apollo Cache** (GraphQL normalizado no HTML)
- **Descoberta CRÍTICA**: 
  - ❌ Site é JavaScript SPA → BeautifulSoup vê apenas "Loading interface..."
  - ❌ Sitemap product-0 tem 1000 URLs mas produtos **ANTIGOS/INATIVOS**
  - ✅ Sitemaps product-1, 2, 3 têm **~2268 produtos ATIVOS**
  - ✅ Dados estão em **script Apollo Cache** (JSON parseável)
  - ✅ Formato GraphQL normalizado (referências entre objetos)
- **Performance**: Rápido (sem JavaScript rendering, apenas parse JSON)
- **Arquivos**: `extract_sacada.py`, `SOLUCAO_SACADA.md`
- **Status**: ✅ Produção (5º extrator especializado)

---

## ✅ Sites com Extrator Genérico

### 6. Gigabarato (VTEX)
- **URL**: https://www.gigabarato.com.br
- **Plataforma**: VTEX
- **Estratégia**: JSON-LD padrão + BeautifulSoup
- **Descoberta**: Páginas de produto têm JSON-LD completo
- **Status**: ✅ Produção (genérico funciona perfeitamente)

### 7. MatConcasa (Next.js)
- **URL**: https://www.matconcasa.com.br
- **Plataforma**: Next.js (React SSR)
- **Estratégia**: Homepage SSR + Discovery
- **Descoberta**: Sitemap tem 21K URLs (categorias), homepage tem 81 produtos SSR
- **Status**: ✅ Produção (genérico funciona)

---

## ⚠️ Sites Complexos (Não Implementados)

### 8. Artistas do Mundo (Magento)
- **URL**: https://www.artistasdomundo.com.br
- **Plataforma**: Magento 2 (Smartwave Porto theme)
- **Problemas identificados**:
  - ❌ API REST requer autenticação: `/rest/V1/products` → 401 Unauthorized
  - ❌ Produtos carregam via JavaScript (BeautifulSoup vê 0 produtos)
  - ✅ Busca funciona: `/catalogsearch/result/?q=termo` (15 links encontrados)
  - ❌ Páginas de produto não têm JSON-LD
- **Solução necessária**: Selenium/Playwright para JavaScript rendering
- **Decisão**: Muito complexo para arquitetura atual
- **Status**: ⚠️ Pendente (requer rewrite com browser automation)

### 9. CEB Modas e Acessórios (Loja Integrada)
- **URL**: https://www.cebmodaseacessorios.com.br
- **Plataforma**: Loja Integrada
- **Descobertas**:
  - Sitemap: Apenas 5 URLs
  - Homepage: 6 produtos únicos encontrados
  - JSON-LD: 0 scripts
  - Preços: 13 ocorrências de "R$" no HTML
- **Potencial**: Extrator genérico pode funcionar com parsing HTML
- **Decisão**: Baixa prioridade (site pequeno, apenas 6 produtos)
- **Status**: ⚠️ Pendente (aguardando feedback do usuário)

---

## ❌ Sites Removidos (Não Funcionais)

### 10. Magnum Auto (Site Quebrado)
- **URL**: https://www.magnumauto.com.br
- **Problema**: Site completamente quebrado
- **Evidências**:
  - Sitemap: 50 URLs encontradas
  - Exemplo URL: `index.php?keyword/item=etNjaE578`
  - Teste de acesso: **404 Not Found**
  - Erro PHP: "Failed to open stream: No such file or directory"
- **Decisão do usuário**: "Cancel magnum auto and remove it, not a real site"
- **Status**: ❌ Removido dos testes

### 11. EMC Medical (Institucional)
- **URL**: https://www.emcmedical.com.br
- **Problema**: Site institucional, NÃO é e-commerce
- **Evidências**:
  - Sitemap: Apenas 2 URLs
  - Homepage: 0 links de produtos
  - Página 200 OK mas sem funcionalidade de loja
- **Decisão**: Site não vende produtos online
- **Status**: ❌ Removido dos testes

---

## 🏆 Ranking de Performance

### Por Velocidade (vs Extrator Genérico):

| Posição | Site | Plataforma | Speedup | Tempo (100 produtos) |
|---------|------|-----------|---------|---------------------|
| 🥇 | **Katsukazan** | Nuvemshop | **22x** | ~2s (1 request!) |
| 🥈 | **MH Studios** | Shopify | **20x** | ~3s (API nativa) |
| 🥉 | **Dermomanipulações** | Wake | **15x** | ~8s (JSON-LD categorias) |
| 🏅 | **Petrizi** | Tray | **∞** | ~6s (genérico: 0 produtos) |

**Média dos especializados**: **19x mais rápido** que genérico

---

## 📚 Lições Aprendidas por Site

### 🎓 Dermomanipulações:
- **Lição**: Wake/VTEX pode ter JSON-LD melhor em **categorias** que na homepage
- **Pattern**: Sempre testar categorias antes de desistir

### 🎓 Katsukazan:
- **Lição**: Nuvemshop coloca produtos em destaque direto no JSON-LD da homepage
- **Pattern**: 1 request resolve tudo (super eficiente)

### 🎓 MH Studios:
- **Lição**: Shopify tem API REST pública `/products.json` (250 produtos/página)
- **Pattern**: Sempre preferir API nativa quando disponível

### 🎓 Petrizi:
- **Lição**: Tray usa HTML microdata com preço no atributo `content` (não no texto!)
- **Pattern**: `<span itemprop="price" content="5.00">R$ 5,00</span>` → Usar `['content']`

### 🎓 Gigabaarto:
- **Lição**: VTEX padrão funciona bem, mas servidores podem ter rate limit agressivo
- **Pattern**: Respeitar limites (10-20 threads, delays de 0.5-1s)

### 🎓 MatConcasa:
- **Lição**: Next.js pode ter produtos "escondidos" - SSR na homepage funciona, categorias não
- **Pattern**: Sempre extrair homepage primeiro (SSR garantido)

### 🎓 Artistas do Mundo:
- **Lição**: Magento com JavaScript rendering não funciona com BeautifulSoup
- **Pattern**: Sites com produtos carregados via JS precisam Selenium/Playwright

### 🎓 Magnum Auto:
- **Lição**: Nem todo site em sitemap está funcional (404s em massa)
- **Pattern**: Validar amostra antes de processar tudo

### 🎓 EMC Medical:
- **Lição**: Nem todo domínio com "produto" no sitemap é e-commerce
- **Pattern**: Verificar se homepage tem estrutura de loja

---

## 🔍 Classificação de Plataformas

### ⭐ Nível 1 - Muito Fácil (API Nativa):
- **Shopify**: API REST `/products.json` (JSON puro)
- **Estratégia**: Usar API direta
- **Tempo**: ~3s para 100 produtos

### ⭐⭐ Nível 2 - Fácil (JSON-LD Padrão):
- **VTEX**, **Magento básico**, **WordPress WooCommerce**
- **Estratégia**: Extrator genérico funciona
- **Tempo**: ~30-60s para 100 produtos

### ⭐⭐⭐ Nível 3 - Médio (JSON-LD Customizado):
- **Wake** (categorias), **Nuvemshop** (homepage)
- **Estratégia**: Extrator especializado + descoberta de sweet spot
- **Tempo**: ~2-8s para 100 produtos

### ⭐⭐⭐⭐ Nível 4 - Difícil (HTML Microdata):
- **Tray**, **Loja Integrada**
- **Estratégia**: Parsing HTML microdata (`itemprop` attributes)
- **Tempo**: ~6-15s para 100 produtos

### ⭐⭐⭐⭐⭐ Nível 5 - Muito Difícil (JavaScript-heavy):
- **Magento avançado**, **Next.js categorias**, **React SPA**
- **Estratégia**: Selenium/Playwright (browser automation)
- **Tempo**: ~60-120s para 100 produtos (muito mais lento)

---

## 📈 Estatísticas do Projeto

### Cobertura:
```
Sites testados: 11
Sites funcionando: 7 (63.6%)
Sites com extrator especializado: 4 (36.4%)
Sites com genérico: 3 (27.3%)
Sites complexos: 2 (18.2%)
Sites removidos: 2 (18.2%)
```

### Performance:
```
Speedup médio (especializados): 19x vs genérico
Tempo médio (100 produtos):
  - API nativa (Shopify): 3s
  - Especializado (Wake/Nuvemshop/Tray): 2-8s
  - Genérico (VTEX/outros): 30-60s
  - JavaScript (Magento): 60-120s
```

### Plataformas Identificadas:
```
✅ Shopify: 1 site (API nativa)
✅ Wake/VTEX: 2 sites (JSON-LD)
✅ Nuvemshop: 1 site (JSON-LD homepage)
✅ Tray: 1 site (HTML microdata)
✅ Next.js: 1 site (SSR + discovery)
⚠️ Magento: 1 site (JavaScript-heavy)
⚠️ Loja Integrada: 1 site (HTML parsing)
❌ Quebrados: 2 sites (404/institucional)
```

---

## 🎯 Recomendações para Novos Sites

### 1. Classificar o site primeiro:
```python
# Ordem de testes:
1. Verificar se tem API pública (/products.json, /api/products)
2. Buscar JSON-LD na homepage
3. Buscar JSON-LD em categorias
4. Tentar HTML microdata (itemprop)
5. Se nada funcionar: JavaScript rendering (Selenium)
```

### 2. Estratégia de desenvolvimento:
```python
# Para cada nova plataforma:
1. Criar script de diagnóstico (test_novosite.py)
2. Identificar plataforma e estrutura de dados
3. Medir performance do genérico
4. Se genérico falhar ou for muito lento (>60s):
   → Criar extrator especializado
5. Testar integração no QuintApp
6. Documentar no LICOES_APRENDIDAS.md
```

### 3. Priorização:
```python
# Alto valor (criar extrator):
- Genérico falha completamente (Petrizi/Tray)
- Site muito popular/importante
- Performance > 10x melhor

# Médio valor (considerar):
- Genérico lento mas funciona (5-10x melhor)
- Plataforma comum no Brasil

# Baixo valor (usar genérico):
- Genérico funciona bem
- Site pequeno/pouco usado
- Melhoria < 5x
```

---

## 🚀 Próximos Passos

### Curto Prazo:
- [ ] Decidir sobre CEB Modas (Loja Integrada) - criar extrator ou ignorar?
- [ ] Testar mais sites Shopify para validar padrão
- [ ] Documentar padrões HTML microdata (além de Tray)

### Médio Prazo:
- [ ] Implementar extrator Loja Integrada (se necessário)
- [ ] Explorar Magento com Selenium (POC)
- [ ] Criar biblioteca de padrões por plataforma

### Longo Prazo:
- [ ] Browser automation para sites JavaScript-heavy
- [ ] Machine Learning para detectar plataforma automaticamente
- [ ] API/Webhook para monitoramento contínuo de sites

---

## 📞 Contato e Feedback

Para adicionar novos sites ou reportar problemas:
1. Criar script `test_novosite.py` com diagnóstico
2. Executar e salvar output
3. Documentar descobertas
4. Decidir se vale criar extrator especializado

---

**Documento criado**: 2025-01-24  
**Última atualização**: 2025-01-24  
**Versão**: QuintApp 1.0 (5 extratores)
