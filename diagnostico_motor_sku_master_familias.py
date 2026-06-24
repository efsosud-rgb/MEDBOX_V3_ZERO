import sqlite3
import re
import csv
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime

DB = Path("banco/medbox_v3.db")

TXT = Path("diagnostico_motor_sku_master_familias.txt")
CSV_FAMILIAS = Path("diagnostico_motor_sku_master_familias.csv")
CSV_AMOSTRAS = Path("diagnostico_motor_sku_master_amostras.csv")

def sem_acento(txt):
    txt = str(txt or "")
    mapa = {
        "Á":"A","À":"A","Ã":"A","Â":"A","Ä":"A",
        "É":"E","Ê":"E","È":"E","Ë":"E",
        "Í":"I","Ì":"I","Î":"I","Ï":"I",
        "Ó":"O","Ô":"O","Õ":"O","Ò":"O","Ö":"O",
        "Ú":"U","Ù":"U","Û":"U","Ü":"U",
        "Ç":"C",
        "á":"a","à":"a","ã":"a","â":"a","ä":"a",
        "é":"e","ê":"e","è":"e","ë":"e",
        "í":"i","ì":"i","î":"i","ï":"i",
        "ó":"o","ô":"o","õ":"o","ò":"o","ö":"o",
        "ú":"u","ù":"u","û":"u","ü":"u",
        "ç":"c",
    }
    for a, b in mapa.items():
        txt = txt.replace(a, b)
    return txt

def norm(txt):
    txt = sem_acento(txt).upper()
    txt = txt.replace("\\", "/")
    txt = txt.replace("N°", "N ")
    txt = txt.replace("Nº", "N ")
    txt = txt.replace("NO ", "N ")
    txt = txt.replace("NUMERO", "N ")
    txt = txt.replace("C/", " COM ")
    txt = txt.replace("S/", " SEM ")
    txt = txt.replace("BALAO", "CUFF")
    txt = txt.replace("BALONETE", "CUFF")
    txt = txt.replace("OROTRAQUEAL", "ENDOTRAQUEAL")
    txt = txt.replace("ORO TRAQUEAL", "ENDOTRAQUEAL")
    txt = txt.replace("POLIVINIL", "PVC")
    txt = txt.replace("POLI VINIL", "PVC")
    txt = txt.replace("CLORETO DE POLIVINILA", "PVC")
    txt = re.sub(r"[^A-Z0-9,.\-/+% ]+", " ", txt)
    txt = re.sub(r"\s+", " ", txt).strip()
    return txt

def detectar_familia(desc):
    t = norm(desc)

    regras = [
        ("TUBO ENDOTRAQUEAL", ["TUBO ENDOTRAQUEAL", "CANULA ENDOTRAQUEAL"]),
        ("FIXADOR TUBO ENDOTRAQUEAL", ["FIXADOR", "TUBO ENDOTRAQUEAL"]),
        ("SISTEMA ASPIRACAO FECHADO", ["SISTEMA DE ASP", "TUBO ENDOTRAQUEAL"]),
        ("SERINGA", ["SERINGA"]),
        ("AGULHA HIPODERMICA", ["AGULHA"]),
        ("EQUIPO", ["EQUIPO"]),
        ("SONDA FOLEY", ["SONDA", "FOLEY"]),
        ("SONDA ASPIRACAO", ["SONDA", "ASPIRACAO"]),
        ("CATETER", ["CATETER"]),
        ("SCALP", ["SCALP"]),
        ("LUVA", ["LUVA"]),
        ("MASCARA", ["MASCARA"]),
        ("GAZE", ["GAZE"]),
        ("COMPRESSA", ["COMPRESSA"]),
        ("ATADURA", ["ATADURA"]),
        ("ALGODAO", ["ALGODAO"]),
        ("SORO", ["SORO"]),
        ("CLORETO DE SODIO", ["CLORETO DE SODIO"]),
        ("GLICOSE", ["GLICOSE"]),
        ("DIPIRONA", ["DIPIRONA"]),
        ("PARACETAMOL", ["PARACETAMOL"]),
        ("IBUPROFENO", ["IBUPROFENO"]),
        ("ONDANSETRONA", ["ONDANSETRONA"]),
        ("ENOXAPARINA", ["ENOXAPARINA"]),
        ("LIDOCAINA", ["LIDOCAINA"]),
        ("CEFTRIAXONA", ["CEFTRIAXONA"]),
        ("OMEPRAZOL", ["OMEPRAZOL"]),
        ("DEXAMETASONA", ["DEXAMETASONA"]),
        ("HIDROCORTISONA", ["HIDROCORTISONA"]),
        ("FRALDA", ["FRALDA"]),
        ("BOLSA COLETORA", ["BOLSA", "COLETORA"]),
        ("CURATIVO", ["CURATIVO"]),
    ]

    # Regras compostas primeiro.
    if "FIXADOR" in t and "ENDOTRAQUEAL" in t:
        return "FIXADOR TUBO ENDOTRAQUEAL"

    if ("SISTEMA DE ASP" in t or "ASP FECHADO" in t or "TRACK CARE" in t):
        return "SISTEMA ASPIRACAO FECHADO"

    if "ENDOTRAQUEAL" in t:
        return "TUBO ENDOTRAQUEAL"

    for familia, termos in regras:
        if all(x in t for x in termos):
            return familia

    # fallback: primeira palavra técnica útil
    palavras_ruins = {
        "SKU", "PENDENTE", "DE", "DA", "DO", "DAS", "DOS", "COM", "SEM", "PARA",
        "UN", "UND", "CX", "CAIXA", "FR", "FRASCO", "AMP", "ITEM", "ADULTO",
        "INFANTIL", "PEDIATRICO", "MARCA"
    }

    palavras = [p for p in re.split(r"\s+", t) if len(p) >= 4 and p not in palavras_ruins]
    if palavras:
        return "OUTROS - " + palavras[0]

    return "INDEFINIDO"

def extrair_atributos_basicos(desc):
    t = norm(desc)
    attrs = {}

    # Medida genérica
    medidas = re.findall(r"\b\d+(?:[,.]\d+)?\s*(?:MM|CM|ML|MG|G|MCG|UI|L)\b", t)
    if medidas:
        attrs["medidas"] = "|".join(medidas[:5])

    # Volume/dosagem
    doses = re.findall(r"\b\d+(?:[,.]\d+)?\s*(?:MG/ML|MG|MCG|UI|ML|G)\b", t)
    if doses:
        attrs["dose_volume"] = "|".join(doses[:5])

    # Cuff
    if "COM CUFF" in t:
        attrs["cuff"] = "C/CUFF"
    elif "SEM CUFF" in t:
        attrs["cuff"] = "S/CUFF"

    # Outras características
    for chave, termo in [
        ("aramado", "ARAMADO"),
        ("aspiracao", "ASPIRACAO"),
        ("fixador", "FIXADOR"),
        ("esteril", "ESTERIL"),
        ("latex", "LATEX"),
        ("silicone", "SILICONE"),
        ("pvc", "PVC"),
        ("duas_vias", "2 VIAS"),
        ("tres_vias", "3 VIAS"),
    ]:
        if termo in t:
            attrs[chave] = "SIM"

    return attrs

def sku_status(sku_master, produto_padrao):
    sku = str(sku_master or "").strip()
    prod = str(produto_padrao or "").strip()

    if not sku:
        return "VAZIO"
    if sku.upper().startswith("SKU PENDENTE"):
        return "SKU PENDENTE"
    if sku.upper() == prod.upper():
        return "IGUAL_DESCRICAO"
    return "PREENCHIDO"

def assinatura_tecnica(familia, attrs):
    partes = [familia]
    for k in sorted(attrs):
        if k in {"pvc", "esteril"}:
            # neste diagnóstico, atributos comuns ficam fora da assinatura forte
            continue
        partes.append(f"{k}={attrs[k]}")
    return " | ".join(partes)

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

cols_produtos = [r["name"] for r in cur.execute("PRAGMA table_info(produtos)").fetchall()]

campos = ["id"]
for c in ["sku", "produto_padrao", "sku_master", "fabricante", "categoria", "ativo"]:
    if c in cols_produtos:
        campos.append(c)

sql = f"""
SELECT {", ".join(campos)}
FROM produtos
WHERE COALESCE(ativo, 1) = 1
ORDER BY id
"""

rows = cur.execute(sql).fetchall()

familias = defaultdict(list)
assinaturas = defaultdict(list)

for r in rows:
    produto_padrao = r["produto_padrao"] if "produto_padrao" in r.keys() else ""
    sku_master = r["sku_master"] if "sku_master" in r.keys() else ""
    familia = detectar_familia(produto_padrao)
    attrs = extrair_atributos_basicos(produto_padrao)
    status = sku_status(sku_master, produto_padrao)
    assinatura = assinatura_tecnica(familia, attrs)

    item = {
        "id": r["id"],
        "produto_padrao": produto_padrao,
        "sku_master": sku_master,
        "fabricante": r["fabricante"] if "fabricante" in r.keys() else "",
        "categoria": r["categoria"] if "categoria" in r.keys() else "",
        "familia": familia,
        "status_sku": status,
        "atributos": attrs,
        "assinatura": assinatura,
    }

    familias[familia].append(item)
    assinaturas[assinatura].append(item)

# Detecta tabela de preços e tenta contar vínculos reais sem presumir demais
tabelas = [r["name"] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
tem_precos = "precos_fornecedores" in tabelas

precos_por_produto = defaultdict(list)

if tem_precos:
    cols_precos = [r["name"] for r in cur.execute("PRAGMA table_info(precos_fornecedores)").fetchall()]

    col_produto_id = None
    for c in ["produto_id", "id_produto"]:
        if c in cols_precos:
            col_produto_id = c
            break

    col_preco = None
    for c in ["preco_unitario", "preco", "valor_unitario", "valor", "custo", "menor_preco"]:
        if c in cols_precos:
            col_preco = c
            break

    col_fornecedor = None
    for c in ["fornecedor", "fornecedor_nome", "nome_fornecedor", "fornecedor_id"]:
        if c in cols_precos:
            col_fornecedor = c
            break

    if col_produto_id:
        select_cols = [col_produto_id]
        if col_preco:
            select_cols.append(col_preco)
        if col_fornecedor:
            select_cols.append(col_fornecedor)

        for p in cur.execute(f"SELECT {', '.join(select_cols)} FROM precos_fornecedores").fetchall():
            produto_id = p[col_produto_id]
            precos_por_produto[produto_id].append(dict(p))

linhas = []
linhas.append("===== DIAGNÓSTICO GERAL - MOTOR SKU_MASTER =====")
linhas.append("")
linhas.append(f"Data/hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
linhas.append(f"Banco: {DB.resolve()}")
linhas.append(f"Produtos ativos analisados: {len(rows)}")
linhas.append(f"Tabela precos_fornecedores encontrada: {'SIM' if tem_precos else 'NAO'}")
linhas.append("")
linhas.append("===== RESUMO POR FAMÍLIA =====")

resumo_familias = []

for familia, itens in sorted(familias.items(), key=lambda x: len(x[1]), reverse=True):
    total = len(itens)
    vazios = sum(1 for x in itens if x["status_sku"] == "VAZIO")
    pendentes = sum(1 for x in itens if x["status_sku"] == "SKU PENDENTE")
    iguais = sum(1 for x in itens if x["status_sku"] == "IGUAL_DESCRICAO")
    preenchidos = sum(1 for x in itens if x["status_sku"] == "PREENCHIDO")

    ids_com_preco = sum(1 for x in itens if precos_por_produto.get(x["id"]))

    assinaturas_familia = Counter(x["assinatura"] for x in itens)
    assinaturas_repetidas = sum(1 for ass, qtd in assinaturas_familia.items() if qtd >= 2)

    potencial_auto = sum(
        qtd for ass, qtd in assinaturas_familia.items()
        if qtd >= 2 and ass != familia
    )

    resumo_familias.append({
        "familia": familia,
        "total": total,
        "sku_vazio": vazios,
        "sku_pendente": pendentes,
        "sku_igual_descricao": iguais,
        "sku_preenchido": preenchidos,
        "produtos_com_preco": ids_com_preco,
        "assinaturas_repetidas": assinaturas_repetidas,
        "potencial_auto_por_assinatura": potencial_auto,
    })

    linhas.append(
        f"{familia}: total={total} | vazios={vazios} | pendentes={pendentes} | "
        f"iguais_descricao={iguais} | preenchidos={preenchidos} | com_preco={ids_com_preco} | "
        f"assinaturas_repetidas={assinaturas_repetidas} | potencial_auto={potencial_auto}"
    )

linhas.append("")
linhas.append("===== TOP ASSINATURAS TÉCNICAS REPETIDAS =====")

top_ass = []
for ass, itens in assinaturas.items():
    if len(itens) >= 2 and "OUTROS -" not in ass and ass != "INDEFINIDO":
        top_ass.append((ass, itens))

top_ass = sorted(top_ass, key=lambda x: len(x[1]), reverse=True)

for ass, itens in top_ass[:80]:
    status_count = Counter(x["status_sku"] for x in itens)
    linhas.append("")
    linhas.append(f"ASSINATURA: {ass}")
    linhas.append(f"Total itens: {len(itens)} | Status: {dict(status_count)}")
    linhas.append("Amostras:")
    for x in itens[:8]:
        linhas.append(f"  ID {x['id']} | SKU atual: {x['sku_master'] or ''} | {x['produto_padrao']}")

linhas.append("")
linhas.append("===== RECOMENDAÇÃO DO MOTOR =====")
linhas.append("")
linhas.append("1. Começar pelas famílias com maior total e maior potencial_auto.")
linhas.append("2. Aprovar regras por assinatura técnica, não por lista pequena de produtos.")
linhas.append("3. Usar revisão manual somente para itens sem família, sem medida/dose ou com conflito técnico.")
linhas.append("4. Depois de validada uma regra, aplicar em produtos atuais e futuros no importador.")

TXT.write_text("\n".join(linhas), encoding="utf-8")

with CSV_FAMILIAS.open("w", newline="", encoding="utf-8-sig") as f:
    campos_csv = [
        "familia",
        "total",
        "sku_vazio",
        "sku_pendente",
        "sku_igual_descricao",
        "sku_preenchido",
        "produtos_com_preco",
        "assinaturas_repetidas",
        "potencial_auto_por_assinatura",
    ]
    w = csv.DictWriter(f, fieldnames=campos_csv, delimiter=";")
    w.writeheader()
    w.writerows(resumo_familias)

with CSV_AMOSTRAS.open("w", newline="", encoding="utf-8-sig") as f:
    campos_csv = [
        "assinatura",
        "total_assinatura",
        "produto_id",
        "familia",
        "status_sku",
        "sku_master_atual",
        "fabricante",
        "categoria",
        "produto_padrao",
    ]
    w = csv.DictWriter(f, fieldnames=campos_csv, delimiter=";")
    w.writeheader()

    for ass, itens in top_ass:
        for x in itens[:20]:
            w.writerow({
                "assinatura": ass,
                "total_assinatura": len(itens),
                "produto_id": x["id"],
                "familia": x["familia"],
                "status_sku": x["status_sku"],
                "sku_master_atual": x["sku_master"] or "",
                "fabricante": x["fabricante"] or "",
                "categoria": x["categoria"] or "",
                "produto_padrao": x["produto_padrao"] or "",
            })

conn.close()

print("Relatório:", TXT.resolve())
print("CSV famílias:", CSV_FAMILIAS.resolve())
print("CSV amostras:", CSV_AMOSTRAS.resolve())
print("Abra com:")
print("notepad diagnostico_motor_sku_master_familias.txt")
