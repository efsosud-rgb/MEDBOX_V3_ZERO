import csv
from pathlib import Path

ORIGEM = Path("previa_regra_tubo_endotraqueal_c_balao_sem_material_APROVADOS_V2.csv")
DESTINO = Path("previa_regra_tubo_endotraqueal_c_cuff_sem_material_APROVADOS_V3.csv")
TXT = Path("relatorio_regra_tubo_c_cuff_sem_material_aprovados_v3.txt")

if not ORIGEM.exists():
    raise SystemExit("ERRO: CSV aprovado V2 não encontrado.")

with ORIGEM.open("r", encoding="utf-8-sig", newline="") as f:
    rows = list(csv.DictReader(f, delimiter=";"))
    campos = f.seek

for r in rows:
    if r.get("sku_master_sugerido"):
        r["sku_master_sugerido"] = r["sku_master_sugerido"].replace("C/BALAO", "C/CUFF")
    if r.get("regra_nome"):
        r["regra_nome"] = r["regra_nome"].replace("_C_BALAO_", "_C_CUFF_")

fieldnames = list(rows[0].keys()) if rows else []

with DESTINO.open("w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=fieldnames, delimiter=";")
    w.writeheader()
    w.writerows(rows)

linhas = []
linhas.append("===== APROVADOS V3 - PADRÃO C/CUFF =====")
linhas.append("")
linhas.append(f"Itens aprovados: {len(rows)}")
linhas.append("")
for r in rows:
    linhas.append(f"ID {r.get('produto_id')} | {r.get('descricao_atual')} | SUGERIDO: {r.get('sku_master_sugerido')}")
linhas.append("")
linhas.append(f"CSV V3: {DESTINO.resolve()}")
linhas.append("Banco alterado: NÃO")

TXT.write_text("\n".join(linhas), encoding="utf-8")

print("CSV V3:", DESTINO.resolve())
print("Relatório:", TXT.resolve())
print("Abra com:")
print("notepad relatorio_regra_tubo_c_cuff_sem_material_aprovados_v3.txt")
