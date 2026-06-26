# Revisao da carga previa DCB medicamentos

## Objetivo
Revisar a carga previa DCB antes de qualquer aplicacao no dicionario final, com foco em CAS duplicados, termos para revisao, colunas sem equivalente direto na DCB e decisao tecnica sobre uso como base de principios ativos.

## Arquivos analisados
- data\dicionario_mestre\processado\carga_previa_dicionario_medicamentos_anvisa_dcb.csv
- data\dicionario_mestre\processado\diff_carga_dicionario_medicamentos_anvisa_dcb.csv
- data\dicionario_mestre\processado\duplicidades_previa_dcb_medicamentos.csv
- data\dicionario_mestre\processado\termos_revisao_previa_dcb_medicamentos.csv

## Totais
- Total de registros na carga: 12715
- Total de acoes previstas no diff: 12715
- Acoes previstas por tipo:
- INSERIR_PREVISTO: 12715
- Total de pendencias: 1877
- Pendencias bloqueantes: 0

## Pendencias por tipo
- CAS_DUPLICADO: 1817
- COLUNA_SEM_EQUIVALENTE_DCB: 6
- TERMO_REVISAO: 54

## Pendencias por severidade
- BAIXA: 6
- MEDIA: 1871

## Pendencias que bloqueiam carga
- Nenhuma pendencia bloqueante identificada.

## Colunas sem equivalente na DCB
As colunas `sku_master_padrao`, `concentracao`, `forma_farmaceutica`, `apresentacao`, `via_uso` e `atc` permanecem vazias por desenho da carga previa. A DCB identifica denominacoes comuns e principios ativos, mas nao descreve apresentacao comercial completa. Essas lacunas nao bloqueiam a carga DCB como base de principio ativo.

Fontes recomendadas para fases posteriores:
- Medicamentos Registrados ANVISA
- Bulario ANVISA
- WHO ATC/DDD
- Catalogos ou compendios, quando necessario

## CAS duplicados
- Linhas de grupos de duplicidade analisadas: 24
- Registros de carga ligados a CAS duplicados: 1817
- Avaliacao: CAS duplicados exigem revisao humana para uso analitico fino, pois podem representar sais, formas, substancias relacionadas ou referencias compartilhadas. Nao bloqueiam a carga como base de principio ativo.

## Termos para revisao
- Termos recebidos para revisao: 54
- Pendencias TERMO_REVISAO geradas: 54
- Avaliacao: os termos devem ser revisados por tamanho, caracteres incomuns ou motivo registrado, mas permanecem rastreados a fonte oficial ANVISA DCB e nao bloqueiam a carga base.

## Resumo da amostra
- Total de linhas na amostra: 2231
- Grupos de amostra:
- ALEATORIA_SEED_42: 20
- CAS_DUPLICADO: 1817
- CLASSIFICACAO_BIOLOGICO: 20
- CLASSIFICACAO_EXTRATO: 20
- CLASSIFICACAO_HOMEOPATICO: 20
- CLASSIFICACAO_INSUMO FARMACEUTICO: 20
- CLASSIFICACAO_INSUMO FARMACEUTICO ATIVO: 20
- CLASSIFICACAO_PRODUTO MANUTENCAO: 20
- CLASSIFICACAO_RADIOFARMACO: 20
- NOMES_MAIS_CURTOS: 20
- NOMES_MAIS_LONGOS: 20
- PRIMEIROS_20: 20
- SUBCATEGORIA_BIOLOGICO: 20
- SUBCATEGORIA_EXTRATO: 20
- SUBCATEGORIA_HOMEOPATICO: 20
- SUBCATEGORIA_INSUMO FARMACEUTICO: 20
- SUBCATEGORIA_INSUMO FARMACEUTICO ATIVO: 20
- SUBCATEGORIA_PRODUTO MANUTENCAO: 20
- SUBCATEGORIA_RADIOFARMACO: 20
- TERMO_REVISAO: 54

## Decisao tecnica recomendada
APROVAR_CARGA_DCB_BASE_PRINCIPIO_ATIVO

A DCB deve entrar no Dicionario Mestre como base de principios ativos e denominacoes oficiais, nao como apresentacao comercial. Concentracao, forma farmaceutica, apresentacao, via de uso e ATC devem ser enriquecidos em fases posteriores com fontes apropriadas.

## Confirmacoes
- Nenhum dicionario final foi alterado.
- Nenhuma fonte interna foi usada.
- Nenhum banco foi alterado.
- Nenhum SKU_MASTER foi aplicado.
- Nenhuma mesclagem foi feita.
