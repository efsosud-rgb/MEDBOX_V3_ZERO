"""Consultas do Dashboard Comercial (SEMPRE somente leitura do banco local).

Não fala com o Gmail. Lê exclusivamente as tabelas já persistidas:
- dashboard_vendas_historicas / dashboard_metas_vendedora / dashboard_metas_cliente
  (alimentadas pela planilha Fev-Mai, e futuramente por vendas reais via OC)
- gmail_cotacoes_itens / gmail_oc_itens / gmail_cotacao_resultado_itens
  (só existem depois que a Fase 6/7 — sincronização Gmail + correlação —
  rodar; até lá, os campos de cotado/perdido/itens críticos legitimamente
  retornam zero/vazio, não é bug).

Regra de negócio (fixada com o usuário): a apuração de VENDAS nunca
depende de correlação com cotação — vem sempre de dashboard_vendas_historicas
(planilha ou OC real). Já cotado/vencido/perdido só existe para os itens
que passaram por correlação segura em gmail_cotacao_resultado_itens.
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from core import banco

STATUS_GANHO = ("VENCIDO", "PARCIAL")


def _filtros_periodo(filtros: dict) -> tuple[int | None, int | None]:
    """Resolve (ano, mes_num) a partir dos filtros, com fallback para o mês
    mais recente que já tenha meta cadastrada e, na ausência disso, o mês
    corrente do servidor."""
    ano = filtros.get("ano")
    mes = filtros.get("mes")
    if ano and mes:
        return int(ano), int(mes)

    conn = banco.conectar()
    cursor = conn.cursor()
    cursor.execute("SELECT ano, mes_num FROM dashboard_metas_vendedora ORDER BY ano DESC, mes_num DESC LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    if row:
        return row["ano"], row["mes_num"]

    agora = datetime.now()
    return agora.year, agora.month


def _condicoes_data(filtros: dict, campo_data: str) -> tuple[list[str], list]:
    condicoes, params = [], []
    if filtros.get("vendedora"):
        condicoes.append("vendedora = ?")
        params.append(filtros["vendedora"])
    if filtros.get("cliente"):
        condicoes.append("cliente = ?")
        params.append(filtros["cliente"])
    if filtros.get("data_inicio"):
        condicoes.append(f"{campo_data} >= ?")
        params.append(filtros["data_inicio"])
    if filtros.get("data_fim"):
        condicoes.append(f"{campo_data} <= ?")
        params.append(filtros["data_fim"])
    return condicoes, params


def resumo_dashboard_comercial(filtros: dict | None = None) -> dict:
    filtros = filtros or {}
    ano, mes = _filtros_periodo(filtros)

    conn = banco.conectar()
    cursor = conn.cursor()

    condicoes, params = _condicoes_data(filtros, "ano || '-' || mes_num")
    where_vendas = (" WHERE " + " AND ".join(condicoes)) if condicoes else ""
    cursor.execute(f"SELECT COALESCE(SUM(valor_vendido), 0) AS total FROM dashboard_vendas_historicas{where_vendas}", params)
    total_vendido = cursor.fetchone()["total"]

    cursor.execute("SELECT COALESCE(SUM(valor_total_cotado), 0) AS total FROM gmail_cotacoes_itens")
    total_cotado = cursor.fetchone()["total"]

    cursor.execute("SELECT COALESCE(SUM(valor_total_cotado), 0) AS total FROM gmail_cotacao_resultado_itens WHERE status_resultado = 'PERDIDO'")
    total_perdido = cursor.fetchone()["total"]

    cursor.execute(
        "SELECT COALESCE(SUM(valor_total_vendido), 0) AS ganho, COALESCE(SUM(valor_total_cotado), 0) AS cotado, "
        "COUNT(*) AS total, SUM(CASE WHEN status_resultado IN ('VENCIDO','PARCIAL') THEN 1 ELSE 0 END) AS ganhos "
        "FROM gmail_cotacao_resultado_itens"
    )
    corr = cursor.fetchone()
    taxa_conversao_valor = round(100 * corr["ganho"] / corr["cotado"], 2) if corr["cotado"] else 0.0
    taxa_conversao_itens = round(100 * corr["ganhos"] / corr["total"], 2) if corr["total"] else 0.0

    cursor.execute("SELECT COUNT(*) AS total, COALESCE(SUM(valor_total_cotado), 0) AS valor FROM gmail_cotacao_resultado_itens WHERE item_critico = 'SIM'")
    criticos = cursor.fetchone()

    cursor.execute("SELECT COALESCE(SUM(valor_vendido), 0) AS total FROM dashboard_vendas_historicas WHERE ano = ? AND mes_num = ?", (ano, mes))
    vendas_mes_atual = cursor.fetchone()["total"]

    cursor.execute("SELECT COALESCE(SUM(meta_valor), 0) AS total FROM dashboard_metas_vendedora WHERE ano = ? AND mes_num = ?", (ano, mes))
    meta_mes_atual = cursor.fetchone()["total"]

    # Vendas por mês (para o bloco "Vendas por mês" do layout)
    cursor.execute(
        "SELECT ano, mes_num, mes_nome, COALESCE(SUM(valor_vendido), 0) AS total "
        "FROM dashboard_vendas_historicas GROUP BY ano, mes_num ORDER BY ano, mes_num"
    )
    vendas_por_mes = [dict(r) for r in cursor.fetchall()]

    # Comparativo por fonte (planilha Fev-Mai x vendas reais via Gmail/OC)
    cursor.execute(
        "SELECT fonte, COALESCE(SUM(valor_vendido), 0) AS total, COUNT(*) AS qtd "
        "FROM dashboard_vendas_historicas GROUP BY fonte"
    )
    por_fonte = [dict(r) for r in cursor.fetchall()]

    conn.close()

    atingimento_meta = round(100 * vendas_mes_atual / meta_mes_atual, 2) if meta_mes_atual else 0.0

    return {
        "ano_referencia": ano,
        "mes_referencia": mes,
        "total_cotado": round(total_cotado, 2),
        "total_vendido": round(total_vendido, 2),
        "total_perdido": round(total_perdido, 2),
        "taxa_conversao_valor": taxa_conversao_valor,
        "taxa_conversao_itens": taxa_conversao_itens,
        "itens_criticos": criticos["total"],
        "valor_itens_criticos": round(criticos["valor"], 2),
        "vendas_por_mes": vendas_por_mes,
        "por_fonte": por_fonte,
        "vendas_mes_atual": round(vendas_mes_atual, 2),
        "meta_mes_atual": round(meta_mes_atual, 2),
        "atingimento_meta": atingimento_meta,
    }


def _todas_vendedoras(cursor) -> list[str]:
    cursor.execute("""
        SELECT DISTINCT vendedora FROM (
            SELECT vendedora FROM dashboard_vendas_historicas
            UNION SELECT vendedora FROM dashboard_metas_vendedora
            UNION SELECT vendedora FROM gmail_cotacoes_itens WHERE vendedora IS NOT NULL
        ) ORDER BY vendedora
    """)
    return [r["vendedora"] for r in cursor.fetchall()]


def vendedores_dashboard_comercial(filtros: dict | None = None) -> list[dict]:
    filtros = filtros or {}
    ano, mes = _filtros_periodo(filtros)

    conn = banco.conectar()
    cursor = conn.cursor()
    resultado = []

    for vendedora in _todas_vendedoras(cursor):
        if filtros.get("vendedora") and filtros["vendedora"] != vendedora:
            continue

        cursor.execute("SELECT COALESCE(SUM(valor_vendido), 0) AS total FROM dashboard_vendas_historicas WHERE vendedora = ?", (vendedora,))
        valor_vendido = cursor.fetchone()["total"]

        cursor.execute("SELECT COALESCE(SUM(valor_vendido), 0) AS total FROM dashboard_vendas_historicas WHERE vendedora = ? AND ano = ? AND mes_num = ?", (vendedora, ano, mes))
        vendido_mes = cursor.fetchone()["total"]

        cursor.execute("SELECT COALESCE(SUM(valor_total_cotado), 0) AS total, COUNT(*) AS qtd FROM gmail_cotacoes_itens WHERE vendedora = ?", (vendedora,))
        cotado_row = cursor.fetchone()

        cursor.execute(
            "SELECT COALESCE(SUM(valor_total_cotado), 0) AS valor, COUNT(*) AS qtd FROM gmail_cotacao_resultado_itens "
            "WHERE vendedora = ? AND status_resultado = 'PERDIDO'", (vendedora,)
        )
        perdido_row = cursor.fetchone()

        cursor.execute(
            "SELECT COUNT(*) AS qtd FROM gmail_cotacao_resultado_itens WHERE vendedora = ? AND status_resultado IN ('VENCIDO','PARCIAL')", (vendedora,)
        )
        vendidos_row = cursor.fetchone()

        cursor.execute("SELECT COUNT(*) AS qtd FROM gmail_cotacao_resultado_itens WHERE vendedora = ? AND item_critico = 'SIM'", (vendedora,))
        criticos_row = cursor.fetchone()

        cursor.execute("SELECT meta_valor FROM dashboard_metas_vendedora WHERE vendedora = ? AND ano = ? AND mes_num = ?", (vendedora, ano, mes))
        meta_row = cursor.fetchone()
        meta_junho = meta_row["meta_valor"] if meta_row else 0.0

        resultado.append({
            "vendedora": vendedora,
            "valor_cotado": round(cotado_row["total"], 2),
            "valor_vendido": round(valor_vendido, 2),
            "valor_perdido": round(perdido_row["valor"], 2),
            "itens_cotados": cotado_row["qtd"],
            "itens_vendidos": vendidos_row["qtd"],
            "itens_perdidos": perdido_row["qtd"],
            "itens_criticos": criticos_row["qtd"],
            "meta_junho": round(meta_junho or 0.0, 2),
            "vendido_junho": round(vendido_mes, 2),
            "atingimento_meta": round(100 * vendido_mes / meta_junho, 2) if meta_junho else 0.0,
        })

    conn.close()
    return sorted(resultado, key=lambda x: -x["valor_vendido"])


def _todos_clientes(cursor) -> list[str]:
    cursor.execute("""
        SELECT DISTINCT cliente FROM (
            SELECT cliente FROM dashboard_vendas_historicas WHERE cliente IS NOT NULL
            UNION SELECT cliente FROM dashboard_metas_cliente
        ) ORDER BY cliente
    """)
    return [r["cliente"] for r in cursor.fetchall()]


def clientes_dashboard_comercial(filtros: dict | None = None) -> list[dict]:
    filtros = filtros or {}
    ano, mes = _filtros_periodo(filtros)

    conn = banco.conectar()
    cursor = conn.cursor()
    resultado = []

    for cliente in _todos_clientes(cursor):
        if filtros.get("cliente") and filtros["cliente"] != cliente:
            continue

        cursor.execute("SELECT COALESCE(SUM(valor_vendido), 0) AS total FROM dashboard_vendas_historicas WHERE cliente = ? AND ano = ? AND mes_num = ?", (cliente, ano, mes))
        valor_vendido_mes = cursor.fetchone()["total"]

        cursor.execute("SELECT meta_valor FROM dashboard_metas_cliente WHERE cliente = ? AND ano = ? AND mes_num = ?", (cliente, ano, mes))
        meta_row = cursor.fetchone()
        meta_junho = meta_row["meta_valor"] if meta_row else 0.0

        cursor.execute("SELECT COALESCE(SUM(valor_total_cotado), 0) AS total FROM gmail_cotacoes_itens WHERE cliente = ?", (cliente,))
        valor_cotado = cursor.fetchone()["total"]

        cursor.execute("SELECT COALESCE(SUM(valor_total_cotado), 0) AS total FROM gmail_cotacao_resultado_itens WHERE cliente = ? AND status_resultado = 'PERDIDO'", (cliente,))
        valor_perdido = cursor.fetchone()["total"]

        cursor.execute("SELECT COUNT(*) AS qtd FROM gmail_cotacao_resultado_itens WHERE cliente = ? AND item_critico = 'SIM'", (cliente,))
        itens_criticos = cursor.fetchone()["qtd"]

        resultado.append({
            "cliente": cliente,
            "valor_vendido_mes": round(valor_vendido_mes, 2),
            "meta_junho": round(meta_junho or 0.0, 2),
            "atingimento_meta": round(100 * valor_vendido_mes / meta_junho, 2) if meta_junho else 0.0,
            "valor_cotado": round(valor_cotado, 2),
            "valor_perdido": round(valor_perdido, 2),
            "itens_criticos": itens_criticos,
        })

    conn.close()
    return sorted(resultado, key=lambda x: -x["valor_vendido_mes"])


def itens_criticos_dashboard_comercial(filtros: dict | None = None) -> dict:
    filtros = filtros or {}
    conn = banco.conectar()
    cursor = conn.cursor()

    condicoes = ["item_critico = 'SIM'", "status_resultado = 'PERDIDO'"]
    params: list = []
    if filtros.get("vendedora"):
        condicoes.append("vendedora = ?")
        params.append(filtros["vendedora"])
    if filtros.get("cliente"):
        condicoes.append("cliente = ?")
        params.append(filtros["cliente"])
    where = " WHERE " + " AND ".join(condicoes)

    cursor.execute(f"SELECT DISTINCT vendedora FROM gmail_cotacao_resultado_itens{where} ORDER BY vendedora", params)
    vendedoras = [r["vendedora"] for r in cursor.fetchall()]

    top5_por_vendedora = {}
    for vendedora in vendedoras:
        cursor.execute(
            f"""SELECT descricao_item, sku_master, cliente, numero_cotacao, numero_oc,
                       quantidade_cotada, valor_total_cotado
                FROM gmail_cotacao_resultado_itens{where} AND vendedora = ?
                ORDER BY valor_total_cotado DESC LIMIT 5""",
            params + [vendedora],
        )
        top5_por_vendedora[vendedora] = [dict(r) for r in cursor.fetchall()]

    # Itens críticos repetidos em mais de um cliente (agrupado por descrição normalizada)
    cursor.execute(
        f"""SELECT descricao_item, sku_master, cliente,
                   SUM(quantidade_cotada) AS qtd, SUM(valor_total_cotado) AS valor
            FROM gmail_cotacao_resultado_itens{where}
            GROUP BY descricao_item, cliente""",
        params,
    )
    por_item_cliente = [dict(r) for r in cursor.fetchall()]
    conn.close()

    agregados: dict[str, dict] = {}
    for linha in por_item_cliente:
        chave = linha["descricao_item"] or linha["sku_master"] or ""
        if not chave:
            continue
        agregados.setdefault(chave, {
            "descricao_item": linha["descricao_item"],
            "sku_master": linha["sku_master"],
            "quantidade_total": 0.0,
            "valor_total_perdido": 0.0,
            "clientes_onde_aparece": [],
        })
        agregados[chave]["quantidade_total"] += linha["qtd"] or 0
        agregados[chave]["valor_total_perdido"] += linha["valor"] or 0
        if linha["cliente"] and linha["cliente"] not in agregados[chave]["clientes_onde_aparece"]:
            agregados[chave]["clientes_onde_aparece"].append(linha["cliente"])

    repetidos = [
        {
            **item,
            "quantidade_total": round(item["quantidade_total"], 2),
            "valor_total_perdido": round(item["valor_total_perdido"], 2),
            "quantidade_clientes": len(item["clientes_onde_aparece"]),
            "repetido_em_multiplos_clientes": "SIM" if len(item["clientes_onde_aparece"]) > 1 else "NAO",
        }
        for item in agregados.values() if len(item["clientes_onde_aparece"]) > 1
    ]
    repetidos.sort(key=lambda x: -x["valor_total_perdido"])

    return {
        "top5_por_vendedora": top5_por_vendedora,
        "itens_repetidos_multiplos_clientes": repetidos,
    }


def cotacoes_dashboard_comercial(filtros: dict | None = None) -> list[dict]:
    filtros = filtros or {}
    conn = banco.conectar()
    cursor = conn.cursor()

    condicoes, params = [], []
    if filtros.get("vendedora"):
        condicoes.append("vendedora = ?")
        params.append(filtros["vendedora"])
    if filtros.get("cliente"):
        condicoes.append("cliente = ?")
        params.append(filtros["cliente"])
    where = (" WHERE " + " AND ".join(condicoes)) if condicoes else ""

    cursor.execute(f"SELECT * FROM gmail_cotacoes_enviadas{where} ORDER BY data_cotacao DESC", params)
    cotacoes = [dict(r) for r in cursor.fetchall()]

    resultado = []
    for cot in cotacoes:
        numero = cot.get("numero_cotacao")
        cursor.execute("SELECT COUNT(*) AS qtd, COALESCE(SUM(valor_total_cotado), 0) AS valor FROM gmail_cotacoes_itens WHERE numero_cotacao = ?", (numero,))
        itens_cotados = cursor.fetchone()

        cursor.execute(
            "SELECT SUM(CASE WHEN status_resultado IN ('VENCIDO','PARCIAL') THEN 1 ELSE 0 END) AS vendidos, "
            "SUM(CASE WHEN status_resultado = 'PERDIDO' THEN 1 ELSE 0 END) AS perdidos, "
            "COALESCE(SUM(CASE WHEN status_resultado IN ('VENCIDO','PARCIAL') THEN valor_total_vendido ELSE 0 END), 0) AS valor_vendido, "
            "COALESCE(SUM(CASE WHEN status_resultado = 'PERDIDO' THEN valor_total_cotado ELSE 0 END), 0) AS valor_perdido "
            "FROM gmail_cotacao_resultado_itens WHERE numero_cotacao = ?",
            (numero,),
        )
        resultado_itens = cursor.fetchone()

        valor_cotado = itens_cotados["valor"] or 0
        valor_vendido = resultado_itens["valor_vendido"] or 0

        resultado.append({
            "numero_cotacao": numero,
            "cliente": cot.get("cliente"),
            "vendedora": cot.get("vendedora"),
            "data": cot.get("data_cotacao"),
            "qtd_itens_cotados": itens_cotados["qtd"],
            "qtd_itens_vendidos": resultado_itens["vendidos"] or 0,
            "qtd_itens_perdidos": resultado_itens["perdidos"] or 0,
            "valor_cotado": round(valor_cotado, 2),
            "valor_vendido": round(valor_vendido, 2),
            "valor_perdido": round(resultado_itens["valor_perdido"] or 0, 2),
            "taxa_conversao": round(100 * valor_vendido / valor_cotado, 2) if valor_cotado else 0.0,
        })

    conn.close()
    return resultado
