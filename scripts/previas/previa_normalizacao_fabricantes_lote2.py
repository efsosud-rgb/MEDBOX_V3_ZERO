import sqlite3
import csv
from pathlib import Path
from collections import Counter
from datetime import datetime

DB = Path("banco/medbox_v3.db")
REL = Path("previa_normalizacao_fabricantes_lote2.txt")
CSV = Path("previa_normalizacao_fabricantes_lote2.csv")

# LOTE 2: somente equivalências óbvias.
# NÃO inclui siglas ambíguas: UN, U N, SR, RL, PR, PT, CX, FL, GL, KT, MT.
# NÃO inclui MEDIXLAB -> MEDIX ainda.
mapeamento = {
    "HALEX ISTAR": "HALEXISTAR",

    "PRATIDONADUZZI": "PRATI DONADUZZI",
    "PRATI, DONADUZZI E CIA LTDA": "PRATI DONADUZZI",

    "BIOLAB SANUS.": "BIOLAB SANUS",
    "BIOLAB": "BIOLAB SANUS",
    "BIOLAB SANUS FARMACEUTICA": "BIOLAB SANUS",

    "TRB PHARMA INDUSTRIA QUIM": "TRB PHARMA",
    "TRB": "TRB PHARMA",

    "RECKITT BENCKISER ( BRASIL ) L": "RECKITT BENCKISER",

    "NEO QUIMICA (BRAINFARMA)": "NEO QUIMICA",

    "SANOFI MEDLEY FARMACEUTIC": "SANOFI MEDLEY",
    "SANOFI-AVENTIS FARMACEUTIC": "SANOFI",

    "NOVARTIS BIOCIENCIAS SA": "NOVARTIS",
    "NOVARTIS BIOCIENCIAS S.A.": "NOVARTIS",

    "CSL BEHRING COMERCIO DE PR": "CSL BEHRING",
    "CSL": "CSL BEHRING",

    "ABBVIE FARMACEUTICA LTDA": "ABBVIE",
    "ABBVIE FARMACEUTICA LTDA.": "ABBVIE",

    "PFIZER BRASIL LTDA": "PFIZER",

    "UCB BIOPHARMA LTDA.": "UCB BIOPHARMA",

    "BAYER S.A.": "BAYER",

    "LIBBS FARMACEUTICA LTDA": "LIBBS",

    "SANDOZ DO BRASIL INDUSTRIA": "SANDOZ",

    "NOVO NORDISK FARMACEUTICA": "NOVO NORDISK",

    "ORGANON FARMACEUTICA LTD.": "ORGANON",

    "ZAMBON LABORATORIOS FARM": "ZAMBON",

    "CHIESI FARMACEUTICA LTDA": "CHIESI",

    "DR. REDDYS FARMACEUTICA DO": "DR REDDYS",

    "LABORATORIO CRISTALIA": "CRISTALIA",

    "MARK MED": "MARKMED",

    "MANDALA BRASIL": "MANDALA",

    "PHARMASCIENCE LABORATORIO": "PHARMASCIENCE",

    "ACHE LABORATORIOS FARMACE": "ACHE",

    "ASTRAZENECA DO BRASIL LTDA.": "ASTRAZENECA",

    "AMGEN BIOTECNOLOGIA DO BR": "AMGEN",

    "DAIICHI SANKYO BRASIL FARMA": "DAIICHI SANKYO",

    "BOEHRINGER": "BOEHRINGER INGELHEIM",
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
        "id",
        "produto_padrao",
        "sku_master",
        "categoria",
        "ativo",
        "fabricante_atual",
        "fabricante_sugerido",
    ]
    w = csv.DictWriter(f, fieldnames=campos, delimiter=";")
    w.writeheader()
    w.writerows(amostras)

contagem = Counter()
for x in amostras:
    contagem[(x["fabricante_atual"], x["fabricante_sugerido"])] += 1

linhas = []
linhas.append("===== PRÉVIA NORMALIZAÇÃO FABRICANTES - LOTE 2 =====")
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
for x in amostras[:120]:
    linhas.append(
        f"ID {x['id']} | {x['fabricante_atual']} -> {x['fabricante_sugerido']} | "
        f"ATIVO {x['ativo']} | {x['produto_padrao']}"
    )

linhas.append("")
linhas.append("===== NÃO INCLUÍDOS NESTE LOTE =====")
linhas.append("UN, U N, RL, PR, PT, CX, FL, GL, KT, MT: revisar como código/unidade/erro de importação.")
linhas.append("SR: já tratado por regra contextual; em AGULHA virou SALDANHA RODRIGUES.")
linhas.append("MEDIXLAB: revisar antes de decidir se vira MEDIX ou fica separado.")
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
