import pandas as pd
import sqlite3
import shutil
import sys
import os
from pathlib import Path
from datetime import datetime
from rapidfuzz import fuzz

# Adiciona o diretório raiz ao path para importar core
sys.path.append(str(Path(__file__).resolve().parent.parent))
from core.banco import DB_PATH, conectar

def criar_backup():
    if not DB_PATH.exists():
        return
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = DB_PATH.parent / "backups" / f"medbox_v3_before_import_{timestamp}.db"
    backup_path.parent.mkdir(exist_ok=True)
    shutil.copy2(DB_PATH, backup_path)
    print(f"Backup criado em: {backup_path}")

def importar_produtos():
    xlsx_path = Path("docs/Produtos.xlsx")
    if not xlsx_path.exists():
        print(f"Erro: Arquivo {xlsx_path} não encontrado.")
        return

    print(f"Lendo planilha {xlsx_path}...")
    # Lê a planilha, assumindo que a primeira linha é o cabeçalho 'BASE DE PRODUTOS'
    df = pd.read_excel(xlsx_path)

    # Se a coluna se chamar 'BASE DE PRODUTOS', pega ela.
    # Caso contrário, pega a primeira coluna disponível.
    col_name = df.columns[0]
    descricoes = df[col_name].dropna().unique().tolist()

    total_lido = len(descricoes)
    total_inserido = 0
    total_ignorado = 0

    print(f"Total de descrições únicas para processar: {total_lido}")

    criar_backup()

    conn = conectar()
    cursor = conn.cursor()

    # Cache para duplicatas
    # Pega descricoes originais de precos_fornecedores e produto_padrao de produtos
    cursor.execute("SELECT DISTINCT descricao_original FROM precos_fornecedores")
    cache_desc = [str(r[0]).upper().strip() for r in cursor.fetchall()]

    cursor.execute("SELECT DISTINCT produto_padrao FROM produtos")
    cache_padrao = [str(r[0]).upper().strip() for r in cursor.fetchall()]

    # Junta tudo num set para busca O(1) exata
    cache_total = set(cache_desc + cache_padrao)

    # Para fuzzy, precisamos da lista completa
    # Mas como são 8k novos vs o que já tem no banco, vamos ser estratégicos

    for desc in descricoes:
        desc_limpa = str(desc).strip()
        desc_upper = desc_limpa.upper()

        if not desc_limpa:
            total_ignorado += 1
            continue

        # 1. Match exato (rápido)
        if desc_upper in cache_total:
            total_ignorado += 1
            continue

        # 2. Match fuzzy (mais lento, >= 95)
        is_dupe = False
        # Para otimizar o fuzzy, só comparamos se houver suspeita,
        # mas a regra pede detectar duplicatas >= 95.
        # Com 8k itens, fazer 8k * N_banco token_set_ratio pode demorar.
        # Vamos usar uma abordagem de filtro por tokens comuns se necessário,
        # mas vamos tentar direto primeiro.

        for p_existente in cache_total:
            if fuzz.token_set_ratio(desc_upper, p_existente) >= 95:
                is_dupe = True
                break

        if is_dupe:
            total_ignorado += 1
            continue

        # 3. Inserção
        try:
            cursor.execute(
                """
                INSERT INTO produtos (sku, produto_padrao, fabricante, categoria, ativo, observacoes)
                VALUES ('', ?, '', '', 1, 'IMPORTADO_PLANILHA_CLIENTE')
                """,
                (desc_limpa,)
            )
            produto_id = cursor.lastrowid

            cursor.execute(
                "INSERT INTO equivalencias (produto_id, descricao_equivalente) VALUES (?, ?)",
                (produto_id, desc_limpa)
            )

            # Atualiza caches para evitar duplicar itens da própria planilha entre si
            cache_total.add(desc_upper)
            total_inserido += 1

            if total_inserido % 100 == 0:
                print(f"Inseridos: {total_inserido}...")
                conn.commit() # Commit parcial para segurança

        except Exception as e:
            print(f"Erro ao inserir {desc_limpa}: {e}")

    conn.commit()
    conn.close()

    print("-" * 30)
    print(f"IMPORTAÇÃO CONCLUÍDA")
    print(f"Total lido:     {total_lido}")
    print(f"Total inserido: {total_inserido}")
    print(f"Total ignorado: {total_ignorado}")
    print("-" * 30)

if __name__ == "__main__":
    importar_produtos()
