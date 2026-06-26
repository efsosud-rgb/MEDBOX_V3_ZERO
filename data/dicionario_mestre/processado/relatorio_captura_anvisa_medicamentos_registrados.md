# Relatorio de captura ANVISA Medicamentos Registrados

Data/hora da captura: 2026-06-26 10:14:43 -03:00

## Objetivo da fase

Capturar de forma bruta, controlada e rastreavel a fonte oficial ANVISA Medicamentos Registrados no Brasil, sem processamento, normalizacao, mesclagem ou alteracao de dicionarios finais.

## Fonte oficial usada

- Nome: ANVISA Medicamentos Registrados no Brasil
- Orgao responsavel: ANVISA
- Pagina oficial do conjunto: https://dados.gov.br/dados/conjuntos-dados/medicamentos-registrados-no-brasil
- Consulta oficial relacionada: https://consultas.anvisa.gov.br/#/medicamentos/

## URLs acessadas

- https://dados.gov.br/dados/conjuntos-dados/medicamentos-registrados-no-brasil
- https://dados.anvisa.gov.br/dados/DADOS_ABERTOS_MEDICAMENTOS.csv
- https://dados.anvisa.gov.br/dados/Documentacao_e_Dicionario_de_Dados_Registros_Validos_Medicamento_V1.pdf

## Recurso bruto identificado

- URL operacional: https://dados.anvisa.gov.br/dados/DADOS_ABERTOS_MEDICAMENTOS.csv
- Formato real: CSV
- Metodo de captura: download direto do recurso oficial `dados.anvisa.gov.br`
- `Last-Modified` informado pelo servidor: 2026-06-26 08:55:29 GMT

## Arquivos salvos

- Arquivo bruto: data/dicionario_mestre/bruto/anvisa/anvisa_medicamentos_registrados_original.csv
- Documentacao/dicionario de dados: data/dicionario_mestre/bruto/anvisa/anvisa_medicamentos_registrados_documentacao_dicionario_dados.pdf
- Metadados: data/dicionario_mestre/bruto/anvisa/anvisa_medicamentos_registrados_metadados.txt

## Tamanho e hash

- Tamanho do arquivo bruto: 8277598 bytes
- SHA256 do arquivo bruto: A33B7C5FD96A80481F03DC1603524293964642AB0D3715887AEE3C66A7AB7A37
- Tamanho da documentacao: 1258610 bytes
- SHA256 da documentacao: 4D2066878415AA61C42FEAF6AC6A4E7A409F200CFD9E94B1485A4DA65FFD6E29

## Campos observados no cabecalho bruto

- TIPO_PRODUTO
- NOME_PRODUTO
- DATA_FINALIZACAO_PROCESSO
- CATEGORIA_REGULATORIA
- NUMERO_REGISTRO_PRODUTO
- DATA_VENCIMENTO_REGISTRO
- NUMERO_PROCESSO
- CLASSE_TERAPEUTICA
- EMPRESA_DETENTORA_REGISTRO
- SITUACAO_REGISTRO
- PRINCIPIO_ATIVO

## Limitacoes

- A fase nao processou nem validou semanticamente os registros.
- A fase nao normalizou nomes, principios ativos, empresas, situacoes ou datas.
- A fase nao vinculou os registros com a base DCB.
- A documentacao foi apenas capturada como arquivo bruto oficial.

## Confirmacoes

- Nenhum processamento foi feito.
- Nenhum dicionario final foi alterado.
- Banco nao foi usado.
- Nenhuma fonte interna foi usada.
- Nenhum SKU_MASTER foi aplicado.
- Nenhuma mesclagem foi feita.

## Proxima etapa recomendada

FASE 2.2 — processamento intermediario controlado do CSV bruto, com leitura estrutural, validacao de colunas e geracao de arquivo intermediario auditavel, ainda sem aplicar no Dicionario Mestre final.
