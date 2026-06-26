# Plano de aplicacao controlada DCB medicamentos

## Objetivo
Preparar a aplicacao controlada da carga DCB de medicamentos no dicionario final, com validacao previa e dry-run auditavel. Nesta fase, nenhuma aplicacao real foi realizada.

## Por que a DCB entra como base de principio ativo
A DCB e uma fonte oficial de denominacoes comuns e principios ativos. Ela deve alimentar o dicionario como base de nomes padronizados, DCB, CAS e classificacao tecnica, sem representar apresentacao comercial.

## O que sera preenchido em aplicacao futura
- id_dicionario
- nome_padrao
- principio_ativo
- dcb
- cas
- classificacao
- fonte_tipo
- fonte_nome
- fonte_origem
- url_fonte
- data_coleta
- validado_internamente
- validado_externamente
- confianca
- status_revisao
- observacao

## O que ficara vazio nesta carga
As colunas `sku_master_padrao`, `concentracao`, `forma_farmaceutica`, `apresentacao`, `via_uso` e `atc` ficam vazias porque nao sao papel da DCB. Elas devem ser enriquecidas em fases posteriores com Medicamentos Registrados ANVISA, Bulario ANVISA, WHO ATC/DDD, catalogos ou compendios quando necessario.

## Backup obrigatorio
Antes de qualquer `--apply` futuro, o script deve criar backup do dicionario final em `backups/`. A aplicacao deve ser bloqueada se o backup nao puder ser criado.

## Comando futuro de aplicacao
`python scripts/dicionario_mestre/aplicar_carga_dcb_medicamentos.py --apply --confirmar`

## Dry-run executado nesta fase
- Registros simulados: 12715
- Arquivo gerado: `data/dicionario_mestre/processado/dry_run_aplicacao_dcb_medicamentos.csv`
- Nenhuma escrita no dicionario final foi feita.

## Riscos
- CAS duplicados exigem revisao humana para usos analiticos finos.
- Termos longos ou incomuns devem continuar rastreados para revisao.
- Aplicar sobre dicionario final com dados inesperados pode gerar duplicidade; por isso o script bloqueia aplicacao se houver linhas de dados no dicionario atual.

## Criterios para autorizar apply
- FASE 1.5 commitada.
- Revisao com decisao `APROVAR_CARGA_DCB_BASE_PRINCIPIO_ATIVO`.
- Nenhuma pendencia bloqueante.
- Dicionario final com cabecalho esperado e 0 linhas de dados.
- Backup criado com sucesso antes da escrita.
- Aprovacao explicita do responsavel.

## Confirmacao desta fase
Nenhum dicionario final foi alterado nesta fase.
