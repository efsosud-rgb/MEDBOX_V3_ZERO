"""
core/importador_base_produtos.py
Importa produtos do Produtos.xlsx para a tabela 'produtos' — Fase 1.

Estrutura esperada do arquivo:
- Aba: "Produtos"
- Coluna única; primeira linha é o título "BASE DE PRODUTOS" (ignorada)
- Demais linhas: descrição completa do produto em texto livre

Uso:
    python core/importador_base_produtos.py              # importa na cópia de TESTE
    python core/importador_base_produtos.py --confirmar  # importa no banco REAL
"""

import sys
import re
import unicodedata
import sqlite3
from datetime import date
from pathlib import Path

# ── Ajuste o caminho do arquivo aqui se necessário ──────────────────────────
BASE_DIR = Path(__file__).resolve().parents[1]
CAMINHO_XLSX = BASE_DIR / "uploads" / "Produtos.xlsx"
# ─────────────────────────────────────────────────────────────────────────────

PASTA_BANCO = BASE_DIR / "banco"
DB_REAL  = PASTA_BANCO / "medbox_v3.db"
DB_TESTE = PASTA_BANCO / "medbox_v3_teste.db"

# Colunas mínimas que devem existir antes de importar (criadas pelo migrador)
COLUNAS_NECESSARIAS = {"chave_sku", "origem", "data_criacao"}


def normalizar_chave(texto: str) -> str:
    """Converte descrição em chave normalizada: maiúsculas, sem acentos, espaços→'_'."""
    texto = str(texto).upper().strip()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = re.sub(r"[^A-Z0-9\s]", "", texto)
    texto = re.sub(r"\s+", "_", texto.strip())
    return texto


def _verificar_colunas(conn: sqlite3.Connection) -> bool:
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(produtos)")
    existentes = {row[1] for row in cursor.fetchall()}
    faltando = COLUNAS_NECESSARIAS - existentes
    if faltando:
        print("\nERRO: as seguintes colunas necessárias não existem na tabela 'produtos':")
        print(f"  {', '.join(sorted(faltando))}")
        print("\nExecute primeiro (cópia de teste):")
        print("    python core/migrador_banco.py")
        print("\nOu para migrar o banco real também:")
        print("    python core/migrador_banco.py --confirmar")
        return False
    return True


def main() -> None:
    confirmar = "--confirmar" in sys.argv

    if not CAMINHO_XLSX.exists():
        print(f"ERRO: arquivo não encontrado: {CAMINHO_XLSX}")
        print("Coloque o arquivo Produtos.xlsx em uploads/ e tente novamente.")
        sys.exit(1)

    db_path = DB_REAL if confirmar else DB_TESTE

    if not db_path.exists():
        if confirmar:
            print(f"ERRO: banco real não encontrado: {db_path}")
            print("Execute core/banco.py para criar o banco.")
        else:
            print(f"ERRO: cópia de teste não encontrada: {db_path}")
            print("Execute primeiro: python core/migrador_banco.py")
        sys.exit(1)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    if not _verificar_colunas(conn):
        conn.close()
        sys.exit(1)

    # Carrega chaves já existentes para verificação de duplicatas
    cursor = conn.cursor()
    cursor.execute("SELECT chave_sku FROM produtos WHERE chave_sku IS NOT NULL")
    chaves_existentes: set = {row[0] for row in cursor.fetchall()}

    # Lê o Excel
    try:
        from openpyxl import load_workbook
    except ImportError:
        print("ERRO: openpyxl não instalado. Execute: pip install openpyxl")
        conn.close()
        sys.exit(1)

    wb = load_workbook(CAMINHO_XLSX, data_only=True, read_only=True)

    if "Produtos" not in wb.sheetnames:
        print(f"ERRO: aba 'Produtos' não encontrada. Abas disponíveis: {wb.sheetnames}")
        conn.close()
        sys.exit(1)

    ws = wb["Produtos"]
    hoje = date.today().isoformat()

    total_lidas = 0
    total_inseridos = 0
    total_duplicados = 0
    total_invalidos = 0

    primeira_linha = True
    for row in ws.iter_rows(min_col=1, max_col=1, values_only=True):
        valor = row[0]

        # Pula o título "BASE DE PRODUTOS"
        if primeira_linha:
            primeira_linha = False
            continue

        total_lidas += 1

        if valor is None or str(valor).strip() == "":
            total_invalidos += 1
            continue

        descricao = str(valor).strip()
        chave = normalizar_chave(descricao)

        if not chave:
            total_invalidos += 1
            continue

        if chave in chaves_existentes:
            total_duplicados += 1
            continue

        cursor.execute("""
            INSERT INTO produtos (
                produto_padrao,
                chave_sku,
                origem,
                ativo,
                data_criacao,
                fabricante,
                categoria,
                sku,
                forma_farmaceutica,
                concentracao,
                apresentacao,
                unidade_compra
            ) VALUES (?, ?, 'BASE_PRODUTOS', 1, ?, NULL, NULL, NULL, NULL, NULL, NULL, NULL)
        """, (descricao, chave, hoje))

        chaves_existentes.add(chave)
        total_inseridos += 1

    conn.commit()
    conn.close()
    wb.close()

    label = "banco REAL" if confirmar else "cópia de TESTE"
    print(f"\n{'='*52}")
    print(f"RELATÓRIO DE IMPORTAÇÃO — {label}")
    print(f"{'='*52}")
    print(f"  Total de linhas lidas:            {total_lidas:>6}")
    print(f"  Total inseridos:                  {total_inseridos:>6}")
    print(f"  Total ignorados (duplicidade):    {total_duplicados:>6}")
    print(f"  Total com dados incompletos:      {total_invalidos:>6}")
    print(f"{'='*52}")

    if not confirmar:
        print("\nModo seguro (sem --confirmar): dados gravados apenas na cópia de teste.")
        print("Para importar no banco real, execute:")
        print("    python core/importador_base_produtos.py --confirmar")


if __name__ == "__main__":
    main()
