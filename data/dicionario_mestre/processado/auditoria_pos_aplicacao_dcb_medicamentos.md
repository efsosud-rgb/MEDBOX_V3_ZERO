# Auditoria pos-aplicacao DCB medicamentos

## Objetivo
Revisar a aplicacao da DCB no dicionario mestre de medicamentos sem alterar o dicionario final.

## Arquivos analisados
- data\dicionario_mestre\dicionario_mestre_medicamentos.csv
- data\dicionario_mestre\processado\carga_previa_dicionario_medicamentos_anvisa_dcb.csv
- data\dicionario_mestre\processado\pendencias_carga_previa_dcb_medicamentos.csv
- data\dicionario_mestre\processado\validacao_pos_aplicacao_dcb_medicamentos.csv

## Totais
- Total de linhas: 12716
- Total de registros: 12715
- Total de colunas: 22

## Total por classificacao
- BIOLOGICO: 514
- EXTRATO: 372
- HOMEOPATICO: 1170
- INSUMO FARMACEUTICO: 9568
- INSUMO FARMACEUTICO ATIVO: 615
- PRODUTO MANUTENCAO: 273
- RADIOFARMACO: 203

## Total por fonte_nome
- ANVISA_DCB: 12715

## Total por confianca
- ALTA: 12715

## Campos vazios esperados
- sku_master_padrao: 12715
- concentracao: 12715
- forma_farmaceutica: 12715
- apresentacao: 12715
- via_uso: 12715
- atc: 12715

## Comparacao com a carga previa
- Registros finais e carga previa possuem mesmo cabecalho e mesma contagem.
- A comparacao normalizada permite apenas ajuste cosmetico de espaco antes de quebra interna em observacoes.

## Pendencias conhecidas
- CAS_DUPLICADO: 1817
- COLUNA_SEM_EQUIVALENTE_DCB: 6
- TERMO_REVISAO: 54

## CAS duplicados conhecidos
- Registros em pendencia CAS_DUPLICADO: 1817
- Avaliacao: conhecidos, rastreados e nao bloqueantes para iniciar a proxima fonte.

## Termos de revisao conhecidos
- Registros em pendencia TERMO_REVISAO: 54
- Avaliacao: conhecidos, rastreados e nao bloqueantes para iniciar a proxima fonte.

## Resumo da amostra
- Total de linhas na amostra: 2131
- Grupos:
- ALEATORIA_SEED_42: 20
- CAS_DUPLICADO: 1817
- CLASSIFICACAO_BIOLOGICO: 20
- CLASSIFICACAO_EXTRATO: 20
- CLASSIFICACAO_HOMEOPATICO: 20
- CLASSIFICACAO_INSUMO FARMACEUTICO: 20
- CLASSIFICACAO_INSUMO FARMACEUTICO ATIVO: 20
- CLASSIFICACAO_PRODUTO MANUTENCAO: 20
- CLASSIFICACAO_RADIOFARMACO: 20
- FONTE_ANVISA_DCB: 20
- NOMES_MAIS_CURTOS: 20
- NOMES_MAIS_LONGOS: 20
- PRIMEIROS_20: 20
- TERMO_REVISAO: 54
- ULTIMOS_20: 20

## Resultado da consistencia
- Falhas bloqueantes: 0
- Decisao tecnica: APTO_PARA_INICIAR_FASE_2_ANVISA_MEDICAMENTOS_REGISTRADOS

## Confirmacoes
- O dicionario final nao foi alterado nesta fase.
- Banco nao foi alterado.
- Fonte interna nao foi usada.
- SKU_MASTER nao foi aplicado.
