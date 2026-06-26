# Relatorio de Processamento — ANVISA Medicamentos Registrados
## FASE 2.2 — 2026-06-26

## Objetivo
Processar o CSV bruto da ANVISA Medicamentos Registrados para um arquivo intermediario auditavel,
sem alterar dicionario final, sem banco, sem fonte interna e sem SKU_MASTER.

## Arquivo bruto usado
`data/dicionario_mestre/bruto/anvisa/anvisa_medicamentos_registrados_original.csv`

## Encoding detectado / usado
`cp1252`

## Separador detectado / usado
`;` (ponto e virgula)

## Totais
- Total de linhas no bruto (com cabecalho): 43241
- Total de registros lidos: 43240
- Total de registros exportados: 43240

## Colunas originais encontradas (11)
TIPO_PRODUTO, NOME_PRODUTO, DATA_FINALIZACAO_PROCESSO, CATEGORIA_REGULATORIA, NUMERO_REGISTRO_PRODUTO, DATA_VENCIMENTO_REGISTRO, NUMERO_PROCESSO, CLASSE_TERAPEUTICA, EMPRESA_DETENTORA_REGISTRO, SITUACAO_REGISTRO, PRINCIPIO_ATIVO

## Colunas padronizadas geradas (27)
id_registro_processamento, fonte, versao_fonte, arquivo_origem, linha_origem, nome_produto, principio_ativo, principio_ativo_normalizado, empresa_detentora, cnpj_empresa, numero_registro, categoria_regulatoria, tipo_produto, situacao_registro, data_registro, data_validade, processo, classe_terapeutica, forma_farmaceutica, concentracao, apresentacao, via_uso, restricao_prescricao, tarja, campo_original_json, status_processamento, motivo_status

## Colunas esperadas nao encontradas no bruto
forma_farmaceutica, concentracao, apresentacao, via_uso, restricao_prescricao, tarja
(mantidas vazias no intermediario)

## Contagem por status_processamento
- OK: 43240
- REVISAR: 0
- ERRO_ESTRUTURA: 0

## Perfil resumido de preenchimento (colunas do bruto)
- `tipo_produto`: 100.0% preenchido (43240/43240)
- `nome_produto`: 100.0% preenchido (43240/43240)
- `data_registro`: 99.8% preenchido (43161/43240)
- `categoria_regulatoria`: 95.8% preenchido (41413/43240)
- `numero_registro`: 75.3% preenchido (32549/43240)
- `data_validade`: 85.9% preenchido (37139/43240)
- `processo`: 75.5% preenchido (32628/43240)
- `classe_terapeutica`: 73.7% preenchido (31856/43240)
- `empresa_detentora`: 100.0% preenchido (43240/43240)
- `situacao_registro`: 100.0% preenchido (43240/43240)
- `principio_ativo`: 67.3% preenchido (29115/43240)

## 10 exemplos processados

### Exemplo 1
- **nome_produto**: GASTROGEL FRESH
- **principio_ativo**: 
- **numero_registro**: 
- **empresa_detentora**: MEDQUIMICA INDÚSTRIA FARMACÊUTICA LTDA
- **cnpj_empresa**: 17875154000391
- **situacao_registro**: Ativo
- **categoria_regulatoria**: BAIXO RISCO
- **status_processamento**: OK

### Exemplo 2
- **nome_produto**: IZONAX
- **principio_ativo**: CETOCONAZOL
- **numero_registro**: 141070069
- **empresa_detentora**: PHARLAB INDÚSTRIA FARMACÊUTICA S.A.
- **cnpj_empresa**: 02501297000102
- **situacao_registro**: Ativo
- **categoria_regulatoria**: Similar
- **status_processamento**: OK

### Exemplo 3
- **nome_produto**: LAXSOFT
- **principio_ativo**: 
- **numero_registro**: 
- **empresa_detentora**: CIFARMA CIENTÍFICA FARMACÊUTICA LTDA
- **cnpj_empresa**: 17562075000169
- **situacao_registro**: Inativo
- **categoria_regulatoria**: BAIXO RISCO
- **status_processamento**: OK

### Exemplo 4
- **nome_produto**: MARESIS
- **principio_ativo**: 
- **numero_registro**: 
- **empresa_detentora**: FARMOQUIMICA S/A
- **cnpj_empresa**: 33349473000310
- **situacao_registro**: Inativo
- **categoria_regulatoria**: BAIXO RISCO
- **status_processamento**: OK

### Exemplo 5
- **nome_produto**: N?O DECLARADO
- **principio_ativo**: 
- **numero_registro**: 
- **empresa_detentora**: FARMACIA E LABORATORIO HOMEOPATICO ALMEIDA PRADO LTDA
- **cnpj_empresa**: 60862208000141
- **situacao_registro**: Ativo
- **categoria_regulatoria**: DINAMIZADO
- **status_processamento**: OK

### Exemplo 6
- **nome_produto**: OLINA ESSÊNCIA DE VIDA
- **principio_ativo**: ALOE FEROX MILL., Angelica archangelica L., GENTIANA LUTEA L., Commyphora myrrha, Rheum palmatum L., Gentiana lutea, CINNAMOMUM ZEYLANICUM NESS.
- **numero_registro**: 102990002
- **empresa_detentora**: LABORATÓRIO WESP LTDA
- **cnpj_empresa**: 92690999000166
- **situacao_registro**: Ativo
- **categoria_regulatoria**: Fitoterápico
- **status_processamento**: OK

### Exemplo 7
- **nome_produto**: PRAVASTATINA SODICA
- **principio_ativo**: pravastatina sódica
- **numero_registro**: 126750053
- **empresa_detentora**: NOVA QUIMICA FARMACÊUTICA S/A
- **cnpj_empresa**: 72593791000111
- **situacao_registro**: Inativo
- **categoria_regulatoria**: Genérico
- **status_processamento**: OK

### Exemplo 8
- **nome_produto**: PREGABALINA
- **principio_ativo**: PREGABALINA
- **numero_registro**: 101180620
- **empresa_detentora**: APSEN FARMACEUTICA S/A
- **cnpj_empresa**: 62462015000129
- **situacao_registro**: Ativo
- **categoria_regulatoria**: Genérico
- **status_processamento**: OK

### Exemplo 9
- **nome_produto**: QUADRINAX
- **principio_ativo**: VALERATO DE BETAMETASONA, SULFATO DE GENTAMICINA, TOLNAFTATO, CLIOQUINOL
- **numero_registro**: 117170046
- **empresa_detentora**: PHARMASCIENCE INDUSTRIA FARMACEUTICA S.A
- **cnpj_empresa**: 25773037000183
- **situacao_registro**: Inativo
- **categoria_regulatoria**: Similar
- **status_processamento**: OK

### Exemplo 10
- **nome_produto**: SOLUçãO IODADA 0,1% UNIPHAR
- **principio_ativo**: 
- **numero_registro**: 
- **empresa_detentora**: J.R.D. INDÚSTRIA FARMACÊUTICA LTDA.
- **cnpj_empresa**: 03869526000109
- **situacao_registro**: Ativo
- **categoria_regulatoria**: BAIXO RISCO
- **status_processamento**: OK


## Riscos e pendencias
- Encoding: arquivo apresenta caracteres especiais (entidades HTML e acentuados). Tratamento via html.unescape e errors=replace.
- DATA_FINALIZACAO_PROCESSO mapeada como data_registro.
- DATA_VENCIMENTO_REGISTRO mapeada como data_validade.
- CNPJ extraido de EMPRESA_DETENTORA_REGISTRO por regex; sem CNPJ detectavel, campo fica vazio.
- Campos de forma_farmaceutica, concentracao, apresentacao, via_uso, restricao_prescricao e tarja ausentes no bruto.
- Registros REVISAR devem ser revisados na FASE 2.3.

## Confirmacoes de integridade
- **Dicionario final nao alterado**: dicionario_mestre_medbox.csv, dicionario_mestre_medicamentos.csv e dicionario_mestre_produtos_saude.csv nao foram lidos nem modificados.
- **Banco nao usado**: nenhuma conexao com banco de dados foi realizada.
- **Fonte interna nao usada**: data/dicionario_mestre/interno nao foi acessado.
- **SKU_MASTER nao aplicado**: uploads/SKU_MASTER_*.xlsx nao foi acessado.
- **Bruto preservado intacto**: arquivo bruto aberto somente em modo leitura.

## Proxima etapa recomendada
**FASE 2.3 — Auditoria do intermediario**
- Revisar registros com status REVISAR e ERRO_ESTRUTURA.
- Avaliar preenchimento dos campos de identificacao.
- Planejar cruzamento com dicionario final (somente leitura do intermediario).
