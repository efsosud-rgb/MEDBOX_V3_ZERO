"""
FASE 2.10 — Aplicação controlada do enriquecimento DCB/CAS nos registros ANVISA_MEDREG
Dual-mode: --dry-run (preview) / --apply --confirmar (escrita real)

Regras:
- Enriquece apenas dcb e cas (classificacao excluída — semânticas distintas).
- Apenas registros com acao_prevista=ENRIQUECER_PREVISTO e pode_aplicar=SIM.
- Nunca sobrescreve campo já preenchido.
- Cria backup antes da escrita em --apply.
- NÃO acessa banco. NÃO usa fonte interna.
"""

import csv
import shutil
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DICT_FILE = ROOT / "data/dicionario_mestre/dicionario_mestre_medicamentos.csv"
DRY_RUN_FILE = ROOT / "data/dicionario_mestre/processado/dry_run_enriquecimento_dcb_anvisa_medreg.csv"
BACKUP_DIR = ROOT / "backups/dicionario_mestre"
PROCESSADO = ROOT / "data/dicionario_mestre/processado"
CHECKLIST_OUT = PROCESSADO / "checklist_aplicacao_enriquecimento_dcb_anvisa_medreg.csv"

ENC = "utf-8-sig"
SEP = ";"
CAMPOS_ALVO = ["dcb", "cas"]


def uso():
    print("Uso:")
    print("  --dry-run                 Simula sem alterar o dicionário")
    print("  --apply --confirmar       Aplica o enriquecimento (cria backup primeiro)")
    sys.exit(1)


args = sys.argv[1:]
dry_run = "--dry-run" in args
apply_real = "--apply" in args and "--confirmar" in args

if not dry_run and not apply_real:
    uso()


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


modo = "DRY-RUN" if dry_run else "APPLY REAL"
print(f"\n{'='*60}")
print(f"FASE 2.10 — Enriquecimento DCB/CAS ANVISA_MEDREG — {modo}")
print(f"{'='*60}")

# ---------------------------------------------------------------------------
# 1. Carregar dados
# ---------------------------------------------------------------------------
print("\n[1] Carregando dados...")
dict_rows = ler_csv(DICT_FILE)
dict_size_antes = DICT_FILE.stat().st_size
print(f"    Dicionário: {len(dict_rows):,} registros ({dict_size_antes:,} bytes)")

dr_rows = ler_csv(DRY_RUN_FILE)
elegíveis = [r for r in dr_rows
             if vz(r, "acao_prevista") == "ENRIQUECER_PREVISTO"
             and vz(r, "pode_aplicar") == "SIM"]
print(f"    Dry-run: {len(dr_rows):,} registros | Elegíveis: {len(elegíveis):,}")

# Índice do dicionário por ID
dict_by_id = {vz(r, "id_dicionario"): r for r in dict_rows}
medreg_count = sum(1 for k in dict_by_id if k.startswith("ANVISA_MEDREG_"))
dcb_count = len(dict_by_id) - medreg_count
print(f"    MEDREG: {medreg_count:,}  |  DCB: {dcb_count:,}")

# ---------------------------------------------------------------------------
# 2. Construir mapa de enriquecimento
# ---------------------------------------------------------------------------
print("\n[2] Construindo mapa de enriquecimento...")

mapa = {}  # id_medreg → {campo: valor_novo}
conflitos_detectados = []
ja_preenchidos = []
ids_nao_encontrados = []

for d in elegíveis:
    id_m = vz(d, "id_medreg")
    row_m = dict_by_id.get(id_m)

    if not row_m:
        ids_nao_encontrados.append(id_m)
        continue

    campos_novo = {}
    for campo, col_novo in [("dcb", "dcb_novo"), ("cas", "cas_novo")]:
        atual = vz(row_m, campo)
        novo = vz(d, col_novo)

        if not novo:
            continue  # candidato sem valor — skip
        if atual and atual.lower() == novo.lower():
            ja_preenchidos.append((id_m, campo))
            continue  # já igual — skip
        if atual and atual.lower() != novo.lower():
            conflitos_detectados.append((id_m, campo, atual, novo))
            continue  # conflito — não aplicar
        # atual vazio e novo disponível → enriquecer
        campos_novo[campo] = novo

    if campos_novo:
        mapa[id_m] = campos_novo

n_registros_enriquecer = len(mapa)
n_campos_total = sum(len(v) for v in mapa.values())
n_dcb_a_preencher = sum(1 for v in mapa.values() if "dcb" in v)
n_cas_a_preencher = sum(1 for v in mapa.values() if "cas" in v)

print(f"    Registros a enriquecer: {n_registros_enriquecer:,}")
print(f"    Campos a preencher:     {n_campos_total:,} (dcb={n_dcb_a_preencher:,}, cas={n_cas_a_preencher:,})")
print(f"    Conflitos (ignorados):  {len(conflitos_detectados)}")
print(f"    Já preenchidos (skip):  {len(ja_preenchidos)}")
print(f"    IDs não encontrados:    {len(ids_nao_encontrados)}")

# ---------------------------------------------------------------------------
# 3. Checklist pré-apply
# ---------------------------------------------------------------------------
print("\n[3] Gerando checklist...")


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
checklist.append(chk("dicionario_existe", DICT_FILE.exists(), "existe", "existe", "SIM"))
checklist.append(chk("dry_run_existe", DRY_RUN_FILE.exists(), "existe", "existe", "SIM"))
checklist.append(chk("elegíveis_encontrados", len(elegíveis) == 7984, 7984, len(elegíveis), "SIM"))
checklist.append(chk("ids_nao_encontrados", len(ids_nao_encontrados) == 0, 0, len(ids_nao_encontrados), "SIM"))
checklist.append(chk("conflitos_em_campos_alvo", len(conflitos_detectados) == 0, 0, len(conflitos_detectados), "SIM"))
checklist.append(chk("registros_a_enriquecer", n_registros_enriquecer > 0, ">0", n_registros_enriquecer, "SIM"))
checklist.append(chk("campos_alvo_dcb_cas_apenas", True, "dcb,cas", "dcb,cas", "NAO",
                      "classificacao excluída: semântica diferente entre MEDREG e DCB"))
checklist.append(chk("nao_sobrescreve_preenchidos", len(conflitos_detectados) == 0, 0, len(conflitos_detectados), "SIM",
                      "nenhum campo com valor diferente seria sobrescrito"))
checklist.append(chk("banco_nao_alterado", True, "nao_acessado", "nao_acessado", "SIM"))
checklist.append(chk("fonte_interna_nao_usada", True, "nao_usada", "nao_usada", "SIM"))
checklist.append(chk("sku_master_nao_aplicado", True, "nao_aplicado", "nao_aplicado", "SIM"))
checklist.append(chk("apply_autorizado_pelo_responsavel",
                      apply_real,
                      "aprovacao_humana_recebida",
                      "aprovacao_humana_recebida" if apply_real else "nao_executado",
                      "NAO",
                      "dry-run: apply nao executado; apply: aprovacao recebida"))

CAMPOS_CK = ["item", "status", "esperado", "encontrado", "bloqueia_apply", "observacao"]
escrever_csv(CHECKLIST_OUT, CAMPOS_CK, checklist)

falhas = [c for c in checklist if c["status"] == "FALHA"]
bloqueantes = [c for c in checklist if c["bloqueia_apply"] == "SIM" and c["status"] == "FALHA"]

print(f"    {len(checklist)} itens | {len(falhas)} falhas | {len(bloqueantes)} bloqueantes")

if bloqueantes:
    print("\n[BLOQUEADO] Falhas bloqueantes detectadas:")
    for b in bloqueantes:
        print(f"  FALHA: {b['item']} — esperado={b['esperado']} / encontrado={b['encontrado']}")
    print("\nApply NÃO executado.")
    sys.exit(1)

# ---------------------------------------------------------------------------
# 4. Modo dry-run — mostrar preview e sair
# ---------------------------------------------------------------------------
if dry_run:
    print(f"\n[DRY-RUN] Preview de enriquecimento:")
    print(f"    {n_registros_enriquecer:,} registros receberiam enriquecimento")
    print(f"    {n_campos_total:,} campos seriam preenchidos")
    print(f"    dcb: {n_dcb_a_preencher:,}  |  cas: {n_cas_a_preencher:,}")
    print(f"\n    Amostra (5 primeiros):")
    for id_m, campos in list(mapa.items())[:5]:
        print(f"      {id_m}: {campos}")
    print("\n[DRY-RUN] Nenhuma alteração aplicada.")
    sys.exit(0)

# ---------------------------------------------------------------------------
# 5. APPLY REAL
# ---------------------------------------------------------------------------
print("\n[4] Criando backup antes da escrita...")
BACKUP_DIR.mkdir(parents=True, exist_ok=True)
ts = datetime.now().strftime("%Y%m%d_%H%M%S")
backup_path = BACKUP_DIR / f"dicionario_mestre_medicamentos_ANTES_ENRIQ_DCB_{ts}.csv"
shutil.copy2(DICT_FILE, backup_path)
backup_size = backup_path.stat().st_size
print(f"    Backup: {backup_path.name} ({backup_size:,} bytes)")

print("\n[5] Aplicando enriquecimento...")
n_aplicados = 0
n_campos_aplicados = 0

for r in dict_rows:
    id_d = vz(r, "id_dicionario")
    if id_d in mapa:
        for campo, valor_novo in mapa[id_d].items():
            if not vz(r, campo):  # só preenche se ainda vazio (segunda verificação de segurança)
                r[campo] = valor_novo
                n_campos_aplicados += 1
        n_aplicados += 1

print(f"    Registros modificados: {n_aplicados:,}")
print(f"    Campos preenchidos:    {n_campos_aplicados:,}")

print("\n[6] Escrevendo dicionário mestre atualizado...")
fieldnames = list(dict_rows[0].keys())
escrever_csv(DICT_FILE, fieldnames, dict_rows)

dict_size_depois = DICT_FILE.stat().st_size
print(f"    Bytes antes: {dict_size_antes:,}")
print(f"    Bytes depois:{dict_size_depois:,}")

# Verificação pós-escrita
print("\n[7] Verificação pós-escrita...")
dict_pos = ler_csv(DICT_FILE)
total_pos = len(dict_pos)
medreg_pos = [r for r in dict_pos if vz(r, "id_dicionario").startswith("ANVISA_MEDREG_")]
dcb_enriq = sum(1 for r in medreg_pos if vz(r, "dcb"))
cas_enriq = sum(1 for r in medreg_pos if vz(r, "cas"))
total_pos_medreg = len(medreg_pos)

print(f"    Total registros pós-apply: {total_pos:,} (esperado {len(dict_rows):,})")
print(f"    MEDREG com dcb preenchido: {dcb_enriq:,}")
print(f"    MEDREG com cas preenchido: {cas_enriq:,}")

# ---------------------------------------------------------------------------
# 6. Resumo final
# ---------------------------------------------------------------------------
print(f"\n{'='*60}")
print("FASE 2.10 — APPLY CONCLUÍDO")
print(f"{'='*60}")
print(f"  Registros enriquecidos: {n_aplicados:,}")
print(f"  Campos preenchidos:     {n_campos_aplicados:,}")
print(f"    dcb:                  {n_dcb_a_preencher:,}")
print(f"    cas:                  {n_cas_a_preencher:,}")
print(f"  Total dicionário:       {total_pos:,}")
print(f"  Backup:                 {backup_path.name}")
print(f"  Checklist:              {len(checklist)} itens / {len(falhas)} falhas / {len(bloqueantes)} bloqueantes")
print(f"{'='*60}")
