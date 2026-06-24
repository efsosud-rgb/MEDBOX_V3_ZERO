import sqlite3
import csv
from pathlib import Path
from datetime import datetime

DB = Path("banco/medbox_v3.db")
REL = Path("previa_correcao_fabricante_fr_fabricante_real.txt")
CSV = Path("previa_correcao_fabricante_fr_fabricante_real.csv")

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

saida = []

for r in rows:
    produto = str(r["produto_padrao"] or "").strip()
    sku = str(r["sku_master"] or "").strip()

    fabricante_sugerido = ""
    motivo = ""

    if produto and sku and produto.upper() == sku.upper():
        fabricante_sugerido = produto
        motivo = "FR=FABRICANTE_REAL; PRODUTO_PADRAO_IGUAL_SKU_MASTER_PARECE_MARCA/FABRICANTE"
    elif sku:
        fabricante_sugerido = sku
        motivo = "FR=FABRICANTE_REAL; SUGERIDO_SKU_MASTER_COMO_FABRICANTE"
    elif produto:
        fabricante_sugerido = produto
        motivo = "FR=FABRICANTE_REAL; SUGERIDO_PRODUTO_PADRAO_COMO_FABRICANTE"
    else:
        motivo = "SEM_SUGESTAO_SEGURA"

    saida.append({
        "id": r["id"],
        "produto_padrao": produto,
        "sku_master": sku,
        "fabricante_atual": r["fabricante"] or "",
        "flag_interpretada": "FABRICANTE_REAL",
        "fabricante_sugerido": fabricante_sugerido,
        "categoria": r["categoria"] or "",
        "ativo": r["ativo"],
        "motivo": motivo,
        "observacoes": r["observacoes"] or "",
    })

with CSV.open("w", encoding="utf-8-sig", newline="") as f:
    campos = [
        "id",
        "produto_padrao",
        "sku_master",
        "fabricante_atual",
        "flag_interpretada",
        "fabricante_sugerido",
        "categoria",
        "ativo",
        "motivo",
        "observacoes",
    ]
    w = csv.DictWriter(f, fieldnames=campos, delimiter=";")
    w.writeheader()
    w.writerows(saida)

linhas = []
linhas.append("===== PRÉVIA CORREÇÃO - FR COMO FABRICANTE REAL =====")
linhas.append("")
linhas.append(f"Data/hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
linhas.append("")
linhas.append("Banco alterado: NÃO")
linhas.append("Fabricantes alterados: NÃO")
linhas.append("")
linhas.append(f"Total produtos com fabricante = FR: {len(saida)}")
linhas.append("")
linhas.append("REGRA USADA:")
linhas.append("FR no campo fabricante significa FABRICANTE_REAL.")
linhas.append("FR não será tratado como nome de fabricante.")
linhas.append("FR não será normalizado como Fresenius.")
linhas.append("")
linhas.append("===== SUGESTÕES =====")

for x in saída if False else saida:
    linhas.append("")
    linhas.append(f"ID: {x['id']}")
    linhas.append(f"Produto padrão: {x['produto_padrao']}")
    linhas.append(f"SKU_MASTER: {x['sku_master']}")
    linhas.append(f"Fabricante atual: {x['fabricante_atual']}")
    linhas.append(f"Flag interpretada: {x['flag_interpretada']}")
    linhas.append(f"Fabricante sugerido: {x['fabricante_sugerido']}")
    linhas.append(f"Categoria: {x['categoria']}")
    linhas.append(f"Motivo: {x['motivo']}")

linhas.append("")
linhas.append(f"CSV gerado: {CSV.resolve()}")
linhas.append("")
linhas.append("VEREDITO:")
linhas.append("PREVIA_GERADA_SEM_ALTERAR_BANCO")

conteudo = "\n".join(linhas)
REL.write_text(conteudo, encoding="utf-8")
conn.close()

print(conteudo)
print("")
print("Relatório:", REL.resolve())
print("CSV:", CSV.resolve())
