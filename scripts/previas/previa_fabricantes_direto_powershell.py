import sqlite3
import re
from pathlib import Path
from collections import Counter

DB = Path("banco/medbox_v3.db")

def norm(txt):
    txt = str(txt or "").upper().strip()
    mapa = {
        "Á":"A","À":"A","Ã":"A","Â":"A",
        "É":"E","Ê":"E",
        "Í":"I",
        "Ó":"O","Ô":"O","Õ":"O",
        "Ú":"U",
        "Ç":"C",
    }
    for a, b in mapa.items():
        txt = txt.replace(a, b)
    txt = re.sub(r"[^A-Z0-9 ]+", " ", txt)
    txt = re.sub(r"\s+", " ", txt).strip()
    return txt

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# Garante que FR não esteja ativo como alias de empresa
cur.execute("""
UPDATE dicionario_empresas_alias
SET ativo = 0
WHERE alias_normalizado = 'FR'
   OR alias_original = 'FR'
""")
conn.commit()

aliases_fr = cur.execute("""
SELECT COUNT(*) AS n
FROM dicionario_empresas_alias
WHERE ativo = 1
  AND (alias_normalizado = 'FR' OR alias_original = 'FR')
""").fetchone()["n"]

aliases = cur.execute("""
SELECT nome_canonico, alias_normalizado
FROM dicionario_empresas_alias
WHERE ativo = 1
ORDER BY LENGTH(alias_normalizado) DESC
""").fetchall()

def resumir(nome):
    original = str(nome or "").strip()
    n = norm(original)

    if not n or n == "FR":
        return original

    for a in aliases:
        an = a["alias_normalizado"]
        canonico = a["nome_canonico"]

        if not an:
            continue

        if len(an) <= 3:
            if n == an:
                return canonico
            continue

        if n == an:
            return canonico

        if re.search(r"(^| )" + re.escape(an) + r"( |$)", n):
            return canonico

    return original

rows = cur.execute("""
SELECT fabricante, COUNT(*) AS qtd
FROM produtos
WHERE fabricante IS NOT NULL
  AND TRIM(fabricante) <> ''
GROUP BY fabricante
ORDER BY qtd DESC, fabricante
""").fetchall()

amostras = []

for r in rows:
    antigo = r["fabricante"]
    novo = resumir(antigo)
    if novo and novo != antigo:
        amostras.append((antigo, novo, r["qtd"]))

contagem = Counter([x[1] for x in amostras])

print("===== PRÉVIA CORRIGIDA - FABRICANTES =====")
print("")
print("Aliases FR ativos como empresa:", aliases_fr)
print("Nomes com sugestão de resumo encontrados:", len(amostras))
print("")
print("===== CONTAGEM POR NOME RESUMIDO =====")
for nome, qtd in contagem.most_common():
    print(f"{nome}: {qtd} nomes/variações")

print("")
print("===== AMOSTRA DAS NORMALIZAÇÕES =====")
for antigo, novo, qtd in amostras[:80]:
    print(f"{antigo} -> {novo} | qtd={qtd}")

conn.close()
