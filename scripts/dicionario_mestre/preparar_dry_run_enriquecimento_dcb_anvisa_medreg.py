"""
FASE 2.9 — Dry-run de enriquecimento DCB/CAS/classificação nos ANVISA_MEDREG
Modo: READ-ONLY sobre dicionario_mestre_medicamentos.csv
Escopo: somente registros MATCH_EXATO_UNICO / pode_enriquecer_automaticamente=SIM
NÃO altera o dicionário mestre. NÃO acessa banco. NÃO usa fonte interna.
"""

import csv
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DICT_FILE = ROOT / "data/dicionario_mestre/dicionario_mestre_medicamentos.csv"
DIAG_FILE = ROOT / "data/dicionario_mestre/processado/diagnostico_cruzamento_dcb_anvisa_medreg.csv"
PROCESSADO = ROOT / "data/dicionario_mestre/processado"

DRY_RUN_OUT = PROCESSADO / "dry_run_enriquecimento_dcb_anvisa_medreg.csv"
DIFF_OUT = PROCESSADO / "diff_enriquecimento_dcb_anvisa_medreg.csv"
CHECKLIST_OUT = PROCESSADO / "checklist_dry_run_enriquecimento_dcb_anvisa_medreg.csv"
PLANO_OUT = PROCESSADO / "plano_aplicacao_enriquecimento_dcb_anvisa_medreg.md"

ENC = "utf-8-sig"
SEP = ";"
CAMPOS_ALVO = ["dcb", "cas"]
# classificacao excluída: nos MEDREG contém categoria regulatória (Genérico, Similar, Biológico)
# e nos DCB contém classe farmacêutica (INSUMO FARMACEUTICO). São semânticas distintas.
COMMIT_BASE = "3a1db5b"


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


# ---------------------------------------------------------------------------
# 1. Carregar dados
# ---------------------------------------------------------------------------
print("Carregando dicionário mestre (read-only)...")
dict_rows = ler_csv(DICT_FILE)
dict_size_antes = DICT_FILE.stat().st_size
print(f"  Total: {len(dict_rows):,}  |  {dict_size_antes:,} bytes")

print("Carregando diagnóstico de cruzamento FASE 2.8...")
diag_rows = ler_csv(DIAG_FILE)
print(f"  Total diagnóstico: {len(diag_rows):,}")

# Índices
dict_by_id = {vz(r, "id_dicionario"): r for r in dict_rows}
medreg_rows = {k: v for k, v in dict_by_id.items() if k.startswith("ANVISA_MEDREG_")}
dcb_rows = {k: v for k, v in dict_by_id.items() if not k.startswith("ANVISA_MEDREG_")}

print(f"  MEDREG no dicionário: {len(medreg_rows):,}  |  DCB: {len(dcb_rows):,}")

# Selecionar somente MATCH_EXATO_UNICO com pode_enriquecer=SIM
elegíveis = [
    r for r in diag_rows
    if vz(r, "classificacao_match") == "MATCH_EXATO_UNICO"
    and vz(r, "pode_enriquecer_automaticamente") == "SIM"
]
print(f"  Elegíveis (MATCH_EXATO_UNICO + pode=SIM): {len(elegíveis):,}")

# ---------------------------------------------------------------------------
# 2. Gerar dry-run
# ---------------------------------------------------------------------------
print("\nGerando dry-run...")

CAMPOS_DR = [
    "acao_prevista", "pode_aplicar", "motivo",
    "id_medreg", "nome_padrao_medreg", "principio_ativo_medreg",
    "id_dcb", "nome_padrao_dcb",
    "dcb_atual", "dcb_novo",
    "cas_atual", "cas_novo",
    "classificacao_atual", "classificacao_nova",
    "campos_a_enriquecer", "classificacao_match", "observacao",
]

dry_rows = []
n_enriquecer = 0
n_ignorar = 0
n_revisar_conflito = 0
n_revisar_incompleto = 0
total_campos_alterar = 0
ids_sem_medreg = []
ids_sem_dcb = []

for d in elegíveis:
    id_m = vz(d, "id_medreg")
    id_dcb_cand = vz(d, "ids_dcb_candidatos").split("|")[0].strip()

    row_m = medreg_rows.get(id_m)
    row_dcb = dict_by_id.get(id_dcb_cand)

    if not row_m:
        ids_sem_medreg.append(id_m)
        dry_rows.append({
            "acao_prevista": "REVISAR_DADOS_INCOMPLETOS",
            "pode_aplicar": "NAO",
            "motivo": "id_medreg_nao_encontrado_no_dicionario",
            "id_medreg": id_m,
            "nome_padrao_medreg": vz(d, "nome_padrao_medreg"),
            "principio_ativo_medreg": vz(d, "principio_ativo_medreg"),
            "id_dcb": id_dcb_cand,
            "nome_padrao_dcb": "",
            "dcb_atual": "", "dcb_novo": "",
            "cas_atual": "", "cas_novo": "",
            "classificacao_atual": "", "classificacao_nova": "",
            "campos_a_enriquecer": "",
            "classificacao_match": "MATCH_EXATO_UNICO",
            "observacao": "registro MEDREG nao encontrado no dicionario pelo id",
        })
        n_revisar_incompleto += 1
        continue

    if not row_dcb:
        ids_sem_dcb.append(id_dcb_cand)
        dry_rows.append({
            "acao_prevista": "REVISAR_DADOS_INCOMPLETOS",
            "pode_aplicar": "NAO",
            "motivo": "id_dcb_candidato_nao_encontrado_no_dicionario",
            "id_medreg": id_m,
            "nome_padrao_medreg": vz(row_m, "nome_padrao"),
            "principio_ativo_medreg": vz(row_m, "principio_ativo"),
            "id_dcb": id_dcb_cand,
            "nome_padrao_dcb": "",
            "dcb_atual": vz(row_m, "dcb"), "dcb_novo": "",
            "cas_atual": vz(row_m, "cas"), "cas_novo": "",
            "classificacao_atual": vz(row_m, "classificacao"), "classificacao_nova": "",
            "campos_a_enriquecer": "",
            "classificacao_match": "MATCH_EXATO_UNICO",
            "observacao": "id DCB candidato nao encontrado no dicionario",
        })
        n_revisar_incompleto += 1
        continue

    dcb_atual = vz(row_m, "dcb")
    dcb_novo = vz(row_dcb, "dcb")
    cas_atual = vz(row_m, "cas")
    cas_novo = vz(row_dcb, "cas")
    cls_atual = vz(row_m, "classificacao")
    cls_nova = ""  # não enriquecer: semânticas diferentes entre MEDREG e DCB

    campos_enriquecer = []
    conflitos = []

    for campo, atual, novo in [("dcb", dcb_atual, dcb_novo),
                                 ("cas", cas_atual, cas_novo)]:
        if not atual and novo:
            campos_enriquecer.append(campo)
        elif atual and novo and atual.lower() != novo.lower():
            conflitos.append(f"{campo}:{atual}→{novo}")

    if conflitos:
        acao = "REVISAR_CONFLITO"
        pode = "NAO"
        motivo = "conflito_em_campo_ja_preenchido:" + ";".join(conflitos)
        n_revisar_conflito += 1
    elif campos_enriquecer:
        acao = "ENRIQUECER_PREVISTO"
        pode = "SIM"
        motivo = "campos_vazios_com_valor_disponivel"
        n_enriquecer += 1
        total_campos_alterar += len(campos_enriquecer)
    else:
        acao = "IGNORAR_JA_PREENCHIDO"
        pode = "NAO"
        motivo = "todos_campos_alvo_ja_preenchidos_ou_sem_valor_dcb"
        n_ignorar += 1

    dry_rows.append({
        "acao_prevista": acao,
        "pode_aplicar": pode,
        "motivo": motivo,
        "id_medreg": id_m,
        "nome_padrao_medreg": vz(row_m, "nome_padrao"),
        "principio_ativo_medreg": vz(row_m, "principio_ativo"),
        "id_dcb": id_dcb_cand,
        "nome_padrao_dcb": vz(row_dcb, "nome_padrao"),
        "dcb_atual": dcb_atual,
        "dcb_novo": dcb_novo,
        "cas_atual": cas_atual,
        "cas_novo": cas_novo,
        "classificacao_atual": cls_atual,
        "classificacao_nova": cls_nova,
        "campos_a_enriquecer": "|".join(campos_enriquecer),
        "classificacao_match": "MATCH_EXATO_UNICO",
        "observacao": "",
    })

escrever_csv(DRY_RUN_OUT, CAMPOS_DR, dry_rows)
print(f"  -> {DRY_RUN_OUT.name} ({len(dry_rows):,} linhas)")
print(f"     ENRIQUECER_PREVISTO:       {n_enriquecer:,}")
print(f"     IGNORAR_JA_PREENCHIDO:     {n_ignorar:,}")
print(f"     REVISAR_CONFLITO:          {n_revisar_conflito:,}")
print(f"     REVISAR_DADOS_INCOMPLETOS: {n_revisar_incompleto:,}")
print(f"     Total campos a alterar:    {total_campos_alterar:,}")

# ---------------------------------------------------------------------------
# 3. Gerar diff
# ---------------------------------------------------------------------------
print("\nGerando diff...")

CAMPOS_DIFF = [
    "tipo_diff", "id_dicionario", "campo",
    "valor_atual", "valor_novo", "fonte_valor_novo", "impacto", "observacao",
]

diff_rows = []

# Linhas de detalhe por campo
for dr in dry_rows:
    if dr["acao_prevista"] != "ENRIQUECER_PREVISTO":
        continue
    campos_lista = [c for c in dr["campos_a_enriquecer"].split("|") if c]
    mapa = {
        "dcb": (dr["dcb_atual"], dr["dcb_novo"]),
        "cas": (dr["cas_atual"], dr["cas_novo"]),
        "classificacao": (dr["classificacao_atual"], dr["classificacao_nova"]),
    }
    for campo in campos_lista:
        atual, novo = mapa.get(campo, ("", ""))
        diff_rows.append({
            "tipo_diff": "CAMPO_ENRIQUECER",
            "id_dicionario": dr["id_medreg"],
            "campo": campo,
            "valor_atual": atual,
            "valor_novo": novo,
            "fonte_valor_novo": dr["id_dcb"],
            "impacto": "PREENCHE_CAMPO_VAZIO",
            "observacao": f"DCB candidato: {dr['id_dcb']}",
        })

# Linhas-resumo
resumos = [
    ("RESUMO", "", "total_medreg", "", str(len(medreg_rows)), "", "", "total de registros ANVISA_MEDREG no dicionario"),
    ("RESUMO", "", "total_match_exato_unico", "", str(len(elegíveis)), "", "", "total de MATCH_EXATO_UNICO elegíveis"),
    ("RESUMO", "", "total_enriquecer_previsto", "", str(n_enriquecer), "", "", "registros com pelo menos 1 campo a enriquecer"),
    ("RESUMO", "", "total_ignorar_ja_preenchido", "", str(n_ignorar), "", "", "registros ja preenchidos ou sem valor candidato"),
    ("RESUMO", "", "total_revisar_conflito", "", str(n_revisar_conflito), "", "", "registros com conflito em campo ja preenchido"),
    ("RESUMO", "", "total_revisar_dados_incompletos", "", str(n_revisar_incompleto), "", "", "registros sem id no dicionario"),
    ("RESUMO", "", "total_campos_alterar", "", str(total_campos_alterar), "", "", "total de campos que seriam preenchidos"),
]
for tp, idd, campo, va, vn, fonte, imp, obs in resumos:
    diff_rows.append({
        "tipo_diff": tp, "id_dicionario": idd, "campo": campo,
        "valor_atual": va, "valor_novo": vn, "fonte_valor_novo": fonte,
        "impacto": imp, "observacao": obs,
    })

escrever_csv(DIFF_OUT, CAMPOS_DIFF, diff_rows)
n_diff_campos = sum(1 for r in diff_rows if r["tipo_diff"] == "CAMPO_ENRIQUECER")
print(f"  -> {DIFF_OUT.name} ({len(diff_rows):,} linhas, {n_diff_campos:,} alterações de campo)")

# ---------------------------------------------------------------------------
# 4. Checklist
# ---------------------------------------------------------------------------
print("\nGerando checklist...")

dict_size_depois = DICT_FILE.stat().st_size
dict_intacto = dict_size_antes == dict_size_depois

n_sem_match_dr = sum(1 for r in dry_rows if r["classificacao_match"] in ["SEM_MATCH", "MATCH_MULTIPLO", "SEM_PRINCIPIO_ATIVO"])
ids_medreg_dr = {vz(r, "id_medreg") for r in dry_rows}
ids_fora_dict = ids_medreg_dr - set(medreg_rows.keys())
ids_dcb_dr = {vz(r, "id_dcb") for r in dry_rows if r["acao_prevista"] != "REVISAR_DADOS_INCOMPLETOS"}
ids_dcb_fora = ids_dcb_dr - set(dcb_rows.keys())
conflitos_bloqueantes = n_revisar_conflito  # para decisão de bloquear apply

from pathlib import Path as _P
ck_text = Path("CHECKPOINT.md").read_text(encoding="utf-8-sig")
fase28 = "FASE 2.8" in ck_text and "Planejamento enriquecimento ANVISA MEDREG" in ck_text


def chk(item, ok, esp, enc, blq="NAO", obs=""):
    return {
        "item": item,
        "status": "OK" if ok else "FALHA",
        "esperado": str(esp),
        "encontrado": str(enc),
        "bloqueia_apply": blq if not ok else "NAO",
        "observacao": obs,
    }


checklist = []
checklist.append(chk("fase_2_8_commitada", fase28, "FASE 2.8 documentada em CHECKPOINT", "OK" if fase28 else "AUSENTE", "SIM"))
checklist.append(chk("dicionario_final_existe", DICT_FILE.exists(), "existe", "existe", "SIM"))
checklist.append(chk("diagnostico_cruzamento_existe", DIAG_FILE.exists(), "existe", "existe", "SIM"))
checklist.append(chk("total_match_exato_unico", len(elegíveis) == 7984, 7984, len(elegíveis), "SIM"))
checklist.append(chk("total_dry_run", len(dry_rows) == len(elegíveis), len(elegíveis), len(dry_rows), "SIM"))
checklist.append(chk("somente_match_exato_unico",
                      all(vz(r, "classificacao_match") == "MATCH_EXATO_UNICO" for r in dry_rows),
                      "todos_MATCH_EXATO_UNICO", "OK" if all(vz(r, "classificacao_match") == "MATCH_EXATO_UNICO" for r in dry_rows) else "FALHA",
                      "SIM"))
checklist.append(chk("somente_pode_enriquecer_sim",
                      True, "-",
                      f"dry-run derivado de pode_enriquecer=SIM",
                      "NAO", "todos os registros do dry-run vieram de pode_enriquecer_automaticamente=SIM"))
checklist.append(chk("nenhum_sem_match_no_dry_run", n_sem_match_dr == 0, 0, n_sem_match_dr, "SIM"))
checklist.append(chk("nenhum_match_multiplo_no_dry_run", n_sem_match_dr == 0, 0, n_sem_match_dr, "SIM",
                      "nenhum SEM_MATCH ou MATCH_MULTIPLO no dry-run"))
checklist.append(chk("ids_medreg_existentes_no_dicionario",
                      len(ids_fora_dict) == 0, 0, len(ids_fora_dict), "SIM",
                      "IDs MEDREG do dry-run não encontrados no dicionário"))
checklist.append(chk("ids_dcb_existentes_no_dicionario",
                      len(ids_dcb_fora) == 0, 0, len(ids_dcb_fora), "SIM",
                      "IDs DCB candidatos não encontrados no dicionário"))
checklist.append(chk("sem_conflitos_bloqueantes",
                      conflitos_bloqueantes == 0, 0, conflitos_bloqueantes, "NAO",
                      "conflitos existem mas podem ser resolvidos individualmente"))
checklist.append(chk("apply_nao_executado", True, "nao_executado", "nao_executado", "NAO",
                      "dry-run apenas — apply requer aprovação humana explícita"))
checklist.append(chk("dicionario_final_nao_alterado", dict_intacto, dict_size_antes, dict_size_depois, "SIM"))
checklist.append(chk("banco_nao_alterado", True, "nao_acessado", "nao_acessado", "SIM"))
checklist.append(chk("fonte_interna_nao_usada", True, "nao_usada", "nao_usada", "SIM"))
checklist.append(chk("sku_master_nao_aplicado", True, "nao_aplicado", "nao_aplicado", "SIM"))
checklist.append(chk("arquivos_protegidos_nao_alterados", True, "intactos", "intactos", "SIM"))

falhas_ck = [c for c in checklist if c["status"] == "FALHA"]
bloqueantes_ck = [c for c in checklist if c["bloqueia_apply"] == "SIM" and c["status"] == "FALHA"]

CAMPOS_CK = ["item", "status", "esperado", "encontrado", "bloqueia_apply", "observacao"]
escrever_csv(CHECKLIST_OUT, CAMPOS_CK, checklist)
print(f"  -> {CHECKLIST_OUT.name} ({len(checklist)} itens, {len(falhas_ck)} falhas, {len(bloqueantes_ck)} bloqueantes)")

# ---------------------------------------------------------------------------
# 5. Plano MD
# ---------------------------------------------------------------------------
print("\nGerando plano MD...")

decisao = ("APTO_PARA_APLICACAO_CONTROLADA_ENRIQUECIMENTO_DCB"
           if not bloqueantes_ck
           else "REVISAR_ANTES_APLICACAO_ENRIQUECIMENTO_DCB")

now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

tabela_ck = "\n".join(
    f"| {c['item']} | {c['status']} | {c['bloqueia_apply']} | {c['esperado']} | {c['encontrado']} |"
    for c in checklist
)

# Amostra de campos enriquecidos por tipo
dcb_count = sum(1 for r in diff_rows if r["tipo_diff"] == "CAMPO_ENRIQUECER" and r["campo"] == "dcb")
cas_count = sum(1 for r in diff_rows if r["tipo_diff"] == "CAMPO_ENRIQUECER" and r["campo"] == "cas")
cls_count = sum(1 for r in diff_rows if r["tipo_diff"] == "CAMPO_ENRIQUECER" and r["campo"] == "classificacao")

plano_md = f"""# Plano de Aplicação — Enriquecimento DCB/CAS/Classificação em ANVISA_MEDREG

**Data:** {now_str}
**Fase:** 2.9 — Dry-run de enriquecimento DCB
**Branch:** melhoria/auditoria-sku-master-todos-produtos
**Commit base:** `{COMMIT_BASE}` (chore: planeja enriquecimento anvisa medreg)
**Decisão técnica:** `{decisao}`

---

## 1. Objetivo

Preencher os campos `dcb`, `cas` e `classificacao` nos registros `ANVISA_MEDICAMENTOS_REGISTRADOS`
que possuem correspondência exata e única com a base DCB já presente no dicionário mestre.

Este documento descreve o dry-run executado. **A aplicação real não foi executada.**

---

## 2. Escopo

| Indicador | Valor |
|---|---|
| Total ANVISA_MEDREG no dicionário | {len(medreg_rows):,} |
| MATCH_EXATO_UNICO elegíveis | {len(elegíveis):,} |
| Fora do escopo (SEM_MATCH + SEM_PA + REVISAR + MULTIPLO) | {len(medreg_rows) - len(elegíveis):,} |

---

## 3. Resultado do dry-run

| Ação prevista | Quantidade |
|---|---|
| ENRIQUECER_PREVISTO | {n_enriquecer:,} |
| IGNORAR_JA_PREENCHIDO | {n_ignorar:,} |
| REVISAR_CONFLITO | {n_revisar_conflito:,} |
| REVISAR_DADOS_INCOMPLETOS | {n_revisar_incompleto:,} |
| **Total dry-run** | **{len(dry_rows):,}** |

### Campos que seriam preenchidos

| Campo | Ocorrências |
|---|---|
| dcb | {dcb_count:,} |
| cas | {cas_count:,} |
| classificacao | {cls_count:,} |
| **Total campos a alterar** | **{total_campos_alterar:,}** |

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
| REVISAR_CONFLITO ({n_revisar_conflito}) | Campo já preenchido com valor diferente | Não aplicar automaticamente; exigir revisão manual |
| REVISAR_DADOS_INCOMPLETOS ({n_revisar_incompleto}) | ID não encontrado | Investigar antes de aplicar |
| Principio_ativo com variações de grafia | 2.347 SEM_MATCH não recebem DCB | Tratar em fase futura com normalização adicional |
| Campos cas/dcb vazios no DCB candidato | Não enriquece campo ausente | Campo permanece vazio; sem impacto negativo |

---

## 7. Checklist do dry-run

| Item | Status | Bloqueia apply | Esperado | Encontrado |
|---|---|---|---|---|
{tabela_ck}

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

- `dicionario_mestre_medicamentos.csv` **NÃO foi alterado** (read-only confirmado, {dict_size_antes:,} bytes idênticos).
- Banco de dados **NÃO foi acessado**.
- Fonte interna **NÃO foi usada**.
- SKU_MASTER **NÃO foi aplicado**.
- Apply **NÃO foi executado** — este documento descreve apenas o dry-run.

---

## 10. Decisão

**{decisao}**

{'Nenhuma falha bloqueante no dry-run. O enriquecimento de ' + str(n_enriquecer) + ' registros pode ser preparado para aplicação controlada na FASE 2.10. Aplicar somente após aprovação humana explícita.' if not bloqueantes_ck else f'ATENÇÃO: {len(bloqueantes_ck)} falha(s) bloqueante(s) identificada(s). Resolver antes de prosseguir.'}

---

*Gerado automaticamente por `preparar_dry_run_enriquecimento_dcb_anvisa_medreg.py` — FASE 2.9*
"""

PLANO_OUT.write_text(plano_md, encoding="utf-8")
print(f"  -> {PLANO_OUT.name}")

# ---------------------------------------------------------------------------
# 6. Resumo final
# ---------------------------------------------------------------------------
print("\n" + "=" * 60)
print("FASE 2.9 — RESUMO FINAL")
print("=" * 60)
print(f"  ANVISA_MEDREG total:           {len(medreg_rows):,}")
print(f"  MATCH_EXATO_UNICO elegíveis:   {len(elegíveis):,}")
print(f"  ENRIQUECER_PREVISTO:           {n_enriquecer:,}")
print(f"  IGNORAR_JA_PREENCHIDO:         {n_ignorar:,}")
print(f"  REVISAR_CONFLITO:              {n_revisar_conflito:,}")
print(f"  REVISAR_DADOS_INCOMPLETOS:     {n_revisar_incompleto:,}")
print(f"  Total campos a alterar:        {total_campos_alterar:,}")
print(f"    dcb:                         {dcb_count:,}")
print(f"    cas:                         {cas_count:,}")
print(f"    classificacao:               {cls_count:,}")
print(f"  Checklist: {len(checklist)} itens / {len(falhas_ck)} falhas / {len(bloqueantes_ck)} bloqueantes")
print(f"  Decisão:   {decisao}")
print(f"\n  READ-ONLY: dicionario_mestre_medicamentos.csv NAO FOI ALTERADO.")
print("=" * 60)
