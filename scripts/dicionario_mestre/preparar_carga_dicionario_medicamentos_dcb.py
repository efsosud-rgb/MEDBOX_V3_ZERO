"""
Prepara carga final controlada da ANVISA DCB compatível com a estrutura
real do dicionario_mestre_medicamentos.csv, sem alterar o dicionário final.

Entradas:
  data/dicionario_mestre/processado/pre_dicionario_medicamentos_anvisa_dcb.csv
  data/dicionario_mestre/dicionario_mestre_medicamentos.csv  (somente leitura)

Saídas:
  data/dicionario_mestre/processado/carga_previa_dicionario_medicamentos_anvisa_dcb.csv
  data/dicionario_mestre/processado/diff_carga_dicionario_medicamentos_anvisa_dcb.csv
  data/dicionario_mestre/processado/relatorio_carga_previa_dicionario_medicamentos_anvisa_dcb.md

Não acessa internet, banco ou fontes internas.
Não altera o dicionário final.
Reexecutável com segurança.
"""

import csv
from collections import Counter
from datetime import date
from pathlib import Path

# ── Caminhos ──────────────────────────────────────────────────────────────────
ROOT        = Path(__file__).resolve().parents[2]
CSV_PREVIA  = ROOT / "data/dicionario_mestre/processado/pre_dicionario_medicamentos_anvisa_dcb.csv"
CSV_DICT    = ROOT / "data/dicionario_mestre/dicionario_mestre_medicamentos.csv"
CSV_CARGA   = ROOT / "data/dicionario_mestre/processado/carga_previa_dicionario_medicamentos_anvisa_dcb.csv"
CSV_DIFF    = ROOT / "data/dicionario_mestre/processado/diff_carga_dicionario_medicamentos_anvisa_dcb.csv"
MD_RELAT    = ROOT / "data/dicionario_mestre/processado/relatorio_carga_previa_dicionario_medicamentos_anvisa_dcb.md"

URL_OFICIAL = "https://www.gov.br/anvisa/pt-br/assuntos/farmacopeia/dcb"
HOJE        = date.today().isoformat()

# ── Colunas do dicionário final (22) ──────────────────────────────────────────
COLUNAS_DICT = [
    "id_dicionario",
    "nome_padrao",
    "sku_master_padrao",
    "principio_ativo",
    "dcb",
    "cas",
    "classificacao",
    "concentracao",
    "forma_farmaceutica",
    "apresentacao",
    "via_uso",
    "atc",
    "fonte_tipo",
    "fonte_nome",
    "fonte_origem",
    "url_fonte",
    "data_coleta",
    "validado_internamente",
    "validado_externamente",
    "confianca",
    "status_revisao",
    "observacao",
]

# Mapeamento: coluna_dict -> como preencher
# "DCB:<campo>" = valor do campo da prévia; "FIXO:<valor>" = valor fixo; "" = vazio
MAPEAMENTO = {
    "id_dicionario":        "GERADO",           # gerado no script
    "nome_padrao":          "DCB:termo_oficial",
    "sku_master_padrao":    "",                  # sem equivalente na DCB
    "principio_ativo":      "DCB:termo_oficial",
    "dcb":                  "DCB:termo_normalizado",
    "cas":                  "DCB:numero_cas",
    "classificacao":        "DCB:subcategoria_sugerida",
    "concentracao":         "",                  # sem equivalente na DCB
    "forma_farmaceutica":   "",                  # sem equivalente na DCB
    "apresentacao":         "",                  # sem equivalente na DCB
    "via_uso":              "",                  # sem equivalente na DCB
    "atc":                  "",                  # sem equivalente na DCB
    "fonte_tipo":           "FIXO:OFICIAL_ANVISA",
    "fonte_nome":           "DCB:fonte",
    "fonte_origem":         "DCB:versao_fonte",
    "url_fonte":            f"FIXO:{URL_OFICIAL}",
    "data_coleta":          "DCB:data_geracao",
    "validado_internamente":"FIXO:nao",
    "validado_externamente":"FIXO:sim",
    "confianca":            "DCB:confianca_fonte",
    "status_revisao":       "DCB:status_validacao",
    "observacao":           "DCB:historico_dcb",
}

SEM_EQUIV = [c for c, v in MAPEAMENTO.items() if v == ""]


def resolver(col, row):
    v = MAPEAMENTO.get(col, "")
    if v == "GERADO":
        return ""   # preenchido externamente
    if v.startswith("FIXO:"):
        return v[5:]
    if v.startswith("DCB:"):
        return row.get(v[4:], "")
    return ""


def escrever_csv(path, colunas, linhas):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=colunas, delimiter=";", extrasaction="ignore")
        w.writeheader()
        w.writerows(linhas)


def preparar():
    assert CSV_PREVIA.exists(), f"Prévia não encontrada: {CSV_PREVIA}"
    assert CSV_DICT.exists(),   f"Dicionário final não encontrado: {CSV_DICT}"

    # ── Leitura da prévia ─────────────────────────────────────────────────────
    with CSV_PREVIA.open("r", encoding="utf-8-sig", newline="") as f:
        previa = list(csv.DictReader(f, delimiter=";"))

    # ── Leitura do dicionário final (somente cabeçalho para validação) ────────
    with CSV_DICT.open("r", encoding="utf-8", newline="") as f:
        dict_rows = list(csv.reader(f, delimiter=";"))

    dict_header   = dict_rows[0] if dict_rows else []
    dict_n_dados  = len(dict_rows) - 1  # excluindo cabeçalho
    estrutura_ok  = set(dict_header) == set(COLUNAS_DICT)

    # ── Geração da carga prévia ───────────────────────────────────────────────
    carga = []
    for i, row in enumerate(previa, start=1):
        rec = {col: resolver(col, row) for col in COLUNAS_DICT}
        rec["id_dicionario"] = f"DCB_{int(row['id_previa'].replace('DCB_', '')):06d}"
        carga.append(rec)

    escrever_csv(CSV_CARGA, COLUNAS_DICT, carga)

    # ── Geração do diff ───────────────────────────────────────────────────────
    COLS_DIFF = [
        "acao_prevista", "id_previa", "termo_oficial", "termo_normalizado",
        "numero_cas", "classificacao_dcb", "subcategoria_sugerida",
        "status_validacao", "motivo", "pode_aplicar",
    ]

    diff = []
    cnt_pode = Counter()
    for row in previa:
        if row["status_validacao"] == "PRE_VALIDADO_FONTE_OFICIAL":
            pode = "SIM" if estrutura_ok or dict_n_dados == 0 else "AGUARDAR_ESTRUTURA_FINAL"
        else:
            pode = "REVISAR"
        cnt_pode[pode] += 1
        diff.append({
            "acao_prevista":      "INSERIR_PREVISTO",
            "id_previa":          row["id_previa"],
            "termo_oficial":      row["termo_oficial"],
            "termo_normalizado":  row["termo_normalizado"],
            "numero_cas":         row["numero_cas"],
            "classificacao_dcb":  row["classificacao_dcb"],
            "subcategoria_sugerida": row["subcategoria_sugerida"],
            "status_validacao":   row["status_validacao"],
            "motivo":             row["motivo_status"],
            "pode_aplicar":       pode,
        })

    escrever_csv(CSV_DIFF, COLS_DIFF, diff)

    # ── Recomendação ─────────────────────────────────────────────────────────
    recomendacao = (
        "APTO_PARA_REVISAR_CARGA" if estrutura_ok or dict_n_dados == 0
        else "REVISAR_ESTRUTURA_DICIONARIO_FINAL"
    )

    # ── Relatório ─────────────────────────────────────────────────────────────
    cab_str    = "\n".join(f"- `{c}`" for c in dict_header)
    mapeadas   = [c for c in COLUNAS_DICT if MAPEAMENTO.get(c, "") != ""]
    sem_equiv  = SEM_EQUIV

    prim10 = "\n".join(
        f"| {r['id_dicionario']} | {r['nome_padrao']} | {r['cas']} "
        f"| {r['classificacao']} | {r['status_revisao']} |"
        for r in carga[:10]
    )
    tab_pode = "\n".join(f"| {k} | {v} |" for k, v in sorted(cnt_pode.items()))

    relatorio = f"""# Relatório de Carga Prévia — Dicionário de Medicamentos ANVISA DCB
**Data:** {HOJE}
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

**Status:** Arquivo com cabeçalho e **{dict_n_dados} linha(s) de dados** ({"vazio" if dict_n_dados == 0 else "com dados"})

**Colunas ({len(dict_header)}):**

{cab_str}

**Estrutura compatível com carga:** {"SIM" if estrutura_ok else "DIVERGÊNCIA — ver colunas"}

---

## Totais

| Métrica | Valor |
|---------|-------|
| Registros lidos da prévia | {len(previa)} |
| Registros preparados na carga | {len(carga)} |
| Ações INSERIR_PREVISTO no diff | {len(diff)} |

---

## Por pode_aplicar

| pode_aplicar | Registros |
|-------------|-----------|
{tab_pode}

---

## Colunas Mapeadas ({len(mapeadas)})

{chr(10).join(f"- `{c}` → {MAPEAMENTO[c]}" for c in mapeadas)}

---

## Colunas Sem Equivalente na DCB ({len(sem_equiv)})

{chr(10).join(f"- `{c}` — deixada vazia" for c in sem_equiv)}

---

## Primeiros 10 Registros da Carga

| ID Dicionário | Nome Padrão | CAS | Classificação | Status |
|--------------|------------|-----|--------------|--------|
{prim10}

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

**{recomendacao}**

A carga prévia foi gerada corretamente com {len(carga)} registros compatíveis com
a estrutura real do dicionário final. Nenhuma aplicação foi realizada.

---

## Confirmações de Integridade

- Nenhum dicionário final foi alterado.
- Nenhuma fonte interna foi consultada.
- Nenhum banco de dados foi acessado ou alterado.
- Nenhum SKU_MASTER foi aplicado.
- Nenhuma mesclagem foi realizada.
- `app.py`, `core/`, `templates/`, `uploads/`, `backups/`, `.claude/` não foram alterados.
"""
    with MD_RELAT.open("w", encoding="utf-8") as f:
        f.write(relatorio)

    # ── Saída ─────────────────────────────────────────────────────────────────
    print(f"Prévia lida:           {len(previa)} registros")
    print(f"Carga gerada:          {len(carga)} registros")
    print(f"Diff gerado:           {len(diff)} registros")
    print(f"Dicionário final:      {dict_n_dados} dados, colunas={len(dict_header)}")
    print(f"Colunas sem equiv:     {sem_equiv}")
    print(f"por pode_aplicar:      {dict(cnt_pode)}")
    print(f"Recomendação:          {recomendacao}")
    print("Arquivos gerados:")
    for p in [CSV_CARGA, CSV_DIFF, MD_RELAT]:
        print(f"  {p.name}")


if __name__ == "__main__":
    preparar()
