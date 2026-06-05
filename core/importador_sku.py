from pathlib import Path
from openpyxl import load_workbook

from core.banco import conectar


def importar_sku_master(caminho_arquivo):
    caminho_arquivo = Path(caminho_arquivo)

    wb = load_workbook(caminho_arquivo, data_only=True)
    ws = wb.active

    cabecalhos = {}
    for col in range(1, ws.max_column + 1):
        valor = ws.cell(row=1, column=col).value
        if valor:
            cabecalhos[str(valor).strip().upper()] = col

    col_produto = None
    col_sku = None
    col_categoria = None
    col_fabricante = None

    for nome, col in cabecalhos.items():
        if nome in ["PRODUTO_PADRAO", "PRODUTO PADRAO", "NOME FANTASIA", "DESCRICAO PADRONIZADA"]:
            col_produto = col
        if nome in ["SKU", "ID_SKU", "CODIGO", "CÓDIGO"]:
            col_sku = col
        if nome in ["CATEGORIA", "TIPO"]:
            col_categoria = col
        if nome in ["FABRICANTE", "MARCA"]:
            col_fabricante = col

    if col_produto is None:
        raise Exception("Não encontrei a coluna do produto padronizado no SKU Master.")

    conn = conectar()
    cursor = conn.cursor()

    importados = 0
    atualizados = 0
    ignorados = 0

    for row in range(2, ws.max_row + 1):
        produto = ws.cell(row=row, column=col_produto).value

        if produto is None or str(produto).strip() == "":
            ignorados += 1
            continue

        produto = str(produto).strip().upper()

        sku = ""
        categoria = ""
        fabricante = ""

        if col_sku:
            valor = ws.cell(row=row, column=col_sku).value
            sku = str(valor).strip().upper() if valor else ""

        if col_categoria:
            valor = ws.cell(row=row, column=col_categoria).value
            categoria = str(valor).strip().upper() if valor else ""

        if col_fabricante:
            valor = ws.cell(row=row, column=col_fabricante).value
            fabricante = str(valor).strip().upper() if valor else ""

        cursor.execute(
            "SELECT id FROM produtos WHERE produto_padrao = ?",
            (produto,)
        )
        existente = cursor.fetchone()

        if existente:
            produto_id = existente["id"]

            cursor.execute("""
                UPDATE produtos
                SET sku = COALESCE(NULLIF(?, ''), sku),
                    fabricante = COALESCE(NULLIF(?, ''), fabricante),
                    categoria = COALESCE(NULLIF(?, ''), categoria),
                    ativo = 1
                WHERE id = ?
            """, (sku, fabricante, categoria, produto_id))

            atualizados += 1

        else:
            cursor.execute("""
                INSERT INTO produtos (sku, produto_padrao, fabricante, categoria, ativo)
                VALUES (?, ?, ?, ?, 1)
            """, (sku, produto, fabricante, categoria))

            produto_id = cursor.lastrowid
            importados += 1

        cursor.execute("""
            SELECT id FROM equivalencias
            WHERE produto_id = ? AND UPPER(descricao_equivalente) = ?
        """, (produto_id, produto))

        if not cursor.fetchone():
            cursor.execute("""
                INSERT INTO equivalencias (produto_id, descricao_equivalente)
                VALUES (?, ?)
            """, (produto_id, produto))

    conn.commit()
    conn.close()

    return importados