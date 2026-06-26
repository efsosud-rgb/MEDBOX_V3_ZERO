# Auditoria Pós-Aplicação — ANVISA Medicamentos Registrados

**Data:** 2026-06-26 13:10
**Fase:** 2.7 — Revisão pós-aplicação
**Branch:** melhoria/auditoria-sku-master-todos-produtos
**Decisão final:** `APTO_PARA_PLANEJAR_ENRIQUECIMENTO`

---

## 1. Sumário executivo

| Indicador | Valor |
|---|---|
| Total de registros no dicionário | 23,060 |
| Registros do backup (pré-apply) | 12,715 |
| Registros ANVISA_MEDREG inseridos | 10,345 |
| IDs tipo ANVISA_MEDREG_<numreg> (padrão) | 10,301 |
| IDs tipo ANVISA_MEDREG_PROC_<processo> (baixo risco) | 44 |
| Registros DCB preservados intactos | True |
| Itens de consistência verificados | 23 |
| Falhas | 1 |
| Falhas bloqueantes | 0 |

---

## 2. Checklist de consistência (23 itens)

| Item | Status | Bloqueia | Esperado | Obtido |
|---|---|---|---|---|
| C01_total_dicionario | OK | NAO | 23060 | 23060 |
| C02_backup_preservado | OK | NAO | 12715 | 12715 |
| C03_medreg_inseridos | OK | NAO | 10345 | 10345 |
| C04_soma_logica | OK | NAO | 23060 | 23060 |
| C05_padrao_ids_count | OK | NAO | 10301 | 10301 |
| C06_baixo_risco_ids_count | OK | NAO | 44 | 44 |
| C07_ids_unicos | OK | NAO | 0 | 0 |
| C08_colisao_ids_dcb | OK | NAO | 0 | 0 |
| C09_backup_ids_preservados | OK | NAO | 0 | 0 |
| C10_dcb_integros | OK | NAO | 0 | 0 |
| C11_fonte_tipo_correta | OK | NAO | 0 | 0 |
| C12_confianca_correta | OK | NAO | 0 | 0 |
| C13_status_revisao_correto | OK | NAO | 0 | 0 |
| C14_rastreabilidade_observacao | OK | NAO | 0 | 0 |
| C15_ids_formato_correto | OK | NAO | 0 | 0 |
| C16_sem_nome_padrao | OK | NAO | 0 | 0 |
| C17_sem_principio_ativo | FALHA | NAO | 0 | 14 |
| C18_sem_id_dicionario | OK | NAO | 0 | 0 |
| C19_sem_data_coleta | OK | NAO | 0 | 0 |
| C20_sem_url_fonte | OK | NAO | 0 | 0 |
| C21_forma_farmaceutica_vazia | OK | NAO | - | 10,345/10,345 (100.0%) |
| C22_dcb_vazio | OK | NAO | - | 10,345/10,345 (100.0%) |
| C23_atc_vazio | OK | NAO | - | 10,345/10,345 |

---

## 3. Distribuição por fonte no dicionário final

- ANVISA_DCB: 12,715
- ANVISA_MEDICAMENTOS_REGISTRADOS: 10,345

---

## 4. Pendências de enriquecimento dos registros MEDREG

| Campo | Vazios | % Vazio | Prioridade | Fonte sugerida |
|---|---|---|---|---|
| forma_farmaceutica | 10,345 | 100.0% | ALTA | ANVISA Consultas / Bulario Eletronico |
| concentracao | 10,345 | 100.0% | ALTA | ANVISA Consultas / Bulario Eletronico |
| apresentacao | 10,345 | 100.0% | ALTA | ANVISA Consultas / Bulario Eletronico |
| via_uso | 10,345 | 100.0% | ALTA | ANVISA Consultas / Bulario Eletronico |
| dcb | 10,345 | 100.0% | ALTA | Cruzamento com registros ANVISA_DCB (nome_padrao ~ prin |
| cas | 10,345 | 100.0% | ALTA | PubChem / ChemSpider por principio_ativo |
| atc | 10,345 | 100.0% | ALTA | WHO ATC Index por principio_ativo / DCB |

### Estratégia de enriquecimento sugerida

1. **DCB** — cruzamento `principio_ativo` dos MEDREG contra `nome_padrao` / `principio_ativo` dos DCB existentes.
2. **Forma farmacêutica / Concentração / Apresentação** — FASE 2.8+ via ANVISA Consultas (registro → dados completos).
3. **Via de uso** — derivável parcialmente da forma farmacêutica; complementar por ANVISA Consultas.
4. **ATC** — WHO ATC Index por DCB ou princípio ativo (fase futura).
5. **CAS** — PubChem por princípio ativo (fase futura, menor prioridade).

---

## 5. Rastreabilidade dos IDs

- Padrão (ANVISA_MEDREG_<NUMREG>): 10,301 registros — rastreados pelo número de registro ANVISA.
- Baixo risco (ANVISA_MEDREG_PROC_<PROCESSO>): 44 registros — rastreados pelo número de processo.
- Registros sem rastreabilidade no campo `observacao`: 0.

---

## 6. Integridade dos registros DCB originais

- Registros no backup: 12,715
- IDs do backup perdidos no dicionário final: 0
- Registros DCB com campos alterados: 0
- **Conclusão:** DCB 100% PRESERVADOS E INTACTOS

---

## 7. Arquivos gerados por esta fase

| Arquivo | Descrição |
|---|---|
| `processado/consistencia_pos_aplicacao_anvisa_medicamentos_registrados.csv` | 23 itens de consistência |
| `processado/pendencias_enriquecimento_anvisa_medicamentos_registrados.csv` | 7 campos a enriquecer |
| `processado/amostra_pos_aplicacao_anvisa_medicamentos_registrados.csv` | 59 registros de amostra |
| `docs/auditoria_pos_aplicacao_anvisa_medicamentos_registrados.md` | Este relatório |

---

## 8. Decisão

**APTO_PARA_PLANEJAR_ENRIQUECIMENTO**

Nenhuma falha bloqueante identificada. O dicionário está íntegro e os 10.345 registros ANVISA_MEDREG foram aplicados corretamente. A próxima etapa é planejar o enriquecimento dos campos vazios, priorizando forma_farmaceutica, concentracao e apresentacao via ANVISA Consultas.

---

*Gerado automaticamente por `revisar_pos_aplicacao_anvisa_medicamentos_registrados.py` — FASE 2.7*
