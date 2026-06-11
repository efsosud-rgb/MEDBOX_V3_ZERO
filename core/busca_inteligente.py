from collections import defaultdict
import re

from rapidfuzz import fuzz

from core.banco import (
    conectar,
    expandir_com_sinonimos,
    gerar_variacoes,
    normalizar_texto,
)


PESOS_CAMPOS = {
    "produto_padrao": 1.00,
    "sku": 0.95,
    "equivalencia": 0.95,
    "descricao_original": 0.80,
    "fabricante": 0.55,
    "marca": 0.55,
    "fornecedor": 0.30,
}

MARCAS_FINAIS_SUSPEITAS = {
    "EQUIPLEX",
    "FARMACE",
    "HALEXISTAR",
    "HYPOFARMA",
    "SAMTEC",
    "MEDIX",
    "WILTEX",
    "INJEX",
    "LEGRAND",
    "BIOLAB",
}

TERMOS_SOLUCAO_GLICOSE = ("GLICOSE", "DEXTROSE", "SORO GLICOSADO")
TERMOS_EXCLUSAO_GLICOSE = (
    "TIRA",
    "TESTE",
    "MEDIDOR",
    "GLUCOMETRO",
    "GLUCOLEADER",
    "BUPIVACAINA",
    "NITROGLICERINA",
)
TERMOS_FORNECEDOR_GENERICOS = {
    "MED",
    "FARMA",
    "DISTRIBUIDORA",
    "DISTRIBUIDOR",
    "HOSPITALAR",
    "MEDICAMENTOS",
    "PRODUTOS",
}


def _termos_expandidos(termo):
    termos = set()

    for variacao in gerar_variacoes(termo):
        termos.add(variacao)

    for sinonimo in expandir_com_sinonimos(termo):
        for variacao in gerar_variacoes(sinonimo):
            termos.add(variacao)

    termo_norm = normalizar_texto(termo)
    for palavra in termo_norm.split():
        if len(palavra) >= 3:
            termos.add(palavra)

    return sorted(t for t in termos if t)


def _termo_generico_fornecedor(termo):
    palavras = set(normalizar_texto(termo).split())
    return bool(palavras) and palavras.issubset(TERMOS_FORNECEDOR_GENERICOS)


def _tokens(texto):
    return normalizar_texto(texto).split()


def _assinatura_sku(texto):
    texto_norm = normalizar_texto(texto)
    partes = re.findall(r"[A-Z]+|\d+(?:[,.]\d+)?\s*(?:MG|ML|G|MCG|UI|%)?", texto_norm)
    assinatura = []

    for parte in partes:
        parte = re.sub(r"\s+", "", parte)
        if parte and parte not in assinatura:
            assinatura.append(parte)

    return " ".join(assinatura[:6])


def _percentuais(texto):
    texto_norm = normalizar_texto(texto)
    return {
        match.replace(",", ".")
        for match in re.findall(r"\b\d+(?:[,.]\d+)?%", texto_norm)
    }


def _consulta_solucao_glicose_percentual(termo):
    termo_norm = normalizar_texto(termo)
    return bool(_percentuais(termo_norm)) and any(
        base in termo_norm for base in TERMOS_SOLUCAO_GLICOSE
    )


def _produto_solucao_glicose_compativel(item, percentuais_termo):
    textos = [
        item.get("sku_master_exibicao", ""),
        item.get("produto_padrao", ""),
    ]

    for textos_campo in item.get("evidencias_busca", {}).values():
        textos.extend(textos_campo)

    texto_total = normalizar_texto(" ".join(textos))

    if any(bloqueado in texto_total for bloqueado in TERMOS_EXCLUSAO_GLICOSE):
        return False

    if not any(base in texto_total for base in TERMOS_SOLUCAO_GLICOSE):
        return False

    percentuais_item = set()
    for texto in textos:
        percentuais_item.update(_percentuais(texto))

    return bool(percentuais_item & percentuais_termo)


def _sku_exato_ou_equivalente(termo, sku):
    termo_norm = normalizar_texto(termo)
    sku_norm = normalizar_texto(sku)

    if not termo_norm or not sku_norm:
        return False

    if sku_norm == termo_norm or sku_norm.startswith(termo_norm):
        return True

    return fuzz.token_set_ratio(termo_norm, sku_norm) >= 96


def _produto_padrao_suspeito(produto_padrao, precos=None):
    texto = normalizar_texto(produto_padrao)
    palavras = texto.split()
    precos = precos or []

    motivos = []

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

    for preco in precos:
        descricao = normalizar_texto(preco.get("descricao_original", ""))
        if descricao and descricao == texto:
            motivos.append("igual_descricao_original")
            break

    return bool(motivos), motivos


def _buscar_sku_limpo_equivalente(resultado, todos_resultados):
    assinatura = _assinatura_sku(resultado.get("produto_padrao", ""))
    if not assinatura:
        return ""

    melhores = []
    for candidato in todos_resultados:
        if candidato["id"] == resultado["id"]:
            continue
        if candidato.get("suspeito_contaminado"):
            continue
        nome = candidato.get("produto_padrao", "")
        if not nome:
            continue

        score = fuzz.token_set_ratio(assinatura, _assinatura_sku(nome))
        if score >= 92:
            melhores.append((score, len(_tokens(nome)), nome))

    if not melhores:
        return ""

    melhores.sort(key=lambda item: (-item[0], item[1], item[2]))
    return melhores[0][2]


def _aplicar_regras_ranking(termo, resultados):
    percentuais_termo = _percentuais(termo)
    consulta_glicose = _consulta_solucao_glicose_percentual(termo)

    for item in resultados:
        sku_exibicao = item.get("sku_master_exibicao") or item.get("produto_padrao") or ""
        percentuais_item = _percentuais(sku_exibicao) or _percentuais(item.get("produto_padrao", ""))
        percentual_divergente = bool(
            percentuais_termo and percentuais_item and not (percentuais_termo & percentuais_item)
        )

        item["sku_exato_termo"] = _sku_exato_ou_equivalente(termo, sku_exibicao)
        item["percentual_divergente"] = percentual_divergente

        if percentual_divergente:
            item["score_busca"] = max(0.0, round(item["score_busca"] - 35.0, 2))

        item["solucao_glicose_compativel"] = (
            _produto_solucao_glicose_compativel(item, percentuais_termo)
            if consulta_glicose else True
        )

        if consulta_glicose and not item["solucao_glicose_compativel"]:
            item["score_busca"] = max(0.0, round(item["score_busca"] - 60.0, 2))

    if percentuais_termo:
        resultados_mesmo_percentual = [
            item for item in resultados
            if not item.get("percentual_divergente")
        ]
        if len(resultados_mesmo_percentual) >= 10:
            resultados[:] = resultados_mesmo_percentual

    if consulta_glicose:
        resultados_compativeis = [
            item for item in resultados
            if item.get("solucao_glicose_compativel")
        ]
        if resultados_compativeis:
            resultados[:] = resultados_compativeis


def _produto_base(row):
    return {
        "id": row["id"],
        "sku": row["sku"],
        "produto_padrao": row["produto_padrao"],
        "fabricante": row["fabricante"],
        "categoria": row["categoria"],
        "evidencias_busca": defaultdict(set),
    }


def _adicionar_candidato(candidatos, row, campo, texto):
    produto_id = row["id"]

    if produto_id not in candidatos:
        candidatos[produto_id] = _produto_base(row)

    texto_norm = normalizar_texto(texto)
    if texto_norm:
        candidatos[produto_id]["evidencias_busca"][campo].add(texto_norm)


def _like_escape(termo):
    # Escapa wildcards SQL para que '%' e '_' no termo sejam buscados literalmente.
    # Sem isso, termos como "10%" viram "%10%%" que é um wildcard e causa full table scan.
    escaped = termo.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _buscar_por_campo_produto(cursor, candidatos, campo_sql, campo_evidencia, termo):
    like = _like_escape(termo)
    cursor.execute(
        f"""
        SELECT id, sku, produto_padrao, fabricante, categoria, {campo_sql} AS texto_match
        FROM produtos
        WHERE UPPER({campo_sql}) LIKE ? ESCAPE '\\' AND ativo = 1
        """,
        (like,),
    )
    for row in cursor.fetchall():
        _adicionar_candidato(candidatos, row, campo_evidencia, row["texto_match"])


def _buscar_por_equivalencias(cursor, candidatos, termo):
    like = _like_escape(termo)
    cursor.execute(
        """
        SELECT p.id, p.sku, p.produto_padrao, p.fabricante, p.categoria,
               e.descricao_equivalente AS texto_match
        FROM produtos p
        JOIN equivalencias e ON e.produto_id = p.id
        WHERE UPPER(e.descricao_equivalente) LIKE ? ESCAPE '\\' AND p.ativo = 1
        """,
        (like,),
    )
    for row in cursor.fetchall():
        _adicionar_candidato(candidatos, row, "equivalencia", row["texto_match"])


def _buscar_por_precos(cursor, candidatos, campo_sql, campo_evidencia, termo):
    like = _like_escape(termo)
    cursor.execute(
        f"""
        SELECT p.id, p.sku, p.produto_padrao, p.fabricante, p.categoria,
               pf.{campo_sql} AS texto_match
        FROM produtos p
        JOIN precos_fornecedores pf ON pf.produto_id = p.id
        WHERE UPPER(pf.{campo_sql}) LIKE ? ESCAPE '\\' AND p.ativo = 1
        """,
        (like,),
    )
    for row in cursor.fetchall():
        _adicionar_candidato(candidatos, row, campo_evidencia, row["texto_match"])


def _buscar_por_fornecedor(cursor, candidatos, termo):
    like = _like_escape(termo)
    cursor.execute(
        """
        SELECT p.id, p.sku, p.produto_padrao, p.fabricante, p.categoria,
               f.nome AS texto_match
        FROM produtos p
        JOIN precos_fornecedores pf ON pf.produto_id = p.id
        JOIN fornecedores f ON f.id = pf.fornecedor_id
        WHERE UPPER(f.nome) LIKE ? ESCAPE '\\' AND p.ativo = 1
        """,
        (like,),
    )
    for row in cursor.fetchall():
        _adicionar_candidato(candidatos, row, "fornecedor", row["texto_match"])


def _recuperar_candidatos(cursor, termos):
    candidatos = {}

    for termo in termos:
        _buscar_por_campo_produto(
            cursor, candidatos, "produto_padrao", "produto_padrao", termo
        )
        _buscar_por_campo_produto(cursor, candidatos, "sku", "sku", termo)
        _buscar_por_campo_produto(cursor, candidatos, "fabricante", "fabricante", termo)
        _buscar_por_equivalencias(cursor, candidatos, termo)
        _buscar_por_precos(
            cursor, candidatos, "descricao_original", "descricao_original", termo
        )
        _buscar_por_precos(cursor, candidatos, "marca", "marca", termo)
        _buscar_por_fornecedor(cursor, candidatos, termo)

    return candidatos


def identificar_fornecedor(termo):
    termo_norm = normalizar_texto(termo)
    if not termo_norm or _termo_generico_fornecedor(termo):
        return None

    conn = conectar()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT f.id, f.nome, f.tipo, f.ativo,
                   COUNT(DISTINCT pf.produto_id) AS total_produtos,
                   COUNT(pf.id) AS total_precos
            FROM fornecedores f
            LEFT JOIN precos_fornecedores pf ON pf.fornecedor_id = f.id
            WHERE f.ativo = 1
            GROUP BY f.id
            """
        )
        fornecedores = [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()

    exatos = [
        f for f in fornecedores
        if normalizar_texto(f["nome"]) == termo_norm
    ]
    if exatos:
        fornecedor = exatos[0]
        fornecedor["confianca_match"] = 100.0
        fornecedor["tipo_match"] = "exato"
        return fornecedor

    candidatos = []
    for fornecedor in fornecedores:
        nome_norm = normalizar_texto(fornecedor["nome"])
        if termo_norm in nome_norm or nome_norm in termo_norm:
            score = 96.0
        else:
            score = fuzz.token_set_ratio(termo_norm, nome_norm)

        if score >= 90:
            item = dict(fornecedor)
            item["confianca_match"] = round(score, 2)
            item["tipo_match"] = "fuzzy"
            candidatos.append(item)

    if not candidatos:
        return None

    candidatos.sort(key=lambda item: (-item["confianca_match"], item["nome"]))
    return candidatos[0]


def buscar_produtos_por_fornecedor(termo, limite=50):
    fornecedor = identificar_fornecedor(termo)
    if not fornecedor:
        return None

    conn = conectar()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT p.id, p.sku, p.produto_padrao, p.fabricante, p.categoria,
                   pf.preco, pf.descricao_original, pf.codigo_fornecedor,
                   pf.marca, pf.data_importacao,
                   f.id AS fornecedor_id, f.nome AS fornecedor
            FROM precos_fornecedores pf
            JOIN produtos p ON p.id = pf.produto_id
            JOIN fornecedores f ON f.id = pf.fornecedor_id
            WHERE f.id = ?
            AND pf.data_importacao = (
                SELECT MAX(pf2.data_importacao)
                FROM precos_fornecedores pf2
                WHERE pf2.produto_id = pf.produto_id
                AND pf2.fornecedor_id = pf.fornecedor_id
            )
            ORDER BY p.produto_padrao ASC, pf.preco ASC
            LIMIT ?
            """,
            (fornecedor["id"], limite),
        )
        rows = [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()

    resultados = []
    for row in rows:
        preco = {
            "preco": row["preco"],
            "descricao_original": row["descricao_original"],
            "codigo_fornecedor": row["codigo_fornecedor"],
            "marca": row["marca"],
            "data_importacao": row["data_importacao"],
            "data_cotacao": row["data_importacao"],
            "fornecedor": row["fornecedor"],
            "fornecedor_id": row["fornecedor_id"],
            "condicao": "",
            "tendencia": "novo",
            "variacao": 0,
            "historico": [],
        }
        resultado = {
            "id": row["id"],
            "sku": row["sku"],
            "produto_padrao": row["produto_padrao"],
            "sku_master": row["produto_padrao"],
            "sku_master_exibicao": row["produto_padrao"],
            "fabricante": row["fabricante"],
            "categoria": row["categoria"],
            "apresentacao": "",
            "concentracao": "",
            "forma": "",
            "unidade_compra": "UN",
            "score_busca": fornecedor["confianca_match"],
            "scores_por_campo": {"fornecedor": fornecedor["confianca_match"]},
            "evidencias_busca": {"fornecedor": [fornecedor["nome"]]},
            "origem_busca": "busca_fornecedor",
            "modo_resultado": "fornecedor",
            "precos": [preco],
            "menor_preco": row["preco"],
            "fornecedor_menor": row["fornecedor"],
            "tem_preco": True,
            "historico_precos": [],
            "tem_historico_real": False,
            "suspeito_contaminado": False,
            "motivos_sku_suspeito": [],
            "sku_pendente_padronizacao": False,
        }
        resultados.append(resultado)

    for item in resultados:
        suspeito, motivos = _produto_padrao_suspeito(
            item["produto_padrao"],
            item.get("precos", []),
        )
        item["suspeito_contaminado"] = suspeito
        item["motivos_sku_suspeito"] = motivos
        item["sku_pendente_padronizacao"] = suspeito

    for item in resultados:
        if item["suspeito_contaminado"]:
            sku_limpo = _buscar_sku_limpo_equivalente(item, resultados)
            if sku_limpo:
                item["sku_master_exibicao"] = sku_limpo
                item["sku_pendente_padronizacao"] = False

    return {
        "modo_busca": "fornecedor",
        "fornecedor": fornecedor,
        "resultados": resultados,
    }


def _score_texto(consulta, texto, usar_partial=False, campo=""):
    consulta_norm = normalizar_texto(consulta)
    texto_norm = normalizar_texto(texto)

    if not consulta_norm or not texto_norm:
        return 0.0

    if consulta_norm == texto_norm:
        return 100.0

    token_score = fuzz.token_set_ratio(consulta_norm, texto_norm)
    texto_longo = len(texto_norm) > len(consulta_norm) * 1.5

    if usar_partial:
        partial_score = fuzz.partial_ratio(consulta_norm, texto_norm)
        score = max(token_score * 0.80, partial_score * 0.70)
    elif texto_longo:
        partial_score = fuzz.partial_ratio(consulta_norm, texto_norm)
        score = max(token_score * 0.90, partial_score * 0.85)
    else:
        score = token_score

    if texto_norm.startswith(consulta_norm):
        bonus = 8.0 if campo in ("produto_padrao", "equivalencia") else 4.0
        return min(100.0, score + bonus)

    palavras_consulta = consulta_norm.split()
    palavras_texto = texto_norm.split()

    if palavras_consulta and palavras_texto and palavras_texto[0] == palavras_consulta[0]:
        bonus = 5.0 if campo in ("produto_padrao", "equivalencia") else 2.0
        return min(100.0, score + bonus)

    posicao = texto_norm.find(consulta_norm)
    if posicao >= 0:
        proporcao_posicao = posicao / max(len(texto_norm), 1)
        penalidade = 12.0 + min(18.0, proporcao_posicao * 30.0)

        if campo == "descricao_original":
            penalidade += 8.0

        excesso_tokens = max(0, len(palavras_texto) - len(palavras_consulta))
        penalidade += min(20.0, excesso_tokens * 2.5)
        score -= penalidade

    return max(0.0, min(100.0, score))


def _calcular_score(termo, produto):
    scores_por_campo = {}

    for campo, textos in produto["evidencias_busca"].items():
        usar_partial = campo == "descricao_original"

        melhor = 0.0
        for texto in textos:
            melhor = max(melhor, _score_texto(termo, texto, usar_partial, campo))

        scores_por_campo[campo] = round(melhor, 2)

    score_ponderado = 0.0
    for campo, score in scores_por_campo.items():
        score_ponderado = max(score_ponderado, score * PESOS_CAMPOS.get(campo, 0.0))

    return round(score_ponderado, 2), scores_por_campo


def _carregar_precos(cursor, produto_id):
    cursor.execute(
        """
        SELECT pf.preco, pf.descricao_original,
               pf.codigo_fornecedor, pf.marca,
               pf.data_importacao, f.nome AS fornecedor,
               f.id AS fornecedor_id
        FROM precos_fornecedores pf
        JOIN fornecedores f ON f.id = pf.fornecedor_id
        WHERE pf.produto_id = ?
        AND pf.data_importacao = (
            SELECT MAX(pf2.data_importacao)
            FROM precos_fornecedores pf2
            WHERE pf2.produto_id = pf.produto_id
            AND pf2.fornecedor_id = pf.fornecedor_id
        )
        ORDER BY pf.preco ASC
        LIMIT 10
        """,
        (produto_id,),
    )

    precos = [dict(row) for row in cursor.fetchall()]

    for preco in precos:
        preco["data_cotacao"] = preco.get("data_importacao", "")
        preco["condicao"] = ""
        preco["tendencia"] = "novo"
        preco["variacao"] = 0
        preco["historico"] = []

    return precos


def _carregar_historico(cursor, produto_id):
    cursor.execute(
        """
        SELECT preco, data_importacao
        FROM precos_fornecedores_historico
        WHERE produto_id = ? AND preco > 0
        ORDER BY data_importacao ASC
        LIMIT 12
        """,
        (produto_id,),
    )
    return [dict(row) for row in cursor.fetchall()]


def _montar_resultado(cursor, termo, produto):
    precos = _carregar_precos(cursor, produto["id"])
    historico_precos = _carregar_historico(cursor, produto["id"])
    score, scores_por_campo = _calcular_score(termo, produto)

    evidencias = {
        campo: sorted(textos)
        for campo, textos in produto["evidencias_busca"].items()
    }

    resultado = {
        "id": produto["id"],
        "sku": produto.get("sku", ""),
        "produto_padrao": produto.get("produto_padrao", ""),
        "fabricante": produto.get("fabricante", ""),
        "categoria": produto.get("categoria", ""),
        "sku_master": produto.get("produto_padrao", ""),
        "apresentacao": "",
        "concentracao": "",
        "forma": "",
        "unidade_compra": "UN",
        "score_busca": score,
        "scores_por_campo": scores_por_campo,
        "evidencias_busca": evidencias,
        "origem_busca": "busca_inteligente_v2",
        "precos": precos,
        "menor_preco": precos[0]["preco"] if precos else None,
        "fornecedor_menor": precos[0]["fornecedor"] if precos else "sem preco cadastrado",
        "tem_preco": bool(precos),
        "historico_precos": historico_precos,
        "tem_historico_real": len(historico_precos) >= 2,
    }

    suspeito, motivos = _produto_padrao_suspeito(resultado["produto_padrao"], precos)
    resultado["suspeito_contaminado"] = suspeito
    resultado["motivos_sku_suspeito"] = motivos
    resultado["sku_master_exibicao"] = resultado["produto_padrao"]
    resultado["sku_pendente_padronizacao"] = suspeito

    if resultado["fabricante"] in (None, "", "NONE"):
        resultado["fabricante"] = precos[0]["marca"] if precos else ""

    return resultado


def buscar_produto_inteligente(termo, limite=20):
    termo = (termo or "").strip()
    if not termo:
        return []

    termos = _termos_expandidos(termo)

    conn = conectar()
    try:
        cursor = conn.cursor()

        candidatos = _recuperar_candidatos(cursor, termos)
        resultados = [
            _montar_resultado(cursor, termo, produto)
            for produto in candidatos.values()
        ]
    finally:
        conn.close()

    for item in resultados:
        if item["suspeito_contaminado"]:
            sku_limpo = _buscar_sku_limpo_equivalente(item, resultados)
            if sku_limpo:
                item["sku_master_exibicao"] = sku_limpo
                item["sku_pendente_padronizacao"] = False

    for item in resultados:
        if _sku_exato_ou_equivalente(termo, item.get("sku_master_exibicao", "")):
            item["score_busca"] = max(
                item["score_busca"],
                round(_score_texto(termo, item["sku_master_exibicao"]), 2),
            )

        if item["suspeito_contaminado"] and item["sku_pendente_padronizacao"]:
            item["score_busca"] = max(0.0, round(item["score_busca"] - 4.0, 2))

    _aplicar_regras_ranking(termo, resultados)

    resultados.sort(
        key=lambda item: (
            -item["score_busca"],
            0 if item["sku_exato_termo"] else 1,
            0 if item["tem_preco"] else 1,
            0 if not item["sku_pendente_padronizacao"] else 1,
            item["menor_preco"] if item["menor_preco"] is not None else 999999999,
            item["produto_padrao"] or "",
        )
    )

    return resultados[:limite]
