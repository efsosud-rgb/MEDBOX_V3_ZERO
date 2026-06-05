from pathlib import Path
from datetime import datetime
import xml.etree.ElementTree as ET

from core.banco import conectar


def _texto(elemento, caminho, ns):
    achado = elemento.find(caminho, ns)
    if achado is not None and achado.text:
        return achado.text.strip()
    return ""


def _float(valor):
    try:
        return float(str(valor).replace(",", "."))
    except:
        return 0.0


def garantir_fornecedor(cursor, nome, tipo="Distribuidor"):
    nome = (nome or "FORNECEDOR NAO IDENTIFICADO").strip().upper()

    cursor.execute("SELECT id FROM fornecedores WHERE nome = ?", (nome,))
    row = cursor.fetchone()

    if row:
        return row["id"]

    cursor.execute("""
        INSERT INTO fornecedores (nome, tipo, contato, email, telefone, ativo)
        VALUES (?, ?, '', '', '', 1)
    """, (nome, tipo))

    return cursor.lastrowid


def garantir_produto(cursor, descricao, codigo="", marca="", categoria=""):
    descricao = (descricao or "").strip().upper()

    cursor.execute("SELECT id FROM produtos WHERE produto_padrao = ?", (descricao,))
    row = cursor.fetchone()

    if row:
        return row["id"]

    cursor.execute("""
        INSERT INTO produtos (sku, produto_padrao, fabricante, categoria, ativo)
        VALUES (?, ?, ?, ?, 1)
    """, (codigo, descricao, marca, categoria))

    produto_id = cursor.lastrowid

    cursor.execute("""
        INSERT INTO equivalencias (produto_id, descricao_equivalente)
        VALUES (?, ?)
    """, (produto_id, descricao))

    return produto_id


def importar_xml_nfe(caminho_xml):
    caminho_xml = Path(caminho_xml)

    tree = ET.parse(caminho_xml)
    root = tree.getroot()

    ns = {"nfe": "http://www.portalfiscal.inf.br/nfe"}

    inf_nfe = root.find(".//nfe:infNFe", ns)
    if inf_nfe is None:
        raise Exception("XML inválido: não encontrei a estrutura infNFe.")

    ide = inf_nfe.find("nfe:ide", ns)
    emit = inf_nfe.find("nfe:emit", ns)

    numero_nf = _texto(ide, "nfe:nNF", ns)
    data_emissao = _texto(ide, "nfe:dhEmi", ns) or _texto(ide, "nfe:dEmi", ns)

    fornecedor_nome = _texto(emit, "nfe:xNome", ns)
    fornecedor_cnpj = _texto(emit, "nfe:CNPJ", ns)

    if data_emissao:
        data_importacao = data_emissao[:10]
    else:
        data_importacao = datetime.now().strftime("%Y-%m-%d")

    conn = conectar()
    cursor = conn.cursor()

    fornecedor_id = garantir_fornecedor(cursor, fornecedor_nome, "Distribuidor")

    total_itens = 0

    for det in inf_nfe.findall("nfe:det", ns):
        prod = det.find("nfe:prod", ns)

        if prod is None:
            continue

        codigo = _texto(prod, "nfe:cProd", ns)
        ean = _texto(prod, "nfe:cEAN", ns)
        descricao = _texto(prod, "nfe:xProd", ns)
        ncm = _texto(prod, "nfe:NCM", ns)
        cfop = _texto(prod, "nfe:CFOP", ns)
        unidade = _texto(prod, "nfe:uCom", ns)

        quantidade = _float(_texto(prod, "nfe:qCom", ns))
        valor_unitario = _float(_texto(prod, "nfe:vUnCom", ns))
        valor_total = _float(_texto(prod, "nfe:vProd", ns))

        if not descricao or valor_unitario <= 0:
            continue

        produto_id = garantir_produto(
            cursor,
            descricao=descricao,
            codigo=codigo,
            marca="",
            categoria=""
        )

        cursor.execute("""
            SELECT id FROM equivalencias
            WHERE produto_id = ? AND UPPER(descricao_equivalente) = ?
        """, (produto_id, descricao.upper()))

        if not cursor.fetchone():
            cursor.execute("""
                INSERT INTO equivalencias (produto_id, descricao_equivalente)
                VALUES (?, ?)
            """, (produto_id, descricao.upper()))

        cursor.execute("""
            INSERT INTO precos_fornecedores
            (fornecedor_id, produto_id, descricao_original, codigo_fornecedor, marca, preco, data_importacao)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            fornecedor_id,
            produto_id,
            descricao.upper(),
            codigo,
            "",
            valor_unitario,
            data_importacao
        ))

        total_itens += 1

    cursor.execute("""
        INSERT INTO cotacoes (fornecedor_id, data_importacao, arquivo_origem, total_itens)
        VALUES (?, ?, ?, ?)
    """, (
        fornecedor_id,
        data_importacao,
        caminho_xml.name,
        total_itens
    ))

    conn.commit()
    conn.close()

    return {
        "nota_fiscal": numero_nf,
        "fornecedor": fornecedor_nome,
        "cnpj": fornecedor_cnpj,
        "data_emissao": data_importacao,
        "itens_importados": total_itens
    }