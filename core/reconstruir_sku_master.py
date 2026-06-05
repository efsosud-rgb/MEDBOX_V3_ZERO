# core/reconstruir_sku_master.py

import sqlite3
import re
import unicodedata
from pathlib import Path
from datetime import datetime


BASE_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BASE_DIR / "banco" / "medbox.db"


def conectar():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def normalizar_texto(texto):
    if texto is None:
        return ""

    texto = str(texto).upper().strip()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = re.sub(r"\s+", " ", texto)
    return texto.strip()


def normalizar_chave(texto):
    texto = normalizar_texto(texto)
    texto = re.sub(r"[^A-Z0-9]+", " ", texto)
    texto = re.sub(r"\s+", " ", texto)
    return texto.strip()


def agora():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def criar_tabelas_inteligentes():
    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS sku_master (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sku_master TEXT NOT NULL,
            chave_sku TEXT NOT NULL UNIQUE,
            fabricante TEXT,
            categoria TEXT,
            forma_farmaceutica TEXT,
            concentracao TEXT,
            apresentacao TEXT,
            unidade_compra TEXT,
            origem TEXT,
            data_criacao TEXT,
            ativo INTEGER DEFAULT 1
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS produtos_fornecedores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sku_master_id INTEGER,
            fornecedor TEXT,
            tipo_fornecedor TEXT,
            codigo_fornecedor TEXT,
            descricao_fornecedor TEXT,
            marca TEXT,
            categoria_fornecedor TEXT,
            unidade_compra TEXT,
            valor_unitario REAL,
            data_lancamento TEXT,
            arquivo_origem TEXT,
            origem_importacao TEXT,
            chave_fornecedor TEXT,
            chave_produto_fornecedor TEXT,
            chave_unica TEXT UNIQUE,
            data_criacao TEXT,
            ativo INTEGER DEFAULT 1
        )
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_sku_master_chave
        ON sku_master (chave_sku)
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_prod_fornecedor_sku
        ON produtos_fornecedores (sku_master_id)
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_prod_fornecedor_desc
        ON produtos_fornecedores (descricao_fornecedor)
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_prod_fornecedor_fornecedor
        ON produtos_fornecedores (fornecedor)
    """)

    conn.commit()
    conn.close()


def limpar_sku_basico(texto):
    texto = normalizar_texto(texto)

    removiveis = [
        " GENERICO",
        " GENÉRICO",
        " MARCA",
        " MANIPULADO",
        " IMPORTADO",
        " ADULTO",
        " INFANTIL",
        " PEDIATRICO",
        " PEDIÁTRICO",
    ]

    for termo in removiveis:
        texto = texto.replace(termo, "")

    texto = texto.replace(" DRAGEA", " COMP")
    texto = texto.replace(" DRAGEAS", " COMP")
    texto = texto.replace(" COMPRIMIDOS", " COMP")
    texto = texto.replace(" COMPRIMIDO", " COMP")
    texto = texto.replace(" CAPSULAS", " CAPS")
    texto = texto.replace(" CAPSULA", " CAPS")
    texto = texto.replace(" AMPOLA", " AMP")
    texto = texto.replace(" FRASCO AMPOLA", " FR AMP")
    texto = texto.replace(" FRASCO-AMPOLA", " FR AMP")
    texto = texto.replace(" FRASCO", " FR")
    texto = texto.replace(" SOLUCAO INJETAVEL", " SOL INJ")
    texto = texto.replace(" SOLUÇÃO INJETÁVEL", " SOL INJ")
    texto = texto.replace(" SOLUCAO", " SOL")
    texto = texto.replace(" SUSPENSAO", " SUSP")
    texto = texto.replace(" XAROPE", " XPE")

    texto = re.sub(r"\s+", " ", texto)
    return texto.strip()


def extrair_categoria(descricao):
    d = normalizar_texto(descricao)

    termos_medicamento = [
        "MG",
        "MCG",
        "ML",
        "SOL INJ",
        "SOLUCAO INJETAVEL",
        "COMPRIMIDO",
        "COMP",
        "CAPS",
        "AMP",
        "FR AMP",
        "XAROPE",
        "SUSP",
        "GLICOSE",
        "CLORETO DE SODIO",
        "SORO",
        "DIPIRONA",
        "CEFTRIAXONA",
        "PREDNISOLONA",
        "ATENOLOL",
    ]

    termos_correlato = [
        "AGULHA",
        "SERINGA",
        "CATETER",
        "EQUIPO",
        "FIO",
        "SONDA",
        "LUVA",
        "MASCARA",
        "GAZE",
        "ATADURA",
        "COLETOR",
        "DRENO",
        "JELCO",
    ]

    for termo in termos_correlato:
        if termo in d:
            return "CORRELATO"

    for termo in termos_medicamento:
        if termo in d:
            return "MEDICAMENTO"

    return ""


def extrair_unidade(descricao):
    d = normalizar_texto(descricao)

    unidades = [
        "AMP",
        "FR AMP",
        "FR",
        "COMP",
        "CAPS",
        "UN",
        "CX",
        "PCT",
        "RL",
        "AP",
        "BOLSA",
        "ENV",
    ]

    for unidade in unidades:
        if re.search(rf"\b{re.escape(unidade)}\b", d):
            return unidade

    return ""


def extrair_concentracao(descricao):
    d = normalizar_texto(descricao)

    padroes = [
        r"\d+[,.]?\d*\s*MG/\s*ML",
        r"\d+[,.]?\d*\s*MG",
        r"\d+[,.]?\d*\s*MCG",
        r"\d+[,.]?\d*\s*%",
        r"\d+[,.]?\d*\s*G",
    ]

    achados = []

    for padrao in padroes:
        for m in re.findall(padrao, d):
            achados.append(re.sub(r"\s+", "", m))

    return " ".join(achados[:3])


def extrair_apresentacao(descricao):
    d = normalizar_texto(descricao)

    padroes = [
        r"\d+[,.]?\d*\s*ML",
        r"\d+[,.]?\d*\s*L",
        r"\d+[,.]?\d*\s*G",
        r"\d+[,.]?\d*\s*CM",
        r"\d+[,.]?\d*\s*MM",
        r"\d+\s*FR",
        r"\d+\s*G",
    ]

    achados = []

    for padrao in padroes:
        for m in re.findall(padrao, d):
            achados.append(re.sub(r"\s+", "", m))

    return " ".join(achados[:4])


def extrair_forma(descricao):
    d = normalizar_texto(descricao)

    formas = [
        ("SOL INJ", "SOL INJ"),
        ("SOLUCAO INJETAVEL", "SOL INJ"),
        ("INJETAVEL", "SOL INJ"),
        ("COMPRIMIDO", "ORAL COMP"),
        ("COMP", "ORAL COMP"),
        ("CAPS", "ORAL CAPS"),
        ("XAROPE", "ORAL XPE"),
        ("SUSP", "SUSP"),
        ("CREME", "TOPICO CREME"),
        ("POMADA", "TOPICO POMADA"),
        ("COLIRIO", "OFTALMICO"),
        ("AGULHA", "MATERIAL HOSPITALAR"),
        ("SERINGA", "MATERIAL HOSPITALAR"),
        ("CATETER", "MATERIAL HOSPITALAR"),
        ("EQUIPO", "MATERIAL HOSPITALAR"),
        ("FIO", "MATERIAL HOSPITALAR"),
    ]

    for termo, forma in formas:
        if termo in d:
            return forma

    return ""


def inserir_sku_master(sku, fabricante="", categoria="", origem="MIGRACAO"):
    sku_limpo = limpar_sku_basico(sku)

    if not sku_limpo:
        return None

    chave_sku = normalizar_chave(sku_limpo)

    categoria_final = normalizar_texto(categoria) or extrair_categoria(sku_limpo)
    unidade = extrair_unidade(sku_limpo)
    concentracao = extrair_concentracao(sku_limpo)
    apresentacao = extrair_apresentacao(sku_limpo)
    forma = extrair_forma(sku_limpo)

    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
        SELECT id FROM sku_master
        WHERE chave_sku = ?
    """, (chave_sku,))

    row = cur.fetchone()

    if row:
        sku_id = row["id"]

        cur.execute("""
            UPDATE sku_master
            SET fabricante = COALESCE(NULLIF(?, ''), fabricante),
                categoria = COALESCE(NULLIF(?, ''), categoria),
                forma_farmaceutica = COALESCE(NULLIF(?, ''), forma_farmaceutica),
                concentracao = COALESCE(NULLIF(?, ''), concentracao),
                apresentacao = COALESCE(NULLIF(?, ''), apresentacao),
                unidade_compra = COALESCE(NULLIF(?, ''), unidade_compra),
                ativo = 1
            WHERE id = ?
        """, (
            normalizar_texto(fabricante),
            categoria_final,
            forma,
            concentracao,
            apresentacao,
            unidade,
            sku_id,
        ))

    else:
        cur.execute("""
            INSERT INTO sku_master (
                sku_master,
                chave_sku,
                fabricante,
                categoria,
                forma_farmaceutica,
                concentracao,
                apresentacao,
                unidade_compra,
                origem,
                data_criacao,
                ativo
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
        """, (
            sku_limpo,
            chave_sku,
            normalizar_texto(fabricante),
            categoria_final,
            forma,
            concentracao,
            apresentacao,
            unidade,
            origem,
            agora(),
        ))

        sku_id = cur.lastrowid

    conn.commit()
    conn.close()

    return sku_id


def inserir_produto_fornecedor(row, sku_master_id):
    fornecedor = normalizar_texto(row["fornecedor"] or "FORNECEDOR NAO IDENTIFICADO")
    descricao = normalizar_texto(row["descricao_produto"] or row["sku_master"])
    codigo = str(row["codigo_produto"] or "").strip()
    marca = normalizar_texto(row["marca"])
    categoria = normalizar_texto(row["categoria"])
    unidade = normalizar_texto(row["unidade_compra"])
    valor = row["valor_unitario"] or 0
    data_lancamento = row["data_lancamento"] or ""
    tipo_fornecedor = normalizar_texto(row["tipo_fornecedor"])
    arquivo_origem = str(row["arquivo_origem"] or "")
    origem_importacao = normalizar_texto(row["origem_importacao"])

    chave_fornecedor = normalizar_chave(fornecedor)
    chave_produto_fornecedor = normalizar_chave(descricao)
    chave_unica = f"{chave_fornecedor}||{chave_produto_fornecedor}"

    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
        INSERT OR REPLACE INTO produtos_fornecedores (
            sku_master_id,
            fornecedor,
            tipo_fornecedor,
            codigo_fornecedor,
            descricao_fornecedor,
            marca,
            categoria_fornecedor,
            unidade_compra,
            valor_unitario,
            data_lancamento,
            arquivo_origem,
            origem_importacao,
            chave_fornecedor,
            chave_produto_fornecedor,
            chave_unica,
            data_criacao,
            ativo
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
    """, (
        sku_master_id,
        fornecedor,
        tipo_fornecedor,
        codigo,
        descricao,
        marca,
        categoria,
        unidade,
        valor,
        data_lancamento,
        arquivo_origem,
        origem_importacao,
        chave_fornecedor,
        chave_produto_fornecedor,
        chave_unica,
        agora(),
    ))

    conn.commit()
    conn.close()


def migrar_sku_master():
    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM bd_base_produtos
        WHERE ativo = 1
        AND origem_importacao = 'SKU_MASTER_2_0'
    """)

    rows = [dict(r) for r in cur.fetchall()]
    conn.close()

    inseridos = 0

    for row in rows:
        sku = row["sku_master"] or row["descricao_produto"]

        sku_id = inserir_sku_master(
            sku=sku,
            fabricante=row["marca"],
            categoria=row["categoria"],
            origem="SKU_MASTER_2_0"
        )

        if sku_id:
            inseridos += 1

    return inseridos


def migrar_produtos_fornecedores():
    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM bd_base_produtos
        WHERE ativo = 1
    """)

    rows = [dict(r) for r in cur.fetchall()]
    conn.close()

    vinculados = 0
    nao_vinculados = 0

    for row in rows:
        sku = row["sku_master"] or row["descricao_produto"]
        chave_sku = normalizar_chave(limpar_sku_basico(sku))

        conn = conectar()
        cur = conn.cursor()

        cur.execute("""
            SELECT id
            FROM sku_master
            WHERE chave_sku = ?
        """, (chave_sku,))

        sku_row = cur.fetchone()
        conn.close()

        if not sku_row:
            sku_id = inserir_sku_master(
                sku=sku,
                fabricante=row["marca"],
                categoria=row["categoria"],
                origem="CRIADO_PELA_MIGRACAO"
            )
            nao_vinculados += 1
        else:
            sku_id = sku_row["id"]
            vinculados += 1

        inserir_produto_fornecedor(row, sku_id)

    return vinculados, nao_vinculados


def resumo():
    conn = conectar()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM sku_master WHERE ativo = 1")
    total_sku = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM produtos_fornecedores WHERE ativo = 1")
    total_fornecedor = cur.fetchone()[0]

    cur.execute("""
        SELECT origem, COUNT(*) total
        FROM sku_master
        GROUP BY origem
        ORDER BY total DESC
    """)
    origem_sku = cur.fetchall()

    conn.close()

    return total_sku, total_fornecedor, origem_sku


def reconstruir():
    print("RECONSTRUINDO ESTRUTURA INTELIGENTE SKU MASTER")
    print("-" * 60)

    criar_tabelas_inteligentes()

    print("Migrando SKU_MASTER 2.0...")
    total_sku_migrados = migrar_sku_master()
    print(f"SKU Master migrados/atualizados: {total_sku_migrados}")

    print("Migrando produtos de fornecedores...")
    vinculados, nao_vinculados = migrar_produtos_fornecedores()
    print(f"Produtos vinculados a SKU existente: {vinculados}")
    print(f"Produtos que criaram SKU provisório: {nao_vinculados}")

    total_sku, total_fornecedor, origem_sku = resumo()

    print("-" * 60)
    print(f"Total SKU Master ativo: {total_sku}")
    print(f"Total produtos fornecedores ativo: {total_fornecedor}")

    print("-" * 60)
    print("Origem dos SKUs:")

    for row in origem_sku:
        print(f"{row['origem']}: {row['total']}")

    print("-" * 60)
    print("Processo finalizado.")


if __name__ == "__main__":
    reconstruir()