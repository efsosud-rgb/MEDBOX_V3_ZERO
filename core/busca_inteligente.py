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


def _buscar_por_campo_produto(cursor, candidatos, campo_sql, campo_evidencia, termo):
    like = f"%{termo}%"
    cursor.execute(
        f"""
        SELECT id, sku, produto_padrao, fabricante, categoria, {campo_sql} AS texto_match
        FROM produtos
        WHERE UPPER({campo_sql}) LIKE ? AND ativo = 1
        """,
        (like,),
    )
    for row in cursor.fetchall():
        _adicionar_candidato(candidatos, row, campo_evidencia, row["texto_match"])


def _buscar_por_equivalencias(cursor, candidatos, termo):
    like = f"%{termo}%"
    cursor.execute(
        """
        SELECT p.id, p.sku, p.produto_padrao, p.fabricante, p.categoria,
               e.descricao_equivalente AS texto_match
        FROM produtos p
        JOIN equivalencias e ON e.produto_id = p.id
        WHERE UPPER(e.descricao_equivalente) LIKE ? AND p.ativo = 1
        """,
        (like,),
    )
    for row in cursor.fetchall():
        _adicionar_candidato(candidatos, row, "equivalencia", row["texto_match"])


def _buscar_por_precos(cursor, candidatos, campo_sql, campo_evidencia, termo):
    like = f"%{termo}%"
    cursor.execute(
        f"""
        SELECT p.id, p.sku, p.produto_padrao, p.fabricante, p.categoria,
               pf.{campo_sql} AS texto_match
        FROM produtos p
        JOIN precos_fornecedores pf ON pf.produto_id = p.id
        WHERE UPPER(pf.{campo_sql}) LIKE ? AND p.ativo = 1
        """,
        (like,),
    )
    for row in cursor.fetchall():
        _adicionar_candidato(candidatos, row, campo_evidencia, row["texto_match"])


def _buscar_por_fornecedor(cursor, candidatos, termo):
    like = f"%{termo}%"
    cursor.execute(
        """
        SELECT p.id, p.sku, p.produto_padrao, p.fabricante, p.categoria,
               f.nome AS texto_match
        FROM produtos p
        JOIN precos_fornecedores pf ON pf.produto_id = p.id
        JOIN fornecedores f ON f.id = pf.fornecedor_id
        WHERE UPPER(f.nome) LIKE ? AND p.ativo = 1
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
        _buscar_por_campo_produto(cursor, candidatos, "fabricante", "fabricante", termo)
        _buscar_por_equivalencias(cursor, candidatos, termo)
        _buscar_por_precos(
            cursor, candidatos, "descricao_original", "descricao_original", termo
        )
        _buscar_por_precos(cursor, candidatos, "marca", "marca", termo)
        _buscar_por_fornecedor(cursor, candidatos, termo)

    return candidatos


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
        if item["suspeito_contaminado"]:
            item["score_busca"] = max(0.0, round(item["score_busca"] - 4.0, 2))

    resultados.sort(
        key=lambda item: (
            -item["score_busca"],
            1 if item["suspeito_contaminado"] else 0,
            0 if item["tem_preco"] else 1,
            item["menor_preco"] if item["menor_preco"] is not None else 999999999,
            item["produto_padrao"] or "",
        )
    )

    return resultados[:limite]
