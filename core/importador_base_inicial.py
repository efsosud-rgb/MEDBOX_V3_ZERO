# core/importador_base_inicial.py

import os
import re
import sqlite3
import unicodedata
from datetime import datetime
from pathlib import Path

from openpyxl import load_workbook


RAIZ_PROJETO = Path(__file__).resolve().parent.parent

PASTA_BANCO = RAIZ_PROJETO / "banco"
CAMINHO_BANCO = PASTA_BANCO / "medbox.db"

PASTA_UPLOADS = RAIZ_PROJETO / "uploads"


UNIDADES_VALIDAS = {
    "UN", "UND", "UNI", "CX", "PCT", "FD", "FR", "FA", "AP", "AMP",
    "CP", "COM", "COMP", "CAP", "CA", "TB", "RL", "BO", "BOL",
    "SG", "KT", "PR", "GL", "ENV", "FRA", "CPR", "UN1"
}


def agora():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def hoje():
    return datetime.now().strftime("%Y-%m-%d")


def normalizar_texto(texto):
    if texto is None:
        return ""

    texto = str(texto).strip().upper()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = texto.replace("?", "")
    texto = re.sub(r"\s+", " ", texto)

    return texto.strip()


def normalizar_chave(texto):
    texto = normalizar_texto(texto)
    texto = re.sub(r"[^A-Z0-9]+", "", texto)
    return texto


def limpar_valor(valor):
    if valor is None:
        return None

    if isinstance(valor, (int, float)):
        return float(valor)

    texto = str(valor).strip()
    texto = texto.replace("R$", "")
    texto = texto.replace(".", "")
    texto = texto.replace(",", ".")
    texto = re.sub(r"[^0-9.]", "", texto)

    if not texto:
        return None

    try:
        return float(texto)
    except Exception:
        return None


def criar_tabela_bd_base_produtos():
    PASTA_BANCO.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(CAMINHO_BANCO)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS bd_base_produtos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_lancamento TEXT,
            razao_social_fornecedor TEXT,
            tipo_fornecedor TEXT,
            fornecedor TEXT,
            codigo_produto TEXT,
            descricao_produto TEXT,
            sku_master TEXT,
            marca TEXT,
            categoria TEXT,
            unidade_compra TEXT,
            valor_unitario REAL,
            chave_fornecedor TEXT,
            chave_produto TEXT,
            chave_unica TEXT UNIQUE,
            arquivo_origem TEXT,
            origem_importacao TEXT,
            data_importacao TEXT,
            ativo INTEGER DEFAULT 1
        )
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_bd_base_produtos_chave_unica
        ON bd_base_produtos (chave_unica)
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_bd_base_produtos_fornecedor_produto
        ON bd_base_produtos (chave_fornecedor, chave_produto)
    """)

    conn.commit()
    conn.close()


def localizar_coluna(cabecalho, possibilidades):
    cabecalho_norm = [normalizar_texto(c) for c in cabecalho]

    for termo in possibilidades:
        termo_norm = normalizar_texto(termo)
        for i, col in enumerate(cabecalho_norm):
            if col == termo_norm:
                return i

    for termo in possibilidades:
        termo_norm = normalizar_texto(termo)
        for i, col in enumerate(cabecalho_norm):
            if termo_norm in col:
                return i

    return None


def data_para_comparacao(data):
    if not data:
        return datetime.min

    if isinstance(data, datetime):
        return data

    texto = str(data).strip()

    formatos = [
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%Y-%m-%d %H:%M:%S",
        "%d/%m/%Y %H:%M:%S",
    ]

    for formato in formatos:
        try:
            return datetime.strptime(texto, formato)
        except Exception:
            pass

    return datetime.min


def montar_registro(
    data_lancamento=None,
    razao_social_fornecedor=None,
    tipo_fornecedor=None,
    fornecedor=None,
    codigo_produto=None,
    descricao_produto=None,
    sku_master=None,
    marca=None,
    categoria=None,
    unidade_compra=None,
    valor_unitario=None,
    arquivo_origem=None,
    origem_importacao=None,
):
    descricao_produto = normalizar_texto(descricao_produto)
    sku_master = normalizar_texto(sku_master)

    if not descricao_produto and not sku_master:
        return None

    fornecedor = normalizar_texto(fornecedor or razao_social_fornecedor or "SKU_MASTER")
    razao_social_fornecedor = normalizar_texto(razao_social_fornecedor or fornecedor)
    tipo_fornecedor = normalizar_texto(tipo_fornecedor or "")
    codigo_produto = normalizar_texto(codigo_produto or "")
    marca = normalizar_texto(marca or "")
    categoria = normalizar_texto(categoria or "")
    unidade_compra = normalizar_texto(unidade_compra or "")

    if not data_lancamento:
        data_lancamento = hoje()
    elif isinstance(data_lancamento, datetime):
        data_lancamento = data_lancamento.strftime("%Y-%m-%d")
    else:
        data_lancamento = str(data_lancamento).strip()

    chave_fornecedor = normalizar_chave(fornecedor)
    chave_produto = normalizar_chave(sku_master or descricao_produto)
    chave_unica = f"{chave_fornecedor}_{chave_produto}"

    return {
        "data_lancamento": data_lancamento,
        "razao_social_fornecedor": razao_social_fornecedor,
        "tipo_fornecedor": tipo_fornecedor,
        "fornecedor": fornecedor,
        "codigo_produto": codigo_produto,
        "descricao_produto": descricao_produto,
        "sku_master": sku_master,
        "marca": marca,
        "categoria": categoria,
        "unidade_compra": unidade_compra,
        "valor_unitario": limpar_valor(valor_unitario),
        "chave_fornecedor": chave_fornecedor,
        "chave_produto": chave_produto,
        "chave_unica": chave_unica,
        "arquivo_origem": arquivo_origem,
        "origem_importacao": origem_importacao,
        "data_importacao": agora(),
        "ativo": 1,
    }


def inserir_ou_atualizar(registro):
    conn = sqlite3.connect(CAMINHO_BANCO)
    cur = conn.cursor()

    cur.execute("""
        SELECT id, data_lancamento
        FROM bd_base_produtos
        WHERE chave_unica = ?
        LIMIT 1
    """, (registro["chave_unica"],))

    existente = cur.fetchone()

    if existente:
        id_existente, data_existente = existente

        if data_para_comparacao(registro["data_lancamento"]) >= data_para_comparacao(data_existente):
            cur.execute("""
                UPDATE bd_base_produtos SET
                    data_lancamento = ?,
                    razao_social_fornecedor = ?,
                    tipo_fornecedor = ?,
                    fornecedor = ?,
                    codigo_produto = ?,
                    descricao_produto = ?,
                    sku_master = ?,
                    marca = ?,
                    categoria = ?,
                    unidade_compra = ?,
                    valor_unitario = ?,
                    chave_fornecedor = ?,
                    chave_produto = ?,
                    chave_unica = ?,
                    arquivo_origem = ?,
                    origem_importacao = ?,
                    data_importacao = ?,
                    ativo = 1
                WHERE id = ?
            """, (
                registro["data_lancamento"],
                registro["razao_social_fornecedor"],
                registro["tipo_fornecedor"],
                registro["fornecedor"],
                registro["codigo_produto"],
                registro["descricao_produto"],
                registro["sku_master"],
                registro["marca"],
                registro["categoria"],
                registro["unidade_compra"],
                registro["valor_unitario"],
                registro["chave_fornecedor"],
                registro["chave_produto"],
                registro["chave_unica"],
                registro["arquivo_origem"],
                registro["origem_importacao"],
                registro["data_importacao"],
                id_existente,
            ))

            status = "ATUALIZADO_MAIS_RECENTE"
        else:
            status = "IGNORADO_DUPLICADO_ANTIGO"

    else:
        cur.execute("""
            INSERT INTO bd_base_produtos (
                data_lancamento,
                razao_social_fornecedor,
                tipo_fornecedor,
                fornecedor,
                codigo_produto,
                descricao_produto,
                sku_master,
                marca,
                categoria,
                unidade_compra,
                valor_unitario,
                chave_fornecedor,
                chave_produto,
                chave_unica,
                arquivo_origem,
                origem_importacao,
                data_importacao,
                ativo
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            registro["data_lancamento"],
            registro["razao_social_fornecedor"],
            registro["tipo_fornecedor"],
            registro["fornecedor"],
            registro["codigo_produto"],
            registro["descricao_produto"],
            registro["sku_master"],
            registro["marca"],
            registro["categoria"],
            registro["unidade_compra"],
            registro["valor_unitario"],
            registro["chave_fornecedor"],
            registro["chave_produto"],
            registro["chave_unica"],
            registro["arquivo_origem"],
            registro["origem_importacao"],
            registro["data_importacao"],
            registro["ativo"],
        ))

        status = "INSERIDO"

    conn.commit()
    conn.close()

    return status


def importar_sku_master(caminho_arquivo):
    wb = load_workbook(caminho_arquivo, data_only=True)
    ws = wb.active

    linhas = list(ws.iter_rows(values_only=True))

    if not linhas:
        return {
            "arquivo": caminho_arquivo,
            "inseridos": 0,
            "atualizados": 0,
            "ignorados": 0,
        }

    cabecalho = list(linhas[0])

    col_codigo = localizar_coluna(cabecalho, [
        "codigo",
        "cod",
        "sku",
        "codigo produto",
        "codigo_produto",
    ])

    col_descricao = localizar_coluna(cabecalho, [
        "descricao",
        "descrição",
        "produto",
        "descricao produto",
        "descrição produto",
        "descricao_produto",
    ])

    col_sku_master = localizar_coluna(cabecalho, [
        "sku master",
        "sku_master",
        "nome padrao",
        "nome padrão",
        "produto padrao",
        "produto padrão",
        "descricao padronizada",
        "descrição padronizada",
        "nome fantasia",
    ])

    col_marca = localizar_coluna(cabecalho, [
        "marca",
        "fabricante",
        "laboratorio",
        "laboratório",
    ])

    col_categoria = localizar_coluna(cabecalho, [
        "categoria",
        "tipo",
        "classe",
    ])

    col_unidade = localizar_coluna(cabecalho, [
        "unidade",
        "unidade compra",
        "unidade_compra",
        "und",
        "un",
    ])

    col_valor = localizar_coluna(cabecalho, [
        "valor",
        "preco",
        "preço",
        "valor unitario",
        "valor unitário",
        "valor_unitario",
    ])

    col_data = localizar_coluna(cabecalho, [
        "data",
        "data lancamento",
        "data lançamento",
        "data_lancamento",
        "data cadastro",
    ])

    inseridos = 0
    atualizados = 0
    ignorados = 0

    for linha in linhas[1:]:
        if not any(linha):
            continue

        descricao = linha[col_descricao] if col_descricao is not None and col_descricao < len(linha) else None

        sku_master = (
            linha[col_sku_master]
            if col_sku_master is not None and col_sku_master < len(linha)
            else descricao
        )

        registro = montar_registro(
            data_lancamento=linha[col_data] if col_data is not None and col_data < len(linha) else hoje(),
            razao_social_fornecedor="SKU_MASTER",
            tipo_fornecedor="BASE_INTERNA",
            fornecedor="SKU_MASTER",
            codigo_produto=linha[col_codigo] if col_codigo is not None and col_codigo < len(linha) else None,
            descricao_produto=descricao,
            sku_master=sku_master,
            marca=linha[col_marca] if col_marca is not None and col_marca < len(linha) else None,
            categoria=linha[col_categoria] if col_categoria is not None and col_categoria < len(linha) else None,
            unidade_compra=linha[col_unidade] if col_unidade is not None and col_unidade < len(linha) else None,
            valor_unitario=linha[col_valor] if col_valor is not None and col_valor < len(linha) else None,
            arquivo_origem=os.path.basename(caminho_arquivo),
            origem_importacao="SKU_MASTER_2_0",
        )

        if not registro:
            continue

        status = inserir_ou_atualizar(registro)

        if status == "INSERIDO":
            inseridos += 1
        elif status == "ATUALIZADO_MAIS_RECENTE":
            atualizados += 1
        else:
            ignorados += 1

    return {
        "arquivo": caminho_arquivo,
        "inseridos": inseridos,
        "atualizados": atualizados,
        "ignorados": ignorados,
    }


def converter_doc_para_docx(caminho_doc):
    caminho_doc = Path(caminho_doc)
    caminho_docx = caminho_doc.with_suffix(".docx")

    if caminho_docx.exists():
        return str(caminho_docx)

    try:
        import win32com.client

        word = win32com.client.Dispatch("Word.Application")
        word.Visible = False

        doc = word.Documents.Open(str(caminho_doc.resolve()))
        doc.SaveAs(str(caminho_docx.resolve()), FileFormat=16)
        doc.Close()
        word.Quit()

        return str(caminho_docx)

    except Exception as erro:
        print("Não foi possível converter .doc para .docx automaticamente.")
        print("Abra o arquivo RELATORIO PRODUTO.doc no Word.")
        print("Clique em Salvar Como.")
        print("Salve como RELATORIO PRODUTO.docx dentro da pasta uploads.")
        print("Erro:", erro)
        return None


def extrair_texto_docx(caminho_docx):
    try:
        from docx import Document
    except Exception:
        print("Biblioteca python-docx não instalada.")
        print("Instale com:")
        print("pip install python-docx")
        return ""

    document = Document(caminho_docx)

    partes = []

    for paragrafo in document.paragraphs:
        texto = paragrafo.text.strip()
        if texto:
            partes.append(texto)

    for tabela in document.tables:
        for row in tabela.rows:
            valores = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if valores:
                partes.append(" ".join(valores))

    return "\n".join(partes)


def extrair_data_emissao(texto):
    padrao = re.search(r"EMISSAO\s*:\s*(\d{2}/\d{2}/\d{4})", normalizar_texto(texto))

    if padrao:
        data_br = padrao.group(1)
        try:
            return datetime.strptime(data_br, "%d/%m/%Y").strftime("%Y-%m-%d")
        except Exception:
            return hoje()

    return hoje()


def linha_eh_produto_relatorio(linha):
    linha = linha.strip()

    if not linha:
        return False

    linha_norm = normalizar_texto(linha)

    if linha_norm in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        return False

    ignorar = [
        "RAZAO SINTETICO",
        "PAGINA",
        "PRODUTO DESCRICAO",
        "EST.INICIAL",
        "SUBTOTAL",
        "TOTAL",
        "CONTINUA",
        "EMITIDO EM",
        "------",
    ]

    for termo in ignorar:
        if termo in linha_norm:
            return False

    return bool(re.match(r"^\s*\d{1,6}\s+", linha))


def remover_colunas_estoque(linha):
    linha = normalizar_texto(linha)

    numeros = r"-?\d[\d ]*,\d{2}"
    padrao_final = rf"\s+{numeros}\s+{numeros}\s+{numeros}\s+{numeros}\s+{numeros}\s+{numeros}\s*$"

    linha_sem_estoque = re.sub(padrao_final, "", linha).strip()

    return linha_sem_estoque


def quebrar_linha_relatorio_produto(linha):
    linha = remover_colunas_estoque(linha)

    match_codigo = re.match(r"^(\d{1,6})\s+(.+)$", linha)

    if not match_codigo:
        return None

    codigo_produto = match_codigo.group(1).strip()
    restante = match_codigo.group(2).strip()

    tokens = restante.split()

    if len(tokens) < 2:
        return None

    unidade_compra = ""

    if tokens[-1] in UNIDADES_VALIDAS:
        unidade_compra = tokens[-1]
        descricao_tokens = tokens[:-1]
    else:
        unidade_compra = ""
        descricao_tokens = tokens

    descricao_produto = " ".join(descricao_tokens).strip()

    descricao_produto = re.sub(r"\(ITEM:\s*\)", "", descricao_produto)
    descricao_produto = re.sub(r"\s+", " ", descricao_produto).strip()

    if not descricao_produto:
        return None

    return {
        "codigo_produto": codigo_produto,
        "descricao_produto": descricao_produto,
        "unidade_compra": unidade_compra,
    }


def importar_relatorio_produto_doc(caminho_arquivo):
    caminho = Path(caminho_arquivo)

    if caminho.suffix.lower() == ".doc":
        caminho_docx = converter_doc_para_docx(caminho_arquivo)

        if not caminho_docx:
            return {
                "arquivo": caminho_arquivo,
                "inseridos": 0,
                "atualizados": 0,
                "ignorados": 0,
            }
    else:
        caminho_docx = caminho_arquivo

    texto = extrair_texto_docx(caminho_docx)

    if not texto:
        return {
            "arquivo": caminho_arquivo,
            "inseridos": 0,
            "atualizados": 0,
            "ignorados": 0,
        }

    data_lancamento = extrair_data_emissao(texto)

    inseridos = 0
    atualizados = 0
    ignorados = 0
    lidos = 0

    for linha in texto.splitlines():
        if not linha_eh_produto_relatorio(linha):
            continue

        produto = quebrar_linha_relatorio_produto(linha)

        if not produto:
            ignorados += 1
            continue

        lidos += 1

        registro = montar_registro(
            data_lancamento=data_lancamento,
            razao_social_fornecedor="MEDBOX DISTRIBUIDORA DE MEDICAMENTOS",
            tipo_fornecedor="BASE_INTERNA",
            fornecedor="MEDBOX",
            codigo_produto=produto["codigo_produto"],
            descricao_produto=produto["descricao_produto"],
            sku_master=produto["descricao_produto"],
            marca="",
            categoria="",
            unidade_compra=produto["unidade_compra"],
            valor_unitario=None,
            arquivo_origem=os.path.basename(caminho_arquivo),
            origem_importacao="RELATORIO_PRODUTO",
        )

        if not registro:
            ignorados += 1
            continue

        status = inserir_ou_atualizar(registro)

        if status == "INSERIDO":
            inseridos += 1
        elif status == "ATUALIZADO_MAIS_RECENTE":
            atualizados += 1
        else:
            ignorados += 1

    print(f"Linhas de produto lidas do relatório: {lidos}")

    return {
        "arquivo": caminho_arquivo,
        "inseridos": inseridos,
        "atualizados": atualizados,
        "ignorados": ignorados,
    }


def localizar_arquivo(nome_base):
    if not PASTA_UPLOADS.exists():
        return None

    nome_base_norm = normalizar_chave(nome_base)

    for arquivo in PASTA_UPLOADS.iterdir():
        if arquivo.is_file():
            if nome_base_norm in normalizar_chave(arquivo.name):
                return str(arquivo)

    return None


def localizar_relatorio_produto():
    if not PASTA_UPLOADS.exists():
        return None

    possibilidades = [
        "RELATORIO PRODUTO",
        "TABELA COMPRAS MEDBOX",
        "RAZAO SINTETICO",
        "PRODUTOS MEDBOX",
        "COMPRAS MEDBOX",
    ]

    for nome in possibilidades:
        encontrado = localizar_arquivo(nome)
        if encontrado:
            return encontrado

    for arquivo in PASTA_UPLOADS.iterdir():
        if arquivo.is_file() and arquivo.suffix.lower() in [".doc", ".docx"]:
            return str(arquivo)

    return None


def importar_base_inicial(
    caminho_sku_master=None,
    caminho_relatorio_produto=None,
):
    criar_tabela_bd_base_produtos()

    if caminho_sku_master is None:
        caminho_sku_master = localizar_arquivo("SKU_MASTER")

    if caminho_relatorio_produto is None:
        caminho_relatorio_produto = localizar_relatorio_produto()

    resultados = []

    if caminho_sku_master and os.path.exists(caminho_sku_master):
        print(f"Importando SKU_MASTER: {caminho_sku_master}")
        resultados.append(importar_sku_master(caminho_sku_master))
    else:
        print("Arquivo SKU_MASTER não encontrado na pasta uploads.")

    if caminho_relatorio_produto and os.path.exists(caminho_relatorio_produto):
        print(f"Importando RELATORIO PRODUTO: {caminho_relatorio_produto}")
        resultados.append(importar_relatorio_produto_doc(caminho_relatorio_produto))
    else:
        print("Arquivo RELATORIO PRODUTO não encontrado na pasta uploads.")

    return resultados


if __name__ == "__main__":
    print("IMPORTADOR BASE INICIAL MEDBOX V3 ZERO")
    print("-" * 60)
    print(f"Banco usado: {CAMINHO_BANCO}")
    print(f"Pasta de uploads: {PASTA_UPLOADS}")
    print("-" * 60)

    resultados = importar_base_inicial()

    print("\nRESULTADO FINAL:")

    if not resultados:
        print("Nenhum arquivo foi importado.")
    else:
        for resultado in resultados:
            print("-" * 60)
            print("Arquivo:", resultado["arquivo"])
            print("Inseridos:", resultado["inseridos"])
            print("Atualizados:", resultado["atualizados"])
            print("Ignorados:", resultado["ignorados"])

    print("-" * 60)
    print("Processo finalizado.")