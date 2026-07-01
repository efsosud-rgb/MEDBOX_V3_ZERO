# SKU-MEMORIA-04 — Aprovação manual dos matches seguros da memória

## Objetivo
Isolar, em uma planilha simples de decisão, apenas os matches classificados como seguros na fase `SKU-MEMORIA-03` (`MATCH_MEMORIA_VALIDADA` e `MATCH_ASSINATURA_TECNICA`), para que o usuário revise e decida caso a caso — **sem aplicar nada no banco nesta fase**.

## Quantidade de matches seguros
**15 linhas**, filtradas de `relatorios/sku_memoria_03_previa_matches_banco.csv` (31 linhas classificadas no total: 11 bloqueadas, 3 pendentes, 2 sem match, que **não** entraram nesta planilha).

## Tipos de match incluídos

| Tipo de match | Quantidade | O que significa |
|---|---:|---|
| `MATCH_MEMORIA_VALIDADA` | 5 | A descrição do produto no banco bate exatamente com uma entrada já validada em `memoria_equivalencias_sku_master.csv` (mesma marca, mesma dose/concentração/volume). |
| `MATCH_ASSINATURA_TECNICA` | 10 | O produto tem marca comercial diferente da memória, mas o princípio ativo, a dose e o volume são idênticos a uma entrada validada — o SKU_MASTER sugerido é o mesmo, mas a marca sugerida é a marca **real** do produto (nunca a marca da entrada de memória usada como referência técnica). |

## O que foi feito e o que não foi feito
- Foi feito: leitura de `sku_memoria_03_previa_matches_banco.csv`, filtro dos 15 registros seguros, geração da planilha de aprovação com a coluna `decisao_usuario` **vazia**, pronta para preenchimento manual.
- **Nada foi aplicado.** Nenhum `UPDATE` foi executado em `banco/medbox_v3.db`, nenhum `sku_master`/`marca`/`categoria` foi alterado em nenhum produto. Esta planilha é só uma ferramenta de decisão — a aplicação real (se autorizada) é uma fase futura separada.

## Como preencher a coluna `decisao_usuario`
Preencha uma das três opções por linha, na planilha `relatorios/sku_memoria_04_aprovacao_manual.csv`:

- **`APROVAR`** — a sugestão está correta; o produto deve receber esse `sku_master_sugerido`/`marca_sugerida`/`categoria_sugerida` em uma fase futura de aplicação controlada.
- **`REJEITAR`** — a sugestão está errada ou não deve ser aplicada a este produto específico; não entra em nenhuma fase de aplicação.
- **`REVISAR`** — ainda há dúvida; o item permanece em análise, não é aprovado nem rejeitado nesta rodada.

A coluna `observacao_usuario` fica disponível para qualquer justificativa ou correção que o usuário queira registrar junto da decisão (ex.: "confirmado por telefone com fornecedor", "SKU errado, deveria ser X").

## Próximo passo (fora do escopo desta fase)
Depois que o usuário preencher `decisao_usuario` para as 15 linhas, uma fase futura (`SKU-LOTE` ou similar) pode ler apenas as linhas marcadas `APROVAR` e aplicá-las de forma controlada, uma a uma ou em lote pequeno, com o mesmo cuidado de preview/backup já usado nas fases anteriores. Nenhuma aplicação automática deve ocorrer sem essa aprovação explícita.
