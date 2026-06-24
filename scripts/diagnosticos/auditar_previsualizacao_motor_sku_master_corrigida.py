import csv
import re
from pathlib import Path
from datetime import datetime

CSV_GRUPOS = Path("previsualizacao_motor_sku_master_grupos.csv")
REL = Path("auditoria_previsualizacao_motor_sku_master_corrigida.txt")

linhas = []
linhas.append("===== AUDITORIA CORRIGIDA DA PREVISUALIZAÇÃO MOTOR SKU_MASTER =====")
linhas.append("")
linhas.append(f"Data/hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
linhas.append(f"Arquivo analisado: {CSV_GRUPOS.resolve()}")
linhas.append("")

if not CSV_GRUPOS.exists():
    linhas.append("ERRO: CSV de grupos não encontrado.")
    REL.write_text("\n".join(linhas), encoding="utf-8")
    print(REL.resolve())
    raise SystemExit()

with CSV_GRUPOS.open("r", encoding="utf-8-sig", newline="") as f:
    rows = list(csv.DictReader(f, delimiter=";"))

def sku_tubo(sku):
    return "TUBO ENDOTRAQUEAL" in (sku or "").upper()

def medida_sem_decimal_padrao(sku):
    """
    Suspeito somente se a medida final for tipo 8MM, 5MM, 10MM.
    Correto: 8,0MM, 5,0MM, 7,5MM.
    """
    sku = sku or ""
    medidas = re.findall(r"\b(\d+(?:[,.]\d+)?)MM\b", sku)
    for m in medidas:
        if "," not in m and "." not in m:
            return True
    return False

aprovaveis_existentes = []
novos_para_revisao = []
suspeitos_tecnicos = []

for r in rows:
    sku = r.get("sku_master_sugerido", "")
    ja_existe = r.get("sku_sugerido_ja_existe", "")
    total_itens = int(r.get("total_itens") or 0)
    motivos = []

    if sku_tubo(sku) and medida_sem_decimal_padrao(sku):
        motivos.append("MEDIDA_SEM_DECIMAL_PADRAO")

    if sku_tubo(sku) and "C/CUFF" not in sku and "S/CUFF" not in sku:
        motivos.append("TUBO_SEM_CUFF_NO_SKU")

    if "C/CUFF" in sku and "S/CUFF" in sku:
        motivos.append("CONFLITO_CUFF_NO_SKU")

    if total_itens <= 0:
        motivos.append("GRUPO_SEM_ITENS")

    if motivos:
        r["motivos_auditoria"] = ", ".join(motivos)
        suspeitos_tecnicos.append(r)
    elif ja_existe == "SIM":
        aprovaveis_existentes.append(r)
    else:
        r["motivos_auditoria"] = "SKU_MASTER_NOVO_EXIGE_REVISAO"
        novos_para_revisao.append(r)

linhas.append(f"Total de grupos: {len(rows)}")
linhas.append(f"Grupos aprováveis já existentes no banco: {len(aprovaveis_existentes)}")
linhas.append(f"Grupos novos para revisão: {len(novos_para_revisao)}")
linhas.append(f"Grupos suspeitos técnicos: {len(suspeitos_tecnicos)}")
linhas.append("")
linhas.append("Banco alterado: NÃO")
linhas.append("Aplicação automática: NÃO")
linhas.append("")

linhas.append("===== GRUPOS APROVÁVEIS JÁ EXISTENTES NO BANCO =====")
for r in aprovaveis_existentes[:120]:
    linhas.append("")
    linhas.append(f"SKU_MASTER: {r.get('sku_master_sugerido','')}")
    linhas.append(f"Total itens: {r.get('total_itens','')}")
    linhas.append(f"Já existe no banco: {r.get('sku_sugerido_ja_existe','')}")
    linhas.append(f"Menor custo: {r.get('menor_custo_grupo','') or '-'}")
    linhas.append(f"Amostra 1: {r.get('amostra_1','')}")
    linhas.append(f"Amostra 2: {r.get('amostra_2','')}")
    linhas.append(f"Amostra 3: {r.get('amostra_3','')}")

linhas.append("")
linhas.append("===== GRUPOS NOVOS PARA REVISÃO =====")
for r in novos_para_revisao[:120]:
    linhas.append("")
    linhas.append(f"SKU_MASTER: {r.get('sku_master_sugerido','')}")
    linhas.append(f"Motivo: {r.get('motivos_auditoria','')}")
    linhas.append(f"Total itens: {r.get('total_itens','')}")
    linhas.append(f"Amostra 1: {r.get('amostra_1','')}")
    linhas.append(f"Amostra 2: {r.get('amostra_2','')}")
    linhas.append(f"Amostra 3: {r.get('amostra_3','')}")

linhas.append("")
linhas.append("===== GRUPOS SUSPEITOS TÉCNICOS =====")
for r in suspeitos_tecnicos[:120]:
    linhas.append("")
    linhas.append(f"SKU_MASTER: {r.get('sku_master_sugerido','')}")
    linhas.append(f"Motivo auditoria: {r.get('motivos_auditoria','')}")
    linhas.append(f"Total itens: {r.get('total_itens','')}")
    linhas.append(f"Amostra 1: {r.get('amostra_1','')}")
    linhas.append(f"Amostra 2: {r.get('amostra_2','')}")
    linhas.append(f"Amostra 3: {r.get('amostra_3','')}")

REL.write_text("\n".join(linhas), encoding="utf-8")

print("Relatório:", REL.resolve())
print("Abra com:")
print("notepad auditoria_previsualizacao_motor_sku_master_corrigida.txt")
