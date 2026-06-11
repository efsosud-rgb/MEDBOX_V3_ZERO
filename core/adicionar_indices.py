"""
core/adicionar_indices.py
Adiciona indices de performance ao banco medbox_v3.db.

Operacao ADITIVA: nenhum dado e removido ou alterado.
Pode ser executado multiplas vezes (CREATE INDEX IF NOT EXISTS).

Uso:
    python core/adicionar_indices.py
"""
import sqlite3
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "banco" / "medbox_v3.db"

INDICES = [
    (
        "idx_produtos_ativo_padrao",
        "CREATE INDEX IF NOT EXISTS idx_produtos_ativo_padrao "
        "ON produtos(ativo, produto_padrao)",
        "Filtra produtos ativos + LIKE em produto_padrao",
    ),
    (
        "idx_produtos_ativo_fabricante",
        "CREATE INDEX IF NOT EXISTS idx_produtos_ativo_fabricante "
        "ON produtos(ativo, fabricante)",
        "Filtra produtos ativos por fabricante",
    ),
    (
        "idx_produtos_ativo_sku",
        "CREATE INDEX IF NOT EXISTS idx_produtos_ativo_sku "
        "ON produtos(ativo, sku)",
        "Busca por codigo SKU com filtro ativo",
    ),
    (
        "idx_precos_produto_fornecedor_data",
        "CREATE INDEX IF NOT EXISTS idx_precos_produto_fornecedor_data "
        "ON precos_fornecedores(produto_id, fornecedor_id, data_importacao)",
        "Elimina correlated subquery lenta em _carregar_precos()",
    ),
    (
        "idx_precos_produto",
        "CREATE INDEX IF NOT EXISTS idx_precos_produto "
        "ON precos_fornecedores(produto_id)",
        "Acelera JOINs de precos por produto",
    ),
    (
        "idx_precos_fornecedor",
        "CREATE INDEX IF NOT EXISTS idx_precos_fornecedor "
        "ON precos_fornecedores(fornecedor_id)",
        "Acelera listagem de precos por fornecedor",
    ),
    (
        "idx_equivalencias_produto",
        "CREATE INDEX IF NOT EXISTS idx_equivalencias_produto "
        "ON equivalencias(produto_id)",
        "Acelera JOIN de equivalencias por produto",
    ),
]


def main():
    if not DB_PATH.exists():
        print(f"ERRO: banco nao encontrado: {DB_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("SELECT name FROM sqlite_master WHERE type='index' ORDER BY name")
    antes = {row[0] for row in cur.fetchall()}

    print(f"Banco: {DB_PATH}")
    print(f"Indices existentes antes: {len(antes)}")
    print()

    criados = 0
    for nome, sql, descricao in INDICES:
        cur.execute(sql)
        conn.commit()
        if nome not in antes:
            criados += 1
            print(f"  [CRIADO]     {nome}")
        else:
            print(f"  [ja existia] {nome}")
        print(f"               {descricao}")

    cur.execute("SELECT name FROM sqlite_master WHERE type='index' ORDER BY name")
    depois = [row[0] for row in cur.fetchall()]

    conn.close()
    print(f"\nTotal de indices apos: {len(depois)} (+{criados} novos)")
    print("Concluido.")


if __name__ == "__main__":
    main()
