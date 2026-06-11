# Diário IA — MEDBOX V3 ZERO

## 2026-06-11

### PR #34 mergeado
- Correções de encoding UTF-8 no menu lateral (`base.html`) e na tela de Lances de Cotação (`cotacao_lances.html`).
- Branch `fix/encoding-menu-cotacao-lances` integrada à `main` via PR #34.

### Branch `feature/sku-editavel-busca-sku-master`

**Tarefa 1 — Auditoria SKU Master: campo SKU Sugerido editável**

Problema: a coluna "Sugestão SKU limpo" em `templates/sku_master_auditoria.html` era somente leitura.

Solução implementada:
- `templates/sku_master_auditoria.html`: coluna "SKU Sugerido" substituída por `<input>` editável com `<datalist>` (autocomplete). Botão "Salvar" adicionado em coluna "Ação". JS carrega todos os SKUs existentes via `GET /sku-master/skus-json` e sincroniza o valor do input no campo hidden antes do submit.
- `app.py`: duas rotas novas adicionadas:
  - `GET /sku-master/skus-json` — retorna JSON com todos os `produto_padrao` ativos.
  - `POST /sku-master/auditoria/salvar-sku` — chama `aplicar_correcao_manual_sku_master`, que cria backup, migra preços/equivalências e loga a correção.

**Tarefa 2 — Busca Inteligente: pesquisar e retornar campo `sku`**

Problema: a busca não pesquisava o campo `sku` (código identificador) da tabela `produtos`. O código SKU do produto não aparecia nos resultados.

Solução implementada:
- `core/busca_inteligente.py`: adicionado `"sku": 0.95` em `PESOS_CAMPOS` e `_buscar_por_campo_produto(..., "sku", "sku", termo)` em `_recuperar_candidatos`. Agora buscas por código SKU retornam resultados.
- `templates/busca.html`: campo `principal.sku` exibido no card "Detalhes do Produto" (sidebar) e o código SKU aparece abaixo do nome em "Outros Produtos Encontrados".
