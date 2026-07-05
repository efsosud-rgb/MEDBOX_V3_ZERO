"""Correlação e-mail cotação <-> e-mail pedido, e cruzamento de itens.

Duas responsabilidades bem separadas:

1. calcular_score_email(...): decide o quão confiável é dizer que um
   e-mail no marcador PEDIDO corresponde a um e-mail de cotação de uma
   vendedora (JESSICA/STHEFANY/PAMELA/LAYANE). Nunca depende só do
   assunto ser igual — combina cliente, categoria, mês, número de
   cotação, termos fortes do assunto, proximidade de data e nomes de
   anexo.

2. cruzar_itens(...): compara item a item a proposta cotada com a Ordem
   de Compra, usando similaridade textual (rapidfuzz) E o perfil técnico
   (perfil_tecnico.py) para nunca marcar GANHO automático quando há
   conflito técnico (calibre, volume, tamanho etc. diferentes).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from rapidfuzz import fuzz

import config
from perfil_tecnico import comparar_perfis, contar_atributos_comparaveis, extrair_perfil, normalizar_texto, score_tecnico


# ---------------------------------------------------------------------------
# Score composto de correlação e-mail cotação <-> e-mail pedido
# ---------------------------------------------------------------------------

@dataclass
class ScoreEmail:
    score_total: float
    score_assunto: float
    score_cliente: float
    score_categoria: float
    score_mes: float
    score_data: float
    score_itens: float
    confianca: str
    motivo: str


def _score_texto_simples(a: str | None, b: str | None) -> float:
    if not a or not b:
        return 0.0
    return float(fuzz.token_sort_ratio(normalizar_texto(a), normalizar_texto(b)))


def _score_cliente(cliente_caso: str, assunto_pedido: str, cliente_pedido: str | None) -> float:
    alvo = normalizar_texto(cliente_caso)
    if not alvo:
        return 0.0
    if cliente_pedido and normalizar_texto(cliente_pedido) == alvo:
        return 100.0
    if alvo in normalizar_texto(assunto_pedido):
        return 100.0
    return _score_texto_simples(cliente_caso, cliente_pedido or assunto_pedido)


def _score_categoria(categoria: str, assunto_pedido: str) -> float:
    alvo = normalizar_texto(categoria)
    if not alvo:
        return 0.0
    return 100.0 if alvo in normalizar_texto(assunto_pedido) else _score_texto_simples(categoria, assunto_pedido)


def _score_mes(mes_referencia: str, assunto_pedido: str) -> float:
    alvo = normalizar_texto(mes_referencia)
    if not alvo:
        return 0.0
    if alvo in normalizar_texto(assunto_pedido):
        return 100.0
    # tenta casar só o mês (ignorando o ano), ex.: "JULHO 26" -> "JULHO"
    mes_only = alvo.split()[0] if alvo.split() else alvo
    return 100.0 if mes_only in normalizar_texto(assunto_pedido) else 0.0


def _score_numero_cotacao(numero_cotacao: str, texto_pedido: str) -> float:
    if not numero_cotacao:
        return 0.0
    alvo = numero_cotacao.replace(".", "").replace("-", "")
    texto_norm = texto_pedido.replace(".", "").replace("-", "")
    return 100.0 if alvo and alvo in texto_norm else 0.0


def _score_proximidade_data(data_a: str | None, data_b: str | None, janela_dias: int) -> float:
    if not data_a or not data_b:
        return 50.0  # neutro: sem dado suficiente para penalizar ou premiar
    try:
        fmt = "%Y-%m-%d" if "-" in data_a[:5] else "%d/%m/%Y"
        dt_a = datetime.strptime(data_a[:10], fmt)
        fmt_b = "%Y-%m-%d" if "-" in data_b[:5] else "%d/%m/%Y"
        dt_b = datetime.strptime(data_b[:10], fmt_b)
    except ValueError:
        return 50.0
    diff_dias = abs((dt_b - dt_a).days)
    if diff_dias > janela_dias:
        return 0.0
    return 100.0 * (1 - diff_dias / janela_dias)


def _score_itens(itens_cotados_desc: list[str], itens_oc_desc: list[str]) -> float:
    if not itens_cotados_desc or not itens_oc_desc:
        return 50.0  # neutro: ainda não temos os dois lados parseados
    acertos = 0
    for desc_cotada in itens_cotados_desc:
        melhor = max((fuzz.token_sort_ratio(normalizar_texto(desc_cotada), normalizar_texto(d)) for d in itens_oc_desc), default=0)
        if melhor >= config.LIMIAR_SIMILARIDADE_REVISAR:
            acertos += 1
    return 100.0 * acertos / len(itens_cotados_desc)


def classificar_confianca_email(score_total: float) -> str:
    if score_total >= config.LIMIAR_CONFIANCA_ALTA:
        return "ALTA"
    if score_total >= config.LIMIAR_CONFIANCA_MEDIA:
        return "MEDIA"
    if score_total >= config.LIMIAR_CONFIANCA_BAIXA:
        return "BAIXA"
    return "REVISAR"


def calcular_score_email(
    *,
    cliente: str,
    categoria: str,
    mes_referencia: str,
    numero_cotacao: str,
    assunto_cotacao: str,
    assunto_pedido: str,
    data_cotacao: str | None = None,
    data_pedido: str | None = None,
    itens_cotados_desc: list[str] | None = None,
    itens_oc_desc: list[str] | None = None,
    nomes_anexos: list[str] | None = None,
) -> ScoreEmail:
    texto_pedido_completo = f"{assunto_pedido} {' '.join(nomes_anexos or [])}"

    s_cliente = _score_cliente(cliente, assunto_pedido, None)
    s_categoria = _score_categoria(categoria, assunto_pedido)
    s_mes = _score_mes(mes_referencia, assunto_pedido)
    s_numero = _score_numero_cotacao(numero_cotacao, texto_pedido_completo)
    s_assunto = _score_texto_simples(assunto_cotacao, assunto_pedido)
    s_data = _score_proximidade_data(data_cotacao, data_pedido, config.JANELA_DIAS_PROXIMIDADE)
    s_itens = _score_itens(itens_cotados_desc or [], itens_oc_desc or [])

    pesos = config.PESOS_SCORE_EMAIL
    # número da cotação, quando presente no assunto/anexos do pedido, é o sinal mais forte
    componentes = {
        "cliente": (s_cliente, pesos["cliente"]),
        "categoria": (s_categoria, pesos["categoria"]),
        "mes": (s_mes, pesos["mes"]),
        "numero_cotacao": (max(s_numero, s_assunto if numero_cotacao in assunto_pedido else 0), pesos["numero_cotacao"]),
        "assunto": (s_assunto, pesos["assunto"]),
        "data": (s_data, pesos["data"]),
        "itens": (s_itens, pesos["itens"]),
    }
    soma_pesos = sum(p for _, p in componentes.values())
    score_total = sum(s * p for s, p in componentes.values()) / soma_pesos if soma_pesos else 0.0

    confianca = classificar_confianca_email(score_total)

    motivos = []
    if s_cliente >= 90:
        motivos.append("cliente confere")
    if s_numero >= 90:
        motivos.append("número da cotação encontrado no pedido")
    if s_mes >= 90:
        motivos.append("mês de referência confere")
    if s_categoria >= 90:
        motivos.append("categoria confere")
    if s_data < 20:
        motivos.append("datas distantes entre cotação e pedido")
    if not motivos:
        motivos.append("correlação baseada principalmente em similaridade textual do assunto")
    motivo = "; ".join(motivos)

    return ScoreEmail(
        score_total=round(score_total, 2),
        score_assunto=round(s_assunto, 2),
        score_cliente=round(s_cliente, 2),
        score_categoria=round(s_categoria, 2),
        score_mes=round(s_mes, 2),
        score_data=round(s_data, 2),
        score_itens=round(s_itens, 2),
        confianca=confianca,
        motivo=motivo,
    )


# ---------------------------------------------------------------------------
# Cruzamento de itens (proposta cotada x Ordem de Compra)
# ---------------------------------------------------------------------------

@dataclass
class ItemCruzado:
    item_cotacao: int
    descricao_cotada: str
    unidade: str
    qtd_cotada: float
    valor_unitario_cotado: float
    valor_total_cotado: float
    item_oc: int | None
    descricao_oc: str | None
    qtd_ganha: float | None
    valor_unitario_ganho: float | None
    valor_total_ganho: float | None
    status_item: str
    score_comparacao: float
    score_texto: float
    score_tecnico: float
    conflito_tecnico: bool
    confianca_match_item: str
    motivo_match_item: str


def _classificar_confianca_item(score_comparacao: float, conflito: bool) -> str:
    if conflito:
        return "BAIXA"
    if score_comparacao >= 85:
        return "ALTA"
    if score_comparacao >= config.LIMIAR_SIMILARIDADE_REVISAR:
        return "MEDIA"
    return "BAIXA"


def cruzar_itens(itens_cotados: list, itens_oc: list) -> list[ItemCruzado]:
    """`itens_cotados` vem de parser_excel_cotacao.ItemCotado, `itens_oc` de parser_pdf_oc.ItemOC."""
    resultado: list[ItemCruzado] = []
    usados: set[int] = set()

    perfis_oc = [extrair_perfil(it.descricao) for it in itens_oc]

    for item in itens_cotados:
        sem_valor = not item.valor_unitario or not item.valor_total
        if sem_valor:
            resultado.append(ItemCruzado(
                item_cotacao=item.numero_item, descricao_cotada=item.descricao, unidade=item.unidade,
                qtd_cotada=item.quantidade, valor_unitario_cotado=item.valor_unitario or 0.0,
                valor_total_cotado=item.valor_total or 0.0,
                item_oc=None, descricao_oc=None, qtd_ganha=None, valor_unitario_ganho=None, valor_total_ganho=None,
                status_item="NAO_COTADO", score_comparacao=0.0, score_texto=0.0, score_tecnico=0.0,
                conflito_tecnico=False, confianca_match_item="ALTA",
                motivo_match_item="item sem valor cotado (zero/vazio/-)",
            ))
            continue

        perfil_cotado = extrair_perfil(item.descricao)
        melhor_idx = None
        melhor_score_texto = 0.0
        for idx, item_oc in enumerate(itens_oc):
            if idx in usados:
                continue
            s = fuzz.token_sort_ratio(normalizar_texto(item.descricao), normalizar_texto(item_oc.descricao))
            if s > melhor_score_texto:
                melhor_score_texto = s
                melhor_idx = idx

        if melhor_idx is None or melhor_score_texto < config.LIMIAR_SIMILARIDADE_REVISAR:
            resultado.append(ItemCruzado(
                item_cotacao=item.numero_item, descricao_cotada=item.descricao, unidade=item.unidade,
                qtd_cotada=item.quantidade, valor_unitario_cotado=item.valor_unitario,
                valor_total_cotado=item.valor_total,
                item_oc=None, descricao_oc=None, qtd_ganha=None, valor_unitario_ganho=None, valor_total_ganho=None,
                status_item="PERDIDO", score_comparacao=round(melhor_score_texto, 2), score_texto=round(melhor_score_texto, 2),
                score_tecnico=0.0, conflito_tecnico=False, confianca_match_item="ALTA",
                motivo_match_item="nenhum item correspondente encontrado na Ordem de Compra",
            ))
            continue

        item_oc = itens_oc[melhor_idx]
        perfil_oc = perfis_oc[melhor_idx]
        conflito, motivos_conflito = comparar_perfis(perfil_cotado, perfil_oc)
        s_tecnico = score_tecnico(perfil_cotado, perfil_oc)
        # só pesa o score técnico quando há atributo comparável nos dois lados —
        # senão o valor "neutro" (50) penaliza injustamente itens sem atributo
        # técnico identificável (ex.: descrições sem calibre/volume/tamanho).
        if contar_atributos_comparaveis(perfil_cotado, perfil_oc) > 0:
            score_comparacao = 0.6 * melhor_score_texto + 0.4 * s_tecnico
        else:
            score_comparacao = melhor_score_texto

        if conflito:
            usados.add(melhor_idx)
            if melhor_score_texto >= config.LIMIAR_SIMILARIDADE_TEXTO:
                status = "POSSIVEL_GANHO_REVISAR"
                motivo = "texto muito parecido, mas perfil técnico diverge: " + "; ".join(motivos_conflito)
            else:
                status = "PERDIDO"
                motivo = "produto tecnicamente diferente: " + "; ".join(motivos_conflito)
        elif score_comparacao >= config.LIMIAR_SIMILARIDADE_TEXTO:
            usados.add(melhor_idx)
            status = "GANHO"
            motivo = "descrição e perfil técnico compatíveis"
        else:
            usados.add(melhor_idx)
            status = "POSSIVEL_GANHO_REVISAR"
            motivo = "similaridade abaixo do limiar de confirmação — revisar manualmente"

        confianca = _classificar_confianca_item(score_comparacao, conflito)

        resultado.append(ItemCruzado(
            item_cotacao=item.numero_item, descricao_cotada=item.descricao, unidade=item.unidade,
            qtd_cotada=item.quantidade, valor_unitario_cotado=item.valor_unitario, valor_total_cotado=item.valor_total,
            item_oc=item_oc.numero_item, descricao_oc=item_oc.descricao,
            qtd_ganha=item_oc.quantidade, valor_unitario_ganho=item_oc.valor_unitario, valor_total_ganho=item_oc.valor_total,
            status_item=status, score_comparacao=round(score_comparacao, 2), score_texto=round(melhor_score_texto, 2),
            score_tecnico=round(s_tecnico, 2), conflito_tecnico=conflito, confianca_match_item=confianca,
            motivo_match_item=motivo,
        ))

    return resultado
