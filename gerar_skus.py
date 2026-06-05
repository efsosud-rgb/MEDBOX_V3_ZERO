"""
gerar_skus.py — MedBox V3
Importa todos os arquivos de base para o banco.
Parser dedicado para cada fornecedor, baseado na estrutura real dos arquivos.
"""

import re
import unicodedata
import sqlite3
from pathlib import Path
from datetime import datetime

# ============================================================
# CAMINHOS
# ============================================================

XLSX    = Path("uploads/SKU_MASTER_2_0.xlsx")
DOCX    = Path("uploads/RELATORIO_PRODUTO.docx")
XML     = Path("uploads/33260617771867000143550010001064711000118964-NFe.xml")

DB_PATH = Path("banco/medbox_v3.db")

# ============================================================
# UTILITÁRIOS
# ============================================================

def normalizar(texto):
    if not texto:
        return ""
    texto = str(texto).upper().strip()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = re.sub(r"\s+", " ", texto)
    return texto.strip()


def converter_float(valor):
    if valor is None:
        return 0.0
    texto = str(valor).strip().replace("R$", "").replace("$", "").replace(" ", "")
    if "," in texto and "." in texto:
        texto = texto.replace(".", "").replace(",", ".")
    else:
        texto = texto.replace(",", ".")
    try:
        f = float(texto)
        return f if f > 0 else 0.0
    except Exception:
        return 0.0


def converter_data(data):
    if not data:
        return datetime.now().strftime("%Y-%m-%d")
    texto = str(data).strip()
    formatos = ["%Y-%m-%d", "%d/%m/%Y", "%d/%m/%Y %H:%M:%S",
                "%Y-%m-%d %H:%M:%S", "%d-%m-%Y"]
    for fmt in formatos:
        try:
            return datetime.strptime(texto[:19], fmt).strftime("%Y-%m-%d")
        except Exception:
            pass
    try:
        return datetime.fromisoformat(texto[:19]).strftime("%Y-%m-%d")
    except Exception:
        return datetime.now().strftime("%Y-%m-%d")


def extrair_unidades_embalagem(texto_emb):
    """
    Extrai número de unidades de texto como:
    'Caixa com 2000 unidades' → 2000
    'Cartucho com 100 und' → 100
    '20 cartuchos com 100 unidades' → 2000 (20 * 100)
    """
    if not texto_emb:
        return 1
    texto = str(texto_emb).lower()
    # Padrão: N cartuchos/pacotes com M unidades
    m = re.search(r'(\d+)\s+(?:cartuchos?|pacotes?|caixas?)\s+com\s+(\d+)', texto)
    if m:
        return int(m.group(1)) * int(m.group(2))
    # Padrão: com N unidades
    m = re.search(r'com\s+(\d[\d\.]*)\s+unidades?', texto)
    if m:
        return int(m.group(1).replace(".", ""))
    # Padrão: N unidades
    m = re.search(r'(\d[\d\.]*)\s+unidades?', texto)
    if m:
        return int(m.group(1).replace(".", ""))
    return 1


def limpar_nome_produto(descricao, fabricante=""):
    """
    Remove sufixos de embalagem, fabricante e códigos do nome do produto.
    Ex: 'AGULHA DESC EST 25 X 0,70 MM DESCARPACK CX100CT' → 'AGULHA 25X0,70MM'
    """
    if not descricao:
        return ""
    desc = descricao.upper()

    # Remove nome do fabricante no final
    if fabricante:
        fab = fabricante.upper()
        desc = re.sub(r'\s+' + re.escape(fab) + r'(\s+.*)?$', '', desc).strip()

    # Remove sufixos de embalagem
    desc = re.sub(r'\s+(CX|PT|FD|DP|RL)\s*\d+\s*(UN|CT|PR|RLS?|PCT|UNID|UNIDADES?).*$', '', desc)
    desc = re.sub(r'\s+CX\d+.*$', '', desc)
    desc = re.sub(r'\s+\d+\s*(CARTUCHOS?|PACOTES?|CAIXAS?|UNIDADES?).*$', '', desc)

    # Remove palavras genéricas de fabricante no final
    for palavra in ['DESCARPACK', 'MEDIX', 'HALEXISTAR', 'BIOLINE',
                    'VITALGOLD', 'ADVANTIVE', 'VITAL', 'BIOSANI']:
        desc = re.sub(r'\s+' + palavra + r'(\s.*)?$', '', desc).strip()

    # Remove (MATRIZ GO) e similares
    desc = re.sub(r'\s*\(MATRIZ\s+\w+\)', '', desc).strip()
    desc = re.sub(r'\s*-\s*MATRIZ\s+\w+', '', desc).strip()

    return desc.strip()


# ============================================================
# BANCO
# ============================================================

def conectar():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def criar_banco():
    conn = conectar()
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS produtos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sku TEXT, produto_padrao TEXT, fabricante TEXT,
        categoria TEXT, ativo INTEGER DEFAULT 1)""")
    c.execute("""CREATE TABLE IF NOT EXISTS fornecedores (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT, tipo TEXT, contato TEXT,
        email TEXT, telefone TEXT, ativo INTEGER DEFAULT 1)""")
    c.execute("""CREATE TABLE IF NOT EXISTS precos_fornecedores (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fornecedor_id INTEGER, produto_id INTEGER,
        descricao_original TEXT, codigo_fornecedor TEXT,
        marca TEXT, preco REAL, data_importacao TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS precos_fornecedores_historico (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fornecedor_id INTEGER, produto_id INTEGER,
        descricao_original TEXT, codigo_fornecedor TEXT,
        marca TEXT, preco REAL, data_importacao TEXT,
        arquivo_origem TEXT, origem_importacao TEXT, data_registro TEXT)""")
    c.execute("""CREATE INDEX IF NOT EXISTS idx_precos_hist_produto_fornecedor
        ON precos_fornecedores_historico (produto_id, fornecedor_id, data_importacao)""")
    c.execute("""CREATE TABLE IF NOT EXISTS equivalencias (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        produto_id INTEGER, descricao_equivalente TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS cotacoes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fornecedor_id INTEGER, data_importacao TEXT,
        arquivo_origem TEXT, total_itens INTEGER DEFAULT 0)""")
    c.execute("""CREATE TABLE IF NOT EXISTS sinonimos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        termo TEXT, significado TEXT)""")
    conn.commit()
    conn.close()


def obter_ou_criar_fornecedor(conn, nome, tipo="Distribuidor"):
    nome_norm = normalizar(nome)
    c = conn.cursor()
    c.execute("SELECT id FROM fornecedores WHERE UPPER(nome) = ?", (nome_norm,))
    row = c.fetchone()
    if row:
        return row["id"]
    c.execute("INSERT INTO fornecedores (nome, tipo, contato, email, telefone, ativo) VALUES (?,?,?,?,?,1)",
              (nome_norm, tipo, "", "", ""))
    conn.commit()
    return c.lastrowid


def obter_ou_criar_produto(conn, produto_padrao, fabricante="", categoria=""):
    produto_padrao = normalizar(produto_padrao)
    if not produto_padrao:
        return None
    c = conn.cursor()
    c.execute("SELECT id FROM produtos WHERE UPPER(produto_padrao) = ? AND ativo = 1", (produto_padrao,))
    row = c.fetchone()
    if row:
        return row["id"]
    c.execute("INSERT INTO produtos (sku, produto_padrao, fabricante, categoria, ativo) VALUES (?,?,?,?,1)",
              ("", produto_padrao, normalizar(fabricante), normalizar(categoria)))
    conn.commit()
    return c.lastrowid


def adicionar_equivalencia(conn, produto_id, descricao):
    descricao = normalizar(descricao)
    if not descricao:
        return
    c = conn.cursor()
    c.execute("SELECT id FROM equivalencias WHERE produto_id = ? AND UPPER(descricao_equivalente) = ?",
              (produto_id, descricao))
    if not c.fetchone():
        c.execute("INSERT INTO equivalencias (produto_id, descricao_equivalente) VALUES (?,?)",
                  (produto_id, descricao))
        conn.commit()


def registrar_preco(conn, fornecedor_id, produto_id, descricao_original,
                    codigo_fornecedor, marca, preco, data_importacao,
                    arquivo_origem, origem_importacao):
    preco = converter_float(preco)
    if preco <= 0:
        return
    data_importacao    = converter_data(data_importacao)
    descricao_original = normalizar(descricao_original)
    codigo_fornecedor  = str(codigo_fornecedor or "").strip()
    marca              = normalizar(marca)
    c = conn.cursor()
    try:
        c.execute("""INSERT INTO precos_fornecedores_historico
            (fornecedor_id, produto_id, descricao_original, codigo_fornecedor,
             marca, preco, data_importacao, arquivo_origem, origem_importacao, data_registro)
            VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (fornecedor_id, produto_id, descricao_original, codigo_fornecedor,
             marca, preco, data_importacao, arquivo_origem, normalizar(origem_importacao),
             datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    except Exception:
        pass
    c.execute("""SELECT id, data_importacao FROM precos_fornecedores
        WHERE fornecedor_id = ? AND produto_id = ? AND UPPER(descricao_original) = ?""",
        (fornecedor_id, produto_id, descricao_original))
    existente = c.fetchone()
    if existente:
        if data_importacao >= existente["data_importacao"]:
            c.execute("""UPDATE precos_fornecedores
                SET preco=?, data_importacao=?, marca=?, codigo_fornecedor=? WHERE id=?""",
                (preco, data_importacao, marca, codigo_fornecedor, existente["id"]))
    else:
        c.execute("""INSERT INTO precos_fornecedores
            (fornecedor_id, produto_id, descricao_original, codigo_fornecedor, marca, preco, data_importacao)
            VALUES (?,?,?,?,?,?,?)""",
            (fornecedor_id, produto_id, descricao_original, codigo_fornecedor, marca, preco, data_importacao))
    conn.commit()


def registrar_cotacao(conn, fornecedor_id, arquivo_origem, total_itens, data=None):
    data = converter_data(data or datetime.now().strftime("%Y-%m-%d"))
    c = conn.cursor()
    c.execute("INSERT INTO cotacoes (fornecedor_id, data_importacao, arquivo_origem, total_itens) VALUES (?,?,?,?)",
              (fornecedor_id, data, arquivo_origem, total_itens))
    conn.commit()


def ja_importado(conn, nome_arquivo):
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM cotacoes WHERE arquivo_origem = ?", (nome_arquivo,))
    return c.fetchone()[0] > 0


def salvar_itens(conn, itens, forn_id, arquivo_nome, origem_tag):
    """Salva lista de dicts {sku, descricao, codigo, marca, preco, categoria} no banco."""
    data_hoje = datetime.now().strftime("%Y-%m-%d")
    importados = 0
    ignorados  = 0
    for item in itens:
        sku      = normalizar(item.get("sku") or item.get("descricao") or "")
        descricao= str(item.get("descricao") or "").strip()
        codigo   = str(item.get("codigo") or "").strip()
        marca    = str(item.get("marca") or "").strip()
        preco    = converter_float(item.get("preco") or 0)
        categoria= str(item.get("categoria") or "Material Hospitalar").strip()

        if not sku or preco <= 0:
            ignorados += 1
            continue

        produto_id = obter_ou_criar_produto(conn, sku, marca, categoria)
        if not produto_id:
            ignorados += 1
            continue

        if descricao and normalizar(descricao) != normalizar(sku):
            adicionar_equivalencia(conn, produto_id, descricao)
        if codigo:
            adicionar_equivalencia(conn, produto_id, codigo)

        registrar_preco(conn, forn_id, produto_id, descricao or sku,
                        codigo, marca, preco, data_hoje, arquivo_nome, origem_tag)
        importados += 1

    registrar_cotacao(conn, forn_id, arquivo_nome, importados, data_hoje)
    print(f"  Importados: {importados} | Ignorados: {ignorados}")


# ============================================================
# IMPORTADOR 1 — SKU_MASTER_2_0.xlsx
# ============================================================

def extrair_sku_da_descricao(descricao):
    if not descricao:
        return ""
    palavras = descricao.split()
    for tamanho in range(2, len(palavras) // 2 + 1):
        prefixo = " ".join(palavras[:tamanho])
        resto   = " ".join(palavras[tamanho:])
        if resto.upper().startswith(prefixo.upper()):
            return prefixo
    return descricao


def importar_xlsx(conn):
    print("=== XLSX: SKU_MASTER_2_0 ===")
    if not XLSX.exists():
        print(f"  Não encontrado: {XLSX}"); return

    import openpyxl
    wb = openpyxl.load_workbook(str(XLSX), read_only=True, data_only=True)
    ws = wb.active
    importados = ignorados = 0

    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i == 0:
            continue
        fab_dist   = str(row[3] or "").strip().upper()
        fornecedor = str(row[4] or "").strip()
        descricao  = str(row[6] or "").strip()
        sku_master = str(row[7] or "").strip()
        marca      = str(row[8] or "").strip()
        categoria  = str(row[9] or "").strip()
        preco_raw  = row[12]
        data_raw   = row[1]
        nf         = str(row[0] or "").strip()

        if not descricao:
            ignorados += 1; continue

        produto_padrao = sku_master if sku_master else extrair_sku_da_descricao(descricao)
        if not produto_padrao:
            ignorados += 1; continue

        produto_id = obter_ou_criar_produto(conn, produto_padrao, marca, categoria)
        if not produto_id:
            ignorados += 1; continue

        if normalizar(descricao) != normalizar(produto_padrao):
            adicionar_equivalencia(conn, produto_id, descricao)

        if fornecedor and preco_raw:
            tipo_forn = "Fabricante" if fab_dist == "FABRICANTE" else "Distribuidor"
            forn_id   = obter_ou_criar_fornecedor(conn, fornecedor, tipo_forn)
            registrar_preco(conn, forn_id, produto_id, descricao, nf, marca,
                            preco_raw, data_raw, XLSX.name, "XLSX_SKU_MASTER")
        importados += 1

    wb.close()
    print(f"  Importados: {importados} | Ignorados: {ignorados}")


# ============================================================
# IMPORTADOR 2 — RELATORIO_PRODUTO.docx
# ============================================================

def importar_docx(conn):
    print("=== DOCX: Relatório de Produtos ===")
    if not DOCX.exists():
        print(f"  Não encontrado: {DOCX}"); return

    from docx import Document
    doc = Document(str(DOCX))
    importados = ignorados = 0

    for table in doc.tables:
        headers = []
        for i, row in enumerate(table.rows):
            cells = [normalizar(c.text) for c in row.cells]
            if i == 0:
                headers = cells; continue
            if len(cells) < 2:
                ignorados += 1; continue

            def get(nome):
                for j, h in enumerate(headers):
                    if nome in h and j < len(cells):
                        return cells[j]
                return ""

            produto = get("PRODUTO") or get("DESCRI") or (cells[0] if cells else "")
            produto = normalizar(produto)
            if not produto:
                ignorados += 1; continue

            produto_id = obter_ou_criar_produto(conn, produto, get("FABRICANTE") or get("MARCA"), get("CATEGORIA") or get("TIPO"))
            if produto_id:
                cod = get("CODIGO") or get("COD")
                if cod:
                    adicionar_equivalencia(conn, produto_id, cod)
                importados += 1
            else:
                ignorados += 1

    for para in doc.paragraphs:
        texto = normalizar(para.text)
        if len(texto) > 5 and not texto.startswith("#"):
            if obter_ou_criar_produto(conn, texto, "", "Material Hospitalar"):
                importados += 1

    print(f"  Produtos: {importados} | Ignorados: {ignorados}")


# ============================================================
# IMPORTADOR 3 — NFe XML
# ============================================================

def importar_xml(conn):
    print("=== XML NFe ===")
    if not XML.exists():
        print(f"  Não encontrado: {XML}"); return

    import xml.etree.ElementTree as ET
    root = ET.parse(str(XML)).getroot()
    ns   = {"nfe": "http://www.portalfiscal.inf.br/nfe"}

    emit     = root.find(".//nfe:emit", ns)
    xNome    = emit.find("nfe:xNome", ns) if emit is not None else None
    nome_emit= xNome.text if xNome is not None else "FORNECEDOR XML"
    forn_id  = obter_ou_criar_fornecedor(conn, nome_emit, "Distribuidor")

    ide   = root.find(".//nfe:ide", ns)
    dhEmi = ide.find("nfe:dhEmi", ns) if ide is not None else None
    data_emissao = dhEmi.text[:10] if dhEmi is not None else ""

    importados = 0
    for det in root.findall(".//nfe:det", ns):
        prod   = det.find("nfe:prod", ns)
        if prod is None: continue
        xProd  = prod.find("nfe:xProd", ns)
        cProd  = prod.find("nfe:cProd", ns)
        vUnCom = prod.find("nfe:vUnCom", ns)
        descricao = normalizar(xProd.text if xProd is not None else "")
        codigo    = cProd.text if cProd is not None else ""
        preco     = float(vUnCom.text) if vUnCom is not None else 0.0
        if not descricao: continue
        produto_id = obter_ou_criar_produto(conn, descricao, "", "Material Hospitalar")
        if produto_id:
            registrar_preco(conn, forn_id, produto_id, descricao, codigo, "",
                            preco, data_emissao, XML.name, "XML_NFE")
            importados += 1

    print(f"  Importados: {importados}")


# ============================================================
# IMPORTADOR 4 — ESPECIFARMA pdf (texto corrido)
# Formato: COD  DESCRICAO  UN  PRECO  SALDO
# ============================================================

def importar_especifarma(conn):
    arquivo = Path("uploads/TABELA DISTRIBUIDOR ESPECIFARMA.pdf")
    print(f"=== ESPECIFARMA ===")
    if not arquivo.exists():
        # Tenta nome alternativo
        arquivo = Path("uploads/TABELA DISTRIBUIDOR ESPECIFARMA (2).pdf")
        if not arquivo.exists():
            print("  Não encontrado"); return

    if ja_importado(conn, arquivo.name):
        print("  Já importada — pulando."); return

    import pdfplumber

    forn_id = obter_ou_criar_fornecedor(conn, "ESPECIFARMA", "Distribuidor")
    UNIDADES = r'(?:ENV|UN|CX|FR|RL|PT|KT|AMP|PC|DZ|MT|DP|BLS?)'
    padrao   = re.compile(
        r'^(\d[\d\.]*)\s+(.+?)\s+' + UNIDADES + r'\s+(\d+[,\.]\d+)',
        re.IGNORECASE
    )

    texto_total = ""
    with pdfplumber.open(str(arquivo)) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                texto_total += t + "\n"

    # Junta linhas quebradas
    linhas_raw = texto_total.split("\n")
    linhas = []
    buf = ""
    for linha in linhas_raw:
        linha = linha.strip()
        if not linha:
            if buf: linhas.append(buf); buf = ""
            continue
        if re.match(r'^\d[\d\.]*\s', linha):
            if buf: linhas.append(buf)
            buf = linha
        else:
            buf = (buf + " " + linha).strip() if buf else linha

    if buf: linhas.append(buf)

    itens = []
    for linha in linhas:
        m = padrao.match(linha.strip())
        if not m: continue
        cod      = m.group(1).strip()
        descricao= m.group(2).strip()
        preco    = converter_float(m.group(3))
        if preco <= 0: continue
        # Remove sufixo BIOLINE (MATRIZ GO)
        descricao_limpa = re.sub(r'\s+BIOLINE\s*(\(.*?\))?$', '', descricao, flags=re.IGNORECASE).strip()
        descricao_limpa = re.sub(r'\s*\(MATRIZ GO\)$', '', descricao_limpa, flags=re.IGNORECASE).strip()
        itens.append({"sku": descricao_limpa, "descricao": descricao, "codigo": cod,
                      "marca": "BIOLINE", "preco": preco, "categoria": "Sutura"})

    salvar_itens(conn, itens, forn_id, arquivo.name, "PDF_ESPECIFARMA")


# ============================================================
# IMPORTADOR 5 — JOAOMED pdf (tabela pdfplumber)
# Colunas: [0]=Cod [2]=Desc [3]=Marca [8]=INTEREST
# ============================================================

def importar_joaomed(conn):
    arquivo = Path("uploads/TABELA DISTRIBUIDOR JOAOMED.pdf")
    print("=== JOAOMED ===")
    if not arquivo.exists():
        print("  Não encontrado"); return
    if ja_importado(conn, arquivo.name):
        print("  Já importada — pulando."); return

    import pdfplumber
    forn_id = obter_ou_criar_fornecedor(conn, "JOAOMED", "Distribuidor")
    CABECALHO = {"COD", "CODIGO", "DESCRICAO", "MARCA", "UN", "ORIGEM",
                 "ICMS", "DISTRIB", "INTEREST", "NCM", "ANVISA"}
    itens = []

    with pdfplumber.open(str(arquivo)) as pdf:
        for page in pdf.pages:
            for table in (page.extract_tables() or []):
                for row in table:
                    if not row or len(row) < 9: continue
                    cod = str(row[0] or "").strip().upper()
                    if not cod or cod in CABECALHO: continue
                    if any(kw in cod for kw in ("CONDI","REGRA","LISTA","DESCONTO","PAGAMENTO","TABELA","ORIGEM")): continue
                    descricao = normalizar(row[2] if len(row) > 2 else "")
                    marca     = normalizar(row[3] if len(row) > 3 else "")
                    preco     = converter_float(row[8] if len(row) > 8 else "")
                    if not descricao or preco <= 0: continue
                    itens.append({"sku": descricao, "descricao": descricao,
                                  "codigo": str(row[0] or "").strip(),
                                  "marca": marca, "preco": preco,
                                  "categoria": "Material Hospitalar"})

    salvar_itens(conn, itens, forn_id, arquivo.name, "PDF_JOAOMED")


# ============================================================
# IMPORTADOR 6 — S3MED xlsx
# Colunas: [0]=EAN [1]=Produto [2]=Laboratorio [3]=Filial [4]=Pç Venda
# ============================================================

def importar_s3med(conn):
    arquivo = Path("uploads/TABELA DISTRIBUIDOR S3MED.xlsx")
    print("=== S3MED ===")
    if not arquivo.exists():
        print("  Não encontrado"); return
    if ja_importado(conn, arquivo.name):
        print("  Já importada — pulando."); return

    import openpyxl
    forn_id = obter_ou_criar_fornecedor(conn, "S3MED", "Distribuidor")
    wb = openpyxl.load_workbook(str(arquivo), read_only=True, data_only=True)
    ws = wb.active
    itens = []

    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i == 0: continue  # cabeçalho
        if not row[1]: continue
        descricao = str(row[1] or "").strip()
        marca     = str(row[2] or "").strip()
        preco     = converter_float(row[4])
        ean       = str(row[0] or "").strip()
        if not descricao or preco <= 0: continue
        itens.append({"sku": descricao, "descricao": descricao,
                      "codigo": ean, "marca": marca,
                      "preco": preco, "categoria": "Medicamento"})

    wb.close()
    salvar_itens(conn, itens, forn_id, arquivo.name, "XLSX_S3MED")


# ============================================================
# IMPORTADOR 7 — DESCARPACK pdf (tabela)
# Colunas: [0]=Cod [1]=Produto [2]=Unid_venda [3]=Embalagem [4]=Preço [5]=IPI
# Preço é por unidade individual
# ============================================================

def importar_descarpack(conn):
    arquivo = Path("uploads/TABELA FABRICANTE DESCARPACK.pdf")
    print("=== DESCARPACK ===")
    if not arquivo.exists():
        print("  Não encontrado"); return
    if ja_importado(conn, arquivo.name):
        print("  Já importada — pulando."); return

    import pdfplumber
    forn_id = obter_ou_criar_fornecedor(conn, "DESCARPACK", "Fabricante")
    itens   = []

    with pdfplumber.open(str(arquivo)) as pdf:
        for page in pdf.pages:
            for table in (page.extract_tables() or []):
                for row in table:
                    if not row or len(row) < 5: continue
                    cod      = str(row[0] or "").strip()
                    descricao= str(row[1] or "").strip()
                    preco_str= str(row[4] or "").strip()
                    if not cod or not descricao: continue
                    if not re.match(r'^\d', cod): continue  # pula cabeçalhos
                    preco = converter_float(preco_str)
                    if preco <= 0: continue
                    sku = limpar_nome_produto(descricao, "DESCARPACK")
                    if not sku: sku = descricao
                    itens.append({"sku": sku, "descricao": descricao,
                                  "codigo": cod, "marca": "DESCARPACK",
                                  "preco": preco, "categoria": "Material Hospitalar"})

    salvar_itens(conn, itens, forn_id, arquivo.name, "PDF_DESCARPACK")


# ============================================================
# IMPORTADOR 8 — FARMAVISION pdf (proposta com tabela)
# Colunas: [0]=Marca [1]=Descrição+Qtd [2]=Qtd [3]=Valor Unit [4]=Total
# ============================================================

def importar_farmavision(conn):
    arquivo = Path("uploads/TABELA FABRICANTE FARMAVISION.pdf")
    print("=== FARMAVISION ===")
    if not arquivo.exists():
        print("  Não encontrado"); return
    if ja_importado(conn, arquivo.name):
        print("  Já importada — pulando."); return

    import pdfplumber
    forn_id = obter_ou_criar_fornecedor(conn, "FARMAVISION", "Fabricante")
    itens   = []

    with pdfplumber.open(str(arquivo)) as pdf:
        texto = ""
        for page in pdf.pages:
            t = page.extract_text()
            if t: texto += t + "\n"

    # Procura linhas com padrão: FARMA VISION  PRODUTO  QTD  $PRECO  $TOTAL
    for linha in texto.split("\n"):
        linha = linha.strip()
        m = re.search(r'CLORETO\s+(\d+\s*ML)', linha, re.IGNORECASE)
        preco_m = re.search(r'\$\s*([\d,\.]+)', linha)
        if m and preco_m:
            vol     = m.group(1).strip()
            descricao = f"CLORETO DE SODIO 0,9% {vol}"
            preco   = converter_float(preco_m.group(1))
            if preco > 0:
                itens.append({"sku": descricao, "descricao": descricao,
                              "codigo": "", "marca": "FARMAVISION",
                              "preco": preco, "categoria": "Medicamento"})

    salvar_itens(conn, itens, forn_id, arquivo.name, "PDF_FARMAVISION")


# ============================================================
# IMPORTADOR 9 — JP FARMA pdf (pedido com tabela)
# Colunas: [Prod, Descrição, Qtd, Preço Unit, Preço Total]
# ============================================================

def importar_jpfarma(conn):
    arquivo = Path("uploads/TABELA FABRICANTE JP FARMA.pdf")
    print("=== JP FARMA ===")
    if not arquivo.exists():
        print("  Não encontrado"); return
    if ja_importado(conn, arquivo.name):
        print("  Já importada — pulando."); return

    import pdfplumber
    forn_id = obter_ou_criar_fornecedor(conn, "JP FARMA", "Fabricante")
    itens   = []

    with pdfplumber.open(str(arquivo)) as pdf:
        texto = ""
        for page in pdf.pages:
            t = page.extract_text()
            if t: texto += t + "\n"

    # Padrão: CODIGO  DESCRICAO  QUANTIDADE  R$ PRECO  R$ TOTAL
    padrao = re.compile(
        r'(\d{4,})\s+'                    # código
        r'([A-Z][A-Z0-9\s\%\./,]+?)\s+'  # descrição
        r'[\d\.,]+\s+'                    # quantidade
        r'R\$\s*([\d,\.]+)'              # preço unitário
    )
    for linha in texto.split("\n"):
        m = padrao.search(linha)
        if m:
            cod      = m.group(1).strip()
            descricao= m.group(2).strip()
            preco    = converter_float(m.group(3))
            if preco > 0:
                itens.append({"sku": descricao, "descricao": descricao,
                              "codigo": cod, "marca": "JP FARMA",
                              "preco": preco, "categoria": "Medicamento"})

    salvar_itens(conn, itens, forn_id, arquivo.name, "PDF_JPFARMA")


# ============================================================
# IMPORTADOR 10 — CIMED xlsx
# Colunas: [0]=BU [1]=UF [2]=EAN [3]=Cod [4]=Nome [5]=Status [6-8]=Qtds [9]=Vlr_P
# Usa Vlr_P (menor preço, col 9). Ignora status != ATIVO
# ============================================================

def importar_cimed(conn):
    arquivo = Path("uploads/TABELA FABRICANTE CIMED.xlsx")
    print("=== CIMED ===")
    if not arquivo.exists():
        print("  Não encontrado"); return
    if ja_importado(conn, arquivo.name):
        print("  Já importada — pulando."); return

    import openpyxl
    forn_id = obter_ou_criar_fornecedor(conn, "CIMED", "Fabricante")
    wb = openpyxl.load_workbook(str(arquivo), read_only=True, data_only=True)
    ws = wb.active
    itens = []

    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i == 0: continue
        nome   = str(row[4] or "").strip()
        status = str(row[5] or "").strip().upper()
        preco  = converter_float(row[9])
        ean    = str(row[2] or "").strip()
        cod    = str(row[3] or "").strip()
        if not nome or preco <= 0: continue
        if "INATIVO" in status or "DESCONT" in status: continue
        itens.append({"sku": nome, "descricao": nome,
                      "codigo": cod or ean, "marca": "CIMED",
                      "preco": preco, "categoria": "Medicamento"})

    wb.close()
    salvar_itens(conn, itens, forn_id, arquivo.name, "XLSX_CIMED")


# ============================================================
# IMPORTADOR 11 — HALEXISTAR xlsx
# Cabeçalho linha 4: [Grupo, CÓD, DESCRIÇÃO PRODUTO, PRINCIPIO ATIVO, ML, QTDE CX]
# Sem preço — importa apenas como catálogo de produtos
# ============================================================

def importar_halexistar(conn):
    arquivo = Path("uploads/TABELA FABRICANTE HALEXISTAR.xlsx")
    print("=== HALEXISTAR ===")
    if not arquivo.exists():
        print("  Não encontrado"); return
    if ja_importado(conn, arquivo.name):
        print("  Já importada — pulando."); return

    import openpyxl
    forn_id = obter_ou_criar_fornecedor(conn, "HALEXISTAR", "Fabricante")
    wb = openpyxl.load_workbook(str(arquivo), read_only=True, data_only=True)
    ws = wb.active
    importados = 0
    data_hoje  = datetime.now().strftime("%Y-%m-%d")

    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i < 5: continue  # pula até linha 6 (dados)
        # Linha de grupo: primeira célula é string tipo "Medicamento - PV"
        if isinstance(row[0], str) and "medicamento" in str(row[0]).lower():
            continue
        cod      = str(row[1] or "").strip() if len(row) > 1 else ""
        descricao= str(row[2] or "").strip() if len(row) > 2 else ""
        if not cod or not descricao or not re.match(r'^\d', str(cod)):
            continue
        produto_id = obter_ou_criar_produto(conn, descricao, "HALEXISTAR", "Medicamento")
        if produto_id:
            adicionar_equivalencia(conn, produto_id, cod)
            importados += 1

    registrar_cotacao(conn, forn_id, arquivo.name, importados, data_hoje)
    wb.close()
    print(f"  Catalogados: {importados} (sem preço)")


# ============================================================
# IMPORTADOR 12 — MEDIX xlsx
# Linha 5: cabeçalho [Cod, Nome, Marca, Tipo_emb, Embalagem, Preco1, Preco2, Preco3]
# Preço col 5 (menor). Embalagem = cartucho com 100 und → preço já é por unidade
# ============================================================

def importar_medix(conn):
    arquivo = Path("uploads/TABELA FABRICANTE MEDIX.xlsx")
    print("=== MEDIX ===")
    if not arquivo.exists():
        print("  Não encontrado"); return
    if ja_importado(conn, arquivo.name):
        print("  Já importada — pulando."); return

    import openpyxl
    forn_id = obter_ou_criar_fornecedor(conn, "MEDIX", "Fabricante")
    wb = openpyxl.load_workbook(str(arquivo), read_only=True, data_only=True)
    ws = wb.active
    itens = []

    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i < 6: continue  # dados a partir linha 7
        cod      = str(row[0] or "").strip()
        descricao= str(row[1] or "").strip()
        marca    = str(row[2] or "MEDIX").strip()
        preco    = converter_float(row[5])
        if not descricao or preco <= 0: continue
        if not re.match(r'^\d', cod): continue
        # Preço é por cartucho com 100 un → divide por 100
        preco_unit = round(preco / 100, 4)
        sku = limpar_nome_produto(descricao, "MEDIX")
        if not sku: sku = descricao
        itens.append({"sku": sku, "descricao": descricao,
                      "codigo": cod, "marca": marca,
                      "preco": preco_unit, "categoria": "Material Hospitalar"})

    wb.close()
    salvar_itens(conn, itens, forn_id, arquivo.name, "XLSX_MEDIX")


# ============================================================
# IMPORTADOR 13 — UNIÃO QUÍMICA xlsx
# Colunas: [0]=Produto [1]=Quant [2]=UND [3]=Pr Compra
# ============================================================

def importar_uniao_quimica(conn):
    arquivo = Path("uploads/TABELA FABRICANTE UNIÃO QUÍMICA.xlsx")
    print("=== UNIAO QUIMICA ===")
    if not arquivo.exists():
        print("  Não encontrado"); return
    if ja_importado(conn, arquivo.name):
        print("  Já importada — pulando."); return

    import openpyxl
    forn_id = obter_ou_criar_fornecedor(conn, "UNIAO QUIMICA", "Fabricante")
    wb = openpyxl.load_workbook(str(arquivo), read_only=True, data_only=True)
    ws = wb.active
    itens = []

    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i == 0: continue
        descricao = str(row[0] or "").strip()
        preco     = converter_float(row[3])
        if not descricao or preco <= 0: continue
        if descricao.upper() in ("PRODUTOS", "PRODUTO"): continue
        itens.append({"sku": descricao, "descricao": descricao,
                      "codigo": "", "marca": "UNIAO QUIMICA",
                      "preco": preco, "categoria": "Medicamento"})

    wb.close()
    salvar_itens(conn, itens, forn_id, arquivo.name, "XLSX_UNIAO_QUIMICA")


# ============================================================
# RESUMO
# ============================================================

def resumo(conn):
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM produtos WHERE ativo = 1")
    produtos = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM fornecedores WHERE ativo = 1")
    fornecedores = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM precos_fornecedores")
    precos = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM precos_fornecedores_historico")
    historico = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM equivalencias")
    equiv = c.fetchone()[0]
    print("\n=== BANCO FINAL ===")
    print(f"  Produtos (SKU Masters): {produtos}")
    print(f"  Fornecedores          : {fornecedores}")
    print(f"  Preços atuais         : {precos}")
    print(f"  Histórico de preços   : {historico}")
    print(f"  Equivalências         : {equiv}")
    print("✅ Concluído!")


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    criar_banco()
    conn = conectar()

    importar_xlsx(conn)
    importar_docx(conn)
    importar_xml(conn)
    importar_especifarma(conn)
    importar_joaomed(conn)
    importar_s3med(conn)
    importar_descarpack(conn)
    importar_farmavision(conn)
    importar_jpfarma(conn)
    importar_cimed(conn)
    importar_halexistar(conn)
    importar_medix(conn)
    importar_uniao_quimica(conn)

    resumo(conn)
    conn.close()