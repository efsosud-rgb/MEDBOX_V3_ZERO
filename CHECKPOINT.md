# CHECKPOINT MEDBOX_V3_ZERO

## Estado atual
- Data/hora: 2026-06-25 08:46:00 -03:00
- Agente em uso: Codex
- Branch: melhoria/auditoria-sku-master-todos-produtos
- Tarefa atual: criar script seguro dry-run para aplicar a decisao aprovada dos 13 registros `SR` / `S R`
- Status: script criado; DRY-RUN executado com sucesso via `py`; APPLY nao executado

## Regras inviolaveis
- Nunca alterar banco sem backup previo.
- Nunca alterar descricao_original.
- SKU_MASTER nao substitui descricao_original.
- Nunca deletar historico de precos.
- Precos antigos vao para precos_fornecedores_historico.
- Nao misturar fornecedor com fabricante/marca.
- Nao fazer patch as cegas: diagnosticar antes.
- Nao aplicar correcao automatica nos 13 registros `SR` / `S R` nesta etapa.
- Nao mexer nos precos.
- Nao alterar `produtos.fabricante`.
- Nao alterar historico de precos.
- Nao fazer commit nesta etapa.

## Arquivos permitidos nesta tarefa
- scripts/correcoes/corrigir_sr_precos.py
- CHECKPOINT.md

## Arquivos proibidos nesta tarefa
- banco/
- uploads/
- backups/
- descricao_original
- historico de precos
- arquivos fora do escopo do script/checkpoint

## Contexto anterior
- A limpeza automatica das 89 marcas invalidas de alta confianca foi aplicada e validada.
- Restaram 13 registros com `SR` / `S R`.
- Foi criado e commitado `scripts/diagnosticos/decisao_manual_sr.csv`.
- O usuario aprovou a Opcao A:
  - 4 registros devem confirmar `marca = SALDANHA RODRIGUES`.
  - 9 registros devem remover `SR` como marca invalida, gravando `marca = NULL` em APPLY futuro.

## Tarefa executada
- Criado arquivo: `scripts/correcoes/corrigir_sr_precos.py`
- O script roda por padrao em DRY-RUN.
- O script le `scripts/diagnosticos/decisao_manual_sr.csv`.
- O script exige exatamente 13 registros.
- O script exige decisao_usuario vazia ou compativel com a decisao aprovada.
- O script valida exatamente 4 registros para `SALDANHA RODRIGUES` e 9 registros para `NULL`.
- O script valida existencia dos 13 `preco_id` no banco.
- O script valida que os 13 ainda estao com marca compactada `SR`.
- O script valida que `produto_id` no banco bate com o CSV.
- O script valida que os 4 registros de SALDANHA têm `fabricante_produto = SALDANHA RODRIGUES`.
- O script valida que os 9 registros para NULL têm fabricante diferente de SALDANHA RODRIGUES.
- O caminho APPLY futuro exige `--apply --confirmar`, bloqueia Git sujo, cria backup, gera auditoria, usa transacao, atualiza somente por `preco_id` e marca antiga compactada `SR`, e exige `rowcount = 1`.

## Resultado do DRY-RUN solicitado
- Comando executado: `python scripts\correcoes\corrigir_sr_precos.py`
- Resultado: o comando nao iniciou porque `python` nao esta disponivel no PATH desta sessao.
- Comando executado em seguida: `py scripts\correcoes\corrigir_sr_precos.py`
- Resultado: DRY-RUN executado com sucesso fora do sandbox, sem `--apply`.
- Registros validados: 13
- Atualizariam para `SALDANHA RODRIGUES`: 4 (`1025`, `1026`, `1027`, `1028`)
- Atualizariam para `NULL`: 9 (`1022`, `1030`, `1031`, `1032`, `1034`, `1036`, `1037`, `1038`, `1041`)
- Confirmacao do script: nenhum UPDATE foi executado; banco aberto somente leitura.
- Nenhum `--apply` foi executado.

## Validacao independente somente leitura
- CSV lido: `scripts/diagnosticos/decisao_manual_sr.csv`
- Total de registros no CSV: 13
- Decisao usuario vazia: 13
- Registros para `SALDANHA RODRIGUES`: 4
- Registros para `NULL`: 9
- IDs para `SALDANHA RODRIGUES`: `1025`, `1026`, `1027`, `1028`
- IDs para `NULL`: `1022`, `1030`, `1031`, `1032`, `1034`, `1036`, `1037`, `1038`, `1041`
- Registros encontrados no banco em leitura: 13
- Divergencias de `produto_id` ou marca atual: 0

## Comandos executados nesta etapa
- `git status --short`
- `Import-Csv -Delimiter ';' -Path scripts\diagnosticos\decisao_manual_sr.csv | Select-Object ... | ConvertTo-Json`
- `python scripts\correcoes\corrigir_sr_precos.py`
- `py scripts\correcoes\corrigir_sr_precos.py`
- Consulta SQLite somente leitura via Node `node:sqlite` sobre `banco\medbox_v3.db`
- `git diff --stat`
- `git diff --check`
- `git check-ignore -v scripts\correcoes\corrigir_sr_precos.py`
- `Get-Date -Format "yyyy-MM-dd HH:mm:ss zzz"`

## Confirmacoes
- Banco nao foi alterado nesta etapa.
- Nenhum `UPDATE`, `INSERT`, `DELETE`, `DROP`, `ALTER` ou `CREATE` foi executado nesta etapa.
- Nenhum commit foi feito nesta etapa.
- Nenhuma correcao foi aplicada aos 13 registros `SR` / `S R`.
- Precos nao foram alterados.
- `descricao_original` nao foi alterada.
- `produtos.fabricante` nao foi alterado.
- Historico de precos nao foi alterado.

## Riscos / observacoes
- O DRY-RUN real do script foi executado com sucesso via `py`.
- O script contem comandos de UPDATE apenas no caminho futuro protegido por `--apply --confirmar`; esse caminho nao foi executado.
- O arquivo `scripts/correcoes/corrigir_sr_precos.py` segue ignorado por regra local `corrigir_*.py` em `.git/info/exclude`; se for necessario versionar futuramente, revisar isso explicitamente.

## Proximo passo recomendado
- Se o usuario aprovar uma etapa futura, planejar APPLY controlado com `py scripts\correcoes\corrigir_sr_precos.py --apply --confirmar`, somente apos nova autorizacao explicita e com Git limpo.
