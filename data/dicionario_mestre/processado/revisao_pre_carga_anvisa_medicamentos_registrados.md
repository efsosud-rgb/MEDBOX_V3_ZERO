# Revisao da Pre-carga — ANVISA Medicamentos Registrados
## FASE 2.5 — 2026-06-26

## Objetivo
Revisar a pre-carga gerada na FASE 2.4, validar qualidade dos registros elegiveis e
preparar decisao tecnica para aplicacao controlada. Somente leitura; nenhum arquivo alterado.

## Arquivos analisados
- `pre_carga_anvisa_medicamentos_registrados.csv` (consolidado)
- `pre_carga_anvisa_medicamentos_registrados_elegiveis_padrao.csv`
- `pre_carga_anvisa_medicamentos_registrados_elegiveis_baixo_risco.csv`
- `pre_carga_anvisa_medicamentos_registrados_nao_elegiveis.csv`

## Total consolidado
43240 registros

## Total por grupo
- ELEGIVEL_PADRAO:      10301 (23.8%)
- ELEGIVEL_BAIXO_RISCO: 79 (0.2%)
- NAO_ELEGIVEL:         32860 (76.0%)
- Soma: 43240 == OK

## Validacao dos criterios de elegibilidade
- ids_pre_carga unicos: SIM
- PADRAO sem numero_registro: 0
- BAIXO_RISCO sem processo: 0
- Elegiveis sem nome E sem PA: 0
- Elegiveis sem empresa_detentora: 0
- Rastreabilidade vazia/invalida: 0
- Rastreabilidade duplicada (elegiveis): 0 chaves
- Fonte invalida: 0 | Tipo invalido: 0
- Confianca invalida: 0 | Status revisao invalido: 0

## Qualidade dos elegiveis padrao (10301 registros)
Campos criticos preenchidos:
- `nome_produto`: 10380/10380 preenchidos
- `principio_ativo`: 10366/10380 preenchidos
- `empresa_detentora`: 10380/10380 preenchidos
- `numero_registro`: 10301/10380 preenchidos
- `processo`: 10380/10380 preenchidos
- `categoria_regulatoria`: 10353/10380 preenchidos
- `tipo_produto`: 10380/10380 preenchidos
- `situacao_registro`: 10380/10380 preenchidos
- `rastreabilidade_chave`: 10380/10380 preenchidos

Top 10 empresas detentoras:
- EUROFARMA LABORATORIOS S.A.: 557
- EMS S/A: 525
- ACHÉ LABORATÓRIOS FARMACÊUTICOS S.A: 449
- LABORATÓRIO TEUTO BRASILEIRO S/A: 357
- BRAINFARMA INDÚSTRIA QUÍMICA E FARMACÊUTICA S.A: 329
- GERMED FARMACEUTICA LTDA: 315
- CRISTÁLIA PRODUTOS QUÍMICOS FARMACÊUTICOS LTDA.: 300
- MULTILAB INDUSTRIA E COMERCIO DE PRODUTOS FARMACEUTICOS LTDA: 287
- UNIÃO QUÍMICA FARMACÊUTICA NACIONAL S/A: 280
- LEGRAND PHARMA INDÚSTRIA FARMACÊUTICA LTDA: 280

Top 10 principios ativos:
- IBUPROFENO: 91
- HEMITARTARATO DE ZOLPIDEM: 69
- PREGABALINA: 61
- COLECALCIFEROL: 55
- NIMESULIDA: 53
- DESLORATADINA: 52
- LEVETIRACETAM: 48
- RIVAROXABANA: 48
- trometamol cetorolaco: 46
- CLORIDRATO  DE ONDANSETRONA DI-hIDRATADO: 42

## Qualidade dos elegiveis baixo risco (79 registros)
- Rastreabilidade por PROCESSO: 79
- Com nome_produto: 79
- Com principio_ativo: 78

## Resumo dos nao elegiveis (32860 registros)
Principais motivos:
- situacao_registro=Inativo: 22248
- sem numero_registro e sem processo: 10612

## Rastreabilidade por tipo (elegiveis)
- REGISTRO: 10301
- PROCESSO: 79

## Pendencias de revisao
- Total de pendencias: 62307
- Total bloqueantes para FASE 2.6: 0

## Checklist resumido
- [OK] arquivos_pre_carga_existem: sim
- [OK] total_consolidado: 43240
- [OK] total_elegivel_padrao: 10301
- [OK] total_elegivel_baixo_risco: 79
- [OK] total_nao_elegivel: 32860
- [OK] soma_grupos_bate_consolidado: 43240
- [OK] ids_pre_carga_unicos: sim
- [OK] rastreabilidade_elegiveis_preenchida: 0
- [OK] rastreabilidade_elegiveis_unica: 0
- [OK] elegivel_padrao_com_numero_registro: 0
- [OK] elegivel_baixo_risco_com_processo: 0
- [OK] elegiveis_com_nome_ou_principio: 0
- [OK] fonte_nome_valida: 0
- [OK] fonte_tipo_valida: 0
- [OK] confianca_valida: 0
- [OK] status_revisao_valido: 0
- [OK] pendencias_bloqueantes: 0
- [OK] dicionario_final_nao_alterado: nao alterado
- [OK] banco_nao_alterado: nao usado
- [OK] fonte_interna_nao_usada: nao acessado
- [OK] sku_master_nao_aplicado: nao aplicado
- [OK] arquivos_protegidos_nao_alterados: nenhum

## Campos vazios por limitacao da fonte (elegiveis)
- `forma_farmaceutica`: 0/10380 preenchidos (ausente no bruto ANVISA)
- `concentracao`: 0/10380 preenchidos (ausente no bruto ANVISA)
- `apresentacao`: 0/10380 preenchidos (ausente no bruto ANVISA)
- `via_uso`: 0/10380 preenchidos (ausente no bruto ANVISA)
- `restricao_prescricao`: 0/10380 preenchidos (ausente no bruto ANVISA)
- `tarja`: 0/10380 preenchidos (ausente no bruto ANVISA)

## Riscos
- Rastreabilidade duplicada (0 chaves) indica medicamentos com multiplas entradas
  com mesmo numero_registro ou processo. Nao e bloqueante, mas deve ser investigado na FASE 2.6.
- Campos forma/concentracao/apresentacao ausentes no bruto ANVISA; precisarao de
  complementacao por outras fontes apos aplicacao controlada.
- Registros BAIXO_RISCO sem numero_registro nao tem rastreabilidade por registro oficial.

## Limitacoes
- Revisao realizada exclusivamente sobre pre-carga FASE 2.4; sem cruzamento externo.
- Campos ausentes permanecem vazios e nao indicam erro de processamento.

## Recomendacao sobre registros baixo risco
**INCLUIR EM GRUPO SEPARADO** — Os 79 registros ELEGIVEL_BAIXO_RISCO apresentam processo preenchido como rastreabilidade e nome_produto ou principio_ativo identificados. Recomenda-se incluir no dicionario em grupo separado usando PROCESSO como chave, com flag 'baixo_risco=sim'.

## Decisao tecnica
**APTO_PARA_PREPARAR_APLICACAO_CONTROLADA**

A pre-carga revisada esta apta para aplicacao controlada na FASE 2.6.

## Confirmacoes de integridade
- **Dicionario final nao alterado**: dicionario_mestre_medbox.csv, dicionario_mestre_medicamentos.csv e dicionario_mestre_produtos_saude.csv nao foram lidos nem modificados.
- **Pre-carga FASE 2.4 nao alterada**: todos os arquivos lidos somente em modo leitura.
- **Banco nao usado**: nenhuma conexao com banco de dados.
- **Fonte interna nao usada**: data/dicionario_mestre/interno nao foi acessado.
- **SKU_MASTER nao aplicado**: uploads/SKU_MASTER_*.xlsx nao foi acessado.

## Proxima etapa recomendada
**FASE 2.6 — Aplicacao controlada da pre-carga ao dicionario_mestre_medicamentos.csv**
- Utilizar somente os registros ELEGIVEL_PADRAO e ELEGIVEL_BAIXO_RISCO.
- Resolver rastreabilidades duplicadas antes da mesclagem.
- Campos vazios (forma/concentracao/apresentacao) aceitos como pendencia conhecida.
- Aplicar com diff auditavel, linha por linha.
