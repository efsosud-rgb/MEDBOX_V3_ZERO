# Plano de Aplicação — Enriquecimento DCB/CAS/Classificação em ANVISA_MEDREG

**Data:** 2026-06-26 13:22
**Fase:** 2.9 — Dry-run de enriquecimento DCB
**Branch:** melhoria/auditoria-sku-master-todos-produtos
**Commit base:** `3a1db5b` (chore: planeja enriquecimento anvisa medreg)
**Decisão técnica:** `APTO_PARA_APLICACAO_CONTROLADA_ENRIQUECIMENTO_DCB`

---

## 1. Objetivo

Preencher os campos `dcb`, `cas` e `classificacao` nos registros `ANVISA_MEDICAMENTOS_REGISTRADOS`
que possuem correspondência exata e única com a base DCB já presente no dicionário mestre.

Este documento descreve o dry-run executado. **A aplicação real não foi executada.**

---

## 2. Escopo

| Indicador | Valor |
|---|---|
| Total ANVISA_MEDREG no dicionário | 10,345 |
| MATCH_EXATO_UNICO elegíveis | 7,984 |
| Fora do escopo (SEM_MATCH + SEM_PA + REVISAR + MULTIPLO) | 2,361 |

---

## 3. Resultado do dry-run

| Ação prevista | Quantidade |
|---|---|
| ENRIQUECER_PREVISTO | 7,984 |
| IGNORAR_JA_PREENCHIDO | 0 |
| REVISAR_CONFLITO | 0 |
| REVISAR_DADOS_INCOMPLETOS | 0 |
| **Total dry-run** | **7,984** |

### Campos que seriam preenchidos

| Campo | Ocorrências |
|---|---|
| dcb | 7,984 |
| cas | 7,984 |
| classificacao | 0 |
| **Total campos a alterar** | **15,968** |

---

## 4. Campos no escopo desta aplicação

- `dcb` — preencher se vazio
- `cas` — preencher se vazio

## 5. Campos explicitamente fora do escopo

- `classificacao` — **EXCLUÍDO**: nos MEDREG contém categoria regulatória ANVISA (Genérico, Similar, Biológico); nos DCB contém classe farmacêutica (INSUMO FARMACEUTICO). Semânticas distintas — não devem ser cruzadas.
- `forma_farmaceutica` — requer ANVISA Consultas (FASE 2.10+)
- `concentracao` — requer ANVISA Consultas (FASE 2.10+)
- `apresentacao` — requer ANVISA Consultas (FASE 2.10+)
- `via_uso` — requer ANVISA Consultas (FASE 2.10+)
- `atc` — requer WHO ATC Index (fase futura)
- `nome_padrao` — nunca alterar
- `principio_ativo` — nunca alterar
- `sku_master_padrao` — nunca alterar

---

## 6. Riscos e limitações

| Risco | Impacto | Mitigação |
|---|---|---|
| REVISAR_CONFLITO (0) | Campo já preenchido com valor diferente | Não aplicar automaticamente; exigir revisão manual |
| REVISAR_DADOS_INCOMPLETOS (0) | ID não encontrado | Investigar antes de aplicar |
| Principio_ativo com variações de grafia | 2.347 SEM_MATCH não recebem DCB | Tratar em fase futura com normalização adicional |
| Campos cas/dcb vazios no DCB candidato | Não enriquece campo ausente | Campo permanece vazio; sem impacto negativo |

---

## 7. Checklist do dry-run

| Item | Status | Bloqueia apply | Esperado | Encontrado |
|---|---|---|---|---|
| fase_2_8_commitada | OK | NAO | FASE 2.8 documentada em CHECKPOINT | OK |
| dicionario_final_existe | OK | NAO | existe | existe |
| diagnostico_cruzamento_existe | OK | NAO | existe | existe |
| total_match_exato_unico | OK | NAO | 7984 | 7984 |
| total_dry_run | OK | NAO | 7984 | 7984 |
| somente_match_exato_unico | OK | NAO | todos_MATCH_EXATO_UNICO | OK |
| somente_pode_enriquecer_sim | OK | NAO | - | dry-run derivado de pode_enriquecer=SIM |
| nenhum_sem_match_no_dry_run | OK | NAO | 0 | 0 |
| nenhum_match_multiplo_no_dry_run | OK | NAO | 0 | 0 |
| ids_medreg_existentes_no_dicionario | OK | NAO | 0 | 0 |
| ids_dcb_existentes_no_dicionario | OK | NAO | 0 | 0 |
| sem_conflitos_bloqueantes | OK | NAO | 0 | 0 |
| apply_nao_executado | OK | NAO | nao_executado | nao_executado |
| dicionario_final_nao_alterado | OK | NAO | 8694344 | 8694344 |
| banco_nao_alterado | OK | NAO | nao_acessado | nao_acessado |
| fonte_interna_nao_usada | OK | NAO | nao_usada | nao_usada |
| sku_master_nao_aplicado | OK | NAO | nao_aplicado | nao_aplicado |
| arquivos_protegidos_nao_alterados | OK | NAO | intactos | intactos |

---

## 8. Comandos

### Dry-run (já executado):
```
python scripts/dicionario_mestre/preparar_dry_run_enriquecimento_dcb_anvisa_medreg.py
```

### Aplicação futura (NÃO EXECUTADO — requer aprovação humana explícita):
```
python scripts/dicionario_mestre/aplicar_enriquecimento_dcb_anvisa_medreg.py --apply --confirmar
```
> **ATENÇÃO:** Só executar após aprovação explícita do responsável pelo projeto.

---

## 9. Confirmações de integridade

- `dicionario_mestre_medicamentos.csv` **NÃO foi alterado** (read-only confirmado, 8,694,344 bytes idênticos).
- Banco de dados **NÃO foi acessado**.
- Fonte interna **NÃO foi usada**.
- SKU_MASTER **NÃO foi aplicado**.
- Apply **NÃO foi executado** — este documento descreve apenas o dry-run.

---

## 10. Decisão

**APTO_PARA_APLICACAO_CONTROLADA_ENRIQUECIMENTO_DCB**

Nenhuma falha bloqueante no dry-run. O enriquecimento de 7984 registros pode ser preparado para aplicação controlada na FASE 2.10. Aplicar somente após aprovação humana explícita.

---

*Gerado automaticamente por `preparar_dry_run_enriquecimento_dcb_anvisa_medreg.py` — FASE 2.9*
