# FASE 2.14A — Preparação da amostra 100 MEDREG

## Objetivo

Preparar, sem internet e sem captura bruta, uma amostra controlada de 100 registros ANVISA_MEDREG para futura captura na FASE 2.14B.

## Arquivo fonte usado

- data/dicionario_mestre/dicionario_mestre_medicamentos.csv

Esse arquivo foi usado somente em leitura. O dicionário final não foi alterado.

## Critérios de seleção

- Filtrar registros de origem ANVISA_MEDREG.
- Exigir número de registro ANVISA válido quando disponível.
- Priorizar registros com dcb e cas preenchidos.
- Incluir pequena parcela de registros sem dcb/cas para testar falhas futuras.
- Exigir campos alvo vazios quando disponíveis: forma_farmaceutica, concentracao, apresentacao e via_uso.
- Evitar repetição excessiva do mesmo princípio ativo/produto.
- Manter saída separada em arquivo processado auditável.

## Totais

- Total de registros no arquivo fonte: 23.060
- Total de registros ANVISA_MEDREG encontrados: 10.345
- Total de registros elegíveis com registro válido e campos-alvo vazios: 10.301
- Total de registros elegíveis com dcb/cas: 7.947
- Total de registros elegíveis sem dcb/cas: 2.354
- Total de registros selecionados: 100
- Selecionados com dcb/cas: 85
- Selecionados sem dcb/cas: 15
- Princípios ativos únicos na amostra: 100
- Produtos únicos na amostra: 99

## Campos presentes na origem

- id_dicionario
- nome_padrao
- principio_ativo
- dcb
- cas
- classificacao
- concentracao
- forma_farmaceutica
- apresentacao
- via_uso
- fonte_nome
- fonte_origem
- url_fonte
- data_coleta
- observacao

## Campos ausentes ou derivados

- registro_anvisa: derivado de id_dicionario no padrão ANVISA_MEDREG_<numero>
- empresa: derivada de observacao quando disponível
- origem: derivada de fonte_nome

## Arquivos gerados

- scripts/dicionario_mestre/preparar_amostra_medreg_100.py
- data/dicionario_mestre/processado/amostra_medreg_100_para_captura.csv
- data/dicionario_mestre/processado/checklist_preparacao_amostra_medreg_100.csv
- data/dicionario_mestre/externo/relatorio_preparacao_amostra_medreg_100.md

## Confirmações

- Internet não foi acessada.
- Scraping não foi executado.
- Crawler não foi executado.
- Captura bruta não foi executada.
- Nenhuma consulta ANVISA foi feita.
- Banco não foi alterado.
- Dicionário final não foi alterado.
- Fonte interna não foi usada.
- SKU_MASTER não foi aplicado.
- Forma farmacêutica, concentração, apresentação e via de uso não foram preenchidos.

## Decisão técnica

APTO_PARA_CAPTURA_BRUTA_CONTROLADA_AMOSTRA_100

## Próxima fase recomendada

FASE 2.14B — captura bruta controlada em fonte ANVISA, somente após autorização explícita.
