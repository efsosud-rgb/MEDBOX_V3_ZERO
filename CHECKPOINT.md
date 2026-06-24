# CHECKPOINT MEDBOX_V3_ZERO

## Estado atual
- Data/hora: 2026-06-24 16:30:07 -03:00
- Agente em uso: Codex
- Branch: melhoria/auditoria-sku-master-todos-produtos
- Tarefa atual: gerar previa CSV read-only das marcas suspeitas em precos_fornecedores
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
- scripts/diagnosticos/previa_marcas_suspeitas_precos.csv
- CHECKPOINT.md

## Arquivos proibidos nesta tarefa
- banco/
- uploads/
- backups/
- descricao_original
- historico de precos
- arquivos fora do escopo da tarefa

## O que ja foi feito
- Banco `banco/medbox_v3.db` aberto explicitamente em modo somente leitura.
- Consultados 102 registros atuais de `precos_fornecedores.marca` com codigos suspeitos.
- Gerado CSV com contexto do produto, fornecedor e recomendacao para validacao manual.
- Aplicadas apenas classificacoes de diagnostico: 89 `REMOVER_MARCA_INVALIDA` e 13 `VALIDAR_MANUALMENTE`.
- Validada a reconciliacao entre as 102 linhas do CSV e as 102 linhas retornadas pelo banco.

## O que falta fazer
- Responsavel revisar manualmente o CSV.
- Validar individualmente os 13 registros `SR` antes de qualquer decisao.
- Nenhuma correcao de banco esta autorizada nesta etapa.

## Arquivos alterados
- scripts/diagnosticos/previa_marcas_suspeitas_precos.csv
- CHECKPOINT.md

## Comandos executados
- Leitura de AGENTS.md, CLAUDE.md, RETOMAR.md e CHECKPOINT.md.
- Consultas `SELECT` e `PRAGMA` via `node:sqlite` com `{ readOnly: true }`.
- `git branch --show-current`, `git status --short` e `git diff --name-only -- banco`.

## Testes executados
- Validacao de 13 colunas em todas as linhas do CSV.
- Validacao de 102 `preco_id` unicos.
- Validacao de codificacao UTF-8 e acentos.
- Reconciliacao do total do CSV com consulta read-only ao banco.
- Comparacao de tamanho e data de modificacao do banco antes/depois.

## Resultado dos testes
- CSV: 102 linhas de dados e 1 cabecalho.
- Todas as linhas possuem 13 colunas.
- Todos os `preco_id` sao unicos.
- Codificacao UTF-8 valida, sem caractere de substituicao.
- Banco permaneceu inalterado.
- Nenhum UPDATE, INSERT, DELETE, DROP, ALTER ou CREATE foi executado.

## Riscos / observacoes
- `SR` e `S R` permanecem para validacao manual; nao assumir SALDANHA RODRIGUES automaticamente.
- O CSV e apenas uma previa diagnostica e nao deve ser usado como script de atualizacao sem nova autorizacao.
- `.claude/` continua nao rastreado e nao foi alterado.

## Proximo passo recomendado
- Revisar `scripts/diagnosticos/previa_marcas_suspeitas_precos.csv` e aprovar/rejeitar cada sugestao antes de planejar qualquer alteracao no banco.
