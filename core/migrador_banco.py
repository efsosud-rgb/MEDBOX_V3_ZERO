"""
core/migrador_banco.py
Migração segura do banco medbox_v3.db — Fase 1 (SKU Master).

Uso:
    python core/migrador_banco.py              # age APENAS na cópia de teste
    python core/migrador_banco.py --confirmar  # age também no banco REAL
"""

import sys
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
PASTA_BANCO = BASE_DIR / "banco"
PASTA_BACKUPS = PASTA_BANCO / "backups"
DB_REAL = PASTA_BANCO / "medbox_v3.db"
DB_TESTE = PASTA_BANCO / "medbox_v3_teste.db"

# Colunas a adicionar na tabela 'produtos'
NOVAS_COLUNAS = [
    ("chave_sku",          "TEXT"),
    ("forma_farmaceutica", "TEXT"),
    ("concentracao",       "TEXT"),
    ("apresentacao",       "TEXT"),
    ("unidade_compra",     "TEXT"),
    ("origem",             "TEXT DEFAULT 'SISTEMA'"),
    ("data_criacao",       "TEXT"),
]


def _colunas_existentes(conn: sqlite3.Connection, tabela: str) -> set:
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({tabela})")
    return {row[1] for row in cursor.fetchall()}


def migrar(db_path: Path, label: str) -> None:
    print(f"\n[{label}] Conectando em: {db_path}")
    conn = sqlite3.connect(db_path)

    existentes = _colunas_existentes(conn, "produtos")
    adicionadas = []
    ja_existiam = []

    for nome, tipo in NOVAS_COLUNAS:
        if nome in existentes:
            ja_existiam.append(nome)
        else:
            conn.execute(f"ALTER TABLE produtos ADD COLUMN {nome} {tipo}")
            conn.commit()
            adicionadas.append(nome)

    conn.close()

    if adicionadas:
        print(f"  Colunas ADICIONADAS ({len(adicionadas)}): {', '.join(adicionadas)}")
    else:
        print("  Nenhuma coluna nova precisou ser adicionada.")

    if ja_existiam:
        print(f"  Colunas já existentes ({len(ja_existiam)}): {', '.join(ja_existiam)}")


def main() -> None:
    confirmar = "--confirmar" in sys.argv

    PASTA_BANCO.mkdir(exist_ok=True)
    PASTA_BACKUPS.mkdir(exist_ok=True)

    if not DB_REAL.exists():
        print(f"ERRO: banco real não encontrado em {DB_REAL}")
        print("Execute core/banco.py primeiro para criar o banco inicial.")
        sys.exit(1)

    # Backup do banco real antes de qualquer operação
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = PASTA_BACKUPS / f"medbox_v3_{timestamp}.db"
    shutil.copy2(DB_REAL, backup_path)
    print(f"Backup criado: {backup_path}")

    # Cria/sobrescreve a cópia de teste a partir do banco real
    shutil.copy2(DB_REAL, DB_TESTE)
    print(f"Cópia de teste criada: {DB_TESTE}")

    migrar(DB_TESTE, "TESTE")

    if confirmar:
        print("\n--confirmar detectado. Aplicando migração no banco REAL...")
        migrar(DB_REAL, "REAL")
        print("\nMigração aplicada ao banco real com sucesso.")
    else:
        print("\nModo seguro (sem --confirmar): banco real NÃO foi alterado.")
        print("Para aplicar no banco real, execute:")
        print("    python core/migrador_banco.py --confirmar")


if __name__ == "__main__":
    main()
