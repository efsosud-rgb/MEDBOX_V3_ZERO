# Relatorio de Pre-carga — ANVISA Medicamentos Registrados
## FASE 2.4 — 2026-06-26

## Objetivo
Preparar pre-carga auditavel a partir do intermediario ANVISA Medicamentos Registrados,
separando registros por elegibilidade. Sem aplicacao no dicionario final.

## Arquivos de entrada
- `data/dicionario_mestre/processado/anvisa_medicamentos_registrados_normalizado.csv`
- `data/dicionario_mestre/processado/duplicidades_anvisa_medicamentos_registrados.csv`
- `data/dicionario_mestre/processado/pendencias_anvisa_medicamentos_registrados.csv`

## Total de registros analisados
43240

## Total por grupo de elegibilidade
- ELEGIVEL_PADRAO:      10301 (23.8%)
- ELEGIVEL_BAIXO_RISCO: 79 (0.2%)
- NAO_ELEGIVEL:         32860 (76.0%)

## Criterios aplicados

### ELEGIVEL_PADRAO
- situacao_registro = "Ativo"
- numero_registro preenchido
- nome_produto OU principio_ativo preenchido
- status_processamento = OK

### ELEGIVEL_BAIXO_RISCO
- numero_registro vazio E processo preenchido
- nome_produto OU principio_ativo preenchido
- status_processamento = OK
- Rastreabilidade garantida pelo numero do processo

### NAO_ELEGIVEL
- status_processamento diferente de OK
- sem nome_produto E sem principio_ativo
- sem numero_registro E sem processo
- situacao_registro "Inativo" com numero_registro preenchido

## Tratamento dos registros BAIXO RISCO sem numero_registro
Os 79 registros de BAIXO RISCO sem numero_registro nao foram descartados.
Por regulacao ANVISA, medicamentos BAIXO RISCO, DINAMIZADO e similares podem nao
exigir numero de registro formal e usam numero de processo como identificador.
Esses registros foram agrupados em ELEGIVEL_BAIXO_RISCO com rastreabilidade pelo processo.

## Rastreabilidade por tipo de chave
- PROCESSO: 79
- REGISTRO: 32549
- SEM_RASTREABILIDADE: 10612

## Principais motivos de nao elegibilidade
- situacao_registro=Inativo: 22248
- sem numero_registro e sem processo: 10612

## Checklist resumido
- [OK] arquivo_intermediario_existe: sim
- [OK] total_intermediario: 43240
- [OK] total_pre_carga: 43240
- [OK] total_elegivel_padrao: 10301
- [OK] total_elegivel_baixo_risco: 79
- [OK] total_nao_elegivel: 32860
- [OK] ids_pre_carga_unicos: sim
- [OK] rastreabilidade_elegiveis_preenchida: OK
- [OK] sem_nome_e_principio_nos_elegiveis: 0
- [OK] status_processamento_ok_nos_elegiveis: 0
- [OK] numero_registro_presente_no_padrao: 0
- [OK] processo_presente_no_baixo_risco: 0
- [OK] dicionario_final_nao_alterado: nao alterado
- [OK] banco_nao_alterado: nao usado
- [OK] fonte_interna_nao_usada: nao acessado
- [OK] sku_master_nao_aplicado: nao aplicado
- [OK] arquivos_protegidos_nao_alterados: nenhum alterado

## Campos que permanecem vazios por limitacao da fonte
Os seguintes campos nao existem no bruto ANVISA e permanecem vazios:
- forma_farmaceutica
- concentracao
- apresentacao
- via_uso
- restricao_prescricao
- tarja
Esses campos precisarao ser complementados por outras fontes em fases futuras.

## Riscos
- Registros com situacao_registro "Inativo" (n=32860 em parte) foram excluidos;
  revisar se algum inativo e necessario para rastreabilidade historica.
- Duplicidades ALTA de numero_registro foram sinalizadas como PRE_VALIDADO_PENDENTE_REVISAO.
- Campos de forma/concentracao/apresentacao ausentes limitam uso direto na pre-carga.

## Limitacoes
- Pre-carga gerada exclusivamente do intermediario ANVISA; sem cruzamento com outros dicionarios.
- Nenhum dado foi inventado; campos ausentes permanecem vazios conforme a fonte.

## Decisao tecnica
**APTO_PARA_REVISAR_PRE_CARGA**

A pre-carga esta estruturalmente correta e pronta para revisao na FASE 2.5.

## Confirmacoes de integridade
- **Dicionario final nao alterado**: dicionario_mestre_medbox.csv, dicionario_mestre_medicamentos.csv e dicionario_mestre_produtos_saude.csv nao foram lidos nem modificados.
- **Intermediario FASE 2.2 nao alterado**: lido somente em modo leitura.
- **Auditoria FASE 2.3 nao alterada**: lida somente em modo leitura.
- **Banco nao usado**: nenhuma conexao com banco de dados.
- **Fonte interna nao usada**: data/dicionario_mestre/interno nao acessado.
- **SKU_MASTER nao aplicado**: uploads/SKU_MASTER_*.xlsx nao acessado.

## Proxima etapa recomendada
**FASE 2.5 — Revisao da pre-carga ANVISA Medicamentos Registrados**
- Revisar registros ELEGIVEL_PADRAO com PRE_VALIDADO_PENDENTE_REVISAO (duplicidades ALTA).
- Avaliar elegibilidade do grupo BAIXO_RISCO para o dicionario final.
- Planejar complementacao dos campos vazios (forma/concentracao/apresentacao) por outras fontes.
- Apos revisao, aprovar mesclagem ao dicionario_mestre_medicamentos.csv.
