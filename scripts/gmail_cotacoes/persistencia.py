"""Persistência do robô Gmail Cotações na tabela gmail_vendas_oc.

Não fala com o Gmail. Só grava/lê no banco MedBox (core/banco.py) o que já
foi extraído por outro passo (parser_pdf_oc.py + classificar_email_venda).

Upsert por `chave_dedupe`: rodar o mesmo processamento duas vezes atualiza
a linha existente em vez de duplicar.
"""

from __future__ import annotations

import hashlib
import sys
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from core import banco  # noqa: E402

_CAMPOS = [
    "chave_dedupe", "id_email", "thread_id", "attachment_id", "message_internal_date",
    "assunto", "remetente", "data_email", "data_venda", "numero_oc", "vendedora", "cliente",
    "status_email", "status_revisao", "considerar_venda", "motivo_exclusao",
    "tem_marcador_pedido", "tem_marcador_cancelado", "tem_anexo_ordem_compra",
    "nome_arquivo", "caminho_anexo", "hash_arquivo", "tamanho_arquivo", "tipo_anexo",
    "metodo_extracao", "avisos_parser", "quantidade_itens", "valor_total_oc",
    "valor_total_impresso", "valor_total_calculado", "divergencia_total",
    "erro_processamento", "data_processamento", "origem_execucao",
]

_FILTROS_IGUALDADE = [
    "vendedora", "cliente", "status_email", "considerar_venda",
    "numero_oc", "id_email", "status_revisao", "origem_execucao",
]

# data_venda é gravada como texto "DD/MM/AAAA" (ver parser_pdf_oc._RE_DATA_OC).
# Os filtros data_venda_de/data_venda_ate chegam em "AAAA-MM-DD" (input HTML
# type="date"). Comparar essas duas strings diretamente dá resultado errado
# (ordem lexicográfica de "03/07/2026" não corresponde à ordem cronológica).
# Por isso a comparação SEMPRE reconverte data_venda para "AAAA-MM-DD" dentro
# do SQL antes de comparar — nunca comparação textual direta entre os formatos.
_DATA_VENDA_ISO_SQL = "(substr(data_venda, 7, 4) || '-' || substr(data_venda, 4, 2) || '-' || substr(data_venda, 1, 2))"
_DATA_VENDA_VALIDA_SQL = "(data_venda IS NOT NULL AND length(data_venda) = 10)"


def calcular_hash_arquivo(caminho: str | Path) -> str:
    """SHA-256 do conteúdo do arquivo (leitura em blocos, sem carregar tudo na memória)."""
    caminho = Path(caminho)
    sha256 = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(65536), b""):
            sha256.update(bloco)
    return sha256.hexdigest()


def caminho_relativo_projeto(caminho: str | Path) -> str:
    """Caminho relativo à raiz do projeto (nunca absoluto — o projeto muda de máquina)."""
    caminho = Path(caminho).resolve()
    try:
        relativo = caminho.relative_to(BASE_DIR)
    except ValueError:
        return str(caminho)
    return str(relativo).replace("\\", "/")


def montar_chave_dedupe(id_email: str, attachment_id: str | None, nome_arquivo: str, hash_arquivo: str | None) -> str:
    """Chave estável: mesmo e-mail + mesmo anexo + mesmo conteúdo = mesma chave.

    Rodar o processamento de novo sobre o mesmo arquivo atualiza a linha
    existente (upsert) em vez de duplicar.
    """
    partes = "|".join(str(x or "") for x in (id_email, attachment_id, nome_arquivo, hash_arquivo))
    return hashlib.sha256(partes.encode("utf-8")).hexdigest()


def _montar_where(filtros: dict) -> tuple[list[str], list]:
    condicoes: list[str] = []
    params: list = []
    for campo in _FILTROS_IGUALDADE:
        valor = filtros.get(campo)
        if valor:
            condicoes.append(f"{campo} = ?")
            params.append(valor)
    if filtros.get("data_venda_de"):
        condicoes.append(f"({_DATA_VENDA_VALIDA_SQL} AND {_DATA_VENDA_ISO_SQL} >= ?)")
        params.append(filtros["data_venda_de"])
    if filtros.get("data_venda_ate"):
        condicoes.append(f"({_DATA_VENDA_VALIDA_SQL} AND {_DATA_VENDA_ISO_SQL} <= ?)")
        params.append(filtros["data_venda_ate"])
    return condicoes, params


def salvar_gmail_venda_oc(registro: dict) -> int:
    """Insere ou atualiza (upsert por chave_dedupe). Retorna o id da linha."""
    if not registro.get("chave_dedupe"):
        raise ValueError("registro precisa de 'chave_dedupe' para o upsert.")
    if not registro.get("vendedora"):
        raise ValueError("registro precisa de 'vendedora' (NOT NULL na tabela).")
    if not registro.get("status_email"):
        raise ValueError("registro precisa de 'status_email' (NOT NULL na tabela).")
    if not registro.get("considerar_venda"):
        raise ValueError("registro precisa de 'considerar_venda' (NOT NULL na tabela).")

    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    valores = {campo: registro.get(campo) for campo in _CAMPOS}
    valores["data_processamento"] = valores.get("data_processamento") or agora

    conn = banco.conectar()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM gmail_vendas_oc WHERE chave_dedupe = ?", (valores["chave_dedupe"],))
    existente = cursor.fetchone()

    if existente:
        id_ = existente["id"]
        set_clause = ", ".join(f"{campo} = ?" for campo in _CAMPOS)
        cursor.execute(
            f"UPDATE gmail_vendas_oc SET {set_clause}, atualizado_em = ? WHERE id = ?",
            [valores[campo] for campo in _CAMPOS] + [agora, id_],
        )
    else:
        colunas = _CAMPOS + ["criado_em", "atualizado_em"]
        placeholders = ", ".join("?" for _ in colunas)
        cursor.execute(
            f"INSERT INTO gmail_vendas_oc ({', '.join(colunas)}) VALUES ({placeholders})",
            [valores[campo] for campo in _CAMPOS] + [agora, agora],
        )
        id_ = cursor.lastrowid

    conn.commit()
    conn.close()
    return id_


def listar_gmail_vendas_oc(filtros: dict | None = None) -> list[dict]:
    filtros = filtros or {}
    conn = banco.conectar()
    cursor = conn.cursor()
    condicoes, params = _montar_where(filtros)
    query = "SELECT * FROM gmail_vendas_oc"
    if condicoes:
        query += " WHERE " + " AND ".join(condicoes)
    query += " ORDER BY data_venda DESC, id DESC"
    cursor.execute(query, params)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


def indicadores_gmail_vendas_oc(filtros: dict | None = None) -> dict:
    """Só conta vendas com status_email='VENDA_CONFIRMADA' e considerar_venda='SIM'."""
    filtros = dict(filtros or {})
    filtros["status_email"] = "VENDA_CONFIRMADA"
    filtros["considerar_venda"] = "SIM"

    conn = banco.conectar()
    cursor = conn.cursor()
    condicoes, params = _montar_where(filtros)
    where = (" WHERE " + " AND ".join(condicoes)) if condicoes else ""

    cursor.execute(
        f"""SELECT COUNT(*) AS total_vendas,
                   COALESCE(SUM(valor_total_oc), 0) AS valor_total,
                   COALESCE(SUM(quantidade_itens), 0) AS total_itens
            FROM gmail_vendas_oc{where}""",
        params,
    )
    geral = dict(cursor.fetchone())

    cursor.execute(
        f"""SELECT vendedora, COUNT(*) AS total, COALESCE(SUM(valor_total_oc), 0) AS valor
            FROM gmail_vendas_oc{where}
            GROUP BY vendedora ORDER BY valor DESC""",
        params,
    )
    por_vendedora = [dict(r) for r in cursor.fetchall()]

    cursor.execute(
        f"""SELECT cliente, COUNT(*) AS total, COALESCE(SUM(valor_total_oc), 0) AS valor
            FROM gmail_vendas_oc{where}
            GROUP BY cliente ORDER BY valor DESC""",
        params,
    )
    por_cliente = [dict(r) for r in cursor.fetchall()]

    # Agregação mensal — só considera linhas com data_venda válida (DD/MM/AAAA);
    # linhas sem data reconhecida não entram em nenhum mês (não inventamos data).
    condicoes_mes = condicoes + [_DATA_VENDA_VALIDA_SQL]
    where_mes = " WHERE " + " AND ".join(condicoes_mes)
    cursor.execute(
        f"""SELECT substr(data_venda, 4, 2) || '/' || substr(data_venda, 7, 4) AS mes,
                   COUNT(*) AS quantidade,
                   COALESCE(SUM(valor_total_oc), 0) AS valor_total
            FROM gmail_vendas_oc{where_mes}
            GROUP BY substr(data_venda, 7, 4), substr(data_venda, 4, 2)
            ORDER BY substr(data_venda, 7, 4), substr(data_venda, 4, 2)""",
        params,
    )
    vendas_por_mes = [dict(r) for r in cursor.fetchall()]
    conn.close()

    return {
        "total_vendas": geral["total_vendas"],
        "valor_total": geral["valor_total"],
        "total_itens": geral["total_itens"],
        "vendas_por_mes": vendas_por_mes,
        "por_vendedora": por_vendedora,
        "por_cliente": por_cliente,
    }


def pendencias_gmail_vendas_oc(filtros: dict | None = None) -> list[dict]:
    """Linhas que precisam de revisão humana: não confirmadas como venda, ou
    marcadas com status_revisao (ex.: REVISAR_VENDEDORA)."""
    filtros = dict(filtros or {})
    conn = banco.conectar()
    cursor = conn.cursor()
    condicoes, params = _montar_where(filtros)
    condicoes.append("(considerar_venda != 'SIM' OR (status_revisao IS NOT NULL AND status_revisao != ''))")
    query = "SELECT * FROM gmail_vendas_oc WHERE " + " AND ".join(condicoes)
    query += " ORDER BY data_processamento DESC, id DESC"
    cursor.execute(query, params)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows
