import csv
from pathlib import Path

CSV_ORIGEM = Path("previa_regra_tubo_endotraqueal_c_balao_sem_material.csv")
CSV_APROVADOS = Path("previa_regra_tubo_endotraqueal_c_balao_sem_material_APROVADOS_V2.csv")
TXT = Path("relatorio_regra_tubo_sem_material_aprovados_v2.txt")

if not CSV_ORIGEM.exists():
    raise SystemExit("ERRO: CSV de origem não encontrado.")

with CSV_ORIGEM.open("r", encoding="utf-8-sig", newline="") as f:
    rows = list(csv.DictReader(f, delimiter=";"))

bloqueios = [
    "ARAMADO",
    "REFORCADO",
    "REFORÇADO",
    "FLEXOMETALICO",
    "FLEXO METALICO",
    "FLEXO-METALICO",
]

aprovados = []
bloqueados = []

for r in rows:
    if (r.get("aplica") or "").upper() != "SIM":
        continue

    desc = (r.get("descricao_atual") or "").upper()

    if any(b in desc for b in bloqueios):
        r["motivo_bloqueio_v2"] = "BLOQUEADO_AROMADO_REFORCADO_FLEXOMETALICO_REGRA_PROPRIA"
        bloqueados.append(r)
    else:
        aprovados.append(r)

with CSV_APROVADOS.open("w", newline="", encoding="utf-8-sig") as f:
    campos = list(rows[0].keys()) if rows else []
    w = csv.DictWriter(f, fieldnames=campos, delimiter=";")
    w.writeheader()
    w.writerows(aprovados)

linhas = []
linhas.append("===== APROVADOS V2 - REGRA TUBO ENDOTRAQUEAL C/BALAO SEM MATERIAL =====")
linhas.append("")
linhas.append(f"Itens aplicáveis no CSV original: {len(aprovados) + len(bloqueados)}")
linhas.append(f"Aprovados V2: {len(aprovados)}")
linhas.append(f"Bloqueados V2: {len(bloqueados)}")
linhas.append("")
linhas.append("===== BLOQUEADOS V2 =====")
for r in bloqueados:
    linhas.append(
        f"ID {r.get('produto_id')} | {r.get('descricao_atual')} | "
        f"SUGERIDO ORIGINAL: {r.get('sku_master_sugerido')}"
    )

linhas.append("")
linhas.append("===== APROVADOS V2 =====")
for r in aprovados:
    linhas.append(
        f"ID {r.get('produto_id')} | {r.get('descricao_atual')} | "
        f"SUGERIDO: {r.get('sku_master_sugerido')}"
    )

linhas.append("")
linhas.append(f"CSV aprovados: {CSV_APROVADOS.resolve()}")
linhas.append("")
linhas.append("Banco alterado: NÃO")
linhas.append("Aplicação automática: NÃO")

TXT.write_text("\n".join(linhas), encoding="utf-8")

print("Relatório:", TXT.resolve())
print("CSV aprovados:", CSV_APROVADOS.resolve())
print("Abra com:")
print("notepad relatorio_regra_tubo_sem_material_aprovados_v2.txt")
