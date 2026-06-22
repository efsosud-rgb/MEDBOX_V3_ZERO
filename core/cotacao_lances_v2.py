from pathlib import Path
import re
import sqlite3
from datetime import datetime

from openpyxl import load_workbook

from core.banco import conectar, normalizar_texto


def configurar_logger_cotacao(logger=None):
    import logging

    # Compatibilidade com app.py:
    # algumas rotas chamam configurar_logger_cotacao(log).
    # Se receber um logger externo, apenas retorna ele.
    if logger is not None:
        return logger

    return logging.getLogger("cotacao_lances_v2")


_log = configurar_logger_cotacao()


def moeda_br(valor):
    try:
        valor = float(valor or 0)
    except Exception:
        valor = 0.0
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def numero_br(valor, padrao=0.0):
    if valor is None:
        return padrao
    if isinstance(valor, (int, float)):
        return float(valor)

    txt = str(valor).strip()
    if not txt:
        return padrao

    txt = txt.replace("R$", "").replace(" ", "")
    if "," in txt:
        txt = txt.replace(".", "").replace(",", ".")

    try:
        return float(txt)
    except Exception:
        return padrao


def norm_header(valor):
    txt = str(valor or "").strip().upper()
    mapa = str.maketrans("ÁÀÂÃÄÉÈÊËÍÌÎÏÓÒÔÕÖÚÙÛÜÇ", "AAAAAEEEEIIIIOOOOOUUUUC")
    txt = txt.translate(mapa)
    txt = re.sub(r"\s+", " ", txt)
    txt = txt.replace(".", "")
    return txt


def norm_busca(valor):
    return normalizar_texto(str(valor or "")).upper().strip()


def achar_coluna(headers, opcoes, parcial=True):
    headers_norm = [norm_header(h) for h in headers]

    for opcao in opcoes:
        op = norm_header(opcao)
        for i, h in enumerate(headers_norm):
            if h == op:
                return i

    if parcial:
        for opcao in opcoes:
            op = norm_header(opcao)
            for i, h in enumerate(headers_norm):
                if op and op in h:
                    return i

    return None


def linha_tem_cabecalho(row):
    headers = list(row)

    col_desc = achar_coluna(headers, [
        "PRODUTO",
        "DESCRICAO",
        "DESCRICAO DO PRODUTO",
        "MEDICAMENTO",
        "ITEM",
    ])

    col_qtd = achar_coluna(headers, [
        "QTDE",
        "QTD",
        "QUANTIDADE",
        "QUANTIDADE NEG",
        "QUANTIDADENEG",
    ])

    return col_desc is not None and col_qtd is not None


def detectar_cabecalho(ws):
    for idx, row in enumerate(ws.iter_rows(values_only=True), start=1):
        if idx > 80:
            break
        if linha_tem_cabecalho(row):
            headers = list(row)
            return {
                "linha": idx,
                "headers": headers,
                "descricao": achar_coluna(headers, ["PRODUTO", "DESCRICAO", "DESCRICAO DO PRODUTO", "MEDICAMENTO", "ITEM"]),
                "quantidade": achar_coluna(headers, ["QTDE", "QTD", "QUANTIDADE", "QUANTIDADE NEG", "QUANTIDADENEG"]),
                "codigo": achar_coluna(headers, ["CODIGO", "COD", "CODIGO PRODUTO", "CODIGO DO PRODUTO"]),
                "unidade": achar_coluna(headers, ["UNIDADE", "UND", "UN"]),
                # OSINFO e última compra só entram se a coluna realmente existir com esse nome.
                "osinfo": achar_coluna(headers, ["PRECO OSINFO", "PREÇO OSINFO", "OSINFO", "VALOR OSINFO"], parcial=False),
                "ultima": achar_coluna(headers, ["ULTIMA COMPRA", "ULTIMA COMP", "ULT COMPRA", "ULT COMP", "ULT COMP DA COTACAO", "ULT COMP DA COTACAO"], parcial=False),
                "menor_lance": achar_coluna(headers, ["MENOR LANCE", "MENOR PRECO OFERTADO", "MENOR PREÇO OFERTADO"]),
                "empresa_lance": achar_coluna(headers, ["EMPRESA MELHOR LANCE", "VENCEDOR", "GANHADOR"]),
            }

    return None


def linha_valida_item(desc):
    txt = str(desc or "").strip()
    if not txt:
        return False

    n = norm_header(txt)
    bloqueios = [
        "PRODUTO",
        "DESCRICAO",
        "TOTAL",
        "TOTAL COTACAO",
        "ELABORADO",
        "APROVADO",
        "GERAR",
        "SALVAR",
        "IMPRIMIR",
        "DATA",
        "CODIGO",
        "UNIDADE",
    ]

    if n in bloqueios:
        return False

    letras = re.sub(r"[^A-Z]", "", n)
    return len(letras) >= 3


def extrair_itens_arquivo(caminho):
    caminho = Path(caminho)
    wb = load_workbook(caminho, data_only=True)
    ws = wb.active

    cab = detectar_cabecalho(ws)
    if not cab:
        return []

    itens = []

    for row in ws.iter_rows(min_row=cab["linha"] + 1, values_only=True):
        desc = row[cab["descricao"]] if cab["descricao"] is not None and cab["descricao"] < len(row) else ""
        desc = str(desc or "").strip()

        if not linha_valida_item(desc):
            continue

        qtd = row[cab["quantidade"]] if cab["quantidade"] is not None and cab["quantidade"] < len(row) else 1
        qtd = numero_br(qtd, 1.0)

        codigo = row[cab["codigo"]] if cab["codigo"] is not None and cab["codigo"] < len(row) else ""
        unidade = row[cab["unidade"]] if cab["unidade"] is not None and cab["unidade"] < len(row) else ""

        osinfo = 0.0
        if cab["osinfo"] is not None and cab["osinfo"] < len(row):
            osinfo = numero_br(row[cab["osinfo"]], 0.0)

        ultima = 0.0
        if cab["ultima"] is not None and cab["ultima"] < len(row):
            ultima = numero_br(row[cab["ultima"]], 0.0)

        menor_lance = 0.0
        if cab["menor_lance"] is not None and cab["menor_lance"] < len(row):
            menor_lance = numero_br(row[cab["menor_lance"]], 0.0)

        empresa = ""
        if cab["empresa_lance"] is not None and cab["empresa_lance"] < len(row):
            empresa = str(row[cab["empresa_lance"]] or "").strip()

        itens.append({
            "codigo_cliente": str(codigo or "").strip(),
            "descricao_cotacao": desc,
            "unidade": str(unidade or "").strip(),
            "quantidade": qtd,
            "preco_osinfo": osinfo,
            "ultima_compra": ultima,
            "menor_lance": menor_lance,
            "empresa_melhor_lance": empresa,
        })

    return itens


def colunas_tabela(conn, tabela):
    cur = conn.cursor()
    try:
        cur.execute(f"PRAGMA table_info({tabela})")
        return {r[1] for r in cur.fetchall()}
    except Exception:
        return set()


def tabela_existe(conn, tabela):
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (tabela,))
    return cur.fetchone() is not None


def carregar_indice_produtos():
    conn = conectar()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cols_prod = colunas_tabela(conn, "produtos")
    tem_sku_master = "sku_master" in cols_prod

    sku_expr = "COALESCE(NULLIF(TRIM(sku_master), ''), produto_padrao)" if tem_sku_master else "produto_padrao"

    cur.execute(f"""
        SELECT
            id,
            sku,
            produto_padrao,
            {sku_expr} AS sku_master_exibicao,
            fabricante,
            categoria
        FROM produtos
        WHERE COALESCE(ativo, 1) = 1
    """)

    produtos = [dict(r) for r in cur.fetchall()]

    # Menor custo por produto.
    precos_por_produto = {}

    if tabela_existe(conn, "precos_fornecedores"):
        cols_pf = colunas_tabela(conn, "precos_fornecedores")
        cols_f = colunas_tabela(conn, "fornecedores")

        marca_col = "pf.marca" if "marca" in cols_pf else "''"
        desc_col = "pf.descricao_original" if "descricao_original" in cols_pf else ("pf.descricao" if "descricao" in cols_pf else "''")
        data_col = "pf.data_cotacao" if "data_cotacao" in cols_pf else ("pf.data_importacao" if "data_importacao" in cols_pf else "''")
        fornecedor_col = "f.nome" if "nome" in cols_f else "''"

        cur.execute(f"""
            SELECT
                pf.produto_id,
                pf.preco,
                {marca_col} AS marca,
                {desc_col} AS descricao_fornecedor,
                {data_col} AS data_preco,
                {fornecedor_col} AS fornecedor
            FROM precos_fornecedores pf
            LEFT JOIN fornecedores f ON f.id = pf.fornecedor_id
            WHERE pf.preco IS NOT NULL AND pf.preco > 0
            ORDER BY pf.produto_id ASC, pf.preco ASC
        """)

        for r in cur.fetchall():
            row = dict(r)
            pid = row["produto_id"]
            if pid not in precos_por_produto:
                precos_por_produto[pid] = row

    conn.close()

    indice = []

    for p in produtos:
        texto_base = " ".join([
            p.get("sku_master_exibicao") or "",
            p.get("produto_padrao") or "",
            p.get("fabricante") or "",
            p.get("categoria") or "",
        ])

        preco = precos_por_produto.get(p["id"]) or {}

        indice.append({
            **p,
            "texto_busca": norm_busca(texto_base),
            "preco": preco,
        })

    return indice


def score_simples(consulta, candidato):
    consulta = norm_busca(consulta)
    candidato = norm_busca(candidato)

    if not consulta or not candidato:
        return 0

    if consulta == candidato:
        return 100

    if consulta in candidato or candidato in consulta:
        return 92

    tokens_q = [t for t in consulta.split() if len(t) >= 2]
    tokens_c = set(candidato.split())

    if not tokens_q:
        return 0

    acertos = sum(1 for t in tokens_q if t in tokens_c)
    cobertura = acertos / len(tokens_q)

    # Penaliza medidas divergentes.
    medidas_q = set(re.findall(r"\b\d+\s*(?:ML|MG|G|MCG|UI|%)\b", consulta))
    medidas_c = set(re.findall(r"\b\d+\s*(?:ML|MG|G|MCG|UI|%)\b", candidato))

    if medidas_q and not medidas_q.issubset(medidas_c):
        cobertura *= 0.45

    return round(cobertura * 100, 2)



def montar_sugestao_sku_lance(produto, score):
    preco = produto.get("preco") or {}
    menor_custo = numero_br(preco.get("preco"), 0.0)

    sku_master = (
        produto.get("sku_master_exibicao")
        or produto.get("produto_padrao")
        or ""
    )

    marca = (
        preco.get("marca")
        or produto.get("fabricante")
        or ""
    )

    fornecedor = preco.get("fornecedor") or ""

    return {
        "sku_master": sku_master,
        "categoria": produto.get("categoria") or "",
        "fornecedor_menor_custo": fornecedor,
        "marca_fabricante": marca,
        "menor_custo_unitario": menor_custo,
        "menor_custo_unitario_formatado": moeda_br(menor_custo) if menor_custo else "",
        "descricao_fornecedor": preco.get("descricao_fornecedor") or "",
        "score": score,
    }


def encontrar_sku_equivalente(descricao, indice, score_minimo=72):
    """
    Busca SKU equivalente, mas evita chute automático em descrições genéricas.

    Regra:
    - Só preenche automático se o melhor score for alto e bem separado do segundo.
    - Se houver empate ou candidatos próximos, retorna REVISAR SKU com sugestões.
    """
    candidatos = []

    for p in indice:
        score = score_simples(descricao, p["texto_busca"])
        if score >= score_minimo:
            candidatos.append((score, p))

    candidatos.sort(key=lambda x: x[0], reverse=True)

    if not candidatos:
        return None, 0, []

    melhor_score, melhor = candidatos[0]
    segundo_score = candidatos[1][0] if len(candidatos) > 1 else 0
    diferenca = melhor_score - segundo_score

    sugestoes = [
        montar_sugestao_sku_lance(produto, score)
        for score, produto in candidatos[:8]
    ]

    # Preenchimento automático somente quando estiver muito seguro.
    # Exemplo seguro: descrição completa com dose/apresentação.
    # Exemplo NÃO seguro: "AGUA DESTILADA", "SORO", "DIPIRONA".
    if melhor_score >= 88 and diferenca >= 8:
        return melhor, melhor_score, []

    return None, melhor_score, sugestoes



def sugerir_skus_lances(termo, limite=12):
    """
    Sugere SKUs para preenchimento manual no módulo de Lances.
    Usado quando o vendedor clica/digita no campo SKU Master.
    """
    termo = str(termo or "").strip()
    if not termo:
        return []

    indice = carregar_indice_produtos()
    candidatos = []

    for p in indice:
        score = score_simples(termo, p.get("texto_busca", ""))
        if score <= 0:
            continue

        # Para autocomplete, aceitamos score menor, mas ordenamos pelos melhores.
        if score >= 35:
            candidatos.append((score, p))

    candidatos.sort(key=lambda x: x[0], reverse=True)

    vistos = set()
    sugestoes = []

    for score, produto in candidatos:
        sugestao = montar_sugestao_sku_lance(produto, score)
        sku = sugestao.get("sku_master", "").strip().upper()

        if not sku or sku in vistos:
            continue

        vistos.add(sku)
        sugestoes.append(sugestao)

        if len(sugestoes) >= int(limite or 12):
            break

    return sugestoes

def status_item(sku_encontrado, menor_custo, preco_medbox, preco_osinfo, ultima_compra, menor_lance):
    if not sku_encontrado:
        return "REVISAR SKU"

    if not menor_custo or menor_custo <= 0:
        return "SEM PREÇO"

    referencias = [v for v in [preco_osinfo, ultima_compra, menor_lance] if v and v > 0]

    if not referencias:
        return "COMPETITIVO"

    return "COMPETITIVO" if preco_medbox <= min(referencias) else "NEGOCIAR"


def analisar_itens_lances(itens, markup_percentual=80, score_minimo=72):
    markup_percentual = numero_br(markup_percentual, 80.0)
    indice = carregar_indice_produtos()

    analisados = []

    for idx, item in enumerate(itens, start=1):
        desc = item["descricao_cotacao"]
        candidato, score, sugestoes_sku = encontrar_sku_equivalente(desc, indice, score_minimo=score_minimo)

        sku_encontrado = candidato is not None

        sku_master = "REVISAR SKU"
        fornecedor = "-"
        fabricante = "-"
        categoria = "-"
        menor_custo = 0.0
        desc_fornecedor = "-"

        if candidato:
            sku_master = candidato.get("sku_master_exibicao") or candidato.get("produto_padrao") or "REVISAR SKU"
            fabricante = candidato.get("fabricante") or "-"
            categoria = candidato.get("categoria") or "-"

            preco = candidato.get("preco") or {}
            menor_custo = numero_br(preco.get("preco"), 0.0)
            fornecedor = preco.get("fornecedor") or "-"
            fabricante = preco.get("marca") or fabricante or "-"
            desc_fornecedor = preco.get("descricao_fornecedor") or "-"

        preco_medbox = round(menor_custo * (1 + markup_percentual / 100), 4) if menor_custo else 0.0

        preco_osinfo = numero_br(item.get("preco_osinfo"), 0.0)
        ultima_compra = numero_br(item.get("ultima_compra"), 0.0)
        menor_lance = numero_br(item.get("menor_lance"), 0.0)

        candidatos_valor = []
        if preco_osinfo > 0:
            candidatos_valor.append(("OSINFO", preco_osinfo))
        if ultima_compra > 0:
            candidatos_valor.append(("Última Compra", ultima_compra))
        if menor_lance > 0:
            candidatos_valor.append((item.get("empresa_melhor_lance") or "Concorrente", menor_lance))
        if preco_medbox > 0:
            candidatos_valor.append(("MedBox", preco_medbox))

        candidatos_valor.sort(key=lambda x: x[1])
        menor_nome, menor_valor = candidatos_valor[0] if candidatos_valor else ("-", 0.0)

        status = status_item(sku_encontrado, menor_custo, preco_medbox, preco_osinfo, ultima_compra, menor_lance)

        analisados.append({
            "item": idx,
            "codigo_cliente": item.get("codigo_cliente", ""),
            "descricao_produto": desc,
            "descricao_cotacao": desc,
            "unidade": item.get("unidade", ""),
            "quantidade": item.get("quantidade", 1),
            "sku_master": sku_master,
            "sku_encontrado": sku_encontrado,
            "score": score,
            "sugestoes_sku": sugestoes_sku,
            "categoria": categoria,
            "descricao_fornecedor": desc_fornecedor,
            "preco_osinfo": preco_osinfo,
            "ultima_compra": ultima_compra,
            "preco_medbox": preco_medbox,
            "markup_atual": markup_percentual if menor_custo else None,
            "menor_preco_ofertado": menor_lance,
            "empresa_melhor_lance": item.get("empresa_melhor_lance", ""),
            "menor_valor": menor_valor,
            "menor_valor_nome": menor_nome,
            "menor_origem": disputa.get("menor_origem", "-"),
            "medbox_vencedora": bool(disputa.get("medbox_vencedora")),
            "classe_osinfo": disputa.get("classe_osinfo", ""),
            "classe_lance": disputa.get("classe_lance", ""),
            "classe_medbox": disputa.get("classe_medbox", ""),
            "menor_custo_unitario": menor_custo if menor_custo else None,
            "fornecedor_menor_custo": fornecedor,
            "marca_fabricante": fabricante,
            "status": status,
            "tem_preco": bool(menor_custo),
            "preco_osinfo_formatado": moeda_br(preco_osinfo),
            "ultima_compra_formatada": moeda_br(ultima_compra),
            "preco_medbox_formatado": moeda_br(preco_medbox),
            "menor_preco_ofertado_formatado": moeda_br(menor_lance),
            "menor_valor_formatado": moeda_br(menor_valor),
            "menor_custo_unitario_formatado": moeda_br(menor_custo) if menor_custo else "-",
            "total_medbox": preco_medbox * item.get("quantidade", 1),
            "total_osinfo": preco_osinfo * item.get("quantidade", 1),
            "total_ultima_compra": ultima_compra * item.get("quantidade", 1),
            "total_menor_valor": menor_valor * item.get("quantidade", 1),
        })

    return {
        "markup_percentual": markup_percentual,
        "itens": analisados,
        "resumo": montar_resumo_lances(analisados),
    }


def montar_resumo_lances(itens):
    total = len(itens)
    com_sku = sum(1 for i in itens if i.get("sku_encontrado"))
    revisar = total - com_sku
    com_preco = sum(1 for i in itens if i.get("tem_preco"))
    sem_preco = total - com_preco
    competitivos = sum(1 for i in itens if i.get("status") == "COMPETITIVO")
    negociar = sum(1 for i in itens if i.get("status") == "NEGOCIAR")
    margens = [i.get("markup_atual") for i in itens if i.get("markup_atual") is not None]

    resumo = {
        "total_itens": total,
        "itens_com_sku": com_sku,
        "itens_revisar_sku": revisar,
        "itens_com_preco_medbox": com_preco,
        "itens_sem_preco": sem_preco,
        "itens_competitivos": competitivos,
        "itens_negociar": negociar,
        "total_osinfo": sum(i.get("total_osinfo", 0) for i in itens),
        "total_ultima_compra": sum(i.get("total_ultima_compra", 0) for i in itens),
        "total_medbox": sum(i.get("total_medbox", 0) for i in itens),
        "total_menor_lance": sum(i.get("menor_preco_ofertado", 0) * i.get("quantidade", 1) for i in itens),
        "total_menor_valor": sum(i.get("total_menor_valor", 0) for i in itens),
        "margem_media_medbox": sum(margens) / len(margens) if margens else 0,
        "valor_total_estimado": sum(i.get("total_medbox", 0) for i in itens),
    }

    for chave in [
        "total_osinfo",
        "total_ultima_compra",
        "total_medbox",
        "total_menor_lance",
        "total_menor_valor",
        "valor_total_estimado",
    ]:
        resumo[f"{chave}_formatado"] = moeda_br(resumo[chave])

    return resumo


def analisar_arquivo_cotacao(caminho, markup_percentual=80):
    caminho = Path(caminho)
    itens = extrair_itens_arquivo(caminho)
    analise = analisar_itens_lances(itens, markup_percentual=markup_percentual)
    analise["arquivo"] = caminho.name
    analise["itens_extraidos"] = len(itens)
    return analise



def extrair_itens_manuais_lance(texto_itens):
    """
    Recebe texto colado/digitado pelo vendedor e transforma cada linha em item de cotação.

    Exemplos aceitos:
    AGUA DESTILADA ESTERIL 10ML - 3000
    CEFAZOLINA SODICA 1G;700
    CEFTRIAXONA 1G IV\t300
    CLORETO DE SODIO 0,9% 500ML
    """
    itens = []

    texto_itens = str(texto_itens or "").strip()
    if not texto_itens:
        return itens

    linhas = [l.strip() for l in texto_itens.splitlines() if l.strip()]

    for linha in linhas:
        original = linha.strip()

        # Remove numeração/bullets no começo, sem remover concentração do produto.
        original = re.sub(r"^\s*[-•*]\s*", "", original)
        original = re.sub(r"^\s*\d+\s*[\).\-\|]\s*", "", original)

        descricao = original
        quantidade = 1

        # Prioridade 1: separadores claros no final: ; qtd | qtd TAB qtd
        partes = re.split(r"\s*(?:;|\||\t)\s*", original)
        if len(partes) >= 2:
            possivel_qtd = partes[-1].strip()
            qtd_num = numero_br(possivel_qtd, None)
            if qtd_num is not None and qtd_num > 0:
                quantidade = qtd_num
                descricao = " ".join(partes[:-1]).strip()

        # Prioridade 2: "descrição - 3000" ou "descrição = 3000"
        if descricao == original:
            m = re.search(r"^(?P<desc>.+?)\s+(?:-|=|:)\s*(?P<qtd>\d+(?:[.,]\d+)?)\s*$", original)
            if m:
                qtd_num = numero_br(m.group("qtd"), None)
                if qtd_num is not None and qtd_num > 0:
                    descricao = m.group("desc").strip()
                    quantidade = qtd_num

        # Prioridade 3: "descrição x 3000" no final
        if descricao == original:
            m = re.search(r"^(?P<desc>.+?)\s+[xX]\s*(?P<qtd>\d+(?:[.,]\d+)?)\s*$", original)
            if m:
                qtd_num = numero_br(m.group("qtd"), None)
                if qtd_num is not None and qtd_num > 0:
                    descricao = m.group("desc").strip()
                    quantidade = qtd_num

        descricao = descricao.strip(" -;|:")
        if not descricao:
            continue

        itens.append({
            "codigo_cliente": "",
            "descricao_cotacao": descricao,
            "unidade": "",
            "quantidade": quantidade,
            "preco_osinfo": 0,
            "ultima_compra": 0,
            "menor_lance": 0,
            "empresa_melhor_lance": "",
        })

    return itens


def analisar_itens_manuais_lance(texto_itens, markup_percentual=80):
    """
    Analisa itens digitados/colados manualmente usando a mesma regra da importação:
    busca SKU Master, menor custo, fornecedor, fabricante, categoria e calcula Preço MedBox.
    """
    itens = extrair_itens_manuais_lance(texto_itens)
    analise = analisar_itens_lances(itens, markup_percentual=markup_percentual)
    analise["arquivo"] = "ITENS MANUAIS"
    analise["itens_extraidos"] = len(itens)
    return analise

def salvar_sku_rapido_lances(descricao_cotacao, sku_master, fornecedor="", fabricante="", categoria=""):
    """
    Correção rápida de SKU dentro do módulo de Lances.
    Mantém a descrição da cotação intacta e salva o SKU Master na base.
    """
    descricao_cotacao = str(descricao_cotacao or "").strip()
    sku_master = str(sku_master or "").strip().upper()
    fornecedor = str(fornecedor or "").strip().upper()
    fabricante = str(fabricante or "").strip().upper()
    categoria = str(categoria or "").strip().upper()

    if not descricao_cotacao:
        return {"ok": False, "erro": "Descrição da cotação vazia."}

    if not sku_master:
        return {"ok": False, "erro": "SKU Master obrigatório."}

    conn = conectar()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cols = colunas_tabela(conn, "produtos")
    tem_sku_master = "sku_master" in cols

    if tem_sku_master:
        cur.execute("""
            SELECT id FROM produtos
            WHERE UPPER(COALESCE(NULLIF(TRIM(sku_master), ''), produto_padrao)) = ?
            LIMIT 1
        """, (sku_master,))
    else:
        cur.execute("""
            SELECT id FROM produtos
            WHERE UPPER(produto_padrao) = ?
            LIMIT 1
        """, (sku_master,))

    row = cur.fetchone()

    if row:
        produto_id = row["id"]

        updates = []
        params = []

        if tem_sku_master:
            updates.append("sku_master = ?")
            params.append(sku_master)

        if "produto_padrao" in cols:
            updates.append("produto_padrao = ?")
            params.append(sku_master)

        if "fabricante" in cols and fabricante:
            updates.append("fabricante = ?")
            params.append(fabricante)

        if "categoria" in cols and categoria:
            updates.append("categoria = ?")
            params.append(categoria)

        if "ativo" in cols:
            updates.append("ativo = 1")

        if updates:
            params.append(produto_id)
            cur.execute(f"UPDATE produtos SET {', '.join(updates)} WHERE id = ?", params)
    else:
        campos = []
        valores = []
        params = []

        def add(campo, valor):
            if campo in cols:
                campos.append(campo)
                valores.append("?")
                params.append(valor)

        add("sku", "")
        add("produto_padrao", sku_master)
        if tem_sku_master:
            add("sku_master", sku_master)
        add("fabricante", fabricante)
        add("categoria", categoria)
        add("ativo", 1)
        add("origem", "lances_cotacao")

        cur.execute(f"""
            INSERT INTO produtos ({", ".join(campos)})
            VALUES ({", ".join(valores)})
        """, params)

        produto_id = cur.lastrowid

    # Equivalência, se tabela existir.
    if tabela_existe(conn, "equivalencias"):
        eq_cols = colunas_tabela(conn, "equivalencias")

        try:
            campos = []
            valores = []
            params = []

            def add_eq(campo, valor):
                if campo in eq_cols:
                    campos.append(campo)
                    valores.append("?")
                    params.append(valor)

            add_eq("produto_id", produto_id)
            add_eq("descricao_equivalente", descricao_cotacao)
            add_eq("descricao", descricao_cotacao)
            add_eq("sku_master", sku_master)
            add_eq("origem", "lances_cotacao")
            add_eq("ativo", 1)

            if campos:
                cur.execute(f"""
                    INSERT INTO equivalencias ({", ".join(campos)})
                    VALUES ({", ".join(valores)})
                """, params)
        except Exception:
            pass

    conn.commit()
    conn.close()

    return {
        "ok": True,
        "produto_id": produto_id,
        "sku_master": sku_master,
        "fornecedor": fornecedor,
        "fabricante": fabricante,
        "categoria": categoria,
    }



# ============================================================
# OVERRIDE FINAL - IMPORTADOR RÁPIDO OAS / LANCES
# Este bloco sobrescreve extrair_itens_arquivo sem depender
# das funções antigas do arquivo.
# ============================================================

def _lances_limpar_texto(valor):
    texto = str(valor or "")
    texto = texto.replace("_x000D_", " ")
    texto = texto.replace("\r", " ").replace("\n", " ")
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


def _lances_header(valor):
    texto = _lances_limpar_texto(valor).upper()
    texto = texto.replace("Ç", "C").replace("Ã", "A").replace("Á", "A")
    texto = texto.replace("É", "E").replace("Í", "I").replace("Ó", "O").replace("Ú", "U")
    texto = re.sub(r"[^A-Z0-9 ]+", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


def _lances_coluna(headers, aliases):
    """
    Localiza coluna respeitando prioridade.
    Ex.: tenta DESCRICAO antes de PRODUTO.
    """
    headers_norm = [_lances_header(h) for h in headers]
    aliases_norm = [_lances_header(a) for a in aliases]

    for alias in aliases_norm:
        for idx, header in enumerate(headers_norm):
            if header == alias:
                return idx

    for alias in aliases_norm:
        for idx, header in enumerate(headers_norm):
            if alias and header and alias in header:
                return idx

    return None


def _lances_detectar_cabecalho_excel(ws, max_linhas=80):
    aliases_desc = [
        "DESCRICAO",
        "DESCRICAO DO PRODUTO",
        "NOME DO PRODUTO",
        "NOME",
        "MEDICAMENTO",
        "ITEM",
        "PRODUTO",
    ]

    aliases_qtd = [
        "QUANTIDADE SOLICITADA",
        "QUANTIDADE ORCADA",
        "QUANTIDADE",
        "QTD",
        "QTDE",
        "QTD.",
        "QTDE.",
    ]

    aliases_unidade = [
        "UNIDADE SOLICITADA",
        "UNIDADE ORCADA",
        "UNIDADE",
        "UND",
        "UN",
        "UM",
    ]

    aliases_osinfo = [
        "OSINFO",
        "PRECO OSINFO",
        "PRECO OS INFO",
        "VALOR OSINFO",
    ]

    aliases_ultima = [
        "ULTIMA COMPRA",
        "ULT COMPRA",
        "ULTIMA COMPRA DA COTACAO",
        "ULT COMPRA DA COTACAO",
    ]

    aliases_menor_lance = [
        "MENOR PRECO",
        "MENOR LANCE",
        "PRECO UNITARIO",
        "VALOR UNITARIO",
    ]

    melhor = None

    for linha_idx, row in enumerate(ws.iter_rows(min_row=1, max_row=max_linhas, values_only=True), start=1):
        headers = [_lances_limpar_texto(v) for v in row]

        col_desc = _lances_coluna(headers, aliases_desc)
        col_qtd = _lances_coluna(headers, aliases_qtd)

        pontos = 0
        if col_desc is not None:
            pontos += 10
        if col_qtd is not None:
            pontos += 10

        # Garante que DESCRICAO vença PRODUTO quando existir.
        headers_norm = [_lances_header(h) for h in headers]
        if "DESCRICAO" in headers_norm:
            col_desc = headers_norm.index("DESCRICAO")
            pontos += 5

        if "QUANTIDADE SOLICITADA" in headers_norm:
            col_qtd = headers_norm.index("QUANTIDADE SOLICITADA")
            pontos += 5

        candidato = {
            "pontos": pontos,
            "linha": linha_idx,
            "headers": headers,
            "descricao": col_desc,
            "quantidade": col_qtd,
            "unidade": _lances_coluna(headers, aliases_unidade),
            "preco_osinfo": _lances_coluna(headers, aliases_osinfo),
            "ultima_compra": _lances_coluna(headers, aliases_ultima),
            "menor_lance": _lances_coluna(headers, aliases_menor_lance),
            "codigo_cliente": _lances_coluna(headers, ["CODIGO", "COD PRODUTO", "CODIGO PRODUTO", "CODITEM"]),
        }

        if melhor is None or candidato["pontos"] > melhor["pontos"]:
            melhor = candidato

        if candidato["pontos"] >= 20:
            return candidato

    return melhor if melhor and melhor["pontos"] >= 15 else None


def _lances_escolher_aba_excel(wb):
    prioridades = [
        "ITENS_ORCAMENTO",
        "ITENS ORCAMENTO",
        "ITENS_ORÇAMENTO",
        "ITENS",
        "ORCAMENTO",
        "ORÇAMENTO",
        "COTACAO",
        "COTAÇÃO",
    ]

    for prioridade in prioridades:
        for ws in wb.worksheets:
            if _lances_header(ws.title) == _lances_header(prioridade):
                cab = _lances_detectar_cabecalho_excel(ws)
                if cab:
                    return ws, cab

    melhor_ws = None
    melhor_cab = None

    for ws in wb.worksheets:
        cab = _lances_detectar_cabecalho_excel(ws)
        if cab and (melhor_cab is None or cab["pontos"] > melhor_cab["pontos"]):
            melhor_ws = ws
            melhor_cab = cab

    return melhor_ws, melhor_cab


def _lances_extrair_excel_rapido(caminho):
    wb = load_workbook(caminho, read_only=True, data_only=True)
    ws, cab = _lances_escolher_aba_excel(wb)

    if not ws or not cab:
        try:
            wb.close()
        except Exception:
            pass
        raise ValueError("Não consegui detectar as colunas DESCRICAO e QUANTIDADE da cotação.")

    itens = []

    for row in ws.iter_rows(min_row=cab["linha"] + 1, values_only=True):
        desc = ""
        if cab["descricao"] is not None and cab["descricao"] < len(row):
            desc = _lances_limpar_texto(row[cab["descricao"]])

        if not desc:
            continue

        desc_norm = norm_busca(desc)

        if len(desc_norm) < 3:
            continue

        if any(x in desc_norm for x in [
            "TOTAL GERAL",
            "OBSERVACOES",
            "CONDICAO DE PAGAMENTO",
            "TRANSPORTADORA",
            "VALIDADE",
            "PRECO UNITARIO",
            "VALOR TOTAL",
        ]):
            continue

        qtd = 1
        if cab["quantidade"] is not None and cab["quantidade"] < len(row):
            qtd = numero_br(row[cab["quantidade"]], 1)

        unidade = ""
        if cab.get("unidade") is not None and cab["unidade"] < len(row):
            unidade = _lances_limpar_texto(row[cab["unidade"]])

        preco_osinfo = 0
        if cab.get("preco_osinfo") is not None and cab["preco_osinfo"] < len(row):
            preco_osinfo = numero_br(row[cab["preco_osinfo"]], 0)

        ultima_compra = 0
        if cab.get("ultima_compra") is not None and cab["ultima_compra"] < len(row):
            ultima_compra = numero_br(row[cab["ultima_compra"]], 0)

        menor_lance = 0
        if cab.get("menor_lance") is not None and cab["menor_lance"] < len(row):
            menor_lance = numero_br(row[cab["menor_lance"]], 0)

        codigo = ""
        if cab.get("codigo_cliente") is not None and cab["codigo_cliente"] < len(row):
            codigo = _lances_limpar_texto(row[cab["codigo_cliente"]])

        itens.append({
            "codigo_cliente": codigo,
            "descricao_cotacao": desc.upper(),
            "unidade": unidade.upper(),
            "quantidade": qtd,
            "preco_osinfo": preco_osinfo,
            "ultima_compra": ultima_compra,
            "menor_lance": menor_lance,
            "empresa_melhor_lance": "",
        })

    try:
        wb.close()
    except Exception:
        pass

    return itens


def _lances_texto_pdf(caminho):
    try:
        from pypdf import PdfReader
    except Exception:
        try:
            from PyPDF2 import PdfReader
        except Exception:
            raise ValueError("Para importar PDF, instale: pip install pypdf")

    reader = PdfReader(str(caminho))
    textos = []

    for page in reader.pages:
        try:
            textos.append(page.extract_text() or "")
        except Exception:
            continue

    return "\n".join(textos)


def _lances_extrair_pdf_rapido(caminho):
    texto = _lances_texto_pdf(caminho)
    texto = texto.replace("\r", "\n")
    linhas = [_lances_limpar_texto(l) for l in texto.splitlines() if _lances_limpar_texto(l)]

    texto_unico = " ".join(linhas)
    texto_unico = re.sub(r"\s+", " ", texto_unico).strip()

    itens = []
    vistos = set()

    unidades = r"(?:AMP|FR|COMP|TB|SER|UN|ENV|CP|F/A|FA|UND|CX|PCT|BISN|BOL)"

    pattern = re.compile(
        rf"(?P<item>\b\d{{1,3}}\b)\s+"
        rf"(?:(?P<unidade1>{unidades})\s+)?"
        rf"(?P<desc>[A-ZÁÉÍÓÚÂÊÔÃÕÇ0-9,./%+\-\s]{{8,220}}?)\s+"
        rf"(?P<qtd>\d{{1,7}},\d{{1,4}})"
        rf"(?:\s+(?P<unidade2>{unidades}))?",
        re.IGNORECASE
    )

    for m in pattern.finditer(texto_unico):
        desc = _lances_limpar_texto(m.group("desc"))
        desc = re.sub(r"^\d{5,}\s+", "", desc).strip()
        desc = re.sub(r"^\d{3}\s+", "", desc).strip()

        desc_norm = norm_busca(desc)

        if len(desc_norm) < 5:
            continue

        if any(x in desc_norm for x in [
            "PRECO UN",
            "PRECO TOTAL",
            "NOME UND",
            "DATA LIMITE",
            "PEDIDO DE COTACAO",
        ]):
            continue

        qtd = numero_br(m.group("qtd"), 1)
        unidade = (m.group("unidade1") or m.group("unidade2") or "").upper()

        chave = (desc_norm, qtd)
        if chave in vistos:
            continue

        vistos.add(chave)

        itens.append({
            "codigo_cliente": "",
            "descricao_cotacao": desc.upper(),
            "unidade": unidade,
            "quantidade": qtd,
            "preco_osinfo": 0,
            "ultima_compra": 0,
            "menor_lance": 0,
            "empresa_melhor_lance": "",
        })

    if not itens:
        raise ValueError("Não consegui extrair itens do PDF. Se for imagem/escaneado, será necessário OCR.")

    return itens


def extrair_itens_arquivo(caminho):
    caminho = Path(caminho)
    ext = caminho.suffix.lower()

    if ext in [".xlsx", ".xlsm", ".xltx", ".xltm"]:
        return _lances_extrair_excel_rapido(caminho)

    if ext == ".pdf":
        return _lances_extrair_pdf_rapido(caminho)

    raise ValueError(f"Formato não suportado: {ext}. Use Excel ou PDF pesquisável.")





# ============================================================
# OVERRIDE FINAL - FUNÇÕES BASE DO ÍNDICE RÁPIDO DE LANCES
# Necessário para analisar cotações grandes sem varrer a base inteira.
# ============================================================

_CACHE_TOKEN_MAP_LANCES = None
_CACHE_INDICE_RAPIDO_LANCES = None

_STOPWORDS_LANCES = {
    "DE", "DA", "DO", "DAS", "DOS", "E", "EM", "PARA", "COM", "SEM",
    "USO", "SOL", "SOLUCAO", "SOLUÇÃO", "INJETAVEL", "INJETÁVEL",
    "COMPRIMIDO", "COMP", "FRASCO", "AMPOLA", "AMP", "FR", "UN",
    "UND", "ORAL", "IV", "IM", "SC", "PO", "SODICA", "SODICO",
    "CLORIDRATO", "DISSODICO", "FOSFATO"
}


def _tokens_lances(texto):
    texto = norm_busca(texto)
    tokens = []

    for t in texto.split():
        t = t.strip()

        if len(t) < 3:
            continue

        if t in _STOPWORDS_LANCES:
            continue

        tokens.append(t)

    return tokens


def _montar_indice_rapido_lances():
    global _CACHE_TOKEN_MAP_LANCES, _CACHE_INDICE_RAPIDO_LANCES

    if _CACHE_TOKEN_MAP_LANCES is not None and _CACHE_INDICE_RAPIDO_LANCES is not None:
        return _CACHE_INDICE_RAPIDO_LANCES, _CACHE_TOKEN_MAP_LANCES

    indice = carregar_indice_produtos()
    token_map = {}

    for produto in indice:
        texto = produto.get("texto_busca", "")
        tokens = set(_tokens_lances(texto))

        produto["_tokens_rapidos"] = tokens

        for token in tokens:
            if token not in token_map:
                token_map[token] = []
            token_map[token].append(produto)

    _CACHE_INDICE_RAPIDO_LANCES = indice
    _CACHE_TOKEN_MAP_LANCES = token_map

    return indice, token_map


def _candidatos_rapidos_lances(descricao, limite=80):
    indice, token_map = _montar_indice_rapido_lances()

    tokens = _tokens_lances(descricao)

    if not tokens:
        return []

    contagem = {}

    for token in tokens:
        produtos = token_map.get(token, [])

        for produto in produtos:
            chave = id(produto)

            if chave not in contagem:
                contagem[chave] = [0, produto]

            contagem[chave][0] += 1

    if not contagem:
        return []

    candidatos = sorted(
        contagem.values(),
        key=lambda x: x[0],
        reverse=True
    )

    return [produto for _, produto in candidatos[:limite]]


def limpar_cache_lances():
    global _CACHE_INDICE_LANCES, _CACHE_TOKEN_MAP_LANCES, _CACHE_INDICE_RAPIDO_LANCES

    try:
        _CACHE_INDICE_LANCES = None
    except Exception:
        pass

    _CACHE_TOKEN_MAP_LANCES = None
    _CACHE_INDICE_RAPIDO_LANCES = None


# ============================================================
# OVERRIDE FINAL - ANÁLISE EM MASSA RÁPIDA
# Na importação grande, não monta sugestões para cada item.
# As sugestões ficam sob demanda no autocomplete do campo SKU.
# ============================================================

def encontrar_sku_automatico_rapido_lances(descricao, score_minimo=72):
    """
    Busca apenas preenchimento automático seguro.
    Não retorna sugestões em massa para não travar cotações grandes.
    """
    candidatos_produtos = _candidatos_rapidos_lances(descricao, limite=80)

    if not candidatos_produtos:
        return None, 0

    candidatos = []

    for produto in candidatos_produtos:
        score = score_simples(descricao, produto.get("texto_busca", ""))

        if score >= score_minimo:
            candidatos.append((score, produto))

    candidatos.sort(key=lambda x: x[0], reverse=True)

    if not candidatos:
        return None, 0

    melhor_score, melhor = candidatos[0]
    segundo_score = candidatos[1][0] if len(candidatos) > 1 else 0
    diferenca = melhor_score - segundo_score

    # Continua evitando chute:
    # só preenche automático se o melhor for bem superior.
    if melhor_score >= 88 and diferenca >= 8:
        return melhor, melhor_score

    return None, melhor_score


def analisar_itens_lances(itens, markup_percentual=80, score_minimo=72):
    """
    Versão otimizada para importação de cotações grandes.

    Diferença principal:
    - não gera sugestoes_sku em massa;
    - deixa sugestoes_sku vazio;
    - o vendedor busca sugestões sob demanda ao clicar no campo SKU Master.
    """
    markup_percentual = numero_br(markup_percentual, 80.0)

    # Garante que o índice rápido seja montado uma única vez.
    _montar_indice_rapido_lances()

    analisados = []

    for idx, item in enumerate(itens, start=1):
        desc = item["descricao_cotacao"]
        candidato, score = encontrar_sku_automatico_rapido_lances(
            desc,
            score_minimo=score_minimo
        )

        sku_encontrado = candidato is not None

        sku_master = "REVISAR SKU"
        fornecedor = "-"
        fabricante = "-"
        categoria = "-"
        menor_custo = 0.0
        desc_fornecedor = "-"

        if candidato:
            sku_master = candidato.get("sku_master_exibicao") or candidato.get("produto_padrao") or "REVISAR SKU"
            fabricante = candidato.get("fabricante") or "-"
            categoria = candidato.get("categoria") or "-"

            preco = candidato.get("preco") or {}
            menor_custo = numero_br(preco.get("preco"), 0.0)
            fornecedor = preco.get("fornecedor") or "-"
            fabricante = preco.get("marca") or fabricante or "-"
            desc_fornecedor = preco.get("descricao_fornecedor") or "-"

        preco_medbox = round(menor_custo * (1 + markup_percentual / 100), 4) if menor_custo else 0.0

        preco_osinfo = numero_br(item.get("preco_osinfo"), 0.0)
        ultima_compra = numero_br(item.get("ultima_compra"), 0.0)
        menor_lance = numero_br(item.get("menor_lance"), 0.0)

        disputa = calcular_disputa_precos_lances(
            preco_osinfo=preco_osinfo,
            menor_lance=menor_lance,
            preco_medbox=preco_medbox,
            empresa_melhor_lance=item.get("empresa_melhor_lance", "")
        )

        menor_nome = disputa.get("menor_empresa") or "-"
        menor_valor = disputa.get("menor_valor") or 0.0

        status = status_item(
            sku_encontrado,
            menor_custo,
            preco_medbox,
            preco_osinfo,
            ultima_compra,
            menor_lance
        )

        qtd = item.get("quantidade", 1)
        qtd = numero_br(qtd, 1)

        analisados.append({
            "item": idx,
            "codigo_cliente": item.get("codigo_cliente", ""),
            "descricao_produto": desc,
            "descricao_cotacao": desc,
            "unidade": item.get("unidade", ""),
            "quantidade": qtd,
            "sku_master": sku_master,
            "sku_encontrado": sku_encontrado,
            "score": score,
            "sugestoes_sku": [],
            "categoria": categoria,
            "descricao_fornecedor": desc_fornecedor,
            "preco_osinfo": preco_osinfo,
            "ultima_compra": ultima_compra,
            "preco_medbox": preco_medbox,
            "markup_atual": markup_percentual if menor_custo else None,
            "menor_preco_ofertado": menor_lance,
            "empresa_melhor_lance": item.get("empresa_melhor_lance", ""),
            "menor_valor": menor_valor,
            "menor_valor_nome": menor_nome,
            "menor_custo_unitario": menor_custo if menor_custo else None,
            "fornecedor_menor_custo": fornecedor,
            "marca_fabricante": fabricante,
            "status": status,
            "tem_preco": bool(menor_custo),
            "preco_osinfo_formatado": moeda_br(preco_osinfo),
            "ultima_compra_formatada": moeda_br(ultima_compra),
            "preco_medbox_formatado": moeda_br(preco_medbox),
            "menor_preco_ofertado_formatado": moeda_br(menor_lance),
            "menor_valor_formatado": moeda_br(menor_valor),
            "menor_custo_unitario_formatado": moeda_br(menor_custo) if menor_custo else "-",
            "total_medbox": preco_medbox * qtd,
            "total_osinfo": preco_osinfo * qtd,
            "total_ultima_compra": ultima_compra * qtd,
            "total_menor_valor": menor_valor * qtd,
        })

    return {
        "markup_percentual": markup_percentual,
        "itens": analisados,
        "resumo": montar_resumo_lances(analisados),
    }



# ============================================================
# OVERRIDE FINAL - COMPARATIVO OSINFO x LANCE x MEDBOX
# Regra:
# - mostra os três preços quando existirem;
# - destaca automaticamente o menor;
# - vencedor só é MedBox se Preço MedBox for o menor preço válido.
# ============================================================

def calcular_disputa_precos_lances(preco_osinfo=0, menor_lance=0, preco_medbox=0, empresa_melhor_lance=""):
    preco_osinfo = numero_br(preco_osinfo, 0.0)
    menor_lance = numero_br(menor_lance, 0.0)
    preco_medbox = numero_br(preco_medbox, 0.0)

    opcoes = []

    if preco_osinfo > 0:
        opcoes.append({
            "origem": "OSINFO",
            "empresa": "OSINFO",
            "valor": preco_osinfo,
        })

    if menor_lance > 0:
        opcoes.append({
            "origem": "LANCE",
            "empresa": empresa_melhor_lance or "LANCE GANHADOR",
            "valor": menor_lance,
        })

    if preco_medbox > 0:
        opcoes.append({
            "origem": "MEDBOX",
            "empresa": "MEDBOX",
            "valor": preco_medbox,
        })

    if not opcoes:
        return {
            "menor_origem": "-",
            "menor_empresa": "-",
            "menor_valor": 0.0,
            "medbox_vencedora": False,
            "classe_osinfo": "",
            "classe_lance": "",
            "classe_medbox": "",
        }

    opcoes.sort(key=lambda x: x["valor"])
    vencedor = opcoes[0]

    return {
        "menor_origem": vencedor["origem"],
        "menor_empresa": vencedor["empresa"],
        "menor_valor": vencedor["valor"],
        "medbox_vencedora": vencedor["origem"] == "MEDBOX",
        "classe_osinfo": "menor-oferta" if vencedor["origem"] == "OSINFO" else "",
        "classe_lance": "menor-oferta" if vencedor["origem"] == "LANCE" else "",
        "classe_medbox": "menor-oferta" if vencedor["origem"] == "MEDBOX" else "",
    }


def status_item(sku_encontrado, menor_custo, preco_medbox, preco_osinfo, ultima_compra, menor_lance):
    disputa = calcular_disputa_precos_lances(
        preco_osinfo=preco_osinfo,
        menor_lance=menor_lance,
        preco_medbox=preco_medbox,
        empresa_melhor_lance=""
    )

    if not sku_encontrado:
        return "REVISAR SKU"

    if not menor_custo:
        return "SEM PREÇO"

    if disputa.get("medbox_vencedora"):
        return "MEDBOX VENCE"

    if disputa.get("menor_origem") in ["OSINFO", "LANCE"]:
        return "NEGOCIAR"

    return "COMPETITIVO"


