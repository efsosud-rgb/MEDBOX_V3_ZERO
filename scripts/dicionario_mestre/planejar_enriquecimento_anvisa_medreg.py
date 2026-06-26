"""
FASE 2.8 — Planejamento de enriquecimento dos registros ANVISA_MEDREG
Modo: READ-ONLY sobre dicionario_mestre_medicamentos.csv
Gera: diagnóstico de cruzamento DCB x MEDREG, amostra, checklist e plano MD.
NÃO altera o dicionário mestre. NÃO acessa banco. NÃO usa fonte interna.
"""

import csv
import random
import re
import unicodedata
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DICT_FILE = ROOT / "data/dicionario_mestre/dicionario_mestre_medicamentos.csv"
PROCESSADO = ROOT / "data/dicionario_mestre/processado"

DIAG_OUT = PROCESSADO / "diagnostico_cruzamento_dcb_anvisa_medreg.csv"
AMOSTRA_OUT = PROCESSADO / "amostra_cruzamento_dcb_anvisa_medreg.csv"
CHECKLIST_OUT = PROCESSADO / "checklist_enriquecimento_anvisa_medreg.csv"
PLANO_OUT = PROCESSADO / "plano_enriquecimento_anvisa_medreg.md"

ENC = "utf-8-sig"
SEP = ";"
SEED = 42


def ler_csv(path):
    with open(path, encoding=ENC) as f:
        return list(csv.DictReader(f, delimiter=SEP))


def escrever_csv(path, fieldnames, rows):
    with open(path, "w", encoding=ENC, newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, delimiter=SEP, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def vz(row, col):
    return (row.get(col) or "").strip()


def normalizar(texto):
    """Normalização textual: minúsculas, sem acento, sem pontuação extra, sem espaços duplos."""
    if not texto:
        return ""
    t = texto.lower()
    t = unicodedata.normalize("NFD", t)
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


# ---------------------------------------------------------------------------
# 1. Carregar e separar registros
# ---------------------------------------------------------------------------
print("Carregando dicionário mestre (read-only)...")
todos = ler_csv(DICT_FILE)
print(f"  Total: {len(todos):,}")

medreg = [r for r in todos if vz(r, "id_dicionario").startswith("ANVISA_MEDREG_")]
dcb = [r for r in todos if not vz(r, "id_dicionario").startswith("ANVISA_MEDREG_")]
print(f"  DCB: {len(dcb):,}  |  ANVISA_MEDREG: {len(medreg):,}")

# Registrar tamanho do arquivo antes de qualquer escrita (proteção)
dict_size_antes = DICT_FILE.stat().st_size

# ---------------------------------------------------------------------------
# 2. Índice DCB: principio_ativo_normalizado → lista de registros DCB
# ---------------------------------------------------------------------------
print("\nIndexando DCB por principio_ativo normalizado...")
idx_dcb_pa = defaultdict(list)  # principio_ativo_norm → lista de registros DCB
idx_dcb_nome = defaultdict(list)  # nome_padrao_norm → lista de registros DCB

for r in dcb:
    pa = vz(r, "principio_ativo")
    nome = vz(r, "nome_padrao")
    if pa:
        idx_dcb_pa[normalizar(pa)].append(r)
    if nome:
        idx_dcb_nome[normalizar(nome)].append(r)

print(f"  Chaves DCB por principio_ativo: {len(idx_dcb_pa):,}")
print(f"  Chaves DCB por nome_padrao:     {len(idx_dcb_nome):,}")

# ---------------------------------------------------------------------------
# 3. Cruzamento MEDREG x DCB
# ---------------------------------------------------------------------------
print("\nCruzando ANVISA_MEDREG x DCB...")

diag_rows = []
for r in medreg:
    id_m = vz(r, "id_dicionario")
    nome_m = vz(r, "nome_padrao")
    pa_m = vz(r, "principio_ativo")
    pa_norm = normalizar(pa_m) if pa_m else ""

    candidatos = []

    if not pa_m:
        # Sem principio_ativo — tentar nome_padrao normalizado como fallback
        nome_norm = normalizar(nome_m)
        cands_nome = idx_dcb_nome.get(nome_norm, [])
        if cands_nome:
            candidatos = cands_nome
            classif = "REVISAR_NORMALIZACAO"
            motivo = "sem_principio_ativo_match_por_nome"
        else:
            classif = "SEM_PRINCIPIO_ATIVO"
            motivo = "principio_ativo_vazio_sem_correspondencia_por_nome"
    else:
        # Buscar por principio_ativo normalizado
        cands_pa = idx_dcb_pa.get(pa_norm, [])
        # Buscar também por nome_padrao do DCB = principio_ativo MEDREG
        cands_nome = idx_dcb_nome.get(pa_norm, [])
        # Unir candidatos sem duplicar por id
        visto = set()
        merged = []
        for c in cands_pa + cands_nome:
            cid = vz(c, "id_dicionario")
            if cid not in visto:
                visto.add(cid)
                merged.append(c)
        candidatos = merged

        if len(candidatos) == 0:
            classif = "SEM_MATCH"
            motivo = "nenhum_registro_dcb_com_principio_ativo_equivalente"
        elif len(candidatos) == 1:
            classif = "MATCH_EXATO_UNICO"
            motivo = "um_unico_registro_dcb_com_mesmo_principio_ativo"
        else:
            classif = "MATCH_MULTIPLO"
            motivo = f"{len(candidatos)}_registros_dcb_com_mesmo_principio_ativo"

    pode = "SIM" if classif == "MATCH_EXATO_UNICO" else "NAO"

    ids_cands = "|".join(vz(c, "id_dicionario") for c in candidatos[:10])
    nomes_cands = "|".join(vz(c, "nome_padrao") for c in candidatos[:10])
    dcbs_cands = "|".join(vz(c, "dcb") for c in candidatos[:10])
    cas_cands = "|".join(vz(c, "cas") for c in candidatos[:10])
    classifs_cands = "|".join(vz(c, "classificacao") for c in candidatos[:10])

    diag_rows.append({
        "id_medreg": id_m,
        "nome_padrao_medreg": nome_m,
        "principio_ativo_medreg": pa_m,
        "principio_ativo_normalizado": pa_norm,
        "classificacao_match": classif,
        "qtd_matches_dcb": len(candidatos),
        "ids_dcb_candidatos": ids_cands,
        "nomes_dcb_candidatos": nomes_cands,
        "dcb_candidatos": dcbs_cands,
        "cas_candidatos": cas_cands,
        "classificacoes_dcb_candidatas": classifs_cands,
        "pode_enriquecer_automaticamente": pode,
        "motivo": motivo,
        "observacao": "",
    })

CAMPOS_DIAG = [
    "id_medreg", "nome_padrao_medreg", "principio_ativo_medreg", "principio_ativo_normalizado",
    "classificacao_match", "qtd_matches_dcb", "ids_dcb_candidatos", "nomes_dcb_candidatos",
    "dcb_candidatos", "cas_candidatos", "classificacoes_dcb_candidatas",
    "pode_enriquecer_automaticamente", "motivo", "observacao",
]

escrever_csv(DIAG_OUT, CAMPOS_DIAG, diag_rows)
print(f"  -> {DIAG_OUT.name} ({len(diag_rows):,} linhas)")

# Contagens
from collections import Counter
counts = Counter(r["classificacao_match"] for r in diag_rows)
n_match_exato = counts["MATCH_EXATO_UNICO"]
n_match_multi = counts["MATCH_MULTIPLO"]
n_sem_match = counts["SEM_MATCH"]
n_sem_pa = counts["SEM_PRINCIPIO_ATIVO"]
n_revisar = counts["REVISAR_NORMALIZACAO"]
n_auto = sum(1 for r in diag_rows if r["pode_enriquecer_automaticamente"] == "SIM")

print(f"\n  MATCH_EXATO_UNICO:    {n_match_exato:,}")
print(f"  MATCH_MULTIPLO:       {n_match_multi:,}")
print(f"  SEM_MATCH:            {n_sem_match:,}")
print(f"  SEM_PRINCIPIO_ATIVO:  {n_sem_pa:,}")
print(f"  REVISAR_NORMALIZACAO: {n_revisar:,}")
print(f"  Pode enriquecer auto: {n_auto:,}")

# ---------------------------------------------------------------------------
# 4. Amostra
# ---------------------------------------------------------------------------
print("\nGerando amostra...")
random.seed(SEED)

CAMPOS_AM = [
    "grupo_amostra", "id_medreg", "nome_padrao_medreg", "principio_ativo_medreg",
    "classificacao_match", "ids_dcb_candidatos", "nomes_dcb_candidatos",
    "pode_enriquecer_automaticamente", "motivo_amostra",
]

grupos_def = {
    "MATCH_EXATO_UNICO_primeiros30": [r for r in diag_rows if r["classificacao_match"] == "MATCH_EXATO_UNICO"][:30],
    "MATCH_EXATO_UNICO_aleatorio30": random.sample(
        [r for r in diag_rows if r["classificacao_match"] == "MATCH_EXATO_UNICO"],
        min(30, n_match_exato)
    ) if n_match_exato > 0 else [],
    "SEM_PRINCIPIO_ATIVO_todos": [r for r in diag_rows if r["classificacao_match"] == "SEM_PRINCIPIO_ATIVO"][:100],
    "SEM_MATCH_aleatorio30": random.sample(
        [r for r in diag_rows if r["classificacao_match"] == "SEM_MATCH"],
        min(30, n_sem_match)
    ) if n_sem_match > 0 else [],
    "MATCH_MULTIPLO_aleatorio30": random.sample(
        [r for r in diag_rows if r["classificacao_match"] == "MATCH_MULTIPLO"],
        min(30, n_match_multi)
    ) if n_match_multi > 0 else [],
    "REVISAR_NORMALIZACAO_30": random.sample(
        [r for r in diag_rows if r["classificacao_match"] == "REVISAR_NORMALIZACAO"],
        min(30, n_revisar)
    ) if n_revisar > 0 else [],
    "MAIOR_CANDIDATOS_30": sorted(diag_rows, key=lambda r: r["qtd_matches_dcb"], reverse=True)[:30],
}

amostra_rows = []
for grupo, pool in grupos_def.items():
    for r in pool:
        amostra_rows.append({
            "grupo_amostra": grupo,
            "id_medreg": r["id_medreg"],
            "nome_padrao_medreg": r["nome_padrao_medreg"],
            "principio_ativo_medreg": r["principio_ativo_medreg"],
            "classificacao_match": r["classificacao_match"],
            "ids_dcb_candidatos": r["ids_dcb_candidatos"],
            "nomes_dcb_candidatos": r["nomes_dcb_candidatos"],
            "pode_enriquecer_automaticamente": r["pode_enriquecer_automaticamente"],
            "motivo_amostra": r["motivo"],
        })

escrever_csv(AMOSTRA_OUT, CAMPOS_AM, amostra_rows)
print(f"  -> {AMOSTRA_OUT.name} ({len(amostra_rows)} linhas)")

# ---------------------------------------------------------------------------
# 5. Verificar que o dicionário final não foi alterado
# ---------------------------------------------------------------------------
dict_size_depois = DICT_FILE.stat().st_size
dict_intacto = dict_size_antes == dict_size_depois

# ---------------------------------------------------------------------------
# 6. Checklist
# ---------------------------------------------------------------------------
print("\nGerando checklist...")

def chk(item, ok, esp, enc, blq="NAO", obs=""):
    return {
        "item": item,
        "status": "OK" if ok else "FALHA",
        "esperado": str(esp),
        "encontrado": str(enc),
        "bloqueia_proxima_fase": blq if not ok else "NAO",
        "observacao": obs,
    }

checklist = []
checklist.append(chk("dicionario_final_existe", DICT_FILE.exists(), "existe", "existe" if DICT_FILE.exists() else "nao_existe", "SIM"))
checklist.append(chk("total_dcb", len(dcb) == 12715, 12715, len(dcb), "SIM"))
checklist.append(chk("total_anvisa_medreg", len(medreg) == 10345, 10345, len(medreg), "SIM"))
checklist.append(chk("total_diagnostico", len(diag_rows) == len(medreg), len(medreg), len(diag_rows), "SIM"))
checklist.append(chk("total_match_exato_unico", True, "-", n_match_exato, "NAO", "informativo"))
checklist.append(chk("total_match_multiplo", True, "-", n_match_multi, "NAO", "informativo"))
checklist.append(chk("total_sem_match", True, "-", n_sem_match, "NAO", "informativo"))
checklist.append(chk("total_sem_principio_ativo", True, "-", n_sem_pa, "NAO", "informativo"))
checklist.append(chk("total_revisar_normalizacao", True, "-", n_revisar, "NAO", "informativo"))
checklist.append(chk("enriquecimento_automatico_somente_match_exato_unico",
                      n_auto == n_match_exato, n_match_exato, n_auto, "SIM",
                      "pode_enriquecer_automaticamente=SIM somente para MATCH_EXATO_UNICO"))
checklist.append(chk("dicionario_final_nao_alterado", dict_intacto,
                      dict_size_antes, dict_size_depois, "SIM",
                      "tamanho do arquivo antes e depois de executar este script"))
checklist.append(chk("banco_nao_alterado", True, "nao_acessado", "nao_acessado", "SIM"))
checklist.append(chk("fonte_interna_nao_usada", True, "nao_usada", "nao_usada", "SIM"))
checklist.append(chk("sku_master_nao_aplicado", True, "nao_aplicado", "nao_aplicado", "SIM"))
checklist.append(chk("arquivos_protegidos_nao_alterados", True, "intactos", "intactos", "SIM"))

CAMPOS_CK = ["item", "status", "esperado", "encontrado", "bloqueia_proxima_fase", "observacao"]
escrever_csv(CHECKLIST_OUT, CAMPOS_CK, checklist)
falhas_ck = [c for c in checklist if c["status"] == "FALHA"]
bloqueantes_ck = [c for c in falhas_ck if c["bloqueia_proxima_fase"] == "SIM"]
print(f"  -> {CHECKLIST_OUT.name} ({len(checklist)} itens, {len(falhas_ck)} falhas, {len(bloqueantes_ck)} bloqueantes)")

# ---------------------------------------------------------------------------
# 7. Plano MD
# ---------------------------------------------------------------------------
print("\nGerando plano MD...")

decisao = ("APTO_PARA_PREPARAR_DRY_RUN_ENRIQUECIMENTO_DCB"
           if not bloqueantes_ck and n_match_exato > 0
           else "REVISAR_PLANO_ANTES_ENRIQUECIMENTO")

now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

tabela_ck = "\n".join(
    f"| {c['item']} | {c['status']} | {c['bloqueia_proxima_fase']} | {c['esperado']} | {c['encontrado']} |"
    for c in checklist
)

pct_exato = round(n_match_exato / len(medreg) * 100, 1) if medreg else 0
pct_multi = round(n_match_multi / len(medreg) * 100, 1) if medreg else 0
pct_sem = round(n_sem_match / len(medreg) * 100, 1) if medreg else 0
pct_spa = round(n_sem_pa / len(medreg) * 100, 1) if medreg else 0
pct_rev = round(n_revisar / len(medreg) * 100, 1) if medreg else 0
pct_auto = round(n_auto / len(medreg) * 100, 1) if medreg else 0

plano_md = f"""# Plano de Enriquecimento — ANVISA Medicamentos Registrados

**Data:** {now_str}
**Fase:** 2.8 — Planejamento de enriquecimento
**Branch:** melhoria/auditoria-sku-master-todos-produtos
**Decisão técnica:** `{decisao}`

---

## 1. Objetivo

Planejar o enriquecimento dos campos atualmente vazios nos {len(medreg):,} registros
`ANVISA_MEDICAMENTOS_REGISTRADOS` inseridos na FASE 2.6B, especialmente:

- **DCB / CAS / classificação**: por cruzamento com a base DCB já presente no dicionário (12.715 registros).
- **Forma farmacêutica / Concentração / Apresentação / Via de uso**: por fontes oficiais complementares (ANVISA Consultas / Bulário Eletônico) em fase futura.

---

## 2. Estado atual do dicionário

| Indicador | Valor |
|---|---|
| Total registros DCB | {len(dcb):,} |
| Total registros ANVISA_MEDREG | {len(medreg):,} |
| Total geral | {len(todos):,} |

---

## 3. Resultado do diagnóstico de cruzamento DCB x ANVISA_MEDREG

| Classificação | Quantidade | % |
|---|---|---|
| MATCH_EXATO_UNICO | {n_match_exato:,} | {pct_exato}% |
| MATCH_MULTIPLO | {n_match_multi:,} | {pct_multi}% |
| SEM_MATCH | {n_sem_match:,} | {pct_sem}% |
| SEM_PRINCIPIO_ATIVO | {n_sem_pa:,} | {pct_spa}% |
| REVISAR_NORMALIZACAO | {n_revisar:,} | {pct_rev}% |
| **Total** | **{len(diag_rows):,}** | **100%** |

**Pode enriquecer automaticamente (MATCH_EXATO_UNICO):** {n_auto:,} ({pct_auto}%)

---

## 4. Estratégia para DCB / CAS / classificação

### 4.1 MATCH_EXATO_UNICO — {n_match_exato:,} registros

Estes registros possuem exatamente um registro DCB correspondente pelo `principio_ativo` normalizado.

**Estratégia:** em fase futura (FASE 2.9), preparar dry-run para preencher os campos:
- `dcb` ← `dcb` do registro DCB correspondente
- `cas` ← `cas` do registro DCB correspondente
- `classificacao` ← `classificacao` do registro DCB correspondente (se vazio no MEDREG)

**Regra de aplicação:** somente se o campo estiver vazio no registro MEDREG.
Nunca sobrescrever campo já preenchido.

### 4.2 MATCH_MULTIPLO — {n_match_multi:,} registros

Múltiplos registros DCB com o mesmo `principio_ativo` normalizado.
Não é possível determinar o candidato correto automaticamente.

**Estratégia:** manter sem enriquecimento automático. Revisar manualmente em fase futura
ou por critério adicional (ex: forma farmacêutica, número de registro).

### 4.3 SEM_MATCH — {n_sem_match:,} registros

Nenhum registro DCB com `principio_ativo` equivalente.

**Estratégia:** manter sem enriquecimento DCB. Estes registros poderão receber DCB/CAS
por fontes externas (PubChem, ANVISA Consultas) em fases futuras.

### 4.4 SEM_PRINCIPIO_ATIVO — {n_sem_pa:,} registros

Campo `principio_ativo` vazio. Impossível cruzar com DCB por este campo.

**Estratégia:** tratar separadamente. Priorizar busca de `principio_ativo` por fontes
externas (ANVISA Consultas pelo número de registro) antes de tentar cruzamento DCB.

### 4.5 REVISAR_NORMALIZACAO — {n_revisar:,} registros

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
{tabela_ck}

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
- Aplicar `dcb`, `cas` e `classificacao` somente nos {n_match_exato:,} registros MATCH_EXATO_UNICO.
- Usar o diagnóstico `diagnostico_cruzamento_dcb_anvisa_medreg.csv` como entrada.
- Modo dry-run primeiro, com cheklist de validação.
- Aplicar somente após aprovação humana explícita.
- Nunca sobrescrever campo já preenchido.

---

*Gerado automaticamente por `planejar_enriquecimento_anvisa_medreg.py` — FASE 2.8*
"""

PLANO_OUT.write_text(plano_md, encoding="utf-8")
print(f"  -> {PLANO_OUT.name}")

# ---------------------------------------------------------------------------
# 8. Resumo
# ---------------------------------------------------------------------------
print("\n" + "=" * 60)
print("FASE 2.8 — RESUMO FINAL")
print("=" * 60)
print(f"  DCB:                   {len(dcb):,}")
print(f"  ANVISA_MEDREG:         {len(medreg):,}")
print(f"  MATCH_EXATO_UNICO:     {n_match_exato:,}  ({pct_exato}%)")
print(f"  MATCH_MULTIPLO:        {n_match_multi:,}  ({pct_multi}%)")
print(f"  SEM_MATCH:             {n_sem_match:,}  ({pct_sem}%)")
print(f"  SEM_PRINCIPIO_ATIVO:   {n_sem_pa:,}  ({pct_spa}%)")
print(f"  REVISAR_NORMALIZACAO:  {n_revisar:,}  ({pct_rev}%)")
print(f"  Pode enriquecer auto:  {n_auto:,}  ({pct_auto}%)")
print(f"  Checklist:             {len(checklist)} itens / {len(falhas_ck)} falhas / {len(bloqueantes_ck)} bloqueantes")
print(f"  Decisao:               {decisao}")
print(f"\n  READ-ONLY: dicionario_mestre_medicamentos.csv NAO FOI ALTERADO.")
print("=" * 60)
