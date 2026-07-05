"""Parser do Excel "Exportação de Cotação" (ERP do cliente).

Este arquivo é a fonte MAIS confiável para os itens da cotação/proposta:
é um export estruturado (planilha ITENS_ORCAMENTO), sem o ruído de
quebra de linha que aparece na extração de texto de PDF. Por isso é
usado como fonte primária de "itens cotados" no pipeline (ver README.md
desta pasta para a justificativa completa).

Requer apenas openpyxl (já é dependência do projeto principal).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import openpyxl

from perfil_tecnico import normalizar_texto


@dataclass
class ItemCotado:
    numero_item: int
    codigo_produto: str
    descricao: str
    unidade: str
    quantidade: float
    valor_unitario: float
    valor_total: float


@dataclass
class CotacaoExcel:
    numero_cotacao: str
    cliente: str
    cnpj_cliente: str
    comprador: str
    data_pedido: object
    data_limite_resposta: object
    fornecedor: str
    itens: list[ItemCotado]


def _norm_header(v) -> str:
    return normalizar_texto(str(v)) if v is not None else ""


def _achar_coluna(headers: list[str], *alvos: str) -> int | None:
    alvos_norm = [normalizar_texto(a) for a in alvos]
    for idx, h in enumerate(headers):
        if h in alvos_norm:
            return idx
    return None


def parse_excel_cotacao(caminho: str | Path) -> CotacaoExcel:
    caminho = Path(caminho)
    if not caminho.exists():
        raise FileNotFoundError(f"Excel de cotação não encontrado: {caminho}")

    wb = openpyxl.load_workbook(caminho, data_only=True)

    numero_cotacao = cliente = cnpj_cliente = comprador = fornecedor = ""
    data_pedido = data_limite_resposta = None

    if "DADOS" in wb.sheetnames:
        ws_dados = wb["DADOS"]
        headers = [_norm_header(c.value) for c in ws_dados[1]]
        valores = [c.value for c in ws_dados[2]] if ws_dados.max_row >= 2 else []

        def campo(*nomes):
            idx = _achar_coluna(headers, *nomes)
            return valores[idx] if idx is not None and idx < len(valores) else None

        numero_cotacao = str(campo("CODCOTACAO") or "")
        cliente = str(campo("EMPRESA") or "")
        cnpj_cliente = str(campo("CNPJ") or "")
        comprador = str(campo("COMPRADOR") or "")
        fornecedor = str(campo("FORNECEDOR") or "")
        data_pedido = campo("DATA DO PEDIDO")
        data_limite_resposta = campo("DATA LIMITE RESPOSTA")

    if "ITENS_ORCAMENTO" not in wb.sheetnames:
        raise ValueError(f"Aba ITENS_ORCAMENTO não encontrada em {caminho.name}")

    ws = wb["ITENS_ORCAMENTO"]
    headers = [_norm_header(c.value) for c in ws[1]]

    col_produto = _achar_coluna(headers, "PRODUTO")
    col_descricao = _achar_coluna(headers, "DESCRICAO")
    col_unidade = _achar_coluna(headers, "UNIDADE SOLICITADA", "UNIDADE ORCADA")
    col_qtd = _achar_coluna(headers, "QUANTIDADE SOLICITADA", "QUANTIDADE ORCADA")
    col_preco = _achar_coluna(headers, "PRECO UNITARIO")
    col_valor_total = _achar_coluna(headers, "VALOR TOTAL")

    faltantes = [
        nome for nome, col in [
            ("PRODUTO", col_produto), ("DESCRICAO", col_descricao),
            ("QUANTIDADE SOLICITADA", col_qtd), ("PRECO UNITARIO", col_preco),
        ] if col is None
    ]
    if faltantes:
        raise ValueError(
            f"Colunas obrigatórias não encontradas em ITENS_ORCAMENTO de {caminho.name}: {faltantes}"
        )

    itens: list[ItemCotado] = []
    for numero_linha, linha in enumerate(ws.iter_rows(min_row=2, values_only=True), start=1):
        descricao = linha[col_descricao]
        if descricao is None or str(descricao).strip() == "":
            continue

        codigo = linha[col_produto]
        unidade = linha[col_unidade] if col_unidade is not None else None
        qtd = linha[col_qtd] or 0
        preco = linha[col_preco] or 0
        valor_total = linha[col_valor_total] if col_valor_total is not None else None
        if not valor_total:
            valor_total = float(qtd) * float(preco)

        itens.append(ItemCotado(
            numero_item=numero_linha,
            codigo_produto=str(codigo) if codigo is not None else "",
            descricao=str(descricao).strip(),
            unidade=str(unidade).split("|")[0].strip() if unidade else "",
            quantidade=float(qtd),
            valor_unitario=float(preco),
            valor_total=float(valor_total),
        ))

    return CotacaoExcel(
        numero_cotacao=numero_cotacao,
        cliente=cliente,
        cnpj_cliente=cnpj_cliente,
        comprador=comprador,
        data_pedido=data_pedido,
        data_limite_resposta=data_limite_resposta,
        fornecedor=fornecedor,
        itens=itens,
    )
