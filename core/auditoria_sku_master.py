import csv
import io
import re
import sqlite3
import unicodedata
from collections import defaultdict
from pathlib import Path

from rapidfuzz import fuzz


BASE_DIR = Path(__file__).resolve().parent.parent
CAMINHO_BANCO = BASE_DIR / "banco" / "medbox_v3.db"

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
    "DE",
    "DA",
    "DO",
    "DAS",
    "DOS",
    "E",
    "A",
    "O",
    "AS",
    "OS",
    "COM",
    "C",
    "SEM",
    "PARA",
    "P",
    "POR",
    "EM",
    "NA",
    "NO",
    "NAS",
    "NOS",
}

MARCAS_FINAIS_SUSPEITAS = {
    "EQUIPLEX",
    "FARMACE",
    "HALEXISTAR",
    "SAMTEC",
    "HIPOLABOR",
    "CRISTALIA",
    "TEUTO",
    "MEDIX",
    "THEOTO",
    "SOL",
    "CARE",
}


def _conectar_leitura():
    caminho = CAMINHO_BANCO.as_posix()
    return sqlite3.connect(f"file:{caminho}?mode=ro", uri=True)


def _normalizar(texto):
    texto = str(texto or "").strip().upper()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(ch for ch in texto if not unicodedata.combining(ch))
    texto = re.sub(r"[^A-Z0-9%+/,.-]+", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()


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
        "excesso_tokens",
        "muito_longo",
        "repeticao_termo_base",
        "marca_fabricante_no_fim",
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
        score = fuzz.token_set_ratio(assinatura, limpo["assinatura"])
        if score >= 92:
            candidatos.append((score, len(_tokens(limpo["produto_padrao"])), limpo["produto_padrao"]))

    if not candidatos:
        return ""

    candidatos.sort(key=lambda item: (-item[0], item[1], item[2]))
    return candidatos[0][2]


def gerar_auditoria_sku_master(filtro="todos", limite=200):
    filtro = filtro if filtro in FILTROS else "todos"
    limite = max(1, int(limite or 200))

    conn = _conectar_leitura()
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, sku, produto_padrao, fabricante, categoria, ativo
            FROM produtos
            ORDER BY produto_padrao
            """
        )
        produtos = [dict(row) for row in cursor.fetchall()]

        cursor.execute(
            """
            SELECT produto_id, descricao_original
            FROM precos_fornecedores
            """
        )
        descricoes_por_produto = defaultdict(list)
        total_precos = defaultdict(int)
        for row in cursor.fetchall():
            produto_id = row["produto_id"]
            total_precos[produto_id] += 1
            if row["descricao_original"]:
                descricoes_por_produto[produto_id].append(row["descricao_original"])

        cursor.execute(
            """
            SELECT produto_id, COUNT(*) AS total
            FROM equivalencias
            GROUP BY produto_id
            """
        )
        total_equivalencias = {
            row["produto_id"]: row["total"]
            for row in cursor.fetchall()
        }
    finally:
        conn.close()

    grupos_normalizados = defaultdict(list)
    for produto in produtos:
        chave = _normalizar(produto.get("produto_padrao"))
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
            produto.get("produto_padrao"),
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
        {
            **item,
            "assinatura": _assinatura_sku(item["produto_padrao"]),
        }
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
    itens_limitados = itens_filtrados[:limite]
    for item in itens_limitados:
        if item["classificacao"] != "LIMPO":
            item["sugestao_sku_limpo"] = _sugerir_sku_limpo(item, indice_limpos)

    return {
        "filtro": filtro,
        "contadores": {
            "total_produtos": len(produtos),
            "total_limpos": contadores["LIMPO"],
            "total_suspeitos": contadores["SUSPEITO"],
            "total_contaminados_fortes": contadores["CONTAMINADO_FORTE"],
            "total_sku_pendente": contadores["SKU_PENDENTE"],
            "total_duplicados": contadores["DUPLICADO"],
            "total_grupos_duplicados": total_grupos_duplicados,
            "total_filtrado": len(itens_filtrados),
        },
        "itens": itens_limitados,
        "total_sem_limite": len(itens_filtrados),
    }


def gerar_csv_auditoria_sku_master(filtro="todos"):
    auditoria = gerar_auditoria_sku_master(filtro=filtro, limite=1000000)
    buffer = io.StringIO()
    campos = [
        "produto_id",
        "produto_padrao",
        "fabricante",
        "categoria",
        "classificacao",
        "motivo",
        "sugestao_sku_limpo",
        "total_precos",
        "total_equivalencias",
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
    if (
        "SORO FISIOLOGICO" in texto
        or "CLORETO DE SODIO 0,9" in texto
        or "CLORETO DE SODIO 20" in texto
    ):
        return "soro_fisiologico"
    if (
        "SORO GLICOSADO" in texto
        or "GLICOSE 5%" in texto
        or "GLICOSE 10%" in texto
        or "GLICOSE 25%" in texto
        or "GLICOSE 50%" in texto
        or "DEXTROSE" in texto
    ):
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


def _sugestao_dicionario_medbox(produto_padrao):
    texto = _normalizar(produto_padrao)

    if "ONDANSETRONA" in texto:
        dose = re.search(r"\b(4|8)\s*MG\s*/?\s*(2|4)?\s*ML\b", texto)
        if dose:
            mg = dose.group(1)
            ml = dose.group(2) or ("2" if mg == "4" else "4")
            return f"ONDANSETRONA {mg}MG/{ml}ML", 91
        return "ONDANSETRONA", 84

    if "RINGER" in texto and "LACTATO" in texto:
        volume = re.search(r"\b(\d+)\s*ML\b", texto)
        if volume:
            return f"SORO RINGER COM LACTATO {volume.group(1)}ML", 90
        return "SORO RINGER COM LACTATO", 88

    glicose = re.search(r"\bGLICOSE\s*(5|10|25|50)\s*%", texto)
    if glicose or "SORO GLICOSADO" in texto or "DEXTROSE" in texto:
        percentual = glicose.group(1) if glicose else ""
        if not percentual:
            percentual_match = re.search(r"\b(5|10|25|50)\s*%", texto)
            percentual = percentual_match.group(1) if percentual_match else ""
        volume = re.search(r"\b(\d+)\s*ML\b", texto)
        partes = ["SORO GLICOSADO"]
        if percentual:
            partes.append(f"{percentual}%")
        if volume:
            partes.append(f"{volume.group(1)}ML")
        return " ".join(partes), 88 if percentual else 82

    cloreto = re.search(r"\bCLORETO DE SODIO\s*(0,9|20)\s*%", texto)
    if cloreto or "SORO FISIOLOGICO" in texto:
        percentual = cloreto.group(1) if cloreto else ""
        if not percentual:
            percentual_match = re.search(r"\b(0,9|20)\s*%", texto)
            percentual = percentual_match.group(1) if percentual_match else "0,9"
        volume = re.search(r"\b(\d+)\s*ML\b", texto)
        partes = ["SORO FISIOLOGICO", f"{percentual}%"]
        if volume:
            partes.append(f"{volume.group(1)}ML")
        return " ".join(partes), 88

    return "", 0


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
        {
            **item,
            "assinatura": _assinatura_sku(item["produto_padrao"]),
        }
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
        score = max(
            fuzz.token_set_ratio(assinatura_atual, candidato["assinatura"]),
            fuzz.token_set_ratio(referencia, candidato["produto_padrao"]),
        )
        if concentracoes_atual and concentracoes_candidato and not (concentracoes_atual & concentracoes_candidato):
            score -= 18

        registro = (score, len(_tokens(candidato["produto_padrao"])), candidato["produto_padrao"])
        if not melhor or registro[0] > melhor[0] or (
            registro[0] == melhor[0] and registro[1] < melhor[1]
        ):
            melhor = registro

    if melhor and melhor[0] >= 92:
        return melhor[2], "existente", round(float(melhor[0]), 2)

    return "", "", 0


def _sugerir_sku_assistido(item, limpos, indice_limpos):
    sugestao_dicionario, confianca_dicionario = _sugestao_dicionario_medbox(item["produto_padrao"])
    sku_existente, origem, confianca = _buscar_sku_existente(
        item,
        limpos,
        indice_limpos,
        sugestao_dicionario,
    )
    if sku_existente:
        return sku_existente, origem, confianca

    if sugestao_dicionario:
        return sugestao_dicionario, "dicionario", confianca_dicionario

    sugestao_regex = _limpar_por_regex(item["produto_padrao"])
    if sugestao_regex and sugestao_regex != _normalizar(item["produto_padrao"]):
        return sugestao_regex, "regex", 70

    return "", "revisao", 0


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

        sku_sugerido, origem, confianca = _sugerir_sku_assistido(item, limpos, indice_limpos)
        sugestoes.append({
            "produto_id": item["id"],
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
        "dicionario": sum(1 for item in sugestoes if item["origem_sugestao"] == "dicionario"),
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
        "produto_id",
        "produto_padrao",
        "fabricante",
        "motivo",
        "classificacao",
        "grupo",
        "sku_sugerido",
        "origem_sugestao",
        "confianca",
        "total_precos",
        "total_equivalencias",
    ]
    writer = csv.DictWriter(buffer, fieldnames=campos, extrasaction="ignore")
    writer.writeheader()
    for item in sugestoes["itens"]:
        writer.writerow(item)
    return buffer.getvalue()
