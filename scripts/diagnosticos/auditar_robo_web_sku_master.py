from pathlib import Path
import csv

CSV = Path("previa_robo_web_sku_master.csv")
SAIDA = Path("auditoria_robo_web_sku_master.txt")

linhas = []
linhas.append("===== AUDITORIA DO ROBÔ WEB SKU_MASTER =====")
linhas.append("")

if not CSV.exists():
    linhas.append("FALHOU: CSV não existe.")
    SAIDA.write_text("\n".join(linhas), encoding="utf-8")
    print("FALHOU: CSV não existe.")
    raise SystemExit

if CSV.stat().st_size == 0:
    linhas.append("FALHOU: CSV existe, mas está vazio.")
    SAIDA.write_text("\n".join(linhas), encoding="utf-8")
    print("FALHOU: CSV vazio.")
    raise SystemExit

with CSV.open("r", encoding="utf-8-sig", newline="") as f:
    reader = csv.DictReader(f, delimiter=";")
    rows = list(reader)
    campos = reader.fieldnames or []

linhas.append(f"CSV encontrado: SIM")
linhas.append(f"Tamanho do CSV: {CSV.stat().st_size} bytes")
linhas.append(f"Linhas de dados: {len(rows)}")
linhas.append("")
linhas.append("===== CAMPOS ENCONTRADOS NO CSV =====")
for c in campos:
    linhas.append(f"- {c}")

campos_obrigatorios = [
    "id",
    "descricao_atual",
    "consulta_web",
    "sku_master_sugerido",
    "confianca",
    "evidencia",
]

linhas.append("")
linhas.append("===== VALIDAÇÃO DE CAMPOS OBRIGATÓRIOS =====")

faltando = [c for c in campos_obrigatorios if c not in campos]

if faltando:
    linhas.append("FALHOU: campos obrigatórios ausentes:")
    for c in faltando:
        linhas.append(f"- {c}")
else:
    linhas.append("OK: campos obrigatórios básicos existem.")

total = len(rows)
alta = 0
alta_sem_evidencia = 0
alta_sem_sku = 0
alta_sem_consulta = 0
alta_com_erro_web = 0
sem_evidencia = 0
com_erro_web = 0

amostras_problema = []

for r in rows:
    confianca = str(r.get("confianca") or "").strip().upper()
    evidencia = str(r.get("evidencia") or "").strip()
    sku = str(r.get("sku_master_sugerido") or "").strip()
    consulta = str(r.get("consulta_web") or "").strip()
    erro = str(r.get("erro_web") or "").strip()

    if confianca == "ALTA":
        alta += 1

        if not evidencia:
            alta_sem_evidencia += 1
            amostras_problema.append((r.get("id"), "ALTA sem evidência", r.get("descricao_atual")))

        if not sku:
            alta_sem_sku += 1
            amostras_problema.append((r.get("id"), "ALTA sem SKU sugerido", r.get("descricao_atual")))

        if not consulta:
            alta_sem_consulta += 1
            amostras_problema.append((r.get("id"), "ALTA sem consulta web", r.get("descricao_atual")))

        if erro:
            alta_com_erro_web += 1
            amostras_problema.append((r.get("id"), "ALTA com erro web", erro))

    if not evidencia:
        sem_evidencia += 1

    if erro:
        com_erro_web += 1

linhas.append("")
linhas.append("===== CONTAGEM =====")
linhas.append(f"Total linhas: {total}")
linhas.append(f"Linhas ALTA confiança: {alta}")
linhas.append(f"Linhas sem evidência: {sem_evidencia}")
linhas.append(f"Linhas com erro web: {com_erro_web}")
linhas.append("")
linhas.append("===== PROBLEMAS EM ALTA CONFIANÇA =====")
linhas.append(f"ALTA sem evidência: {alta_sem_evidencia}")
linhas.append(f"ALTA sem SKU sugerido: {alta_sem_sku}")
linhas.append(f"ALTA sem consulta web: {alta_sem_consulta}")
linhas.append(f"ALTA com erro web: {alta_com_erro_web}")

linhas.append("")
linhas.append("===== VEREDITO =====")

if total == 0:
    linhas.append("FALHOU: CSV sem linhas.")
elif faltando:
    linhas.append("FALHOU: CSV não tem campos mínimos para auditoria.")
elif alta > 0 and (alta_sem_evidencia > 0 or alta_sem_sku > 0 or alta_sem_consulta > 0 or alta_com_erro_web > 0):
    linhas.append("REPROVADO: existem itens ALTA confiança sem prova mínima.")
elif alta == 0:
    linhas.append("SEM ALTA CONFIANÇA: nada deve ser aplicado automaticamente.")
else:
    linhas.append("PARCIALMENTE OK: o CSV tem evidências textuais, mas ainda falta prova forte com URL e arquivo bruto salvo.")
    linhas.append("NÃO APLICAR NO BANCO AINDA.")

linhas.append("")
linhas.append("===== AMOSTRAS DE PROBLEMAS =====")
for pid, motivo, desc in amostras_problema[:20]:
    linhas.append(f"ID {pid} | {motivo} | {desc}")

SAIDA.write_text("\n".join(linhas), encoding="utf-8")

print("Relatório gerado:", SAIDA.resolve())
print("Abra com:")
print("notepad auditoria_robo_web_sku_master.txt")
