"""
Auditoria da prévia DCB para dicionário de medicamentos.

Entrada:  data/dicionario_mestre/processado/pre_dicionario_medicamentos_anvisa_dcb.csv
Saídas:   data/dicionario_mestre/processado/amostra_previa_dcb_medicamentos.csv
          data/dicionario_mestre/processado/auditoria_previa_dcb_medicamentos.md
          data/dicionario_mestre/processado/duplicidades_previa_dcb_medicamentos.csv
          data/dicionario_mestre/processado/termos_revisao_previa_dcb_medicamentos.csv

Não acessa internet, banco ou fontes internas.
Não altera dicionários finais.
Reexecutável com segurança.
"""

import csv
import random
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

# ── Caminhos ──────────────────────────────────────────────────────────────────
ROOT        = Path(__file__).resolve().parents[2]
CSV_ENTRADA = ROOT / "data/dicionario_mestre/processado/pre_dicionario_medicamentos_anvisa_dcb.csv"
CSV_AMOSTRA = ROOT / "data/dicionario_mestre/processado/amostra_previa_dcb_medicamentos.csv"
MD_AUDIT    = ROOT / "data/dicionario_mestre/processado/auditoria_previa_dcb_medicamentos.md"
CSV_DUP     = ROOT / "data/dicionario_mestre/processado/duplicidades_previa_dcb_medicamentos.csv"
CSV_REV     = ROOT / "data/dicionario_mestre/processado/termos_revisao_previa_dcb_medicamentos.csv"

SEED = 42

# ── Helpers ───────────────────────────────────────────────────────────────────
_PAT_ESPECIAL   = re.compile(r"[àáâãäåæçèéêëìíîïðñòóôõöùúûüýþÿ]", re.IGNORECASE)
_PAT_NUMERO     = re.compile(r"\d")
_PAT_HIFBAR_PAR = re.compile(r"[-/()\[\]]")

def tem_especial(t):   return bool(_PAT_ESPECIAL.search(t))
def tem_numero(t):     return bool(_PAT_NUMERO.search(t))
def tem_hifbar(t):     return bool(_PAT_HIFBAR_PAR.search(t))
def tem_incomum(t):
    for c in t:
        cat = unicodedata.category(c)
        if cat.startswith("C") or (cat.startswith("P") and c not in "-/()., "):
            return True
    return False


def escrever_csv(path, colunas, linhas):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=colunas, delimiter=";", extrasaction="ignore")
        w.writeheader()
        w.writerows(linhas)


def campos_amostra(rec, grupo):
    return {
        "grupo_amostra":       grupo,
        "id_previa":           rec["id_previa"],
        "termo_oficial":       rec["termo_oficial"],
        "termo_normalizado":   rec["termo_normalizado"],
        "numero_cas":          rec["numero_cas"],
        "classificacao_dcb":   rec["classificacao_dcb"],
        "subcategoria_sugerida": rec["subcategoria_sugerida"],
        "status_validacao":    rec["status_validacao"],
        "motivo_status":       rec["motivo_status"],
        "linha_origem":        rec["linha_origem"],
    }


# ── Principal ─────────────────────────────────────────────────────────────────
def auditar():
    assert CSV_ENTRADA.exists(), f"Entrada não encontrada: {CSV_ENTRADA}"

    with CSV_ENTRADA.open("r", encoding="utf-8-sig", newline="") as f:
        dados = list(csv.DictReader(f, delimiter=";"))

    total = len(dados)
    hoje  = date.today().isoformat()

    # ── Contagens básicas ─────────────────────────────────────────────────────
    cnt_classif  = Counter(r["classificacao_dcb"]   for r in dados)
    cnt_subcat   = Counter(r["subcategoria_sugerida"] for r in dados)
    cnt_status   = Counter(r["status_validacao"]     for r in dados)

    sem_termo     = [r for r in dados if not r["termo_oficial"].strip()]
    sem_norm      = [r for r in dados if not r["termo_normalizado"].strip()]
    sem_cas       = [r for r in dados if not r["numero_cas"].strip()]
    com_especial  = [r for r in dados if tem_especial(r["termo_oficial"])]
    com_numero    = [r for r in dados if tem_numero(r["termo_oficial"])]
    com_hifbar    = [r for r in dados if tem_hifbar(r["termo_oficial"])]
    com_incomum   = [r for r in dados if tem_incomum(r["termo_oficial"])]

    # ── Duplicidades ──────────────────────────────────────────────────────────
    # por termo_normalizado
    norm_map = defaultdict(list)
    for r in dados:
        norm_map[r["termo_normalizado"]].append(r)
    dup_norm = {k: v for k, v in norm_map.items() if len(v) > 1}

    # por numero_cas (excluir vazios)
    cas_map = defaultdict(list)
    for r in dados:
        cas = r["numero_cas"].strip()
        if cas:
            cas_map[cas].append(r)
    dup_cas = {k: v for k, v in cas_map.items() if len(v) > 1}

    linhas_dup = []
    for chave, recs in sorted(dup_norm.items()):
        linhas_dup.append({
            "tipo_duplicidade":  "TERMO_NORMALIZADO",
            "chave":             chave,
            "quantidade":        len(recs),
            "ids_previa":        "|".join(r["id_previa"] for r in recs),
            "termos_oficiais":   "|".join(r["termo_oficial"] for r in recs),
            "numeros_cas":       "|".join(r["numero_cas"] for r in recs),
            "classificacoes":    "|".join(r["classificacao_dcb"] for r in recs),
            "status_revisao":    "REVISAR_DUPLICIDADE_TERMO",
        })
    for chave, recs in sorted(dup_cas.items()):
        linhas_dup.append({
            "tipo_duplicidade":  "NUMERO_CAS",
            "chave":             chave,
            "quantidade":        len(recs),
            "ids_previa":        "|".join(r["id_previa"] for r in recs),
            "termos_oficiais":   "|".join(r["termo_oficial"] for r in recs),
            "numeros_cas":       "|".join(r["numero_cas"] for r in recs),
            "classificacoes":    "|".join(r["classificacao_dcb"] for r in recs),
            "status_revisao":    "REVISAR_DUPLICIDADE_CAS",
        })

    escrever_csv(CSV_DUP, [
        "tipo_duplicidade","chave","quantidade","ids_previa",
        "termos_oficiais","numeros_cas","classificacoes","status_revisao",
    ], linhas_dup)

    # ── Termos para revisão ───────────────────────────────────────────────────
    LIMITE_LONGO = 60
    linhas_rev = []
    vistos_rev = set()

    def add_rev(rec, motivo):
        chave = (rec["id_previa"], motivo)
        if chave not in vistos_rev:
            vistos_rev.add(chave)
            linhas_rev.append({
                "motivo_revisao":      motivo,
                "id_previa":           rec["id_previa"],
                "termo_oficial":       rec["termo_oficial"],
                "termo_normalizado":   rec["termo_normalizado"],
                "numero_cas":          rec["numero_cas"],
                "classificacao_dcb":   rec["classificacao_dcb"],
                "subcategoria_sugerida": rec["subcategoria_sugerida"],
                "status_validacao":    rec["status_validacao"],
                "motivo_status":       rec["motivo_status"],
                "linha_origem":        rec["linha_origem"],
            })

    for r in sem_termo:   add_rev(r, "TERMO_OFICIAL_VAZIO")
    for r in sem_norm:    add_rev(r, "TERMO_NORMALIZADO_VAZIO")
    for r in sem_cas:     add_rev(r, "CAS_VAZIO")
    for r in dados:
        if r["status_validacao"] != "PRE_VALIDADO_FONTE_OFICIAL":
            add_rev(r, "STATUS_VALIDACAO_DIFERENTE")
        if r["categoria_medbox_sugerida"] != "MEDICAMENTO":
            add_rev(r, "CATEGORIA_DIFERENTE")
        if r["subcategoria_sugerida"] == "REVISAR":
            add_rev(r, "SUBCATEGORIA_REVISAR")
        if len(r["termo_oficial"]) > LIMITE_LONGO:
            add_rev(r, "TERMO_MUITO_LONGO")
        if tem_incomum(r["termo_oficial"]):
            add_rev(r, "CARACTERE_INCOMUM")

    escrever_csv(CSV_REV, [
        "motivo_revisao","id_previa","termo_oficial","termo_normalizado",
        "numero_cas","classificacao_dcb","subcategoria_sugerida",
        "status_validacao","motivo_status","linha_origem",
    ], linhas_rev)

    # ── Amostra ───────────────────────────────────────────────────────────────
    COLS_AMOSTRA = [
        "grupo_amostra","id_previa","termo_oficial","termo_normalizado",
        "numero_cas","classificacao_dcb","subcategoria_sugerida",
        "status_validacao","motivo_status","linha_origem",
    ]

    amostra = []

    def add_grupo(registros, grupo, n=20):
        for r in registros[:n]:
            amostra.append(campos_amostra(r, grupo))

    add_grupo(dados[:20],                                       "PRIMEIROS_20")
    add_grupo([r for r in dados if r["classificacao_dcb"]=="IFA"], "CLASSIF_IFA")
    add_grupo([r for r in dados if r["classificacao_dcb"]=="INF"], "CLASSIF_INF")
    add_grupo([r for r in dados if r["classificacao_dcb"]=="BIO"], "CLASSIF_BIO")
    add_grupo([r for r in dados if r["classificacao_dcb"]=="HOM"], "CLASSIF_HOM")
    add_grupo([r for r in dados if r["classificacao_dcb"]=="EXA"], "CLASSIF_EXA")
    add_grupo([r for r in dados if r["classificacao_dcb"]=="PM"],  "CLASSIF_PM")
    add_grupo([r for r in dados if r["classificacao_dcb"]=="RAD"], "CLASSIF_RAD")
    add_grupo(com_especial,                                     "ESPECIAIS")
    add_grupo(com_numero,                                       "COM_NUMERO")
    add_grupo(com_hifbar,                                       "COM_HIFBAR_PAR")
    add_grupo(sorted(dados, key=lambda r: -len(r["termo_oficial"]))[:20], "MAIS_LONGOS")
    add_grupo(sorted(dados, key=lambda r:  len(r["termo_oficial"]))[:20], "MAIS_CURTOS")
    rng = random.Random(SEED)
    add_grupo(rng.sample(dados, min(20, total)),                "ALEATORIO_SEED42")

    escrever_csv(CSV_AMOSTRA, COLS_AMOSTRA, amostra)

    # ── Recomendação ─────────────────────────────────────────────────────────
    problemas_criticos = bool(sem_termo or sem_norm or sem_cas)
    recomendacao = (
        "REVISAR_ANTES_DA_CARGA" if problemas_criticos
        else "APTO_PARA_PREPARAR_CARGA_FINAL"
    )

    # ── Relatório ─────────────────────────────────────────────────────────────
    def tab_cnt(cnt, ordem=None):
        items = sorted(cnt.items(), key=lambda x: -x[1]) if not ordem else [(k, cnt.get(k,0)) for k in ordem]
        return "\n".join(f"| {k} | {v} |" for k, v in items)

    top30_longos = sorted(dados, key=lambda r: -len(r["termo_oficial"]))[:30]
    top30_linhas = "\n".join(
        f"| {r['id_previa']} | {r['termo_oficial']} | {len(r['termo_oficial'])} | {r['classificacao_dcb']} |"
        for r in top30_longos
    )

    dup_norm_resumo = "\n".join(
        f"| TERMO | `{k}` | {len(v)} | {', '.join(r['id_previa'] for r in v)} |"
        for k, v in list(dup_norm.items())[:20]
    ) or "_Nenhuma duplicidade por termo normalizado encontrada._"

    dup_cas_resumo = "\n".join(
        f"| CAS | `{k}` | {len(v)} | {', '.join(r['id_previa'] for r in v)} |"
        for k, v in list(dup_cas.items())[:20]
    ) or "_Nenhuma duplicidade por CAS encontrada._"

    # grupos da amostra
    grupos_cnt = Counter(a["grupo_amostra"] for a in amostra)
    tab_grupos = "\n".join(f"| {g} | {n} |" for g, n in grupos_cnt.items())

    # primeiros 10 da amostra PRIMEIROS_20
    prim10 = [a for a in amostra if a["grupo_amostra"] == "PRIMEIROS_20"][:10]
    tab_prim10 = "\n".join(
        f"| {a['id_previa']} | {a['termo_oficial']} | {a['numero_cas']} | {a['classificacao_dcb']} |"
        for a in prim10
    )

    # riscos
    riscos = []
    if sem_termo:    riscos.append(f"- {len(sem_termo)} registros sem `termo_oficial` — CRÍTICO")
    if sem_cas:      riscos.append(f"- {len(sem_cas)} registros sem `numero_cas` — CRÍTICO")
    if dup_norm:     riscos.append(f"- {len(dup_norm)} possíveis duplicidades por termo normalizado — REVISAR")
    if dup_cas:      riscos.append(f"- {len(dup_cas)} possíveis duplicidades por CAS — REVISAR")
    if com_incomum:  riscos.append(f"- {len(com_incomum)} termos com caracteres incomuns — REVISAR AMOSTRA")
    riscos = riscos or ["- Nenhum problema crítico identificado."]

    relatorio = f"""# Auditoria da Prévia DCB — Dicionário de Medicamentos
**Data:** {hoje}
**Fase:** FASE 1.3 — Auditoria da prévia DCB para medicamentos

---

## Objetivo

Auditar a prévia auditável da ANVISA DCB antes de qualquer integração no dicionário
de medicamentos final. Gerar amostras e identificar riscos para revisão humana.

---

## Arquivo de Entrada

`data/dicionario_mestre/processado/pre_dicionario_medicamentos_anvisa_dcb.csv`

---

## Totais

| Métrica | Valor |
|---------|-------|
| Registros analisados | {total} |
| Sem termo_oficial | {len(sem_termo)} |
| Sem termo_normalizado | {len(sem_norm)} |
| Sem numero_cas | {len(sem_cas)} |
| Com caracteres especiais (acentos) | {len(com_especial)} |
| Com números no termo | {len(com_numero)} |
| Com hífen, barra ou parênteses | {len(com_hifbar)} |
| Com caracteres incomuns | {len(com_incomum)} |

---

## Por Classificação DCB

| Classificação | Registros |
|--------------|-----------|
{tab_cnt(cnt_classif)}

---

## Por Subcategoria Sugerida

| Subcategoria | Registros |
|-------------|-----------|
{tab_cnt(cnt_subcat)}

---

## Por Status de Validação

| Status | Registros |
|--------|-----------|
{tab_cnt(cnt_status)}

---

## Top 30 Termos Mais Longos

| ID Prévia | Termo | Comprimento | Classificação |
|-----------|-------|-------------|--------------|
{top30_linhas}

---

## Possíveis Duplicidades por Termo Normalizado

Total: **{len(dup_norm)}**

| Tipo | Chave | Qtd | IDs |
|------|-------|-----|-----|
{dup_norm_resumo}

---

## Possíveis Duplicidades por Número CAS

Total: **{len(dup_cas)}**

| Tipo | CAS | Qtd | IDs |
|------|-----|-----|-----|
{dup_cas_resumo}

---

## Resumo da Amostra Gerada

| Grupo | Registros |
|-------|-----------|
{tab_grupos}

Total de linhas na amostra (com repetições entre grupos): **{len(amostra)}**

### Primeiros 10 registros (grupo PRIMEIROS_20)

| ID Prévia | Termo Oficial | CAS | Classificação |
|-----------|--------------|-----|--------------|
{tab_prim10}

---

## Riscos Identificados

{chr(10).join(riscos)}

---

## Recomendação Final

**{recomendacao}**

{"Nenhum problema crítico encontrado. A prévia pode avançar para preparação da carga final, com revisão humana das duplicidades e termos longos identificados." if recomendacao == "APTO_PARA_PREPARAR_CARGA_FINAL" else "Problemas críticos encontrados. Revisar registros sem termo_oficial, sem CAS ou com status inválido antes de prosseguir."}

---

## Confirmações de Integridade

- Nenhum dicionário final foi alterado (`dicionario_mestre_medbox.csv`,
  `dicionario_mestre_medicamentos.csv`, `dicionario_mestre_produtos_saude.csv`).
- Nenhuma fonte interna foi consultada.
- Nenhum banco de dados foi acessado ou alterado.
- Nenhum SKU_MASTER foi aplicado.
- Nenhuma mesclagem foi feita.
- O arquivo de entrada não foi modificado.
- `app.py`, `core/`, `templates/`, `uploads/`, `backups/`, `.claude/` não foram alterados.
"""
    with MD_AUDIT.open("w", encoding="utf-8") as f:
        f.write(relatorio)

    # ── Impressão final ───────────────────────────────────────────────────────
    print(f"Total analisado:              {total}")
    print(f"Duplicidades termo_norm:      {len(dup_norm)}")
    print(f"Duplicidades CAS:             {len(dup_cas)}")
    print(f"Termos para revisao:          {len(linhas_rev)}")
    print(f"Linhas na amostra:            {len(amostra)}")
    print(f"Recomendacao:                 {recomendacao}")
    print(f"Arquivos gerados:")
    for p in [CSV_AMOSTRA, MD_AUDIT, CSV_DUP, CSV_REV]:
        print(f"  {p.name}")


if __name__ == "__main__":
    auditar()
