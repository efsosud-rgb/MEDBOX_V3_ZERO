import csv
import io
import re
import unicodedata
from pathlib import Path

from rapidfuzz import fuzz

from core.auditoria_sku_master import sugerir_sku_medbox_oficial
from core.busca_inteligente import buscar_produto_inteligente
from core.formatadores import moeda_br


EXTENSOES_SUPORTADAS = {".pdf", ".xlsx", ".xls", ".doc", ".docx", ".csv", ".png", ".jpg", ".jpeg"}

COLUNAS_DESCRICAO = (
    "DESCRICAO",
    "DESCRICAO DO PRODUTO",
    "PRODUTO",
    "MATERIAL",
    "ITEM",
    "ESPECIFICACAO",
)
COLUNAS_QUANTIDADE = ("QUANTIDADE", "QTD", "QTDE", "QUANT")
COLUNAS_OSINFO = ("PRECO OSINFO", "OSINFO", "VALOR OSINFO", "MENOR PRECO", "PRECO REFERENCIA")
COLUNAS_ULTIMA_COMPRA = (
    "ULT COMP",
    "ULTIMA COMPRA",
    "ULTIMA COMPRA DA COTACAO",
    "ULTIMA AQUISICAO",
)


def normalizar_texto(texto):
    texto = str(texto or "").strip().upper()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(ch for ch in texto if not unicodedata.combining(ch))
    texto = re.sub(r"[^A-Z0-9%+/,.-]+", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()


def numero_br(valor, padrao=0.0):
    if valor is None:
        return padrao
    if isinstance(valor, (int, float)):
        return float(valor)

    texto = str(valor).strip()
    if not texto:
        return padrao
    texto = texto.replace("R$", "").replace(" ", "")
    if "," in texto and "." in texto:
        texto = texto.replace(".", "").replace(",", ".")
    else:
        texto = texto.replace(",", ".")
    texto = re.sub(r"[^0-9.-]", "", texto)
    if not texto:
        return padrao
    try:
        return float(texto)
    except ValueError:
        return padrao


def _coluna_por_sinonimos(colunas, sinonimos):
    normalizadas = {normalizar_texto(coluna): coluna for coluna in colunas}
    for sinonimo in sinonimos:
        sinonimo_norm = normalizar_texto(sinonimo)
        if sinonimo_norm in normalizadas:
            return normalizadas[sinonimo_norm]
    for coluna_norm, coluna_original in normalizadas.items():
        if any(s in coluna_norm for s in map(normalizar_texto, sinonimos)):
            return coluna_original
    return None


def _item_extraido(descricao, quantidade=1, preco_osinfo=0, ultima_compra=0, origem="arquivo"):
    descricao = str(descricao or "").strip()
    return {
        "descricao_original": descricao,
        "quantidade": numero_br(quantidade, 1.0) or 1.0,
        "preco_osinfo": numero_br(preco_osinfo, 0.0),
        "ultima_compra": numero_br(ultima_compra, 0.0),
        "origem": origem,
    }


def _linhas_para_itens(linhas, origem="texto"):
    itens = []
    for linha in linhas:
        texto = str(linha or "").strip()
        if not texto or len(texto) < 3:
            continue

        partes = [p.strip() for p in re.split(r"\s*[|;]\s*|\t+", texto) if p.strip()]
        if len(partes) >= 2:
            descricao = partes[0]
            quantidade = partes[1] if len(partes) > 1 else 1
            preco_osinfo = partes[2] if len(partes) > 2 else 0
            ultima_compra = partes[3] if len(partes) > 3 else 0
            if not _parece_cabecalho(descricao):
                itens.append(_item_extraido(descricao, quantidade, preco_osinfo, ultima_compra, origem))
            continue

        valores = re.findall(r"(?:R\$\s*)?\d+(?:[.,]\d{1,4})", texto)
        if valores:
            descricao = texto
            for valor in valores[-3:]:
                descricao = descricao.replace(valor, "", 1)
            descricao = re.sub(r"\s+", " ", descricao).strip(" -|;")
            quantidade = valores[-3] if len(valores) >= 3 else 1
            preco_osinfo = valores[-2] if len(valores) >= 2 else 0
            ultima_compra = valores[-1] if len(valores) >= 1 else 0
            if descricao and not _parece_cabecalho(descricao):
                itens.append(_item_extraido(descricao, quantidade, preco_osinfo, ultima_compra, origem))
        elif not _parece_cabecalho(texto):
            itens.append(_item_extraido(texto, 1, 0, 0, origem))
    return itens


def _parece_cabecalho(texto):
    texto_norm = normalizar_texto(texto)
    termos = ("DESCRICAO", "PRODUTO", "QUANTIDADE", "PRECO", "ULTIMA COMPRA")
    return sum(1 for termo in termos if termo in texto_norm) >= 2


def _registros_para_itens(registros):
    if not registros:
        return []

    colunas = list(registros[0].keys())
    coluna_descricao = _coluna_por_sinonimos(colunas, COLUNAS_DESCRICAO)
    coluna_quantidade = _coluna_por_sinonimos(colunas, COLUNAS_QUANTIDADE)
    coluna_osinfo = _coluna_por_sinonimos(colunas, COLUNAS_OSINFO)
    coluna_ultima = _coluna_por_sinonimos(colunas, COLUNAS_ULTIMA_COMPRA)

    if not coluna_descricao:
        linhas = [" | ".join(str(v) for v in registro.values() if str(v).strip()) for registro in registros]
        return _linhas_para_itens(linhas, origem="tabela_sem_colunas")

    itens = []
    for registro in registros:
        descricao = registro.get(coluna_descricao)
        if not descricao or _parece_cabecalho(descricao):
            continue
        itens.append(_item_extraido(
            descricao,
            registro.get(coluna_quantidade, 1) if coluna_quantidade else 1,
            registro.get(coluna_osinfo, 0) if coluna_osinfo else 0,
            registro.get(coluna_ultima, 0) if coluna_ultima else 0,
            origem="tabela",
        ))
    return itens


def extrair_itens_cotacao(caminho):
    caminho = Path(caminho)
    ext = caminho.suffix.lower()
    if ext not in EXTENSOES_SUPORTADAS:
        raise ValueError(f"Formato nao suportado para cotacao: {ext}")

    if ext == ".csv":
        return _extrair_csv(caminho)
    if ext in (".xlsx", ".xls"):
        return _extrair_excel(caminho)
    if ext == ".docx":
        return _extrair_docx(caminho)
    if ext == ".doc":
        return _extrair_doc(caminho)
    if ext == ".pdf":
        return _extrair_pdf(caminho)
    return _extrair_imagem(caminho)


def _extrair_csv(caminho):
    texto = caminho.read_text(encoding="utf-8-sig", errors="ignore")
    amostra = texto[:2048]
    try:
        dialect = csv.Sniffer().sniff(amostra, delimiters=",;|\t")
    except csv.Error:
        dialect = csv.excel
        dialect.delimiter = ";"

    reader = csv.DictReader(io.StringIO(texto), dialect=dialect)
    if reader.fieldnames:
        registros = [dict(row) for row in reader]
        itens = _registros_para_itens(registros)
        if itens:
            return itens
    return _linhas_para_itens(texto.splitlines(), origem="csv_texto")


def _extrair_excel(caminho):
    try:
        import pandas as pd
    except ImportError as erro:
        raise ValueError("Pandas nao esta disponivel para ler Excel.") from erro

    planilhas = pd.read_excel(caminho, sheet_name=None, dtype=str)
    registros = []
    for _, df in planilhas.items():
        df = df.dropna(how="all")
        df = df.fillna("")
        registros.extend(df.to_dict(orient="records"))
    return _registros_para_itens(registros)


def _extrair_docx(caminho):
    try:
        from docx import Document
    except ImportError as erro:
        raise ValueError("python-docx nao esta disponivel para ler DOCX.") from erro

    doc = Document(caminho)
    linhas = [p.text for p in doc.paragraphs if p.text.strip()]
    for tabela in doc.tables:
        for row in tabela.rows:
            linhas.append(" | ".join(cell.text.strip() for cell in row.cells))
    return _linhas_para_itens(linhas, origem="docx")


def _extrair_doc(caminho):
    dados = caminho.read_bytes()
    texto = dados.decode("latin-1", errors="ignore")
    linhas = []
    for linha in texto.splitlines():
        linha_limpa = re.sub(r"[^\x20-\x7E\u00C0-\u00FF]+", " ", linha).strip()
        if linha_limpa:
            linhas.append(linha_limpa)
    itens = _linhas_para_itens(linhas, origem="doc")
    if not itens:
        raise ValueError("Nao foi possivel extrair itens do DOC. Salve como DOCX, PDF com texto, XLSX ou CSV.")
    return itens


def _extrair_pdf(caminho):
    try:
        import pdfplumber
    except ImportError as erro:
        raise ValueError("pdfplumber nao esta disponivel para ler PDF.") from erro

    linhas = []
    with pdfplumber.open(caminho) as pdf:
        for pagina in pdf.pages:
            texto = pagina.extract_text() or ""
            linhas.extend(texto.splitlines())
            for tabela in pagina.extract_tables() or []:
                for row in tabela:
                    linhas.append(" | ".join(str(cell or "").strip() for cell in row))

    if not linhas:
        raise ValueError("PDF sem texto extraivel. Use arquivo com texto ou OCR disponivel.")
    return _linhas_para_itens(linhas, origem="pdf")


def _extrair_imagem(caminho):
    try:
        from PIL import Image
        import pytesseract
    except ImportError as erro:
        raise ValueError("OCR indisponivel para imagem. Envie XLSX, CSV, DOCX ou PDF com texto.") from erro

    try:
        texto = pytesseract.image_to_string(Image.open(caminho), lang="por")
    except Exception:
        try:
            texto = pytesseract.image_to_string(Image.open(caminho), lang="eng")
        except Exception as erro:
            raise ValueError(
                "OCR indisponivel. Instale o idioma portugues do Tesseract ou envie XLSX/CSV/PDF com texto."
            ) from erro
    return _linhas_para_itens(texto.splitlines(), origem="ocr")


def _termo_busca_tecnico(descricao):
    texto = normalizar_texto(descricao)
    sku_oficial, confianca_oficial = sugerir_sku_medbox_oficial(texto)
    if sku_oficial and confianca_oficial >= 88:
        return sku_oficial

    texto = texto.replace("DESC HIP", "HIPODERMICA")
    texto = texto.replace("DISP SEG", "COM DISPOSITIVO DE SEGURANCA")

    percentual = re.search(r"\b(\d+(?:[,.]\d+)?)\s*%", texto)
    volume = re.search(r"\b(\d+(?:[,.]\d+)?)\s*ML\b", texto)
    medida_agulha = re.search(r"\b\d{1,2}\s*[Xx]\s*\d{1,2}(?:[,.]\d+)?\b", texto)

    if "GLICOSE" in texto and percentual:
        partes = ["SORO GLICOSADO", percentual.group(0).replace(" ", "")]
        if volume:
            partes.append(volume.group(0).replace(" ", ""))
        return " ".join(partes)

    if "CLORETO DE SODIO" in texto and percentual:
        partes = ["SORO FISIOLOGICO", percentual.group(0).replace(" ", "")]
        if volume:
            partes.append(volume.group(0).replace(" ", ""))
        return " ".join(partes)

    if "AGULHA" in texto and medida_agulha:
        partes = ["AGULHA"]
        if "SEGURANCA" in texto:
            partes.extend(["COM", "DISPOSITIVO", "DE", "SEGURANCA"])
        partes.append(medida_agulha.group(0).replace(" ", ""))
        return " ".join(partes)

    return texto


def _sku_tecnico_derivado(descricao):
    texto = normalizar_texto(descricao)
    sku_oficial, confianca_oficial = sugerir_sku_medbox_oficial(texto)
    if sku_oficial and confianca_oficial >= 88:
        return {
            "id": f"oficial:{sku_oficial}",
            "sku": "",
            "produto_padrao": sku_oficial,
            "sku_master_exibicao": sku_oficial,
            "sku_master_lances": sku_oficial,
            "fabricante": "",
            "categoria": "DICIONARIO MEDBOX",
            "score_busca": float(confianca_oficial),
            "precos": [],
            "menor_preco": None,
            "fornecedor_menor": "-",
            "tem_preco": False,
        }

    medida_agulha = re.search(r"\b\d{1,2}\s*[Xx]\s*\d{1,2}(?:[,.]\d+)?\b", texto)
    if "AGULHA" in texto and medida_agulha and ("SEGURANCA" in texto or "DISP SEG" in texto):
        return {
            "id": f"assinatura:{medida_agulha.group(0)}:seg",
            "sku": "",
            "produto_padrao": f"AGULHA C/DISP SEG {medida_agulha.group(0).replace(' ', '')}",
            "sku_master_exibicao": f"AGULHA C/DISP SEG {medida_agulha.group(0).replace(' ', '')}",
            "fabricante": "",
            "categoria": "ASSINATURA TECNICA",
            "score_busca": 72.0,
            "precos": [],
            "menor_preco": None,
            "fornecedor_menor": "-",
            "tem_preco": False,
        }
    return None


def _assinatura_compativel(descricao, candidato):
    descricao_norm = normalizar_texto(descricao)
    sku_norm = normalizar_texto(candidato.get("sku_master_exibicao") or candidato.get("produto_padrao"))

    percentuais_desc = set(re.findall(r"\b\d+(?:[,.]\d+)?%", descricao_norm))
    percentuais_sku = set(re.findall(r"\b\d+(?:[,.]\d+)?%", sku_norm))
    if percentuais_desc and percentuais_sku and not (percentuais_desc & percentuais_sku):
        return False

    medidas_desc = set(re.findall(r"\b\d{1,2}X\d{1,2}(?:[,.]\d+)?\b", descricao_norm.replace(" ", "")))
    medidas_sku = set(re.findall(r"\b\d{1,2}X\d{1,2}(?:[,.]\d+)?\b", sku_norm.replace(" ", "")))
    if medidas_desc and medidas_sku and not (medidas_desc & medidas_sku):
        return False

    if "SEGURANCA" in descricao_norm or "DISP SEG" in descricao_norm:
        return "SEG" in sku_norm or "SEGURANCA" in sku_norm

    return True


def buscar_sku_para_lance(descricao, score_minimo=70):
    termo_tecnico = _termo_busca_tecnico(descricao)
    sku_oficial, confianca_oficial = sugerir_sku_medbox_oficial(descricao)
    termos = [termo_tecnico, descricao]
    candidatos = []
    vistos = set()
    for termo in termos:
        for candidato in buscar_produto_inteligente(termo, limite=8):
            if candidato["id"] in vistos:
                continue
            vistos.add(candidato["id"])
            candidatos.append(candidato)

    candidatos = [c for c in candidatos if _assinatura_compativel(descricao, c)]
    candidatos.sort(key=lambda c: (
        -(c.get("score_busca") or 0),
        -int(bool(c.get("tem_preco"))),
        c.get("menor_preco") if c.get("menor_preco") is not None else 999999999,
        c.get("produto_padrao") or "",
    ))

    if not candidatos:
        return _sku_tecnico_derivado(descricao)

    melhor = candidatos[0]
    if sku_oficial and confianca_oficial >= 88:
        melhor = dict(melhor)
        melhor["sku_master_lances"] = sku_oficial
        melhor["sku_master_exibicao"] = sku_oficial

    derivado = _sku_tecnico_derivado(descricao)
    if derivado and not sku_oficial:
        sku_norm = normalizar_texto(melhor.get("sku_master_exibicao") or melhor.get("produto_padrao"))
        medida_derivada = re.search(r"\d{1,2}X\d{1,2}(?:[,.]\d+)?", derivado["sku_master_exibicao"].replace(" ", ""))
        if medida_derivada and medida_derivada.group(0) not in sku_norm.replace(" ", ""):
            return derivado

    if (melhor.get("score_busca") or 0) < score_minimo:
        return None
    return melhor


def _menor_preco(candidato):
    precos = candidato.get("precos") or []
    if not precos:
        return None
    return precos[0]


def _vencedor_item(valores):
    candidatos = [(nome, valor) for nome, valor in valores if valor and valor > 0]
    if not candidatos:
        return 0.0, "-"
    nome, valor = min(candidatos, key=lambda item: item[1])
    return valor, nome


def _status_item(sku_encontrado, menor_custo, preco_medbox, preco_osinfo, menor_lance):
    if not sku_encontrado:
        return "REVISAR SKU"
    if menor_custo is None:
        return "SEM PRECO"
    referencia = menor_lance if menor_lance and menor_lance > 0 else preco_osinfo
    if not referencia or referencia <= 0:
        return "SEM LANCE INFORMADO"
    return "COMPETITIVO" if preco_medbox <= referencia else "NEGOCIAR"


def analisar_itens_lances(itens, markup_percentual=80, score_minimo=70):
    markup_percentual = numero_br(markup_percentual, 80.0)
    analisados = []

    for indice, item in enumerate(itens, start=1):
        candidato = buscar_sku_para_lance(item["descricao_original"], score_minimo=score_minimo)
        preco_menor = _menor_preco(candidato) if candidato else None
        menor_custo = preco_menor.get("preco") if preco_menor else None
        preco_medbox = round(float(menor_custo) * (1 + markup_percentual / 100), 4) if menor_custo is not None else 0.0
        menor_lance = 0.0
        menor_valor, vencedor = _vencedor_item([
            ("OSINFO", item["preco_osinfo"]),
            ("Ultima Compra", item["ultima_compra"]),
            ("MedBox", preco_medbox),
            ("Concorrente", menor_lance),
        ])
        status = _status_item(bool(candidato), menor_custo, preco_medbox, item["preco_osinfo"], menor_lance)
        quantidade = item["quantidade"] or 1.0

        analisado = {
            "item": indice,
            "descricao_original": item["descricao_original"],
            "sku_master": (candidato or {}).get("sku_master_lances") or (candidato or {}).get("sku_master_exibicao") or (candidato or {}).get("produto_padrao") or "REVISAR SKU",
            "score_busca": (candidato or {}).get("score_busca", 0),
            "quantidade": quantidade,
            "preco_osinfo": item["preco_osinfo"],
            "ultima_compra": item["ultima_compra"],
            "preco_medbox": preco_medbox,
            "menor_preco_ofertado": menor_lance,
            "empresa_melhor_lance": "",
            "menor_valor_item": menor_valor,
            "vencedor_item": vencedor,
            "menor_custo_unitario": menor_custo,
            "fornecedor_menor_custo": (candidato or {}).get("fornecedor_menor") or "-",
            "marca_fabricante": (preco_menor or {}).get("marca") or (candidato or {}).get("fabricante") or "-",
            "status": status,
            "tem_sku": bool(candidato),
            "tem_preco": menor_custo is not None,
            "markup_atual": markup_percentual if menor_custo else None,
            "preco_osinfo_formatado": moeda_br(item["preco_osinfo"]),
            "ultima_compra_formatada": moeda_br(item["ultima_compra"]),
            "preco_medbox_formatado": moeda_br(preco_medbox),
            "menor_preco_ofertado_formatado": moeda_br(menor_lance),
            "menor_valor_item_formatado": moeda_br(menor_valor),
            "menor_custo_unitario_formatado": moeda_br(menor_custo),
            "total_medbox": preco_medbox * quantidade,
            "total_osinfo": item["preco_osinfo"] * quantidade,
            "total_ultima_compra": item["ultima_compra"] * quantidade,
            "total_menor_lance": menor_lance * quantidade,
            "total_menor_valor": menor_valor * quantidade,
        }
        analisados.append(analisado)

    return {
        "markup_percentual": markup_percentual,
        "itens": analisados,
        "resumo": montar_resumo_lances(analisados),
    }


def montar_resumo_lances(itens):
    total_itens = len(itens)
    itens_com_sku = sum(1 for item in itens if item["tem_sku"])
    itens_revisar = sum(1 for item in itens if item["status"] == "REVISAR SKU")
    itens_com_preco = sum(1 for item in itens if item["tem_preco"])
    itens_sem_preco = sum(1 for item in itens if item["status"] == "SEM PRECO")
    itens_competitivos = sum(1 for item in itens if item["status"] == "COMPETITIVO")
    itens_negociar = sum(1 for item in itens if item["status"] == "NEGOCIAR")
    margens = [item["markup_atual"] for item in itens if item["markup_atual"] is not None]

    resumo = {
        "total_itens": total_itens,
        "itens_com_sku": itens_com_sku,
        "itens_revisar_sku": itens_revisar,
        "itens_com_preco_medbox": itens_com_preco,
        "itens_sem_preco": itens_sem_preco,
        "itens_competitivos": itens_competitivos,
        "itens_negociar": itens_negociar,
        "total_osinfo": sum(item["total_osinfo"] for item in itens),
        "total_ultima_compra": sum(item["total_ultima_compra"] for item in itens),
        "total_medbox": sum(item["total_medbox"] for item in itens),
        "total_menor_lance": sum(item["total_menor_lance"] for item in itens),
        "total_menor_valor": sum(item["total_menor_valor"] for item in itens),
        "margem_media_medbox": round(sum(margens) / len(margens), 2) if margens else 0.0,
        "valor_total_estimado": sum(item["total_medbox"] for item in itens),
    }
    for chave in (
        "total_osinfo",
        "total_ultima_compra",
        "total_medbox",
        "total_menor_lance",
        "total_menor_valor",
        "valor_total_estimado",
    ):
        resumo[f"{chave}_formatado"] = moeda_br(resumo[chave])
    return resumo


def analisar_arquivo_cotacao(caminho, markup_percentual=80):
    itens = extrair_itens_cotacao(caminho)
    return analisar_itens_lances(itens, markup_percentual=markup_percentual)
