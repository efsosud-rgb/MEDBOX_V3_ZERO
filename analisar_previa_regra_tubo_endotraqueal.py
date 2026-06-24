import csv
from pathlib import Path
from collections import Counter, defaultdict

CSV = Path("previa_aplicacao_regra_tubo_endotraqueal.csv")
TXT = Path("analise_previa_regra_tubo_endotraqueal.txt")

if not CSV.exists():
    raise SystemExit("ERRO: CSV não encontrado: previa_aplicacao_regra_tubo_endotraqueal.csv")

with CSV.open("r", encoding="utf-8-sig", newline="") as f:
    rows = list(csv.DictReader(f, delimiter=";"))

cont = Counter()
por_motivo = defaultdict(list)

for r in rows:
    aplica = (r.get("aplica") or "").strip().upper()
    motivo = (r.get("motivo") or "").strip()
    confianca = (r.get("confianca") or "").strip()

    cont[f"aplica_{aplica}"] += 1
    cont[f"confianca_{confianca}"] += 1
    cont[f"motivo_{motivo}"] += 1

    por_motivo[motivo].append(r)

linhas = []
linhas.append("===== ANÁLISE DA PRÉVIA - REGRA TUBO ENDOTRAQUEAL =====")
linhas.append("")
linhas.append(f"Total de linhas no CSV: {len(rows)}")
linhas.append(f"Aplicaria SIM: {cont['aplica_SIM']}")
linhas.append(f"Aplicaria NÃO: {cont['aplica_NAO']}")
linhas.append("")
linhas.append("===== CONTAGEM POR MOTIVO =====")

for k, v in cont.items():
    if k.startswith("motivo_"):
        linhas.append(f"{k.replace('motivo_', '')}: {v}")

linhas.append("")
linhas.append("===== ITENS QUE A REGRA APLICARIA =====")

aplicaveis = [r for r in rows if (r.get("aplica") or "").upper() == "SIM"]

for r in aplicaveis:
    linhas.append(
        f"ID {r.get('produto_id')} | {r.get('descricao_atual')} | "
        f"SUGERIDO: {r.get('sku_master_sugerido')} | "
        f"MEDIDA: {r.get('medida_detectada')}"
    )

linhas.append("")
linhas.append("===== AMOSTRAS DOS QUE NÃO APLICOU =====")

for motivo, itens in sorted(por_motivo.items(), key=lambda x: (-len(x[1]), x[0])):
    if motivo == "REGRA_VALIDADA_TUBO_ENDOTRAQUEAL_C_BALAO_PVC_MEDIDA_VARIAVEL":
        continue

    linhas.append("")
    linhas.append(f"--- {motivo} | total: {len(itens)} ---")

    for r in itens[:15]:
        linhas.append(
            f"ID {r.get('produto_id')} | {r.get('descricao_atual')} | "
            f"SKU atual: {r.get('sku_master_atual')}"
        )

TXT.write_text("\n".join(linhas), encoding="utf-8")

print("Relatório gerado:", TXT.resolve())
print("Abra com:")
print("notepad analise_previa_regra_tubo_endotraqueal.txt")
