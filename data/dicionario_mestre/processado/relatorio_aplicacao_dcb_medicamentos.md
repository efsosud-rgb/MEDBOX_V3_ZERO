# Relatorio de aplicacao DCB medicamentos

## Objetivo
Aplicar a carga DCB no dicionario mestre de medicamentos como base de principios ativos e denominacoes oficiais.

## Autorizacao humana registrada
O usuario aprovou explicitamente: "Aprovo aplicar a DCB no dicionario_mestre_medicamentos.csv".

## Commit base antes da aplicacao
5ea158f chore: prepara aplicacao controlada dcb medicamentos

## Bloqueios encontrados e correcoes feitas
- Caminho do backup: corrigido para `backups/dicionario_mestre/`.
- Nome do backup: corrigido para `dicionario_mestre_medicamentos_ANTES_DCB_YYYYMMDD_HHMMSS.csv`.
- Checklist `--apply nao executado`: ajustado para nao bloquear quando `--apply --confirmar` esta autorizado.

## Comando executado
`python scripts/dicionario_mestre/aplicar_carga_dcb_medicamentos.py --apply --confirmar`

## Arquivo aplicado
- data/dicionario_mestre/dicionario_mestre_medicamentos.csv

## Backup criado
- backups/dicionario_mestre/dicionario_mestre_medicamentos_ANTES_DCB_20260626_094804.csv

## Total de registros aplicados
- 12.715 registros
- 12.716 linhas totais incluindo cabecalho

## Validacoes pos-aplicacao
- Total de linhas: 12716
- Total de registros: 12715
- Larguras encontradas: [22]
- Cabecalho preservado: True
- IDs DCB: True
- Sem id vazio: True
- Sem nome_padrao vazio: True
- Sem DCB vazio: True
- Sem CAS vazio: True
- fonte_nome ANVISA_DCB em todos: True
- confianca ALTA em todos: True
- Backup com estado anterior somente cabecalho: True
- Falhas bloqueantes: 0

## Riscos remanescentes
- CAS duplicados e termos longos seguem como pontos de revisao humana para uso analitico fino.
- A carga DCB nao representa apresentacao comercial.

## Confirmacoes
- A DCB entrou como base de principio ativo.
- Concentracao, forma farmaceutica, apresentacao, via_uso e ATC ficam para fases posteriores.
- Banco nao foi alterado.
- Fonte interna nao foi usada.
- SKU_MASTER nao foi aplicado.
