from __future__ import annotations

import re
from datetime import datetime, date
from pathlib import Path
from typing import Any

import openpyxl

try:
    from parser_pdf_oc import ItemOC, OrdemDeCompra
except ImportError:
    from scripts.gmail_cotacoes.parser_pdf_oc import ItemOC, OrdemDeCompra


_RE_OC_NOME = re.compile(r"ORDEM\s+DE\s+COMPRA\s+([0-9]{3,6}(?:[./-][0-9]{2,4})?)", re.IGNORECASE)
_RE_OC_TEXTO = re.compile(
    r"(?:ORDEM\s+DE\s+COMPRA|O\.?\s*C\.?|OC|PEDIDO)\s*(?:N[ºO.]*)?\s*[:\-]?\s*([0-9]{3,6}(?:[./-][0-9]{2,4})?)",
    re.IGNORECASE,
)
_RE_DATA = re.compile(r"\b(\d{2}/\d{2}/\d{4})\b")
_RE_MONETARIO = re.compile(r"^-?\s*R?\$?\s*[\d.]+,\d{2}$", re.IGNORECASE)


def _normalizar(txt: Any) -> str:
    txt = "" if txt is None else str(txt)
    troca = {
        "Á": "A", "À": "A", "Â": "A", "Ã": "A",
        "É": "E", "Ê": "E",
        "Í": "I",
        "Ó": "O", "Ô": "O", "Õ": "O",
        "Ú": "U",
        "Ç": "C",
    }
    txt = txt.upper()
    for a, b in troca.items():
        txt = txt.replace(a, b)
    return re.sub(r"\s+", " ", txt).strip()


def _texto_celula(valor: Any) -> str:
    if valor is None:
        return ""
    if isinstance(valor, (datetime, date)):
        return valor.strftime("%d/%m/%Y")
    return str(valor).strip()


def _para_float(valor: Any) -> float | None:
    if valor is None:
        return None
    if isinstance(valor, bool):
        return None
    if isinstance(valor, (int, float)):
        return float(valor)

    s = str(valor).strip()
    if not s:
        return None

    s = s.replace("R$", "").replace(" ", "").replace("\u00a0", "")
    s = s.replace("−", "-")

    # Formato brasileiro: 1.234,56
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    else:
        # Mantém decimal americano simples, se houver.
        s = s.replace(",", "")

    try:
        return float(s)
    except ValueError:
        return None


def _formatar_data(valor: Any) -> str | None:
    if isinstance(valor, datetime):
        return valor.strftime("%d/%m/%Y")
    if isinstance(valor, date):
        return valor.strftime("%d/%m/%Y")

    txt = _texto_celula(valor)
    m = _RE_DATA.search(txt)
    if not m:
        return None

    try:
        dt = datetime.strptime(m.group(1), "%d/%m/%Y")
    except ValueError:
        return None
    return dt.strftime("%d/%m/%Y")


def _linhas_planilha(ws) -> list[list[Any]]:
    return [list(row) for row in ws.iter_rows(values_only=True)]


def _texto_planilha(rows: list[list[Any]]) -> str:
    partes = []
    for row in rows:
        linha = " ".join(_texto_celula(v) for v in row if _texto_celula(v))
        if linha:
            partes.append(linha)
    return "\n".join(partes)


def _extrair_numero_oc(caminho: Path, textos: list[str]) -> str | None:
    m_nome = _RE_OC_NOME.search(caminho.stem)
    if m_nome:
        return m_nome.group(1).replace("/", ".").replace("-", ".")

    for texto in textos:
        m = _RE_OC_TEXTO.search(texto)
        if m:
            return m.group(1).replace("/", ".").replace("-", ".")
    return None


def _extrair_data_oc(rows_por_aba: dict[str, list[list[Any]]]) -> str | None:
    candidatos_prioritarios: list[str] = []
    candidatos_gerais: list[str] = []

    for _aba, rows in rows_por_aba.items():
        for r_idx, row in enumerate(rows):
            for c_idx, valor in enumerate(row):
                data = _formatar_data(valor)
                if not data:
                    continue

                vizinhos = []
                for rr in range(max(0, r_idx - 1), min(len(rows), r_idx + 2)):
                    for cc in range(max(0, c_idx - 2), min(len(rows[rr]), c_idx + 3)):
                        vizinhos.append(_texto_celula(rows[rr][cc]))
                contexto = _normalizar(" ".join(vizinhos))

                if "ENTREGA" in contexto:
                    continue

                if any(p in contexto for p in ["EMISSAO", "EMISSÃO", "ORDEM DE COMPRA", "DATA OC", "DATA DA OC"]):
                    candidatos_prioritarios.append(data)
                else:
                    candidatos_gerais.append(data)

    return (candidatos_prioritarios or candidatos_gerais or [None])[0]


def _extrair_cliente(rows_por_aba: dict[str, list[list[Any]]]) -> str | None:
    """
    Extrai cliente/unidade do XLSX de OC.

    Regra para modelo conhecido:
    - B2 costuma trazer a entidade compradora.
    - B7 costuma trazer o local de entrega/unidade.
    - Nunca usar linha de item como cliente.
    """
    for _aba, rows in rows_por_aba.items():
        # Prioridade 1: célula B2, quando existir.
        try:
            b2 = _texto_celula(rows[1][1]).strip()
            if b2 and _normalizar(b2) not in {"ORDEM DE COMPRA", "MEDBOX"}:
                return b2
        except Exception:
            pass

        # Prioridade 2: valor ao lado de LOCAL DE ENTREGA.
        for row in rows:
            textos = [_texto_celula(v) for v in row]
            norm = [_normalizar(v) for v in textos]
            for idx, cel in enumerate(norm):
                if "LOCAL DE ENTREGA" in cel:
                    for prox in row[idx + 1:idx + 5]:
                        val = _texto_celula(prox).strip()
                        if val:
                            return val

    return None

def _mapear_header(row: list[Any]) -> dict[str, int]:
    mapa: dict[str, int] = {}
    for idx, valor in enumerate(row):
        n = _normalizar(valor)
        if not n:
            continue

        if "DESCR" in n or "PRODUTO" in n or "MATERIAL" in n or "ITEM" == n:
            mapa.setdefault("descricao", idx)
        elif "QTD" in n or "QUANT" in n:
            mapa.setdefault("quantidade", idx)
        elif ("VALOR" in n or "PRECO" in n or "PREÇO" in n) and ("UNIT" in n or "UN" in n):
            mapa.setdefault("valor_unitario", idx)
        elif ("TOTAL" in n or "VALOR TOTAL" in n or "VL TOTAL" in n) and "UNIT" not in n:
            mapa.setdefault("valor_total", idx)
        elif n in ["UN", "UND", "UNIDADE"]:
            mapa.setdefault("unidade", idx)

    return mapa


def _valor_col(row: list[Any], idx: int | None) -> Any:
    if idx is None or idx >= len(row):
        return None
    return row[idx]


def _linha_vazia(row: list[Any]) -> bool:
    return all(_texto_celula(v) == "" for v in row)


def _extrair_itens(rows_por_aba: dict[str, list[list[Any]]]) -> list[ItemOC]:
    itens: list[ItemOC] = []
    numero_item = 1

    for aba, rows in rows_por_aba.items():
        for h_idx, row in enumerate(rows):
            mapa = _mapear_header(row)
            if "descricao" not in mapa or "quantidade" not in mapa:
                continue

            # Precisa ter valor unitário ou total para ser tabela de itens confiável.
            if "valor_unitario" not in mapa and "valor_total" not in mapa:
                continue

            vazias_seguintes = 0
            for data_row in rows[h_idx + 1:]:
                if _linha_vazia(data_row):
                    vazias_seguintes += 1
                    if vazias_seguintes >= 3:
                        break
                    continue
                vazias_seguintes = 0

                descricao = _texto_celula(_valor_col(data_row, mapa.get("descricao"))).strip()
                if not descricao:
                    continue

                desc_norm = _normalizar(descricao)
                if desc_norm in ["TOTAL", "TOTAL GERAL", "SUBTOTAL", "VALOR TOTAL"]:
                    break
                if "TOTAL" == desc_norm or desc_norm.startswith("TOTAL ") or "VALOR TOTAL" in desc_norm:
                    break

                quantidade = _para_float(_valor_col(data_row, mapa.get("quantidade")))
                valor_unitario = _para_float(_valor_col(data_row, mapa.get("valor_unitario")))
                valor_total = _para_float(_valor_col(data_row, mapa.get("valor_total")))
                unidade = _texto_celula(_valor_col(data_row, mapa.get("unidade"))) or None

                if quantidade is None and valor_unitario is None and valor_total is None:
                    continue

                if valor_total is None and quantidade is not None and valor_unitario is not None:
                    valor_total = round(quantidade * valor_unitario, 2)

                if valor_unitario is None and quantidade not in (None, 0) and valor_total is not None:
                    valor_unitario = round(valor_total / quantidade, 6)

                if valor_total is None:
                    confianca = "BAIXA"
                else:
                    confianca = "ALTA"

                itens.append(ItemOC(
                    numero_item=numero_item,
                    descricao=descricao,
                    unidade=unidade,
                    quantidade=quantidade,
                    valor_unitario=valor_unitario,
                    valor_total=valor_total,
                    confianca_extracao=confianca,
                ))
                numero_item += 1

    return itens


def parse_xlsx_oc(caminho: str | Path) -> OrdemDeCompra:
    caminho = Path(caminho)
    if not caminho.exists():
        raise FileNotFoundError(f"XLSX de Ordem de Compra não encontrado: {caminho}")

    wb = openpyxl.load_workbook(caminho, data_only=True, read_only=True)
    rows_por_aba = {ws.title: _linhas_planilha(ws) for ws in wb.worksheets}
    textos = [_texto_planilha(rows) for rows in rows_por_aba.values()]

    numero_oc = _extrair_numero_oc(caminho, textos)
    data_oc = _extrair_data_oc(rows_por_aba)
    cliente = _extrair_cliente(rows_por_aba)
    itens = _extrair_itens(rows_por_aba)

    avisos: list[str] = []

    if not numero_oc:
        raise ValueError("numero_oc não encontrado no XLSX nem no nome do arquivo.")
    if not data_oc:
        avisos.append("XLSX sem data interna; DATA_VENDA deve ser preenchida pela data de recebimento do e-mail.")
    if not cliente:
        raise ValueError("cliente não encontrado com segurança no XLSX.")
    if not itens:
        raise ValueError("nenhuma tabela de itens confiável encontrada no XLSX.")

    valor_total_calculado = round(sum(i.valor_total or 0 for i in itens), 2)
    if valor_total_calculado <= 0:
        raise ValueError("valor total calculado da OC XLSX é zero ou inválido.")

    baixa = [i for i in itens if i.confianca_extracao != "ALTA"]
    if baixa:
        avisos.append(f"{len(baixa)} item(ns) com confiança BAIXA no XLSX.")

    return OrdemDeCompra(
        numero_oc=numero_oc,
        data_oc=data_oc,
        cliente=cliente,
        valor_total_impresso=None,
        valor_total_calculado=valor_total_calculado,
        itens=itens,
        metodo_extracao="openpyxl_xlsx_oc",
        avisos=avisos,
    )
