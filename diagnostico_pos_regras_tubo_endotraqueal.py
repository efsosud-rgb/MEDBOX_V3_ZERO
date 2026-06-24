import sqlite3
from pathlib import Path
from collections import Counter

DB = Path("banco/medbox_v3.db")
TXT = Path("diagnostico_pos_regras_tubo_endotraqueal.txt")

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

linhas = []
linhas.append("===== DIAGNÓSTICO PÓS-REGRAS TUBO ENDOTRAQUEAL =====")
linhas.append("")

consultas = {
    "TUBO ENDOTRAQUEAL C/CUFF": """
        SELECT COUNT(*) total
        FROM produtos
        WHERE UPPER(COALESCE(sku_master,'')) LIKE 'TUBO ENDOTRAQUEAL C/CUFF%'
    """,
    "TUBO ENDOTRAQUEAL C/CUFF PVC": """
        SELECT COUNT(*) total
        FROM produtos
        WHERE UPPER(COALESCE(sku_master,'')) LIKE 'TUBO ENDOTRAQUEAL C/CUFF PVC%'
    """,
    "Ainda com C/BALAO": """
        SELECT COUNT(*) total
        FROM produtos
        WHERE UPPER(COALESCE(sku_master,'')) LIKE 'TUBO ENDOTRAQUEAL C/BALAO%'
    """,
    "TUBO ENDOTRAQUEAL S/CUFF": """
        SELECT COUNT(*) total
        FROM produtos
        WHERE UPPER(COALESCE(sku_master,'')) LIKE 'TUBO ENDOTRAQUEAL S/CUFF%'
    """,
    "TUBO ENDOTRAQUEAL ARAMADO": """
        SELECT COUNT(*) total
        FROM produtos
        WHERE UPPER(COALESCE(produto_padrao,'')) LIKE '%TUBO ENDOTRAQUEAL ARAMADO%'
           OR UPPER(COALESCE(sku_master,'')) LIKE '%TUBO ENDOTRAQUEAL ARAMADO%'
    """,
}

for nome, sql in consultas.items():
    total = cur.execute(sql).fetchone()["total"]
    linhas.append(f"{nome}: {total}")

linhas.append("")
linhas.append("===== ITENS AINDA COM C/BALAO NO SKU_MASTER =====")

rows = cur.execute("""
    SELECT id, produto_padrao, sku_master, categoria
    FROM produtos
    WHERE UPPER(COALESCE(sku_master,'')) LIKE 'TUBO ENDOTRAQUEAL C/BALAO%'
    ORDER BY id
""").fetchall()

if not rows:
    linhas.append("Nenhum.")
else:
    for r in rows:
        linhas.append(f"ID {r['id']} | {r['produto_padrao']} | SKU: {r['sku_master']} | CAT: {r['categoria']}")

linhas.append("")
linhas.append("===== TUBOS ENDOTRAQUEAIS SEM SKU_MASTER PADRONIZADO =====")

rows = cur.execute("""
    SELECT id, produto_padrao, sku_master, categoria
    FROM produtos
    WHERE ativo = 1
      AND (
            UPPER(COALESCE(produto_padrao,'')) LIKE '%TUBO ENDOTRAQUEAL%'
         OR UPPER(COALESCE(produto_padrao,'')) LIKE '%TUBO OROTRAQUEAL%'
      )
      AND (
            sku_master IS NULL
         OR TRIM(sku_master) = ''
         OR UPPER(TRIM(sku_master)) LIKE 'SKU PENDENTE%'
         OR UPPER(TRIM(sku_master)) = UPPER(TRIM(produto_padrao))
      )
    ORDER BY id
""").fetchall()

linhas.append(f"Total pendentes: {len(rows)}")
for r in rows[:80]:
    linhas.append(f"ID {r['id']} | {r['produto_padrao']} | SKU atual: {r['sku_master'] or ''}")

TXT.write_text("\n".join(linhas), encoding="utf-8")
conn.close()

print("Relatório gerado:", TXT.resolve())
print("Abra com:")
print("notepad diagnostico_pos_regras_tubo_endotraqueal.txt")
