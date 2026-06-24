import sqlite3
import csv
from pathlib import Path
from collections import defaultdict
from datetime import datetime

from core.motor_sku_master import sugerir_sku_master

DB = Path("banco/medbox_v3.db")

TXT = Path("previsualizacao_motor_sku_master_geral.txt")
CSV_DETALHE = Path("previsualizacao_motor_sku_master_detalhe.csv")
CSV_GRUPOS = Path("previsualizacao_motor_sku_master_grupos.csv")

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

def cols_tabela(nome):
    try:
        return [r["name"] for r in cur.execute(f"PRAGMA table_info({nome})").fetchall()]
    except Exception:
        return []

def existe_tabela(nome):
    r = cur.execute("""
    SELECT name
    FROM sqlite_master
    WHERE type='table'
      AND name=?
    """, (nome,)).fetchone()
    return bool(r)

cols_produtos = cols_tabela("produtos")
tem_precos = existe_tabela("precos_fornecedores")
cols_precos = cols_tabela("precos_fornecedores") if tem_precos else []

# Detecta colunas possíveis da tabela precos_fornecedores sem presumir demais.
col_preco_produto_id = None
for c in ["produto_id", "id_produto"]:
    if c in cols_precos:
        col_preco_produto_id = c
        break

col_preco_valor = None
for c in ["preco_unitario", "valor_unitario", "preco", "valor", "custo", "menor_preco"]:
    if c in cols_precos:
        col_preco_valor = c
        break

col_preco_fornecedor = None
for c in ["fornecedor", "fornecedor_nome", "nome_fornecedor", "fornecedor_id"]:
    if c in cols_precos:
        col_preco_fornecedor = c
        break

col_preco_marca = None
for c in ["marca", "fabricante", "laboratorio"]:
    if c in cols_precos:
        col_preco_marca = c
        break

# Carrega preços por produto_id, se o banco permitir.
precos_por_produto = defaultdict(list)

if tem_precos and col_preco_produto_id:
    select_cols = [col_preco_produto_id]
    for c in [col_preco_valor, col_preco_fornecedor, col_preco_marca]:
        if c and c not in select_cols:
            select_cols.append(c)

    sql = f"SELECT {', '.join(select_cols)} FROM precos_fornecedores"

    for p in cur.execute(sql).fetchall():
        pid = p[col_preco_produto_id]
        precos_por_produto[pid].append(dict(p))

def to_float(v):
    if v is None:
        return None
    try:
        s = str(v).strip()
        if not s:
            return None
        s = s.replace("R$", "").replace(" ", "")
        if "," in s and "." in s:
            s = s.replace(".", "").replace(",", ".")
        elif "," in s:
            s = s.replace(",", ".")
        return float(s)
    except Exception:
        return None

def status_sku(sku_master, produto_padrao):
    sku = str(sku_master or "").strip()
    prod = str(produto_padrao or "").strip()

    if not sku:
        return "VAZIO"
    if sku.upper().startswith("SKU PENDENTE"):
        return "SKU_PENDENTE"
    if sku.upper() == prod.upper():
        return "IGUAL_DESCRICAO"
    return "PREENCHIDO"

# Produtos ativos.
rows = cur.execute("""
SELECT id, sku, produto_padrao, sku_master, fabricante, categoria, ativo
FROM produtos
WHERE COALESCE(ativo, 1) = 1
ORDER BY id
""").fetchall()

# Mapa de SKU_MASTER já existentes no banco.
skus_existentes = defaultdict(list)

for r in rows:
    sku_atual = (r["sku_master"] or "").strip()
    if sku_atual:
        skus_existentes[sku_atual.upper()].append(r)

detalhes = []
grupos = defaultdict(list)

for r in rows:
    desc = r["produto_padrao"] or r["sku"] or ""
    atual = r["sku_master"] or ""

    sugestao = sugerir_sku_master(desc)

    aplica = sugestao.get("aplica")
    sku_sugerido = sugestao.get("sku_master") or ""
    familia = sugestao.get("familia") or ""
    assinatura = sugestao.get("assinatura") or ""
    confianca = sugestao.get("confianca") or ""
    motivo = sugestao.get("motivo") or ""

    st = status_sku(atual, desc)

    preco_vals = []
    fornecedores = set()
    marcas_precos = set()

    for p in precos_por_produto.get(r["id"], []):
        if col_preco_valor:
            vf = to_float(p.get(col_preco_valor))
            if vf is not None and vf > 0:
                preco_vals.append(vf)

        if col_preco_fornecedor and p.get(col_preco_fornecedor) not in (None, ""):
            fornecedores.add(str(p.get(col_preco_fornecedor)).strip())

        if col_preco_marca and p.get(col_preco_marca) not in (None, ""):
            marcas_precos.add(str(p.get(col_preco_marca)).strip())

    menor_custo_item = min(preco_vals) if preco_vals else None

    registro = {
        "produto_id": r["id"],
        "descricao_original": desc,
        "sku_master_atual": atual,
        "sku_master_sugerido": sku_sugerido,
        "familia": familia,
        "assinatura": assinatura,
        "aplica": aplica,
        "confianca": confianca,
        "motivo": motivo,
        "status_sku_atual": st,
        "categoria_atual": r["categoria"] or "",
        "fabricante_atual": r["fabricante"] or "",
        "menor_custo_item": menor_custo_item if menor_custo_item is not None else "",
        "fornecedores_item": " | ".join(sorted(fornecedores)),
        "marcas_precos_item": " | ".join(sorted(marcas_precos)),
        "sku_sugerido_ja_existe": "SIM" if sku_sugerido and sku_sugerido.upper() in skus_existentes else "NAO",
    }

    detalhes.append(registro)

    if aplica == "SIM" and sku_sugerido:
        grupos[sku_sugerido].append(registro)

# Gera CSV detalhe.
with CSV_DETALHE.open("w", newline="", encoding="utf-8-sig") as f:
    campos = [
        "produto_id",
        "descricao_original",
        "sku_master_atual",
        "sku_master_sugerido",
        "familia",
        "assinatura",
        "aplica",
        "confianca",
        "motivo",
        "status_sku_atual",
        "categoria_atual",
        "fabricante_atual",
        "menor_custo_item",
        "fornecedores_item",
        "marcas_precos_item",
        "sku_sugerido_ja_existe",
    ]
    w = csv.DictWriter(f, fieldnames=campos, delimiter=";")
    w.writeheader()
    w.writerows(detalhes)

# Monta resumo por grupo.
resumo_grupos = []

for sku_sugerido, itens in grupos.items():
    ids = [str(x["produto_id"]) for x in itens]
    status_count = defaultdict(int)
    fabricantes = set()
    fornecedores = set()
    marcas_precos = set()
    custos = []

    for x in itens:
        status_count[x["status_sku_atual"]] += 1

        if x["fabricante_atual"]:
            fabricantes.add(x["fabricante_atual"])

        if x["fornecedores_item"]:
            for f in x["fornecedores_item"].split("|"):
                f = f.strip()
                if f:
                    fornecedores.add(f)

        if x["marcas_precos_item"]:
            for m in x["marcas_precos_item"].split("|"):
                m = m.strip()
                if m:
                    marcas_precos.add(m)

        vf = to_float(x["menor_custo_item"])
        if vf is not None and vf > 0:
            custos.append(vf)

    ja_existe = "SIM" if sku_sugerido.upper() in skus_existentes else "NAO"
    registros_existentes = skus_existentes.get(sku_sugerido.upper(), [])

    fabricantes_existentes = sorted({
        (r["fabricante"] or "").strip()
        for r in registros_existentes
        if (r["fabricante"] or "").strip()
    })

    menor_custo_grupo = min(custos) if custos else ""

    resumo_grupos.append({
        "sku_master_sugerido": sku_sugerido,
        "total_itens": len(itens),
        "ids": ", ".join(ids),
        "familia": itens[0]["familia"],
        "assinatura": itens[0]["assinatura"],
        "sku_sugerido_ja_existe": ja_existe,
        "status_sku_atual": dict(status_count),
        "fabricantes_nos_itens": " | ".join(sorted(fabricantes)),
        "fabricantes_sku_existente": " | ".join(fabricantes_existentes),
        "fornecedores_item": " | ".join(sorted(fornecedores)),
        "marcas_precos_item": " | ".join(sorted(marcas_precos)),
        "menor_custo_grupo": menor_custo_grupo,
        "amostra_1": itens[0]["descricao_original"] if len(itens) > 0 else "",
        "amostra_2": itens[1]["descricao_original"] if len(itens) > 1 else "",
        "amostra_3": itens[2]["descricao_original"] if len(itens) > 2 else "",
    })

resumo_grupos = sorted(resumo_grupos, key=lambda x: x["total_itens"], reverse=True)

with CSV_GRUPOS.open("w", newline="", encoding="utf-8-sig") as f:
    campos = [
        "sku_master_sugerido",
        "total_itens",
        "ids",
        "familia",
        "assinatura",
        "sku_sugerido_ja_existe",
        "status_sku_atual",
        "fabricantes_nos_itens",
        "fabricantes_sku_existente",
        "fornecedores_item",
        "marcas_precos_item",
        "menor_custo_grupo",
        "amostra_1",
        "amostra_2",
        "amostra_3",
    ]
    w = csv.DictWriter(f, fieldnames=campos, delimiter=";")
    w.writeheader()
    w.writerows(resumo_grupos)

# TXT resumido.
total_aplica = sum(1 for x in detalhes if x["aplica"] == "SIM")
total_nao = sum(1 for x in detalhes if x["aplica"] != "SIM")

linhas = []
linhas.append("===== PREVISUALIZACAO GERAL - MOTOR SKU_MASTER =====")
linhas.append("")
linhas.append(f"Data/hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
linhas.append(f"Produtos ativos analisados: {len(rows)}")
linhas.append(f"Produtos com sugestao automatica: {total_aplica}")
linhas.append(f"Produtos sem sugestao automatica: {total_nao}")
linhas.append(f"Grupos SKU_MASTER sugeridos: {len(resumo_grupos)}")
linhas.append("")
linhas.append("Banco alterado: NAO")
linhas.append("Aplicacao automatica: NAO")
linhas.append("")
linhas.append("===== TOP GRUPOS SUGERIDOS =====")

for g in resumo_grupos[:120]:
    linhas.append("")
    linhas.append(f"SKU_MASTER: {g['sku_master_sugerido']}")
    linhas.append(f"Total itens: {g['total_itens']}")
    linhas.append(f"Ja existe no banco: {g['sku_sugerido_ja_existe']}")
    linhas.append(f"Assinatura: {g['assinatura']}")
    linhas.append(f"Status atuais: {g['status_sku_atual']}")
    linhas.append(f"Fabricantes nos itens: {g['fabricantes_nos_itens'] or '-'}")
    linhas.append(f"Fabricantes SKU existente: {g['fabricantes_sku_existente'] or '-'}")
    linhas.append(f"Fornecedores encontrados: {g['fornecedores_item'] or '-'}")
    linhas.append(f"Menor custo do grupo: {g['menor_custo_grupo'] or '-'}")
    linhas.append("Amostras:")
    linhas.append(f"  1. {g['amostra_1']}")
    if g["amostra_2"]:
        linhas.append(f"  2. {g['amostra_2']}")
    if g["amostra_3"]:
        linhas.append(f"  3. {g['amostra_3']}")

linhas.append("")
linhas.append(f"CSV detalhe: {CSV_DETALHE.resolve()}")
linhas.append(f"CSV grupos: {CSV_GRUPOS.resolve()}")

TXT.write_text("\n".join(linhas), encoding="utf-8")

conn.close()

print("Relatorio:", TXT.resolve())
print("CSV detalhe:", CSV_DETALHE.resolve())
print("CSV grupos:", CSV_GRUPOS.resolve())
print("Abra com:")
print("notepad previsualizacao_motor_sku_master_geral.txt")
