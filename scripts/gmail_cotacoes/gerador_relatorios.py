"""Geração dos relatórios finais: XLSX (várias abas), TXT resumo e CSVs.

Usa apenas openpyxl + a biblioteca padrão (csv). Não importa pandas nem
numpy — no ambiente Windows deste projeto, uma política de Controle de
Aplicativo bloqueou a DLL nativa que o numpy (dependência transitiva do
pandas) carrega ao importar, e o robô não pode depender disso.

Recebe uma lista de "casos processados" (um por cotação correlacionada) e
produz:
- <saida>.xlsx com as abas EMAILS_COTACOES, EMAILS_PEDIDOS, ITENS_COTADOS,
  ITENS_PEDIDOS, CRUZAMENTO_ITENS, RELATORIO_COTACOES,
  ITENS_CRITICOS_PERDIDOS, ITENS_REVISAR, DASHBOARD_BASE
- <saida>_resumo.txt com um resumo legível
- CSVs equivalentes (separador ';', utf-8-sig) em data/gmail_cotacoes/relatorios/csv/
"""

from __future__ import annotations

import csv
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

import config

_CABECALHO_EMAILS_COTACOES = ["VENDEDORA", "CLIENTE", "ASSUNTO", "COTACAO", "CATEGORIA", "MES_REFERENCIA"]
_CABECALHO_EMAILS_PEDIDOS = ["MARCADOR", "ASSUNTO", "CLIENTE", "NUMERO_OC"]
_CABECALHO_ITENS_COTADOS = [
    "VENDEDORA", "CLIENTE", "COTACAO", "ITEM", "CODIGO_PRODUTO", "DESCRICAO",
    "UNIDADE", "QUANTIDADE", "VALOR_UNITARIO", "VALOR_TOTAL",
]
_CABECALHO_ITENS_PEDIDOS = [
    "CLIENTE", "NUMERO_OC", "ITEM", "DESCRICAO", "UNIDADE",
    "QUANTIDADE", "VALOR_UNITARIO", "VALOR_TOTAL", "CONFIANCA_EXTRACAO",
]
_CABECALHO_DASHBOARD_BASE = [
    "TOTAL_COTACOES", "TOTAL_ITENS_COTADOS", "TOTAL_ITENS_GANHOS", "TOTAL_ITENS_PERDIDOS",
    "TOTAL_ITENS_NAO_COTADOS", "TOTAL_ITENS_REVISAR", "VALOR_TOTAL_COTADO", "VALOR_TOTAL_GANHO",
    "DIFERENCA_VALOR", "PERC_ITENS_GANHOS", "PERC_ITENS_NAO_COTADOS", "CORRELACOES_BAIXA_CONFIANCA",
]

_CABECALHOS_POR_ABA = {
    "EMAILS_COTACOES": _CABECALHO_EMAILS_COTACOES,
    "EMAILS_PEDIDOS": _CABECALHO_EMAILS_PEDIDOS,
    "ITENS_COTADOS": _CABECALHO_ITENS_COTADOS,
    "ITENS_PEDIDOS": _CABECALHO_ITENS_PEDIDOS,
    "CRUZAMENTO_ITENS": config.COLUNAS_CRUZAMENTO_ITENS,
    "RELATORIO_COTACOES": config.COLUNAS_RELATORIO_COTACOES,
    "ITENS_CRITICOS_PERDIDOS": config.COLUNAS_CRUZAMENTO_ITENS,
    "ITENS_REVISAR": config.COLUNAS_CRUZAMENTO_ITENS,
    "DASHBOARD_BASE": _CABECALHO_DASHBOARD_BASE,
}


def _linhas_emails(casos_processados: list[dict]) -> tuple[list[dict], list[dict]]:
    cotacoes, pedidos = [], []
    for cp in casos_processados:
        caso = cp["caso"]
        cotacoes.append({
            "VENDEDORA": caso.vendedora,
            "CLIENTE": caso.cliente,
            "ASSUNTO": caso.assunto_cotacao,
            "COTACAO": caso.numero_cotacao,
            "CATEGORIA": caso.categoria,
            "MES_REFERENCIA": caso.mes_referencia,
        })
        pedidos.append({
            "MARCADOR": config.MARCADOR_PEDIDO,
            "ASSUNTO": caso.assunto_pedido,
            "CLIENTE": caso.cliente,
            "NUMERO_OC": caso.numero_oc,
        })
    return cotacoes, pedidos


def _linhas_itens_cotados(casos_processados: list[dict]) -> list[dict]:
    linhas = []
    for cp in casos_processados:
        caso = cp["caso"]
        for item in cp["cotacao_excel"].itens:
            linhas.append({
                "VENDEDORA": caso.vendedora, "CLIENTE": caso.cliente, "COTACAO": caso.numero_cotacao,
                "ITEM": item.numero_item, "CODIGO_PRODUTO": item.codigo_produto, "DESCRICAO": item.descricao,
                "UNIDADE": item.unidade, "QUANTIDADE": item.quantidade,
                "VALOR_UNITARIO": item.valor_unitario, "VALOR_TOTAL": item.valor_total,
            })
    return linhas


def _linhas_itens_pedidos(casos_processados: list[dict]) -> list[dict]:
    linhas = []
    for cp in casos_processados:
        caso = cp["caso"]
        for item in cp["ordem_compra"].itens:
            linhas.append({
                "CLIENTE": caso.cliente, "NUMERO_OC": caso.numero_oc,
                "ITEM": item.numero_item, "DESCRICAO": item.descricao, "UNIDADE": item.unidade,
                "QUANTIDADE": item.quantidade, "VALOR_UNITARIO": item.valor_unitario,
                "VALOR_TOTAL": item.valor_total, "CONFIANCA_EXTRACAO": item.confianca_extracao,
            })
    return linhas


def _linhas_cruzamento(casos_processados: list[dict]) -> list[dict]:
    linhas = []
    for cp in casos_processados:
        caso = cp["caso"]
        for it in cp["cruzamento"]:
            linhas.append({
                "VENDEDORA": caso.vendedora, "CLIENTE": caso.cliente, "CATEGORIA": caso.categoria,
                "COTACAO": caso.numero_cotacao, "NUMERO_OC": caso.numero_oc,
                "ITEM_COTACAO": it.item_cotacao, "DESCRICAO_COTADA": it.descricao_cotada,
                "UNIDADE": it.unidade, "QTD_COTADA": it.qtd_cotada,
                "VALOR_UNITARIO_COTADO": it.valor_unitario_cotado, "VALOR_TOTAL_COTADO": it.valor_total_cotado,
                "ITEM_OC": it.item_oc, "DESCRICAO_OC": it.descricao_oc,
                "QTD_GANHA": it.qtd_ganha, "VALOR_UNITARIO_GANHO": it.valor_unitario_ganho,
                "VALOR_TOTAL_GANHO": it.valor_total_ganho, "STATUS_ITEM": it.status_item,
                "SCORE_COMPARACAO": it.score_comparacao, "SCORE_TEXTO": it.score_texto,
                "SCORE_TECNICO": it.score_tecnico,
                "CONFLITO_TECNICO": "SIM" if it.conflito_tecnico else "NAO",
                "CONFIANCA_MATCH_ITEM": it.confianca_match_item, "MOTIVO_MATCH_ITEM": it.motivo_match_item,
            })
    return linhas


def _linha_relatorio_cotacao(cp: dict) -> dict:
    caso = cp["caso"]
    score = cp["score_email"]
    cruzamento = cp["cruzamento"]

    total_cotados = len(cruzamento)
    ganhos = [i for i in cruzamento if i.status_item == "GANHO"]
    perdidos = [i for i in cruzamento if i.status_item == "PERDIDO"]
    nao_cotados = [i for i in cruzamento if i.status_item == "NAO_COTADO"]
    revisar = [i for i in cruzamento if i.status_item == "POSSIVEL_GANHO_REVISAR"]

    valor_total_cotacao = sum(i.valor_total_cotado for i in cruzamento)
    valor_total_ganho = sum(i.valor_total_ganho or 0.0 for i in ganhos)
    diferenca = valor_total_ganho - valor_total_cotacao
    perc_diferenca = (diferenca / valor_total_cotacao * 100) if valor_total_cotacao else 0.0

    return {
        "VENDEDORA": caso.vendedora, "CLIENTE": caso.cliente, "CATEGORIA": caso.categoria,
        "COTACAO": caso.numero_cotacao, "MES_REFERENCIA": caso.mes_referencia,
        "DATA_COTACAO": cp["cotacao_excel"].data_pedido, "NUMERO_OC": caso.numero_oc,
        "DATA_OC": cp["ordem_compra"].data_oc,
        "TOTAL_ITENS_COTADOS": total_cotados, "TOTAL_ITENS_GANHOS": len(ganhos),
        "TOTAL_ITENS_PERDIDOS": len(perdidos), "TOTAL_ITENS_NAO_COTADOS": len(nao_cotados),
        "TOTAL_ITENS_REVISAR": len(revisar),
        "PERC_ITENS_GANHOS": round(100 * len(ganhos) / total_cotados, 2) if total_cotados else 0.0,
        "PERC_ITENS_NAO_COTADOS": round(100 * len(nao_cotados) / total_cotados, 2) if total_cotados else 0.0,
        "VALOR_TOTAL_COTACAO": round(valor_total_cotacao, 2), "VALOR_TOTAL_GANHO": round(valor_total_ganho, 2),
        "DIFERENCA_VALOR": round(diferenca, 2), "PERC_DIFERENCA": round(perc_diferenca, 2),
        "SCORE_EMAIL_TOTAL": score.score_total, "SCORE_EMAIL_ASSUNTO": score.score_assunto,
        "SCORE_EMAIL_CLIENTE": score.score_cliente, "SCORE_EMAIL_CATEGORIA": score.score_categoria,
        "SCORE_EMAIL_MES": score.score_mes, "SCORE_EMAIL_DATA": score.score_data,
        "SCORE_EMAIL_ITENS": score.score_itens,
        "CONFIANCA_CORRELACAO_EMAIL": score.confianca, "MOTIVO_CORRELACAO_EMAIL": score.motivo,
        "LINK_EMAIL_COTACAO": "", "LINK_EMAIL_PEDIDO": "",
    }


def _linhas_criticos_perdidos(linhas_cruzamento: list[dict]) -> list[dict]:
    return [
        l for l in linhas_cruzamento
        if l["STATUS_ITEM"] == "PERDIDO" and l["VALOR_TOTAL_COTADO"] > config.VALOR_CRITICO_PERDIDO
    ]


def _linhas_revisar(linhas_cruzamento: list[dict]) -> list[dict]:
    return [
        l for l in linhas_cruzamento
        if l["STATUS_ITEM"] == "POSSIVEL_GANHO_REVISAR"
        or l["CONFLITO_TECNICO"] == "SIM"
        or l["CONFIANCA_MATCH_ITEM"] == "BAIXA"
    ]


def _linhas_dashboard_base(linhas_relatorio: list[dict]) -> list[dict]:
    if not linhas_relatorio:
        return []

    total_cotados = sum(l["TOTAL_ITENS_COTADOS"] for l in linhas_relatorio)
    total_ganhos = sum(l["TOTAL_ITENS_GANHOS"] for l in linhas_relatorio)
    total_perdidos = sum(l["TOTAL_ITENS_PERDIDOS"] for l in linhas_relatorio)
    total_nao_cotados = sum(l["TOTAL_ITENS_NAO_COTADOS"] for l in linhas_relatorio)
    total_revisar = sum(l["TOTAL_ITENS_REVISAR"] for l in linhas_relatorio)
    valor_total_cotado = sum(l["VALOR_TOTAL_COTACAO"] for l in linhas_relatorio)
    valor_total_ganho = sum(l["VALOR_TOTAL_GANHO"] for l in linhas_relatorio)
    diferenca_valor = sum(l["DIFERENCA_VALOR"] for l in linhas_relatorio)
    correlacoes_baixa_confianca = sum(
        1 for l in linhas_relatorio if l["CONFIANCA_CORRELACAO_EMAIL"] in ("BAIXA", "REVISAR")
    )
    divisor = max(1, total_cotados)

    return [{
        "TOTAL_COTACOES": len(linhas_relatorio),
        "TOTAL_ITENS_COTADOS": total_cotados,
        "TOTAL_ITENS_GANHOS": total_ganhos,
        "TOTAL_ITENS_PERDIDOS": total_perdidos,
        "TOTAL_ITENS_NAO_COTADOS": total_nao_cotados,
        "TOTAL_ITENS_REVISAR": total_revisar,
        "VALOR_TOTAL_COTADO": round(valor_total_cotado, 2),
        "VALOR_TOTAL_GANHO": round(valor_total_ganho, 2),
        "DIFERENCA_VALOR": round(diferenca_valor, 2),
        "PERC_ITENS_GANHOS": round(100 * total_ganhos / divisor, 2),
        "PERC_ITENS_NAO_COTADOS": round(100 * total_nao_cotados / divisor, 2),
        "CORRELACOES_BAIXA_CONFIANCA": correlacoes_baixa_confianca,
    }]


_ESTILO_CABECALHO_FONTE = Font(bold=True, color="FFFFFF")
_ESTILO_CABECALHO_FUNDO = PatternFill(start_color="00486C", end_color="00486C", fill_type="solid")


def _escrever_aba_xlsx(wb: Workbook, nome_aba: str, cabecalho: list[str], linhas: list[dict]) -> None:
    ws = wb.create_sheet(title=nome_aba[:31])

    ws.append(cabecalho)
    for celula in ws[1]:
        celula.font = _ESTILO_CABECALHO_FONTE
        celula.fill = _ESTILO_CABECALHO_FUNDO
        celula.alignment = Alignment(horizontal="center", vertical="center")

    for linha in linhas:
        ws.append([linha.get(coluna, "") for coluna in cabecalho])

    ws.freeze_panes = "A2"
    ultima_linha = max(1, len(linhas) + 1)
    ws.auto_filter.ref = f"A1:{get_column_letter(len(cabecalho))}{ultima_linha}"

    for i, coluna in enumerate(cabecalho, start=1):
        maior = len(str(coluna))
        for linha in linhas:
            valor = linha.get(coluna, "")
            maior = max(maior, len(str(valor)) if valor is not None else 0)
        ws.column_dimensions[get_column_letter(i)].width = min(60, max(10, maior + 2))


def _escrever_csv(caminho: Path, cabecalho: list[str], linhas: list[dict]) -> None:
    with open(caminho, "w", newline="", encoding="utf-8-sig") as f:
        escritor = csv.DictWriter(f, fieldnames=cabecalho, delimiter=";", extrasaction="ignore")
        escritor.writeheader()
        for linha in linhas:
            escritor.writerow(linha)


def gerar_relatorios(casos_processados: list[dict], caminho_saida_xlsx: str | Path) -> dict:
    """Retorna um dicionário com as tabelas geradas (para uso em testes/relatório final)."""
    caminho_saida_xlsx = Path(caminho_saida_xlsx)
    caminho_saida_xlsx.parent.mkdir(parents=True, exist_ok=True)

    emails_cotacoes, emails_pedidos = _linhas_emails(casos_processados)
    itens_cotados = _linhas_itens_cotados(casos_processados)
    itens_pedidos = _linhas_itens_pedidos(casos_processados)
    cruzamento = _linhas_cruzamento(casos_processados)
    relatorio_cotacoes = [_linha_relatorio_cotacao(cp) for cp in casos_processados]
    criticos_perdidos = _linhas_criticos_perdidos(cruzamento)
    revisar = _linhas_revisar(cruzamento)
    dashboard_base = _linhas_dashboard_base(relatorio_cotacoes)

    abas = {
        "EMAILS_COTACOES": emails_cotacoes,
        "EMAILS_PEDIDOS": emails_pedidos,
        "ITENS_COTADOS": itens_cotados,
        "ITENS_PEDIDOS": itens_pedidos,
        "CRUZAMENTO_ITENS": cruzamento,
        "RELATORIO_COTACOES": relatorio_cotacoes,
        "ITENS_CRITICOS_PERDIDOS": criticos_perdidos,
        "ITENS_REVISAR": revisar,
        "DASHBOARD_BASE": dashboard_base,
    }

    wb = Workbook()
    wb.remove(wb.active)  # remove a aba padrão "Sheet" — cada tabela ganha sua própria aba abaixo
    for nome_aba, linhas in abas.items():
        _escrever_aba_xlsx(wb, nome_aba, _CABECALHOS_POR_ABA[nome_aba], linhas)
    wb.save(caminho_saida_xlsx)

    config.CSV_DIR.mkdir(parents=True, exist_ok=True)
    for nome_aba, linhas in abas.items():
        _escrever_csv(config.CSV_DIR / f"{nome_aba}.csv", _CABECALHOS_POR_ABA[nome_aba], linhas)

    caminho_txt = caminho_saida_xlsx.with_name(caminho_saida_xlsx.stem + "_resumo.txt")
    _escrever_resumo_txt(caminho_txt, casos_processados, relatorio_cotacoes, dashboard_base)

    return abas


def _escrever_resumo_txt(caminho: Path, casos_processados: list[dict], relatorio_cotacoes: list[dict], dashboard_base: list[dict]) -> None:
    linhas = ["RESUMO — ROBÔ GMAIL COTAÇÕES (MODO LOCAL)", "=" * 50, ""]

    for cp, rel in zip(casos_processados, relatorio_cotacoes):
        caso = cp["caso"]
        linhas.append(f"Vendedora: {caso.vendedora}  |  Cliente: {caso.cliente}  |  Cotação: {caso.numero_cotacao}  |  OC: {caso.numero_oc}")
        linhas.append(f"  Confiança correlação e-mail: {rel['CONFIANCA_CORRELACAO_EMAIL']} (score {rel['SCORE_EMAIL_TOTAL']})")
        linhas.append(f"  Motivo: {rel['MOTIVO_CORRELACAO_EMAIL']}")
        linhas.append(f"  Itens cotados: {rel['TOTAL_ITENS_COTADOS']}  |  Ganhos: {rel['TOTAL_ITENS_GANHOS']}  |  Perdidos: {rel['TOTAL_ITENS_PERDIDOS']}  |  Não cotados: {rel['TOTAL_ITENS_NAO_COTADOS']}  |  Revisar: {rel['TOTAL_ITENS_REVISAR']}")
        linhas.append(f"  Valor cotado: R$ {rel['VALOR_TOTAL_COTACAO']:.2f}  |  Valor ganho: R$ {rel['VALOR_TOTAL_GANHO']:.2f}  |  Diferença: R$ {rel['DIFERENCA_VALOR']:.2f} ({rel['PERC_DIFERENCA']:.1f}%)")

        avisos = cp.get("avisos") or []
        if avisos:
            linhas.append("  Avisos dos parsers:")
            for a in avisos:
                linhas.append(f"    - {a}")
        linhas.append("")

    if dashboard_base:
        d = dashboard_base[0]
        linhas.append("-" * 50)
        linhas.append("DASHBOARD_BASE (consolidado)")
        for k, v in d.items():
            linhas.append(f"  {k}: {v}")

    caminho.write_text("\n".join(linhas), encoding="utf-8")
