# CHECKPOINT MEDBOX_V3_ZERO

## Estado atual
- Data/hora: 2026-06-24 17:01:32 -03:00
- Agente em uso: Codex
- Branch: melhoria/auditoria-sku-master-todos-produtos
- Tarefa atual: gerar previa especifica read-only para marcas SR/S R
- Status Git antes da tarefa: somente `.claude/` nao rastreado

## Regras inviolaveis
- Nunca alterar banco sem backup previo.
- Nunca alterar descricao_original.
- SKU_MASTER nao substitui descricao_original.
- Nunca deletar historico de precos.
- Precos antigos vao para precos_fornecedores_historico.
- Nao misturar fornecedor com fabricante/marca.
- Nao fazer patch as cegas: diagnosticar antes.

## Arquivos permitidos nesta tarefa
- scripts/diagnosticos/previa_sr_validacao_manual.csv
- CHECKPOINT.md

## Arquivos proibidos nesta tarefa
- banco/
- uploads/
- backups/
- descricao_original
- historico de precos
- arquivos fora do escopo da tarefa

## O que ja foi feito
- Mantida a previa geral `scripts/diagnosticos/previa_marcas_suspeitas_precos.csv` com 102 registros.
- Banco `banco/medbox_v3.db` aberto explicitamente em modo somente leitura.
- Consultados os 13 registros atuais de `precos_fornecedores.marca` iguais a `SR` ou `S R` apos remover espacos.
- Gerado `scripts/diagnosticos/previa_sr_validacao_manual.csv` com 15 colunas para decisao manual.
- Recuperada `descricao_original` nos 13 registros, priorizando o preco atual e usando historico apenas como fallback de leitura.
- Classificados 4 registros como possivel `SALDANHA RODRIGUES` com confianca `MEDIA`.
- Classificados 9 registros como `VALIDAR` com confianca `BAIXA` por divergencia com BD ou VITALGOLD.

## O que falta fazer
- Responsavel preencher a coluna `decisao_usuario` nas 13 linhas.
- Confirmar manualmente os quatro casos sugeridos como SALDANHA RODRIGUES.
- Revisar os nove casos divergentes antes de qualquer correcao.
- Nenhuma correcao de banco esta autorizada nesta etapa.

## Arquivos alterados
- scripts/diagnosticos/previa_sr_validacao_manual.csv
- CHECKPOINT.md

## Comandos executados
- `git status --short` antes da tarefa.
- Leitura de AGENTS.md, CLAUDE.md, RETOMAR.md e CHECKPOINT.md.
- Consultas `SELECT` via `node:sqlite` com `{ readOnly: true }`.
- `git branch --show-current`, `git status --short` e `git diff --name-only -- banco`.

## Testes executados
- Validacao de 15 colunas em todas as linhas do CSV.
- Validacao de 13 `preco_id` unicos.
- Confirmacao de que todas as marcas normalizam para `SR`.
- Confirmacao de que as 13 celulas `decisao_usuario` estao vazias.
- Validacao de codificacao UTF-8 e acentos.
- Reconciliacao do total do CSV com consulta read-only ao banco.
- Comparacao de tamanho e data de modificacao do banco antes/depois.

## Resultado dos testes
- CSV: 13 linhas de dados e 1 cabecalho.
- Todas as linhas possuem 15 colunas.
- Todos os `preco_id` sao unicos.
- `descricao_original` recuperada nas 13 linhas.
- Possivel correcao: 4 `SALDANHA RODRIGUES` e 9 `VALIDAR`.
- Confianca: 4 `MEDIA` e 9 `BAIXA`.
- Codificacao UTF-8 valida.
- Banco permaneceu inalterado.
- Nenhum UPDATE, INSERT, DELETE, DROP, ALTER ou CREATE foi executado.

## Riscos / observacoes
- A sigla `SR` isolada nao foi considerada prova de fabricante.
- Os quatro casos sugeridos como SALDANHA RODRIGUES dependem do fabricante ja cadastrado no produto e ainda exigem validacao manual.
- Os nove casos restantes possuem contexto divergente, principalmente BD ou VITALGOLD.
- O CSV e apenas diagnostico; nao deve ser usado como script de atualizacao sem nova autorizacao.
- `.claude/` continua nao rastreado e nao foi alterado.

## Proximo passo recomendado
- Preencher `decisao_usuario` em `scripts/diagnosticos/previa_sr_validacao_manual.csv` e revisar as decisoes antes de planejar qualquer alteracao no banco.
