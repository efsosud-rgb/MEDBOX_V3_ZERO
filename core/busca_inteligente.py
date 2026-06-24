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
    "sku_master": 1.00,
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



def _formatar_moeda_br(valor):
    try:
        valor = float(valor)
    except (TypeError, ValueError):
        return ""
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _detectar_qtd_embalagem(descricao):
    """
    Detecta quantidade por embalagem somente quando houver indicador claro
    de pacote/caixa/embalagem/unidades.

    Exemplos que detecta:
    - PC C/ 10UN
    - PCT C/ 100UN
    - CX C/ 50
    - C/ 500UN
    - PACOTE COM 20
    - CAIXA COM 100

    Não confunde medidas como 10ML, 500MG, 7,5X7,5 ou 13FIOS.
    """
    bruto = str(descricao or "").upper()
    texto = normalizar_texto(descricao or "").upper()

    candidatos = [bruto, texto]

    padroes = [
        # PC C/ 10UN, PC C / 10 UN, PCT C/100UN, CX C/50
        r"\b(?:PC|PCT|PACOTE|CX|CAIXA|KIT|EMB|EMBALAGEM|CARTELA|DISPLAY)\s*C\s*/\s*(\d{1,5})\s*(?:UN|UND|UNID|UNIDADES|PCS|PECAS|PEÇAS|AMP|AMPOLAS|FR|FRASCOS)?\b",

        # PC COM 10UN, PACOTE COM 20 UNIDADES, CAIXA COM 100
        r"\b(?:PC|PCT|PACOTE|CX|CAIXA|KIT|EMB|EMBALAGEM|CARTELA|DISPLAY)\s+COM\s+(\d{1,5})\s*(?:UN|UND|UNID|UNIDADES|PCS|PECAS|PEÇAS|AMP|AMPOLAS|FR|FRASCOS)?\b",

        # C/ 10UN, C/500 UN, C/ 12 FRASCOS
        r"\bC\s*/\s*(\d{1,5})\s*(?:UN|UND|UNID|UNIDADES|PCS|PECAS|PEÇAS|AMP|AMPOLAS|FR|FRASCOS)\b",

        # COM 10 UNIDADES
        r"\bCOM\s+(\d{1,5})\s*(?:UN|UND|UNID|UNIDADES|PCS|PECAS|PEÇAS|AMP|AMPOLAS|FR|FRASCOS)\b",
    ]

    for origem in candidatos:
        for padrao in padroes:
            achou = re.search(padrao, origem)
            if achou:
                qtd = int(achou.group(1))
                if qtd > 1:
                    return qtd, True

    return 1, False


def _aplicar_preco_unitario_embalagem(preco):
    """
    Não divide automaticamente preço por pacote.

    Regra ERP:
    - preço recebido do fornecedor permanece como preço unidade/original;
    - divisão por pacote só acontece quando o usuário clicar no botão
      "Preço é pacote" na tela.
    """
    preco_original = preco.get("preco")
    preco["qtd_embalagem"] = 1
    preco["venda_por_pacote"] = False
    preco["preco_pacote"] = None
    preco["preco_pacote_formatado"] = ""
    preco["preco_unidade_calculado"] = preco_original
    preco["preco_unidade_formatado"] = preco.get("preco_formatado") or _formatar_moeda_br(preco_original)
    return preco


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
    assinatura = _assinatura_sku(
        resultado.get("sku_master_exibicao") or resultado.get("produto_padrao", "")
    )
    if not assinatura:
        return ""

    melhores = []
    for candidato in todos_resultados:
        if candidato["id"] == resultado["id"]:
            continue
        if candidato.get("suspeito_contaminado"):
            continue
        nome = candidato.get("sku_master_exibicao") or candidato.get("produto_padrao", "")
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


def _row_get(row, campo, padrao=""):
    """Lê sqlite3.Row com segurança, mantendo compatibilidade com dict."""
    try:
        if hasattr(row, "keys") and campo not in row.keys():
            return padrao
        valor = row[campo]
    except (KeyError, IndexError, TypeError):
        return padrao
    return valor if valor is not None else padrao


def _sku_master_exibicao_linha(row):
    """SKU operacional corrigido; fallback para produto_padrao quando vazio."""
    sku_master = (_row_get(row, "sku_master", "") or "").strip()
    produto_padrao = (_row_get(row, "produto_padrao", "") or "").strip()
    return sku_master or produto_padrao


def _produto_base(row):
    sku_master = (_row_get(row, "sku_master", "") or "").strip()
    sku_master_exibicao = _sku_master_exibicao_linha(row)

    return {
        "id": row["id"],
        "sku": row["sku"],
        "produto_padrao": row["produto_padrao"],
        "sku_master": sku_master,
        "sku_master_exibicao": sku_master_exibicao,
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
        SELECT id, sku, produto_padrao, sku_master, fabricante, categoria, {campo_sql} AS texto_match
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
        SELECT p.id, p.sku, p.produto_padrao, p.sku_master, p.fabricante, p.categoria,
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
        SELECT p.id, p.sku, p.produto_padrao, p.sku_master, p.fabricante, p.categoria,
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
        SELECT p.id, p.sku, p.produto_padrao, p.sku_master, p.fabricante, p.categoria,
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
        _buscar_por_campo_produto(cursor, candidatos, "sku_master", "sku_master", termo)
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
            SELECT p.id, p.sku, p.produto_padrao, p.sku_master, p.fabricante, p.categoria,
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
            ORDER BY COALESCE(NULLIF(TRIM(p.sku_master), ''), p.produto_padrao) ASC, pf.preco ASC
            LIMIT ?
            """,
            (fornecedor["id"], limite),
        )
        rows = [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()

    resultados = []
    for row in rows:
        sku_master_corrigido = bool((row.get("sku_master") if hasattr(row, "get") else row["sku_master"]) or "")
        sku_master_exibicao = _sku_master_exibicao_linha(row)

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
            "sku_master": sku_master_exibicao,
            "sku_master_exibicao": sku_master_exibicao,
            "sku_master_corrigido": sku_master_corrigido,
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
        item["sku_pendente_padronizacao"] = bool(suspeito and not item.get("sku_master_corrigido"))

    for item in resultados:
        if item["suspeito_contaminado"] and not item.get("sku_master_corrigido"):
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

    sku_master_corrigido = bool((produto.get("sku_master") or "").strip())
    sku_master_exibicao = produto.get("sku_master_exibicao") or produto.get("produto_padrao", "")

    resultado = {
        "id": produto["id"],
        "sku": produto.get("sku", ""),
        "produto_padrao": produto.get("produto_padrao", ""),
        "sku_master_original": produto.get("sku_master", ""),
        "fabricante": produto.get("fabricante", ""),
        "categoria": produto.get("categoria", ""),
        "sku_master": sku_master_exibicao,
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
    resultado["sku_master_exibicao"] = sku_master_exibicao
    resultado["sku_master_corrigido"] = sku_master_corrigido
    resultado["sku_pendente_padronizacao"] = bool(suspeito and not sku_master_corrigido)

    if resultado["fabricante"] in (None, "", "NONE"):
        resultado["fabricante"] = precos[0]["marca"] if precos else ""

    return resultado



def _normalizar_precos_embalagem_resultados(resultados):
    """
    Normaliza preços sem dividir automaticamente por embalagem.

    A decisão de preço pacote agora é manual na tela:
    botão "Preço é pacote".
    """
    if not resultados:
        return resultados

    def moeda(valor):
        try:
            valor = float(valor)
        except (TypeError, ValueError):
            return ""
        return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    for item in resultados:
        precos = item.get("precos") or []

        for preco in precos:
            preco_original = preco.get("preco")
            preco["qtd_embalagem"] = 1
            preco["venda_por_pacote"] = False
            preco["preco_pacote"] = None
            preco["preco_pacote_formatado"] = ""
            preco["preco_unidade_calculado"] = preco_original
            preco["preco_unidade_formatado"] = preco.get("preco_formatado") or moeda(preco_original)

        if precos:
            # Ordenação original por preço recebido, sem divisão automática.
            precos.sort(
                key=lambda p: (
                    p.get("preco")
                    if p.get("preco") is not None
                    else 999999999
                )
            )

            menor = precos[0].get("preco")

            item["precos"] = precos
            item["menor_preco"] = menor
            item["menor_preco_formatado"] = moeda(menor)
            item["preco_unitario_real"] = menor
            item["preco_unitario_real_formatado"] = moeda(menor)
            item["preco"] = menor
            item["preco_formatado"] = moeda(menor)

    return resultados



def _descricao_fornecedor_do_item(item):
    """
    Retorna descrição real do fornecedor/preço para exibição.
    Não usa SKU Master como fallback, para evitar duplicidade visual.
    """
    for preco in item.get("precos") or []:
        desc = (
            preco.get("descricao_original")
            or preco.get("descricao_fornecedor")
            or preco.get("descricao")
            or ""
        )
        if desc and desc.strip():
            return desc.strip()

    return ""


def _ordenar_outros_produtos_por_preco_unitario(resultados):
    """
    Mantém primeiro item como principal e ordena os demais pelo menor preço original.
    A reordenação por preço unitário calculado acontece no frontend após o clique manual.
    """
    if not resultados:
        return resultados

    for item in resultados:
        precos = item.get("precos") or []
        if precos:
            melhor = precos[0]
            item["tem_preco"] = True
            item["descricao_fornecedor_exibicao"] = (
                melhor.get("descricao_original")
                or melhor.get("descricao_fornecedor")
                or item.get("produto_padrao")
                or item.get("sku_master_exibicao")
                or ""
            )
            item["melhor_qtd_embalagem"] = 1
            item["melhor_preco_pacote"] = None
            item["melhor_preco_pacote_formatado"] = ""
            item["melhor_preco_unidade"] = melhor.get("preco")
            item["melhor_preco_unidade_formatado"] = melhor.get("preco_formatado") or item.get("menor_preco_formatado", "")
        else:
            item["tem_preco"] = False
            item["descricao_fornecedor_exibicao"] = (
                item.get("produto_padrao")
                or item.get("sku_master_exibicao")
                or ""
            )
            item["melhor_qtd_embalagem"] = 1
            item["melhor_preco_pacote"] = None
            item["melhor_preco_pacote_formatado"] = ""
            item["melhor_preco_unidade"] = None
            item["melhor_preco_unidade_formatado"] = ""

    if len(resultados) <= 1:
        return resultados

    principal = resultados[0]
    demais = resultados[1:]

    demais.sort(
        key=lambda item: (
            0 if item.get("tem_preco") else 1,
            item.get("melhor_preco_unidade") if item.get("melhor_preco_unidade") is not None else 999999999,
            item.get("sku_master_exibicao", "") or item.get("produto_padrao", "")
        )
    )

    return [principal] + demais




def _extrair_medidas_obrigatorias_consulta(termo):
    """
    Extrai medidas explícitas da busca.
    Ex.: soro 500ml -> ["500ML"]
    """
    texto = normalizar_texto(termo or "").upper()
    medidas = []

    padrao = re.compile(r"\b(\d+(?:[,.]\d+)?)\s*(ML|L|MG|G|MCG|UI|%)\b", re.I)

    for valor, unidade in padrao.findall(texto):
        unidade = unidade.upper()
        valor_norm = valor.replace(",", ".")

        try:
            numero = float(valor_norm)
        except ValueError:
            continue

        if unidade == "L":
            numero = numero * 1000
            unidade = "ML"

        if float(numero).is_integer():
            valor_final = str(int(numero))
        else:
            valor_final = str(numero).replace(".", ",")

        medidas.append(f"{valor_final}{unidade}")

    return list(dict.fromkeys(medidas))


def _extrair_palavras_obrigatorias_consulta(termo):
    """
    Extrai termos relevantes da busca, ignorando medidas e termos genéricos.
    Tokens técnicos com números, como 25X7, permanecem obrigatórios.
    Ex.: soro 500ml -> ["SORO"]
    """
    texto = normalizar_texto(termo or "").upper()

    # Remove medidas explícitas para não virar palavra solta.
    texto = re.sub(r"\b\d+(?:[,.]\d+)?\s*(ML|L|MG|G|MCG|UI|%)\b", " ", texto, flags=re.I)

    palavras = re.findall(r"\b[A-Z0-9]+(?:[,.][0-9]+)?\b", texto)

    stopwords = {
        "DE", "DA", "DO", "DAS", "DOS", "E", "A", "O", "AS", "OS",
        "COM", "SEM", "PARA", "POR", "EM", "NA", "NO", "NAS", "NOS",
        "UND", "UNID", "UNIDADE", "UNIDADES",
        "CAIXA", "PACOTE", "PCT", "KIT", "FR", "FRASCO", "AMP", "AMPOLA",
        "ITEM", "GENERICO", "SIMILAR"
    }

    palavras = [
        p for p in palavras
        if p not in stopwords and (len(p) >= 3 or any(ch.isdigit() for ch in p))
    ]

    return list(dict.fromkeys(palavras))


def _texto_completo_resultado_para_medidas(item):
    """
    Junta campos relevantes do resultado para validar palavras e medidas.
    """
    partes = [
        item.get("sku_master_exibicao", ""),
        item.get("sku_master", ""),
        item.get("produto_padrao", ""),
        item.get("sku", ""),
        item.get("fabricante", ""),
        item.get("categoria", ""),
    ]

    for preco in item.get("precos") or []:
        partes.extend([
            preco.get("descricao_original", ""),
            preco.get("descricao_fornecedor", ""),
            preco.get("sku_master_exibicao", ""),
            preco.get("sku_master", ""),
            preco.get("codigo_fornecedor", ""),
        ])

    for eq in item.get("equivalencias") or item.get("descricoes_equivalentes") or []:
        if isinstance(eq, dict):
            partes.append(eq.get("descricao_equivalente", ""))
            partes.append(eq.get("descricao", ""))
        else:
            partes.append(str(eq))

    # Inclui os textos que efetivamente tornaram o item candidato, inclusive
    # equivalencias e descricoes originais/de fornecedor.
    for textos in (item.get("evidencias_busca") or {}).values():
        if isinstance(textos, (list, tuple, set)):
            partes.extend(textos)
        elif textos:
            partes.append(str(textos))

    texto = " ".join(str(p or "") for p in partes)
    return normalizar_texto(texto).upper()


def _contem_medida_exata(texto, medida):
    """
    Valida medida exata.
    500ML não pode bater com 1500ML.
    """
    medida = normalizar_texto(medida).upper().replace(" ", "")

    m = re.match(r"^(\d+(?:[,.]\d+)?)(ML|L|MG|G|MCG|UI|%)$", medida)
    if not m:
        return medida in texto.replace(" ", "")

    valor, unidade = m.groups()

    # Aceita 500ML, 500 ML, 500-ML, mas não 1500ML.
    padrao = r"(?<!\d)" + re.escape(valor) + r"\s*" + re.escape(unidade) + r"\b"
    return re.search(padrao, texto, flags=re.I) is not None


def _resultado_atende_medidas_obrigatorias(item, medidas, palavras):
    texto = _texto_completo_resultado_para_medidas(item)

    for palavra in palavras:
        if not re.search(r"\b" + re.escape(palavra) + r"\b", texto, flags=re.I):
            return False

    for medida in medidas:
        if not _contem_medida_exata(texto, medida):
            return False

    return True


def _filtrar_resultados_por_medidas_da_consulta(resultados, termo):
    """
    Exige todos os termos relevantes quando a consulta tiver dois ou mais.
    Consultas com um único termo continuam amplas.

    Ex.: "soro 500ml" não deve listar:
    - soro 10ml;
    - soro 250ml;
    - saco 1500ml;
    - almotolia 500ml;
    - agua 500ml.
    """
    medidas = _extrair_medidas_obrigatorias_consulta(termo)
    palavras = _extrair_palavras_obrigatorias_consulta(termo)

    if len(medidas) + len(palavras) < 2:
        return resultados

    filtrados = [
        item for item in resultados
        if _resultado_atende_medidas_obrigatorias(item, medidas, palavras)
    ]

    return filtrados




def _aplicar_descricao_fornecedor_exibicao(resultados):
    """
    Define a coluna 'Descrição do Fornecedor' para a tabela Outros Produtos.

    Regra:
    - usar descrição original do fornecedor/preço quando existir;
    - NÃO usar produto_padrao nem sku_master como fallback;
    - se não houver descrição do fornecedor, deixar vazio para o template exibir '—'.
    """
    if not resultados:
        return resultados

    for item in resultados:
        descricao = ""

        for preco in item.get("precos") or []:
            descricao = (
                preco.get("descricao_original")
                or preco.get("descricao_fornecedor")
                or preco.get("descricao")
                or ""
            )
            if descricao:
                break

        item["descricao_fornecedor_exibicao"] = descricao or ""

    return resultados



def _aplicar_descricao_fornecedor_outros(resultados):
    if not resultados:
        return resultados

    for item in resultados:
        item["descricao_fornecedor_exibicao"] = _descricao_fornecedor_do_item(item)

    return resultados



def _deduplicar_outros_produtos_por_sku_fornecedor_fabricante(resultados):
    """
    Consolida 'Outros Produtos Encontrados' na Busca Inteligente.

    Regra ERP:
    - Mesmo SKU_MASTER + mesmo fornecedor + mesmo fabricante/marca = uma linha só.
    - Mantém o item com preço mais recente/importação mais recente quando possível.
    - Não remove dados do banco; apenas evita duplicidade visual na busca.
    """
    if not resultados or len(resultados) <= 1:
        return resultados

    principal = resultados[0]
    outros = resultados[1:]

    def norm(valor):
        return normalizar_texto(str(valor or "")).strip().upper()

    def primeiro_preco(item):
        precos = item.get("precos") or []
        return precos[0] if precos else {}

    def chave(item):
        preco = primeiro_preco(item)

        sku_master = (
            item.get("sku_master_exibicao")
            or item.get("sku_master")
            or item.get("produto_padrao")
            or ""
        )

        fornecedor = (
            item.get("fornecedor_principal")
            or preco.get("fornecedor")
            or preco.get("nome_fornecedor")
            or ""
        )

        fabricante = (
            preco.get("marca")
            or item.get("fabricante")
            or item.get("marca")
            or ""
        )

        return (
            norm(sku_master),
            norm(fornecedor),
            norm(fabricante),
        )

    def ranking_atualidade(item):
        """
        Ordena por evidências de atualização.
        Strings YYYY-MM-DD funcionam bem em comparação lexicográfica.
        Quando existir ID de preço/importação, usa como desempate.
        """
        preco = primeiro_preco(item)

        data = (
            preco.get("data_importacao")
            or preco.get("data_cotacao")
            or item.get("data_importacao")
            or item.get("data_cotacao")
            or ""
        )

        try:
            preco_id = int(
                preco.get("preco_id")
                or preco.get("id")
                or item.get("preco_id")
                or item.get("id")
                or 0
            )
        except Exception:
            preco_id = 0

        try:
            valor = float(
                preco.get("preco")
                if preco.get("preco") is not None
                else item.get("menor_preco") or 999999999
            )
        except Exception:
            valor = 999999999

        # Mais recente primeiro; se empatar, menor preço; se empatar, maior ID.
        return (str(data), -valor, preco_id)

    consolidados = {}

    for item in outros:
        k = chave(item)

        # Se não tem SKU ou fornecedor, não consolida agressivamente.
        if not k[0] or not k[1]:
            k = ("__UNICO__", str(item.get("id") or item.get("sku") or id(item)))

        atual = consolidados.get(k)
        if atual is None:
            consolidados[k] = item
            continue

        if ranking_atualidade(item) > ranking_atualidade(atual):
            consolidados[k] = item

    deduplicados = list(consolidados.values())

    deduplicados.sort(
        key=lambda item: (
            0 if item.get("tem_preco") or item.get("menor_preco") else 1,
            item.get("menor_preco") if item.get("menor_preco") is not None else 999999999,
            norm(item.get("sku_master_exibicao") or item.get("produto_padrao"))
        )
    )

    return [principal] + deduplicados


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
        if item["suspeito_contaminado"] and not item.get("sku_master_corrigido"):
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

        if item["suspeito_contaminado"] and item["sku_pendente_padronizacao"] and not item.get("sku_master_corrigido"):
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

    resultados = _filtrar_resultados_por_medidas_da_consulta(resultados, termo)
    resultados = _normalizar_precos_embalagem_resultados(resultados)
    resultados = _ordenar_outros_produtos_por_preco_unitario(resultados)
    resultados = _aplicar_descricao_fornecedor_outros(resultados)
    resultados = _aplicar_descricao_fornecedor_exibicao(resultados)
    resultados = _deduplicar_outros_produtos_por_sku_fornecedor_fabricante(resultados)
    return resultados[:limite]
