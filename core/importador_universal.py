import re
import json
import urllib.request
from pathlib import Path
from datetime import datetime

from core.banco import conectar, registrar_preco_fornecedor


# ================================================
# LEITORES POR FORMATO
# ================================================

def ler_pdf(caminho):
    import pdfplumber

    linhas = []

    with pdfplumber.open(caminho) as pdf:
        for pagina in pdf.pages:
            texto = pagina.extract_text()
            if texto:
                linhas += texto.splitlines()

    return linhas


def ler_excel(caminho):
    from openpyxl import load_workbook

    wb = load_workbook(caminho, data_only=True)
    resultados = []

    for ws in wb.worksheets:
        cabecalhos = []

        for i, row in enumerate(ws.iter_rows(values_only=True)):
            if i == 0:
                cabecalhos = [str(c).strip().upper() if c else "" for c in row]
                continue

            if all(c is None for c in row):
                continue

            item = {}

            for j, val in enumerate(row):
                if j < len(cabecalhos):
                    item[cabecalhos[j]] = val

            resultados.append(item)

    return resultados


def ler_csv(caminho):
    import csv

    resultados = []

    with open(caminho, encoding="utf-8", errors="ignore") as f:
        reader = csv.DictReader(f)

        for row in reader:
            resultados.append({k.strip().upper(): v for k, v in row.items()})

    return resultados


def ler_txt(caminho):
    with open(caminho, encoding="utf-8", errors="ignore") as f:
        return f.readlines()


def ler_docx(caminho):
    from docx import Document

    doc = Document(caminho)
    return [p.text for p in doc.paragraphs if p.text.strip()]


def ler_imagem(caminho):
    import pytesseract
    from PIL import Image

    pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

    img = Image.open(caminho)
    texto = pytesseract.image_to_string(img, lang="por")

    return texto.splitlines()


# ================================================
# GERAÇÃO DE SKU_MASTER COM IA
# ================================================

def gerar_sku_master_lote(descricoes):
    lista = "\n".join([f"{i + 1}. {d}" for i, d in enumerate(descricoes)])

    prompt = f"""Você é um especialista em padronização de produtos hospitalares e farmacêuticos.

Para cada descrição abaixo, gere um SKU_MASTER padronizado seguindo estas regras:
- Remova marca, fabricante, lote, validade, embalagem secundária e detalhes desnecessários
- Mantenha: princípio ativo + concentração/volume + forma farmacêutica quando relevante
- Para correlatos/materiais: mantenha nome + especificação técnica essencial
- Para fios cirúrgicos: mantenha tipo + calibre + comprimento + tipo de agulha
- Use maiúsculas, sem acentos
- Seja conciso mas específico o suficiente para diferenciar produtos similares

Retorne APENAS um JSON válido no formato:
{{"1": "SKU_MASTER_1", "2": "SKU_MASTER_2", ...}}

Descrições:
{lista}"""

    payload = json.dumps({
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 2000,
        "messages": [{"role": "user", "content": prompt}]
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload,
        headers={
            "content-type": "application/json",
            "anthropic-version": "2023-06-01"
        }
    )

    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read())

    texto = data["content"][0]["text"].strip()
    texto = re.sub(r"```json|```", "", texto).strip()

    resultado = json.loads(texto)

    return {descricoes[int(k) - 1]: v for k, v in resultado.items()}


def gerar_skus_em_lotes(descricoes, tamanho_lote=30):
    mapa = {}
    descricoes_unicas = list(set(descricoes))

    for i in range(0, len(descricoes_unicas), tamanho_lote):
        lote = descricoes_unicas[i:i + tamanho_lote]

        try:
            resultado = gerar_sku_master_lote(lote)
            mapa.update(resultado)
        except Exception:
            for d in lote:
                mapa[d] = d

    return mapa


# ================================================
# DETECTA COLUNAS FLEXÍVEL
# ================================================

SINONIMOS_COLUNAS = {
    "sku_master": [
        "SKU_MASTER",
        "SKU MASTER",
        "PRODUTO PADRAO",
        "PRODUTO_PADRAO",
        "PRODUTO PADRÃO",
        "DESCRICAO PADRONIZADA",
        "DESCRIÇÃO PADRONIZADA",
        "NOME FANTASIA"
    ],
    "descricao": [
        "DESCRIÇÃO DO PRODUTO",
        "DESCRICAO DO PRODUTO",
        "DESCRICAO",
        "DESCRIÇÃO",
        "PRODUTO",
        "ITEM",
        "NOME"
    ],
    "codigo": [
        "CÓDIGO PRODUTO",
        "CODIGO PRODUTO",
        "COD. PRODUTO",
        "CODIGO",
        "CÓDIGO",
        "COD"
    ],
    "preco": [
        "VALOR UNITÁRIO",
        "VALOR UNITARIO",
        "PRECO",
        "PREÇO",
        "VALOR",
        "UNITARIO",
        "VL_UNIT",
        "PRICE"
    ],
    "marca": [
        "MARCA",
        "MARCA/FABRICANTE",
        "FABRICANTE",
        "LABORATORIO",
        "LABORATÓRIO"
    ],
    "categoria": [
        "CATEGORIA",
        "TIPO",
        "GRUPO"
    ],
    "fornecedor": [
        "FORNECEDOR",
        "RAZÃO SOCIAL DO FORNECEDOR",
        "RAZAO SOCIAL DO FORNECEDOR",
        "EMPRESA"
    ],
    "tipo_fornecedor": [
        "FABRICANTE/DISTRIBUIDOR",
        "TIPO FORNECEDOR",
        "TIPO_FORNECEDOR"
    ],
    "unidade": [
        "UNIDADE DE COMPRA",
        "UNIDADE",
        "UN",
        "UNIT"
    ],
}


def detectar_coluna(cabecalhos, chave):
    sinonimos = SINONIMOS_COLUNAS.get(chave, [])

    for cab in cabecalhos:
        cab_norm = str(cab).strip().upper()

        for s in sinonimos:
            if s in cab_norm or cab_norm in s:
                return cab

    return None


# ================================================
# PARSER EXCEL/CSV
# ================================================

def limpar_preco(preco_raw):
    if preco_raw is None:
        return 0.0

    texto = str(preco_raw).strip()
    texto = texto.replace("R$", "").replace(" ", "")

    if "," in texto and "." in texto:
        texto = texto.replace(".", "").replace(",", ".")
    else:
        texto = texto.replace(",", ".")

    try:
        return float(texto)
    except Exception:
        return 0.0


def extrair_itens_estruturado(registros):
    if not registros:
        return []

    cabecalhos = list(registros[0].keys())

    col_sku = detectar_coluna(cabecalhos, "sku_master")
    col_descricao = detectar_coluna(cabecalhos, "descricao")
    col_codigo = detectar_coluna(cabecalhos, "codigo")
    col_preco = detectar_coluna(cabecalhos, "preco")
    col_marca = detectar_coluna(cabecalhos, "marca")
    col_categoria = detectar_coluna(cabecalhos, "categoria")
    col_fornecedor = detectar_coluna(cabecalhos, "fornecedor")
    col_tipo = detectar_coluna(cabecalhos, "tipo_fornecedor")
    col_unidade = detectar_coluna(cabecalhos, "unidade")

    itens = []

    for row in registros:
        sku_existente = str(row.get(col_sku, "") or "").strip().upper()
        descricao_orig = str(row.get(col_descricao, "") or "").strip().upper()

        nome_produto = sku_existente if sku_existente else descricao_orig

        if not nome_produto:
            continue

        preco = limpar_preco(row.get(col_preco, None))

        if preco <= 0:
            continue

        itens.append({
            "nome_produto": nome_produto,
            "descricao_orig": descricao_orig or nome_produto,
            "sku_existente": sku_existente,
            "codigo": str(row.get(col_codigo, "") or "").strip(),
            "marca": str(row.get(col_marca, "") or "").strip().upper(),
            "categoria": str(row.get(col_categoria, "") or "").strip().upper(),
            "preco": preco,
            "fornecedor_nome": str(row.get(col_fornecedor, "") or "").strip().upper(),
            "tipo_fornecedor": str(row.get(col_tipo, "") or "").strip().upper(),
            "unidade": str(row.get(col_unidade, "") or "").strip().upper(),
        })

    return itens


# ================================================
# PARSER TEXTO/PDF
# ================================================

def extrair_itens_texto(linhas, nome_fornecedor, tipo_fornecedor):
    itens = []

    padrao = re.compile(
        r"""^\s*(?P<codigo>[\d.,]+)?\s+(?P<descricao>[A-Z][A-Z0-9 \-\.,/()%°#]+?)\s+
        (?:ENV|UN|UNI|CX|FR|PC|KIT|AMP|BIS|SC|RL|MT|KG|GR|ML|L|TB|BX|AP|EV|CP|FA)?\s*
        (?P<preco>\d{1,6}[.,]\d{2})\s*""",
        re.VERBOSE | re.IGNORECASE
    )

    marca = nome_fornecedor.upper() if tipo_fornecedor.upper() == "FABRICANTE" else ""

    for linha in linhas:
        linha = str(linha).strip().upper()

        if not linha:
            continue

        m = padrao.match(linha)

        if m:
            descricao = m.group("descricao").strip().upper()

            if len(descricao) < 4:
                continue

            preco = limpar_preco(m.group("preco"))

            if preco <= 0:
                continue

            itens.append({
                "nome_produto": descricao,
                "descricao_orig": descricao,
                "sku_existente": "",
                "codigo": (m.group("codigo") or "").strip(),
                "marca": marca,
                "categoria": "",
                "preco": preco,
                "fornecedor_nome": nome_fornecedor.upper(),
                "tipo_fornecedor": tipo_fornecedor.upper(),
                "unidade": "",
            })

    return itens


# ================================================
# GARANTE FORNECEDOR NO BANCO
# ================================================

def garantir_fornecedor(cursor, nome, tipo):
    nome = str(nome or "").strip().upper()

    if not nome:
        nome = "FORNECEDOR NAO IDENTIFICADO"

    tipo = str(tipo or "Distribuidor").strip()

    cursor.execute("SELECT id FROM fornecedores WHERE UPPER(nome) = ?", (nome,))
    row = cursor.fetchone()

    if row:
        return row["id"]

    cursor.execute("""
        INSERT INTO fornecedores (nome, tipo, contato, email, telefone, ativo)
        VALUES (?, ?, '', '', '', 1)
    """, (nome, tipo))

    return cursor.lastrowid


# ================================================
# GARANTE PRODUTO NO SKU MASTER
# ================================================

def garantir_produto(cursor, sku_master, categoria, fabricante):
    sku_master = str(sku_master or "").strip().upper()
    categoria = str(categoria or "").strip().upper()
    fabricante = str(fabricante or "").strip().upper()

    if not sku_master:
        return None

    cursor.execute("SELECT id FROM produtos WHERE UPPER(produto_padrao) = ?", (sku_master,))
    row = cursor.fetchone()

    if row:
        produto_id = row["id"]

        cursor.execute("""
            UPDATE produtos
            SET fabricante = COALESCE(NULLIF(?, ''), fabricante),
                categoria = COALESCE(NULLIF(?, ''), categoria),
                ativo = 1
            WHERE id = ?
        """, (fabricante, categoria, produto_id))

        return produto_id

    cursor.execute("""
        INSERT INTO produtos (sku, produto_padrao, fabricante, categoria, ativo)
        VALUES ('', ?, ?, ?, 1)
    """, (sku_master, fabricante, categoria))

    produto_id = cursor.lastrowid

    cursor.execute("""
        INSERT INTO equivalencias (produto_id, descricao_equivalente)
        VALUES (?, ?)
    """, (produto_id, sku_master))

    return produto_id


# ================================================
# IMPORTAÇÃO PRINCIPAL
# ================================================

def importar_arquivo_fornecedor(caminho, fornecedor_id, nome_fornecedor, tipo_fornecedor):
    caminho = Path(caminho)
    ext = caminho.suffix.lower()
    data_hoje = datetime.now().strftime("%Y-%m-%d")

    if ext in [".xlsx", ".xls"]:
        registros = ler_excel(caminho)
        itens = extrair_itens_estruturado(registros)

    elif ext == ".csv":
        registros = ler_csv(caminho)
        itens = extrair_itens_estruturado(registros)

    elif ext == ".pdf":
        itens = extrair_itens_texto(
            ler_pdf(caminho),
            nome_fornecedor,
            tipo_fornecedor
        )

    elif ext == ".txt":
        itens = extrair_itens_texto(
            ler_txt(caminho),
            nome_fornecedor,
            tipo_fornecedor
        )

    elif ext == ".docx":
        itens = extrair_itens_texto(
            ler_docx(caminho),
            nome_fornecedor,
            tipo_fornecedor
        )

    elif ext in [".jpg", ".jpeg", ".png"]:
        itens = extrair_itens_texto(
            ler_imagem(caminho),
            nome_fornecedor,
            tipo_fornecedor
        )

    else:
        raise Exception(f"Formato não suportado: {ext}")

    if not itens:
        raise Exception("Nenhum item encontrado no arquivo.")

    descricoes_sem_sku = [
        item["descricao_orig"]
        for item in itens
        if not item["sku_existente"]
    ]

    mapa_sku = {}

    if descricoes_sem_sku:
        mapa_sku = gerar_skus_em_lotes(descricoes_sem_sku)

    conn = conectar()
    cursor = conn.cursor()

    importados = 0

    for item in itens:
        if item["sku_existente"]:
            sku_master = item["sku_existente"]
        else:
            sku_master = mapa_sku.get(item["descricao_orig"], item["descricao_orig"])

        if item["fornecedor_nome"] and item["fornecedor_nome"] != nome_fornecedor.upper():
            fid = garantir_fornecedor(
                cursor,
                item["fornecedor_nome"],
                item["tipo_fornecedor"] or tipo_fornecedor
            )
        else:
            fid = fornecedor_id

        marca = item["marca"]

        if not marca and item["tipo_fornecedor"] == "FABRICANTE":
            marca = item["fornecedor_nome"] or nome_fornecedor.upper()

        produto_id = garantir_produto(
            cursor,
            sku_master,
            item["categoria"],
            marca
        )

        if not produto_id:
            continue

        cursor.execute("""
            SELECT id FROM equivalencias
            WHERE produto_id = ?
            AND UPPER(descricao_equivalente) = ?
        """, (produto_id, item["descricao_orig"]))

        if not cursor.fetchone():
            cursor.execute("""
                INSERT INTO equivalencias (produto_id, descricao_equivalente)
                VALUES (?, ?)
            """, (produto_id, item["descricao_orig"]))

        conn.commit()

        registrar_preco_fornecedor(
            fornecedor_id=fid,
            produto_id=produto_id,
            descricao_original=item["descricao_orig"],
            codigo_fornecedor=item["codigo"],
            marca=marca,
            preco=item["preco"],
            data_importacao=data_hoje,
            arquivo_origem=caminho.name,
            origem_importacao="IMPORTADOR_UNIVERSAL"
        )

        importados += 1

    cursor.execute("""
        INSERT INTO cotacoes (
            fornecedor_id,
            data_importacao,
            arquivo_origem,
            total_itens
        )
        VALUES (?, ?, ?, ?)
    """, (
        fornecedor_id,
        data_hoje,
        caminho.name,
        importados
    ))

    conn.commit()
    conn.close()

    return importados