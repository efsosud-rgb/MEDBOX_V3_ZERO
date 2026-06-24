import sqlite3
import re
import csv
import shutil
from pathlib import Path
from datetime import datetime

DB = Path("banco/medbox_v3.db")
BACKUP_DIR = Path("banco/backups")
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

CSV = Path("previa_regra_tubo_endotraqueal_s_cuff_v2.csv")
TXT = Path("relatorio_previa_regra_tubo_endotraqueal_s_cuff_v2.txt")

REGRA_NOME = "REGRA_TUBO_ENDOTRAQUEAL_S_CUFF_MEDIDA_VARIAVEL"

backup = BACKUP_DIR / f"medbox_v3_backup_previa_regra_tubo_s_cuff_v2_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
shutil.copy2(DB, backup)

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
    txt = txt.replace("NO ", "N ")
    txt = txt.replace("NUMERO", "N ")

    txt = txt.replace("C/", "COM ")
    txt = txt.replace("S/", "SEM ")

    txt = txt.replace("COM/BALAO", "COM BALAO")
    txt = txt.replace("SEM/BALAO", "SEM BALAO")

    txt = txt.replace("BALONETE", "CUFF")
    txt = txt.replace("BALAO", "CUFF")

    txt = txt.replace("POLIVINIL", "PVC")
    txt = txt.replace("POLI VINIL", "PVC")
    txt = txt.replace("CLORETO DE POLIVINILA", "PVC")

    txt = txt.replace("OROTRAQUEAL", "ENDOTRAQUEAL")
    txt = txt.replace("ORO TRAQUEAL", "ENDOTRAQUEAL")
    txt = txt.replace("ORO-TRAQUEAL", "ENDOTRAQUEAL")

    txt = re.sub(r"[^A-Z0-9%/,.\-+ X]+", " ", txt)
    txt = re.sub(r"\s+", " ", txt).strip()
    return txt

def formatar_medida(v):
    v = str(v or "").strip().replace(".", ",")
    return v + "MM"

def extrair_medida(desc):
    t = norm(desc)

    # Caso: "NO 12, 2,5MM" ou "N 10, 2,0MM".
    # O 12/10 pode ser código; a medida real é 2,5MM / 2,0MM.
    m = re.search(r"\bN\s*\d+\s*,\s*(\d+(?:[,.]\d+)?)\s*MM\b", t)
    if m:
        return formatar_medida(m.group(1)), "MEDIDA_APOS_N_COMPLEXO"

    # N 7,0 / N. 5,0 / N 3,5
    m = re.search(r"\bN\.?\s*(\d+(?:[,.]\d+)?)\s*MM?\b", t)
    if m:
        valor = m.group(1)
        try:
            numero = float(valor.replace(",", "."))
            if 2.0 <= numero <= 10.0:
                return formatar_medida(valor), "MEDIDA_POR_N_NUMERO"
        except Exception:
            pass

    m = re.search(r"\bTAM\s*(\d+(?:[,.]\d+)?)\b", t)
    if m:
        return formatar_medida(m.group(1)), "MEDIDA_POR_TAM"

    t_limpo = re.sub(r"CONECTOR\s+DE\s+\d+(?:[,.]\d+)?\s*MM", " ", t)
    t_limpo = re.sub(r"CONECTOR\s+\d+(?:[,.]\d+)?\s*MM", " ", t_limpo)
    t_limpo = re.sub(r"GRADUACAO\s+EM\s+CENTIMETROS", " ", t_limpo)

    # TUBO ENDOTRAQUEAL 3,5MM S/BALAO
    m = re.search(r"ENDOTRAQUEAL\s+(\d+(?:[,.]\d+)?)\s*MM", t_limpo)
    if m:
        return formatar_medida(m.group(1)), "MEDIDA_APOS_ENDOTRAQUEAL_MM"

    # TUBO ENDOTRAQUEAL 2.0 SEM/BALAO
    m = re.search(r"ENDOTRAQUEAL\s+(\d+(?:[,.]\d+)?)\s+SEM\s+CUFF", t_limpo)
    if m:
        return formatar_medida(m.group(1)), "MEDIDA_APOS_ENDOTRAQUEAL"

    medidas = re.findall(r"\b(\d+(?:[,.]\d+)?)\s*MM\b", t_limpo)
    for x in medidas:
        try:
            n = float(x.replace(",", "."))
            if 2.0 <= n <= 10.0:
                return formatar_medida(x), "MEDIDA_MM_FILTRADA"
        except Exception:
            pass

    return "", "SEM_MEDIDA_SEGURA"

def aplicar_regra(desc):
    t = norm(desc)

    bloqueios_familia = [
        "FIXADOR",
        "SISTEMA DE ASP",
        "ASP FECHADO",
        "TRACK CARE",
        "ARAMADO",
        "REFORCADO",
        "REFORÇADO",
        "FLEXOMETALICO",
        "FLEXO METALICO",
        "FLEXO-METALICO",
    ]

    for b in bloqueios_familia:
        if b in t:
            return None

    if "TUBO" not in t:
        return None

    if "ENDOTRAQUEAL" not in t:
        return None

    if "COM CUFF" in t:
        return {
            "aplica": "NAO",
            "motivo": "BLOQUEADO_COM_CUFF",
            "sku_master_sugerido": "",
            "categoria_sugerida": "",
            "medida": "",
            "origem_medida": "",
            "confianca": "BLOQUEADO"
        }

    if "SEM CUFF" not in t:
        return {
            "aplica": "NAO",
            "motivo": "FALTA_SEM_CUFF",
            "sku_master_sugerido": "",
            "categoria_sugerida": "",
            "medida": "",
            "origem_medida": "",
            "confianca": "BAIXA"
        }

    medida, origem = extrair_medida(t)

    if not medida:
        return {
            "aplica": "NAO",
            "motivo": "FALTA_MEDIDA_SEGURA",
            "sku_master_sugerido": "",
            "categoria_sugerida": "",
            "medida": "",
            "origem_medida": origem,
            "confianca": "BAIXA"
        }

    return {
        "aplica": "SIM",
        "motivo": REGRA_NOME,
        "sku_master_sugerido": f"TUBO ENDOTRAQUEAL S/CUFF {medida}",
        "categoria_sugerida": "CORRELATOS",
        "medida": medida,
        "origem_medida": origem,
        "confianca": "ALTA_REGRA_VALIDADA_S_CUFF"
    }

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

cur.execute("""
SELECT id
FROM sku_master_regras
WHERE nome_regra = ?
LIMIT 1
""", (REGRA_NOME,))

existe = cur.fetchone()

if not existe:
    cur.execute("""
    INSERT INTO sku_master_regras (
        nome_regra,
        familia,
        sku_master_padrao,
        categoria,
        fabricante,
        termos_equivalentes,
        termos_obrigatorios,
        especificacoes_obrigatorias,
        termos_proibidos,
        exemplos_positivos,
        exemplos_negativos,
        fonte_validacao,
        observacoes,
        usuario_validou,
        ativo
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        REGRA_NOME,
        "TUBO ENDOTRAQUEAL",
        "TUBO ENDOTRAQUEAL S/CUFF {MEDIDA}",
        "CORRELATOS",
        "",
        """
OROTRAQUEAL=ENDOTRAQUEAL
SEM BALAO=S/CUFF
SEM BALONETE=S/CUFF
SEM CUFF=S/CUFF
S/BALAO=S/CUFF
S/CUFF=S/CUFF
POLIVINIL=PVC
POLI VINIL=PVC
CLORETO DE POLIVINILA=PVC
""".strip(),
        """
TUBO
ENDOTRAQUEAL|OROTRAQUEAL
S/CUFF|SEM CUFF|SEM BALAO|SEM BALONETE|S/BALAO
MEDIDA
""".strip(),
        "MEDIDA_MM",
        """
COM CUFF
COM BALAO
COM BALONETE
C/CUFF
C/BALAO
ARAMADO
REFORCADO
FLEXOMETALICO
FIXADOR
SISTEMA DE ASPIRACAO
""".strip(),
        """
TUBO ENDOTRAQUEAL 3,5MM S/BALAO => TUBO ENDOTRAQUEAL S/CUFF 3,5MM
TUBO ENDOTRAQUEAL N 3,0 SEM CUFF => TUBO ENDOTRAQUEAL S/CUFF 3,0MM
TUBO OROTRAQUEAL SEM BALAO POLIVINIL 3,5MM => TUBO ENDOTRAQUEAL S/CUFF 3,5MM
""".strip(),
        """
TUBO ENDOTRAQUEAL C/BALAO 7,5MM
TUBO ENDOTRAQUEAL COM CUFF 7,5MM
TUBO ENDOTRAQUEAL ARAMADO S/BALAO 3,5MM
FIXADOR TUBO ENDOTRAQUEAL
""".strip(),
        "VALIDADO PELO USUARIO: COM=C/; SEM=S/; CUFF É CARACTERÍSTICA TÉCNICA; PVC NÃO DIFERENCIA ESTE SKU_MASTER",
        "Regra para tubo endotraqueal sem cuff. Não mistura com C/CUFF. PVC/POLIVINIL não entra no SKU_MASTER porque não diferencia comercialmente este produto.",
        "ERIC",
        1
    ))
    regra_id = cur.lastrowid
else:
    regra_id = existe["id"]

conn.commit()

rows = cur.execute("""
SELECT id, sku, produto_padrao, sku_master, fabricante, categoria, ativo
FROM produtos
WHERE ativo = 1
  AND (
      UPPER(COALESCE(produto_padrao, '')) LIKE '%TUBO ENDOTRAQUEAL%'
      OR UPPER(COALESCE(produto_padrao, '')) LIKE '%TUBO OROTRAQUEAL%'
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
    res = aplicar_regra(desc)

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
        "origem_medida": res["origem_medida"],
        "aplica": res["aplica"],
        "confianca": res["confianca"],
        "motivo": res["motivo"],
        "regra_id": regra_id,
        "regra_nome": REGRA_NOME,
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
        "confianca",
        "motivo",
        "regra_id",
        "regra_nome",
    ]
    w = csv.DictWriter(f, fieldnames=campos, delimiter=";")
    w.writeheader()
    w.writerows(saida)

aplicaveis = [r for r in saida if r["aplica"] == "SIM"]

linhas = []
linhas.append("===== PRÉVIA REGRA V2 - TUBO ENDOTRAQUEAL S/CUFF =====")
linhas.append("")
linhas.append(f"Data/hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
linhas.append(f"Backup criado: {backup}")
linhas.append(f"Regra ID: {regra_id}")
linhas.append(f"Regra: {REGRA_NOME}")
linhas.append("")
linhas.append(f"Produtos analisados: {cont['analisados']}")
linhas.append(f"Linhas classificadas: {len(saida)}")
linhas.append(f"Aplicaria automaticamente: {cont['aplica']}")
linhas.append(f"Não aplicaria: {cont['nao_aplica']}")
linhas.append(f"Bloqueados: {cont['bloqueados']}")
linhas.append("")
linhas.append("===== ITENS QUE A REGRA APLICARIA =====")

for r in aplicaveis:
    linhas.append(
        f"ID {r['produto_id']} | {r['descricao_atual']} | "
        f"SUGERIDO: {r['sku_master_sugerido']} | "
        f"MEDIDA: {r['medida_detectada']} | "
        f"ORIGEM_MEDIDA: {r['origem_medida']}"
    )

linhas.append("")
linhas.append(f"CSV: {CSV.resolve()}")
linhas.append("")
linhas.append("Banco de produtos alterado: NÃO")
linhas.append("Aplicação automática: NÃO")
linhas.append("")
linhas.append("Observação: regra S/CUFF separada da regra C/CUFF. PVC/POLIVINIL não entra no SKU_MASTER.")

TXT.write_text("\n".join(linhas), encoding="utf-8")

conn.close()

print("Relatório:", TXT.resolve())
print("CSV:", CSV.resolve())
print("Abra com:")
print("notepad relatorio_previa_regra_tubo_endotraqueal_s_cuff_v2.txt")
