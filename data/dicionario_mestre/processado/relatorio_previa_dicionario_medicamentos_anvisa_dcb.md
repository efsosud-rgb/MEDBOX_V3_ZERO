# Relatório de Prévia — Dicionário de Medicamentos ANVISA DCB
**Data:** 2026-06-25
**Fase:** FASE 1.2 — Prévia de integração DCB para medicamentos

---

## Objetivo

Gerar prévia auditável de integração da ANVISA DCB para o formato futuro do dicionário de
medicamentos, sem alterar o dicionário final. Serve como base para revisão humana antes
de qualquer decisão de mesclagem.

---

## Arquivos

| | Caminho |
|--|---------|
| Entrada | `data/dicionario_mestre/processado/anvisa_dcb_normalizada.csv` |
| Saída   | `data/dicionario_mestre/processado/pre_dicionario_medicamentos_anvisa_dcb.csv` |

---

## Totais

| Métrica | Valor |
|---------|-------|
| Registros lidos | 12715 |
| Registros exportados | 12715 |
| Todos preservados | Sim |

---

## Contagem por Classificação DCB

| Classificação | Registros |
|--------------|-----------|
| INF | 9568 |
| HOM | 1170 |
| IFA | 615 |
| BIO | 514 |
| EXA | 372 |
| PM | 273 |
| RAD | 203 |

---

## Contagem por Subcategoria Sugerida

| Subcategoria | Registros |
|-------------|-----------|
| INSUMO FARMACEUTICO | 9568 |
| HOMEOPATICO | 1170 |
| INSUMO FARMACEUTICO ATIVO | 615 |
| BIOLOGICO | 514 |
| EXTRATO | 372 |
| PRODUTO MANUTENCAO | 273 |
| RADIOFARMACO | 203 |

---

## Contagem por Status de Validação

| Status | Registros |
|--------|-----------|
| PRE_VALIDADO_FONTE_OFICIAL | 12715 |

---

## Primeiros 10 Exemplos

| ID Prévia | Termo Oficial | Normalizado | CAS | Classif. | Subcategoria | Status |
|-----------|--------------|-------------|-----|----------|--------------|--------|
| DCB_000001 | abacavir | ABACAVIR | 136470-78-5 | IFA | INSUMO FARMACEUTICO ATIVO | PRE_VALIDADO_FONTE_OFICIAL |
| DCB_000002 | sulfato de abacavir | SULFATO DE ABACAVIR | 188062-50-2 | IFA | INSUMO FARMACEUTICO ATIVO | PRE_VALIDADO_FONTE_OFICIAL |
| DCB_000003 | abamectina | ABAMECTINA | 65195-55-3 | INF | INSUMO FARMACEUTICO | PRE_VALIDADO_FONTE_OFICIAL |
| DCB_000004 | abanoquila | ABANOQUILA | 90402-40-7 | INF | INSUMO FARMACEUTICO | PRE_VALIDADO_FONTE_OFICIAL |
| DCB_000006 | abaperidona | ABAPERIDONA | 183849-43-6 | INF | INSUMO FARMACEUTICO | PRE_VALIDADO_FONTE_OFICIAL |
| DCB_000007 | abarrelix | ABARRELIX | 183552-38-7 | INF | INSUMO FARMACEUTICO | PRE_VALIDADO_FONTE_OFICIAL |
| DCB_000008 | abciximabe | ABCIXIMABE | 143653-53-6 | BIO | BIOLOGICO | PRE_VALIDADO_FONTE_OFICIAL |
| DCB_000009 | abecarnila | ABECARNILA | 111841-85-1 | INF | INSUMO FARMACEUTICO | PRE_VALIDADO_FONTE_OFICIAL |
| DCB_000010 | abétimo | ABETIMO | 167362-48-3 | INF | INSUMO FARMACEUTICO | PRE_VALIDADO_FONTE_OFICIAL |
| DCB_000011 | ablucaste | ABLUCASTE | 96566-25-5 | INF | INSUMO FARMACEUTICO | PRE_VALIDADO_FONTE_OFICIAL |

---

## Confirmações de Integridade

- Nenhum banco de dados foi acessado ou alterado.
- Nenhum SQL foi executado.
- Nenhuma fonte interna foi consultada.
- Nenhum download foi realizado.
- Nenhum dicionário final foi alterado (`dicionario_mestre_medbox.csv`,
  `dicionario_mestre_medicamentos.csv`, `dicionario_mestre_produtos_saude.csv`).
- Nenhum SKU_MASTER foi aplicado.
- `app.py`, `core/`, `templates/`, `uploads/`, `backups/`, `.claude/` não foram alterados.
- Todos os 12715 registros da DCB normalizada foram preservados na prévia.

---

## Próxima Etapa Recomendada

Revisar amostra da prévia (`pre_dicionario_medicamentos_anvisa_dcb.csv`) antes de
decidir se será aplicada ao `dicionario_mestre_medicamentos.csv`. A aplicação deve
ocorrer em etapa separada, com autorização explícita, e nunca de forma automática.
