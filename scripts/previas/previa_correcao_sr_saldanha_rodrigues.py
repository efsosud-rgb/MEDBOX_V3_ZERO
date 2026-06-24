import sqlite3
import csv
from pathlib import Path
from datetime import datetime

DB = Path("banco/medbox_v3.db")
REL = Path("previa_correcao_sr_saldanha_rodrigues.txt")
CSV = Path("previa_correcao_sr_saldanha_rodrigues.csv")

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

rows = cur.execute("""
SELECT id, produto_padrao, sku_master, fabricante, categoria, ativo, observacoes
FROM produtos
WHERE UPPER(TRIM(COALESCE(fabricante,''))) = 'SR'
ORDER BY id
""").fetchall()

saida = []

for r in rows:
    produto = str(r["produto_padrao"] or "").upper()
    sku = str(r["sku_master"] or "").upper()

    contexto_agulha = ("AGULHA" in produto) or ("AGULHA" in sku)
    contexto_seringa = ("SERINGA" in produto) or ("SERINGA" in sku)

    if contexto_agulha and not contexto_seringa:
        sugestao = "SALDANHA RODRIGUES"
        decisao = "SUGERIR_CORRECAO"
        motivo = "SR no campo fabricante; contexto é AGULHA, não SERINGA; provável SALDANHA RODRIGUES."
    else:
        sugestao = ""
        decisao = "REVISAR_MANUALMENTE"
        motivo = "SR ambíguo; contexto não permite decisão automática."

    saida.append({
        "id": r["id"],
        "produto_padrao": r["produto_padrao"] or "",
        "sku_master": r["sku_master"] or "",
        "fabricante_atual": r["fabricante"] or "",
        "fabricante_sugerido": sugestao,
        "categoria": r["categoria"] or "",
        "ativo": r["ativo"],
        "decisao": decisao,
        "motivo": motivo,
    })

with CSV.open("w", encoding="utf-8-sig", newline="") as f:
    campos = [
        "id",
        "produto_padrao",
        "sku_master",
        "fabricante_atual",
        "fabricante_sugerido",
        "categoria",
        "ativo",
        "decisao",
        "motivo",
    ]
    w = csv.DictWriter(f, fieldnames=campos, delimiter=";")
    w.writeheader()
    w.writerows(saida)

linhas = []
linhas.append("===== PRÉVIA CORREÇÃO SR =====")
linhas.append("")
linhas.append(f"Data/hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
linhas.append("")
linhas.append("Banco alterado: NÃO")
linhas.append("Fabricantes alterados: NÃO")
linhas.append("")
linhas.append("REGRA:")
linhas.append("SR é ambíguo.")
linhas.append("Se estiver no campo fabricante e o produto for AGULHA, sugerir SALDANHA RODRIGUES.")
linhas.append("Se o contexto for SERINGA ou inconclusivo, não aplicar.")
linhas.append("")
linhas.append(f"Total SR encontrados: {len(saida)}")
linhas.append(f"Sugeridos para SALDANHA RODRIGUES: {sum(1 for x in saida if x['decisao'] == 'SUGERIR_CORRECAO')}")
linhas.append(f"Revisão manual: {sum(1 for x in saida if x['decisao'] != 'SUGERIR_CORRECAO')}")
linhas.append("")
linhas.append("===== SUGESTÕES =====")

for x in saida:
    linhas.append("")
    linhas.append(f"ID: {x['id']}")
    linhas.append(f"Produto: {x['produto_padrao']}")
    linhas.append(f"SKU_MASTER: {x['sku_master']}")
    linhas.append(f"Fabricante atual: {x['fabricante_atual']}")
    linhas.append(f"Fabricante sugerido: {x['fabricante_sugerido']}")
    linhas.append(f"Ativo: {x['ativo']}")
    linhas.append(f"Decisão: {x['decisao']}")
    linhas.append(f"Motivo: {x['motivo']}")

linhas.append("")
linhas.append(f"CSV gerado: {CSV.resolve()}")
linhas.append("")
linhas.append("VEREDITO:")
linhas.append("PREVIA_GERADA_SEM_ALTERAR_BANCO")

REL.write_text("\n".join(linhas), encoding="utf-8")
conn.close()

print("\n".join(linhas))
print("")
print("Relatório:", REL.resolve())
