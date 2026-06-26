# Plano de Enriquecimento — ANVISA Medicamentos Registrados

**Data:** 2026-06-26 13:15
**Fase:** 2.8 — Planejamento de enriquecimento
**Branch:** melhoria/auditoria-sku-master-todos-produtos
**Decisão técnica:** `APTO_PARA_PREPARAR_DRY_RUN_ENRIQUECIMENTO_DCB`

---

## 1. Objetivo

Planejar o enriquecimento dos campos atualmente vazios nos 10,345 registros
`ANVISA_MEDICAMENTOS_REGISTRADOS` inseridos na FASE 2.6B, especialmente:

- **DCB / CAS / classificação**: por cruzamento com a base DCB já presente no dicionário (12.715 registros).
- **Forma farmacêutica / Concentração / Apresentação / Via de uso**: por fontes oficiais complementares (ANVISA Consultas / Bulário Eletônico) em fase futura.

---

## 2. Estado atual do dicionário

| Indicador | Valor |
|---|---|
| Total registros DCB | 12,715 |
| Total registros ANVISA_MEDREG | 10,345 |
| Total geral | 23,060 |

---

## 3. Resultado do diagnóstico de cruzamento DCB x ANVISA_MEDREG

| Classificação | Quantidade | % |
|---|---|---|
| MATCH_EXATO_UNICO | 7,984 | 77.2% |
| MATCH_MULTIPLO | 0 | 0.0% |
| SEM_MATCH | 2,347 | 22.7% |
| SEM_PRINCIPIO_ATIVO | 11 | 0.1% |
| REVISAR_NORMALIZACAO | 3 | 0.0% |
| **Total** | **10,345** | **100%** |

**Pode enriquecer automaticamente (MATCH_EXATO_UNICO):** 7,984 (77.2%)

---

## 4. Estratégia para DCB / CAS / classificação

### 4.1 MATCH_EXATO_UNICO — 7,984 registros

Estes registros possuem exatamente um registro DCB correspondente pelo `principio_ativo` normalizado.

**Estratégia:** em fase futura (FASE 2.9), preparar dry-run para preencher os campos:
- `dcb` ← `dcb` do registro DCB correspondente
- `cas` ← `cas` do registro DCB correspondente
- `classificacao` ← `classificacao` do registro DCB correspondente (se vazio no MEDREG)

**Regra de aplicação:** somente se o campo estiver vazio no registro MEDREG.
Nunca sobrescrever campo já preenchido.

### 4.2 MATCH_MULTIPLO — 0 registros

Múltiplos registros DCB com o mesmo `principio_ativo` normalizado.
Não é possível determinar o candidato correto automaticamente.

**Estratégia:** manter sem enriquecimento automático. Revisar manualmente em fase futura
ou por critério adicional (ex: forma farmacêutica, número de registro).

### 4.3 SEM_MATCH — 2,347 registros

Nenhum registro DCB com `principio_ativo` equivalente.

**Estratégia:** manter sem enriquecimento DCB. Estes registros poderão receber DCB/CAS
por fontes externas (PubChem, ANVISA Consultas) em fases futuras.

### 4.4 SEM_PRINCIPIO_ATIVO — 11 registros

Campo `principio_ativo` vazio. Impossível cruzar com DCB por este campo.

**Estratégia:** tratar separadamente. Priorizar busca de `principio_ativo` por fontes
externas (ANVISA Consultas pelo número de registro) antes de tentar cruzamento DCB.

### 4.5 REVISAR_NORMALIZACAO — 3 registros

Sem `principio_ativo`, mas com correspondência por `nome_padrao`.
Requer revisão manual antes de aplicar.

---

## 5. Estratégia para forma farmacêutica / concentração / apresentação / via de uso

Estes campos não estão presentes nos dados brutos ANVISA Medicamentos Registrados
e não podem ser inferidos a partir dos dados disponíveis no dicionário atual.

**Estratégia:**
- Fonte planejada: **ANVISA Consultas** (consulta por número de registro) e/ou **Bulário Eletrônico**.
- Não preencher por inferência ou cruzamento aproximado.
- Planejar captura estruturada em fase futura dedicada (FASE 2.10+).
- Prioridade: forma_farmaceutica e concentracao (campos de alta criticidade clínica).

---

## 6. Riscos e limitações

| Risco | Impacto | Mitigação |
|---|---|---|
| Principio_ativo com grafia variante | MATCH_EXATO pode falhar | Revisar REVISAR_NORMALIZACAO; considerar fuzzy controlado em fase futura |
| MATCH_MULTIPLO com candidatos ambíguos | Enriquecimento incorreto | Não aplicar automaticamente; exigir revisão manual |
| SEM_PRINCIPIO_ATIVO (14 registros) | Campo DCB/CAS não pode ser preenchido por cruzamento | Buscar principio_ativo por ANVISA Consultas primeiro |
| Campos forma/concentração/apresentação | Exigem fonte adicional | Planejar FASE 2.10+ com ANVISA Consultas |

---

## 7. Checklist desta fase

| Item | Status | Bloqueia | Esperado | Encontrado |
|---|---|---|---|---|
| dicionario_final_existe | OK | NAO | existe | existe |
| total_dcb | OK | NAO | 12715 | 12715 |
| total_anvisa_medreg | OK | NAO | 10345 | 10345 |
| total_diagnostico | OK | NAO | 10345 | 10345 |
| total_match_exato_unico | OK | NAO | - | 7984 |
| total_match_multiplo | OK | NAO | - | 0 |
| total_sem_match | OK | NAO | - | 2347 |
| total_sem_principio_ativo | OK | NAO | - | 11 |
| total_revisar_normalizacao | OK | NAO | - | 3 |
| enriquecimento_automatico_somente_match_exato_unico | OK | NAO | 7984 | 7984 |
| dicionario_final_nao_alterado | OK | NAO | 8694344 | 8694344 |
| banco_nao_alterado | OK | NAO | nao_acessado | nao_acessado |
| fonte_interna_nao_usada | OK | NAO | nao_usada | nao_usada |
| sku_master_nao_aplicado | OK | NAO | nao_aplicado | nao_aplicado |
| arquivos_protegidos_nao_alterados | OK | NAO | intactos | intactos |

---

## 8. Confirmações de integridade

- `dicionario_mestre_medicamentos.csv` **NÃO foi alterado** (read-only confirmado, tamanho idêntico).
- Banco de dados **NÃO foi acessado**.
- Fonte interna **NÃO foi usada**.
- SKU_MASTER **NÃO foi aplicado**.
- Nenhum download realizado.
- Nenhum arquivo protegido alterado.

---

## 9. Próxima etapa recomendada

**FASE 2.9 — Dry-run de enriquecimento DCB nos registros ANVISA_MEDREG**

Escopo proposto:
- Aplicar `dcb`, `cas` e `classificacao` somente nos 7,984 registros MATCH_EXATO_UNICO.
- Usar o diagnóstico `diagnostico_cruzamento_dcb_anvisa_medreg.csv` como entrada.
- Modo dry-run primeiro, com cheklist de validação.
- Aplicar somente após aprovação humana explícita.
- Nunca sobrescrever campo já preenchido.

---

*Gerado automaticamente por `planejar_enriquecimento_anvisa_medreg.py` — FASE 2.8*
