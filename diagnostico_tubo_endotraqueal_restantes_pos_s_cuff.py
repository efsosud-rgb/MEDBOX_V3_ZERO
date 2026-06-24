import sqlite3
from pathlib import Path
from collections import Counter

DB = Path("banco/medbox_v3.db")
TXT = Path("diagnostico_tubo_endotraqueal_restantes_pos_s_cuff.txt")

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

rows = cur.execute("""
SELECT id, produto_padrao, sku_master, categoria
FROM produtos
WHERE ativo = 1
  AND (
      UPPER(COALESCE(produto_padrao,'')) LIKE '%TUBO ENDOTRAQUEAL%'
      OR UPPER(COALESCE(produto_padrao,'')) LIKE '%TUBO OROTRAQUEAL%'
      OR UPPER(COALESCE(sku_master,'')) LIKE '%TUBO ENDOTRAQUEAL%'
      OR UPPER(COALESCE(sku_master,'')) LIKE '%TUBO OROTRAQUEAL%'
  )
ORDER BY id
""").fetchall()

def cls(desc, sku):
    t = (str(desc or '') + ' ' + str(sku or '')).upper()

    if 'FIXADOR' in t:
        return 'FIXADOR'
    if 'SISTEMA DE ASP' in t or 'ASP. FECHADO' in t or 'TRACK CARE' in t:
        return 'SISTEMA ASPIRACAO FECHADO'
    if 'COM ASPIRACAO' in t:
        return 'TUBO ENDOTRAQUEAL COM ASPIRACAO'
    if 'ARAMADO' in t:
        if 'SEM' in t or 'S/CUFF' in t or 'S/BALAO' in t:
            return 'TUBO ENDOTRAQUEAL ARAMADO S/CUFF'
        return 'TUBO ENDOTRAQUEAL ARAMADO C/CUFF'
    if 'S/CUFF' in t or 'SEM BALAO' in t or 'SEM CUFF' in t or 'SEM BALONETE' in t or 'S/BALAO' in t:
        return 'TUBO ENDOTRAQUEAL S/CUFF'
    if 'C/CUFF' in t or 'COM BALAO' in t or 'COM CUFF' in t or 'COM BALONETE' in t or 'C/BALAO' in t:
        return 'TUBO ENDOTRAQUEAL C/CUFF'
    return 'INCOMPLETO / REVISAR'

cont = Counter()
grupos = {}

for r in rows:
    grupo = cls(r['produto_padrao'], r['sku_master'])
    cont[grupo] += 1
    grupos.setdefault(grupo, []).append(r)

linhas = []
linhas.append("===== DIAGNÓSTICO RESTANTE - TUBO ENDOTRAQUEAL / OROTRAQUEAL =====")
linhas.append("")
linhas.append(f"Total analisado: {len(rows)}")
linhas.append("")
linhas.append("===== CONTAGEM POR GRUPO =====")

for grupo, total in cont.most_common():
    linhas.append(f"{grupo}: {total}")

linhas.append("")
linhas.append("===== ITENS POR GRUPO =====")

for grupo, itens in sorted(grupos.items()):
    linhas.append("")
    linhas.append(f"--- {grupo} | total: {len(itens)} ---")
    for r in itens[:80]:
        linhas.append(
            f"ID {r['id']} | {r['produto_padrao']} | SKU atual: {r['sku_master'] or ''} | CAT: {r['categoria'] or ''}"
        )

TXT.write_text("\n".join(linhas), encoding="utf-8")
conn.close()

print("Relatório gerado:", TXT.resolve())
print("Abra com:")
print("notepad diagnostico_tubo_endotraqueal_restantes_pos_s_cuff.txt")
