import sqlite3
from pathlib import Path

DB = Path("banco/medbox_v3.db")
REL = Path("produtos_com_fabricante_fr.txt")

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

rows = cur.execute("""
SELECT
    id,
    produto_padrao,
    sku_master,
    fabricante,
    categoria,
    ativo,
    observacoes
FROM produtos
WHERE UPPER(TRIM(COALESCE(fabricante, ''))) = 'FR'
ORDER BY id
""").fetchall()

linhas = []
linhas.append("===== PRODUTOS COM FABRICANTE = FR =====")
linhas.append("")
linhas.append(f"Total encontrado: {len(rows)}")
linhas.append("")

for r in rows:
    linhas.append(f"ID: {r['id']}")
    linhas.append(f"Descrição completa / produto_padrao: {r['produto_padrao'] or ''}")
    linhas.append(f"SKU_MASTER: {r['sku_master'] or ''}")
    linhas.append(f"Fabricante atual: {r['fabricante'] or ''}")
    linhas.append(f"Categoria: {r['categoria'] or ''}")
    linhas.append(f"Ativo: {r['ativo']}")
    linhas.append(f"Observações: {r['observacoes'] or ''}")
    linhas.append("-" * 100)

REL.write_text("\n".join(linhas), encoding="utf-8")
conn.close()

print("Relatório:", REL.resolve())
print("Abra com:")
print("notepad produtos_com_fabricante_fr.txt")
