import sqlite3
import csv
from pathlib import Path
from datetime import datetime

DB = Path("banco/medbox_v3.db")
REL = Path("previa_corrigir_fabricantes_codigo_unidade.txt")
CSV = Path("previa_corrigir_fabricantes_codigo_unidade.csv")

codigos_suspeitos = [
    "UN", "U N", "RL", "PR", "PT", "MT", "CX", "FL", "GL", "KT"
]

# Palavras que indicam que produto_padrao é produto real, não marca.
# Se tiver uma dessas, não sugerimos usar produto_padrao como fabricante.
indicadores_produto_real = [
    "AGULHA", "SERINGA", "LUVA", "TUBO", "SONDA", "CATETER", "EQUIPO",
    "COMP", "CAP", "ML", "MG", "FR", "CX", "UN", "CM", "MM", "PCT",
    "COLETOR", "BOLSA", "GAZE", "ATADURA", "MASCARA", "AVENTAL",
    "LENÇOL", "LENCOL", "ESPARADRAPO", "FITA", "LAMINA", "LAMINULA",
    "PIPETA", "PLACA", "SWAB", "PONTEIRA"
]

def parece_marca(txt):
    t = str(txt or "").upper().strip()
    if not t:
        return False, "VAZIO"

    # Se é curto mas alfabético, pode ser marca.
    # Ex.: BD, MD, ICE, ABC.
    palavras = t.replace("-", " ").split()

    for p in indicadores_produto_real:
        if p in t:
            return False, f"CONTEM_INDICADOR_PRODUTO_REAL:{p}"

    # Marcas/nomes geralmente não têm muita informação técnica.
    if len(palavras) <= 3:
        return True, "PRODUTO_PADRAO_PARECE_MARCA_OU_NOME_COMERCIAL"

    return False, "NOME_LONGO_OU_INCONCLUSIVO"

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

saida = []

for codigo in codigos_suspeitos:
    rows = cur.execute("""
        SELECT id, produto_padrao, sku_master, fabricante, categoria, ativo, observacoes
        FROM produtos
        WHERE UPPER(TRIM(COALESCE(fabricante,''))) = UPPER(TRIM(?))
        ORDER BY id
    """, (codigo,)).fetchall()

    for r in rows:
        produto = r["produto_padrao"] or ""
        ok, motivo = parece_marca(produto)

        if ok:
            sugestao = produto.strip().upper()
            decisao = "SUGERIR_FABRICANTE_PRODUTO_PADRAO"
        else:
            sugestao = ""
            decisao = "REVISAR_MANUALMENTE"

        saida.append({
            "id": r["id"],
            "produto_padrao": produto,
            "sku_master": r["sku_master"] or "",
            "fabricante_atual": r["fabricante"] or "",
            "fabricante_sugerido": sugestao,
            "categoria": r["categoria"] or "",
            "ativo": r["ativo"],
            "decisao": decisao,
            "motivo": motivo,
            "observacoes": r["observacoes"] or "",
        })

with CSV.open("w", encoding="utf-8-sig", newline="") as f:
    campos = [
        "id",
        "produto_padrao",
        "sku_master",
        "fabricante_atual",
        "fabricante_sugerido",
        "categoria",
        "ativo",
        "decisao",
        "motivo",
        "observacoes",
    ]
    w = csv.DictWriter(f, fieldnames=campos, delimiter=";")
    w.writeheader()
    w.writerows(saida)

linhas = []
linhas.append("===== PRÉVIA CORREÇÃO FABRICANTES COM CÓDIGO/UNIDADE =====")
linhas.append("")
linhas.append(f"Data/hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
linhas.append("")
linhas.append("Banco alterado: NÃO")
linhas.append("Fabricantes alterados: NÃO")
linhas.append("")
linhas.append("REGRA:")
linhas.append("UN, U N, RL, PR, PT, MT, CX, FL, GL, KT são códigos/siglas suspeitos no campo fabricante.")
linhas.append("Não serão tratados como fabricante real.")
linhas.append("Quando produto_padrao parecer marca/nome comercial, sugerir fabricante = produto_padrao.")
linhas.append("Quando produto_padrao parecer produto real, enviar para revisão manual.")
linhas.append("")
linhas.append(f"Total analisado: {len(saida)}")
linhas.append(f"Sugeridos: {sum(1 for x in saida if x['decisao'] == 'SUGERIR_FABRICANTE_PRODUTO_PADRAO')}")
linhas.append(f"Revisão manual: {sum(1 for x in saida if x['decisao'] != 'SUGERIR_FABRICANTE_PRODUTO_PADRAO')}")
linhas.append("")
linhas.append("===== RESUMO POR FABRICANTE ATUAL =====")

for codigo in codigos_suspeitos:
    total = sum(1 for x in saida if x["fabricante_atual"].upper().strip() == codigo)
    sugeridos = sum(1 for x in saida if x["fabricante_atual"].upper().strip() == codigo and x["decisao"] == "SUGERIR_FABRICANTE_PRODUTO_PADRAO")
    revisao = total - sugeridos
    if total:
        linhas.append(f"{codigo}: total={total} | sugeridos={sugeridos} | revisar={revisao}")

linhas.append("")
linhas.append("===== SUGESTÕES =====")

for x in saida:
    linhas.append("")
    linhas.append(f"ID: {x['id']}")
    linhas.append(f"Produto padrão: {x['produto_padrao']}")
    linhas.append(f"SKU_MASTER: {x['sku_master']}")
    linhas.append(f"Fabricante atual: {x['fabricante_atual']}")
    linhas.append(f"Fabricante sugerido: {x['fabricante_sugerido']}")
    linhas.append(f"Categoria: {x['categoria']}")
    linhas.append(f"Ativo: {x['ativo']}")
    linhas.append(f"Decisão: {x['decisao']}")
    linhas.append(f"Motivo: {x['motivo']}")

linhas.append("")
linhas.append("===== BLOQUEADOS =====")
linhas.append("MEDIXLAB não entra nesta correção. Deve permanecer separado de MEDIX.")
linhas.append("SR já foi tratado por regra contextual.")
linhas.append("")
linhas.append(f"CSV gerado: {CSV.resolve()}")
linhas.append("")
linhas.append("VEREDITO:")
linhas.append("PREVIA_GERADA_SEM_ALTERAR_BANCO")

REL.write_text("\n".join(linhas), encoding="utf-8")
conn.close()

print("Relatório:", REL.resolve())
print("CSV:", CSV.resolve())
print("Abra com:")
print("notepad previa_corrigir_fabricantes_codigo_unidade.txt")
