"""Consultas do Dashboard Comercial.

Somente leitura do banco local. Não chama Gmail e não altera dados.
Esta versão consolida clientes por sigla de projeto e aplica filtros em Python
para evitar divergências de nomes longos, acentos e abreviações.
"""

from __future__ import annotations

import calendar
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parents[2]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from core import banco  # noqa: E402

try:
    from cliente_aliases import cliente_match, normalizar_texto, sigla_cliente
except ImportError:
    from scripts.gmail_cotacoes.cliente_aliases import cliente_match, normalizar_texto, sigla_cliente

MESES_PT = {
    1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril",
    5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto",
    9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro",
}
STATUS_GANHO = ("VENCIDO", "PARCIAL")


def _to_int(valor: Any) -> int | None:
    try:
        if valor in (None, ""):
            return None
        return int(valor)
    except (TypeError, ValueError):
        return None


def _to_float(valor: Any) -> float:
    try:
        return float(valor or 0)
    except (TypeError, ValueError):
        return 0.0


def _parse_data_iso(valor: Any) -> date | None:
    if not valor:
        return None
    try:
        return datetime.strptime(str(valor)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _mes_intervalo(ano: int, mes: int) -> tuple[date, date]:
    ultimo = calendar.monthrange(ano, mes)[1]
    return date(ano, mes, 1), date(ano, mes, ultimo)


def _filtros_periodo(filtros: dict) -> tuple[int | None, int | None]:
    ano = _to_int(filtros.get("ano"))
    mes = _to_int(filtros.get("mes"))
    if ano and mes:
        return ano, mes

    conn = banco.conectar()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT ano, mes_num
        FROM dashboard_metas_vendedora
        ORDER BY ano DESC, mes_num DESC
        LIMIT 1
    """)
    row = cursor.fetchone()
    conn.close()

    if row:
        return int(row["ano"]), int(row["mes_num"])

    agora = datetime.now()
    return agora.year, agora.month


def _periodo_passou(row: dict, filtros: dict, usar_mes: bool = True, usar_datas: bool = True) -> bool:
    ano_f = _to_int(filtros.get("ano"))
    mes_f = _to_int(filtros.get("mes"))
    ano = _to_int(row.get("ano"))
    mes = _to_int(row.get("mes_num"))

    if ano_f and ano != ano_f:
        return False
    if usar_mes and mes_f and mes != mes_f:
        return False

    if usar_datas and filtros.get("data_inicio") and filtros.get("data_fim") and ano and mes:
        inicio_f = _parse_data_iso(filtros.get("data_inicio"))
        fim_f = _parse_data_iso(filtros.get("data_fim"))
        if inicio_f and fim_f:
            inicio_mes, fim_mes = _mes_intervalo(ano, mes)
            if fim_mes < inicio_f or inicio_mes > fim_f:
                return False

    return True


def _base_match(row: dict, filtros: dict, usar_mes: bool = True, usar_datas: bool = True) -> bool:
    if filtros.get("vendedora") and str(row.get("vendedora") or "").upper() != str(filtros["vendedora"]).upper():
        return False
    if filtros.get("cliente") and not cliente_match(filtros["cliente"], row.get("cliente")):
        return False
    return _periodo_passou(row, filtros, usar_mes=usar_mes, usar_datas=usar_datas)


def _rows_vendas(filtros: dict, usar_mes: bool = True, usar_datas: bool = True) -> list[dict]:
    conn = banco.conectar()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM dashboard_vendas_historicas")
    rows = []
    for r in cursor.fetchall():
        d = dict(r)
        d["cliente_original"] = d.get("cliente")
        d["cliente"] = sigla_cliente(d.get("cliente"))
        d["valor_vendido"] = _to_float(d.get("valor_vendido"))
        if _base_match(d, filtros, usar_mes=usar_mes, usar_datas=usar_datas):
            rows.append(d)
    conn.close()
    return rows


def _agrupar_soma(rows: list[dict], chave: str, campo_valor: str) -> dict[str, float]:
    out: dict[str, float] = defaultdict(float)
    for r in rows:
        out[str(r.get(chave) or "")] += _to_float(r.get(campo_valor))
    return dict(out)


def _mes_key(ano: int, mes: int) -> int:
    return int(ano) * 12 + int(mes)


def _ultimo_mes_finalizado(hoje: date | None = None) -> tuple[int, int]:
    """Retorna o último mês completamente fechado."""
    hoje = hoje or date.today()
    primeiro_dia_mes_atual = date(hoje.year, hoje.month, 1)
    ultimo_dia_mes_anterior = primeiro_dia_mes_atual - timedelta(days=1)
    return ultimo_dia_mes_anterior.year, ultimo_dia_mes_anterior.month


def _gerar_tendencia_vendas(vendas_por_mes: list[dict], ano_final: int = 2027, mes_final: int = 7) -> list[dict]:
    """Gera série mensal real + tendência até Jul/2027 usando somente meses finalizados."""
    if not vendas_por_mes:
        return []

    ult_ano, ult_mes = _ultimo_mes_finalizado()
    limite_fechado = _mes_key(ult_ano, ult_mes)

    reais = {
        (int(r["ano"]), int(r["mes_num"])): _to_float(r.get("total"))
        for r in vendas_por_mes
        if _mes_key(int(r["ano"]), int(r["mes_num"])) <= limite_fechado
    }

    if not reais:
        return []

    ordenados = sorted(reais.items())
    inicio_ano, inicio_mes = ordenados[0][0]

    meses = []
    ano, mes = inicio_ano, inicio_mes
    while (ano, mes) <= (ano_final, mes_final):
        meses.append((ano, mes))
        mes += 1
        if mes > 12:
            mes = 1
            ano += 1

    pontos = []
    for idx, chave in enumerate(sorted(reais)):
        pontos.append((idx, reais[chave]))

    if len(pontos) >= 2:
        n = len(pontos)
        sx = sum(p[0] for p in pontos)
        sy = sum(p[1] for p in pontos)
        sxx = sum(p[0] * p[0] for p in pontos)
        sxy = sum(p[0] * p[1] for p in pontos)
        denom = n * sxx - sx * sx
        slope = (n * sxy - sx * sy) / denom if denom else 0.0
        intercept = (sy - slope * sx) / n
    else:
        slope = 0.0
        intercept = pontos[0][1] if pontos else 0.0

    saida = []
    for idx, (ano, mes) in enumerate(meses):
        real = reais.get((ano, mes))
        tendencia = max(0.0, intercept + slope * idx)
        fechado = _mes_key(ano, mes) <= limite_fechado
        saida.append({
            "ano": ano,
            "mes_num": mes,
            "mes_nome": MESES_PT.get(mes, str(mes)),
            "label": f"{MESES_PT.get(mes, str(mes))[:3]}/{str(ano)[-2:]}",
            "real": round(real, 2) if real is not None else None,
            "tendencia": round(tendencia, 2),
            "tipo": "REAL" if real is not None else "PROJETADO",
            "mes_fechado": fechado,
        })

    return saida


def _meta_progressiva_por_chave(
    filtros: dict,
    ano: int,
    mes: int,
    chave: str,
) -> dict[str, float]:
    """
    Meta = média dos 2 maiores meses finalizados anteriores ao mês analisado + 15%.

    Como sempre usa os 2 maiores históricos disponíveis até o período base,
    a meta nunca diminui; só aumenta quando um novo mês entra entre os 2 maiores.
    """
    filtros_base = dict(filtros)
    filtros_base.pop("mes", None)
    filtros_base.pop("data_inicio", None)
    filtros_base.pop("data_fim", None)

    vendas = _rows_vendas(filtros_base, usar_mes=False, usar_datas=False)

    ult_ano, ult_mes = _ultimo_mes_finalizado()
    limite_base = min(_mes_key(ano, mes) - 1, _mes_key(ult_ano, ult_mes))

    por_chave_mes: dict[str, dict[tuple[int, int], float]] = defaultdict(lambda: defaultdict(float))

    for r in vendas:
        r_ano = _to_int(r.get("ano"))
        r_mes = _to_int(r.get("mes_num"))
        if not r_ano or not r_mes:
            continue
        if _mes_key(r_ano, r_mes) > limite_base:
            continue

        nome = str(r.get(chave) or "").strip()
        if not nome:
            continue

        por_chave_mes[nome][(r_ano, r_mes)] += _to_float(r.get("valor_vendido"))

    metas: dict[str, float] = {}
    for nome, meses in por_chave_mes.items():
        maiores = sorted(meses.values(), reverse=True)[:2]
        if not maiores:
            metas[nome] = 0.0
            continue
        media = sum(maiores) / len(maiores)
        metas[nome] = round(media * 1.15, 2)

    return metas


def _metas_vendedora(filtros: dict, ano: int, mes: int) -> dict[str, float]:
    return _meta_progressiva_por_chave(filtros, ano, mes, "vendedora")


def _metas_cliente(filtros: dict, ano: int, mes: int) -> dict[str, float]:
    return _meta_progressiva_por_chave(filtros, ano, mes, "cliente")


def _cotacao_resultado_rows(filtros: dict) -> list[dict]:
    conn = banco.conectar()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM gmail_cotacao_resultado_itens")
    rows = []
    for r in cursor.fetchall():
        d = dict(r)
        d["cliente_original"] = d.get("cliente")
        d["cliente"] = sigla_cliente(d.get("cliente"))
        if filtros.get("vendedora") and str(d.get("vendedora") or "").upper() != str(filtros["vendedora"]).upper():
            continue
        if filtros.get("cliente") and not cliente_match(filtros["cliente"], d.get("cliente")):
            continue
        if filtros.get("status_resultado") and d.get("status_resultado") != filtros["status_resultado"]:
            continue
        if filtros.get("item_critico") and d.get("item_critico") != filtros["item_critico"]:
            continue
        rows.append(d)
    conn.close()
    return rows


def resumo_dashboard_comercial(filtros: dict | None = None) -> dict:
    filtros = filtros or {}
    ano, mes = _filtros_periodo(filtros)

    vendas_periodo = _rows_vendas(filtros, usar_mes=True, usar_datas=True)
    vendas_tendencia = _rows_vendas(filtros, usar_mes=False, usar_datas=False)
    resultados = _cotacao_resultado_rows(filtros)

    total_vendido = sum(r["valor_vendido"] for r in vendas_periodo)
    total_cotado = sum(_to_float(r.get("valor_total_cotado")) for r in resultados)
    total_perdido = sum(_to_float(r.get("valor_total_cotado")) for r in resultados if r.get("status_resultado") == "PERDIDO")
    ganho_valor = sum(_to_float(r.get("valor_total_vendido")) for r in resultados if r.get("status_resultado") in STATUS_GANHO)
    ganhos_itens = sum(1 for r in resultados if r.get("status_resultado") in STATUS_GANHO)

    metas_vend = _metas_vendedora(filtros, ano, mes)
    metas_cli = _metas_cliente(filtros, ano, mes)

    if filtros.get("cliente"):
        meta_mes_atual = sum(metas_cli.values())
    else:
        meta_mes_atual = sum(metas_vend.values())

    por_mes: dict[tuple[int, int], float] = defaultdict(float)
    for r in vendas_tendencia:
        por_mes[(int(r["ano"]), int(r["mes_num"]))] += r["valor_vendido"]

    vendas_por_mes = [
        {"ano": a, "mes_num": m, "mes_nome": MESES_PT.get(m, str(m)), "total": round(v, 2)}
        for (a, m), v in sorted(por_mes.items())
    ]

    por_fonte: dict[str, dict] = {}
    for r in vendas_periodo:
        fonte = r.get("fonte") or "SEM_FONTE"
        por_fonte.setdefault(fonte, {"fonte": fonte, "total": 0.0, "qtd": 0})
        por_fonte[fonte]["total"] += r["valor_vendido"]
        por_fonte[fonte]["qtd"] += 1

    criticos = [r for r in resultados if r.get("item_critico") == "SIM"]

    return {
        "ano_referencia": ano,
        "mes_referencia": mes,
        "total_cotado": round(total_cotado, 2),
        "total_vendido": round(total_vendido, 2),
        "total_perdido": round(total_perdido, 2),
        "taxa_conversao_valor": round(100 * ganho_valor / total_cotado, 2) if total_cotado else 0.0,
        "taxa_conversao_itens": round(100 * ganhos_itens / len(resultados), 2) if resultados else 0.0,
        "itens_criticos": len(criticos),
        "valor_itens_criticos": round(sum(_to_float(r.get("valor_total_cotado")) for r in criticos), 2),
        "vendas_por_mes": vendas_por_mes,
        "tendencia_vendas": _gerar_tendencia_vendas(vendas_por_mes, 2027, 7),
        "por_fonte": [
            {"fonte": k, "total": round(v["total"], 2), "qtd": v["qtd"]}
            for k, v in sorted(por_fonte.items())
        ],
        "vendas_mes_atual": round(total_vendido, 2),
        "meta_mes_atual": round(meta_mes_atual, 2),
        "atingimento_meta": round(100 * total_vendido / meta_mes_atual, 2) if meta_mes_atual else 0.0,
    }


def vendedores_dashboard_comercial(filtros: dict | None = None) -> list[dict]:
    filtros = filtros or {}
    ano, mes = _filtros_periodo(filtros)

    vendas_periodo = _rows_vendas(filtros, usar_mes=True, usar_datas=True)
    vendas_total = _rows_vendas(filtros, usar_mes=False, usar_datas=False)
    resultados = _cotacao_resultado_rows(filtros)
    metas = _metas_vendedora(filtros, ano, mes)

    nomes = set(metas)
    nomes.update(r.get("vendedora") for r in vendas_periodo if r.get("vendedora"))
    nomes.update(r.get("vendedora") for r in vendas_total if r.get("vendedora"))
    nomes.update(r.get("vendedora") for r in resultados if r.get("vendedora"))

    saida = []
    for vend in sorted(nomes):
        if filtros.get("vendedora") and str(filtros["vendedora"]).upper() != str(vend).upper():
            continue
        vendas_vend_periodo = [r for r in vendas_periodo if r.get("vendedora") == vend]
        vendas_vend_total = [r for r in vendas_total if r.get("vendedora") == vend]
        res_vend = [r for r in resultados if r.get("vendedora") == vend]
        vendido_mes = sum(r["valor_vendido"] for r in vendas_vend_periodo)
        vendido_total = sum(r["valor_vendido"] for r in vendas_vend_total)
        meta = metas.get(vend, 0.0)

        saida.append({
            "vendedora": vend,
            "valor_cotado": round(sum(_to_float(r.get("valor_total_cotado")) for r in res_vend), 2),
            "valor_vendido": round(vendido_total, 2),
            "valor_perdido": round(sum(_to_float(r.get("valor_total_cotado")) for r in res_vend if r.get("status_resultado") == "PERDIDO"), 2),
            "itens_cotados": len(res_vend),
            "itens_vendidos": sum(1 for r in res_vend if r.get("status_resultado") in STATUS_GANHO),
            "itens_perdidos": sum(1 for r in res_vend if r.get("status_resultado") == "PERDIDO"),
            "itens_criticos": sum(1 for r in res_vend if r.get("item_critico") == "SIM"),
            "meta_junho": round(meta, 2),
            "vendido_junho": round(vendido_mes, 2),
            "atingimento_meta": round(100 * vendido_mes / meta, 2) if meta else 0.0,
        })

    return sorted(saida, key=lambda x: (-x["vendido_junho"], x["vendedora"]))


def clientes_dashboard_comercial(filtros: dict | None = None) -> list[dict]:
    filtros = filtros or {}
    ano, mes = _filtros_periodo(filtros)

    vendas_periodo = _rows_vendas(filtros, usar_mes=True, usar_datas=True)
    resultados = _cotacao_resultado_rows(filtros)
    metas = _metas_cliente(filtros, ano, mes)

    nomes = set(metas)
    nomes.update(r.get("cliente") for r in vendas_periodo if r.get("cliente"))
    nomes.update(r.get("cliente") for r in resultados if r.get("cliente"))

    saida = []
    for cliente in sorted(nomes):
        if filtros.get("cliente") and not cliente_match(filtros["cliente"], cliente):
            continue

        vendas_cli = [r for r in vendas_periodo if r.get("cliente") == cliente]
        res_cli = [r for r in resultados if r.get("cliente") == cliente]
        vendido = sum(r["valor_vendido"] for r in vendas_cli)
        meta = metas.get(cliente, 0.0)

        saida.append({
            "cliente": cliente,
            "valor_vendido_mes": round(vendido, 2),
            "meta_junho": round(meta, 2),
            "atingimento_meta": round(100 * vendido / meta, 2) if meta else 0.0,
            "valor_cotado": round(sum(_to_float(r.get("valor_total_cotado")) for r in res_cli), 2),
            "valor_perdido": round(sum(_to_float(r.get("valor_total_cotado")) for r in res_cli if r.get("status_resultado") == "PERDIDO"), 2),
            "itens_criticos": sum(1 for r in res_cli if r.get("item_critico") == "SIM"),
        })

    return sorted(saida, key=lambda x: (-x["valor_vendido_mes"], x["cliente"]))


def itens_criticos_dashboard_comercial(filtros: dict | None = None) -> dict:
    filtros = filtros or {}
    rows = [
        r for r in _cotacao_resultado_rows(filtros)
        if r.get("item_critico") == "SIM" and r.get("status_resultado") == "PERDIDO"
    ]

    por_vendedora: dict[str, list[dict]] = defaultdict(list)
    repetidos: dict[str, dict] = {}

    for r in rows:
        vend = r.get("vendedora") or "SEM_VENDEDORA"
        item = {
            "descricao_item": r.get("descricao_item") or "",
            "sku_master": r.get("sku_master") or "",
            "cliente": r.get("cliente") or "",
            "numero_cotacao": r.get("numero_cotacao") or "",
            "quantidade_cotada": r.get("quantidade_cotada") or 0,
            "valor_total_cotado": round(_to_float(r.get("valor_total_cotado")), 2),
        }
        por_vendedora[vend].append(item)

        chave = normalizar_texto(r.get("sku_master") or r.get("descricao_item") or "")
        if chave:
            rep = repetidos.setdefault(chave, {
                "descricao_item": r.get("descricao_item") or "",
                "sku_master": r.get("sku_master") or "",
                "quantidade_total": 0,
                "valor_total_perdido": 0.0,
                "clientes_onde_aparece": set(),
            })
            rep["quantidade_total"] += _to_float(r.get("quantidade_cotada"))
            rep["valor_total_perdido"] += _to_float(r.get("valor_total_cotado"))
            rep["clientes_onde_aparece"].add(r.get("cliente") or "")

    top5 = {}
    for vend, itens in por_vendedora.items():
        top5[vend] = sorted(itens, key=lambda x: -_to_float(x["valor_total_cotado"]))[:5]

    repetidos_saida = []
    for rep in repetidos.values():
        clientes = sorted(c for c in rep["clientes_onde_aparece"] if c)
        if len(clientes) < 2:
            continue
        repetidos_saida.append({
            "descricao_item": rep["descricao_item"],
            "sku_master": rep["sku_master"],
            "quantidade_total": round(rep["quantidade_total"], 2),
            "valor_total_perdido": round(rep["valor_total_perdido"], 2),
            "quantidade_clientes": len(clientes),
            "clientes_onde_aparece": clientes,
        })

    return {
        "top5_por_vendedora": top5,
        "itens_repetidos_multiplos_clientes": sorted(repetidos_saida, key=lambda x: -x["valor_total_perdido"])[:50],
    }


def cotacoes_dashboard_comercial(filtros: dict | None = None) -> list[dict]:
    filtros = filtros or {}
    rows = _cotacao_resultado_rows(filtros)
    agrupado: dict[tuple, dict] = {}

    for r in rows:
        chave = (
            r.get("numero_cotacao") or "SEM_COTACAO",
            r.get("cliente") or "SEM_CLIENTE",
            r.get("vendedora") or "SEM_VENDEDORA",
            r.get("data_cotacao") or "",
        )
        g = agrupado.setdefault(chave, {
            "numero_cotacao": chave[0],
            "cliente": chave[1],
            "vendedora": chave[2],
            "data": chave[3],
            "qtd_itens_cotados": 0,
            "qtd_itens_vendidos": 0,
            "qtd_itens_perdidos": 0,
            "valor_cotado": 0.0,
            "valor_vendido": 0.0,
            "valor_perdido": 0.0,
        })
        g["qtd_itens_cotados"] += 1
        g["valor_cotado"] += _to_float(r.get("valor_total_cotado"))
        if r.get("status_resultado") in STATUS_GANHO:
            g["qtd_itens_vendidos"] += 1
            g["valor_vendido"] += _to_float(r.get("valor_total_vendido"))
        if r.get("status_resultado") == "PERDIDO":
            g["qtd_itens_perdidos"] += 1
            g["valor_perdido"] += _to_float(r.get("valor_total_cotado"))

    saida = []
    for g in agrupado.values():
        g["valor_cotado"] = round(g["valor_cotado"], 2)
        g["valor_vendido"] = round(g["valor_vendido"], 2)
        g["valor_perdido"] = round(g["valor_perdido"], 2)
        g["taxa_conversao"] = round(100 * g["valor_vendido"] / g["valor_cotado"], 2) if g["valor_cotado"] else 0.0
        saida.append(g)

    return sorted(saida, key=lambda x: (-x["valor_cotado"], x["cliente"]))[:300]
