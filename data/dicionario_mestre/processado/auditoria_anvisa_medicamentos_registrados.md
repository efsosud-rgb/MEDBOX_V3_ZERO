# Auditoria do Intermediario — ANVISA Medicamentos Registrados
## FASE 2.3 — 2026-06-26

## Objetivo
Auditar o arquivo intermediario da ANVISA Medicamentos Registrados para identificar qualidade,
duplicidades, campos vazios, padroes de dados e aptidao para preparar pre-carga futura.
Somente leitura. Nenhum arquivo foi alterado.

## Arquivo auditado
`data/dicionario_mestre/processado/anvisa_medicamentos_registrados_normalizado.csv`

## Totais
- Total de registros: 43240
- Total de colunas:   27

## Contagem por status_processamento
- OK: 43240

## Contagem por situacao_registro
- Inativo: 25996
- Ativo: 17244

## Contagem por tipo_produto
- MEDICAMENTO: 43240

## Contagem por categoria_regulatoria (top 20)
- Similar: 15364
- Genérico: 8116
- BAIXO RISCO: 7075
- DINAMIZADO: 3452
- Novo: 3220
- (vazio): 1827
- Específico: 1531
- Fitoterápico: 1234
- Biológico: 920
- Dinamizado: 278
- FITOTER?PICO: 85
- Radiofármaco: 69
- Gases Medici: 61
- Produto de T: 8

## Top 20 empresas detentoras
- FARMACIA E LABORATORIO HOMEOPATICO ALMEIDA PRADO LTDA: 2636
- EMS S/A: 1205
- EUROFARMA LABORATORIOS S.A.: 976
- GERMED FARMACEUTICA LTDA: 900
- ACHÉ LABORATÓRIOS FARMACÊUTICOS S.A: 737
- BRAINFARMA INDÚSTRIA QUÍMICA E FARMACÊUTICA S.A: 710
- LEGRAND PHARMA INDÚSTRIA FARMACÊUTICA LTDA: 692
- RIOQUIMICA S.A.: 686
- UNIÃO QUÍMICA FARMACÊUTICA NACIONAL S/A: 682
- LABORATÓRIO TEUTO BRASILEIRO S/A: 664
- EMS SIGMA PHARMA LTDA: 576
- CRISTÁLIA PRODUTOS QUÍMICOS FARMACÊUTICOS LTDA.: 567
- HYPERA S.A.: 537
- SANOFI MEDLEY FARMACÊUTICA LTDA.: 524
- MULTILAB INDUSTRIA E COMERCIO DE PRODUTOS FARMACEUTICOS LTDA: 483
- COSMED INDUSTRIA DE COSMETICOS E MEDICAMENTOS S.A.: 475
- CIMED INDUSTRIA S.A: 472
- SANDOZ DO BRASIL INDÚSTRIA FARMACÊUTICA LTDA: 459
- LABORATÓRIO NEO QUÍMICA COMÉRCIO E INDÚSTRIA LTDA: 419
- NOVA QUIMICA FARMACÊUTICA S/A: 396

## Preenchimento dos campos criticos
- `nome_produto`: 43240/43240 (100.0%)
- `principio_ativo`: 29115/43240 (67.3%)
- `empresa_detentora`: 43240/43240 (100.0%)
- `numero_registro`: 32549/43240 (75.3%)
- `situacao_registro`: 43240/43240 (100.0%)
- `forma_farmaceutica`: 0/43240 (0.0%)
- `concentracao`: 0/43240 (0.0%)
- `apresentacao`: 0/43240 (0.0%)

## Campos 100% vazios
forma_farmaceutica, concentracao, apresentacao, via_uso, restricao_prescricao, tarja, motivo_status

## Registros com campos criticos ausentes
- Sem nome_produto:        0 (0.0%)
- Sem principio_ativo:     14125 (32.7%)
- Sem numero_registro:     10691 (24.7%)
- Sem empresa_detentora:   0 (0.0%)
- Sem forma_farmaceutica:  43240 (100.0%) — ausente no bruto
- Sem concentracao:        43240 (100.0%) — ausente no bruto
- Sem apresentacao:        43240 (100.0%) — ausente no bruto
- Sem via_uso:             43240 (100.0%) — ausente no bruto

## Resumo de duplicidades
- NUMERO_REGISTRO: 1 grupos de duplicidade
- NOME_PA_EMPRESA: 500 grupos de duplicidade
- PA_CONC_FORMA_APRES: 500 grupos de duplicidade
- NOME_NORMALIZADO: 500 grupos de duplicidade
- PA_NORMALIZADO: 500 grupos de duplicidade

Arquivo completo: `data/dicionario_mestre/processado/duplicidades_anvisa_medicamentos_registrados.csv`

## Resumo de pendencias
- FORMA_FARMACEUTICA_AUSENTE: 43240
- CONCENTRACAO_AUSENTE: 43240
- APRESENTACAO_AUSENTE: 43240
- PRINCIPIO_ATIVO_AUSENTE: 14125
- NUMERO_REGISTRO_AUSENTE: 10691

- **Total de pendencias**: 154536
- **Pendencias bloqueantes**: 10691

Arquivo completo: `data/dicionario_mestre/processado/pendencias_anvisa_medicamentos_registrados.csv`

## Exemplos relevantes

### Exemplo 1
- **nome_produto**: IZONAX
- **principio_ativo**: CETOCONAZOL
- **empresa_detentora**: PHARLAB INDÚSTRIA FARMACÊUTICA S.A.
- **numero_registro**: 141070069
- **situacao_registro**: Ativo
- **categoria_regulatoria**: Similar
- **status_processamento**: OK

### Exemplo 2
- **nome_produto**: OLINA ESSÊNCIA DE VIDA
- **principio_ativo**: ALOE FEROX MILL., Angelica archangelica L., GENTIANA LUTEA L., Commyphora myrrha, Rheum palmatum L., Gentiana lutea, CINNAMOMUM ZEYLANICUM NESS.
- **empresa_detentora**: LABORATÓRIO WESP LTDA
- **numero_registro**: 102990002
- **situacao_registro**: Ativo
- **categoria_regulatoria**: Fitoterápico
- **status_processamento**: OK

### Exemplo 3
- **nome_produto**: PRAVASTATINA SODICA
- **principio_ativo**: pravastatina sódica
- **empresa_detentora**: NOVA QUIMICA FARMACÊUTICA S/A
- **numero_registro**: 126750053
- **situacao_registro**: Inativo
- **categoria_regulatoria**: Genérico
- **status_processamento**: OK

### Exemplo 4
- **nome_produto**: PREGABALINA
- **principio_ativo**: PREGABALINA
- **empresa_detentora**: APSEN FARMACEUTICA S/A
- **numero_registro**: 101180620
- **situacao_registro**: Ativo
- **categoria_regulatoria**: Genérico
- **status_processamento**: OK

### Exemplo 5
- **nome_produto**: QUADRINAX
- **principio_ativo**: VALERATO DE BETAMETASONA, SULFATO DE GENTAMICINA, TOLNAFTATO, CLIOQUINOL
- **empresa_detentora**: PHARMASCIENCE INDUSTRIA FARMACEUTICA S.A
- **numero_registro**: 117170046
- **situacao_registro**: Inativo
- **categoria_regulatoria**: Similar
- **status_processamento**: OK


## Riscos
- Campos forma_farmaceutica, concentracao, apresentacao e via_uso ausentes no bruto da ANVISA.
  Precisarao ser preenchidos por outras fontes ou processo manual na pre-carga.
- Duplicidades em numero_registro devem ser investigadas antes da mesclagem com o dicionario final.
- Registros sem numero_registro (se houver) sao de rastreabilidade reduzida.

## Limitacoes
- Auditoria realizada exclusivamente sobre o intermediario gerado na FASE 2.2.
- Nenhum cruzamento com dicionario final, SKU_MASTER ou fonte interna foi realizado.
- Campos ausentes no bruto permanecem vazios e nao indicam erro de processamento.

## Decisao tecnica
**REVISAR_ANTES_PRE_CARGA**

Foram identificadas 10691 pendencias bloqueantes. Revisar antes de prosseguir.

## Confirmacoes de integridade
- **Dicionario final nao alterado**: dicionario_mestre_medbox.csv, dicionario_mestre_medicamentos.csv e dicionario_mestre_produtos_saude.csv nao foram lidos nem modificados.
- **Intermediario FASE 2.2 nao alterado**: arquivo lido em modo somente leitura.
- **Banco nao usado**: nenhuma conexao com banco de dados.
- **Fonte interna nao usada**: data/dicionario_mestre/interno nao foi acessado.
- **SKU_MASTER nao aplicado**: uploads/SKU_MASTER_*.xlsx nao foi acessado.

## Proxima etapa recomendada
**FASE 2.4 — Preparacao da pre-carga ANVISA Medicamentos Registrados**
- Definir criterios de elegibilidade (situacao_registro, tipo_produto, etc).
- Mapear campos do intermediario para o dicionario final.
- Gerar pre-dicionario de medicamentos ANVISA como rascunho auditavel.
- Nao mesclar ainda.
