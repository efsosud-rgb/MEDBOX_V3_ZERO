# CHECKPOINT MEDBOX_V3_ZERO

## Estado atual
- Data/hora: 2026-06-25 08:39:08 -03:00
- Agente em uso: Codex
- Branch: melhoria/auditoria-sku-master-todos-produtos
- Tarefa atual: gerar apoio para decisao manual dos 13 registros `SR` / `S R` restantes em `precos_fornecedores.marca`
- Status: arquivo de decisao manual criado; banco nao alterado; nenhum commit realizado

## Regras inviolaveis
- Nunca alterar banco sem backup previo.
- Nunca alterar descricao_original.
- SKU_MASTER nao substitui descricao_original.
- Nunca deletar historico de precos.
- Precos antigos vao para precos_fornecedores_historico.
- Nao misturar fornecedor com fabricante/marca.
- Nao fazer patch as cegas: diagnosticar antes.
- Nao aplicar correcao automatica nos 13 registros `SR` / `S R`.
- Nao mexer nos precos.

## Arquivos permitidos nesta tarefa
- scripts/diagnosticos/decisao_manual_sr.csv
- CHECKPOINT.md

## Arquivos proibidos nesta tarefa
- banco/
- uploads/
- backups/
- descricao_original
- historico de precos
- arquivos fora do escopo da validacao/manualizacao

## Contexto anterior
- A limpeza automatica das 89 marcas invalidas de alta confianca foi aplicada e validada.
- Os 89 registros auditados ficaram com `marca NULL`.
- Restaram apenas 13 registros com `SR` / `S R`.
- Os 13 registros `SR` / `S R` exigem decisao manual antes de qualquer correcao.

## Tarefa executada
- Usado como base: `scripts/diagnosticos/previa_sr_validacao_manual.csv`
- Criado arquivo: `scripts/diagnosticos/decisao_manual_sr.csv`
- O novo CSV contem os 13 registros restantes com as colunas de apoio para decisao manual:
  - `preco_id`
  - `produto_id`
  - `produto_padrao`
  - `sku_master`
  - `fabricante_produto`
  - `marca_preco_atual`
  - `fornecedor`
  - `preco`
  - `data_importacao`
  - `descricao_original`
  - `possivel_correcao_atual`
  - `confianca_atual`
  - `decisao_recomendada`
  - `motivo_recomendacao`
  - `decisao_usuario`

## Totais encontrados
- Total de registros: 13
- Total por `fabricante_produto`:
  - BD: 8
  - SALDANHA RODRIGUES: 4
  - VITALGOLD: 1
- Total por `decisao_recomendada`:
  - MANTER_OU_CONFIRMAR_SALDANHA_RODRIGUES: 4
  - REMOVER_SR_COMO_MARCA_INVALIDA: 9
  - VALIDAR_MANUALMENTE: 0

## Listas de apoio
- Parecem SALDANHA RODRIGUES: `1025`, `1026`, `1027`, `1028`
- Devem remover `SR` como marca invalida: `1022`, `1030`, `1031`, `1032`, `1034`, `1036`, `1037`, `1038`, `1041`

## Comandos executados nesta etapa
- `git status --short`
- `Import-Csv -Delimiter ';' -Path scripts\diagnosticos\previa_sr_validacao_manual.csv | ConvertTo-Json -Depth 3`
- `Import-Csv -Delimiter ';' -Path scripts\diagnosticos\decisao_manual_sr.csv`
- `Get-Date -Format "yyyy-MM-dd HH:mm:ss zzz"`

## Confirmacoes
- Banco nao foi alterado nesta etapa.
- Nenhum `UPDATE`, `INSERT`, `DELETE`, `DROP`, `ALTER` ou `CREATE` foi executado nesta etapa.
- Nenhum commit foi feito nesta etapa.
- Nenhuma correcao foi aplicada aos 13 registros `SR` / `S R`.
- `descricao_original` foi apenas copiada para o CSV de apoio, sem alteracao.
- Precos foram apenas copiados para o CSV de apoio, sem alteracao.

## Riscos / observacoes
- A recomendacao ainda nao e autorizacao para corrigir automaticamente.
- Os 4 casos de SALDANHA RODRIGUES continuam exigindo confirmacao manual, pois `SR` pode ser abreviacao relacionada.
- Os 9 casos com fabricante diferente parecem codigo auxiliar em `marca_preco_atual`, mas a decisao final deve ser preenchida pelo usuario em `decisao_usuario`.

## Proximo passo recomendado
- Usuario preencher/validar a coluna `decisao_usuario` em `scripts/diagnosticos/decisao_manual_sr.csv`.
