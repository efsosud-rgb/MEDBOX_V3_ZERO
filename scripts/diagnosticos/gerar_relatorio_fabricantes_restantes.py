import sqlite3
import csv
from pathlib import Path
from datetime import datetime

DB = Path("banco/medbox_v3.db")
REL = Path("relatorio_fabricantes_restantes.txt")
CSV = Path("relatorio_fabricantes_restantes.csv")

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

rows = cur.execute("""
SELECT
    fabricante,
    COUNT(*) AS qtd
FROM produtos
WHERE fabricante IS NOT NULL
  AND TRIM(fabricante) <> ''
GROUP BY fabricante
ORDER BY qtd DESC, fabricante
""").fetchall()

with CSV.open("w", encoding="utf-8-sig", newline="") as f:
    campos = ["fabricante", "qtd"]
    w = csv.DictWriter(f, fieldnames=campos, delimiter=";")
    w.writeheader()
    for r in rows:
        w.writerow({
            "fabricante": r["fabricante"],
            "qtd": r["qtd"],
        })

linhas = []
linhas.append("===== RELATÓRIO FABRICANTES RESTANTES =====")
linhas.append("")
linhas.append(f"Data/hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
linhas.append("")
linhas.append("Banco alterado: NÃO")
linhas.append("")
linhas.append(f"Total de fabricantes distintos: {len(rows)}")
linhas.append("")
linhas.append("===== FABRICANTES POR QUANTIDADE =====")

for r in rows:
    linhas.append(f"{r['fabricante']} | qtd={r['qtd']}")

linhas.append("")
linhas.append(f"CSV gerado: {CSV.resolve()}")

REL.write_text("\n".join(linhas), encoding="utf-8")
conn.close()

print("Relatório:", REL.resolve())
print("CSV:", CSV.resolve())
print("Abra com:")
print("notepad relatorio_fabricantes_restantes.txt")
