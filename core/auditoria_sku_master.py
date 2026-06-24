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


def _descricao_auditoria(produto):
    """Usa o SKU Master corrigido sem sobrescrever a descricao de referencia."""
    sku_master = produto.get("sku_master")
    if str(sku_master or "").strip():
        return sku_master
    return produto.get("produto_padrao") or ""


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
    assinatura = _assinatura_sku(_descricao_auditoria(produto))
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


def gerar_auditoria_sku_master(filtro="todos", q="", pagina=1, limite=50):
    filtro = filtro if filtro in FILTROS else "todos"
    pagina = max(1, int(pagina or 1))
    limite = max(1, int(limite or 50))
    offset = (pagina - 1) * limite

    conn = _conectar_leitura()
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()

        # Busca base para contagem e filtragem
        where_clauses = ["ativo = 1"]
        params = []

        if q:
            # Pesquisa somente pelos campos de descricao, sem filtrar classificacao.
            where_clauses.append("""(
                produto_padrao LIKE ? OR
                sku_master LIKE ? OR
                id IN (SELECT produto_id FROM precos_fornecedores WHERE descricao_original LIKE ?)
            )""")
            p = f"%{q}%"
            params.extend([p, p, p])

        where_sql = " WHERE " + " AND ".join(where_clauses)

        cursor.execute(
            f"""
            SELECT id, sku, produto_padrao, sku_master, fabricante, categoria, ativo, observacoes
            FROM produtos
            {where_sql}
            ORDER BY id DESC
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
        chave = _normalizar(_descricao_auditoria(produto))
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
            _descricao_auditoria(produto),
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
        {**item, "assinatura": _assinatura_sku(_descricao_auditoria(item))}
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
    total_paginas = (total_filtrado + limite - 1) // limite if total_filtrado > 0 else 1

    itens_paginados = itens_filtrados[offset : offset + limite]

    for item in itens_paginados:
        if item["classificacao"] != "LIMPO":
            item["sugestao_sku_limpo"] = _sugerir_sku_limpo(item, indice_limpos)

    return {
        "filtro": filtro,
        "q": q,
        "pagina": pagina,
        "total_paginas": total_paginas,
        "total": total_filtrado,
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
        "itens": itens_paginados,
        "total_sem_limite": total_filtrado,
    }


def gerar_csv_auditoria_sku_master(filtro="todos", q=""):
    auditoria = gerar_auditoria_sku_master(filtro=filtro, q=q, pagina=1, limite=1000000)
    buffer = io.StringIO()
    campos = [
        "produto_id", "produto_padrao", "fabricante", "categoria",
        "classificacao", "motivo", "sugestao_sku_limpo", "total_precos", "total_equivalencias",
    ]
    writer = csv.DictWriter(buffer, fieldnames=campos, extrasaction="ignore")
    writer.writeheader()
    for item in auditoria["itens"]:
        writer.writerow({
            "produto_id": item["id"],
            "produto_padrao": item["produto_padrao"],
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
    auditoria = gerar_auditoria_sku_master(filtro="todos", pagina=1, limite=1000000)
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
        SELECT COUNT(*) AS total
        FROM produtos
        WHERE ativo = 1
          AND UPPER(TRIM(COALESCE(NULLIF(TRIM(sku_master), ''), produto_padrao))) = UPPER(TRIM(?))
        """,
        (_descricao_auditoria(produto),),
    )
    row = cursor.fetchone()
    duplicado = bool(row and row["total"] > 1)
    motivos = _motivos_sku(_descricao_auditoria(produto), descricoes)
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


def _garantir_colunas_correcao_sku(cursor):
    """
    Colunas leves para rastrear que o SKU já foi tratado.
    Não quebra bancos antigos: adiciona somente se ainda não existir.
    """
    cursor.execute("PRAGMA table_info(produtos)")
    colunas = {row[1] for row in cursor.fetchall()}

    if "sku_corrigido" not in colunas:
        cursor.execute("ALTER TABLE produtos ADD COLUMN sku_corrigido INTEGER DEFAULT 0")

    if "corrigido_em" not in colunas:
        cursor.execute("ALTER TABLE produtos ADD COLUMN corrigido_em TEXT")


def _normalizar_valor_campo(valor):
    return str(valor or "").strip().upper()


def _produto_por_id_para_correcao(cursor, produto_id):
    cursor.execute(
        """
        SELECT id, sku, produto_padrao, sku_master, fabricante, categoria, ativo
        FROM produtos
        WHERE id = ?
        LIMIT 1
        """,
        (produto_id,),
    )
    row = cursor.fetchone()
    return dict(row) if row else None


def _sincronizar_destino_corrigido(cursor, produto_destino_id, origem=None):
    """
    Garante que o produto destino fique com SKU_MASTER, fabricante/categoria,
    marca nos preços e sinalização de corrigido.
    """
    _garantir_colunas_correcao_sku(cursor)

    destino = _produto_por_id_para_correcao(cursor, produto_destino_id)
    if not destino:
        return {
            "precos_marca_atualizados": 0,
            "produto_destino_atualizado": 0,
        }

    origem = origem or {}

    sku_destino = _normalizar_valor_campo(destino.get("sku_master")) or _normalizar_valor_campo(destino.get("produto_padrao"))
    fabricante = _normalizar_valor_campo(destino.get("fabricante")) or _normalizar_valor_campo(origem.get("fabricante"))
    categoria = _normalizar_valor_campo(destino.get("categoria")) or _normalizar_valor_campo(origem.get("categoria"))

    cursor.execute(
        """
        UPDATE produtos
        SET sku_master = COALESCE(NULLIF(?, ''), sku_master),
            fabricante = COALESCE(NULLIF(?, ''), fabricante),
            categoria = COALESCE(NULLIF(?, ''), categoria),
            sku_corrigido = 1,
            corrigido_em = CURRENT_TIMESTAMP,
            ativo = 1
        WHERE id = ?
        """,
        (sku_destino, fabricante, categoria, produto_destino_id),
    )
    produto_destino_atualizado = cursor.rowcount

    # Preenche marca vazia nos preços do produto corrigido.
    precos_marca_atualizados = 0
    if fabricante:
        cursor.execute(
            """
            UPDATE precos_fornecedores
            SET marca = ?
            WHERE produto_id = ?
              AND (marca IS NULL OR TRIM(marca) = '')
            """,
            (fabricante, produto_destino_id),
        )
        precos_marca_atualizados = cursor.rowcount

    return {
        "precos_marca_atualizados": precos_marca_atualizados,
        "produto_destino_atualizado": produto_destino_atualizado,
    }


def _consolidar_produtos_mesmo_sku_master(cursor, produto_destino_id):
    """
    Consolida produtos ativos que já estejam com o mesmo SKU_MASTER do destino.
    Isso evita que a Auditoria continue mostrando duplicatas corrigidas.
    """
    destino = _produto_por_id_para_correcao(cursor, produto_destino_id)
    if not destino:
        return {
            "produtos_consolidados": 0,
            "precos_migrados": 0,
            "equivalencias_migradas": 0,
        }

    sku_destino = _normalizar_valor_campo(destino.get("sku_master")) or _normalizar_valor_campo(destino.get("produto_padrao"))
    if not sku_destino or sku_destino.startswith("SKU PENDENTE"):
        return {
            "produtos_consolidados": 0,
            "precos_migrados": 0,
            "equivalencias_migradas": 0,
        }

    cursor.execute(
        """
        SELECT id
        FROM produtos
        WHERE ativo = 1
          AND id != ?
          AND (
                UPPER(TRIM(COALESCE(sku_master, ''))) = UPPER(TRIM(?))
             OR UPPER(TRIM(COALESCE(produto_padrao, ''))) = UPPER(TRIM(?))
          )
        ORDER BY id
        """,
        (produto_destino_id, sku_destino, sku_destino),
    )
    duplicados = [row["id"] for row in cursor.fetchall()]

    produtos_consolidados = 0
    precos_migrados = 0
    equivalencias_migradas = 0

    for origem_id in duplicados:
        if origem_id == produto_destino_id:
            continue

        cursor.execute(
            "UPDATE precos_fornecedores SET produto_id = ? WHERE produto_id = ?",
            (produto_destino_id, origem_id),
        )
        precos_migrados += cursor.rowcount

        cursor.execute(
            "UPDATE equivalencias SET produto_id = ? WHERE produto_id = ?",
            (produto_destino_id, origem_id),
        )
        equivalencias_migradas += cursor.rowcount

        cursor.execute(
            """
            UPDATE produtos
            SET ativo = 0,
                sku_corrigido = 1,
                corrigido_em = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (origem_id,),
        )
        produtos_consolidados += cursor.rowcount

    _sincronizar_destino_corrigido(cursor, produto_destino_id)

    return {
        "produtos_consolidados": produtos_consolidados,
        "precos_migrados": precos_migrados,
        "equivalencias_migradas": equivalencias_migradas,
    }


def _aplicar_item_validado(cursor, item):
    produto_origem_id = item["produto_origem_id"]
    produto_destino_id = item["produto_destino_id"]

    origem = _produto_por_id_para_correcao(cursor, produto_origem_id)
    destino = _produto_por_id_para_correcao(cursor, produto_destino_id)

    if not origem:
        raise RuntimeError("Produto origem nao encontrado.")
    if not destino:
        raise RuntimeError("Produto destino nao encontrado.")

    # Antes de migrar, garante que o destino herde fabricante/categoria quando estiver vazio.
    _sincronizar_destino_corrigido(cursor, produto_destino_id, origem=origem)

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

    cursor.execute(
        """
        UPDATE produtos
        SET ativo = 0,
            sku_corrigido = 1,
            corrigido_em = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (produto_origem_id,),
    )
    produtos_inativados = cursor.rowcount
    if produtos_inativados != 1:
        raise RuntimeError("Produto origem nao foi inativado corretamente.")

    sync = _sincronizar_destino_corrigido(cursor, produto_destino_id, origem=origem)

    return {
        "precos_migrados": precos_migrados,
        "equivalencias_migradas": equivalencias_migradas,
        "produtos_inativados": produtos_inativados,
        "precos_marca_atualizados": sync.get("precos_marca_atualizados", 0),
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


def _buscar_produto_ativo_por_nome(cursor, produto_padrao):
    cursor.execute(
        """
        SELECT id, sku, produto_padrao, fabricante, categoria, ativo
        FROM produtos
        WHERE ativo = 1
          AND UPPER(TRIM(produto_padrao)) = UPPER(TRIM(?))
        ORDER BY id
        LIMIT 1
        """,
        (produto_padrao,),
    )
    row = cursor.fetchone()
    return dict(row) if row else None


def _criar_produto_manual(cursor, sku_manual, origem):
    categoria = origem.get("categoria") or ""
    if "SKU PENDENTE" in _normalizar(categoria):
        categoria = ""
    cursor.execute(
        """
        INSERT INTO produtos (sku, produto_padrao, fabricante, categoria, ativo)
        VALUES (?, ?, ?, ?, 1)
        """,
        ("", sku_manual, origem.get("fabricante") or "", categoria),
    )
    produto_id = cursor.lastrowid
    return {
        "id": produto_id,
        "sku": "",
        "produto_padrao": sku_manual,
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
            SELECT id, sku, produto_padrao, fabricante, categoria, ativo
            FROM produtos
            WHERE ativo = 1 AND id != ? AND id != ?
            """,
            (produto_origem_id, destino_id),
        )
        candidatos = [dict(row) for row in cursor.fetchall()]

        itens_cascata = []
        for cand in candidatos:
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

        consolidacao_mesmo_sku = _consolidar_produtos_mesmo_sku_master(cursor, destino_id)

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
            "consolidacao_mesmo_sku": consolidacao_mesmo_sku,
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

        consolidacao_mesmo_sku = _consolidar_produtos_mesmo_sku_master(cursor, int(produto_destino_id))

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
            "consolidacao_mesmo_sku": consolidacao_mesmo_sku,
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
            cursor.execute(
                "SELECT id, produto_padrao, ativo FROM produtos WHERE produto_padrao = ? AND id != ?",
                (origem["produto_padrao"], produto_id),
            )
            return [dict(row) for row in cursor.fetchall()]

        if tipo_cascata == "semelhante":
            cursor.execute("SELECT id, produto_padrao, ativo FROM produtos WHERE ativo = 1 AND id != ?", (produto_id,))
            candidatos = [dict(row) for row in cursor.fetchall()]
            afetados = []
            for cand in candidatos:
                if not origem.get("produto_padrao") or not cand.get("produto_padrao"):
                    continue
                score = fuzz.token_set_ratio(origem["produto_padrao"], cand["produto_padrao"])
                if score >= 88:
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
                SELECT DISTINCT p.id, p.produto_padrao, p.ativo
                FROM produtos p
                JOIN precos_fornecedores pf ON pf.produto_id = p.id
                WHERE pf.fornecedor_id IN ({placeholders}) AND p.id != ?
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
    ids_cascata_selecionados=None
):
    produto_id = int(produto_id)
    opcoes_cascata = opcoes_cascata or []

    criar_backup_banco(caminho_banco=caminho_banco)
    conn = _conectar_escrita(caminho_banco)
    try:
        cursor = conn.cursor()
        origem = _buscar_produto(cursor, produto_id)
        if not origem:
            raise ValueError("Produto nao encontrado.")

        ids_afetados = set()
        if ids_cascata_selecionados is not None:
            # Respeita exatamente a lista enviada pelo frontend
            ids_afetados = set(int(x) for x in ids_cascata_selecionados)
        elif opcoes_cascata:
            # Fallback por retrocompatibilidade: recalcula IDs
            for tipo in opcoes_cascata:
                if tipo == "mesmo_sku":
                    cursor.execute("SELECT id FROM produtos WHERE produto_padrao = ? AND id != ?", (origem["produto_padrao"], produto_id))
                    ids_afetados.update(row[0] for row in cursor.fetchall())
                elif tipo == "semelhante":
                    cursor.execute("SELECT id, produto_padrao FROM produtos WHERE ativo = 1 AND id != ?", (produto_id,))
                    for cand in cursor.fetchall():
                        if origem.get("produto_padrao") and cand[1] and fuzz.token_set_ratio(origem["produto_padrao"], cand[1]) >= 88:
                            ids_afetados.add(cand[0])
                elif tipo == "mesmo_fornecedor":
                    cursor.execute("SELECT DISTINCT fornecedor_id FROM precos_fornecedores WHERE produto_id = ?", (produto_id,))
                    fids = [row[0] for row in cursor.fetchall()]
                    if fids:
                        placeholders = ",".join(["?"] * len(fids))
                        cursor.execute(f"SELECT DISTINCT produto_id FROM precos_fornecedores WHERE fornecedor_id IN ({placeholders}) AND produto_id != ?", (*fids, produto_id))
                        ids_afetados.update(row[0] for row in cursor.fetchall())

        conn.execute("BEGIN")

        # produto_padrao é estritamente somente leitura (referência de sistema).
        # sku_master é o campo editável principal para correções.
        campos_editaveis = ["sku_master", "fabricante", "categoria", "ativo", "observacoes"]
        for campo in campos_editaveis:
            novo_valor = dados_novos.get(campo)
            if novo_valor is not None and str(novo_valor) != str(origem.get(campo) or ""):
                cursor.execute(f"UPDATE produtos SET {campo} = ? WHERE id = ?", (novo_valor, produto_id))
                registrar_auditoria_sku(cursor, produto_id, campo, origem.get(campo), novo_valor, usuario=usuario)

        # Cascata: aplica apenas os campos que foram realmente alterados
        for aid in ids_afetados:
            afetado = _buscar_produto(cursor, aid)
            if not afetado: continue

            for campo in ["sku_master", "fabricante", "categoria"]:
                if campo in dados_novos:
                    val = dados_novos[campo]
                    if val is not None and str(val) != str(afetado.get(campo) or ""):
                        cursor.execute(f"UPDATE produtos SET {campo} = ? WHERE id = ?", (val, aid))
                        registrar_auditoria_sku(cursor, aid, campo, afetado.get(campo), val, tipo_correcao="cascata", usuario=usuario)

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



# ============================================================
# PATCH CASCATA RÍGIDA POR ESPECIFICAÇÃO - AUDITORIA SKU MASTER
# Evita que produtos parecidos, mas com tamanho/dosagem/material/tipo
# diferentes, sejam atualizados no mesmo SKU_MASTER.
# Ex.: TUBO OROTRAQUEAL C/BALAO 8,5MM não pode puxar 7,0MM,
# 7,5MM, 8,0MM ou SEM BALAO.
# ============================================================

import re as _re_cascata_specs

def _medbox_norm_cascata_specs(valor):
    texto = str(valor or "").upper().strip()
    mapa = {
        "Á": "A", "À": "A", "Ã": "A", "Â": "A",
        "É": "E", "Ê": "E",
        "Í": "I",
        "Ó": "O", "Ô": "O", "Õ": "O",
        "Ú": "U",
        "Ç": "C",
    }
    for a, b in mapa.items():
        texto = texto.replace(a, b)

    texto = texto.replace("\\", "/")
    texto = texto.replace("N°", "N ").replace("Nº", "N ").replace("NUMERO", "N ")
    texto = texto.replace("C/", "COM ").replace("S/", "SEM ")
    texto = texto.replace("POLIVINIL", "PVC").replace("POLI VINIL", "PVC")
    texto = texto.replace("CLORETO DE POLIVINILA", "PVC")
    texto = texto.replace("ENDOTRAQUEAL", "OROTRAQUEAL")
    texto = texto.replace("ORO TRAQUEAL", "OROTRAQUEAL")
    texto = texto.replace("ORO-TRAQUEAL", "OROTRAQUEAL")

    texto = _re_cascata_specs.sub(r"[^A-Z0-9%/,.\-+ X]+", " ", texto)
    texto = _re_cascata_specs.sub(r"\s+", " ", texto).strip()
    return texto


def _medbox_specs_criticas(valor):
    texto = _medbox_norm_cascata_specs(valor)
    specs = set()

    def add(v):
        v = str(v or "").upper().strip()
        v = v.replace(".", ",")
        v = _re_cascata_specs.sub(r"\s+", "", v)
        if v:
            specs.add(v)

    # COM BALAO / SEM BALAO precisa ser obrigatório.
    if "COM BALAO" in texto or "C BALAO" in texto:
        specs.add("COM_BALAO")
    if "SEM BALAO" in texto or "S BALAO" in texto:
        specs.add("SEM_BALAO")

    # Materiais.
    for termo in ["PVC", "LATEX", "SILICONE", "POLIURETANO"]:
        if termo in texto:
            specs.add(termo)

    # Vias.
    if "2 VIAS" in texto or "DUAS VIAS" in texto:
        specs.add("2VIAS")
    if "3 VIAS" in texto or "TRES VIAS" in texto:
        specs.add("3VIAS")

    # Cores e características que mudam o produto.
    for termo in ["AZUL", "PRETO", "VERDE", "ROSA", "BRANCO", "OPACO", "TRANSPARENTE", "DRENAVEL", "FECHADO", "ESTERIL", "NAO ESTERIL"]:
        if termo in texto:
            specs.add(termo)

    # Dosagem/volume/medida.
    for m in _re_cascata_specs.findall(r"\b\d+(?:[,.]\d+)?\s*(?:MG/ML|MG|MCG|G|ML|L|UI|U|CM|MM|M|FR|G)\b", texto):
        add(m)

    # Medidas compostas: 13X4,5 / 20CMX30CM.
    for m in _re_cascata_specs.findall(r"\b\d+(?:[,.]\d+)?\s*X\s*\d+(?:[,.]\d+)?(?:\s*(?:MM|CM|M))?\b", texto):
        add(m)

    # Número/tamanho: N 8,5 => 8,5MM para tubo/cânula.
    for m in _re_cascata_specs.findall(r"\bN\s*\d+(?:[,.]\d+)?\b", texto):
        numero = m.replace("N", "").strip()
        add(numero + "MM")

    # Se tiver valor solto tipo 8,5MM, mantém.
    for m in _re_cascata_specs.findall(r"\b\d+(?:[,.]\d+)?MM\b", texto):
        add(m)

    return specs


def _medbox_base_sem_specs(valor):
    texto = _medbox_norm_cascata_specs(valor)

    # Remove especificações para comparar a família do produto.
    texto = _re_cascata_specs.sub(r"\b\d+(?:[,.]\d+)?\s*(?:MG/ML|MG|MCG|G|ML|L|UI|U|CM|MM|M|FR|G)\b", " ", texto)
    texto = _re_cascata_specs.sub(r"\b\d+(?:[,.]\d+)?\s*X\s*\d+(?:[,.]\d+)?(?:\s*(?:MM|CM|M))?\b", " ", texto)
    texto = _re_cascata_specs.sub(r"\bN\s*\d+(?:[,.]\d+)?\b", " ", texto)

    remover = [
        "COM BALAO", "SEM BALAO", "C BALAO", "S BALAO",
        "PVC", "LATEX", "SILICONE", "POLIURETANO",
        "2 VIAS", "3 VIAS", "DUAS VIAS", "TRES VIAS",
        "AZUL", "PRETO", "VERDE", "ROSA", "BRANCO",
        "OPACO", "TRANSPARENTE", "DRENAVEL", "FECHADO",
        "ESTERIL", "NAO ESTERIL", "ADULTO", "INFANTIL",
        "MARCA", "GENERICO", "IMPORTADO", "MANIPULADO"
    ]
    for termo in remover:
        texto = texto.replace(termo, " ")

    texto = _re_cascata_specs.sub(r"\s+", " ", texto).strip()
    return texto


def _medbox_score_base_cascata(a, b):
    ta = set([x for x in _medbox_base_sem_specs(a).split() if len(x) > 2])
    tb = set([x for x in _medbox_base_sem_specs(b).split() if len(x) > 2])
    if not ta or not tb:
        return 0
    return int(round((len(ta & tb) / max(1, len(ta | tb))) * 100))


def _medbox_specs_compativeis_cascata(origem_desc, candidato_desc):
    specs_origem = _medbox_specs_criticas(origem_desc)
    specs_cand = _medbox_specs_criticas(candidato_desc)

    # Se a origem tem especificações, o candidato precisa conter TODAS.
    faltando = specs_origem - specs_cand

    # Se houver conflito explícito, bloqueia.
    conflitos = []
    pares_conflito = [
        ("COM_BALAO", "SEM_BALAO"),
        ("2VIAS", "3VIAS"),
        ("LATEX", "SILICONE"),
        ("PVC", "SILICONE"),
        ("PVC", "LATEX"),
    ]
    for a, b in pares_conflito:
        if a in specs_origem and b in specs_cand:
            conflitos.append(f"{a} x {b}")
        if b in specs_origem and a in specs_cand:
            conflitos.append(f"{b} x {a}")

    # Bloqueia medidas diferentes quando ambos têm medida/tamanho.
    medidas_origem = {s for s in specs_origem if any(ch in s for ch in ["MM", "CM", "ML", "MG", "FR", "UI", "X"])}
    medidas_cand = {s for s in specs_cand if any(ch in s for ch in ["MM", "CM", "ML", "MG", "FR", "UI", "X"])}

    if medidas_origem and medidas_cand and not medidas_origem.issubset(medidas_cand):
        conflitos.append("MEDIDA_DIFERENTE")

    ok = not faltando and not conflitos

    return ok, {
        "specs_origem": sorted(specs_origem),
        "specs_candidato": sorted(specs_cand),
        "faltando": sorted(faltando),
        "conflitos": conflitos,
    }


def buscar_produtos_afetados_cascata(produto_id, tipo_cascata, sku_master_novo=None, caminho_banco=None):
    """
    Versão rígida: só retorna candidatos realmente compatíveis por especificação.
    Mantém a mesma assinatura usada pelo app.py.
    """
    conn = _conectar_leitura()
    conn.row_factory = sqlite3.Row

    try:
        cursor = conn.cursor()

        origem = cursor.execute("""
            SELECT id, sku, produto_padrao, sku_master, fabricante, categoria, ativo
            FROM produtos
            WHERE id = ?
            LIMIT 1
        """, (produto_id,)).fetchone()

        if not origem:
            return []

        origem_desc = origem["produto_padrao"] or origem["sku_master"] or origem["sku"] or ""

        candidatos = []

        # Mesmo SKU atual: só é seguro quando já é exatamente o mesmo SKU_MASTER.
        if tipo_cascata == "mesmo_sku":
            sku_atual = str(origem["sku_master"] or "").strip()
            if sku_atual:
                rows = cursor.execute("""
                    SELECT id, sku, produto_padrao, sku_master, fabricante, categoria, ativo
                    FROM produtos
                    WHERE ativo = 1
                      AND id != ?
                      AND UPPER(TRIM(COALESCE(sku_master, ''))) = UPPER(TRIM(?))
                    ORDER BY id
                    LIMIT 200
                """, (produto_id, sku_atual)).fetchall()
                candidatos = rows

        elif tipo_cascata == "mesmo_fornecedor":
            fabricante = str(origem["fabricante"] or "").strip()
            if fabricante:
                rows = cursor.execute("""
                    SELECT id, sku, produto_padrao, sku_master, fabricante, categoria, ativo
                    FROM produtos
                    WHERE ativo = 1
                      AND id != ?
                      AND UPPER(TRIM(COALESCE(fabricante, ''))) = UPPER(TRIM(?))
                    ORDER BY id
                    LIMIT 300
                """, (produto_id, fabricante)).fetchall()
                candidatos = rows

        else:
            # semelhante: busca ampla por palavras principais, mas filtra por especificações rígidas.
            base_tokens = [t for t in _medbox_base_sem_specs(origem_desc).split() if len(t) > 2][:5]

            where = []
            params = []
            for t in base_tokens:
                where.append("UPPER(COALESCE(produto_padrao, '')) LIKE ?")
                params.append(f"%{t}%")

            if not where:
                return []

            rows = cursor.execute(f"""
                SELECT id, sku, produto_padrao, sku_master, fabricante, categoria, ativo
                FROM produtos
                WHERE ativo = 1
                  AND id != ?
                  AND ({" OR ".join(where)})
                ORDER BY id DESC
                LIMIT 500
            """, [produto_id] + params).fetchall()

            candidatos = rows

        saida = []

        for r in candidatos:
            cand_desc = r["produto_padrao"] or r["sku_master"] or r["sku"] or ""

            ok_specs, info_specs = _medbox_specs_compativeis_cascata(origem_desc, cand_desc)
            if not ok_specs:
                continue

            score = _medbox_score_base_cascata(origem_desc, cand_desc)
            if tipo_cascata == "semelhante" and score < 70:
                continue

            item = dict(r)
            item["score"] = score
            item["specs_origem"] = info_specs.get("specs_origem", [])
            item["specs_candidato"] = info_specs.get("specs_candidato", [])
            saida.append(item)

        saida.sort(key=lambda x: (-int(x.get("score") or 0), str(x.get("produto_padrao") or "")))

        return saida[:100]

    finally:
        conn.close()

