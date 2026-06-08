from pathlib import Path

from core.banco import conectar
from core.importador_universal import importar_arquivo_fornecedor


def importar_cotacao(caminho, fornecedor_id):
    caminho = Path(caminho)

    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT nome, tipo FROM fornecedores WHERE id = ? AND ativo = 1",
        (fornecedor_id,),
    )
    fornecedor = cursor.fetchone()
    conn.close()

    if not fornecedor:
        raise Exception("Fornecedor nao encontrado.")

    return importar_arquivo_fornecedor(
        caminho,
        fornecedor_id,
        fornecedor["nome"],
        fornecedor["tipo"] or "Distribuidor",
    )
