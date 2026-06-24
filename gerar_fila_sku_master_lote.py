import sqlite3
import csv
import re
from pathlib import Path
from collections import defaultdict, Counter

DB = Path("banco/medbox_v3.db")
SAIDA = Path("fila_sku_master_lote.csv")
RELATORIO = Path("relatorio_fila_sku_master_lote.txt")

def normalizar(txt):
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
    txt = re.sub(r"[^A-Z0-9%/,.\-+ ]+", " ", txt)
    txt = re.sub(r"\s+", " ", txt).strip()
    return txt

def limpar_base(desc):
    desc = normalizar(desc)

    desc = desc.replace("SKU PENDENTE -", "")
    desc = desc.replace("SKU PENDENTE", "")

    remover = [
        "ADULTO", "INFANTIL", "PEDIATRICO", "GENERICO", "GENÉRICO",
        "MARCA", "MANIPULADO", "IMPORTADO", "VIA ORAL",
        "UNIDADE", "UND", "UN",
    ]

    partes = []
    for p in desc.split():
        if p not in remover:
            partes.append(p)

    return " ".join(partes).strip()

def chave_familia(desc):
    desc = limpar_base(desc)

    # Mantém mais termos para evitar misturar produtos muito diferentes.
    return " ".join(desc.split()[:7])

def extrair_alertas(desc):
    d = normalizar(desc)
    alertas = []

    if re.search(r"\bN[º°]?\s*\d+", d) or re.search(r"\bN\s*\d+", d):
        alertas.append("TEM_NUMERO")
    if re.search(r"\d+\s*(FR|FRS|CM|MM|ML|MG|G|UI|FR)", d):
        alertas.append("TEM_MEDIDA")
    if "REF" in d:
        alertas.append("TEM_REFERENCIA")
    if "COM BALAO" in d or "SEM BALAO" in d or "C/ BALAO" in d or "S/ BALAO" in d:
        alertas.append("VARIA_BALAO")
    if "LATEX" in d or "SILICONE" in d:
        alertas.append("VARIA_MATERIAL")
    if "SKU PENDENTE" in d:
        alertas.append("OCR_PENDENTE")

    return ",".join(alertas)

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

rows = cur.execute("""
    SELECT
        id,
        sku,
        produto_padrao,
        sku_master,
        fabricante,
        categoria,
        ativo
    FROM produtos
    WHERE ativo = 1
    ORDER BY produto_padrao
""").fetchall()

# Índice de SKU_MASTER já existentes por descrição normalizada
sku_existentes = defaultdict(list)

for r in rows:
    sku_master = str(r["sku_master"] or "").strip()
    produto = str(r["produto_padrao"] or r["sku"] or "").strip()

    if sku_master:
        sku_existentes[limpar_base(produto)].append(sku_master)
        sku_existentes[limpar_base(sku_master)].append(sku_master)

sem_sku = []

for r in rows:
    sku_master = str(r["sku_master"] or "").strip()
    produto = str(r["produto_padrao"] or r["sku"] or "").strip()

    if not sku_master and produto:
        sem_sku.append(r)

grupos = defaultdict(list)

for r in sem_sku:
    produto = str(r["produto_padrao"] or r["sku"] or "").strip()
    grupos[chave_familia(produto)].append(r)

linhas_csv = []
resumo = Counter()

for grupo, itens in grupos.items():
    if len(itens) < 2:
        continue

    categorias = Counter(str(i["categoria"] or "SEM CATEGORIA") for i in itens)
    fabricantes = Counter(str(i["fabricante"] or "") for i in itens)

    amostras = [str(i["produto_padrao"] or i["sku"] or "") for i in itens[:8]]
    ids = [str(i["id"]) for i in itens]

    sugestoes = []
    for item in itens:
        produto = str(item["produto_padrao"] or item["sku"] or "")
        chave = limpar_base(produto)
        sugestoes.extend(sku_existentes.get(chave, []))

    if sugestoes:
        sugestao = Counter(sugestoes).most_common(1)[0][0]
        confianca = "ALTA_EXATA"
        acao = "PODE_APLICAR_APOS_CONFERIR"
    else:
        sugestao = grupo
        confianca = "MEDIA_GRUPO"
        acao = "CONFERIR_ANTES_DE_APLICAR"

    alertas = set()
    for a in amostras:
        for alerta in extrair_alertas(a).split(","):
            if alerta:
                alertas.add(alerta)

    if alertas:
        acao = "CONFERIR_COM_CUIDADO"
        if "OCR_PENDENTE" in alertas:
            confianca = "BAIXA_OCR"

    resumo[confianca] += 1

    linhas_csv.append({
        "grupo_provavel": grupo,
        "quantidade_itens": len(itens),
        "sku_master_sugerido": sugestao,
        "confianca": confianca,
        "acao_recomendada": acao,
        "categoria_mais_comum": categorias.most_common(1)[0][0] if categorias else "",
        "fabricante_mais_comum": fabricantes.most_common(1)[0][0] if fabricantes else "",
        "alertas": ",".join(sorted(alertas)),
        "ids_produtos": ";".join(ids),
        "amostras": " || ".join(amostras),
    })

linhas_csv.sort(
    key=lambda x: (
        {"ALTA_EXATA": 0, "MEDIA_GRUPO": 1, "BAIXA_OCR": 2}.get(x["confianca"], 9),
        -int(x["quantidade_itens"])
    )
)

with SAIDA.open("w", newline="", encoding="utf-8-sig") as f:
    campos = [
        "grupo_provavel",
        "quantidade_itens",
        "sku_master_sugerido",
        "confianca",
        "acao_recomendada",
        "categoria_mais_comum",
        "fabricante_mais_comum",
        "alertas",
        "ids_produtos",
        "amostras",
    ]
    writer = csv.DictWriter(f, fieldnames=campos, delimiter=";")
    writer.writeheader()
    writer.writerows(linhas_csv)

linhas_rel = []
linhas_rel.append("===== FILA SKU_MASTER EM LOTE =====")
linhas_rel.append("")
linhas_rel.append(f"Produtos ativos: {len(rows)}")
linhas_rel.append(f"Sem SKU_MASTER: {len(sem_sku)}")
linhas_rel.append(f"Grupos gerados para análise: {len(linhas_csv)}")
linhas_rel.append("")
linhas_rel.append("===== POR CONFIANÇA =====")
for k, v in resumo.most_common():
    linhas_rel.append(f"{k}: {v}")
linhas_rel.append("")
linhas_rel.append(f"Arquivo CSV gerado: {SAIDA.resolve()}")
linhas_rel.append("")
linhas_rel.append("Abra no Excel e revise principalmente os grupos com:")
linhas_rel.append("- BAIXA_OCR")
linhas_rel.append("- TEM_NUMERO")
linhas_rel.append("- TEM_MEDIDA")
linhas_rel.append("- TEM_REFERENCIA")
linhas_rel.append("- VARIA_BALAO")
linhas_rel.append("- VARIA_MATERIAL")

RELATORIO.write_text("\n".join(linhas_rel), encoding="utf-8")

conn.close()

print("CSV gerado:", SAIDA.resolve())
print("Relatório gerado:", RELATORIO.resolve())
print("Abra o relatório com:")
print("notepad relatorio_fila_sku_master_lote.txt")
