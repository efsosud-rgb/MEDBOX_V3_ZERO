# core/base_produtos.py

import sqlite3
from pathlib import Path


RAIZ_PROJETO = Path(__file__).resolve().parent.parent
CAMINHO_BANCO = RAIZ_PROJETO / "banco" / "medbox.db"


def conectar():
    conn = sqlite3.connect(CAMINHO_BANCO)
    conn.row_factory = sqlite3.Row
    return conn


def listar_base_produtos(
    termo="",
    fornecedor="",
    origem_importacao="",
    categoria="",
    marca="",
    limite=200
):
    conn = conectar()
    cur = conn.cursor()

    sql = """
        SELECT
            id,
            data_lancamento,
            fornecedor,
            tipo_fornecedor,
            codigo_produto,
            descricao_produto,
            sku_master,
            marca,
            categoria,
            unidade_compra,
            valor_unitario,
            origem_importacao,
            arquivo_origem,
            data_importacao
        FROM bd_base_produtos
        WHERE ativo = 1
    """

    params = []

    if termo:
        sql += """
            AND (
                descricao_produto LIKE ?
                OR sku_master LIKE ?
                OR codigo_produto LIKE ?
            )
        """
        like = f"%{termo}%"
        params.extend([like, like, like])

    if fornecedor:
        sql += " AND fornecedor LIKE ? "
        params.append(f"%{fornecedor}%")

    if origem_importacao:
        sql += " AND origem_importacao = ? "
        params.append(origem_importacao)

    if categoria:
        sql += " AND categoria LIKE ? "
        params.append(f"%{categoria}%")

    if marca:
        sql += " AND marca LIKE ? "
        params.append(f"%{marca}%")

    sql += """
        ORDER BY
            data_lancamento DESC,
            fornecedor ASC,
            descricao_produto ASC
        LIMIT ?
    """

    params.append(limite)

    cur.execute(sql, params)
    registros = cur.fetchall()

    conn.close()
    return registros


def resumo_base_produtos():
    conn = conectar()
    cur = conn.cursor()

    resumo = {}

    cur.execute("SELECT COUNT(*) FROM bd_base_produtos WHERE ativo = 1")
    resumo["total"] = cur.fetchone()[0]

    cur.execute("""
        SELECT origem_importacao, COUNT(*) AS total
        FROM bd_base_produtos
        WHERE ativo = 1
        GROUP BY origem_importacao
        ORDER BY total DESC
    """)
    resumo["por_origem"] = cur.fetchall()

    cur.execute("""
        SELECT fornecedor, COUNT(*) AS total
        FROM bd_base_produtos
        WHERE ativo = 1
        GROUP BY fornecedor
        ORDER BY total DESC
        LIMIT 10
    """)
    resumo["por_fornecedor"] = cur.fetchall()

    conn.close()
    return resumo


def listar_origens():
    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
        SELECT DISTINCT origem_importacao
        FROM bd_base_produtos
        WHERE origem_importacao IS NOT NULL
        AND origem_importacao <> ''
        ORDER BY origem_importacao
    """)

    origens = [row[0] for row in cur.fetchall()]
    conn.close()
    return origens