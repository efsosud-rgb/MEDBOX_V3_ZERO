# Relatório de Processamento — ANVISA DCB
**Data:** 2026-06-25
**Fase:** FASE 1.1 — Processamento intermediário ANVISA DCB

---

## Objetivo

Ler o XLSX bruto oficial da ANVISA DCB capturado na FASE 1 e gerar CSV normalizado intermediário,
sem mesclar em nenhum Dicionário Mestre e sem acessar banco ou fontes internas.

---

## Arquivo Bruto Lido

- **Caminho:** `data/dicionario_mestre/bruto/anvisa/anvisa_dcb_lista_consolidada_in_439_2026_original.xlsx`
- **Versão:** IN 439/2026
- **Status da fonte:** VIGENTE
- **Total de linhas no XLSX (incluindo título e cabeçalho):** 12718

---

## Abas Encontradas

| Aba | Usada |
|-----|-------|
| Lista DCB Consolidada | Sim |

---

## Estrutura do XLSX

- **L1:** Título da planilha (ignorado)
- **L2:** Cabeçalho das colunas
- **L3 em diante:** Dados da lista DCB
- **Última linha:** Vazia (ignorada)

---

## Colunas Encontradas no XLSX

| Posição | Nome original | Mapeado para |
|---------|--------------|--------------|
| A | Nº DCB | id_registro |
| B | DENOMINAÇÃO COMUM BRASILEIRA | termo_dcb / termo_dcb_normalizado |
| C | Nº CAS | numero_cas |
| D | CLASSIFICAÇÃO | tipo_registro |
| E | HISTÓRICO | observacao_fonte |
| F–K | (vazias) | ignoradas |

---

## Totais

| Métrica | Valor |
|---------|-------|
| Linhas brutas no XLSX (total) | 12718 |
| Linhas de dados processadas | 12716 |
| Registros exportados | 12715 |
| Registros sem termo DCB | 0 |
| Registros sem CAS | 0 |
| Registros sem classificação | 0 |
| Status OK | 12715 |
| Status INCOMPLETO | 0 |
| Status REVISAR | 0 |

---

## Primeiras 10 Linhas Normalizadas

| Nº DCB | Termo DCB | Normalizado | CAS | Tipo | Status |
|--------|-----------|-------------|-----|------|--------|
| 1 | abacavir | ABACAVIR | 136470-78-5 | IFA | OK |
| 2 | sulfato de abacavir | SULFATO DE ABACAVIR | 188062-50-2 | IFA | OK |
| 3 | abamectina | ABAMECTINA | 65195-55-3 | INF | OK |
| 4 | abanoquila | ABANOQUILA | 90402-40-7 | INF | OK |
| 6 | abaperidona | ABAPERIDONA | 183849-43-6 | INF | OK |
| 7 | abarrelix | ABARRELIX | 183552-38-7 | INF | OK |
| 8 | abciximabe | ABCIXIMABE | 143653-53-6 | BIO | OK |
| 9 | abecarnila | ABECARNILA | 111841-85-1 | INF | OK |
| 10 | abétimo | ABETIMO | 167362-48-3 | INF | OK |
| 11 | ablucaste | ABLUCASTE | 96566-25-5 | INF | OK |

---

## Confirmações de Integridade

- Nenhum banco de dados foi acessado ou alterado.
- Nenhum SQL foi executado.
- Nenhuma fonte interna foi consultada.
- Nenhum download adicional foi realizado.
- O arquivo XLSX bruto foi preservado sem edição.
- Nenhuma mesclagem no Dicionário Mestre foi executada.
- Nenhum SKU_MASTER foi aplicado.
- `app.py`, `core/`, `templates/`, `uploads/`, `backups/`, `.claude/` não foram alterados.

---

## Próxima Etapa Recomendada

Com o CSV intermediário validado, a próxima etapa é:
- validar amostra do CSV normalizado com revisão humana;
- definir mapeamento final de colunas para o Dicionário Mestre;
- somente então mesclar ao Dicionário Mestre, em etapa separada e autorizada.
