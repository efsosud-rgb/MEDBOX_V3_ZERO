# Plano de Aplicacao Controlada — ANVISA Medicamentos Registrados
## FASE 2.6 — 2026-06-26

## Objetivo
Aplicar controladamente os registros elegíveis da pre-carga ANVISA Medicamentos Registrados
ao dicionario_mestre_medicamentos.csv. Esta fase documenta o plano e executa o dry-run;
o apply real exige aprovacao humana explicita.

## Commit base (FASE 2.5)
9a4ce02 chore: revisa pre-carga anvisa medicamentos registrados

## Estado atual do dicionario
- Arquivo: data/dicionario_mestre/dicionario_mestre_medicamentos.csv
- Total atual: 12715 registros (todos ANVISA_DCB)
- Colunas: 22

## Registros elegíveis para inserção
- ELEGIVEL_PADRAO:      10301
- ELEGIVEL_BAIXO_RISCO: 44
- Total elegiveis:       10345

## Resultado do dry-run
- INSERIR_PREVISTO:              10345
- IGNORAR_DUPLICADO_ID:          0
- IGNORAR_DUPLICADO_RASTREAB:    0
- REVISAR_ANTES_APLICAR:         0
- **Total apos apply previsto:   23060**

## Tratamento de ELEGIVEL_PADRAO
- Incluir todos com situacao_registro Ativo + numero_registro + nome ou PA.
- ID gerado: ANVISA_MEDREG_<numero_registro_normalizado>
- Rastreabilidade: REGISTRO:<numero_registro>

## Tratamento de ELEGIVEL_BAIXO_RISCO
- Incluir com processo preenchido + nome ou PA.
- ID gerado: ANVISA_MEDREG_PROC_<processo_normalizado>
- Rastreabilidade: PROCESSO:<processo>
- Flag: observacao inclui grupo=ELEGIVEL_BAIXO_RISCO

## Tratamento de NAO_ELEGIVEL
- NAO incluir registros NAO_ELEGIVEL (situacao Inativo, sem rastreabilidade, etc.)
- Esses registros permanecem em pre_carga_anvisa_medicamentos_registrados_nao_elegiveis.csv

## Mapeamento de colunas
| Coluna dicionario   | Origem                              |
|---------------------|-------------------------------------|
| id_dicionario       | ANVISA_MEDREG_<numero_registro>     |
| nome_padrao         | nome_produto ou principio_ativo     |
| sku_master_padrao   | (vazio)                             |
| principio_ativo     | principio_ativo                     |
| dcb                 | (vazio — sem cruzamento DCB)        |
| cas                 | (vazio — nao disponivel na fonte)   |
| classificacao       | categoria_regulatoria ou tipo_produto|
| concentracao        | (vazio — nao disponivel na fonte)   |
| forma_farmaceutica  | (vazio — nao disponivel na fonte)   |
| apresentacao        | (vazio — nao disponivel na fonte)   |
| via_uso             | (vazio — nao disponivel na fonte)   |
| atc                 | (vazio — nao disponivel na fonte)   |
| fonte_tipo          | EXTERNA_OFICIAL                     |
| fonte_nome          | ANVISA_MEDICAMENTOS_REGISTRADOS     |
| fonte_origem        | dados.anvisa.gov.br                 |
| url_fonte           | dados.anvisa.gov.br/...MEDICAMENTOS |
| data_coleta         | 2026-06-26                       |
| validado_internamente| nao                                |
| validado_externamente| sim                                |
| confianca           | ALTA                                |
| status_revisao      | PRE_VALIDADO_FONTE_OFICIAL          |
| observacao          | grupo + rastr + empresa + situacao  |

## Campos propositalmente vazios
dcb, cas, atc, sku_master_padrao, concentracao, forma_farmaceutica, apresentacao, via_uso
(ausentes na fonte ANVISA_MEDICAMENTOS_REGISTRADOS; serao complementados por outras fontes)

## Riscos
- Rastreabilidade duplicada entre elegiveis: primeira ocorrencia inserida, demais ignoradas.
- IDs ja existentes no dicionario: ignorados (sem atualizar registros existentes).
- Campos vazios sao conhecidos e aceitos para esta fase.
- Apply deve ser precedido de backup.

## Checklist
- [OK] fase_2_5_commitada: sim
- [OK] dicionario_final_existe: sim
- [OK] cabecalho_dicionario_preservado: 22 colunas
- [OK] pre_carga_elegivel_existe: sim
- [OK] total_elegiveis: 10345
- [OK] total_inserir_previsto: 10345
- [OK] ids_novos_unicos: sim
- [OK] sem_coluna_obrigatoria_vazia_para_id: OK
- [OK] sem_coluna_obrigatoria_vazia_para_nome: 0
- [OK] fonte_nome_valida: ANVISA_MEDICAMENTOS_REGISTRADOS
- [OK] confianca_alta: ALTA
- [OK] status_revisao_valido: PRE_VALIDADO_FONTE_OFICIAL
- [OK] sem_nao_elegiveis_no_dry_run: sim
- [OK] sem_inativos_no_dry_run: sim
- [OK] apply_nao_executado: nao executado
- [OK] dicionario_final_nao_alterado: nao alterado
- [OK] banco_nao_alterado: nao usado
- [OK] fonte_interna_nao_usada: nao acessado
- [OK] sku_master_nao_aplicado: nao aplicado
- [OK] backup_planejado: backup sera criado em backups/dicionario_mestre/ antes do apply

## Comando dry-run executado nesta fase
```
python scripts/dicionario_mestre/aplicar_pre_carga_anvisa_medicamentos_registrados.py --dry-run
```

## Comando apply futuro (NAO EXECUTADO — exige aprovacao humana)
```
python scripts/dicionario_mestre/aplicar_pre_carga_anvisa_medicamentos_registrados.py --apply --confirmar
```
**ATENCAO: NAO executar --apply sem aprovacao humana explicita do responsavel pelo projeto.**

## Backup planejado para o apply
O script cria automaticamente antes de qualquer escrita:
`backups/dicionario_mestre/dicionario_mestre_medicamentos_ANTES_ANVISA_MEDREG_YYYYMMDD_HHMMSS.csv`

## Confirmacoes de integridade desta fase
- **Dicionario final nao alterado**: lido apenas em modo leitura.
- **Apply NAO executado**: somente dry-run.
- **Banco nao usado**: nenhuma conexao.
- **Fonte interna nao usada**: data/dicionario_mestre/interno nao acessado.
- **SKU_MASTER nao aplicado**: uploads/SKU_MASTER_*.xlsx nao acessado.
