import sqlite3
import re
import csv
from pathlib import Path
from datetime import datetime

DB = Path("banco/medbox_v3.db")
CSV = Path("previa_aplicacao_regra_tubo_endotraqueal.csv")
TXT = Path("relatorio_previa_regra_tubo_endotraqueal.txt")

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
    for a,b in mapa.items():
        txt = txt.replace(a,b)

    txt = txt.replace("\\", "/")
    txt = txt.replace("N°", "N ")
    txt = txt.replace("Nº", "N ")
    txt = txt.replace("NUMERO", "N ")
    txt = txt.replace("C/", "COM ")
    txt = txt.replace("S/", "SEM ")
    txt = txt.replace("BALONETE", "BALAO")
    txt = txt.replace("CUFF", "BALAO")
    txt = txt.replace("POLIVINIL", "PVC")
    txt = txt.replace("POLI VINIL", "PVC")
    txt = txt.replace("CLORETO DE POLIVINILA", "PVC")
    txt = txt.replace("OROTRAQUEAL", "ENDOTRAQUEAL")
    txt = txt.replace("ORO TRAQUEAL", "ENDOTRAQUEAL")
    txt = txt.replace("ORO-TRAQUEAL", "ENDOTRAQUEAL")

    txt = re.sub(r"[^A-Z0-9%/,.\-+ X]+", " ", txt)
    txt = re.sub(r"\s+", " ", txt).strip()
    return txt

def extrair_medida_mm(txt):
    t = norm(txt)

    # 8,5MM / 8.5MM / 7,0 MM
    m = re.search(r"\b(\d+(?:[,.]\d+)?)\s*MM\b", t)
    if m:
        return m.group(1).replace(".", ",") + "MM"

    # N 8,5 / N 7.5 / NO 10
    m = re.search(r"\bN\s*(\d+(?:[,.]\d+)?)\b", t)
    if m:
        return m.group(1).replace(".", ",") + "MM"

    # TAM 9,0
    m = re.search(r"\bTAM\s*(\d+(?:[,.]\d+)?)\b", t)
    if m:
        return m.group(1).replace(".", ",") + "MM"

    return ""

def aplicar_regra_tubo_endotraqueal(desc):
    t = norm(desc)
    motivos = []

    if "TUBO" not in t and "CANULA" not in t:
        return None

    if "ENDOTRAQUEAL" not in t:
        return None

    # Bloqueios absolutos
    proibidos = ["SEM BALAO", "SEM CUFF", "SEM BALONETE", "LATEX", "SILICONE"]
    for p in proibidos:
        if p in t:
            return {
                "aplica": "NAO",
                "motivo": f"BLOQUEADO_TERMO_PROIBIDO: {p}",
                "sku_master_sugerido": "",
                "categoria_sugerida": "",
                "medida": "",
                "confianca": "BLOQUEADO"
            }

    if "COM BALAO" not in t and "BALAO" not in t:
        return {
            "aplica": "NAO",
            "motivo": "FALTA_COM_BALAO_BALONETE_CUFF",
            "sku_master_sugerido": "",
            "categoria_sugerida": "",
            "medida": "",
            "confianca": "BAIXA"
        }

    if "PVC" not in t:
        return {
            "aplica": "NAO",
            "motivo": "FALTA_MATERIAL_PVC_POLIVINIL",
            "sku_master_sugerido": "",
            "categoria_sugerida": "",
            "medida": "",
            "confianca": "MEDIA"
        }

    medida = extrair_medida_mm(t)

    if not medida:
        return {
            "aplica": "NAO",
            "motivo": "FALTA_MEDIDA_MM",
            "sku_master_sugerido": "",
            "categoria_sugerida": "",
            "medida": "",
            "confianca": "BAIXA"
        }

    sku = f"TUBO ENDOTRAQUEAL C/BALAO PVC {medida}"

    return {
        "aplica": "SIM",
        "motivo": "REGRA_VALIDADA_TUBO_ENDOTRAQUEAL_C_BALAO_PVC_MEDIDA_VARIAVEL",
        "sku_master_sugerido": sku,
        "categoria_sugerida": "CORRELATOS",
        "medida": medida,
        "confianca": "ALTA_REGRA_VALIDADA"
    }

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

regra = cur.execute("""
SELECT id, nome_regra
FROM sku_master_regras
WHERE nome_regra = ?
  AND ativo = 1
LIMIT 1
""", ("REGRA_TUBO_ENDOTRAQUEAL_C_BALAO_PVC_MEDIDA_VARIAVEL",)).fetchone()

if not regra:
    raise SystemExit("ERRO: regra não encontrada ou inativa.")

rows = cur.execute("""
SELECT id, sku, produto_padrao, sku_master, fabricante, categoria, ativo
FROM produtos
WHERE ativo = 1
  AND UPPER(COALESCE(produto_padrao, '')) LIKE '%TUBO%'
  AND (
      UPPER(COALESCE(produto_padrao, '')) LIKE '%OROTRAQUEAL%'
      OR UPPER(COALESCE(produto_padrao, '')) LIKE '%ENDOTRAQUEAL%'
  )
ORDER BY id
""").fetchall()

saida = []
cont = {
    "analisados": 0,
    "aplica": 0,
    "nao_aplica": 0,
    "bloqueados": 0,
}

for r in rows:
    cont["analisados"] += 1
    desc = r["produto_padrao"] or r["sku"] or ""
    res = aplicar_regra_tubo_endotraqueal(desc)

    if not res:
        continue

    if res["aplica"] == "SIM":
        cont["aplica"] += 1
    else:
        cont["nao_aplica"] += 1
        if res["confianca"] == "BLOQUEADO":
            cont["bloqueados"] += 1

    saida.append({
        "produto_id": r["id"],
        "descricao_atual": desc,
        "sku_master_atual": r["sku_master"] or "",
        "sku_master_sugerido": res["sku_master_sugerido"],
        "categoria_atual": r["categoria"] or "",
        "categoria_sugerida": res["categoria_sugerida"],
        "medida_detectada": res["medida"],
        "aplica": res["aplica"],
        "confianca": res["confianca"],
        "motivo": res["motivo"],
        "regra_id": regra["id"],
        "regra_nome": regra["nome_regra"],
    })

with CSV.open("w", newline="", encoding="utf-8-sig") as f:
    campos = [
        "produto_id",
        "descricao_atual",
        "sku_master_atual",
        "sku_master_sugerido",
        "categoria_atual",
        "categoria_sugerida",
        "medida_detectada",
        "aplica",
        "confianca",
        "motivo",
        "regra_id",
        "regra_nome",
    ]
    w = csv.DictWriter(f, fieldnames=campos, delimiter=";")
    w.writeheader()
    w.writerows(saida)

linhas = []
linhas.append("===== PRÉVIA REGRA VALIDADA - TUBO ENDOTRAQUEAL =====")
linhas.append("")
linhas.append(f"Data/hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
linhas.append(f"Regra ID: {regra['id']}")
linhas.append(f"Regra: {regra['nome_regra']}")
linhas.append("")
linhas.append(f"Produtos analisados: {cont['analisados']}")
linhas.append(f"Linhas classificadas: {len(saida)}")
linhas.append(f"Aplicaria automaticamente: {cont['aplica']}")
linhas.append(f"Não aplicaria: {cont['nao_aplica']}")
linhas.append(f"Bloqueados por termo proibido: {cont['bloqueados']}")
linhas.append("")
linhas.append(f"CSV: {CSV.resolve()}")
linhas.append("")
linhas.append("Banco alterado: NÃO")
linhas.append("Aplicação automática: NÃO")
linhas.append("")
linhas.append("Regra: só aplica quando for ENDOTRAQUEAL/OROTRAQUEAL + COM BALAO/BALONETE/CUFF + PVC/POLIVINIL + MEDIDA MM.")
linhas.append("Bloqueia SEM BALAO, SEM CUFF, LATEX e SILICONE.")

TXT.write_text("\n".join(linhas), encoding="utf-8")

conn.close()

print("Relatório:", TXT.resolve())
print("CSV:", CSV.resolve())
print("Abra com:")
print("notepad relatorio_previa_regra_tubo_endotraqueal.txt")
print("start excel previa_aplicacao_regra_tubo_endotraqueal.csv")
