import csv
import io
import json
import re
import shutil
import sqlite3
import unicodedata
import uuid
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from rapidfuzz import fuzz


BASE_DIR = Path(__file__).resolve().parent.parent
CAMINHO_BANCO = BASE_DIR / "banco" / "medbox_v3.db"
PASTA_BACKUPS = BASE_DIR / "banco" / "backups"
PASTA_RELATORIOS = BASE_DIR / "relatorios"
CAMINHO_LOG_CORRECOES = PASTA_RELATORIOS / "sku_master_correcoes.jsonl"

CLASSIFICACOES = {
    "LIMPO",
    "SUSPEITO",
    "CONTAMINADO_FORTE",
    "SKU_PENDENTE",
    "DUPLICADO",
}

FILTROS = {
    "todos": "",
    "limpo": "LIMPO",
    "suspeito": "SUSPEITO",
    "contaminado_forte": "CONTAMINADO_FORTE",
    "sku_pendente": "SKU_PENDENTE",
    "duplicado": "DUPLICADO",
}

GRUPOS_SUGESTOES = {
    "todos": "",
    "soro_fisiologico": "soro_fisiologico",
    "soro_glicosado": "soro_glicosado",
    "ondansetrona": "ondansetrona",
    "dipirona": "dipirona",
    "agulha": "agulha",
}

STOPWORDS_SKU = {
    "DE", "DA", "DO", "DAS", "DOS", "E", "A", "O", "AS", "OS",
    "COM", "C", "SEM", "PARA", "P", "POR", "EM", "NA", "NO", "NAS", "NOS",
}

MARCAS_FINAIS_SUSPEITAS = {
    "EQUIPLEX", "FARMACE", "HALEXISTAR", "SAMTEC", "HIPOLABOR",
    "CRISTALIA", "TEUTO", "MEDIX", "THEOTO", "SOL", "CARE",
}

ABREVIACOES_MEDBOX = {
    "COM DISPOSITIVO DE SEGURANCA": "C/DISP SEG",
    "DISPOSITIVO DE SEGURANCA": "DISP SEG",
    "SISTEMA DE SEGURANCA": "SIST SEG",
    "SISTEMA FECHADO": "SIST FECH",
    "SISTEMA ABERTO": "SIST ABER",
    "COLETA A VACUO": "COLETA VAC",
    "A VACUO": "VAC",
    "NAO ESTERIL": "N/EST",
    "FRASCO AMPOLA": "FR AMP",
    "FRASCO-AMPOLA": "FR AMP",
    "SOLUCAO INJETAVEL": "SOL INJ",
    "SOL INJETAVEL": "SOL INJ",
    "SOLUCAO ORAL": "SOL ORAL",
    "RINGER COM LACTATO": "RINGER C/LACTATO",
    "RINGER LACTATO": "RINGER C/LACTATO",
    "SONDA FOLEY": "FOLEY",
    "INTRAVENOSO": "IV",
    "INTRAMUSCULAR": "IM",
    "SUBCUTANEO": "SC",
    "VIA ORAL": "VO",
    "OFTALMICO": "OFT",
    "TOPICO": "TOP",
    "NASAL": "NAS",
    "RETAL": "RET",
    "COMPRIMIDOS": "COMP",
    "COMPRIMIDO": "COMP",
    "CAPSULAS": "CAPS",
    "CAPSULA": "CAPS",
    "DRAGEA": "COMP",
    "SUSPENSAO": "SUSP",
    "XAROPE": "XPE",
    "EMULSAO": "EMUL",
    "CREME": "CREM",
    "POMADA": "POM",
    "LOCAO": "LOC",
    "AEROSSOL": "AER",
    "AMPOLAS": "AMP",
    "AMPOLA": "AMP",
    "FRASCO": "FR",
    "BOLSA": "BOL",
    "BISNAGA": "BIS",
    "SERINGA": "SER",
    "ENVELOPE": "ENV",
    "REFIL": "REF",
    "ESTERIL": "EST",
    "DESCARTAVEL": "DESC",
    "CIRURGICO": "CIR",
    "PROCEDIMENTO": "PROC",
}


def _conectar_leitura():
    caminho = CAMINHO_BANCO.as_posix()
    return sqlite3.connect(f"file:{caminho}?mode=ro", uri=True)


def _normalizar(texto):
    if texto is None:
        return ""
    texto = str(texto).strip().upper()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(ch for ch in texto if not unicodedata.combining(ch))
    texto = re.sub(r"[^A-Z0-9%+/,.-]+", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()


def aplicar_abreviacoes_medbox(texto):
    texto = _normalizar(texto)
    if not texto:
        return ""

    for termo, abreviacao in sorted(ABREVIACOES_MEDBOX.items(), key=lambda item: len(item[0]), reverse=True):
        if termo == "DESCARTAVEL":
            padrao = rf"(?<![A-Z0-9/])(?<!AGULHA ){re.escape(termo)}(?![A-Z0-9/])"
        else:
            padrao = rf"(?<![A-Z0-9/]){re.escape(termo)}(?![A-Z0-9/])"
        texto = re.sub(padrao, abreviacao, texto)

    texto = re.sub(r"(?<!SOL )(?<!SOLUCAO )\bORAL\b", "VO", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


def _tokens(texto):
    return _normalizar(texto).split()


def _assinatura_sku(texto):
    texto = _normalizar(texto)
    texto = re.sub(r"\bSKU PENDENTE\b\s*-?\s*", "", texto)
    texto = re.sub(r"\b(AP|FR|CX|C/|COM|UN|UND|PC|L|LT|VAL|VALIDADE|LOTE)\b.*$", "", texto)
    texto = re.sub(r"\b\d{4,}\b", "", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    palavras = texto.split()
    return " ".join(palavras[:8])


def _motivos_sku(produto_padrao, descricoes_originais):
    texto = _normalizar(produto_padrao)
    palavras = texto.split()
    motivos = []

    if texto.startswith("SKU PENDENTE"):
        motivos.append("sku_pendente")

    if len(palavras) > 8:
        motivos.append("excesso_tokens")

    if len(texto) > 55:
        motivos.append("muito_longo")

    if len(palavras) >= 4:
        metade = max(2, len(palavras) // 2)
        inicio = " ".join(palavras[:metade])
        restante = " ".join(palavras[metade:])
        if inicio and inicio in restante:
            motivos.append("repeticao_termo_base")
        prefixo_curto = " ".join(palavras[:2])
        prefixo_medio = " ".join(palavras[:3])
        restante_curto = " ".join(palavras[2:])
        if prefixo_curto and prefixo_curto in restante_curto:
            motivos.append("repeticao_termo_base")
        if prefixo_medio and prefixo_medio in restante:
            motivos.append("repeticao_termo_base")

    if re.search(r"\bAP\s+[A-Z0-9]+$", texto):
        marca_final = palavras[-1] if palavras else ""
        if marca_final in MARCAS_FINAIS_SUSPEITAS or len(marca_final) >= 4:
            motivos.append("marca_fabricante_no_fim")

    for descricao in descricoes_originais:
        if _normalizar(descricao) == texto:
            motivos.append("igual_descricao_original")
            break

    return sorted(set(motivos))


def _classificar(produto, motivos, duplicado):
    if duplicado:
        return "DUPLICADO"
    if "sku_pendente" in motivos:
        return "SKU_PENDENTE"
    motivos_fortes = {
        "excesso_tokens", "muito_longo", "repeticao_termo_base", "marca_fabricante_no_fim",
    }
    if motivos_fortes.intersection(motivos):
        return "CONTAMINADO_FORTE"
    if motivos:
        return "SUSPEITO"
    return "LIMPO"


def _sugerir_sku_limpo(produto, indice_limpos):
    assinatura = _assinatura_sku(produto.get("produto_padrao"))
    if not assinatura:
        return ""

    chave = assinatura.split()[0] if assinatura.split() else ""
    produtos_limpos = indice_limpos.get(chave, [])
    if not produtos_limpos:
        return ""

    candidatos = []
    for limpo in produtos_limpos:
        if limpo["id"] == produto["id"]:
            continue
        if not assinatura or not limpo["assinatura"]:
            continue
        score = fuzz.token_set_ratio(assinatura, limpo["assinatura"])
        if score >= 92:
            candidatos.append((score, len(_tokens(limpo["produto_padrao"])), limpo["produto_padrao"]))

    if not candidatos:
        return ""

    candidatos.sort(key=lambda item: (-item[0], item[1], item[2]))
    return candidatos[0][2]


def gerar_auditoria_sku_master(filtro="todos", limite=None, q="", pagina=1, itens_por_pagina=50):
    filtro = filtro if filtro in FILTROS else "todos"
    pagina = max(1, int(pagina or 1))
    itens_por_pagina = int(itens_por_pagina or 50)

    conn = _conectar_leitura()
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()

        # Filtro de busca textual expandido
        where_clause = "WHERE p.ativo = 1"
        params = []
        if q:
            termos = q.strip().split()
            for t in termos:
                where_clause += " AND (p.produto_padrao LIKE ? OR p.sku_master LIKE ? OR p.fabricante LIKE ? OR p.categoria LIKE ? OR p.id IN (SELECT produto_id FROM precos_fornecedores WHERE descricao_original LIKE ?))"
                like_val = f"%{t}%"
                params.extend([like_val, like_val, like_val, like_val, like_val])

        cursor.execute(
            f"""
            SELECT p.id, p.sku, p.produto_padrao, p.sku_master, p.fabricante, p.categoria, p.ativo, p.observacoes
            FROM produtos p
            {where_clause}
            ORDER BY p.produto_padrao
            """,
            params
        )
        produtos = [dict(row) for row in cursor.fetchall()]

        cursor.execute("SELECT produto_id, descricao_original FROM precos_fornecedores")
        descricoes_por_produto = defaultdict(list)
        total_precos = defaultdict(int)
        for row in cursor.fetchall():
            produto_id = row["produto_id"]
            total_precos[produto_id] += 1
            if row["descricao_original"]:
                descricoes_por_produto[produto_id].append(row["descricao_original"])

        cursor.execute(
            "SELECT produto_id, COUNT(*) AS total FROM equivalencias GROUP BY produto_id"
        )
        total_equivalencias = {row["produto_id"]: row["total"] for row in cursor.fetchall()}
    finally:
        conn.close()

    grupos_normalizados = defaultdict(list)
    for produto in produtos:
        chave = _normalizar(produto.get("sku_master") or produto.get("produto_padrao"))
        if chave:
            grupos_normalizados[chave].append(produto["id"])

    ids_duplicados = {
        produto_id
        for ids in grupos_normalizados.values()
        if len(ids) > 1
        for produto_id in ids
    }
    total_grupos_duplicados = sum(1 for ids in grupos_normalizados.values() if len(ids) > 1)

    pre_classificados = []
    for produto in produtos:
        motivos = _motivos_sku(
            produto.get("sku_master") or produto.get("produto_padrao"),
            descricoes_por_produto.get(produto["id"], []),
        )
        duplicado = produto["id"] in ids_duplicados
        classificacao = _classificar(produto, motivos, duplicado)
        pre_classificados.append({
            **produto,
            "classificacao": classificacao,
            "motivo": ", ".join(motivos) if motivos else "-",
            "motivos_lista": motivos,
            "total_precos": total_precos.get(produto["id"], 0),
            "total_equivalencias": total_equivalencias.get(produto["id"], 0),
            "sugestao_sku_limpo": "",
        })

    produtos_limpos = [
        {**item, "assinatura": _assinatura_sku(item.get("sku_master") or item["produto_padrao"])}
        for item in pre_classificados
        if item["classificacao"] == "LIMPO"
    ]
    indice_limpos = defaultdict(list)
    for item in produtos_limpos:
        chave = item["assinatura"].split()[0] if item["assinatura"].split() else ""
        if chave:
            indice_limpos[chave].append(item)

    itens = pre_classificados
    contadores = {classificacao: 0 for classificacao in CLASSIFICACOES}
    for item in itens:
        contadores[item["classificacao"]] += 1

    classificacao_filtro = FILTROS[filtro]
    itens_filtrados = [
        item for item in itens
        if not classificacao_filtro or item["classificacao"] == classificacao_filtro
    ]

    total_filtrado = len(itens_filtrados)
    total_paginas = max(1, (total_filtrado + itens_por_pagina - 1) // itens_por_pagina)

    if limite:
        itens_limitados = itens_filtrados[:limite]
    else:
        inicio = (pagina - 1) * itens_por_pagina
        fim = inicio + itens_por_pagina
        itens_limitados = itens_filtrados[inicio:fim]

    for item in itens_limitados:
        if item["classificacao"] != "LIMPO":
            item["sugestao_sku_limpo"] = _sugerir_sku_limpo(item, indice_limpos)

    return {
        "filtro": filtro,
        "q": q,
        "pagina": pagina,
        "total_paginas": total_paginas,
        "itens_por_pagina": itens_por_pagina,
        "contadores": {
            "total_produtos": len(produtos),
            "total_limpos": contadores["LIMPO"],
            "total_suspeitos": contadores["SUSPEITO"],
            "total_contaminados_fortes": contadores["CONTAMINADO_FORTE"],
            "total_sku_pendente": contadores["SKU_PENDENTE"],
            "total_duplicados": contadores["DUPLICADO"],
            "total_grupos_duplicados": total_grupos_duplicados,
            "total_filtrado": total_filtrado,
        },
        "itens": itens_limitados,
        "total_sem_limite": total_filtrado,
    }


def gerar_csv_auditoria_sku_master(filtro="todos", q=""):
    auditoria = gerar_auditoria_sku_master(filtro=filtro, limite=1000000, q=q)
    buffer = io.StringIO()
    campos = [
        "produto_id", "produto_padrao", "sku_master", "fabricante", "categoria",
        "classificacao", "motivo", "sugestao_sku_limpo", "total_precos", "total_equivalencias",
    ]
    writer = csv.DictWriter(buffer, fieldnames=campos, extrasaction="ignore")
    writer.writeheader()
    for item in auditoria["itens"]:
        writer.writerow({
            "produto_id": item["id"],
            "produto_padrao": item["produto_padrao"],
            "sku_master": item.get("sku_master"),
            "fabricante": item["fabricante"],
            "categoria": item["categoria"],
            "classificacao": item["classificacao"],
            "motivo": item["motivo"],
            "sugestao_sku_limpo": item["sugestao_sku_limpo"],
            "total_precos": item["total_precos"],
            "total_equivalencias": item["total_equivalencias"],
        })
    return buffer.getvalue()


def _grupo_sugestao(produto_padrao):
    texto = _normalizar(produto_padrao)
    if "SORO FISIOLOGICO" in texto or "CLORETO DE SODIO 0,9" in texto or "CLORETO DE SODIO 3" in texto or "CLORETO DE SODIO 20" in texto:
        return "soro_fisiologico"
    if "SORO GLICOSADO" in texto or "GLICOSE 5%" in texto or "GLICOSE 10%" in texto or "GLICOSE 25%" in texto or "GLICOSE 50%" in texto or "DEXTROSE" in texto:
        return "soro_glicosado"
    if "RINGER" in texto and "LACTATO" in texto:
        return "soro_fisiologico"
    if "ONDANSETRONA" in texto:
        return "ondansetrona"
    if "DIPIRONA" in texto:
        return "dipirona"
    if "AGULHA" in texto:
        return "agulha"
    return "outros"


def _extrair_percentual(texto, valores=None):
    valores = valores or ("0,9", "3", "5", "10", "20", "25", "50")
    texto = _normalizar(texto)
    for valor in valores:
        padrao = valor.replace(",", r"[,\.]")
        if re.search(rf"\b{padrao}\s*%", texto):
            return f"{valor}%"
    return ""


def _extrair_volume(texto):
    match = re.search(r"\b(\d+(?:[,.]\d+)?)\s*ML\b", _normalizar(texto))
    if not match:
        return ""
    volume = match.group(1).replace(",", ".")
    if volume.endswith(".0"):
        volume = volume[:-2]
    return f"{volume}ML"


def _extrair_dose_ondansetrona(texto):
    texto = _normalizar(texto)
    match = re.search(r"\b(\d+(?:[,.]\d+)?)\s*MG\s*/?\s*(\d+(?:[,.]\d+)?)?\s*ML\b", texto)
    if match:
        mg = match.group(1).replace(",", ".")
        ml = match.group(2)
        if ml:
            ml = ml.replace(",", ".")
            return f"{mg}MG/{ml}ML"
        return f"{mg}MG"
    match = re.search(r"\b(\d+(?:[,.]\d+)?)\s*MG\b", texto)
    if match:
        return f"{match.group(1).replace(',', '.')}MG"
    return ""


def sugerir_sku_medbox_oficial(descricao):
    texto = _normalizar(descricao)

    if "ONDANSETRONA" in texto:
        dose = _extrair_dose_ondansetrona(texto)
        partes = ["ONDANSETRONA"]
        if dose:
            partes.append(dose)
        return aplicar_abreviacoes_medbox(" ".join(partes)), 94 if dose else 86

    if "RINGER" in texto:
        volume = _extrair_volume(texto)
        if "LACTATO" in texto:
            partes = ["SORO RINGER COM LACTATO"]
        elif "SIMPLES" in texto:
            partes = ["SORO RINGER"]
        else:
            partes = []
        if partes:
            if volume:
                partes.append(volume)
            return aplicar_abreviacoes_medbox(" ".join(partes)), 94 if volume else 88

    if "GLICOSE" in texto or "SORO GLICOSADO" in texto or "DEXTROSE" in texto:
        percentual = _extrair_percentual(texto, ("5", "10", "25", "50"))
        volume = _extrair_volume(texto)
        if percentual:
            partes = ["SORO GLICOSADO", percentual]
            if volume:
                partes.append(volume)
            return aplicar_abreviacoes_medbox(" ".join(partes)), 94 if volume else 88

    if "CLORETO DE SODIO" in texto or "SORO FISIOLOGICO" in texto:
        percentual = _extrair_percentual(texto, ("0,9", "3", "20"))
        volume = _extrair_volume(texto)
        if percentual:
            partes = ["SORO FISIOLOGICO", percentual]
            if volume:
                partes.append(volume)
            return aplicar_abreviacoes_medbox(" ".join(partes)), 94 if volume else 88

    return "", 0


def _sugestao_dicionario_medbox(produto_padrao):
    return sugerir_sku_medbox_oficial(produto_padrao)


def _buscar_sku_existente_exato(sku_sugerido, limpos):
    sku_norm = _normalizar(sku_sugerido)
    if not sku_norm:
        return "", None, 0

    candidatos = []
    for item in limpos:
        produto_norm = _normalizar(item["produto_padrao"])
        if produto_norm == sku_norm:
            candidatos.append((100.0, len(_tokens(item["produto_padrao"])), item["produto_padrao"], item["id"]))

    if not candidatos:
        return "", None, 0

    candidatos.sort(key=lambda item: (-item[0], item[1], item[2]))
    melhor = candidatos[0]
    return melhor[2], melhor[3], round(float(melhor[0]), 2)


def _limpar_por_regex(produto_padrao):
    texto = _normalizar(produto_padrao)
    texto = re.sub(r"^SKU PENDENTE\s*-\s*", "", texto)
    texto = re.sub(r"^\d{3,}\s+", "", texto)
    texto = re.sub(r"\b(CX|CAIXA)\b.*$", "", texto)
    texto = re.sub(r"\b(AP|FR|FA|BO|BOLSA|CP|COMPRIMIDO|UN)\b\s+[A-Z0-9].*$", "", texto)
    texto = re.sub(r"\b(LOTE|LT|VAL|VALIDADE|PAGINA)\b.*$", "", texto)
    texto = re.sub(r"\s+", " ", texto).strip(" -,.")

    palavras = texto.split()
    for tamanho in range(2, min(6, len(palavras) // 2 + 1)):
        inicio = " ".join(palavras[:tamanho])
        restante = " ".join(palavras[tamanho:])
        if inicio and inicio in restante:
            texto = inicio
            break

    return texto[:90].strip()


def _tokens_sugestao(texto):
    return [
        token for token in _normalizar(texto).split()
        if token not in STOPWORDS_SKU and not re.fullmatch(r"\d{4,}", token)
    ]


def _montar_indice_limpos(itens):
    limpos = [
        {**item, "assinatura": _assinatura_sku(item["produto_padrao"])}
        for item in itens
        if item["classificacao"] == "LIMPO"
    ]
    indice = defaultdict(list)
    for posicao, item in enumerate(limpos):
        for token in set(_tokens_sugestao(item["produto_padrao"])):
            indice[token].append(posicao)
    return limpos, indice


def _buscar_sku_existente(item, limpos, indice_limpos, sugestao_dicionario=""):
    termos = set(_tokens_sugestao(item["produto_padrao"]))
    if sugestao_dicionario:
        termos.update(_tokens_sugestao(sugestao_dicionario))

    candidatos_ids = set()
    for termo in termos:
        candidatos_ids.update(indice_limpos.get(termo, []))

    melhor = None
    texto_atual = item["produto_padrao"]
    assinatura_atual = _assinatura_sku(texto_atual)
    referencia = sugestao_dicionario or texto_atual
    concentracoes_atual = set(re.findall(r"\b\d+(?:[,.]\d+)?\s*(?:MG|ML|G|MCG|UI|%)\b", _normalizar(referencia)))

    for posicao in candidatos_ids:
        candidato = limpos[posicao]
        concentracoes_candidato = set(
            re.findall(r"\b\d+(?:[,.]\d+)?\s*(?:MG|ML|G|MCG|UI|%)\b", _normalizar(candidato["produto_padrao"]))
        )
        s1 = fuzz.token_set_ratio(assinatura_atual, candidato["assinatura"]) if assinatura_atual and candidato["assinatura"] else 0
        s2 = fuzz.token_set_ratio(referencia, candidato["produto_padrao"]) if referencia and candidato["produto_padrao"] else 0
        score = max(s1, s2)
        if concentracoes_atual and concentracoes_candidato and not (concentracoes_atual & concentracoes_candidato):
            score -= 18

        registro = (score, len(_tokens(candidato["produto_padrao"])), candidato["produto_padrao"], candidato["id"])
        if not melhor or registro[0] > melhor[0] or (registro[0] == melhor[0] and registro[1] < melhor[1]):
            melhor = registro

    if melhor and melhor[0] >= 92:
        return melhor[2], melhor[3], "existente", round(float(melhor[0]), 2)

    return "", None, "", 0


def _sugerir_sku_assistido(item, limpos, indice_limpos):
    sugestao_dicionario, confianca_dicionario = _sugestao_dicionario_medbox(item["produto_padrao"])
    if sugestao_dicionario:
        sku_existente_oficial, produto_destino_id, confianca_existente = _buscar_sku_existente_exato(
            sugestao_dicionario, limpos,
        )
        if sku_existente_oficial:
            return sku_existente_oficial, produto_destino_id, "existente", confianca_existente
        return sugestao_dicionario, None, "dicionario_medbox", confianca_dicionario

    sku_existente, produto_destino_id, origem, confianca = _buscar_sku_existente(item, limpos, indice_limpos)
    if sku_existente:
        return sku_existente, produto_destino_id, origem, confianca

    sugestao_regex = _limpar_por_regex(item["produto_padrao"])
    if sugestao_regex and sugestao_regex != _normalizar(item["produto_padrao"]):
        return sugestao_regex, None, "regex", 70

    return "", None, "revisao", 0


def gerar_sugestoes_sku_master(grupo="todos", limite=250):
    grupo = grupo if grupo in GRUPOS_SUGESTOES else "todos"
    limite = max(1, int(limite or 250))
    auditoria = gerar_auditoria_sku_master(filtro="todos", limite=1000000)
    itens = auditoria["itens"]
    limpos, indice_limpos = _montar_indice_limpos(itens)

    sugestoes = []
    for item in itens:
        if item["classificacao"] not in ("CONTAMINADO_FORTE", "SKU_PENDENTE"):
            continue

        grupo_item = _grupo_sugestao(item["produto_padrao"])
        if grupo != "todos" and grupo_item != grupo:
            continue

        sku_sugerido, produto_destino_id, origem, confianca = _sugerir_sku_assistido(item, limpos, indice_limpos)
        sugestoes.append({
            "produto_id": item["id"],
            "produto_destino_id": produto_destino_id,
            "produto_padrao": item["produto_padrao"],
            "fabricante": item["fabricante"],
            "motivo": item["motivo"],
            "classificacao": item["classificacao"],
            "grupo": grupo_item,
            "sku_sugerido": sku_sugerido,
            "origem_sugestao": origem,
            "confianca": confianca,
            "total_precos": item["total_precos"],
            "total_equivalencias": item["total_equivalencias"],
        })

    contadores = {
        "total": len(sugestoes),
        "existente": sum(1 for item in sugestoes if item["origem_sugestao"] == "existente"),
        "dicionario": sum(1 for item in sugestoes if item["origem_sugestao"] in ("dicionario", "dicionario_medbox")),
        "dicionario_medbox": sum(1 for item in sugestoes if item["origem_sugestao"] == "dicionario_medbox"),
        "regex": sum(1 for item in sugestoes if item["origem_sugestao"] == "regex"),
        "revisao": sum(1 for item in sugestoes if item["origem_sugestao"] == "revisao"),
    }

    sugestoes.sort(key=lambda item: (
        item["origem_sugestao"] == "revisao",
        -item["confianca"],
        item["grupo"],
        item["produto_padrao"],
    ))

    return {
        "grupo": grupo,
        "contadores": contadores,
        "itens": sugestoes[:limite],
        "total_sem_limite": len(sugestoes),
    }


def gerar_csv_sugestoes_sku_master(grupo="todos"):
    sugestoes = gerar_sugestoes_sku_master(grupo=grupo, limite=1000000)
    buffer = io.StringIO()
    campos = [
        "produto_id", "produto_destino_id", "produto_padrao", "fabricante",
        "motivo", "classificacao", "grupo", "sku_sugerido", "origem_sugestao",
        "confianca", "total_precos", "total_equivalencias",
    ]
    writer = csv.DictWriter(buffer, fieldnames=campos, extrasaction="ignore")
    writer.writeheader()
    for item in sugestoes["itens"]:
        writer.writerow(item)
    return buffer.getvalue()


def _conectar_escrita(caminho_banco=None):
    caminho = Path(caminho_banco or CAMINHO_BANCO)
    conn = sqlite3.connect(caminho)
    conn.row_factory = sqlite3.Row
    return conn


def _buscar_produto(cursor, produto_id):
    cursor.execute(
        """
        SELECT id, sku, produto_padrao, sku_master, fabricante, categoria, ativo, observacoes
        FROM produtos
        WHERE id = ?
        """,
        (produto_id,),
    )
    row = cursor.fetchone()
    return dict(row) if row else None


def _classificar_produto_no_banco(cursor, produto):
    cursor.execute(
        "SELECT descricao_original FROM precos_fornecedores WHERE produto_id = ?",
        (produto["id"],),
    )
    descricoes = [row["descricao_original"] for row in cursor.fetchall()]

    cursor.execute(
        """
        SELECT produto_padrao, COUNT(*) AS total
        FROM produtos
        WHERE UPPER(TRIM(produto_padrao)) = UPPER(TRIM(?))
        GROUP BY UPPER(TRIM(produto_padrao))
        """,
        (produto["produto_padrao"],),
    )
    row = cursor.fetchone()
    duplicado = bool(row and row["total"] > 1)
    motivos = _motivos_sku(produto.get("produto_padrao"), descricoes)
    return _classificar(produto, motivos, duplicado), motivos


def _validar_correcao_sku_com_cursor(cursor, produto_origem_id, produto_destino_id, sku_sugerido, origem_sugestao):
    if origem_sugestao != "existente":
        raise ValueError("Somente sugestoes com origem_sugestao = existente podem ser aplicadas.")

    produto_origem_id = int(produto_origem_id)
    produto_destino_id = int(produto_destino_id)
    sku_sugerido = str(sku_sugerido or "").strip()

    if produto_origem_id == produto_destino_id:
        raise ValueError("Produto origem e destino nao podem ser iguais.")

    origem = _buscar_produto(cursor, produto_origem_id)
    destino = _buscar_produto(cursor, produto_destino_id)

    if not origem:
        raise ValueError("Produto origem nao encontrado.")
    if not destino:
        raise ValueError("Produto destino nao encontrado.")
    if int(origem.get("ativo") or 0) != 1:
        raise ValueError("Produto origem precisa estar ativo.")
    if int(destino.get("ativo") or 0) != 1:
        raise ValueError("Produto destino precisa estar ativo.")
    if _normalizar(destino.get("produto_padrao")) != _normalizar(sku_sugerido):
        raise ValueError("SKU sugerido nao confere com o produto destino.")

    classificacao_origem, motivos_origem = _classificar_produto_no_banco(cursor, origem)
    classificacao_destino, motivos_destino = _classificar_produto_no_banco(cursor, destino)

    cursor.execute("SELECT COUNT(*) AS total FROM precos_fornecedores WHERE produto_id = ?", (produto_origem_id,))
    total_precos = cursor.fetchone()["total"]
    cursor.execute("SELECT COUNT(*) AS total FROM equivalencias WHERE produto_id = ?", (produto_origem_id,))
    total_equivalencias = cursor.fetchone()["total"]

    return {
        "origem": origem,
        "destino": destino,
        "classificacao_origem": classificacao_origem,
        "classificacao_destino": classificacao_destino,
        "motivos_origem": motivos_origem,
        "motivos_destino": motivos_destino,
        "total_precos_origem": total_precos,
        "total_equivalencias_origem": total_equivalencias,
        "sku_sugerido": sku_sugerido,
        "origem_sugestao": origem_sugestao,
    }


def validar_correcao_sku(produto_origem_id, produto_destino_id, sku_sugerido, origem_sugestao, caminho_banco=None):
    conn = _conectar_escrita(caminho_banco)
    try:
        cursor = conn.cursor()
        return _validar_correcao_sku_com_cursor(cursor, produto_origem_id, produto_destino_id, sku_sugerido, origem_sugestao)
    finally:
        conn.close()


def criar_backup_banco(caminho_banco=None, pasta_backups=None):
    origem = Path(caminho_banco or CAMINHO_BANCO)
    destino_dir = Path(pasta_backups or PASTA_BACKUPS)
    destino_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    destino = destino_dir / f"{origem.stem}_backup_sku_master_{timestamp}{origem.suffix}"
    shutil.copy2(origem, destino)
    if not destino.exists() or destino.stat().st_size == 0:
        raise RuntimeError("Backup do banco nao foi criado corretamente.")
    return str(destino)


def registrar_log_correcao(registro, caminho_log=None):
    destino = Path(caminho_log or CAMINHO_LOG_CORRECOES)
    destino.parent.mkdir(parents=True, exist_ok=True)
    with destino.open("a", encoding="utf-8") as arquivo:
        arquivo.write(json.dumps(registro, ensure_ascii=False, sort_keys=True) + "\n")
    return str(destino)


def _normalizar_item_lote(item):
    return {
        "produto_origem_id": int(item.get("produto_origem_id") or item.get("produto_id")),
        "produto_destino_id": int(item.get("produto_destino_id")),
        "sku_sugerido": str(item.get("sku_sugerido") or "").strip(),
        "origem_sugestao": str(item.get("origem_sugestao") or "").strip(),
    }


def _validar_tamanho_lote(itens):
    if not itens:
        raise ValueError("Selecione pelo menos uma correcao para o lote.")
    if len(itens) > 10:
        raise ValueError("O lote pode ter no maximo 10 itens.")


def previsualizar_lote_correcoes_sku_master(itens, caminho_banco=None):
    itens_normalizados = [_normalizar_item_lote(item) for item in itens]
    _validar_tamanho_lote(itens_normalizados)

    conn = _conectar_escrita(caminho_banco)
    try:
        cursor = conn.cursor()
        itens_preview = []
        pares_origem = set()
        for item in itens_normalizados:
            if item["produto_origem_id"] in pares_origem:
                raise ValueError("O mesmo produto origem nao pode aparecer mais de uma vez no lote.")
            pares_origem.add(item["produto_origem_id"])

            validacao = _validar_correcao_sku_com_cursor(
                cursor,
                item["produto_origem_id"],
                item["produto_destino_id"],
                item["sku_sugerido"],
                item["origem_sugestao"],
            )
            itens_preview.append({
                **item,
                "produto_origem_nome": validacao["origem"]["produto_padrao"],
                "produto_destino_nome": validacao["destino"]["produto_padrao"],
                "classificacao_origem": validacao["classificacao_origem"],
                "classificacao_destino": validacao["classificacao_destino"],
                "precos_migrar": validacao["total_precos_origem"],
                "equivalencias_migrar": validacao["total_equivalencias_origem"],
            })

        return {
            "total_itens": len(itens_preview),
            "total_precos_migrar": sum(item["precos_migrar"] for item in itens_preview),
            "total_equivalencias_migrar": sum(item["equivalencias_migrar"] for item in itens_preview),
            "itens": itens_preview,
        }
    finally:
        conn.close()


def _aplicar_item_validado(cursor, item):
    produto_origem_id = item["produto_origem_id"]
    produto_destino_id = item["produto_destino_id"]

    cursor.execute(
        "UPDATE precos_fornecedores SET produto_id = ? WHERE produto_id = ?",
        (produto_destino_id, produto_origem_id),
    )
    precos_migrados = cursor.rowcount

    cursor.execute(
        "UPDATE equivalencias SET produto_id = ? WHERE produto_id = ?",
        (produto_destino_id, produto_origem_id),
    )
    equivalencias_migradas = cursor.rowcount

    cursor.execute("UPDATE produtos SET ativo = 0 WHERE id = ?", (produto_origem_id,))
    produtos_inativados = cursor.rowcount
    if produtos_inativados != 1:
        raise RuntimeError("Produto origem nao foi inativado corretamente.")

    return {
        "precos_migrados": precos_migrados,
        "equivalencias_migradas": equivalencias_migradas,
        "produtos_inativados": produtos_inativados,
    }


def _normalizar_sku_manual(sku_manual):
    sku = aplicar_abreviacoes_medbox(sku_manual)
    if not sku:
        raise ValueError("SKU Master manual nao pode estar vazio.")
    if len(sku) < 3:
        raise ValueError("SKU Master manual precisa ter pelo menos 3 caracteres.")
    if sku.startswith("SKU PENDENTE"):
        raise ValueError("SKU Master manual nao pode comecar com SKU PENDENTE.")
    return sku


def _buscar_produto_ativo_por_nome(cursor, sku_master):
    cursor.execute(
        """
        SELECT id, sku, produto_padrao, sku_master, fabricante, categoria, ativo
        FROM produtos
        WHERE ativo = 1
          AND (UPPER(TRIM(sku_master)) = UPPER(TRIM(?)) OR (sku_master IS NULL AND UPPER(TRIM(produto_padrao)) = UPPER(TRIM(?))))
        ORDER BY id
        LIMIT 1
        """,
        (sku_master, sku_master),
    )
    row = cursor.fetchone()
    return dict(row) if row else None


def _criar_produto_manual(cursor, sku_manual, origem):
    categoria = origem.get("categoria") or ""
    if "SKU PENDENTE" in _normalizar(categoria):
        categoria = ""
    # Ao criar manual, o produto_padrao e sku_master começam iguais
    cursor.execute(
        """
        INSERT INTO produtos (sku, produto_padrao, sku_master, fabricante, categoria, ativo)
        VALUES (?, ?, ?, ?, ?, 1)
        """,
        ("", sku_manual, sku_manual, origem.get("fabricante") or "", categoria),
    )
    produto_id = cursor.lastrowid
    return {
        "id": produto_id,
        "sku": "",
        "produto_padrao": sku_manual,
        "sku_master": sku_manual,
        "fabricante": origem.get("fabricante") or "",
        "categoria": categoria,
        "ativo": 1,
    }


def aplicar_correcao_manual_sku_master(
    produto_origem_id,
    sku_manual,
    usuario="compras",
    caminho_banco=None,
    pasta_backups=None,
    caminho_log=None,
):
    produto_origem_id = int(produto_origem_id)
    sku_manual = _normalizar_sku_manual(sku_manual)
    backup = ""

    conn = _conectar_escrita(caminho_banco)
    destino_criado = False
    try:
        cursor = conn.cursor()
        origem = _buscar_produto(cursor, produto_origem_id)
        if not origem:
            raise ValueError("Produto origem nao encontrado.")
        if int(origem.get("ativo") or 0) != 1:
            raise ValueError("Produto origem precisa estar ativo.")

        classificacao_origem, motivos_origem = _classificar_produto_no_banco(cursor, origem)

        destino = _buscar_produto_ativo_por_nome(cursor, sku_manual)

        backup = criar_backup_banco(caminho_banco=caminho_banco, pasta_backups=pasta_backups)
        conn.execute("BEGIN")
        if destino:
            destino_id = destino["id"]
        else:
            destino = _criar_produto_manual(cursor, sku_manual, origem)
            destino_id = destino["id"]
            destino_criado = True

        if produto_origem_id == destino_id:
            raise ValueError("Produto origem e destino nao podem ser iguais.")

        contadores = _aplicar_item_validado(cursor, {
            "produto_origem_id": produto_origem_id,
            "produto_destino_id": destino_id,
        })

        # Propagação em cascata
        cursor.execute(
            """
            SELECT id, sku, produto_padrao, sku_master, fabricante, categoria, ativo
            FROM produtos
            WHERE ativo = 1 AND id != ? AND id != ?
            """,
            (produto_origem_id, destino_id),
        )
        candidatos = [dict(row) for row in cursor.fetchall()]

        itens_cascata = []
        for cand in candidatos:
            # Compara usando a referência fixa (produto_padrao) para encontrar semelhantes reais
            if not origem.get("produto_padrao") or not cand.get("produto_padrao"):
                continue
            score = fuzz.token_set_ratio(origem["produto_padrao"], cand["produto_padrao"])
            if score >= 88:
                classificacao_cand, _ = _classificar_produto_no_banco(cursor, cand)
                if classificacao_cand in ("CONTAMINADO_FORTE", "SKU_PENDENTE"):
                    contadores_casc = _aplicar_item_validado(cursor, {
                        "produto_origem_id": cand["id"],
                        "produto_destino_id": destino_id,
                    })
                    registro_cascata = {
                        "timestamp": datetime.now().isoformat(timespec="seconds"),
                        "usuario": usuario,
                        "status": "sucesso",
                        "tipo_correcao": "cascata",
                        "produto_origem_id": cand["id"],
                        "produto_origem": cand["produto_padrao"],
                        "produto_destino_id": destino_id,
                        "produto_destino": destino["produto_padrao"],
                        "sku_manual": sku_manual,
                        "precos_migrados": contadores_casc["precos_migrados"],
                        "equivalencias_migradas": contadores_casc["equivalencias_migradas"],
                        "produtos_inativados": contadores_casc["produtos_inativados"],
                    }
                    registrar_log_correcao(registro_cascata, caminho_log=caminho_log)
                    itens_cascata.append({
                        "produto_id": cand["id"],
                        "produto_padrao": cand["produto_padrao"],
                        "precos_migrados": contadores_casc["precos_migrados"],
                    })

        conn.commit()

        registro = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "usuario": usuario,
            "status": "sucesso",
            "tipo_correcao": "manual",
            "produto_origem_id": produto_origem_id,
            "produto_origem": origem["produto_padrao"],
            "produto_destino_id": destino_id,
            "produto_destino": destino["produto_padrao"],
            "sku_manual": sku_manual,
            "destino_criado": destino_criado,
            "classificacao_origem": classificacao_origem,
            "motivos_origem": motivos_origem,
            "precos_migrados": contadores["precos_migrados"],
            "equivalencias_migradas": contadores["equivalencias_migradas"],
            "produtos_inativados": contadores["produtos_inativados"],
            "cascata": itens_cascata,
            "backup": backup,
        }
        caminho_log_final = registrar_log_correcao(registro, caminho_log=caminho_log)
        registro["log"] = caminho_log_final
        return registro
    except Exception as erro:
        conn.rollback()
        if backup:
            registrar_log_correcao({
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "usuario": usuario,
                "status": "erro",
                "tipo_correcao": "manual",
                "produto_origem_id": produto_origem_id,
                "sku_manual": sku_manual,
                "erro": str(erro),
                "backup": backup,
            }, caminho_log=caminho_log)
        raise
    finally:
        conn.close()


def aplicar_correcao_sku_master(
    produto_origem_id,
    produto_destino_id,
    sku_sugerido,
    origem_sugestao,
    usuario="sistema",
    caminho_banco=None,
    pasta_backups=None,
    caminho_log=None,
):
    validacao = validar_correcao_sku(
        produto_origem_id, produto_destino_id, sku_sugerido, origem_sugestao,
        caminho_banco=caminho_banco,
    )
    backup = criar_backup_banco(caminho_banco=caminho_banco, pasta_backups=pasta_backups)

    conn = _conectar_escrita(caminho_banco)
    try:
        cursor = conn.cursor()
        conn.execute("BEGIN")

        contadores = _aplicar_item_validado(cursor, {
            "produto_origem_id": int(produto_origem_id),
            "produto_destino_id": int(produto_destino_id),
        })

        conn.commit()

        registro = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "usuario": usuario,
            "status": "sucesso",
            "produto_origem_id": int(produto_origem_id),
            "produto_origem": validacao["origem"]["produto_padrao"],
            "produto_destino_id": int(produto_destino_id),
            "produto_destino": validacao["destino"]["produto_padrao"],
            "sku_sugerido": sku_sugerido,
            "origem_sugestao": origem_sugestao,
            "classificacao_origem": validacao["classificacao_origem"],
            "classificacao_destino": validacao["classificacao_destino"],
            "precos_migrados": contadores["precos_migrados"],
            "equivalencias_migradas": contadores["equivalencias_migradas"],
            "produtos_inativados": contadores["produtos_inativados"],
            "backup": backup,
        }
        caminho_log_final = registrar_log_correcao(registro, caminho_log=caminho_log)
        registro["log"] = caminho_log_final
        return registro
    except Exception as erro:
        conn.rollback()
        registro = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "usuario": usuario,
            "status": "erro",
            "produto_origem_id": int(produto_origem_id),
            "produto_destino_id": int(produto_destino_id),
            "sku_sugerido": sku_sugerido,
            "origem_sugestao": origem_sugestao,
            "erro": str(erro),
            "backup": backup,
        }
        registrar_log_correcao(registro, caminho_log=caminho_log)
        raise
    finally:
        conn.close()


def registrar_auditoria_sku(
    cursor,
    produto_id,
    campo,
    valor_antigo,
    valor_novo,
    tipo_correcao="manual",
    origem_correcao="auditoria",
    usuario="sistema",
):
    cursor.execute(
        """
        INSERT INTO auditoria_sku (
            produto_id, campo, valor_antigo, valor_novo,
            data_hora, tipo_correcao, origem_correcao, usuario
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            produto_id,
            campo,
            str(valor_antigo or ""),
            str(valor_novo or ""),
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            tipo_correcao,
            origem_correcao,
            usuario,
        ),
    )


def buscar_produtos_afetados_cascata(produto_id, tipo_cascata, sku_master_novo=None, caminho_banco=None):
    conn = _conectar_leitura()
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()
        origem = _buscar_produto(cursor, produto_id)
        if not origem:
            return []

        if tipo_cascata == "mesmo_sku":
            # Agrupa por sku_master atual
            sku_master_atual = origem.get("sku_master") or origem.get("produto_padrao")
            cursor.execute(
                "SELECT id, produto_padrao, sku_master, fabricante, categoria, ativo FROM produtos WHERE (sku_master = ? OR (sku_master IS NULL AND produto_padrao = ?)) AND id != ? AND ativo = 1",
                (sku_master_atual, sku_master_atual, produto_id),
            )
            return [dict(row) for row in cursor.fetchall()]

        if tipo_cascata == "semelhante":
            # Busca semelhantes usando produto_padrao como base de comparação
            cursor.execute("SELECT id, produto_padrao, sku_master, fabricante, categoria, ativo FROM produtos WHERE ativo = 1 AND id != ?", (produto_id,))
            candidatos = [dict(row) for row in cursor.fetchall()]
            afetados = []
            for cand in candidatos:
                if not origem.get("produto_padrao") or not cand.get("produto_padrao"):
                    continue
                score = fuzz.token_set_ratio(origem["produto_padrao"], cand["produto_padrao"])
                if score >= 88:
                    cand["score"] = round(score, 1)
                    afetados.append(cand)
            return afetados

        if tipo_cascata == "mesmo_fornecedor":
            cursor.execute("SELECT DISTINCT fornecedor_id FROM precos_fornecedores WHERE produto_id = ?", (produto_id,))
            fids = [row["fornecedor_id"] for row in cursor.fetchall()]
            if not fids:
                return []
            placeholders = ",".join(["?"] * len(fids))
            cursor.execute(
                f"""
                SELECT DISTINCT p.id, p.produto_padrao, p.sku_master, p.fabricante, p.categoria, p.ativo
                FROM produtos p
                JOIN precos_fornecedores pf ON pf.produto_id = p.id
                WHERE pf.fornecedor_id IN ({placeholders}) AND p.id != ? AND p.ativo = 1
                """,
                (*fids, produto_id),
            )
            return [dict(row) for row in cursor.fetchall()]

        return []
    finally:
        conn.close()


def salvar_edicao_manual_produto(
    produto_id,
    dados_novos,
    opcoes_cascata=None,
    usuario="sistema",
    caminho_banco=None,
    ids_cascata_selecionados=None,
):
    produto_id = int(produto_id)
    opcoes_cascata = opcoes_cascata or []
    ids_afetados = set()
    if ids_cascata_selecionados:
        ids_afetados.update(int(i) for i in ids_cascata_selecionados if int(i) != produto_id)

    criar_backup_banco(caminho_banco=caminho_banco)
    conn = _conectar_escrita(caminho_banco)
    try:
        cursor = conn.cursor()
        origem = _buscar_produto(cursor, produto_id)
        if not origem:
            raise ValueError("Produto nao encontrado.")

        # Se não foram enviados IDs específicos, calculamos baseados nas opções (retrocompatibilidade ou fallback)
        if not ids_cascata_selecionados:
            for tipo in opcoes_cascata:
                if tipo == "mesmo_sku":
                    sku_master_atual = origem.get("sku_master") or origem.get("produto_padrao")
                    cursor.execute("SELECT id FROM produtos WHERE (sku_master = ? OR (sku_master IS NULL AND produto_padrao = ?)) AND id != ? AND ativo = 1", (sku_master_atual, sku_master_atual, produto_id))
                    ids_afetados.update(row[0] for row in cursor.fetchall())
                elif tipo == "semelhante":
                    cursor.execute("SELECT id, produto_padrao, sku_master FROM produtos WHERE ativo = 1 AND id != ?", (produto_id,))
                    for cand in cursor.fetchall():
                        if origem.get("produto_padrao") and cand[1] and fuzz.token_set_ratio(origem["produto_padrao"], cand[1]) >= 88:
                            ids_afetados.add(cand[0])
                elif tipo == "mesmo_fornecedor":
                    cursor.execute("SELECT DISTINCT fornecedor_id FROM precos_fornecedores WHERE produto_id = ?", (produto_id,))
                    fids = [row[0] for row in cursor.fetchall()]
                    if fids:
                        placeholders = ",".join(["?"] * len(fids))
                        cursor.execute(f"SELECT DISTINCT pf.produto_id FROM precos_fornecedores pf JOIN produtos p ON p.id = pf.produto_id WHERE pf.fornecedor_id IN ({placeholders}) AND pf.produto_id != ? AND p.ativo = 1", (*fids, produto_id))
                        ids_afetados.update(row[0] for row in cursor.fetchall())

        conn.execute("BEGIN")

        campos_editaveis = ["sku_master", "fabricante", "categoria", "ativo", "observacoes"]
        for campo in campos_editaveis:
            novo_valor = dados_novos.get(campo)
            if novo_valor is not None and str(novo_valor) != str(origem.get(campo) or ""):
                cursor.execute(f"UPDATE produtos SET {campo} = ? WHERE id = ?", (novo_valor, produto_id))
                registrar_auditoria_sku(cursor, produto_id, campo, origem.get(campo), novo_valor, usuario=usuario)

        sku_novo = dados_novos.get("sku_master")
        fab_novo = dados_novos.get("fabricante")
        cat_novo = dados_novos.get("categoria")

        for aid in ids_afetados:
            afetado = _buscar_produto(cursor, aid)
            if not afetado:
                continue

            # Cascata deve alterar APENAS o que foi alterado no produto de origem e enviado no payload
            if "sku_master" in dados_novos:
                novo_val = dados_novos["sku_master"]
                if novo_val != afetado.get("sku_master"):
                    cursor.execute("UPDATE produtos SET sku_master = ? WHERE id = ?", (novo_val, aid))
                    registrar_auditoria_sku(cursor, aid, "sku_master", afetado.get("sku_master"), novo_val, tipo_correcao="cascata", usuario=usuario)

            if "fabricante" in dados_novos:
                novo_val = dados_novos["fabricante"]
                if novo_val != afetado.get("fabricante"):
                    cursor.execute("UPDATE produtos SET fabricante = ? WHERE id = ?", (novo_val, aid))
                    registrar_auditoria_sku(cursor, aid, "fabricante", afetado.get("fabricante"), novo_val, tipo_correcao="cascata", usuario=usuario)

            if "categoria" in dados_novos:
                novo_val = dados_novos["categoria"]
                if novo_val != afetado.get("categoria"):
                    cursor.execute("UPDATE produtos SET categoria = ? WHERE id = ?", (novo_val, aid))
                    registrar_auditoria_sku(cursor, aid, "categoria", afetado.get("categoria"), novo_val, tipo_correcao="cascata", usuario=usuario)

        conn.commit()
        return {"ok": True, "afetados_cascata": len(ids_afetados)}
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def excluir_produto_logico(produto_id, usuario="sistema", caminho_banco=None):
    produto_id = int(produto_id)
    criar_backup_banco(caminho_banco=caminho_banco)
    conn = _conectar_escrita(caminho_banco)
    try:
        cursor = conn.cursor()
        origem = _buscar_produto(cursor, produto_id)
        if not origem:
            raise ValueError("Produto nao encontrado.")

        conn.execute("BEGIN")

        cursor.execute(
            """
            INSERT INTO precos_fornecedores_historico (
                fornecedor_id, produto_id, descricao_original,
                codigo_fornecedor, marca, preco, data_importacao,
                arquivo_origem, origem_importacao, data_registro
            )
            SELECT
                fornecedor_id, produto_id, descricao_original,
                codigo_fornecedor, marca, preco, data_importacao,
                arquivo_origem, 'PRODUTO_EXCLUIDO', ?
            FROM precos_fornecedores
            WHERE produto_id = ?
            """,
            (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), produto_id),
        )

        cursor.execute("DELETE FROM precos_fornecedores WHERE produto_id = ?", (produto_id,))
        cursor.execute("UPDATE produtos SET ativo = 0 WHERE id = ?", (produto_id,))

        registrar_auditoria_sku(
            cursor, produto_id, "ativo", "1", "0",
            tipo_correcao="exclusao", usuario=usuario
        )

        conn.commit()
        return {"ok": True}
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def aplicar_lote_correcoes_sku_master(
    itens,
    usuario="sistema",
    caminho_banco=None,
    pasta_backups=None,
    caminho_log=None,
):
    preview = previsualizar_lote_correcoes_sku_master(itens, caminho_banco=caminho_banco)
    lote_id = str(uuid.uuid4())
    backup = criar_backup_banco(caminho_banco=caminho_banco, pasta_backups=pasta_backups)
    conn = _conectar_escrita(caminho_banco)
    registros = []
    try:
        cursor = conn.cursor()
        conn.execute("BEGIN")

        for item in preview["itens"]:
            validacao = _validar_correcao_sku_com_cursor(
                cursor,
                item["produto_origem_id"],
                item["produto_destino_id"],
                item["sku_sugerido"],
                item["origem_sugestao"],
            )
            contadores = _aplicar_item_validado(cursor, item)
            registros.append({
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "usuario": usuario,
                "status": "sucesso",
                "lote_id": lote_id,
                "produto_origem_id": item["produto_origem_id"],
                "produto_origem": validacao["origem"]["produto_padrao"],
                "produto_destino_id": item["produto_destino_id"],
                "produto_destino": validacao["destino"]["produto_padrao"],
                "sku_sugerido": item["sku_sugerido"],
                "origem_sugestao": item["origem_sugestao"],
                "classificacao_origem": validacao["classificacao_origem"],
                "classificacao_destino": validacao["classificacao_destino"],
                "precos_migrados": contadores["precos_migrados"],
                "equivalencias_migradas": contadores["equivalencias_migradas"],
                "produtos_inativados": contadores["produtos_inativados"],
                "backup": backup,
            })

        conn.commit()
        caminho_log_final = ""
        for registro in registros:
            caminho_log_final = registrar_log_correcao(registro, caminho_log=caminho_log)
            registro["log"] = caminho_log_final

        return {
            "lote_id": lote_id,
            "backup": backup,
            "log": caminho_log_final,
            "total_itens": len(registros),
            "precos_migrados": sum(item["precos_migrados"] for item in registros),
            "equivalencias_migradas": sum(item["equivalencias_migradas"] for item in registros),
            "produtos_inativados": sum(item["produtos_inativados"] for item in registros),
            "itens": registros,
        }
    except Exception as erro:
        conn.rollback()
        registrar_log_correcao({
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "usuario": usuario,
            "status": "erro",
            "lote_id": lote_id,
            "erro": str(erro),
            "backup": backup,
            "total_itens": len(preview["itens"]),
        }, caminho_log=caminho_log)
        raise
    finally:
        conn.close()