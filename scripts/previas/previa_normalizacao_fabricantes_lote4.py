import sqlite3
import csv
from pathlib import Path
from collections import Counter
from datetime import datetime

DB = Path("banco/medbox_v3.db")
REL = Path("previa_normalizacao_fabricantes_lote4.txt")
CSV = Path("previa_normalizacao_fabricantes_lote4.csv")

mapeamento = {
    "ASPEN PHARMA INDUSTRIA FAR": "ASPEN PHARMA",
    "ASTELLAS FARMA BRASIL IMP. E": "ASTELLAS",
    "BEAUFOUR IPSEN FARMACEUTIC": "IPSEN",
    "LABORATORIOS PIERRE FABRE D": "PIERRE FABRE",
    "LABORATORIOS BAGO DO BRAS": "BAGO",
    "MOKSHA8 BRASIL INDUSTRIA E": "MOKSHA8",
    "COPELI COSMETICOS E PERFUM": "COPELI",
    "TRUST - IMPORTACAO E EXPORT": "TRUST",
    "GERMED - OL": "GERMED",
    "BBRAUN": "B BRAUN",
}

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

amostras = []

for antigo, novo in mapeamento.items():
    rows = cur.execute("""
        SELECT id, produto_padrao, sku_master, fabricante, categoria, ativo
        FROM produtos
        WHERE fabricante = ?
        ORDER BY id
    """, (antigo,)).fetchall()

    for r in rows:
        amostras.append({
            "id": r["id"],
            "produto_padrao": r["produto_padrao"] or "",
            "sku_master": r["sku_master"] or "",
            "categoria": r["categoria"] or "",
            "ativo": r["ativo"],
            "fabricante_atual": antigo,
            "fabricante_sugerido": novo,
        })

with CSV.open("w", encoding="utf-8-sig", newline="") as f:
    campos = [
        "id", "produto_padrao", "sku_master", "categoria", "ativo",
        "fabricante_atual", "fabricante_sugerido"
    ]
    w = csv.DictWriter(f, fieldnames=campos, delimiter=";")
    w.writeheader()
    w.writerows(amostras)

contagem = Counter()
for x in amostras:
    contagem[(x["fabricante_atual"], x["fabricante_sugerido"])] += 1

linhas = []
linhas.append("===== PRÉVIA NORMALIZAÇÃO FABRICANTES - LOTE 4 =====")
linhas.append("")
linhas.append(f"Data/hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
linhas.append("")
linhas.append("Banco alterado: NÃO")
linhas.append("Aplicação automática: NÃO")
linhas.append("")
linhas.append(f"Total de registros candidatos: {len(amostras)}")
linhas.append("")
linhas.append("===== RESUMO POR NORMALIZAÇÃO =====")

for (antigo, novo), qtd in contagem.most_common():
    linhas.append(f"{antigo} -> {novo}: {qtd}")

linhas.append("")
linhas.append("===== AMOSTRA =====")
for x in amostras:
    linhas.append(
        f"ID {x['id']} | {x['fabricante_atual']} -> {x['fabricante_sugerido']} | "
        f"ATIVO {x['ativo']} | {x['produto_padrao']}"
    )

linhas.append("")
linhas.append("===== OBSERVAÇÃO =====")
linhas.append("Este lote é apenas prévia. Nenhum dado foi alterado.")
linhas.append("Não inclui marcas pequenas, nomes comerciais ou fabricantes sem confiança.")
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
