import re
import json
import csv
import zipfile
import urllib.request
import unicodedata
from pathlib import Path
from datetime import datetime

<<<<<<< HEAD
from rapidfuzz import fuzz

=======
>>>>>>> origin/main
from core.banco import conectar, registrar_preco_fornecedor
from core.formatadores import moeda_br


TESSERACT_PADRAO = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
MENSAGEM_OCR_INDISPONIVEL = (
    "OCR indispon\u00edvel. Instale o idioma portugu\u00eas do Tesseract "
    "ou envie XLSX/CSV/PDF com texto."
)


def normalizar_cabecalho(texto):
    texto = str(texto or "").upper().strip()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = re.sub(r"[^A-Z0-9]+", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()


def detectar_excel_binario(caminho):
    caminho = Path(caminho)

    if caminho.suffix.lower() == ".xlsb":
        return True

    try:
        with zipfile.ZipFile(caminho) as pacote:
            nomes = {nome.lower() for nome in pacote.namelist()}
    except (OSError, zipfile.BadZipFile):
        return False

    if "xl/workbook.bin" in nomes or "xl/vbaproject.bin" in nomes:
        return True

    return any(
        nome.startswith("xl/worksheets/") and nome.endswith(".bin")
        for nome in nomes
    )


# ================================================
# LEITORES POR FORMATO
# ================================================

def ler_pdf(caminho):
    return ler_pdf_detalhado(caminho)["linhas"]


def ler_pdf_detalhado(caminho, tentar_ocr=True):
    import pdfplumber

    linhas = []
    linhas_ocr = []
    mensagens = []
    total_paginas = 0

    with pdfplumber.open(caminho) as pdf:
        total_paginas = len(pdf.pages)

        for pagina in pdf.pages:
            texto = pagina.extract_text()
            if texto:
                linhas += texto.splitlines()

        pdf_tem_texto = bool(linhas)

        if not pdf_tem_texto and tentar_ocr:
            try:
                for pagina in pdf.pages:
                    imagem = pagina.to_image(resolution=200).original
                    texto_ocr = executar_ocr_imagem(imagem)
                    if texto_ocr:
                        linhas_ocr += texto_ocr.splitlines()
            except Exception as erro:
                mensagens.append(str(erro) or MENSAGEM_OCR_INDISPONIVEL)

    if linhas_ocr:
        linhas = linhas_ocr

    return {
        "linhas": linhas,
        "pdf_tem_texto": bool(linhas) and not bool(linhas_ocr),
        "usou_ocr": bool(linhas_ocr),
        "total_paginas": total_paginas,
        "mensagens": mensagens,
    }


def ler_excel(caminho):
    if detectar_excel_binario(caminho):
        return ler_xlsb(caminho)

    from openpyxl import load_workbook

    wb = load_workbook(caminho, data_only=True, read_only=True)
    resultados = []

    for ws in wb.worksheets:
        linhas = list(ws.iter_rows(values_only=True))
        info = detectar_cabecalho_em_linhas(linhas)
        cabecalhos = info["cabecalhos"]

        if info["linha_cabecalho"] is None:
            continue

        for row in linhas[info["linha_cabecalho"] + 1:]:
            if all(c is None for c in row):
                continue

            item = {}

            for j, val in enumerate(row):
                if j < len(cabecalhos):
                    item[cabecalhos[j]] = val

            resultados.append(item)

    wb.close()
    return resultados


def ler_xlsb(caminho):
    from pyxlsb import open_workbook

    resultados = []

    with open_workbook(str(caminho)) as wb:
        for nome_aba in wb.sheets:
            with wb.get_sheet(nome_aba) as ws:
                linhas = [
                    [cell.v for cell in row]
                    for row in ws.rows()
                ]

            info = detectar_cabecalho_em_linhas(linhas)

            if info["linha_cabecalho"] is None:
                continue

            cabecalhos = info["cabecalhos"]
            registros_aba = []

            for row in linhas[info["linha_cabecalho"] + 1:]:
                if all(c is None for c in row):
                    continue

                item = {}
                for j, val in enumerate(row):
                    if j < len(cabecalhos):
                        item[cabecalhos[j]] = val
                registros_aba.append(item)

            if extrair_itens_estruturado(registros_aba):
                resultados.extend(registros_aba)

    return resultados


def ler_csv(caminho):
    resultados = []
    texto = ler_texto_csv(caminho)
    dialect = detectar_dialeto_csv(texto)
    linhas = list(csv.reader(texto.splitlines(), dialect))
    info = detectar_cabecalho_em_linhas(linhas)

    if info["linha_cabecalho"] is None:
        return resultados

    cabecalhos = info["cabecalhos"]
    for row in linhas[info["linha_cabecalho"] + 1:]:
        if not row or all(c in (None, "") for c in row):
            continue
        item = {}
        for j, val in enumerate(row):
            if j < len(cabecalhos):
                item[cabecalhos[j]] = val
        resultados.append(item)

    return resultados


def ler_txt(caminho):
    with open(caminho, encoding="utf-8", errors="ignore") as f:
        return f.readlines()


def ler_docx(caminho):
    from docx import Document

    doc = Document(caminho)
    return [p.text for p in doc.paragraphs if p.text.strip()]


def ler_imagem(caminho):
    from PIL import Image

    img = Image.open(caminho)
    texto = executar_ocr_imagem(img)

    return texto.splitlines()


def executar_ocr_imagem(imagem):
    import pytesseract

    try:
        tesseract = validar_tesseract()
    except Exception:
        raise Exception(MENSAGEM_OCR_INDISPONIVEL)

    pytesseract.pytesseract.tesseract_cmd = str(tesseract)

    erros = []
    for idioma in ("por", "eng"):
        try:
            return pytesseract.image_to_string(imagem, lang=idioma)
        except Exception as erro:
            erros.append(str(erro))

    raise Exception(MENSAGEM_OCR_INDISPONIVEL)


def validar_tesseract(caminho=TESSERACT_PADRAO):
    caminho = Path(caminho)
    if not caminho.exists():
        raise Exception(f"Tesseract nao encontrado em: {caminho}")
    return caminho


def ler_texto_csv(caminho):
    caminho = Path(caminho)
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return caminho.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return caminho.read_text(encoding="utf-8", errors="ignore")


def detectar_dialeto_csv(texto):
    amostra = texto[:4096]
    try:
        return csv.Sniffer().sniff(amostra, delimiters=";,|\t,")
    except Exception:
        return csv.excel


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
                mapa[d] = None

    return mapa


def sku_gerado_valido(descricao, sku_master):
    descricao_norm = normalizar_cabecalho(descricao)
    sku_norm = normalizar_cabecalho(sku_master)

    if not sku_norm:
        return False

    if sku_norm == descricao_norm:
        return False

    return len(sku_norm.split()) <= 10


def montar_sku_provisorio(descricao):
    texto = str(descricao or "").strip().upper()
    texto = re.sub(r"\s+", " ", texto)
    return f"SKU PENDENTE - {texto[:90]}"


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


SINONIMOS_COLUNAS["sku_master"].extend([
    "PRODUTO PADRÃO",
    "DESCRIÇÃO PADRONIZADA",
])
SINONIMOS_COLUNAS["descricao"].extend([
    "DESCRIÇÃO DO PRODUTO",
    "DESCRIÇÃO PRODUTO",
    "DESCRICAO PRODUTO",
    "DESCR PRODUTO",
    "DESCRIÇÃO",
    "DESCR",
])
SINONIMOS_COLUNAS["codigo"].extend([
    "CÓDIGO PRODUTO",
    "COD PRODUTO",
    "CÓDIGO",
    "CÓD",
    "COD.",
])
SINONIMOS_COLUNAS["preco"].extend([
    "VALOR UNITÁRIO",
    "VALOR UNIT",
    "VLR UNITARIO",
    "VL UNITARIO",
    "VL UNIT",
    "PREÇO",
    "PRECO UNITARIO",
    "PREÇO UNITÁRIO",
    "PF 12%",
    "PF",
    "R$",
])
SINONIMOS_COLUNAS["marca"].append("LABORATÓRIO")
SINONIMOS_COLUNAS["categoria"].extend(["LINHA"])
SINONIMOS_COLUNAS["fornecedor"].append("RAZÃO SOCIAL DO FORNECEDOR")
SINONIMOS_COLUNAS["unidade"].extend(["QTDE CX", "QTD CX", "QTD", "QTDE", "ML"])


def detectar_coluna(cabecalhos, chave):
    sinonimos = SINONIMOS_COLUNAS.get(chave, [])

    if chave == "preco":
        for cab in cabecalhos:
            cab_norm = normalizar_cabecalho(cab)
            if not cab_norm:
                continue

            for s in sinonimos:
                s_norm = normalizar_cabecalho(s)
                if len(s_norm) < 2:
                    continue
                if cab_norm == s_norm:
                    return cab

    for cab in cabecalhos:
        cab_norm = normalizar_cabecalho(cab)
        if not cab_norm:
            continue

        for s in sinonimos:
            s_norm = normalizar_cabecalho(s)
            if len(s_norm) < 2:
                continue
            if s_norm in cab_norm or (len(cab_norm) >= 3 and cab_norm in s_norm):
                return cab

    return None


def colunas_detectadas(cabecalhos):
    return {
        chave: detectar_coluna(cabecalhos, chave)
        for chave in SINONIMOS_COLUNAS
    }


def pontuar_cabecalho(cabecalhos):
    detectadas = colunas_detectadas(cabecalhos)
    chaves_detectadas = [chave for chave, valor in detectadas.items() if valor]
    nao_vazios = sum(1 for cab in cabecalhos if normalizar_cabecalho(cab))

    score = len(chaves_detectadas) * 10 + min(nao_vazios, 10)
    if detectadas.get("descricao"):
        score += 20
    if detectadas.get("preco"):
        score += 20
    if detectadas.get("codigo"):
        score += 5

    return score, detectadas


def detectar_cabecalho_em_linhas(linhas, limite=15):
    melhor = {
        "linha_cabecalho": None,
        "cabecalhos": [],
        "colunas_detectadas": {},
        "score": 0,
    }

    for idx, row in enumerate(linhas[:limite]):
        cabecalhos = [str(c).strip().upper() if c is not None else "" for c in row]
        score, detectadas = pontuar_cabecalho(cabecalhos)
        if score > melhor["score"]:
            melhor = {
                "linha_cabecalho": idx,
                "cabecalhos": cabecalhos,
                "colunas_detectadas": detectadas,
                "score": score,
            }

    if not melhor["colunas_detectadas"].get("descricao") and not melhor["colunas_detectadas"].get("sku_master"):
        melhor["linha_cabecalho"] = None

    return melhor


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


def normalizar_descricao_catalogo(descricao):
    descricao = str(descricao or "").strip().upper()
    descricao = re.sub(r"\s+", " ", descricao)
    descricao = re.sub(r"(\d+(?:[.,]\d+)?MG)\s+(\d+(?:[.,]\d+)?ML)\b", r"\1/\2", descricao)
    return descricao


def extrair_itens_catalogo_estruturado(registros, nome_fornecedor="", tipo_fornecedor=""):
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

    if col_preco or (not col_descricao and not col_sku):
        return []

    itens = []
    fornecedor_padrao = str(nome_fornecedor or "").strip().upper()
    tipo_padrao = str(tipo_fornecedor or "").strip().upper()

    for row in registros:
        sku_existente = normalizar_descricao_catalogo(row.get(col_sku, ""))
        descricao_orig = normalizar_descricao_catalogo(row.get(col_descricao, ""))
        nome_produto = sku_existente if sku_existente else descricao_orig

        if not nome_produto:
            continue

        fornecedor_nome = str(row.get(col_fornecedor, "") or "").strip().upper()
        tipo_item = str(row.get(col_tipo, "") or "").strip().upper()
        marca = str(row.get(col_marca, "") or "").strip().upper()

        if not fornecedor_nome:
            fornecedor_nome = fornecedor_padrao

        if not tipo_item:
            tipo_item = tipo_padrao

        if not marca and tipo_item == "FABRICANTE":
            marca = fornecedor_nome or fornecedor_padrao

        itens.append({
            "nome_produto": nome_produto,
            "descricao_orig": descricao_orig or nome_produto,
            "sku_existente": sku_existente,
            "codigo": str(row.get(col_codigo, "") or "").strip(),
            "marca": marca,
            "categoria": str(row.get(col_categoria, "") or "").strip().upper(),
            "preco": None,
            "fornecedor_nome": fornecedor_nome,
            "tipo_fornecedor": tipo_item,
            "unidade": str(row.get(col_unidade, "") or "").strip().upper(),
        })

    return itens


def diagnosticar_registros_estruturados(registros, contexto=None):
    contexto = contexto or {}
    cabecalhos = list(registros[0].keys()) if registros else contexto.get("cabecalhos", [])
    detectadas = colunas_detectadas(cabecalhos)
    itens = extrair_itens_estruturado(registros)
    itens_catalogo = extrair_itens_catalogo_estruturado(
        registros,
        contexto.get("nome_fornecedor", ""),
        contexto.get("tipo_fornecedor", ""),
    )
    modo_importacao = "tabela_com_preco" if itens else None

    faltantes = []
    if not detectadas.get("descricao") and not detectadas.get("sku_master"):
        faltantes.append("descricao")
    if not detectadas.get("preco"):
        if itens_catalogo:
            modo_importacao = "catalogo_sem_preco"
        else:
            faltantes.append("preco")

    mensagens = []
    if contexto.get("linha_cabecalho") is None:
        mensagens.append("Cabeçalho não identificado.")
    elif contexto.get("linha_cabecalho", 0) > 0:
        mensagens.append(f"Cabeçalho detectado na linha {contexto['linha_cabecalho'] + 1}.")

    if faltantes:
        mensagens.append(f"Colunas obrigatórias ausentes: {', '.join(faltantes)}.")
    if modo_importacao == "catalogo_sem_preco":
        mensagens.append("Catalogo sem preco identificado.")
    elif not itens:
        mensagens.append("Nenhum item com descrição e preço válido foi extraído.")

    return {
        "ok": bool(itens or itens_catalogo) and not faltantes,
        "modo_importacao": modo_importacao,
        "mensagens": mensagens,
        "linha_cabecalho": (
            contexto["linha_cabecalho"] + 1
            if contexto.get("linha_cabecalho") is not None
            else None
        ),
        "aba": contexto.get("aba"),
        "delimiter": contexto.get("delimiter"),
        "cabecalhos": cabecalhos,
        "colunas_detectadas": detectadas,
        "colunas_obrigatorias_ausentes": faltantes,
        "total_registros_lidos": len(registros),
        "total_itens_extraidos": len(itens),
        "total_produtos_catalogo": len(itens_catalogo),
        "total_precos_importados": len(itens),
        "preview_itens": itens[:5],
        "preview_catalogo": itens_catalogo[:5],
    }


def diagnosticar_arquivo_fornecedor(caminho, nome_fornecedor="", tipo_fornecedor="Distribuidor"):
    caminho = Path(caminho)
    ext = caminho.suffix.lower()
    diagnostico = {
        "arquivo": caminho.name,
        "formato": ext.lstrip("."),
        "ok": False,
        "modo_importacao": None,
        "total_produtos_catalogo": 0,
        "total_precos_importados": 0,
        "mensagens": [],
        "detalhes": {},
    }

    try:
        if ext == ".xlsb" or detectar_excel_binario(caminho):
            registros = ler_xlsb(caminho)
            detalhe = diagnosticar_registros_estruturados(
                registros,
                {
                    "linha_cabecalho": 0,
                    "cabecalhos": list(registros[0].keys()) if registros else [],
                    "nome_fornecedor": nome_fornecedor,
                    "tipo_fornecedor": tipo_fornecedor,
                },
            )

            diagnostico["formato"] = "xlsb"
            diagnostico["detalhes"] = detalhe
            diagnostico["ok"] = detalhe["ok"]
            diagnostico["modo_importacao"] = detalhe.get("modo_importacao")
            diagnostico["total_produtos_catalogo"] = detalhe.get("total_produtos_catalogo", 0)
            diagnostico["total_precos_importados"] = detalhe.get("total_precos_importados", 0)
            diagnostico["total_itens_extraidos"] = detalhe.get("total_itens_extraidos", 0)
            diagnostico["total_registros_lidos"] = detalhe.get("total_registros_lidos", 0)
            diagnostico["mensagens"] = detalhe["mensagens"]

        elif ext in [".xlsx", ".xls"]:
            from openpyxl import load_workbook

            wb = load_workbook(caminho, data_only=True, read_only=True)
            abas = []
            todos_registros = []

            for ws in wb.worksheets:
                linhas = list(ws.iter_rows(values_only=True))
                info = detectar_cabecalho_em_linhas(linhas)
                registros = []

                if info["linha_cabecalho"] is not None:
                    cabecalhos = info["cabecalhos"]
                    for row in linhas[info["linha_cabecalho"] + 1:]:
                        if all(c is None for c in row):
                            continue
                        item = {}
                        for j, val in enumerate(row):
                            if j < len(cabecalhos):
                                item[cabecalhos[j]] = val
                        registros.append(item)
                    todos_registros.extend(registros)

                detalhe = diagnosticar_registros_estruturados(
                    registros,
                        {
                            "aba": ws.title,
                            "linha_cabecalho": info["linha_cabecalho"],
                            "cabecalhos": info["cabecalhos"],
                            "nome_fornecedor": nome_fornecedor,
                            "tipo_fornecedor": tipo_fornecedor,
                        },
                    )
                abas.append(detalhe)

            wb.close()

            diagnostico["detalhes"]["abas"] = abas
            diagnostico["detalhes"]["total_registros_lidos"] = len(todos_registros)
            diagnostico["detalhes"]["total_itens_extraidos"] = sum(
                aba["total_itens_extraidos"] for aba in abas
            )
            diagnostico["detalhes"]["total_produtos_catalogo"] = sum(
                aba.get("total_produtos_catalogo", 0) for aba in abas
            )
            diagnostico["detalhes"]["total_precos_importados"] = sum(
                aba.get("total_precos_importados", 0) for aba in abas
            )
            if diagnostico["detalhes"]["total_precos_importados"]:
                diagnostico["modo_importacao"] = "tabela_com_preco"
            elif diagnostico["detalhes"]["total_produtos_catalogo"]:
                diagnostico["modo_importacao"] = "catalogo_sem_preco"
            diagnostico["total_produtos_catalogo"] = diagnostico["detalhes"]["total_produtos_catalogo"]
            diagnostico["total_precos_importados"] = diagnostico["detalhes"]["total_precos_importados"]
            diagnostico["ok"] = any(aba["ok"] for aba in abas)
            diagnostico["mensagens"] = [
                msg for aba in abas for msg in aba["mensagens"]
            ]

        elif ext == ".csv":
            texto = ler_texto_csv(caminho)
            dialect = detectar_dialeto_csv(texto)
            linhas = list(csv.reader(texto.splitlines(), dialect))
            info = detectar_cabecalho_em_linhas(linhas)
            registros = ler_csv(caminho)
            detalhe = diagnosticar_registros_estruturados(
                registros,
                {
                    "linha_cabecalho": info["linha_cabecalho"],
                    "cabecalhos": info["cabecalhos"],
                    "delimiter": getattr(dialect, "delimiter", None),
                    "nome_fornecedor": nome_fornecedor,
                    "tipo_fornecedor": tipo_fornecedor,
                },
            )
            diagnostico["detalhes"] = detalhe
            diagnostico["ok"] = detalhe["ok"]
            diagnostico["modo_importacao"] = detalhe.get("modo_importacao")
            diagnostico["total_produtos_catalogo"] = detalhe.get("total_produtos_catalogo", 0)
            diagnostico["total_precos_importados"] = detalhe.get("total_precos_importados", 0)
            diagnostico["mensagens"] = detalhe["mensagens"]

        elif ext == ".pdf":
            leitura_pdf = ler_pdf_detalhado(caminho)
            linhas = leitura_pdf["linhas"]
            itens = extrair_itens_texto(linhas, nome_fornecedor, tipo_fornecedor)
            diagnostico["ok"] = bool(itens)
            diagnostico["modo_importacao"] = "tabela_com_preco" if itens else None
            diagnostico["total_precos_importados"] = len(itens)
            diagnostico["detalhes"] = {
                "pdf_tem_texto": leitura_pdf["pdf_tem_texto"],
                "usou_ocr": leitura_pdf["usou_ocr"],
                "total_paginas": leitura_pdf["total_paginas"],
                "total_linhas_lidas": len(linhas),
                "total_itens_extraidos": len(itens),
                "preview_itens": itens[:5],
            }
            diagnostico["mensagens"].extend(leitura_pdf["mensagens"])
            if not itens:
                diagnostico["mensagens"].append("Nenhum item com preço foi extraído do PDF.")

        elif ext in [".jpg", ".jpeg", ".png"]:
            linhas = ler_imagem(caminho)
            itens = extrair_itens_texto(linhas, nome_fornecedor, tipo_fornecedor)
            diagnostico["ok"] = bool(itens)
            diagnostico["modo_importacao"] = "tabela_com_preco" if itens else None
            diagnostico["total_precos_importados"] = len(itens)
            diagnostico["detalhes"] = {
                "tesseract": str(TESSERACT_PADRAO),
                "total_linhas_lidas": len(linhas),
                "total_itens_extraidos": len(itens),
                "preview_itens": itens[:5],
            }
            if not itens:
                diagnostico["mensagens"].append("Nenhum item com preço foi extraído da imagem.")

        else:
            diagnostico["mensagens"].append(f"Formato não suportado para diagnóstico: {ext}")

    except Exception as erro:
        diagnostico["ok"] = False
        diagnostico["mensagens"].append(str(erro))

    return diagnostico


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


def extrair_itens_texto(linhas, nome_fornecedor, tipo_fornecedor):
    itens = []
    unidades = r"UN|UNI|CX|FR|PC|PT|KIT|AMP|BIS|SC|RL|MT|KG|GR|ML|L|TB|BX|AP|EV|CP|FA|FD"
    preco_re = r"(?:R\$\s*)?\d{1,6}(?:\.\d{3})*,\d{2,4}"
    usar_interest = any("INTEREST" in normalizar_cabecalho(linha) for linha in linhas)
    padrao_tabela = re.compile(
        rf"^\s*(?P<codigo>\S+)\s+(?P<descricao>.+?)\s+"
        rf"(?P<unidade>{unidades})\s+\d+\s+\d{{1,2}}%\s+"
        rf"(?P<precos>.+)$",
        re.IGNORECASE
    )
    padrao_generico = re.compile(
        rf"^\s*(?:(?P<codigo>\S+)\s+)?(?P<descricao>.+?)\s+(?P<preco>{preco_re})\b",
        re.IGNORECASE
    )

    marca = nome_fornecedor.upper() if tipo_fornecedor.upper() == "FABRICANTE" else ""

    for linha in linhas:
        linha = re.sub(r"\s+", " ", str(linha or "").strip().upper())

        if not linha:
            continue

        if normalizar_cabecalho(linha).startswith(("COD DESCRICAO", "CODIGO DESCRICAO")):
            continue

        m = padrao_tabela.match(linha)
        if m:
            precos_linha = re.findall(preco_re, m.group("precos"))
            indice_preco = 1 if usar_interest and len(precos_linha) > 1 else 0
            preco_raw = precos_linha[indice_preco] if precos_linha else None
        else:
            m = padrao_generico.match(linha)
            preco_raw = m.group("preco") if m else None

        if not m:
            continue

        descricao = re.sub(r"\s+", " ", m.group("descricao").strip().upper())

        if len(descricao) < 4 or not re.search(r"[A-Z]", descricao):
            continue

        preco = limpar_preco(preco_raw)

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
            "preco_formatado": moeda_br(preco),
            "fornecedor_nome": nome_fornecedor.upper(),
            "tipo_fornecedor": tipo_fornecedor.upper(),
            "unidade": (m.groupdict().get("unidade") or "").strip().upper(),
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
        cursor.execute("UPDATE fornecedores SET ativo = 1 WHERE id = ?", (row["id"],))
        return row["id"]

    cursor.execute("""
        INSERT INTO fornecedores (nome, tipo, contato, email, telefone, ativo)
        VALUES (?, ?, '', '', '', 1)
    """, (nome, tipo))

    return cursor.lastrowid


# ================================================
# GARANTE PRODUTO NO SKU MASTER
# ================================================

<<<<<<< HEAD
def _extrair_numeros_unidades(texto):
    """Extrai números seguidos de unidades comuns para evitar match errado."""
    if not texto: return []
    # Busca por 500MG, 10ML, 0.9%, etc e normaliza removendo espaços
    encontrados = re.findall(r'(\d+(?:[.,]\d+)?\s*(?:MG|ML|G|MCG|UI|%))', texto.upper())
    return [re.sub(r'\s+', '', e) for e in encontrados]


def garantir_produto(cursor, sku_master, categoria, fabricante, cache_produtos=None):
=======
def garantir_produto(cursor, sku_master, categoria, fabricante):
>>>>>>> origin/main
    sku_master = str(sku_master or "").strip().upper()
    categoria = str(categoria or "").strip().upper()
    fabricante = str(fabricante or "").strip().upper()

    if not sku_master:
        return None

<<<<<<< HEAD
    # 1. Match exato
=======
>>>>>>> origin/main
    cursor.execute("SELECT id FROM produtos WHERE UPPER(produto_padrao) = ?", (sku_master,))
    row = cursor.fetchone()

    if row:
        produto_id = row["id"]
<<<<<<< HEAD
        cursor.execute("""
            UPDATE produtos
            SET fabricante = CASE WHEN fabricante IS NULL OR fabricante = '' THEN ? ELSE fabricante END,
                categoria = CASE WHEN categoria IS NULL OR categoria = '' THEN ? ELSE categoria END,
                ativo = 1
            WHERE id = ?
        """, (fabricante, categoria, produto_id))
        return produto_id

    # 2. Match fuzzy (se não encontrou exato)
    # Usa cache se disponível para performance
    if cache_produtos is not None:
        todos_produtos = cache_produtos
    else:
        cursor.execute("SELECT id, produto_padrao FROM produtos WHERE ativo = 1")
        todos_produtos = [{"id": r[0], "produto_padrao": r[1]} for r in cursor.fetchall()]

    melhor_match = None
    maior_score = 0
    num_origem = _extrair_numeros_unidades(sku_master)

    for p in todos_produtos:
        if not p["produto_padrao"]:
            continue

        p_nome = p["produto_padrao"].upper()
        # Se os nomes normalizados sem espaços/pontuação forem iguais, match imediato 100%
        # Isso ajuda muito em casos como "DIPIRONA 500MG" vs "DIPIRONA 500 MG"
        if re.sub(r'[^A-Z0-9]', '', sku_master) == re.sub(r'[^A-Z0-9]', '', p_nome):
            score = 100.0
        else:
            score = fuzz.token_set_ratio(sku_master, p_nome)

        if score >= 92 and score > maior_score:
            # Segurança extra: se tem números/unidades, eles PRECISAM bater
            num_destino = _extrair_numeros_unidades(p_nome)
            if num_origem or num_destino:
                # Se os conjuntos de concentrações/volumes são diferentes, ignora o fuzzy
                if set(num_origem) != set(num_destino):
                    continue

            maior_score = score
            melhor_match = p["id"]

    if melhor_match:
        cursor.execute("""
            UPDATE produtos
            SET fabricante = CASE WHEN fabricante IS NULL OR fabricante = '' THEN ? ELSE fabricante END,
                categoria = CASE WHEN categoria IS NULL OR categoria = '' THEN ? ELSE categoria END,
                ativo = 1
            WHERE id = ?
        """, (fabricante, categoria, melhor_match))
        return melhor_match

    # 3. Cria novo se nada for encontrado
=======

        cursor.execute("""
            UPDATE produtos
            SET fabricante = COALESCE(NULLIF(?, ''), fabricante),
                categoria = COALESCE(NULLIF(?, ''), categoria),
                ativo = 1
            WHERE id = ?
        """, (fabricante, categoria, produto_id))

        return produto_id

>>>>>>> origin/main
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


def garantir_produto_catalogo(cursor, sku_master, categoria, fabricante):
    sku_master = str(sku_master or "").strip().upper()
    categoria = str(categoria or "").strip().upper()
    fabricante = str(fabricante or "").strip().upper()

    if not sku_master:
        return None, "ignorado"

    cursor.execute("""
        SELECT id, fabricante, categoria
        FROM produtos
        WHERE UPPER(produto_padrao) = ?
    """, (sku_master,))
    row = cursor.fetchone()

    if row:
        produto_id = row["id"]
        fabricante_atual = str(row["fabricante"] or "").strip()
        categoria_atual = str(row["categoria"] or "").strip()
        novo_fabricante = fabricante_atual or fabricante
        nova_categoria = categoria_atual or categoria

        cursor.execute("""
            UPDATE produtos
            SET fabricante = ?,
                categoria = ?,
                ativo = 1
            WHERE id = ?
        """, (novo_fabricante, nova_categoria, produto_id))

        if novo_fabricante != fabricante_atual or nova_categoria != categoria_atual:
            return produto_id, "atualizado"

        return produto_id, "existente"

    cursor.execute("""
        INSERT INTO produtos (sku, produto_padrao, fabricante, categoria, ativo)
        VALUES ('', ?, ?, ?, 1)
    """, (sku_master, fabricante, categoria))

    produto_id = cursor.lastrowid

    cursor.execute("""
        INSERT INTO equivalencias (produto_id, descricao_equivalente)
        VALUES (?, ?)
    """, (produto_id, sku_master))

    return produto_id, "criado"


def garantir_equivalencia(cursor, produto_id, descricao):
    descricao = str(descricao or "").strip().upper()

    if not produto_id or not descricao:
        return

    cursor.execute("""
        SELECT id FROM equivalencias
        WHERE produto_id = ?
        AND UPPER(descricao_equivalente) = ?
    """, (produto_id, descricao))

    if cursor.fetchone():
        return

    cursor.execute("""
        INSERT INTO equivalencias (produto_id, descricao_equivalente)
        VALUES (?, ?)
    """, (produto_id, descricao))


def importar_catalogo_sem_preco(caminho, fornecedor_id, nome_fornecedor, tipo_fornecedor, itens):
    conn = conectar()
    cursor = conn.cursor()

    criados = 0
    atualizados = 0

    try:
        garantir_fornecedor(cursor, nome_fornecedor, tipo_fornecedor)

        for item in itens:
            marca = item["marca"]

            if not marca and item["tipo_fornecedor"] == "FABRICANTE":
                marca = item["fornecedor_nome"] or nome_fornecedor.upper()

            produto_id, status = garantir_produto_catalogo(
                cursor,
                item["nome_produto"],
                item["categoria"],
                marca
            )

            if not produto_id:
                continue

            garantir_equivalencia(cursor, produto_id, item["descricao_orig"])

            if status == "criado":
                criados += 1
            elif status == "atualizado":
                atualizados += 1

        conn.commit()
    finally:
        conn.close()

    return {
        "ok": True,
        "modo_importacao": "catalogo_sem_preco",
        "total_produtos_catalogo": len(itens),
        "total_produtos_criados": criados,
        "total_produtos_atualizados": atualizados,
        "total_precos_importados": 0,
        "arquivo_origem": Path(caminho).name,
        "mensagens": [],
    }


# ================================================
# IMPORTAÇÃO PRINCIPAL
# ================================================

def importar_arquivo_fornecedor(caminho, fornecedor_id, nome_fornecedor, tipo_fornecedor):
    caminho = Path(caminho)
    ext = caminho.suffix.lower()
    data_hoje = datetime.now().strftime("%Y-%m-%d")
    itens_catalogo = []

    if ext == ".xlsb" or detectar_excel_binario(caminho):
        registros = ler_xlsb(caminho)
        itens = extrair_itens_estruturado(registros)
        if not itens:
            itens_catalogo = extrair_itens_catalogo_estruturado(
                registros,
                nome_fornecedor,
                tipo_fornecedor
            )

    elif ext in [".xlsx", ".xls"]:
        registros = ler_excel(caminho)
        itens = extrair_itens_estruturado(registros)
        if not itens:
            itens_catalogo = extrair_itens_catalogo_estruturado(
                registros,
                nome_fornecedor,
                tipo_fornecedor
            )

    elif ext == ".csv":
        registros = ler_csv(caminho)
        itens = extrair_itens_estruturado(registros)
        if not itens:
            itens_catalogo = extrair_itens_catalogo_estruturado(
                registros,
                nome_fornecedor,
                tipo_fornecedor
            )

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

    if not itens and itens_catalogo:
        diagnostico_catalogo = importar_catalogo_sem_preco(
            caminho,
            fornecedor_id,
            nome_fornecedor,
            tipo_fornecedor,
            itens_catalogo
        )
        importar_arquivo_fornecedor.ultimo_diagnostico = diagnostico_catalogo
        return diagnostico_catalogo["total_produtos_catalogo"]

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
<<<<<<< HEAD

    # Cache de produtos ativos para evitar SELECTs repetidos no fuzzy
    cursor.execute("SELECT id, produto_padrao FROM produtos WHERE ativo = 1")
    cache_produtos = [{"id": r[0], "produto_padrao": r[1]} for r in cursor.fetchall()]
=======
>>>>>>> origin/main

    importados = 0

    for item in itens:
        if item["sku_existente"]:
            sku_master = item["sku_existente"]
            sku_provisorio = False
        else:
            sku_master = mapa_sku.get(item["descricao_orig"])
            sku_provisorio = not sku_gerado_valido(item["descricao_orig"], sku_master)
            if sku_provisorio:
                sku_master = montar_sku_provisorio(item["descricao_orig"])

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

        categoria = item["categoria"]
        if sku_provisorio:
            categoria = (
                f"{categoria} | SKU PENDENTE DE PADRONIZACAO"
                if categoria else "SKU PENDENTE DE PADRONIZACAO"
            )

        produto_id = garantir_produto(
            cursor,
            sku_master,
            categoria,
<<<<<<< HEAD
            marca,
            cache_produtos=cache_produtos
=======
            marca
>>>>>>> origin/main
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

<<<<<<< HEAD
=======
        conn.commit()

>>>>>>> origin/main
        registrar_preco_fornecedor(
            fornecedor_id=fid,
            produto_id=produto_id,
            descricao_original=item["descricao_orig"],
            codigo_fornecedor=item["codigo"],
            marca=marca,
            preco=item["preco"],
            data_importacao=data_hoje,
            arquivo_origem=caminho.name,
<<<<<<< HEAD
            origem_importacao="IMPORTADOR_UNIVERSAL",
            conn_existente=conn
=======
            origem_importacao="IMPORTADOR_UNIVERSAL"
>>>>>>> origin/main
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
