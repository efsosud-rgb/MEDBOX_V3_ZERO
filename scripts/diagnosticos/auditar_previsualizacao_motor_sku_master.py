import csv
import re
from pathlib import Path
from datetime import datetime

CSV_GRUPOS = Path("previsualizacao_motor_sku_master_grupos.csv")
REL = Path("auditoria_previsualizacao_motor_sku_master.txt")

linhas = []
linhas.append("===== AUDITORIA DA PREVISUALIZAÇÃO MOTOR SKU_MASTER =====")
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

total = len(rows)
suspeitos = []
aprovaveis = []

def medida_suspeita(sku):
    # Queremos evitar SKU tipo 5MM, 8MM quando o padrão correto é 5,0MM / 8,0MM.
    return bool(re.search(r"\b\d+MM\b", sku or ""))

def sku_tubo(sku):
    return "TUBO ENDOTRAQUEAL" in (sku or "").upper()

for r in rows:
    sku = r.get("sku_master_sugerido", "")
    total_itens = int(r.get("total_itens") or 0)
    ja_existe = r.get("sku_sugerido_ja_existe", "")
    amostras = " | ".join([
        r.get("amostra_1", ""),
        r.get("amostra_2", ""),
        r.get("amostra_3", ""),
    ])

    motivos = []

    if sku_tubo(sku) and medida_suspeita(sku):
        motivos.append("MEDIDA_SEM_DECIMAL_PADRAO")

    if sku_tubo(sku) and "C/CUFF" not in sku and "S/CUFF" not in sku:
        motivos.append("TUBO_SEM_CUFF_NO_SKU")

    if "C/CUFF" in sku and "S/CUFF" in sku:
        motivos.append("CONFLITO_CUFF_NO_SKU")

    if total_itens <= 0:
        motivos.append("GRUPO_SEM_ITENS")

    # SKU novo não é necessariamente erro, mas não deve aplicar automático sem revisão.
    if ja_existe == "NAO":
        motivos.append("SKU_MASTER_NOVO_EXIGE_REVISAO")

    if motivos:
        r["motivos_auditoria"] = ", ".join(motivos)
        suspeitos.append(r)
    else:
        aprovaveis.append(r)

linhas.append(f"Total de grupos: {total}")
linhas.append(f"Grupos aprováveis tecnicamente: {len(aprovaveis)}")
linhas.append(f"Grupos suspeitos/revisão: {len(suspeitos)}")
linhas.append("")
linhas.append("Banco alterado: NÃO")
linhas.append("Aplicação automática: NÃO")
linhas.append("")

linhas.append("===== GRUPOS APROVÁVEIS TECNICAMENTE =====")
for r in aprovaveis[:80]:
    linhas.append("")
    linhas.append(f"SKU_MASTER: {r.get('sku_master_sugerido','')}")
    linhas.append(f"Total itens: {r.get('total_itens','')}")
    linhas.append(f"Já existe no banco: {r.get('sku_sugerido_ja_existe','')}")
    linhas.append(f"Menor custo: {r.get('menor_custo_grupo','') or '-'}")
    linhas.append(f"Amostra 1: {r.get('amostra_1','')}")

linhas.append("")
linhas.append("===== GRUPOS SUSPEITOS / REVISÃO =====")
for r in suspeitos[:120]:
    linhas.append("")
    linhas.append(f"SKU_MASTER: {r.get('sku_master_sugerido','')}")
    linhas.append(f"Motivo auditoria: {r.get('motivos_auditoria','')}")
    linhas.append(f"Total itens: {r.get('total_itens','')}")
    linhas.append(f"Já existe no banco: {r.get('sku_sugerido_ja_existe','')}")
    linhas.append(f"Amostra 1: {r.get('amostra_1','')}")
    linhas.append(f"Amostra 2: {r.get('amostra_2','')}")
    linhas.append(f"Amostra 3: {r.get('amostra_3','')}")

REL.write_text("\n".join(linhas), encoding="utf-8")

print("Relatório:", REL.resolve())
print("Abra com:")
print("notepad auditoria_previsualizacao_motor_sku_master.txt")
