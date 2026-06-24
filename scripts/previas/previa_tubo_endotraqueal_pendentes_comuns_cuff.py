import sqlite3
import re
import csv
import shutil
from pathlib import Path
from datetime import datetime

DB = Path("banco/medbox_v3.db")
BACKUP_DIR = Path("banco/backups")
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

CSV = Path("previa_tubo_endotraqueal_pendentes_comuns_cuff.csv")
TXT = Path("relatorio_previa_tubo_endotraqueal_pendentes_comuns_cuff.txt")

backup = BACKUP_DIR / f"medbox_v3_backup_previa_tubo_pendentes_comuns_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
shutil.copy2(DB, backup)

def normalizar(txt):
    txt = str(txt or "").upper()

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

    txt = txt.replace("\\", "/")
    txt = txt.replace("N°", "N ")
    txt = txt.replace("Nº", "N ")
    txt = txt.replace("NO ", "N ")
    txt = txt.replace("NUMERO", "N ")

    txt = txt.replace("C/", "COM ")
    txt = txt.replace("S/", "SEM ")

    txt = txt.replace("COM/BALAO", "COM BALAO")
    txt = txt.replace("SEM/BALAO", "SEM BALAO")
    txt = txt.replace("C BALAO", "COM BALAO")
    txt = txt.replace("S BALAO", "SEM BALAO")

    txt = txt.replace("BALONETE", "CUFF")
    txt = txt.replace("BALAO", "CUFF")

    txt = txt.replace("OROTRAQUEAL", "ENDOTRAQUEAL")
    txt = txt.replace("ORO TRAQUEAL", "ENDOTRAQUEAL")
    txt = txt.replace("ORO-TRAQUEAL", "ENDOTRAQUEAL")

    txt = re.sub(r"[^A-Z0-9,.\-/ ]+", " ", txt)
    txt = re.sub(r"\s+", " ", txt).strip()
    return txt

def medida_fmt(valor):
    valor = str(valor or "").strip().replace(".", ",")
    return valor + "MM"

def extrair_medida(desc):
    t = normalizar(desc)

    # Casos complexos: NO 12, 2,5MM / N 10, 2,0MM.
    # O primeiro número pode ser código; a medida real é o valor com MM.
    m = re.search(r"\bN\s*\d+\s*,\s*(\d+(?:[,.]\d+)?)\s*MM\b", t)
    if m:
        return medida_fmt(m.group(1)), "MEDIDA_APOS_N_COMPLEXO"

    # N. 3,5 / N 3,5 / N. 6,0 / N 2,5 SEM CUFF
    m = re.search(r"\bN\.?\s*(\d+(?:[,.]\d+)?)\b", t)
    if m:
        valor = m.group(1)
        try:
            n = float(valor.replace(",", "."))
            if 2.0 <= n <= 10.0:
                return medida_fmt(valor), "MEDIDA_POR_N"
        except Exception:
            pass

    # TAM 9,0
    m = re.search(r"\bTAM\s*(\d+(?:[,.]\d+)?)\b", t)
    if m:
        return medida_fmt(m.group(1)), "MEDIDA_POR_TAM"

    # TUBO ENDOTRAQUEAL 3,5MM
    m = re.search(r"ENDOTRAQUEAL\s+(\d+(?:[,.]\d+)?)\s*MM", t)
    if m:
        return medida_fmt(m.group(1)), "MEDIDA_APOS_ENDOTRAQUEAL_MM"

    # TUBO ENDOTRAQUEAL 3.5 SEM CUFF / COM CUFF
    m = re.search(r"ENDOTRAQUEAL\s+(\d+(?:[,.]\d+)?)\s+(SEM|COM)\s+CUFF", t)
    if m:
        return medida_fmt(m.group(1)), "MEDIDA_APOS_ENDOTRAQUEAL"

    # Última tentativa: qualquer medida em MM dentro da faixa de tubo
    medidas = re.findall(r"\b(\d+(?:[,.]\d+)?)\s*MM\b", t)
    for valor in medidas:
        try:
            n = float(valor.replace(",", "."))
            if 2.0 <= n <= 10.0:
                return medida_fmt(valor), "MEDIDA_MM_FILTRADA"
        except Exception:
            pass

    return "", "SEM_MEDIDA_SEGURA"

def classificar(desc):
    t = normalizar(desc)

    bloqueios = [
        "FIXADOR",
        "SISTEMA DE ASP",
        "ASP FECHADO",
        "TRACK CARE",
        "COM ASPIRACAO",
        "ARAMADO",
        "REFORCADO",
        "FLEXOMETALICO",
        "FLEXO METALICO",
    ]

    for b in bloqueios:
        if b in t:
            return None

    if "TUBO" not in t or "ENDOTRAQUEAL" not in t:
        return None

    tem_com = "COM CUFF" in t
    tem_sem = "SEM CUFF" in t

    if tem_com and tem_sem:
        return {
            "aplica": "NAO",
            "motivo": "CONFLITO_COM_E_SEM_CUFF",
            "sku": "",
            "medida": "",
            "origem": "",
        }

    medida, origem = extrair_medida(t)

    if not medida:
        return {
            "aplica": "NAO",
            "motivo": "SEM_MEDIDA_SEGURA",
            "sku": "",
            "medida": "",
            "origem": origem,
        }

    if tem_com:
        return {
            "aplica": "SIM",
            "motivo": "TUBO_ENDOTRAQUEAL_COMUM_C_CUFF",
            "sku": f"TUBO ENDOTRAQUEAL C/CUFF {medida}",
            "medida": medida,
            "origem": origem,
        }

    if tem_sem:
        return {
            "aplica": "SIM",
            "motivo": "TUBO_ENDOTRAQUEAL_COMUM_S_CUFF",
            "sku": f"TUBO ENDOTRAQUEAL S/CUFF {medida}",
            "medida": medida,
            "origem": origem,
        }

    return {
        "aplica": "NAO",
        "motivo": "NAO_IDENTIFICOU_CUFF",
        "sku": "",
        "medida": medida,
        "origem": origem,
    }

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

rows = cur.execute("""
SELECT id, produto_padrao, sku_master, categoria, fabricante
FROM produtos
WHERE ativo = 1
  AND (
      UPPER(COALESCE(produto_padrao,'')) LIKE '%TUBO ENDOTRAQUEAL%'
      OR UPPER(COALESCE(produto_padrao,'')) LIKE '%TUBO OROTRAQUEAL%'
  )
  AND (
      sku_master IS NULL
      OR TRIM(sku_master) = ''
      OR UPPER(TRIM(sku_master)) LIKE 'SKU PENDENTE%'
      OR UPPER(TRIM(sku_master)) = UPPER(TRIM(produto_padrao))
  )
ORDER BY id
""").fetchall()

saida = []

for r in rows:
    desc = r["produto_padrao"] or ""
    res = classificar(desc)

    if not res:
        continue

    saida.append({
        "produto_id": r["id"],
        "descricao_atual": desc,
        "sku_master_atual": r["sku_master"] or "",
        "sku_master_sugerido": res["sku"],
        "categoria_atual": r["categoria"] or "",
        "categoria_sugerida": "CORRELATOS" if res["aplica"] == "SIM" else "",
        "medida_detectada": res["medida"],
        "origem_medida": res["origem"],
        "aplica": res["aplica"],
        "motivo": res["motivo"],
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
        "origem_medida",
        "aplica",
        "motivo",
    ]
    w = csv.DictWriter(f, fieldnames=campos, delimiter=";")
    w.writeheader()
    w.writerows(saida)

aprovados = [r for r in saida if r["aplica"] == "SIM"]
nao = [r for r in saida if r["aplica"] != "SIM"]

linhas = []
linhas.append("===== PRÉVIA - TUBO ENDOTRAQUEAL PENDENTES COMUNS C/CUFF E S/CUFF =====")
linhas.append("")
linhas.append(f"Data/hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
linhas.append(f"Backup criado: {backup}")
linhas.append("")
linhas.append(f"Pendentes analisados: {len(rows)}")
linhas.append(f"Classificados: {len(saida)}")
linhas.append(f"Aplicaria automaticamente: {len(aprovados)}")
linhas.append(f"Não aplicaria: {len(nao)}")
linhas.append("")
linhas.append("===== ITENS QUE A REGRA APLICARIA =====")

for r in aprovados:
    linhas.append(
        f"ID {r['produto_id']} | {r['descricao_atual']} | "
        f"SUGERIDO: {r['sku_master_sugerido']} | "
        f"MEDIDA: {r['medida_detectada']} | "
        f"ORIGEM: {r['origem_medida']}"
    )

linhas.append("")
linhas.append("===== ITENS QUE NÃO APLICARIA =====")
for r in nao:
    linhas.append(
        f"ID {r['produto_id']} | {r['descricao_atual']} | "
        f"MOTIVO: {r['motivo']} | MEDIDA: {r['medida_detectada']}"
    )

linhas.append("")
linhas.append(f"CSV: {CSV.resolve()}")
linhas.append("Banco de produtos alterado: NÃO")
linhas.append("Aplicação automática: NÃO")

TXT.write_text("\n".join(linhas), encoding="utf-8")
conn.close()

print("Relatório:", TXT.resolve())
print("CSV:", CSV.resolve())
print("Abra com:")
print("notepad relatorio_previa_tubo_endotraqueal_pendentes_comuns_cuff.txt")
