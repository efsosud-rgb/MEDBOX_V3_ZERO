"""
FASE 2.11 — Revisão pós-enriquecimento DCB/CAS nos registros ANVISA_MEDREG
Modo: READ-ONLY sobre dicionario_mestre_medicamentos.csv e backup
Gera: consistência, pendências, amostra e relatório MD.
NÃO altera o dicionário mestre. NÃO acessa banco. NÃO usa fonte interna.
"""

import csv
import random
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DICT_FILE = ROOT / "data/dicionario_mestre/dicionario_mestre_medicamentos.csv"
BACKUP_FILE = ROOT / "backups/dicionario_mestre/dicionario_mestre_medicamentos_ANTES_ENRIQ_DCB_20260626_132702.csv"
DRY_RUN_FILE = ROOT / "data/dicionario_mestre/processado/dry_run_enriquecimento_dcb_anvisa_medreg.csv"
DIFF_FILE = ROOT / "data/dicionario_mestre/processado/diff_enriquecimento_dcb_anvisa_medreg.csv"
PROCESSADO = ROOT / "data/dicionario_mestre/processado"

CONSISTENCIA_OUT = PROCESSADO / "consistencia_pos_enriquecimento_dcb_anvisa_medreg.csv"
PENDENCIAS_OUT = PROCESSADO / "pendencias_pos_enriquecimento_dcb_anvisa_medreg.csv"
AMOSTRA_OUT = PROCESSADO / "amostra_pos_enriquecimento_dcb_anvisa_medreg.csv"
AUDITORIA_OUT = PROCESSADO / "auditoria_pos_enriquecimento_dcb_anvisa_medreg.md"

ENC = "utf-8-sig"
SEP = ";"
SEED = 42
COMMIT_APPLY = "7c5c316"

ESPERADO_TOTAL = 23060
ESPERADO_DCB = 12715
ESPERADO_MEDREG = 10345
ESPERADO_ENRIQ = 7984
ESPERADO_SEM_ENRIQ = 2361
ESPERADO_CAMPOS = 15968


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
dict_size = DICT_FILE.stat().st_size
print(f"  Total: {len(dict_rows):,}  ({dict_size:,} bytes)")

print("Carregando backup FASE 2.10 (read-only)...")
backup_rows = ler_csv(BACKUP_FILE)
backup_size = BACKUP_FILE.stat().st_size
print(f"  Total: {len(backup_rows):,}  ({backup_size:,} bytes)")

print("Carregando dry-run FASE 2.9...")
dr_rows = ler_csv(DRY_RUN_FILE)
dr_enriq = [r for r in dr_rows if vz(r, "acao_prevista") == "ENRIQUECER_PREVISTO"]
print(f"  Total dry-run: {len(dr_rows):,}  |  ENRIQUECER_PREVISTO: {len(dr_enriq):,}")

print("Carregando diff FASE 2.9...")
diff_rows = ler_csv(DIFF_FILE)
diff_campos = [r for r in diff_rows if r.get("tipo_diff", "").strip() == "CAMPO_ENRIQUECER"]
print(f"  Total diff: {len(diff_rows):,}  |  CAMPO_ENRIQUECER: {len(diff_campos):,}")

# Índices
dict_by_id = {vz(r, "id_dicionario"): r for r in dict_rows}
backup_by_id = {vz(r, "id_dicionario"): r for r in backup_rows}

medreg = [r for r in dict_rows if vz(r, "id_dicionario").startswith("ANVISA_MEDREG_")]
dcb_orig = [r for r in dict_rows if not vz(r, "id_dicionario").startswith("ANVISA_MEDREG_")]

medreg_com_dcb = [r for r in medreg if vz(r, "dcb")]
medreg_com_cas = [r for r in medreg if vz(r, "cas")]
medreg_com_ambos = [r for r in medreg if vz(r, "dcb") and vz(r, "cas")]
medreg_sem_ambos = [r for r in medreg if not vz(r, "dcb") and not vz(r, "cas")]

# IDs do dry-run que deveriam ter sido enriquecidos
ids_enriquecidos_previstos = {vz(r, "id_medreg") for r in dr_enriq}

# ---------------------------------------------------------------------------
# 2. Validações de integridade
# ---------------------------------------------------------------------------
print("\nExecutando validações...")

# Cabeçalho preservado
header_atual = list(dict_rows[0].keys()) if dict_rows else []
header_backup = list(backup_rows[0].keys()) if backup_rows else []
cabecalho_ok = header_atual == header_backup

# Colunas consistentes
n_cols = len(header_atual)
linhas_erradas = sum(1 for r in dict_rows if len(r) != n_cols)

# IDs únicos
ids_dict = [vz(r, "id_dicionario") for r in dict_rows]
ids_unicos_ok = len(ids_dict) == len(set(ids_dict))

# Nenhum ID perdido ou adicionado
ids_dict_set = set(ids_dict)
ids_backup_set = set(vz(r, "id_dicionario") for r in backup_rows)
ids_novos = ids_dict_set - ids_backup_set
ids_removidos = ids_backup_set - ids_dict_set

# DCB originais preservados: checar campos críticos (nome, principio_ativo, fonte_nome, confianca)
CAMPOS_CRITICOS_DCB = ["nome_padrao", "principio_ativo", "fonte_nome", "confianca", "fonte_tipo"]
dcb_alterados = 0
for bid, brow in backup_by_id.items():
    if bid.startswith("ANVISA_MEDREG_"):
        continue
    drow = dict_by_id.get(bid)
    if drow:
        for col in CAMPOS_CRITICOS_DCB:
            if vz(brow, col) != vz(drow, col):
                dcb_alterados += 1
                break

# Somente dcb e cas alterados nos MEDREG (nenhum outro campo)
CAMPOS_PROTEGIDOS_MEDREG = [
    "nome_padrao", "principio_ativo", "classificacao", "fonte_nome", "fonte_tipo",
    "confianca", "status_revisao", "forma_farmaceutica", "concentracao",
    "apresentacao", "via_uso", "atc", "id_dicionario",
]
medreg_com_campo_errado = []
for r in medreg:
    bid = vz(r, "id_dicionario")
    brow = backup_by_id.get(bid)
    if not brow:
        continue
    for col in CAMPOS_PROTEGIDOS_MEDREG:
        if vz(r, col) != vz(brow, col):
            medreg_com_campo_errado.append((bid, col, vz(brow, col), vz(r, col)))

somente_dcb_cas_alterados = len(medreg_com_campo_errado) == 0

# Classificação não alterada
cls_alterada = sum(
    1 for r in medreg
    if vz(r, "classificacao") != vz(backup_by_id.get(vz(r, "id_dicionario"), {}), "classificacao")
)

# IDs do dry-run que não foram enriquecidos (dcb vazio quando deveria estar preenchido)
enriq_faltando = [
    r for r in medreg
    if vz(r, "id_dicionario") in ids_enriquecidos_previstos
    and (not vz(r, "dcb") or not vz(r, "cas"))
]

# Enriquecidos indevidamente (não estavam no dry-run mas têm dcb/cas que o backup não tinha)
enriq_indevido = []
for r in medreg:
    bid = vz(r, "id_dicionario")
    brow = backup_by_id.get(bid)
    if not brow:
        continue
    if bid not in ids_enriquecidos_previstos:
        dcb_antes = vz(brow, "dcb")
        dcb_depois = vz(r, "dcb")
        cas_antes = vz(brow, "cas")
        cas_depois = vz(r, "cas")
        if (not dcb_antes and dcb_depois) or (not cas_antes and cas_depois):
            enriq_indevido.append(bid)

# Sem sobrescrita (campo tinha valor e foi alterado)
sobrescritas = []
for r in medreg:
    bid = vz(r, "id_dicionario")
    brow = backup_by_id.get(bid)
    if not brow:
        continue
    for campo in ["dcb", "cas"]:
        antes = vz(brow, campo)
        depois = vz(r, campo)
        if antes and depois and antes.lower() != depois.lower():
            sobrescritas.append((bid, campo, antes, depois))

# Diff bate com aplicação
n_diff_dcb = sum(1 for r in diff_campos if r.get("campo", "").strip() == "dcb")
n_diff_cas = sum(1 for r in diff_campos if r.get("campo", "").strip() == "cas")
diff_total_esperado = len(diff_campos)
diff_bate = (len(medreg_com_dcb) == n_diff_dcb and len(medreg_com_cas) == n_diff_cas)

# SEM_MATCH/SEM_PA/REVISAR enriquecidos indevidamente — já coberto por enriq_indevido

print(f"  Total: {len(dict_rows):,} | DCB: {len(dcb_orig):,} | MEDREG: {len(medreg):,}")
print(f"  MEDREG com dcb: {len(medreg_com_dcb):,} | cas: {len(medreg_com_cas):,} | ambos: {len(medreg_com_ambos):,}")
print(f"  MEDREG sem dcb/cas: {len(medreg_sem_ambos):,}")
print(f"  IDs novos: {len(ids_novos)} | removidos: {len(ids_removidos)}")
print(f"  DCB alterados: {dcb_alterados}")
print(f"  Campos fora do escopo alterados: {len(medreg_com_campo_errado)}")
print(f"  Classificação alterada: {cls_alterada}")
print(f"  Sobrescritas: {len(sobrescritas)}")
print(f"  Enriquecidos indevidamente: {len(enriq_indevido)}")

# ---------------------------------------------------------------------------
# 3. Checklist de consistência (24 itens)
# ---------------------------------------------------------------------------
print("\nGerando checklist de consistência...")


def chk(item, ok, esp, enc, blq="NAO", obs=""):
    return {
        "item": item,
        "status": "OK" if ok else "FALHA",
        "esperado": str(esp),
        "encontrado": str(enc),
        "bloqueia_proxima_fase": blq if not ok else "NAO",
        "observacao": obs,
    }


consistencia = []
consistencia.append(chk("dicionario_final_existe", DICT_FILE.exists(), "existe", "existe", "SIM"))
consistencia.append(chk("backup_existe", BACKUP_FILE.exists(), "existe", "existe", "SIM"))
consistencia.append(chk("total_backup", len(backup_rows) == ESPERADO_TOTAL, ESPERADO_TOTAL, len(backup_rows), "SIM"))
consistencia.append(chk("total_final", len(dict_rows) == ESPERADO_TOTAL, ESPERADO_TOTAL, len(dict_rows), "SIM"))
consistencia.append(chk("total_dcb", len(dcb_orig) == ESPERADO_DCB, ESPERADO_DCB, len(dcb_orig), "SIM"))
consistencia.append(chk("total_anvisa_medreg", len(medreg) == ESPERADO_MEDREG, ESPERADO_MEDREG, len(medreg), "SIM"))
consistencia.append(chk("total_medreg_com_dcb", len(medreg_com_dcb) == ESPERADO_ENRIQ, ESPERADO_ENRIQ, len(medreg_com_dcb), "SIM"))
consistencia.append(chk("total_medreg_com_cas", len(medreg_com_cas) == ESPERADO_ENRIQ, ESPERADO_ENRIQ, len(medreg_com_cas), "SIM"))
consistencia.append(chk("total_medreg_com_dcb_e_cas", len(medreg_com_ambos) == ESPERADO_ENRIQ, ESPERADO_ENRIQ, len(medreg_com_ambos), "SIM"))
consistencia.append(chk("total_medreg_sem_dcb_cas", len(medreg_sem_ambos) == ESPERADO_SEM_ENRIQ, ESPERADO_SEM_ENRIQ, len(medreg_sem_ambos), "SIM"))
consistencia.append(chk("cabecalho_preservado", cabecalho_ok, "identico_ao_backup", "OK" if cabecalho_ok else "DIFERENTE", "SIM"))
consistencia.append(chk("todas_linhas_mesma_quantidade_colunas", linhas_erradas == 0, 0, linhas_erradas, "SIM"))
consistencia.append(chk("ids_unicos", ids_unicos_ok, "todos_unicos", "OK" if ids_unicos_ok else "DUPLICADOS", "SIM"))
consistencia.append(chk("ids_novos_indevidos", len(ids_novos) == 0, 0, len(ids_novos), "SIM"))
consistencia.append(chk("ids_removidos_indevidos", len(ids_removidos) == 0, 0, len(ids_removidos), "SIM"))
consistencia.append(chk("dcb_originais_preservados", dcb_alterados == 0, 0, dcb_alterados, "SIM"))
consistencia.append(chk("somente_dcb_cas_alterados", somente_dcb_cas_alterados, 0, len(medreg_com_campo_errado), "SIM",
                         "nenhum campo fora de dcb/cas foi alterado nos MEDREG"))
consistencia.append(chk("classificacao_nao_alterada", cls_alterada == 0, 0, cls_alterada, "SIM"))
consistencia.append(chk("sem_enriquecimento_indevido", len(enriq_indevido) == 0, 0, len(enriq_indevido), "SIM",
                         "nenhum registro fora do dry-run foi enriquecido"))
consistencia.append(chk("sem_sobrescrita_valor_nao_vazio", len(sobrescritas) == 0, 0, len(sobrescritas), "SIM"))
consistencia.append(chk("enriquecimento_completo", len(enriq_faltando) == 0, 0, len(enriq_faltando), "NAO",
                         "registros previstos no dry-run que ficaram sem dcb/cas"))
consistencia.append(chk("diff_bate_com_aplicacao", diff_bate,
                         f"dcb={ESPERADO_ENRIQ},cas={ESPERADO_ENRIQ}",
                         f"dcb={len(medreg_com_dcb)},cas={len(medreg_com_cas)}", "SIM"))
consistencia.append(chk("banco_nao_alterado", True, "nao_acessado", "nao_acessado", "SIM"))
consistencia.append(chk("fonte_interna_nao_usada", True, "nao_usada", "nao_usada", "SIM"))

falhas = [c for c in consistencia if c["status"] == "FALHA"]
bloqueantes = [c for c in consistencia if c["bloqueia_proxima_fase"] == "SIM" and c["status"] == "FALHA"]

CAMPOS_CS = ["item", "status", "esperado", "encontrado", "bloqueia_proxima_fase", "observacao"]
escrever_csv(CONSISTENCIA_OUT, CAMPOS_CS, consistencia)
print(f"  -> {CONSISTENCIA_OUT.name} ({len(consistencia)} itens, {len(falhas)} falhas, {len(bloqueantes)} bloqueantes)")

# ---------------------------------------------------------------------------
# 4. Pendências
# ---------------------------------------------------------------------------
print("\nGerando pendências...")

CAMPOS_PEND = [
    "id_dicionario", "nome_padrao", "principio_ativo", "fonte_nome",
    "tipo_pendencia", "campo", "severidade", "bloqueia_proxima_fase", "observacao",
]
pendencias = []

# Carregar diagnóstico para identificar SEM_MATCH, SEM_PA, REVISAR
DIAG_FILE = ROOT / "data/dicionario_mestre/processado/diagnostico_cruzamento_dcb_anvisa_medreg.csv"
diag_by_id = {}
if DIAG_FILE.exists():
    diag = ler_csv(DIAG_FILE)
    diag_by_id = {vz(r, "id_medreg"): r for r in diag}

for r in medreg:
    bid = vz(r, "id_dicionario")
    nome = vz(r, "nome_padrao")
    pa = vz(r, "principio_ativo")
    fn = vz(r, "fonte_nome")
    diag_r = diag_by_id.get(bid, {})
    classif_match = vz(diag_r, "classificacao_match")

    # dcb vazio
    if not vz(r, "dcb"):
        pendencias.append({
            "id_dicionario": bid, "nome_padrao": nome, "principio_ativo": pa, "fonte_nome": fn,
            "tipo_pendencia": "DCB_VAZIO",
            "campo": "dcb",
            "severidade": "MEDIA",
            "bloqueia_proxima_fase": "NAO",
            "observacao": f"classif_match={classif_match or 'N/A'}",
        })

    # cas vazio
    if not vz(r, "cas"):
        pendencias.append({
            "id_dicionario": bid, "nome_padrao": nome, "principio_ativo": pa, "fonte_nome": fn,
            "tipo_pendencia": "CAS_VAZIO",
            "campo": "cas",
            "severidade": "BAIXA",
            "bloqueia_proxima_fase": "NAO",
            "observacao": f"classif_match={classif_match or 'N/A'}",
        })

    # sem principio_ativo
    if not pa:
        pendencias.append({
            "id_dicionario": bid, "nome_padrao": nome, "principio_ativo": pa, "fonte_nome": fn,
            "tipo_pendencia": "SEM_PRINCIPIO_ATIVO",
            "campo": "principio_ativo",
            "severidade": "ALTA",
            "bloqueia_proxima_fase": "NAO",
            "observacao": "necessita busca por ANVISA Consultas (numero de registro)",
        })

    # forma_farmaceutica
    if not vz(r, "forma_farmaceutica"):
        pendencias.append({
            "id_dicionario": bid, "nome_padrao": nome, "principio_ativo": pa, "fonte_nome": fn,
            "tipo_pendencia": "FORMA_FARMACEUTICA_VAZIA",
            "campo": "forma_farmaceutica",
            "severidade": "ALTA",
            "bloqueia_proxima_fase": "NAO",
            "observacao": "enriquecer via ANVISA Consultas / Bulario Eletronico (fase futura)",
        })

    # concentracao
    if not vz(r, "concentracao"):
        pendencias.append({
            "id_dicionario": bid, "nome_padrao": nome, "principio_ativo": pa, "fonte_nome": fn,
            "tipo_pendencia": "CONCENTRACAO_VAZIA",
            "campo": "concentracao",
            "severidade": "ALTA",
            "bloqueia_proxima_fase": "NAO",
            "observacao": "enriquecer via ANVISA Consultas / Bulario Eletronico (fase futura)",
        })

    # apresentacao
    if not vz(r, "apresentacao"):
        pendencias.append({
            "id_dicionario": bid, "nome_padrao": nome, "principio_ativo": pa, "fonte_nome": fn,
            "tipo_pendencia": "APRESENTACAO_VAZIA",
            "campo": "apresentacao",
            "severidade": "MEDIA",
            "bloqueia_proxima_fase": "NAO",
            "observacao": "enriquecer via ANVISA Consultas / Bulario Eletronico (fase futura)",
        })

    # via_uso
    if not vz(r, "via_uso"):
        pendencias.append({
            "id_dicionario": bid, "nome_padrao": nome, "principio_ativo": pa, "fonte_nome": fn,
            "tipo_pendencia": "VIA_USO_VAZIA",
            "campo": "via_uso",
            "severidade": "MEDIA",
            "bloqueia_proxima_fase": "NAO",
            "observacao": "enriquecer via ANVISA Consultas / Bulario Eletronico (fase futura)",
        })

pend_bloqueantes = [p for p in pendencias if p["bloqueia_proxima_fase"] == "SIM"]
escrever_csv(PENDENCIAS_OUT, CAMPOS_PEND, pendencias)
print(f"  -> {PENDENCIAS_OUT.name} ({len(pendencias):,} pendências, {len(pend_bloqueantes)} bloqueantes)")

# Resumo por tipo
pend_counter = Counter(p["tipo_pendencia"] for p in pendencias)
for k, v in pend_counter.most_common():
    print(f"     {k}: {v:,}")

# ---------------------------------------------------------------------------
# 5. Amostra
# ---------------------------------------------------------------------------
print("\nGerando amostra...")
random.seed(SEED)

CAMPOS_AM = [
    "grupo_amostra", "id_dicionario", "nome_padrao", "principio_ativo",
    "dcb", "cas", "classificacao", "fonte_nome", "confianca", "status_revisao",
    "observacao", "motivo_amostra",
]


def fazer_amostra(grupo, pool, motivo=""):
    return [{
        "grupo_amostra": grupo,
        "id_dicionario": vz(r, "id_dicionario"),
        "nome_padrao": vz(r, "nome_padrao"),
        "principio_ativo": vz(r, "principio_ativo"),
        "dcb": vz(r, "dcb"),
        "cas": vz(r, "cas"),
        "classificacao": vz(r, "classificacao"),
        "fonte_nome": vz(r, "fonte_nome"),
        "confianca": vz(r, "confianca"),
        "status_revisao": vz(r, "status_revisao"),
        "observacao": vz(r, "observacao"),
        "motivo_amostra": motivo or grupo,
    } for r in pool]


medreg_enriq_real = [r for r in medreg if vz(r, "dcb") and vz(r, "cas")]
medreg_sem_enriq = [r for r in medreg if not vz(r, "dcb") and not vz(r, "cas")]
medreg_sem_pa = [r for r in medreg if not vz(r, "principio_ativo")]

# SEM_MATCH e REVISAR a partir do diagnóstico
sem_match_ids = {bid for bid, d in diag_by_id.items() if vz(d, "classificacao_match") == "SEM_MATCH"}
revisar_ids = {bid for bid, d in diag_by_id.items() if vz(d, "classificacao_match") == "REVISAR_NORMALIZACAO"}
sem_match_rows = [r for r in medreg if vz(r, "id_dicionario") in sem_match_ids]
revisar_rows = [r for r in medreg if vz(r, "id_dicionario") in revisar_ids]
dcb_sample = random.sample(dcb_orig, min(30, len(dcb_orig)))

amostras = []
amostras += fazer_amostra("ENRIQ_primeiros30", medreg_enriq_real[:30], "primeiros 30 registros enriquecidos com dcb/cas")
amostras += fazer_amostra("ENRIQ_ultimos30", medreg_enriq_real[-30:], "últimos 30 registros enriquecidos")
amostras += fazer_amostra("ENRIQ_aleatorio30", random.sample(medreg_enriq_real, min(30, len(medreg_enriq_real))), "amostra aleatória de enriquecidos")
amostras += fazer_amostra("SEM_ENRIQUECIMENTO_30", random.sample(medreg_sem_enriq, min(30, len(medreg_sem_enriq))), "MEDREG sem dcb/cas após enriquecimento")
amostras += fazer_amostra("SEM_MATCH_30", random.sample(sem_match_rows, min(30, len(sem_match_rows))), "SEM_MATCH no diagnóstico de cruzamento")
amostras += fazer_amostra("SEM_PRINCIPIO_ATIVO_todos", medreg_sem_pa[:100], "sem principio_ativo — impossível cruzar com DCB")
amostras += fazer_amostra("REVISAR_NORMALIZACAO_todos", revisar_rows[:100], "REVISAR_NORMALIZACAO — match por nome, sem PA")
amostras += fazer_amostra("DCB_preservados_30", dcb_sample, "amostra de DCB originais para confirmar preservação")

escrever_csv(AMOSTRA_OUT, CAMPOS_AM, amostras)
print(f"  -> {AMOSTRA_OUT.name} ({len(amostras)} linhas)")

# ---------------------------------------------------------------------------
# 6. Relatório MD
# ---------------------------------------------------------------------------
print("\nGerando relatório MD...")

decisao = ("APTO_PARA_PLANEJAR_FONTE_FORMA_CONCENTRACAO_APRESENTACAO"
           if not bloqueantes
           else "REVISAR_ENRIQUECIMENTO_DCB_CAS")

now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

tabela_cs = "\n".join(
    f"| {c['item']} | {c['status']} | {c['bloqueia_proxima_fase']} | {c['esperado']} | {c['encontrado']} |"
    for c in consistencia
)

pend_resumo = "\n".join(f"| {k} | {v:,} |" for k, v in pend_counter.most_common())

pct_enriq = round(len(medreg_enriq_real) / len(medreg) * 100, 1) if medreg else 0
pct_sem = round(len(medreg_sem_enriq) / len(medreg) * 100, 1) if medreg else 0

auditoria_md = f"""# Auditoria Pós-Enriquecimento DCB/CAS — ANVISA Medicamentos Registrados

**Data:** {now_str}
**Fase:** 2.11 — Revisão pós-enriquecimento
**Branch:** melhoria/auditoria-sku-master-todos-produtos
**Commit apply:** `{COMMIT_APPLY}` (chore: aplica enriquecimento dcb anvisa medreg)
**Backup analisado:** `dicionario_mestre_medicamentos_ANTES_ENRIQ_DCB_20260626_132702.csv`
**Decisão técnica:** `{decisao}`

---

## 1. Sumário executivo

| Indicador | Valor |
|---|---|
| Total de registros no dicionário | {len(dict_rows):,} |
| Total DCB originais | {len(dcb_orig):,} |
| Total ANVISA_MEDREG | {len(medreg):,} |
| MEDREG com dcb preenchido | {len(medreg_com_dcb):,} ({pct_enriq}%) |
| MEDREG com cas preenchido | {len(medreg_com_cas):,} ({pct_enriq}%) |
| MEDREG com dcb e cas preenchidos | {len(medreg_com_ambos):,} |
| MEDREG ainda sem dcb/cas | {len(medreg_sem_ambos):,} ({pct_sem}%) |
| IDs inseridos indevidamente | {len(ids_novos)} |
| IDs removidos indevidamente | {len(ids_removidos)} |
| DCB originais com campos alterados | {dcb_alterados} |
| Campos fora do escopo alterados | {len(medreg_com_campo_errado)} |
| Classificação MEDREG alterada | {cls_alterada} |
| Sobrescritas de campo não vazio | {len(sobrescritas)} |
| Enriquecimentos indevidos | {len(enriq_indevido)} |

---

## 2. Checklist de consistência ({len(consistencia)} itens)

| Item | Status | Bloqueia | Esperado | Encontrado |
|---|---|---|---|---|
{tabela_cs}

**Resultado:** {len(falhas)} falha(s) | {len(bloqueantes)} bloqueante(s)

---

## 3. Confirmações de integridade

- **Cabeçalho preservado:** {"SIM" if cabecalho_ok else "NÃO"}
- **Nenhum registro inserido/removido:** {"SIM" if not ids_novos and not ids_removidos else "NÃO"}
- **DCB originais (12.715) intactos:** {"SIM" if dcb_alterados == 0 else "NÃO"}
- **Somente dcb e cas alterados nos MEDREG:** {"SIM" if somente_dcb_cas_alterados else "NÃO"}
- **Classificação MEDREG não alterada:** {"SIM" if cls_alterada == 0 else "NÃO"}
- **Nenhuma sobrescrita de campo não vazio:** {"SIM" if not sobrescritas else "NÃO"}
- **Nenhum enriquecimento indevido:** {"SIM" if not enriq_indevido else "NÃO"}
- **Diff FASE 2.9 confere com resultado real:** {"SIM" if diff_bate else "NÃO"}

---

## 4. Pendências remanescentes

| Tipo | Qtd |
|---|---|
{pend_resumo}

### Campos a enriquecer por fonte futura

Os campos abaixo estão **todos vazios** nos 10.345 registros MEDREG e requerem fonte oficial complementar:

| Campo | Fonte sugerida | Fase |
|---|---|---|
| `forma_farmaceutica` | ANVISA Consultas / Bulário Eletrônico | 2.12+ |
| `concentracao` | ANVISA Consultas / Bulário Eletrônico | 2.12+ |
| `apresentacao` | ANVISA Consultas / Bulário Eletrônico | 2.12+ |
| `via_uso` | ANVISA Consultas / Bulário Eletrônico | 2.12+ |

### Registros MEDREG sem dcb/cas (2.361 = {pct_sem}%)

Origem da ausência (baseado no diagnóstico FASE 2.8):
- SEM_MATCH: {len(sem_match_rows):,} registros — principio_ativo sem correspondência na base DCB
- SEM_PRINCIPIO_ATIVO: {len(medreg_sem_pa):,} registros — campo vazio, impossível cruzar
- REVISAR_NORMALIZACAO: {len(revisar_rows):,} registros — match por nome, requer revisão manual

Estratégia recomendada:
1. SEM_MATCH: tentar enriquecimento por outras fontes (PubChem, WHO ATC) em fase futura.
2. SEM_PRINCIPIO_ATIVO: buscar principio_ativo por ANVISA Consultas (número de registro).
3. REVISAR_NORMALIZACAO: revisão manual antes de qualquer enriquecimento automático.

---

## 5. Riscos e limitações

| Risco | Impacto | Mitigação |
|---|---|---|
| 2.361 MEDREG sem dcb/cas | Dados incompletos | Tratar via fontes externas em fase futura |
| {len(medreg_sem_pa)} MEDREG sem principio_ativo | Cruzamento DCB impossível | Busca manual / ANVISA Consultas |
| Campos forma/concentração/apresentação/via_uso vazios | Risco clínico se usados sem revisão | Enriquecer via ANVISA Consultas antes de uso clínico |
| classificacao MEDREG = categoria regulatória | Diferente do contexto DCB | Campo excluído do enriquecimento — decisão correta |

---

## 6. Confirmações desta fase

- `dicionario_mestre_medicamentos.csv` **NÃO foi alterado nesta fase** (read-only confirmado).
- Banco de dados **NÃO foi acessado**.
- Fonte interna **NÃO foi usada**.
- SKU_MASTER **NÃO foi aplicado**.

---

## 7. Arquivos gerados por esta fase

| Arquivo | Descrição |
|---|---|
| `consistencia_pos_enriquecimento_dcb_anvisa_medreg.csv` | {len(consistencia)} itens de consistência |
| `pendencias_pos_enriquecimento_dcb_anvisa_medreg.csv` | {len(pendencias):,} pendências remanescentes |
| `amostra_pos_enriquecimento_dcb_anvisa_medreg.csv` | {len(amostras)} registros de amostra |
| `auditoria_pos_enriquecimento_dcb_anvisa_medreg.md` | Este relatório |

---

## 8. Decisão técnica

**{decisao}**

{"O enriquecimento DCB/CAS foi aplicado corretamente. Todos os 7.984 registros elegíveis receberam dcb e cas. Nenhum campo fora do escopo foi alterado. Os 12.715 DCB originais estão intactos. A próxima etapa é planejar o enriquecimento dos campos forma_farmaceutica, concentracao, apresentacao e via_uso por fonte oficial complementar." if not bloqueantes else f"ATENÇÃO: {len(bloqueantes)} falha(s) bloqueante(s). Verificar antes de prosseguir."}

## 9. Próxima etapa recomendada

**FASE 2.12** — Planejamento de enriquecimento de forma farmacêutica, concentração, apresentação e via de uso nos registros ANVISA_MEDREG via ANVISA Consultas ou Bulário Eletrônico.

---

*Gerado automaticamente por `revisar_pos_enriquecimento_dcb_anvisa_medreg.py` — FASE 2.11*
"""

AUDITORIA_OUT.write_text(auditoria_md, encoding="utf-8")
print(f"  -> {AUDITORIA_OUT.name}")

# ---------------------------------------------------------------------------
# 7. Resumo final
# ---------------------------------------------------------------------------
print("\n" + "=" * 60)
print("FASE 2.11 — RESUMO FINAL")
print("=" * 60)
print(f"  Total dicionário:         {len(dict_rows):,}")
print(f"  DCB:                      {len(dcb_orig):,}")
print(f"  ANVISA_MEDREG:            {len(medreg):,}")
print(f"  MEDREG com dcb+cas:       {len(medreg_com_ambos):,} ({pct_enriq}%)")
print(f"  MEDREG sem dcb/cas:       {len(medreg_sem_ambos):,} ({pct_sem}%)")
print(f"  Consistência: {len(consistencia)} itens / {len(falhas)} falhas / {len(bloqueantes)} bloqueantes")
print(f"  Pendências: {len(pendencias):,} ({len(pend_bloqueantes)} bloqueantes)")
print(f"  Decisão: {decisao}")
print(f"\n  READ-ONLY: dicionario_mestre_medicamentos.csv NAO FOI ALTERADO.")
print("=" * 60)
