# Relatório de Carga Prévia — Dicionário de Medicamentos ANVISA DCB
**Data:** 2026-06-25
**Fase:** FASE 1.4 — Preparar carga final controlada da DCB para dicionário de medicamentos

---

## Objetivo

Gerar carga final controlada da ANVISA DCB compatível com a estrutura real do
`dicionario_mestre_medicamentos.csv`, sem alterar o dicionário final.

---

## Arquivos

| | Caminho |
|--|---------|
| Entrada (prévia) | `data/dicionario_mestre/processado/pre_dicionario_medicamentos_anvisa_dcb.csv` |
| Dicionário final (somente leitura) | `data/dicionario_mestre/dicionario_mestre_medicamentos.csv` |
| Carga prévia gerada | `data/dicionario_mestre/processado/carga_previa_dicionario_medicamentos_anvisa_dcb.csv` |
| Diff gerado | `data/dicionario_mestre/processado/diff_carga_dicionario_medicamentos_anvisa_dcb.csv` |

---

## Estrutura Encontrada no Dicionário Final

**Status:** Arquivo com cabeçalho e **0 linha(s) de dados** (vazio)

**Colunas (22):**

- `id_dicionario`
- `nome_padrao`
- `sku_master_padrao`
- `principio_ativo`
- `dcb`
- `cas`
- `classificacao`
- `concentracao`
- `forma_farmaceutica`
- `apresentacao`
- `via_uso`
- `atc`
- `fonte_tipo`
- `fonte_nome`
- `fonte_origem`
- `url_fonte`
- `data_coleta`
- `validado_internamente`
- `validado_externamente`
- `confianca`
- `status_revisao`
- `observacao`

**Estrutura compatível com carga:** SIM

---

## Totais

| Métrica | Valor |
|---------|-------|
| Registros lidos da prévia | 12715 |
| Registros preparados na carga | 12715 |
| Ações INSERIR_PREVISTO no diff | 12715 |

---

## Por pode_aplicar

| pode_aplicar | Registros |
|-------------|-----------|
| SIM | 12715 |

---

## Colunas Mapeadas (16)

- `id_dicionario` → GERADO
- `nome_padrao` → DCB:termo_oficial
- `principio_ativo` → DCB:termo_oficial
- `dcb` → DCB:termo_normalizado
- `cas` → DCB:numero_cas
- `classificacao` → DCB:subcategoria_sugerida
- `fonte_tipo` → FIXO:OFICIAL_ANVISA
- `fonte_nome` → DCB:fonte
- `fonte_origem` → DCB:versao_fonte
- `url_fonte` → FIXO:https://www.gov.br/anvisa/pt-br/assuntos/farmacopeia/dcb
- `data_coleta` → DCB:data_geracao
- `validado_internamente` → FIXO:nao
- `validado_externamente` → FIXO:sim
- `confianca` → DCB:confianca_fonte
- `status_revisao` → DCB:status_validacao
- `observacao` → DCB:historico_dcb

---

## Colunas Sem Equivalente na DCB (6)

- `sku_master_padrao` — deixada vazia
- `concentracao` — deixada vazia
- `forma_farmaceutica` — deixada vazia
- `apresentacao` — deixada vazia
- `via_uso` — deixada vazia
- `atc` — deixada vazia

---

## Primeiros 10 Registros da Carga

| ID Dicionário | Nome Padrão | CAS | Classificação | Status |
|--------------|------------|-----|--------------|--------|
| DCB_000001 | abacavir | 136470-78-5 | INSUMO FARMACEUTICO ATIVO | PRE_VALIDADO_FONTE_OFICIAL |
| DCB_000002 | sulfato de abacavir | 188062-50-2 | INSUMO FARMACEUTICO ATIVO | PRE_VALIDADO_FONTE_OFICIAL |
| DCB_000003 | abamectina | 65195-55-3 | INSUMO FARMACEUTICO | PRE_VALIDADO_FONTE_OFICIAL |
| DCB_000004 | abanoquila | 90402-40-7 | INSUMO FARMACEUTICO | PRE_VALIDADO_FONTE_OFICIAL |
| DCB_000006 | abaperidona | 183849-43-6 | INSUMO FARMACEUTICO | PRE_VALIDADO_FONTE_OFICIAL |
| DCB_000007 | abarrelix | 183552-38-7 | INSUMO FARMACEUTICO | PRE_VALIDADO_FONTE_OFICIAL |
| DCB_000008 | abciximabe | 143653-53-6 | BIOLOGICO | PRE_VALIDADO_FONTE_OFICIAL |
| DCB_000009 | abecarnila | 111841-85-1 | INSUMO FARMACEUTICO | PRE_VALIDADO_FONTE_OFICIAL |
| DCB_000010 | abétimo | 167362-48-3 | INSUMO FARMACEUTICO | PRE_VALIDADO_FONTE_OFICIAL |
| DCB_000011 | ablucaste | 96566-25-5 | INSUMO FARMACEUTICO | PRE_VALIDADO_FONTE_OFICIAL |

---

## Riscos e Pendências Antes da Aplicação Real

- O dicionário final não foi alterado nesta fase.
- Antes da aplicação real, revisar:
  - As 24 duplicidades de CAS identificadas na FASE 1.3.
  - Os 54 termos longos/incomuns identificados na FASE 1.3.
  - Definir se `sku_master_padrao`, `concentracao`, `forma_farmaceutica`,
    `apresentacao`, `via_uso` e `atc` serão preenchidos por outras fontes
    antes ou após a inserção da DCB.
  - A aplicação real deve usar script separado com dry-run obrigatório
    e autorização explícita do responsável.

---

## Recomendação Final

**APTO_PARA_REVISAR_CARGA**

A carga prévia foi gerada corretamente com 12715 registros compatíveis com
a estrutura real do dicionário final. Nenhuma aplicação foi realizada.

---

## Confirmações de Integridade

- Nenhum dicionário final foi alterado.
- Nenhuma fonte interna foi consultada.
- Nenhum banco de dados foi acessado ou alterado.
- Nenhum SKU_MASTER foi aplicado.
- Nenhuma mesclagem foi realizada.
- `app.py`, `core/`, `templates/`, `uploads/`, `backups/`, `.claude/` não foram alterados.
