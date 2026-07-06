"""Parser da Ordem de Compra (XLSX).

Seguro e read-only. Tenta extrair dados estruturados de planilhas de Ordem de Compra.
Lida com arquivos de 'rateio' (múltiplas abas) e múltiplas OCs no mesmo arquivo.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime

import openpyxl

from perfil_tecnico import normalizar_texto

@dataclass
class ItemOC:
    numero_item: int
    descricao: str
    unidade: str | None
    quantidade: float | None
    valor_unitario: float | None
    valor_total: float | None
    confianca_extracao: str  # ALTA | BAIXA

@dataclass
class OrdemDeCompra:
    numero_oc: str | None
    data_oc: str | None  # DD/MM/AAAA
    cliente: str | None
    valor_total_impresso: float | None
    valor_total_calculado: float
    itens: list[ItemOC]
    metodo_extracao: str
    avisos: list[str] = field(default_factory=list)
    aba_origem: str | None = None

def _norm_header(v) -> str:
    return normalizar_texto(str(v)) if v is not None else ""

def _achar_coluna(headers: list[str], *alvos: str) -> int | None:
    alvos_norm = [normalizar_texto(a) for a in alvos]
    for idx, h in enumerate(headers):
        if h in alvos_norm:
            return idx
    return None

def parse_xlsx_oc(caminho: str | Path) -> list[OrdemDeCompra]:
    """Retorna uma lista de OrdemDeCompra, pois um XLSX pode conter múltiplas OCs."""
    caminho = Path(caminho)
    if not caminho.exists():
        raise FileNotFoundError(f"Excel de Ordem de Compra não encontrado: {caminho}")

    wb = openpyxl.load_workbook(caminho, data_only=True)
    resultado: list[OrdemDeCompra] = []

    # Se for 'RATEIO', geralmente as abas relevantes têm nomes como 'OC XXXX' ou 'RESUMO'
    # Vamos processar todas as abas que pareçam conter itens de OC.
    for sheet_name in wb.sheetnames:
        oc = _processar_aba(wb[sheet_name])
        if oc and oc.itens:
            oc.aba_origem = sheet_name
            oc.metodo_extracao = "openpyxl"
            resultado.append(oc)

    # Se houver múltiplas OCs na mesma lista (mesmo número), talvez precisemos agrupar ou filtrar.
    # Mas por enquanto, retornamos todas as encontradas.

    if not resultado:
        # Se não encontrou nada estruturado, retorna uma OC vazia com aviso para marcar como PENDENTE
        return [OrdemDeCompra(
            numero_oc=None, data_oc=None, cliente=None,
            valor_total_impresso=None, valor_total_calculado=0.0,
            itens=[], metodo_extracao="openpyxl",
            avisos=["Nenhuma aba com estrutura de Ordem de Compra reconhecida."]
        )]

    return resultado

def _processar_aba(ws: openpyxl.worksheet.worksheet.Worksheet) -> OrdemDeCompra | None:
    """Tenta extrair uma OC de uma aba específica."""
    headers = []
    header_row_idx = -1

    # Procura a linha de cabeçalho (que contém 'DESCRICAO' e 'QUANTIDADE')
    for row_idx, row in enumerate(ws.iter_rows(min_row=1, max_row=20, values_only=True), start=1):
        row_norm = [_norm_header(c) for c in row]
        if _achar_coluna(row_norm, "DESCRICAO", "PRODUTO") is not None and \
           _achar_coluna(row_norm, "QUANTIDADE", "QTD") is not None:
            headers = row_norm
            header_row_idx = row_idx
            break

    if header_row_idx == -1:
        return None

    col_item = _achar_coluna(headers, "ITEM", "N")
    col_desc = _achar_coluna(headers, "DESCRICAO", "PRODUTO", "NOME DO PRODUTO")
    col_un = _achar_coluna(headers, "UNIDADE", "UNID", "UN")
    col_qtd = _achar_coluna(headers, "QUANTIDADE", "QTD", "QUANT")
    col_preco = _achar_coluna(headers, "PRECO UNITARIO", "VALOR UNITARIO", "PRECO UNIT", "UNITARIO")
    col_total = _achar_coluna(headers, "VALOR TOTAL", "TOTAL", "PRECO TOTAL")

    if col_desc is None or col_qtd is None:
        return None

    # Tenta achar Numero OC, Data e Cliente nos arredores (acima do cabeçalho)
    numero_oc = None
    data_oc = None
    cliente = None

    # Busca em toda a aba por padrões de OC
    for row in ws.iter_rows(min_row=1, max_row=header_row_idx, values_only=True):
        for cell in row:
            if not cell: continue
            texto = str(cell).upper()

            # Numero OC
            if not numero_oc:
                m_oc = re.search(r"ORDEM DE COMPRA[ N.]+(\d+)", texto)
                if m_oc: numero_oc = m_oc.group(1)
                elif "ORDEM DE COMPRA" in texto and header_row_idx > 1:
                   # Às vezes o número está na célula ao lado
                   pass # Implementação simples por ora

            # Data
            if not data_oc:
                if isinstance(cell, datetime):
                    data_oc = cell.strftime("%d/%m/%Y")
                else:
                    m_data = re.search(r"(\d{2}/\d{2}/\d{4})", texto)
                    if m_data: data_oc = m_data.group(1)

            # Cliente
            if not cliente:
                if "NOME:" in texto or "CLIENTE:" in texto:
                    cliente = texto.split(":")[-1].strip()

    itens: list[ItemOC] = []
    valor_total_impresso = None

    for row_idx, row in enumerate(ws.iter_rows(min_row=header_row_idx + 1, values_only=True), start=1):
        desc = row[col_desc]
        if desc is None or str(desc).strip() == "" or _norm_header(desc) == "TOTAL":
            # Se encontrar "TOTAL" na coluna de descrição, tenta pegar o valor total impresso
            if _norm_header(desc) == "TOTAL" and col_total is not None:
                valor_total_impresso = _to_float(row[col_total])
            break

        try:
            qtd = _to_float(row[col_qtd])
            preco = _to_float(row[col_preco]) if col_preco is not None else 0.0
            total = _to_float(row[col_total]) if col_total is not None else (qtd * preco)

            itens.append(ItemOC(
                numero_item=int(_to_float(row[col_item])) if col_item is not None and row[col_item] else row_idx,
                descricao=str(desc).strip(),
                unidade=str(row[col_un]).strip() if col_un is not None and row[col_un] else "UN",
                quantidade=qtd,
                valor_unitario=preco,
                valor_total=total,
                confianca_extracao="ALTA" if qtd and total else "BAIXA"
            ))
        except:
            continue

    if not itens:
        return None

    valor_total_calculado = sum(it.valor_total for it in itens if it.valor_total)

    # Se não achou numero_oc no texto, tenta pegar do nome da aba
    if not numero_oc:
        m_aba = re.search(r"(?:OC|ORDEM DE COMPRA)[ N.]+(\d+)", ws.title.upper())
        if m_aba:
            numero_oc = m_aba.group(1)

    return OrdemDeCompra(
        numero_oc=numero_oc,
        data_oc=data_oc,
        cliente=cliente,
        valor_total_impresso=valor_total_impresso,
        valor_total_calculado=valor_total_calculado,
        itens=itens,
        metodo_extracao="openpyxl",
        avisos=[],
        aba_origem=ws.title
    )

def _to_float(v) -> float:
    if v is None: return 0.0
    if isinstance(v, (int, float)): return float(v)
    try:
        s = str(v).replace("R$", "").replace(" ", "").replace(".", "").replace(",", ".")
        return float(s)
    except:
        return 0.0
