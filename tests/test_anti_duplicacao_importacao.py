"""
Teste da correção de duplicação na importação (fix/duplicacao-importacao).

Não toca no banco real: cria um SQLite temporário com a tabela
precos_fornecedores e reproduz a lógica de identificação usada em
core/importador_universal.py após a correção.

Cenário coberto:
- Importação 1: fornecedor 1 + descrição "Dipirona 500mg" -> SKU gerado A (produto_id 10)
- Importação 2: MESMO fornecedor + MESMA descrição, porém o SKU gerado
  "deriva" para B (produto_id 20).

Antes da correção, a deduplicação de registrar_preco_fornecedor (que casa por
fornecedor_id + produto_id + descricao) erraria por causa do produto_id
diferente e INSERIRIA uma segunda linha -> duplicação.

Depois da correção, a guarda em importador_universal.py detecta o preço
existente por (fornecedor_id + descricao normalizada), reaproveita o
produto_id 10 e o upsert atualiza a linha existente -> sem duplicação.
"""

import sqlite3
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.banco import normalizar_texto


def criar_db_temporario():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE precos_fornecedores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fornecedor_id INTEGER,
            produto_id INTEGER,
            descricao_original TEXT,
            codigo_fornecedor TEXT,
            marca TEXT,
            preco REAL,
            data_importacao TEXT
        )
    """)
    return conn


def upsert_simulado(conn, fornecedor_id, descricao_orig, sku_drift_produto_id,
                    preco, data_importacao):
    """Reproduz o caminho do loop de importar_arquivo_fornecedor + o upsert
    de registrar_preco_fornecedor, já com a correção aplicada."""
    cursor = conn.cursor()
    descricao_norm = normalizar_texto(descricao_orig)

    # --- guarda anti-duplicação (NOVO, vindo de importador_universal.py) ---
    cursor.execute("""
        SELECT produto_id FROM precos_fornecedores
        WHERE fornecedor_id = ? AND UPPER(descricao_original) = ?
    """, (fornecedor_id, descricao_norm))
    preco_existente = cursor.fetchone()

    if preco_existente and preco_existente["produto_id"]:
        produto_id = preco_existente["produto_id"]      # reaproveita
    else:
        produto_id = sku_drift_produto_id               # "garantir_produto"

    # --- upsert equivalente ao de registrar_preco_fornecedor (banco.py) ---
    cursor.execute("""
        SELECT id, data_importacao FROM precos_fornecedores
        WHERE fornecedor_id = ? AND produto_id = ?
        AND UPPER(descricao_original) = ?
    """, (fornecedor_id, produto_id, descricao_norm))
    existente = cursor.fetchone()

    if existente:
        if data_importacao >= existente["data_importacao"]:
            cursor.execute("""
                UPDATE precos_fornecedores SET preco = ?, data_importacao = ?
                WHERE id = ?
            """, (preco, data_importacao, existente["id"]))
    else:
        cursor.execute("""
            INSERT INTO precos_fornecedores
            (fornecedor_id, produto_id, descricao_original, preco, data_importacao)
            VALUES (?, ?, ?, ?, ?)
        """, (fornecedor_id, produto_id, descricao_norm, preco, data_importacao))

    conn.commit()
    return produto_id


def test_nao_duplica_com_sku_drift():
    conn = criar_db_temporario()

    # Importação 1 -> SKU gera produto_id 10
    upsert_simulado(conn, 1, "Dipirona 500mg", 10, 12.50, "2026-01-10")
    # Importação 2 -> MESMO fornecedor+descrição, SKU deriva para produto_id 20
    upsert_simulado(conn, 1, "DIPIRONA  500MG", 20, 11.90, "2026-02-10")

    linhas = conn.execute("""
        SELECT preco, produto_id FROM precos_fornecedores
        WHERE fornecedor_id = 1
    """).fetchall()

    assert len(linhas) == 1, f"Esperava 1 linha, obtido {len(linhas)} (duplicou!)"
    assert linhas[0]["produto_id"] == 10, "Deveria reaproveitar o produto_id original"
    assert linhas[0]["preco"] == 11.90, "Deveria atualizar para o preço mais recente"
    print("OK test_nao_duplica_com_sku_drift: 1 linha, preco atualizado para 11.90")


def test_nao_atualiza_se_data_mais_antiga():
    conn = criar_db_temporario()
    upsert_simulado(conn, 1, "Amoxicilina 500mg", 30, 20.00, "2026-03-01")
    # Reimportação com data mais antiga -> não pode rebaixar o preço
    upsert_simulado(conn, 1, "amoxicilina 500mg", 99, 5.00, "2025-01-01")

    linhas = conn.execute("SELECT preco FROM precos_fornecedores WHERE fornecedor_id = 1").fetchall()
    assert len(linhas) == 1, "Não pode duplicar"
    assert linhas[0]["preco"] == 20.00, "Não pode atualizar com data mais antiga"
    print("OK test_nao_atualiza_se_data_mais_antiga: preco preservado em 20.00")


def test_fornecedores_diferentes_nao_se_misturam():
    conn = criar_db_temporario()
    upsert_simulado(conn, 1, "Paracetamol 750mg", 40, 8.00, "2026-01-01")
    upsert_simulado(conn, 2, "Paracetamol 750mg", 41, 9.00, "2026-01-01")

    linhas = conn.execute("SELECT fornecedor_id FROM precos_fornecedores").fetchall()
    assert len(linhas) == 2, "Fornecedores distintos devem manter linhas distintas"
    print("OK test_fornecedores_diferentes_nao_se_misturam: 2 linhas (1 por fornecedor)")


if __name__ == "__main__":
    test_nao_duplica_com_sku_drift()
    test_nao_atualiza_se_data_mais_antiga()
    test_fornecedores_diferentes_nao_se_misturam()
    print("\nTODOS OS TESTES PASSARAM")
