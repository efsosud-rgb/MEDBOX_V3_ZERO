from datetime import datetime
from pathlib import Path
import sqlite3
import re

from core.banco import conectar


CLIENTES_FIXOS_MAPA = [
    ("VIVA RIO", 1),
    ("AFNE", 2),
    ("HD CID ADEMAR", 3),
    ("HD SANTO AMARO", 4),
    ("HOSP GUARAPIRANGA", 5),
    ("UPA SANTO AMARO", 6),
    ("INTS", 7),
    ("SOLAR", 8),
    ("IGEDES", 9),
]


def moeda_br(valor):
    try:
        valor = float(valor or 0)
    except Exception:
        valor = 0.0
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def criar_tabelas_mapa_precos_clientes():
    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS clientes_mapa_precos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL UNIQUE,
            fixo_mapa INTEGER DEFAULT 0,
            ordem_mapa INTEGER DEFAULT 999,
            ativo INTEGER DEFAULT 1,
            criado_em TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS cotacoes_clientes_mapa (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente_id INTEGER NOT NULL,
            data_referencia TEXT,
            meses_referencia REAL DEFAULT 1,
            arquivo_origem TEXT,
            observacao TEXT,
            criado_em TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(cliente_id) REFERENCES clientes_mapa_precos(id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS cotacoes_clientes_mapa_itens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cotacao_id INTEGER NOT NULL,
            cliente_id INTEGER NOT NULL,
            produto_id INTEGER,
            descricao_original TEXT,
            sku_master TEXT,
            categoria TEXT,
            quantidade_total REAL DEFAULT 0,
            meses_referencia REAL DEFAULT 1,
            quantidade_mensal REAL DEFAULT 0,
            valor_unitario REAL DEFAULT 0,
            valor_total REAL DEFAULT 0,
            arquivo_origem TEXT,
            criado_em TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(cotacao_id) REFERENCES cotacoes_clientes_mapa(id),
            FOREIGN KEY(cliente_id) REFERENCES clientes_mapa_precos(id),
            FOREIGN KEY(produto_id) REFERENCES produtos(id)
        )
    """)

    conn.commit()
    conn.close()


def garantir_clientes_fixos_mapa():
    criar_tabelas_mapa_precos_clientes()

    conn = conectar()
    cur = conn.cursor()

    for nome, ordem in CLIENTES_FIXOS_MAPA:
        cur.execute("""
            INSERT INTO clientes_mapa_precos (nome, fixo_mapa, ordem_mapa, ativo)
            VALUES (?, 1, ?, 1)
            ON CONFLICT(nome) DO UPDATE SET
                fixo_mapa = 1,
                ordem_mapa = excluded.ordem_mapa,
                ativo = 1
        """, (nome, ordem))

    conn.commit()
    conn.close()


def listar_clientes_mapa_precos():
    garantir_clientes_fixos_mapa()

    conn = conectar()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("""
        SELECT id, nome, fixo_mapa, ordem_mapa, ativo
        FROM clientes_mapa_precos
        WHERE ativo = 1
        ORDER BY fixo_mapa DESC, ordem_mapa ASC, nome ASC
    """)

    clientes = [dict(row) for row in cur.fetchall()]
    conn.close()
    return clientes


def clientes_colunas_mapa():
    """
    Retorna exatamente 15 posições:
    - 9 clientes fixos
    - 6 variáveis por maior volume mensal importado
    """
    garantir_clientes_fixos_mapa()

    conn = conectar()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("""
        SELECT id, nome, 1 AS fixo, ordem_mapa
        FROM clientes_mapa_precos
        WHERE ativo = 1 AND fixo_mapa = 1
        ORDER BY ordem_mapa ASC
    """)
    fixos = [dict(row) for row in cur.fetchall()]

    cur.execute("""
        SELECT 
            c.id,
            c.nome,
            0 AS fixo,
            999 AS ordem_mapa,
            COALESCE(SUM(i.quantidade_mensal), 0) AS volume_mensal
        FROM clientes_mapa_precos c
        LEFT JOIN cotacoes_clientes_mapa_itens i ON i.cliente_id = c.id
        WHERE c.ativo = 1
          AND COALESCE(c.fixo_mapa, 0) = 0
        GROUP BY c.id, c.nome
        ORDER BY volume_mensal DESC, c.nome ASC
        LIMIT 6
    """)
    variaveis = [dict(row) for row in cur.fetchall()]

    conn.close()

    colunas = fixos[:9] + variaveis[:6]

    while len(colunas) < 15:
        colunas.append({
            "id": None,
            "nome": f"CLIENTE VARIÁVEL {len(colunas) - 8}",
            "fixo": 0,
            "ordem_mapa": 999,
            "placeholder": True,
        })

    return colunas[:15]


def resumo_mapa_precos_clientes():
    garantir_clientes_fixos_mapa()

    conn = conectar()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) AS total FROM clientes_mapa_precos WHERE ativo = 1")
    total_clientes = cur.fetchone()["total"]

    cur.execute("SELECT COUNT(*) AS total FROM cotacoes_clientes_mapa")
    total_cotacoes = cur.fetchone()["total"]

    cur.execute("SELECT COUNT(*) AS total FROM cotacoes_clientes_mapa_itens")
    total_itens = cur.fetchone()["total"]

    cur.execute("SELECT COALESCE(SUM(quantidade_mensal), 0) AS total FROM cotacoes_clientes_mapa_itens")
    demanda_mensal_total = float(cur.fetchone()["total"] or 0)

    cur.execute("SELECT COALESCE(SUM(quantidade_mensal * valor_unitario), 0) AS total FROM cotacoes_clientes_mapa_itens")
    faturamento_estimado = float(cur.fetchone()["total"] or 0)

    conn.close()

    return {
        "total_clientes": total_clientes,
        "total_cotacoes": total_cotacoes,
        "total_itens": total_itens,
        "demanda_mensal_total": demanda_mensal_total,
        "faturamento_estimado": faturamento_estimado,
        "faturamento_estimado_formatado": moeda_br(faturamento_estimado),
    }


def mapa_consolidado_vazio():
    """
    Fase 1: estrutura pronta.
    Fase 2: será preenchido com importação e cruzamento com SKU Master.
    """
    return []


def dados_tela_mapa_precos_clientes():
    garantir_clientes_fixos_mapa()

    return {
        "resumo_mapa": resumo_mapa_precos_clientes(),
        "clientes": listar_clientes_mapa_precos(),
        "clientes_colunas": clientes_colunas_mapa(),
        "itens": mapa_consolidado_vazio(),
        "markup_percentual": 80,
    }


# ============================================================
# FASE 2 - IMPORTAÇÃO E CONSOLIDAÇÃO DO MAPA
# ============================================================

def normalizar_texto_mapa(valor):
    import unicodedata
    texto = str(valor or "").strip().upper()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = texto.replace("Ç", "C")
    texto = re.sub(r"\s+", " ", texto)
    return texto.strip()


def converter_float_mapa(valor):
    if valor is None:
        return 0.0

    if isinstance(valor, (int, float)):
        return float(valor)

    texto = str(valor).strip()
    texto = texto.replace("R$", "").replace(" ", "")

    if not texto:
        return 0.0

    # Ex.: 1.234,56
    if "," in texto and "." in texto:
        texto = texto.replace(".", "").replace(",", ".")
    else:
        texto = texto.replace(",", ".")

    texto = re.sub(r"[^0-9.\-]", "", texto)

    try:
        return float(texto)
    except Exception:
        return 0.0


def formatar_quantidade_mapa(valor):
    try:
        valor = float(valor or 0)
    except Exception:
        valor = 0.0

    if valor == int(valor):
        return f"{int(valor):,}".replace(",", ".")
    return f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def obter_ou_criar_cliente_mapa(nome):
    nome = normalizar_texto_mapa(nome)

    if not nome:
        raise ValueError("Nome do cliente não pode ficar vazio.")

    garantir_clientes_fixos_mapa()

    conn = conectar()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("""
        SELECT id, nome
        FROM clientes_mapa_precos
        WHERE UPPER(TRIM(nome)) = UPPER(TRIM(?))
        LIMIT 1
    """, (nome,))
    row = cur.fetchone()

    if row:
        cliente_id = row["id"]
    else:
        cur.execute("""
            INSERT INTO clientes_mapa_precos (nome, fixo_mapa, ordem_mapa, ativo)
            VALUES (?, 0, 999, 1)
        """, (nome,))
        cliente_id = cur.lastrowid

    conn.commit()
    conn.close()
    return cliente_id


def _detectar_colunas_cotacao_cliente(cabecalhos):
    normalizados = [normalizar_texto_mapa(c) for c in cabecalhos]

    def achar(possiveis):
        for termo in possiveis:
            termo_n = normalizar_texto_mapa(termo)
            for idx, cab in enumerate(normalizados):
                if termo_n in cab:
                    return idx
        return None

    col_desc = achar([
        "PRODUTO",
        "DESCRICAO",
        "DESCRICAO DO PRODUTO",
        "ITEM",
        "MATERIAL",
        "COTACAO MEDICAMENTO",
        "COTACAO",
    ])

    col_qtd = achar([
        "QUANTIDADE",
        "QUANT",
        "QTDE",
        "QTD",
        "QTD TOTAL",
        "DEMANDA",
        "CONSUMO",
    ])

    col_valor = achar([
        "VALOR UNITARIO",
        "VALOR UNIT",
        "VALOR",
        "PRECO UNITARIO",
        "PRECO UNIT",
        "PRECO",
        "VL UNIT",
        "UNITARIO",
    ])

    col_categoria = achar([
        "CATEGORIA",
        "GRUPO",
        "CLASSE",
    ])

    col_sku = achar([
        "SKU MASTER",
        "SKU_MASTER",
        "SKU",
        "PRODUTO PADRONIZADO",
    ])

    return {
        "descricao": col_desc,
        "quantidade": col_qtd,
        "valor_unitario": col_valor,
        "categoria": col_categoria,
        "sku_master": col_sku,
    }


def _linha_util_mapa(row):
    preenchidos = [c for c in row if str(c or "").strip()]
    return len(preenchidos) >= 2


def _localizar_produto_mapa(cursor, descricao, sku_master=""):
    descricao_n = normalizar_texto_mapa(descricao)
    sku_n = normalizar_texto_mapa(sku_master)

    if not descricao_n and not sku_n:
        return None

    # 1) SKU Master exato
    if sku_n:
        cursor.execute("""
            SELECT id, produto_padrao, sku_master, fabricante, categoria
            FROM produtos
            WHERE ativo = 1
              AND UPPER(TRIM(COALESCE(sku_master, ''))) = UPPER(TRIM(?))
            ORDER BY id
            LIMIT 1
        """, (sku_n,))
        row = cursor.fetchone()
        if row:
            return dict(row)

    # 2) Produto padrão exato
    cursor.execute("""
        SELECT id, produto_padrao, sku_master, fabricante, categoria
        FROM produtos
        WHERE ativo = 1
          AND UPPER(TRIM(COALESCE(produto_padrao, ''))) = UPPER(TRIM(?))
        ORDER BY id
        LIMIT 1
    """, (descricao_n,))
    row = cursor.fetchone()
    if row:
        return dict(row)

    # 3) Descrição original já vinculada em preço de fornecedor
    cursor.execute("""
        SELECT p.id, p.produto_padrao, p.sku_master, p.fabricante, p.categoria
        FROM precos_fornecedores pf
        JOIN produtos p ON p.id = pf.produto_id
        WHERE p.ativo = 1
          AND UPPER(TRIM(COALESCE(pf.descricao_original, ''))) = UPPER(TRIM(?))
        ORDER BY p.id
        LIMIT 1
    """, (descricao_n,))
    row = cursor.fetchone()
    if row:
        return dict(row)

    return None


def _menor_preco_medbox(cursor, produto_id):
    if not produto_id:
        return {
            "menor_preco": 0,
            "fornecedor": "",
            "fabricante": "",
        }

    cursor.execute("""
        SELECT 
            pf.preco,
            pf.marca,
            f.nome AS fornecedor
        FROM precos_fornecedores pf
        LEFT JOIN fornecedores f ON f.id = pf.fornecedor_id
        WHERE pf.produto_id = ?
          AND COALESCE(pf.preco, 0) > 0
        ORDER BY pf.preco ASC
        LIMIT 1
    """, (produto_id,))
    row = cursor.fetchone()

    if not row:
        return {
            "menor_preco": 0,
            "fornecedor": "",
            "fabricante": "",
        }

    return {
        "menor_preco": float(row["preco"] or 0),
        "fornecedor": row["fornecedor"] or "",
        "fabricante": row["marca"] or "",
    }


def importar_cotacao_cliente_mapa(
    caminho,
    cliente_id=None,
    nome_cliente_novo="",
    meses_referencia=1,
    data_referencia="",
    observacao="",
):
    from openpyxl import load_workbook
    from werkzeug.utils import secure_filename

    criar_tabelas_mapa_precos_clientes()
    garantir_clientes_fixos_mapa()

    meses_referencia = converter_float_mapa(meses_referencia)
    if meses_referencia <= 0:
        meses_referencia = 1

    if nome_cliente_novo:
        cliente_id = obter_ou_criar_cliente_mapa(nome_cliente_novo)
    elif cliente_id:
        cliente_id = int(cliente_id)
    else:
        raise ValueError("Selecione um cliente ou informe um novo cliente.")

    caminho = Path(caminho)
    arquivo_origem = secure_filename(caminho.name)

    wb = load_workbook(caminho, data_only=True, read_only=True)
    ws = wb.active

    linhas = list(ws.iter_rows(values_only=True))
    wb.close()

    if not linhas:
        raise ValueError("A planilha está vazia.")

    melhor_linha_header = None
    melhor_colunas = None
    melhor_score = -1

    for idx, row in enumerate(linhas[:25]):
        cabecalhos = [str(c or "").strip() for c in row]
        colunas = _detectar_colunas_cotacao_cliente(cabecalhos)

        score = 0
        if colunas["descricao"] is not None:
            score += 3
        if colunas["quantidade"] is not None:
            score += 2
        if colunas["valor_unitario"] is not None:
            score += 1

        if score > melhor_score:
            melhor_score = score
            melhor_linha_header = idx
            melhor_colunas = colunas

    if not melhor_colunas or melhor_colunas["descricao"] is None or melhor_colunas["quantidade"] is None:
        raise ValueError(
            "Não consegui identificar as colunas de Produto/Descrição e Quantidade. "
            "A planilha precisa ter pelo menos essas duas colunas."
        )

    conn = conectar()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO cotacoes_clientes_mapa (
            cliente_id,
            data_referencia,
            meses_referencia,
            arquivo_origem,
            observacao
        )
        VALUES (?, ?, ?, ?, ?)
    """, (
        cliente_id,
        str(data_referencia or "").strip(),
        meses_referencia,
        arquivo_origem,
        str(observacao or "").strip(),
    ))

    cotacao_id = cur.lastrowid

    total_linhas = 0
    total_importado = 0
    total_sem_sku = 0
    erros = []

    inicio = melhor_linha_header + 1

    for pos, row in enumerate(linhas[inicio:], start=inicio + 1):
        if not _linha_util_mapa(row):
            continue

        total_linhas += 1

        def valor_coluna(nome):
            idx = melhor_colunas.get(nome)
            if idx is None:
                return ""
            if idx >= len(row):
                return ""
            return row[idx]

        descricao = normalizar_texto_mapa(valor_coluna("descricao"))
        sku_master_informado = normalizar_texto_mapa(valor_coluna("sku_master"))
        categoria_informada = normalizar_texto_mapa(valor_coluna("categoria"))

        quantidade_total = converter_float_mapa(valor_coluna("quantidade"))
        valor_unitario = converter_float_mapa(valor_coluna("valor_unitario"))

        if not descricao:
            continue

        if quantidade_total <= 0:
            erros.append(f"Linha {pos}: quantidade inválida para {descricao[:60]}")
            continue

        produto = _localizar_produto_mapa(cur, descricao, sku_master_informado)

        produto_id = None
        sku_master_final = sku_master_informado
        categoria_final = categoria_informada

        if produto:
            produto_id = produto.get("id")
            sku_master_final = normalizar_texto_mapa(produto.get("sku_master") or produto.get("produto_padrao") or sku_master_final)
            categoria_final = normalizar_texto_mapa(produto.get("categoria") or categoria_final)
        else:
            total_sem_sku += 1
            sku_master_final = sku_master_final or ""

        quantidade_mensal = quantidade_total / meses_referencia
        valor_total = quantidade_total * valor_unitario

        cur.execute("""
            INSERT INTO cotacoes_clientes_mapa_itens (
                cotacao_id,
                cliente_id,
                produto_id,
                descricao_original,
                sku_master,
                categoria,
                quantidade_total,
                meses_referencia,
                quantidade_mensal,
                valor_unitario,
                valor_total,
                arquivo_origem
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            cotacao_id,
            cliente_id,
            produto_id,
            descricao,
            sku_master_final,
            categoria_final,
            quantidade_total,
            meses_referencia,
            quantidade_mensal,
            valor_unitario,
            valor_total,
            arquivo_origem,
        ))

        total_importado += 1

    conn.commit()
    conn.close()

    return {
        "cotacao_id": cotacao_id,
        "cliente_id": cliente_id,
        "arquivo": arquivo_origem,
        "meses_referencia": meses_referencia,
        "total_linhas": total_linhas,
        "total_importado": total_importado,
        "total_sem_sku": total_sem_sku,
        "erros": erros[:20],
    }


def listar_cotacoes_mapa_precos(limite=20):
    criar_tabelas_mapa_precos_clientes()

    conn = conectar()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("""
        SELECT
            cm.id,
            cm.data_referencia,
            cm.meses_referencia,
            cm.arquivo_origem,
            cm.criado_em,
            c.nome AS cliente,
            COUNT(i.id) AS total_itens,
            COALESCE(SUM(i.quantidade_mensal), 0) AS demanda_mensal
        FROM cotacoes_clientes_mapa cm
        JOIN clientes_mapa_precos c ON c.id = cm.cliente_id
        LEFT JOIN cotacoes_clientes_mapa_itens i ON i.cotacao_id = cm.id
        GROUP BY cm.id, cm.data_referencia, cm.meses_referencia, cm.arquivo_origem, cm.criado_em, c.nome
        ORDER BY cm.id DESC
        LIMIT ?
    """, (int(limite),))

    cotacoes = [dict(row) for row in cur.fetchall()]
    conn.close()

    for c in cotacoes:
        c["demanda_mensal_formatada"] = formatar_quantidade_mapa(c.get("demanda_mensal"))
    return cotacoes


def mapa_consolidado_vazio():
    """
    Fase 2: agora retorna o mapa consolidado real.
    """
    criar_tabelas_mapa_precos_clientes()
    garantir_clientes_fixos_mapa()

    clientes_colunas = clientes_colunas_mapa()
    nomes_clientes_colunas = [c["nome"] for c in clientes_colunas]

    conn = conectar()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("""
        SELECT
            i.*,
            c.nome AS cliente_nome,
            p.produto_padrao,
            p.fabricante AS fabricante_produto,
            p.categoria AS categoria_produto,
            p.sku_master AS sku_master_produto
        FROM cotacoes_clientes_mapa_itens i
        JOIN clientes_mapa_precos c ON c.id = i.cliente_id
        LEFT JOIN produtos p ON p.id = i.produto_id
        ORDER BY COALESCE(i.sku_master, i.descricao_original), c.nome
    """)
    linhas = [dict(row) for row in cur.fetchall()]

    grupos = {}

    for row in linhas:
        produto_id = row.get("produto_id")
        chave = f"PID:{produto_id}" if produto_id else "DESC:" + normalizar_texto_mapa(row.get("sku_master") or row.get("descricao_original"))

        if chave not in grupos:
            produto_id_ref = produto_id
            custo = _menor_preco_medbox(cur, produto_id_ref)

            sku_master = normalizar_texto_mapa(
                row.get("sku_master_produto")
                or row.get("sku_master")
                or row.get("produto_padrao")
                or row.get("descricao_original")
            )

            categoria = normalizar_texto_mapa(
                row.get("categoria_produto")
                or row.get("categoria")
                or ""
            )

            fabricante = normalizar_texto_mapa(
                custo.get("fabricante")
                or row.get("fabricante_produto")
                or ""
            )

            menor_preco = float(custo.get("menor_preco") or 0)
            preco_medbox = menor_preco * 1.8 if menor_preco > 0 else 0

            grupos[chave] = {
                "categoria": categoria,
                "descricao": normalizar_texto_mapa(row.get("descricao_original")),
                "sku_master": sku_master,
                "produto_id": produto_id_ref,
                "demanda_mensal_total": 0.0,
                "valor_ponderado_total": 0.0,
                "quantidade_valor_total": 0.0,
                "preco_compra": menor_preco,
                "preco_compra_formatado": moeda_br(menor_preco) if menor_preco else "",
                "fornecedor": custo.get("fornecedor") or "",
                "fabricante": fabricante,
                "preco_medbox": preco_medbox,
                "preco_medbox_formatado": moeda_br(preco_medbox) if preco_medbox else "",
                "clientes": {
                    nome: {
                        "quantidade_mensal": 0.0,
                        "valor_ponderado": 0.0,
                        "quantidade_valor": 0.0,
                        "valor_unitario": 0.0,
                        "valor_unitario_formatado": "",
                    }
                    for nome in nomes_clientes_colunas
                }
            }

        grupo = grupos[chave]

        qtd_mensal = float(row.get("quantidade_mensal") or 0)
        valor_unitario = float(row.get("valor_unitario") or 0)
        cliente_nome = row.get("cliente_nome")

        grupo["demanda_mensal_total"] += qtd_mensal

        if valor_unitario > 0 and qtd_mensal > 0:
            grupo["valor_ponderado_total"] += valor_unitario * qtd_mensal
            grupo["quantidade_valor_total"] += qtd_mensal

        if cliente_nome in grupo["clientes"]:
            cel = grupo["clientes"][cliente_nome]
            cel["quantidade_mensal"] += qtd_mensal

            if valor_unitario > 0 and qtd_mensal > 0:
                cel["valor_ponderado"] += valor_unitario * qtd_mensal
                cel["quantidade_valor"] += qtd_mensal

    itens = []

    for grupo in grupos.values():
        if grupo["quantidade_valor_total"] > 0:
            preco_medio = grupo["valor_ponderado_total"] / grupo["quantidade_valor_total"]
        else:
            preco_medio = 0

        faturamento = grupo["demanda_mensal_total"] * preco_medio

        grupo["preco_medio"] = preco_medio
        grupo["preco_medio_formatado"] = moeda_br(preco_medio) if preco_medio else ""
        grupo["faturamento"] = faturamento
        grupo["faturamento_formatado"] = moeda_br(faturamento) if faturamento else ""
        grupo["demanda_mensal_total_formatada"] = formatar_quantidade_mapa(grupo["demanda_mensal_total"])

        for nome, cel in grupo["clientes"].items():
            if cel["quantidade_valor"] > 0:
                cel["valor_unitario"] = cel["valor_ponderado"] / cel["quantidade_valor"]

            cel["quantidade_mensal_formatada"] = (
                formatar_quantidade_mapa(cel["quantidade_mensal"])
                if cel["quantidade_mensal"] else ""
            )
            cel["valor_unitario_formatado"] = (
                moeda_br(cel["valor_unitario"])
                if cel["valor_unitario"] else ""
            )

        itens.append(grupo)

    conn.close()

    itens.sort(key=lambda x: (-x["demanda_mensal_total"], x["sku_master"]))
    return itens


# ============================================================
# FASE 3 - MAPA ERP, SKU/CATEGORIA EDITÁVEL E AGRUPAMENTO
# ============================================================

def _buscar_produto_por_sku_master_mapa(cursor, sku_master):
    sku = normalizar_texto_mapa(sku_master)
    if not sku:
        return None

    cursor.execute("""
        SELECT id, produto_padrao, sku_master, fabricante, categoria
        FROM produtos
        WHERE ativo = 1
          AND UPPER(TRIM(COALESCE(sku_master, ''))) = UPPER(TRIM(?))
        ORDER BY id
        LIMIT 1
    """, (sku,))
    row = cursor.fetchone()
    return dict(row) if row else None


def atualizar_item_mapa_precos(grupo_key, sku_master="", categoria=""):
    """
    Atualiza SKU_MASTER e/ou categoria dos itens do mapa.

    grupo_key vem da tela e pode ser:
    SKU::<sku>
    DESC::<descricao>
    PID::<produto_id>
    """
    criar_tabelas_mapa_precos_clientes()

    grupo_key = str(grupo_key or "").strip()
    sku_master = normalizar_texto_mapa(sku_master)
    categoria = normalizar_texto_mapa(categoria)

    if not grupo_key:
        raise ValueError("Grupo do item não informado.")

    conn = conectar()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    try:
        produto = _buscar_produto_por_sku_master_mapa(cur, sku_master) if sku_master else None
        produto_id = produto.get("id") if produto else None

        where = ""
        params = []

        if grupo_key.startswith("SKU::"):
            valor = grupo_key.replace("SKU::", "", 1)
            where = "UPPER(TRIM(COALESCE(sku_master, ''))) = UPPER(TRIM(?))"
            params = [valor]
        elif grupo_key.startswith("DESC::"):
            valor = grupo_key.replace("DESC::", "", 1)
            where = "UPPER(TRIM(COALESCE(descricao_original, ''))) = UPPER(TRIM(?))"
            params = [valor]
        elif grupo_key.startswith("PID::"):
            valor = grupo_key.replace("PID::", "", 1)
            where = "produto_id = ?"
            params = [int(valor)]
        else:
            raise ValueError("Grupo do item inválido.")

        sets = []
        set_params = []

        if sku_master:
            sets.append("sku_master = ?")
            set_params.append(sku_master)

        if categoria:
            sets.append("categoria = ?")
            set_params.append(categoria)

        if produto_id:
            sets.append("produto_id = ?")
            set_params.append(produto_id)

            if not categoria and produto.get("categoria"):
                sets.append("categoria = ?")
                set_params.append(normalizar_texto_mapa(produto.get("categoria")))

        if not sets:
            raise ValueError("Nenhuma alteração informada.")

        sql = f"""
            UPDATE cotacoes_clientes_mapa_itens
            SET {", ".join(sets)}
            WHERE {where}
        """

        cur.execute(sql, (*set_params, *params))
        atualizados = cur.rowcount

        conn.commit()

        return {
            "ok": True,
            "atualizados": atualizados,
            "produto_id": produto_id,
            "sku_master": sku_master,
            "categoria": categoria,
        }

    finally:
        conn.close()


def mapa_consolidado_vazio():
    """
    Mapa consolidado real.

    Regras:
    - Agrupa por SKU_MASTER quando existir.
    - Se não houver SKU_MASTER, agrupa por descrição.
    - Soma quantidade mensal por cliente e no total.
    - Calcula preço médio ponderado dos clientes.
    - Calcula preço MedBox com markup padrão 80%.
    - Calcula menor preço entre MedBox e valores dos clientes.
    """
    criar_tabelas_mapa_precos_clientes()
    garantir_clientes_fixos_mapa()

    clientes_colunas = clientes_colunas_mapa()
    nomes_clientes_colunas = [c["nome"] for c in clientes_colunas]

    conn = conectar()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("""
        SELECT
            i.*,
            c.nome AS cliente_nome,
            p.produto_padrao,
            p.fabricante AS fabricante_produto,
            p.categoria AS categoria_produto,
            p.sku_master AS sku_master_produto
        FROM cotacoes_clientes_mapa_itens i
        JOIN clientes_mapa_precos c ON c.id = i.cliente_id
        LEFT JOIN produtos p ON p.id = i.produto_id
        ORDER BY COALESCE(NULLIF(i.sku_master, ''), i.descricao_original), c.nome
    """)

    linhas = [dict(row) for row in cur.fetchall()]
    grupos = {}

    for row in linhas:
        sku_normalizado = normalizar_texto_mapa(
            row.get("sku_master_produto")
            or row.get("sku_master")
            or ""
        )

        descricao_original = normalizar_texto_mapa(row.get("descricao_original"))
        produto_id = row.get("produto_id")

        if sku_normalizado:
            chave = "SKU::" + sku_normalizado
        elif produto_id:
            chave = "PID::" + str(produto_id)
        else:
            chave = "DESC::" + descricao_original

        if chave not in grupos:
            produto_id_ref = produto_id

            # Se tem SKU_MASTER, tenta localizar produto ativo correspondente.
            if not produto_id_ref and sku_normalizado:
                produto = _buscar_produto_por_sku_master_mapa(cur, sku_normalizado)
                if produto:
                    produto_id_ref = produto.get("id")

            custo = _menor_preco_medbox(cur, produto_id_ref)

            menor_preco_compra = float(custo.get("menor_preco") or 0)
            markup_padrao = 80.0
            preco_medbox = menor_preco_compra * (1 + markup_padrao / 100) if menor_preco_compra > 0 else 0

            # IMPORTANTE:
            # Não usar descrição do produto como SKU_MASTER.
            # Se o item ainda não estiver vinculado a um SKU_MASTER real,
            # a tela deve mostrar campo vazio/REVISAR SKU para correção manual.
            sku_final = sku_normalizado

            # No Mapa de Preços, a categoria editada no próprio mapa
            # tem prioridade sobre a categoria antiga do cadastro do produto.
            categoria_final = normalizar_texto_mapa(
                row.get("categoria")
                or row.get("categoria_produto")
                or ""
            )

            fabricante_final = normalizar_texto_mapa(
                custo.get("fabricante")
                or row.get("fabricante_produto")
                or ""
            )

            grupos[chave] = {
                "grupo_key": chave,
                "categoria": categoria_final,
                "descricao": descricao_original,
                "sku_master": sku_final,
                "produto_id": produto_id_ref,
                "demanda_mensal_total": 0.0,
                "valor_ponderado_total": 0.0,
                "quantidade_valor_total": 0.0,
                "preco_compra": menor_preco_compra,
                "preco_compra_formatado": moeda_br(menor_preco_compra) if menor_preco_compra else "",
                "markup_percentual": markup_padrao,
                "fornecedor": custo.get("fornecedor") or "",
                "fabricante": fabricante_final,
                "preco_medbox": preco_medbox,
                "preco_medbox_formatado": moeda_br(preco_medbox) if preco_medbox else "",
                "menor_preco_geral": 0.0,
                "menor_preco_geral_formatado": "",
                "menor_preco_origem": "",
                "clientes": {
                    nome: {
                        "quantidade_mensal": 0.0,
                        "valor_ponderado": 0.0,
                        "quantidade_valor": 0.0,
                        "valor_unitario": 0.0,
                        "valor_unitario_formatado": "",
                        "menor_cliente": False,
                    }
                    for nome in nomes_clientes_colunas
                }
            }

        grupo = grupos[chave]

        qtd_mensal = float(row.get("quantidade_mensal") or 0)
        valor_unitario = float(row.get("valor_unitario") or 0)
        cliente_nome = row.get("cliente_nome")

        grupo["demanda_mensal_total"] += qtd_mensal

        if valor_unitario > 0 and qtd_mensal > 0:
            grupo["valor_ponderado_total"] += valor_unitario * qtd_mensal
            grupo["quantidade_valor_total"] += qtd_mensal

        if cliente_nome in grupo["clientes"]:
            cel = grupo["clientes"][cliente_nome]
            cel["quantidade_mensal"] += qtd_mensal

            if valor_unitario > 0 and qtd_mensal > 0:
                cel["valor_ponderado"] += valor_unitario * qtd_mensal
                cel["quantidade_valor"] += qtd_mensal

    itens = []

    for grupo in grupos.values():
        if grupo["quantidade_valor_total"] > 0:
            preco_medio = grupo["valor_ponderado_total"] / grupo["quantidade_valor_total"]
        else:
            preco_medio = 0

        faturamento = grupo["demanda_mensal_total"] * preco_medio

        grupo["preco_medio"] = preco_medio
        grupo["preco_medio_formatado"] = moeda_br(preco_medio) if preco_medio else ""
        grupo["faturamento"] = faturamento
        grupo["faturamento_formatado"] = moeda_br(faturamento) if faturamento else ""
        grupo["demanda_mensal_total_formatada"] = formatar_quantidade_mapa(grupo["demanda_mensal_total"])

        candidatos_menor = []

        # Preço MedBox participa da comparação.
        if grupo["preco_medbox"] > 0:
            candidatos_menor.append(("MEDBOX", grupo["preco_medbox"]))

        for nome, cel in grupo["clientes"].items():
            if cel["quantidade_valor"] > 0:
                cel["valor_unitario"] = cel["valor_ponderado"] / cel["quantidade_valor"]

            cel["quantidade_mensal_formatada"] = (
                formatar_quantidade_mapa(cel["quantidade_mensal"])
                if cel["quantidade_mensal"] else ""
            )

            cel["valor_unitario_formatado"] = (
                moeda_br(cel["valor_unitario"])
                if cel["valor_unitario"] else ""
            )

            if cel["valor_unitario"] > 0:
                candidatos_menor.append((nome, cel["valor_unitario"]))

        if candidatos_menor:
            origem, menor = min(candidatos_menor, key=lambda x: x[1])
            grupo["menor_preco_geral"] = menor
            grupo["menor_preco_geral_formatado"] = moeda_br(menor)
            grupo["menor_preco_origem"] = origem

            if origem == "MEDBOX":
                grupo["medbox_menor"] = True
            elif origem in grupo["clientes"]:
                grupo["clientes"][origem]["menor_cliente"] = True
                grupo["medbox_menor"] = False
        else:
            grupo["medbox_menor"] = False

        itens.append(grupo)

    conn.close()

    itens.sort(key=lambda x: (-x["demanda_mensal_total"], x["sku_master"]))
    return itens


# ============================================================
# FASE 4 - EDIÇÃO COMPLETA DO MAPA
# ============================================================

def _colunas_produtos_mapa(cursor):
    cursor.execute("PRAGMA table_info(produtos)")
    return {row[1] for row in cursor.fetchall()}


def _criar_produto_sku_mapa(cursor, sku_master, categoria=""):
    """
    Cria um SKU_MASTER novo a partir do Mapa de Preços quando ele ainda não existe.
    Mantém simples e seguro: produto_padrao = sku_master.
    """
    sku = normalizar_texto_mapa(sku_master)
    categoria = normalizar_texto_mapa(categoria)

    if not sku:
        return None

    existente = _buscar_produto_por_sku_master_mapa(cursor, sku)
    if existente:
        return existente

    colunas = _colunas_produtos_mapa(cursor)

    campos = []
    valores = []

    def add(campo, valor):
        if campo in colunas:
            campos.append(campo)
            valores.append(valor)

    add("sku", "")
    add("produto_padrao", sku)
    add("sku_master", sku)
    add("fabricante", "")
    add("categoria", categoria)
    add("ativo", 1)

    if not campos:
        return None

    placeholders = ", ".join(["?"] * len(campos))

    cursor.execute(
        f"INSERT INTO produtos ({', '.join(campos)}) VALUES ({placeholders})",
        valores
    )

    produto_id = cursor.lastrowid

    return {
        "id": produto_id,
        "produto_padrao": sku,
        "sku_master": sku,
        "fabricante": "",
        "categoria": categoria,
    }


def _where_grupo_mapa(grupo_key):
    grupo_key = str(grupo_key or "").strip()

    if grupo_key.startswith("SKU::"):
        valor = grupo_key.replace("SKU::", "", 1)
        return "UPPER(TRIM(COALESCE(sku_master, ''))) = UPPER(TRIM(?))", [valor]

    if grupo_key.startswith("DESC::"):
        valor = grupo_key.replace("DESC::", "", 1)
        return "UPPER(TRIM(COALESCE(descricao_original, ''))) = UPPER(TRIM(?))", [valor]

    if grupo_key.startswith("PID::"):
        valor = int(grupo_key.replace("PID::", "", 1))
        return "produto_id = ?", [valor]

    raise ValueError("Grupo do item inválido.")


def atualizar_item_mapa_precos(grupo_key, sku_master="", categoria=""):
    """
    Atualiza SKU_MASTER e/ou categoria dos itens do mapa.
    Se o SKU_MASTER não existir, cria um produto novo com esse SKU.
    """
    criar_tabelas_mapa_precos_clientes()

    grupo_key = str(grupo_key or "").strip()
    sku_master = normalizar_texto_mapa(sku_master)
    categoria = normalizar_texto_mapa(categoria)

    if not grupo_key:
        raise ValueError("Grupo do item não informado.")

    conn = conectar()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    try:
        produto = None

        if sku_master:
            produto = _buscar_produto_por_sku_master_mapa(cur, sku_master)

            if not produto:
                produto = _criar_produto_sku_mapa(cur, sku_master, categoria)

        produto_id = produto.get("id") if produto else None

        where, params = _where_grupo_mapa(grupo_key)

        sets = []
        set_params = []

        if sku_master:
            sets.append("sku_master = ?")
            set_params.append(sku_master)

        if categoria:
            sets.append("categoria = ?")
            set_params.append(categoria)

        if produto_id:
            sets.append("produto_id = ?")
            set_params.append(produto_id)

            if not categoria and produto.get("categoria"):
                sets.append("categoria = ?")
                set_params.append(normalizar_texto_mapa(produto.get("categoria")))

        if not sets:
            raise ValueError("Nenhuma alteração informada.")

        sql = f"""
            UPDATE cotacoes_clientes_mapa_itens
            SET {", ".join(sets)}
            WHERE {where}
        """

        cur.execute(sql, (*set_params, *params))
        atualizados = cur.rowcount

        conn.commit()

        return {
            "ok": True,
            "atualizados": atualizados,
            "produto_id": produto_id,
            "sku_master": sku_master,
            "categoria": categoria,
            "produto_criado": bool(produto_id and produto and normalizar_texto_mapa(produto.get("produto_padrao")) == sku_master),
        }

    finally:
        conn.close()


def atualizar_valor_cliente_mapa(grupo_key, cliente_id, valor_unitario):
    """
    Atualiza valor unitário de um cliente para todos os itens daquele grupo.
    """
    criar_tabelas_mapa_precos_clientes()

    cliente_id = int(cliente_id)
    valor_unitario = converter_float_mapa(valor_unitario)

    if valor_unitario < 0:
        valor_unitario = 0

    where, params = _where_grupo_mapa(grupo_key)

    conn = conectar()
    cur = conn.cursor()

    try:
        sql = f"""
            UPDATE cotacoes_clientes_mapa_itens
            SET valor_unitario = ?,
                valor_total = quantidade_total * ?
            WHERE cliente_id = ?
              AND {where}
        """

        cur.execute(sql, (valor_unitario, valor_unitario, cliente_id, *params))
        atualizados = cur.rowcount

        conn.commit()

        return {
            "ok": True,
            "atualizados": atualizados,
            "valor_unitario": valor_unitario,
            "valor_unitario_formatado": moeda_br(valor_unitario) if valor_unitario else "",
        }

    finally:
        conn.close()


def mapa_consolidado_vazio():
    """
    Mapa consolidado V4.

    Correções:
    - Agrupa por SKU_MASTER real quando existir.
    - Não usa descrição como SKU_MASTER.
    - Preço médio clientes usa valor_unitario salvo.
    - Faturamento = demanda x preço médio; se não houver preço médio, usa Preço MedBox.
    - Menor preço compara MedBox x valores unitários dos clientes.
    """
    criar_tabelas_mapa_precos_clientes()
    garantir_clientes_fixos_mapa()

    clientes_colunas = clientes_colunas_mapa()
    nomes_clientes_colunas = [c["nome"] for c in clientes_colunas]

    conn = conectar()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("""
        SELECT
            i.*,
            c.nome AS cliente_nome,
            c.id AS cliente_id_real,
            p.produto_padrao,
            p.fabricante AS fabricante_produto,
            p.categoria AS categoria_produto,
            p.sku_master AS sku_master_produto
        FROM cotacoes_clientes_mapa_itens i
        JOIN clientes_mapa_precos c ON c.id = i.cliente_id
        LEFT JOIN produtos p ON p.id = i.produto_id
        ORDER BY COALESCE(NULLIF(i.sku_master, ''), i.descricao_original), c.nome
    """)

    linhas = [dict(row) for row in cur.fetchall()]
    grupos = {}

    for row in linhas:
        sku_normalizado = normalizar_texto_mapa(
            row.get("sku_master_produto")
            or row.get("sku_master")
            or ""
        )

        descricao_original = normalizar_texto_mapa(row.get("descricao_original"))
        produto_id = row.get("produto_id")

        if sku_normalizado:
            chave = "SKU::" + sku_normalizado
        elif produto_id:
            chave = "PID::" + str(produto_id)
        else:
            chave = "DESC::" + descricao_original

        if chave not in grupos:
            produto_id_ref = produto_id

            if not produto_id_ref and sku_normalizado:
                produto = _buscar_produto_por_sku_master_mapa(cur, sku_normalizado)
                if produto:
                    produto_id_ref = produto.get("id")

            custo = _menor_preco_medbox(cur, produto_id_ref)

            menor_preco_compra = float(custo.get("menor_preco") or 0)
            markup_padrao = 80.0
            preco_medbox = menor_preco_compra * (1 + markup_padrao / 100) if menor_preco_compra > 0 else 0

            # No Mapa de Preços, a categoria editada no próprio mapa
            # tem prioridade sobre a categoria antiga do cadastro do produto.
            categoria_final = normalizar_texto_mapa(
                row.get("categoria")
                or row.get("categoria_produto")
                or ""
            )

            if categoria_final in ("INSUMOS HOSPITALARES", "INSUMO HOSPITALAR", "MATERIAL HOSPITALAR"):
                categoria_final = "CORRELATOS"

            if categoria_final not in ("MEDICAMENTOS", "CORRELATOS"):
                categoria_final = ""

            fabricante_final = normalizar_texto_mapa(
                custo.get("fabricante")
                or row.get("fabricante_produto")
                or ""
            )

            grupos[chave] = {
                "grupo_key": chave,
                "categoria": categoria_final,
                "descricao": descricao_original,
                "sku_master": sku_normalizado,
                "produto_id": produto_id_ref,
                "demanda_mensal_total": 0.0,
                "valor_ponderado_total": 0.0,
                "quantidade_valor_total": 0.0,
                "preco_compra": menor_preco_compra,
                "preco_compra_formatado": moeda_br(menor_preco_compra) if menor_preco_compra else "",
                "markup_percentual": markup_padrao,
                "fornecedor": custo.get("fornecedor") or "",
                "fabricante": fabricante_final,
                "preco_medbox": preco_medbox,
                "preco_medbox_formatado": moeda_br(preco_medbox) if preco_medbox else "",
                "menor_preco_geral": 0.0,
                "menor_preco_geral_formatado": "",
                "menor_preco_origem": "",
                "medbox_menor": False,
                "clientes": {
                    nome: {
                        "cliente_id": next((c["id"] for c in clientes_colunas if c["nome"] == nome), None),
                        "quantidade_mensal": 0.0,
                        "valor_ponderado": 0.0,
                        "quantidade_valor": 0.0,
                        "valor_unitario": 0.0,
                        "valor_unitario_formatado": "",
                        "menor_cliente": False,
                    }
                    for nome in nomes_clientes_colunas
                }
            }

        grupo = grupos[chave]

        qtd_mensal = float(row.get("quantidade_mensal") or 0)
        valor_unitario = float(row.get("valor_unitario") or 0)
        cliente_nome = row.get("cliente_nome")

        grupo["demanda_mensal_total"] += qtd_mensal

        if valor_unitario > 0 and qtd_mensal > 0:
            grupo["valor_ponderado_total"] += valor_unitario * qtd_mensal
            grupo["quantidade_valor_total"] += qtd_mensal

        if cliente_nome in grupo["clientes"]:
            cel = grupo["clientes"][cliente_nome]
            cel["quantidade_mensal"] += qtd_mensal

            if valor_unitario > 0 and qtd_mensal > 0:
                cel["valor_ponderado"] += valor_unitario * qtd_mensal
                cel["quantidade_valor"] += qtd_mensal

    itens = []

    for grupo in grupos.values():
        if grupo["quantidade_valor_total"] > 0:
            preco_medio = grupo["valor_ponderado_total"] / grupo["quantidade_valor_total"]
        else:
            preco_medio = 0

        base_faturamento = preco_medio if preco_medio > 0 else grupo["preco_medbox"]
        faturamento = grupo["demanda_mensal_total"] * base_faturamento if base_faturamento > 0 else 0

        grupo["preco_medio"] = preco_medio
        grupo["preco_medio_formatado"] = moeda_br(preco_medio) if preco_medio else ""
        grupo["faturamento"] = faturamento
        grupo["faturamento_formatado"] = moeda_br(faturamento) if faturamento else ""
        grupo["demanda_mensal_total_formatada"] = formatar_quantidade_mapa(grupo["demanda_mensal_total"])

        candidatos_menor = []

        if grupo["preco_medbox"] > 0:
            candidatos_menor.append(("MEDBOX", grupo["preco_medbox"]))

        for nome, cel in grupo["clientes"].items():
            if cel["quantidade_valor"] > 0:
                cel["valor_unitario"] = cel["valor_ponderado"] / cel["quantidade_valor"]

            cel["quantidade_mensal_formatada"] = (
                formatar_quantidade_mapa(cel["quantidade_mensal"])
                if cel["quantidade_mensal"] else ""
            )

            cel["valor_unitario_formatado"] = (
                moeda_br(cel["valor_unitario"])
                if cel["valor_unitario"] else ""
            )

            if cel["valor_unitario"] > 0:
                candidatos_menor.append((nome, cel["valor_unitario"]))

        if candidatos_menor:
            origem, menor = min(candidatos_menor, key=lambda x: x[1])
            grupo["menor_preco_geral"] = menor
            grupo["menor_preco_geral_formatado"] = moeda_br(menor)
            grupo["menor_preco_origem"] = origem

            if origem == "MEDBOX":
                grupo["medbox_menor"] = True
            elif origem in grupo["clientes"]:
                grupo["clientes"][origem]["menor_cliente"] = True
                grupo["medbox_menor"] = False

        itens.append(grupo)

    conn.close()

    itens.sort(key=lambda x: (-x["demanda_mensal_total"], x["descricao"]))
    return itens



# ============================================================
# PATCH FINAL MAPA PREÇOS CLIENTES - 2026-06-23
# Regras:
# - Agrupa por descrição exata normalizada.
# - Descrição 100% igual vira uma linha só.
# - Soma demanda mensal por cliente e total.
# - Salva produto novo na base produtos.
# - Permite SKU_MASTER novo digitado no mapa.
# ============================================================

def _garantir_colunas_produtos_mapa_final(cursor):
    cursor.execute("PRAGMA table_info(produtos)")
    colunas = {row[1] for row in cursor.fetchall()}

    if "sku_master" not in colunas:
        cursor.execute("ALTER TABLE produtos ADD COLUMN sku_master TEXT")

    if "sku_corrigido" not in colunas:
        cursor.execute("ALTER TABLE produtos ADD COLUMN sku_corrigido INTEGER DEFAULT 0")

    if "corrigido_em" not in colunas:
        cursor.execute("ALTER TABLE produtos ADD COLUMN corrigido_em TEXT")


def _produto_por_descricao_exata_mapa(cursor, descricao):
    desc = normalizar_texto_mapa(descricao)
    if not desc:
        return None

    cursor.execute("""
        SELECT id, sku, produto_padrao, sku_master, fabricante, categoria, ativo
        FROM produtos
        WHERE ativo = 1
          AND UPPER(TRIM(COALESCE(produto_padrao, ''))) = UPPER(TRIM(?))
        ORDER BY id
        LIMIT 1
    """, (desc,))
    row = cursor.fetchone()
    return dict(row) if row else None


def _obter_ou_criar_produto_mapa(cursor, descricao, sku_master="", categoria=""):
    """
    Garante que todo item importado exista na tabela produtos.
    Isso faz o produto aparecer no módulo Auditoria SKU Master.
    """
    _garantir_colunas_produtos_mapa_final(cursor)

    descricao = normalizar_texto_mapa(descricao)
    sku_master = normalizar_texto_mapa(sku_master)
    categoria = normalizar_texto_mapa(categoria)

    if not descricao and not sku_master:
        return None

    produto = None

    if sku_master:
        produto = _buscar_produto_por_sku_master_mapa(cursor, sku_master)

    if not produto and descricao:
        produto = _produto_por_descricao_exata_mapa(cursor, descricao)

    if produto:
        return produto

    produto_padrao = sku_master or descricao

    cursor.execute("""
        INSERT INTO produtos (
            sku,
            produto_padrao,
            fabricante,
            categoria,
            ativo,
            observacoes,
            sku_master,
            sku_corrigido,
            corrigido_em
        )
        VALUES (?, ?, ?, ?, 1, ?, ?, 0, NULL)
    """, (
        "",
        produto_padrao,
        "",
        categoria,
        "CRIADO AUTOMATICAMENTE PELO MAPA DE PREÇOS CLIENTES",
        sku_master,
    ))

    produto_id = cursor.lastrowid

    return {
        "id": produto_id,
        "sku": "",
        "produto_padrao": produto_padrao,
        "sku_master": sku_master,
        "fabricante": "",
        "categoria": categoria,
        "ativo": 1,
    }


def sincronizar_produtos_itens_mapa_precos():
    """
    Corrige importações antigas:
    - Para itens do mapa sem produto_id, cria/localiza produto.
    - Vincula cotacoes_clientes_mapa_itens.produto_id.
    """
    criar_tabelas_mapa_precos_clientes()

    conn = conectar()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    try:
        _garantir_colunas_produtos_mapa_final(cur)

        cur.execute("""
            SELECT id, descricao_original, sku_master, categoria, produto_id
            FROM cotacoes_clientes_mapa_itens
            WHERE produto_id IS NULL OR produto_id = 0
        """)
        linhas = [dict(row) for row in cur.fetchall()]

        vinculados = 0
        criados_ou_localizados = 0

        for row in linhas:
            produto = _obter_ou_criar_produto_mapa(
                cur,
                row.get("descricao_original"),
                row.get("sku_master"),
                row.get("categoria"),
            )

            if produto and produto.get("id"):
                criados_ou_localizados += 1
                cur.execute("""
                    UPDATE cotacoes_clientes_mapa_itens
                    SET produto_id = ?
                    WHERE id = ?
                """, (produto["id"], row["id"]))
                vinculados += cur.rowcount

        conn.commit()

        return {
            "ok": True,
            "itens_verificados": len(linhas),
            "produtos_criados_ou_localizados": criados_ou_localizados,
            "itens_vinculados": vinculados,
        }

    finally:
        conn.close()


def _where_grupo_mapa(grupo_key):
    grupo_key = str(grupo_key or "").strip()

    if grupo_key.startswith("DESC::"):
        valor = grupo_key.replace("DESC::", "", 1)
        return "UPPER(TRIM(COALESCE(descricao_original, ''))) = UPPER(TRIM(?))", [valor]

    if grupo_key.startswith("SKU::"):
        valor = grupo_key.replace("SKU::", "", 1)
        return "UPPER(TRIM(COALESCE(sku_master, ''))) = UPPER(TRIM(?))", [valor]

    if grupo_key.startswith("PID::"):
        valor = int(grupo_key.replace("PID::", "", 1))
        return "produto_id = ?", [valor]

    raise ValueError("Grupo do item inválido.")


def atualizar_item_mapa_precos(grupo_key, sku_master="", categoria=""):
    """
    Atualiza SKU_MASTER e categoria do grupo.
    Se SKU_MASTER não existir, cria produto novo na base produtos.
    Agrupamento principal é por descrição exata.
    """
    criar_tabelas_mapa_precos_clientes()

    grupo_key = str(grupo_key or "").strip()
    sku_master = normalizar_texto_mapa(sku_master)
    categoria = normalizar_texto_mapa(categoria)

    if not grupo_key:
        raise ValueError("Grupo do item não informado.")

    conn = conectar()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    try:
        _garantir_colunas_produtos_mapa_final(cur)

        where, params = _where_grupo_mapa(grupo_key)

        # Pega uma descrição de referência do grupo.
        cur.execute(f"""
            SELECT descricao_original, categoria
            FROM cotacoes_clientes_mapa_itens
            WHERE {where}
            ORDER BY id
            LIMIT 1
        """, params)
        ref = cur.fetchone()

        descricao_ref = ref["descricao_original"] if ref else ""
        categoria_ref = categoria or (ref["categoria"] if ref else "")

        produto = None
        if sku_master:
            produto = _obter_ou_criar_produto_mapa(
                cur,
                descricao_ref or sku_master,
                sku_master,
                categoria_ref,
            )

        produto_id = produto.get("id") if produto else None

        sets = []
        set_params = []

        if sku_master:
            sets.append("sku_master = ?")
            set_params.append(sku_master)

        if categoria:
            sets.append("categoria = ?")
            set_params.append(categoria)

        if produto_id:
            sets.append("produto_id = ?")
            set_params.append(produto_id)

        if not sets:
            raise ValueError("Nenhuma alteração informada.")

        cur.execute(f"""
            UPDATE cotacoes_clientes_mapa_itens
            SET {", ".join(sets)}
            WHERE {where}
        """, (*set_params, *params))

        atualizados = cur.rowcount

        # Marca o produto como corrigido quando SKU_MASTER foi informado.
        if produto_id and sku_master:
            cur.execute("""
                UPDATE produtos
                SET sku_master = ?,
                    produto_padrao = COALESCE(NULLIF(produto_padrao, ''), ?),
                    categoria = COALESCE(NULLIF(?, ''), categoria),
                    sku_corrigido = 1,
                    corrigido_em = CURRENT_TIMESTAMP,
                    ativo = 1
                WHERE id = ?
            """, (sku_master, sku_master, categoria, produto_id))

            try:
                cur.execute("""
                    INSERT INTO auditoria_sku (
                        produto_id, campo, valor_antigo, valor_novo,
                        data_hora, tipo_correcao, origem_correcao, usuario
                    )
                    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, ?, ?, ?)
                """, (
                    produto_id,
                    "sku_master",
                    "",
                    sku_master,
                    "manual",
                    "mapa_precos_clientes",
                    "compras",
                ))
            except Exception:
                pass

        conn.commit()

        return {
            "ok": True,
            "atualizados": atualizados,
            "produto_id": produto_id,
            "sku_master": sku_master,
            "categoria": categoria,
            "produto_criado": bool(produto_id),
        }

    finally:
        conn.close()


def atualizar_valor_cliente_mapa(grupo_key, cliente_id, valor_unitario):
    """
    Atualiza valor unitário do cliente para todos os itens daquele grupo.
    """
    criar_tabelas_mapa_precos_clientes()

    cliente_id = int(cliente_id)
    valor_unitario = converter_float_mapa(valor_unitario)

    if valor_unitario < 0:
        valor_unitario = 0

    where, params = _where_grupo_mapa(grupo_key)

    conn = conectar()
    cur = conn.cursor()

    try:
        cur.execute(f"""
            UPDATE cotacoes_clientes_mapa_itens
            SET valor_unitario = ?,
                valor_total = quantidade_total * ?
            WHERE cliente_id = ?
              AND {where}
        """, (valor_unitario, valor_unitario, cliente_id, *params))

        atualizados = cur.rowcount
        conn.commit()

        return {
            "ok": True,
            "atualizados": atualizados,
            "valor_unitario": valor_unitario,
            "valor_unitario_formatado": moeda_br(valor_unitario) if valor_unitario else "",
        }

    finally:
        conn.close()


def mapa_consolidado_vazio():
    """
    Mapa consolidado final.

    Regra principal solicitada:
    - Agrupa por descrição original 100% igual normalizada.
    - Não agrupa primeiro por SKU_MASTER.
    - Descrição igual soma demanda e junta clientes na mesma linha.
    """
    criar_tabelas_mapa_precos_clientes()
    garantir_clientes_fixos_mapa()

    clientes_colunas = clientes_colunas_mapa()
    nomes_clientes_colunas = [c["nome"] for c in clientes_colunas]

    conn = conectar()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    _garantir_colunas_produtos_mapa_final(cur)

    cur.execute("""
        SELECT
            i.*,
            c.nome AS cliente_nome,
            c.id AS cliente_id_real,
            p.produto_padrao,
            p.fabricante AS fabricante_produto,
            p.categoria AS categoria_produto,
            p.sku_master AS sku_master_produto
        FROM cotacoes_clientes_mapa_itens i
        JOIN clientes_mapa_precos c ON c.id = i.cliente_id
        LEFT JOIN produtos p ON p.id = i.produto_id
        ORDER BY UPPER(TRIM(COALESCE(i.descricao_original, ''))), c.ordem_mapa, c.nome
    """)

    linhas = [dict(row) for row in cur.fetchall()]
    grupos = {}

    for row in linhas:
        descricao_original = normalizar_texto_mapa(row.get("descricao_original"))
        if not descricao_original:
            continue

        # REGRA CENTRAL: descrição 100% igual = uma linha.
        chave = "DESC::" + descricao_original

        sku_normalizado = normalizar_texto_mapa(
            row.get("sku_master_produto")
            or row.get("sku_master")
            or ""
        )

        produto_id = row.get("produto_id")

        if chave not in grupos:
            produto_id_ref = produto_id

            if not produto_id_ref:
                produto = _obter_ou_criar_produto_mapa(
                    cur,
                    descricao_original,
                    sku_normalizado,
                    row.get("categoria"),
                )
                produto_id_ref = produto.get("id") if produto else None

                if produto_id_ref:
                    cur.execute("""
                        UPDATE cotacoes_clientes_mapa_itens
                        SET produto_id = ?
                        WHERE UPPER(TRIM(COALESCE(descricao_original, ''))) = UPPER(TRIM(?))
                    """, (produto_id_ref, descricao_original))

            custo = _menor_preco_medbox(cur, produto_id_ref)

            menor_preco_compra = float(custo.get("menor_preco") or 0)
            markup_padrao = 80.0
            preco_medbox = menor_preco_compra * (1 + markup_padrao / 100) if menor_preco_compra > 0 else 0

            categoria_final = normalizar_texto_mapa(
                row.get("categoria")
                or row.get("categoria_produto")
                or ""
            )

            if categoria_final in ("INSUMOS HOSPITALARES", "INSUMO HOSPITALAR", "MATERIAL HOSPITALAR"):
                categoria_final = "CORRELATOS"

            if categoria_final not in ("MEDICAMENTOS", "CORRELATOS"):
                categoria_final = ""

            fabricante_final = normalizar_texto_mapa(
                custo.get("fabricante")
                or row.get("fabricante_produto")
                or ""
            )

            grupos[chave] = {
                "grupo_key": chave,
                "categoria": categoria_final,
                "descricao": descricao_original,
                "sku_master": sku_normalizado,
                "produto_id": produto_id_ref,
                "demanda_mensal_total": 0.0,
                "valor_ponderado_total": 0.0,
                "quantidade_valor_total": 0.0,
                "preco_compra": menor_preco_compra,
                "preco_compra_formatado": moeda_br(menor_preco_compra) if menor_preco_compra else "",
                "markup_percentual": markup_padrao,
                "fornecedor": custo.get("fornecedor") or "",
                "fabricante": fabricante_final,
                "preco_medbox": preco_medbox,
                "preco_medbox_formatado": moeda_br(preco_medbox) if preco_medbox else "",
                "menor_preco_geral": 0.0,
                "menor_preco_geral_formatado": "",
                "menor_preco_origem": "",
                "medbox_menor": False,
                "clientes": {
                    nome: {
                        "cliente_id": next((c["id"] for c in clientes_colunas if c["nome"] == nome), None),
                        "quantidade_mensal": 0.0,
                        "valor_ponderado": 0.0,
                        "quantidade_valor": 0.0,
                        "valor_unitario": 0.0,
                        "valor_unitario_formatado": "",
                        "menor_cliente": False,
                    }
                    for nome in nomes_clientes_colunas
                }
            }

        grupo = grupos[chave]

        # Se alguma linha do grupo já tiver SKU, aproveita.
        if not grupo["sku_master"] and sku_normalizado:
            grupo["sku_master"] = sku_normalizado

        qtd_mensal = float(row.get("quantidade_mensal") or 0)
        valor_unitario = float(row.get("valor_unitario") or 0)
        cliente_nome = row.get("cliente_nome")

        grupo["demanda_mensal_total"] += qtd_mensal

        if valor_unitario > 0 and qtd_mensal > 0:
            grupo["valor_ponderado_total"] += valor_unitario * qtd_mensal
            grupo["quantidade_valor_total"] += qtd_mensal

        if cliente_nome in grupo["clientes"]:
            cel = grupo["clientes"][cliente_nome]
            cel["quantidade_mensal"] += qtd_mensal

            if valor_unitario > 0 and qtd_mensal > 0:
                cel["valor_ponderado"] += valor_unitario * qtd_mensal
                cel["quantidade_valor"] += qtd_mensal

    itens = []

    for grupo in grupos.values():
        if grupo["quantidade_valor_total"] > 0:
            preco_medio = grupo["valor_ponderado_total"] / grupo["quantidade_valor_total"]
        else:
            preco_medio = 0

        base_faturamento = preco_medio if preco_medio > 0 else grupo["preco_medbox"]
        faturamento = grupo["demanda_mensal_total"] * base_faturamento if base_faturamento > 0 else 0

        grupo["preco_medio"] = preco_medio
        grupo["preco_medio_formatado"] = moeda_br(preco_medio) if preco_medio else ""
        grupo["faturamento"] = faturamento
        grupo["faturamento_formatado"] = moeda_br(faturamento) if faturamento else ""
        grupo["demanda_mensal_total_formatada"] = formatar_quantidade_mapa(grupo["demanda_mensal_total"])

        candidatos_menor = []

        if grupo["preco_medbox"] > 0:
            candidatos_menor.append(("MEDBOX", grupo["preco_medbox"]))

        for nome, cel in grupo["clientes"].items():
            if cel["quantidade_valor"] > 0:
                cel["valor_unitario"] = cel["valor_ponderado"] / cel["quantidade_valor"]

            cel["quantidade_mensal_formatada"] = (
                formatar_quantidade_mapa(cel["quantidade_mensal"])
                if cel["quantidade_mensal"] else ""
            )

            cel["valor_unitario_formatado"] = (
                moeda_br(cel["valor_unitario"])
                if cel["valor_unitario"] else ""
            )

            if cel["valor_unitario"] > 0:
                candidatos_menor.append((nome, cel["valor_unitario"]))

        if candidatos_menor:
            origem, menor = min(candidatos_menor, key=lambda x: x[1])
            grupo["menor_preco_geral"] = menor
            grupo["menor_preco_geral_formatado"] = moeda_br(menor)
            grupo["menor_preco_origem"] = origem

            if origem == "MEDBOX":
                grupo["medbox_menor"] = True
            elif origem in grupo["clientes"]:
                grupo["clientes"][origem]["menor_cliente"] = True
                grupo["medbox_menor"] = False

        itens.append(grupo)

    conn.commit()
    conn.close()

    itens.sort(key=lambda x: (-x["demanda_mensal_total"], x["descricao"]))
    return itens



# ============================================================
# PATCH MAPA LEVE - RENDERIZAÇÃO LIMITADA
# Banco completo, tela leve.
# ============================================================

def _filtrar_limitar_itens_mapa(itens, q="", limite=300, pagina=1):
    q = normalizar_texto_mapa(q)
    termos = [t for t in q.split() if t.strip()]

    try:
        limite = int(limite or 300)
    except Exception:
        limite = 300

    if limite not in (100, 300, 500, 1000):
        limite = 300

    try:
        pagina = int(pagina or 1)
    except Exception:
        pagina = 1

    pagina = max(1, pagina)

    if termos:
        filtrados = []
        for item in itens:
            texto_busca = normalizar_texto_mapa(" ".join([
                str(item.get("descricao") or ""),
                str(item.get("sku_master") or ""),
                str(item.get("categoria") or ""),
                str(item.get("fornecedor") or ""),
                str(item.get("fabricante") or ""),
                str(item.get("menor_preco_origem") or ""),
            ]))

            if all(t in texto_busca for t in termos):
                filtrados.append(item)
    else:
        filtrados = itens

    total_geral = len(itens)
    total_filtrado = len(filtrados)

    total_paginas = max(1, (total_filtrado + limite - 1) // limite)
    if pagina > total_paginas:
        pagina = total_paginas

    inicio = (pagina - 1) * limite
    fim = inicio + limite

    itens_pagina = filtrados[inicio:fim]

    meta = {
        "q": q,
        "limite": limite,
        "pagina": pagina,
        "total_paginas": total_paginas,
        "total_geral": total_geral,
        "total_filtrado": total_filtrado,
        "exibindo_inicio": inicio + 1 if total_filtrado else 0,
        "exibindo_fim": min(fim, total_filtrado),
        "pagina_anterior": max(1, pagina - 1),
        "proxima_pagina": min(total_paginas, pagina + 1),
        "tem_anterior": pagina > 1,
        "tem_proxima": pagina < total_paginas,
        "celulas_estimadas": len(itens_pagina) * 43,
    }

    return itens_pagina, meta


def dados_tela_mapa_precos_clientes(q="", limite=300, pagina=1):
    garantir_clientes_fixos_mapa()

    clientes_colunas = clientes_colunas_mapa()
    itens_completos = mapa_consolidado_vazio()
    itens_pagina, filtros_mapa = _filtrar_limitar_itens_mapa(
        itens_completos,
        q=q,
        limite=limite,
        pagina=pagina,
    )

    return {
        "resumo_mapa": resumo_mapa_precos_clientes(),
        "clientes": listar_clientes_mapa_precos(),
        "clientes_colunas": clientes_colunas,
        "itens": itens_pagina,
        "markup_percentual": 80,
        "filtros_mapa": filtros_mapa,
    }



# ============================================================
# PATCH DETECTOR V. UNIT - MAPA PREÇOS CLIENTES
# Corrige reconhecimento de coluna "V. Unit" como valor unitário.
# ============================================================

def _detectar_colunas_cotacao_cliente(cabecalhos):
    normalizados = [normalizar_texto_mapa(c) for c in cabecalhos]

    def achar(possiveis):
        for termo in possiveis:
            termo_n = normalizar_texto_mapa(termo)
            for idx, cab in enumerate(normalizados):
                if termo_n and termo_n in cab:
                    return idx
        return None

    col_desc = achar([
        "DESCRICAO DO PRODUTO",
        "DESCRICAO",
        "PRODUTOS",
        "PRODUTO",
        "ITEM",
        "MATERIAL",
        "COTACAO MEDICAMENTO",
        "COTACAO",
    ])

    col_qtd = achar([
        "QUANTIDADE",
        "QUANT",
        "QTDE",
        "QTD",
        "QTD TOTAL",
        "DEMANDA",
        "CONSUMO",
    ])

    # IMPORTANTE:
    # As planilhas do Mapa Clientes usam "V. Unit".
    # Depois de normalizar, isso vira algo próximo de "V. UNIT".
    col_valor = achar([
        "VALOR UNITARIO",
        "VALOR UNIT",
        "VALOR UNIT.",
        "V. UNIT",
        "V UNIT",
        "VLR UNIT",
        "VL UNIT",
        "VL. UNIT",
        "PRECO UNITARIO",
        "PRECO UNIT",
        "PREÇO UNITARIO",
        "PREÇO UNITÁRIO",
        "PRECO UNIT.",
        "PREÇO UNIT.",
        "UNITARIO",
        "UNITÁRIO",
        "CUSTO UNITARIO",
        "CUSTO UNITÁRIO",
    ])

    # Fallback específico para as abas BD_ dos clientes:
    # Categoria | Produtos | Quant | UND | V. Unit
    if col_valor is None:
        for idx, cab in enumerate(normalizados):
            cab_limpo = cab.replace(".", " ").replace("-", " ")
            cab_limpo = " ".join(cab_limpo.split())
            if cab_limpo in ("V UNIT", "V UNITARIO", "VL UNIT", "VL UNITARIO"):
                col_valor = idx
                break

    col_categoria = achar([
        "CATEGORIA",
        "GRUPO",
        "CLASSE",
    ])

    col_sku = achar([
        "SKU MASTER",
        "SKU_MASTER",
        "SKU",
        "PRODUTO PADRONIZADO",
    ])

    return {
        "descricao": col_desc,
        "quantidade": col_qtd,
        "valor_unitario": col_valor,
        "categoria": col_categoria,
        "sku_master": col_sku,
    }



# ============================================================
# PATCH RESUMO DO FILTRO - MAPA PREÇOS CLIENTES
# Mostra demanda filtrada, menor preço e custo necessário
# para ganhar com markup de 80%.
# ============================================================

def _float_mapa_seguro(valor, padrao=0.0):
    try:
        if valor is None:
            return padrao
        if isinstance(valor, str):
            return converter_float_mapa(valor)
        return float(valor)
    except Exception:
        return padrao


def _moeda_mapa_segura(valor):
    try:
        return moeda_br(float(valor or 0))
    except Exception:
        return "R$ 0,00"


def _descricao_origem_menor_preco_mapa(item):
    for chave in [
        "menor_preco_origem",
        "origem_menor_preco",
        "cliente_menor_preco",
        "menor_preco_cliente",
        "fornecedor_menor_preco",
    ]:
        valor = item.get(chave)
        if valor:
            return str(valor)
    return ""


def _valor_menor_preco_mapa(item):
    for chave in [
        "menor_preco",
        "menor_preco_geral",
        "menor_valor",
        "menor_preco_valor",
    ]:
        valor = _float_mapa_seguro(item.get(chave), 0.0)
        if valor > 0:
            return valor
    return 0.0


def _demanda_item_mapa(item):
    for chave in [
        "demanda_mensal_total",
        "quantidade_mensal_total",
        "demanda_total",
        "quantidade_total",
    ]:
        valor = _float_mapa_seguro(item.get(chave), 0.0)
        if valor:
            return valor
    return 0.0


def _filtrar_itens_resumo_mapa(itens, q=""):
    q = normalizar_texto_mapa(q or "")
    termos = [t for t in q.split() if t.strip()]

    if not termos:
        return list(itens)

    filtrados = []

    for item in itens:
        texto_busca = normalizar_texto_mapa(" ".join([
            str(item.get("descricao") or ""),
            str(item.get("descricao_original") or ""),
            str(item.get("sku_master") or ""),
            str(item.get("categoria") or ""),
            str(item.get("fornecedor") or ""),
            str(item.get("fabricante") or ""),
            str(item.get("menor_preco_origem") or ""),
            str(item.get("origem_menor_preco") or ""),
        ]))

        if all(t in texto_busca for t in termos):
            filtrados.append(item)

    return filtrados


def _resumo_filtro_mapa(itens_filtrados):
    demanda_total = 0.0
    menor_preco = 0.0
    menor_preco_origem = ""
    menor_preco_descricao = ""
    menor_preco_eh_medbox = False

    for item in itens_filtrados:
        demanda_total += _demanda_item_mapa(item)

        preco = _valor_menor_preco_mapa(item)
        if preco <= 0:
            continue

        if menor_preco <= 0 or preco < menor_preco:
            menor_preco = preco
            menor_preco_origem = _descricao_origem_menor_preco_mapa(item)
            menor_preco_descricao = str(item.get("descricao") or item.get("descricao_original") or "")
            origem_norm = normalizar_texto_mapa(menor_preco_origem)
            menor_preco_eh_medbox = "MEDBOX" in origem_norm

    markup_fator = 1.80
    custo_necessario = 0.0

    if menor_preco > 0 and not menor_preco_eh_medbox:
        custo_necessario = menor_preco / markup_fator

    return {
        "demanda_total": demanda_total,
        "demanda_total_formatada": formatar_numero_mapa(demanda_total),
        "menor_preco": menor_preco,
        "menor_preco_formatado": _moeda_mapa_segura(menor_preco),
        "menor_preco_origem": menor_preco_origem or "Não identificado",
        "menor_preco_descricao": menor_preco_descricao,
        "menor_preco_eh_medbox": menor_preco_eh_medbox,
        "custo_necessario": custo_necessario,
        "custo_necessario_formatado": _moeda_mapa_segura(custo_necessario),
        "markup_percentual": 80,
        "markup_fator": markup_fator,
        "total_itens_considerados": len(itens_filtrados),
    }


def dados_tela_mapa_precos_clientes(q="", limite=300, pagina=1):
    garantir_clientes_fixos_mapa()

    clientes_colunas = clientes_colunas_mapa()
    itens_completos = mapa_consolidado_vazio()

    itens_filtrados_resumo = _filtrar_itens_resumo_mapa(itens_completos, q=q)
    resumo_filtro = _resumo_filtro_mapa(itens_filtrados_resumo)

    itens_pagina, filtros_mapa = _filtrar_limitar_itens_mapa(
        itens_completos,
        q=q,
        limite=limite,
        pagina=pagina,
    )

    return {
        "resumo_mapa": resumo_mapa_precos_clientes(),
        "clientes": listar_clientes_mapa_precos(),
        "clientes_colunas": clientes_colunas,
        "itens": itens_pagina,
        "markup_percentual": 80,
        "filtros_mapa": filtros_mapa,
        "resumo_filtro": resumo_filtro,
    }



# ============================================================
# PATCH CORREÇÃO FORMATAR NÚMERO MAPA
# Corrige NameError: formatar_numero_mapa não definido.
# ============================================================

def formatar_numero_mapa(valor):
    try:
        numero = float(valor or 0)
    except Exception:
        numero = 0.0

    if numero == int(numero):
        return f"{int(numero):,}".replace(",", ".")

    texto = f"{numero:,.2f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")



# ============================================================
# PATCH RESUMO COMPRA 80% E 50% - MAPA PREÇOS CLIENTES
# Recalcula compra máxima necessária a partir do menor preço.
# ============================================================

def _resumo_filtro_mapa(itens_filtrados):
    demanda_total = 0.0
    menor_preco = 0.0
    menor_preco_origem = ""
    menor_preco_descricao = ""
    menor_preco_eh_medbox = False

    for item in itens_filtrados:
        demanda_total += _demanda_item_mapa(item)

        preco = _valor_menor_preco_mapa(item)
        if preco <= 0:
            continue

        if menor_preco <= 0 or preco < menor_preco:
            menor_preco = preco
            menor_preco_origem = _descricao_origem_menor_preco_mapa(item)
            menor_preco_descricao = str(item.get("descricao") or item.get("descricao_original") or "")
            origem_norm = normalizar_texto_mapa(menor_preco_origem)
            menor_preco_eh_medbox = "MEDBOX" in origem_norm

    # Fórmula:
    # preço venda = custo compra x fator markup
    # custo compra máximo = preço venda / fator markup
    fator_80 = 1.80
    fator_50 = 1.50

    custo_compra_80 = 0.0
    custo_compra_50 = 0.0

    if menor_preco > 0:
        custo_compra_80 = menor_preco / fator_80
        custo_compra_50 = menor_preco / fator_50

    return {
        "demanda_total": demanda_total,
        "demanda_total_formatada": formatar_numero_mapa(demanda_total),

        "menor_preco": menor_preco,
        "menor_preco_formatado": _moeda_mapa_segura(menor_preco),
        "menor_preco_origem": menor_preco_origem or "Não identificado",
        "menor_preco_descricao": menor_preco_descricao,
        "menor_preco_eh_medbox": menor_preco_eh_medbox,

        "custo_compra_80": custo_compra_80,
        "custo_compra_80_formatado": _moeda_mapa_segura(custo_compra_80),

        "custo_compra_50": custo_compra_50,
        "custo_compra_50_formatado": _moeda_mapa_segura(custo_compra_50),

        # Mantém compatibilidade com o card antigo, se algum trecho ainda usar:
        "custo_necessario": custo_compra_80,
        "custo_necessario_formatado": _moeda_mapa_segura(custo_compra_80),

        "markup_percentual": 80,
        "markup_fator": fator_80,
        "total_itens_considerados": len(itens_filtrados),
    }



# ============================================================
# PATCH FLAG FATURAMENTO ESTIMADO DO FILTRO
# Soma faturamento estimado dos itens pesquisados/filtrados.
# ============================================================

def _faturamento_item_mapa(item):
    # Primeiro tenta usar campos já calculados no item consolidado.
    for chave in [
        "faturamento_estimado",
        "faturamento_estimado_valor",
        "faturamento",
        "faturamento_total",
    ]:
        valor = _float_mapa_seguro(item.get(chave), 0.0)
        if valor > 0:
            return valor

    demanda = _demanda_item_mapa(item)

    # Depois tenta calcular: demanda mensal x preço médio dos clientes.
    for chave in [
        "preco_medio_clientes",
        "preco_medio_cliente",
        "media_clientes",
        "preco_medio",
    ]:
        preco = _float_mapa_seguro(item.get(chave), 0.0)
        if demanda > 0 and preco > 0:
            return demanda * preco

    # Se não houver preço médio, usa preço MedBox.
    for chave in [
        "preco_medbox",
        "preco_venda_medbox",
        "preco_medbox_calculado",
    ]:
        preco = _float_mapa_seguro(item.get(chave), 0.0)
        if demanda > 0 and preco > 0:
            return demanda * preco

    return 0.0


def _resumo_filtro_mapa(itens_filtrados):
    demanda_total = 0.0
    faturamento_estimado_total = 0.0

    menor_preco = 0.0
    menor_preco_origem = ""
    menor_preco_descricao = ""
    menor_preco_eh_medbox = False

    for item in itens_filtrados:
        demanda_total += _demanda_item_mapa(item)
        faturamento_estimado_total += _faturamento_item_mapa(item)

        preco = _valor_menor_preco_mapa(item)
        if preco <= 0:
            continue

        if menor_preco <= 0 or preco < menor_preco:
            menor_preco = preco
            menor_preco_origem = _descricao_origem_menor_preco_mapa(item)
            menor_preco_descricao = str(item.get("descricao") or item.get("descricao_original") or "")
            origem_norm = normalizar_texto_mapa(menor_preco_origem)
            menor_preco_eh_medbox = "MEDBOX" in origem_norm

    fator_80 = 1.80
    fator_50 = 1.50

    custo_compra_80 = 0.0
    custo_compra_50 = 0.0

    if menor_preco > 0:
        custo_compra_80 = menor_preco / fator_80
        custo_compra_50 = menor_preco / fator_50

    return {
        "demanda_total": demanda_total,
        "demanda_total_formatada": formatar_numero_mapa(demanda_total),

        "faturamento_estimado_total": faturamento_estimado_total,
        "faturamento_estimado_total_formatado": _moeda_mapa_segura(faturamento_estimado_total),

        "menor_preco": menor_preco,
        "menor_preco_formatado": _moeda_mapa_segura(menor_preco),
        "menor_preco_origem": menor_preco_origem or "Não identificado",
        "menor_preco_descricao": menor_preco_descricao,
        "menor_preco_eh_medbox": menor_preco_eh_medbox,

        "custo_compra_80": custo_compra_80,
        "custo_compra_80_formatado": _moeda_mapa_segura(custo_compra_80),

        "custo_compra_50": custo_compra_50,
        "custo_compra_50_formatado": _moeda_mapa_segura(custo_compra_50),

        "custo_necessario": custo_compra_80,
        "custo_necessario_formatado": _moeda_mapa_segura(custo_compra_80),

        "markup_percentual": 80,
        "markup_fator": fator_80,
        "total_itens_considerados": len(itens_filtrados),
    }



# ============================================================
# PATCH QUANTIDADES INTEIRAS NA TELA - MAPA PREÇOS CLIENTES
# Mantém o banco original, mas exibe quantidades arredondadas
# para cima na tela.
# Ex.: 223,33 -> 224 | 61,67 -> 62
# ============================================================

import math as _math_mapa_quantidades

def _quantidade_inteira_mapa(valor):
    try:
        numero = _float_mapa_seguro(valor, 0.0)
    except Exception:
        try:
            numero = converter_float_mapa(valor)
        except Exception:
            numero = 0.0

    if numero <= 0:
        return ""

    inteiro = int(_math_mapa_quantidades.ceil(numero))
    return f"{inteiro:,}".replace(",", ".")


def _aplicar_quantidades_inteiras_tela_mapa(dados):
    try:
        itens = dados.get("itens", [])
    except Exception:
        return dados

    for item in itens:
        # Coluna fixa: Demanda mensal total
        for chave in [
            "demanda_mensal_total",
            "quantidade_mensal_total",
            "demanda_total",
            "quantidade_total",
        ]:
            if chave in item and _float_mapa_seguro(item.get(chave), 0.0) > 0:
                item["demanda_mensal_total_formatada"] = _quantidade_inteira_mapa(item.get(chave))
                break

        # Colunas dos clientes: Quant. mês
        clientes = item.get("clientes", {})
        if isinstance(clientes, dict):
            for _, celula in clientes.items():
                if not isinstance(celula, dict):
                    continue

                qtd = None
                for chave in [
                    "quantidade_mensal",
                    "quantidade_total",
                    "qtd_mensal",
                    "qtd",
                ]:
                    if chave in celula and _float_mapa_seguro(celula.get(chave), 0.0) > 0:
                        qtd = celula.get(chave)
                        break

                if qtd is None:
                    qtd = celula.get("quantidade_mensal_formatada")

                if qtd is not None:
                    celula["quantidade_mensal_formatada"] = _quantidade_inteira_mapa(qtd)

    return dados


_dados_tela_mapa_precos_clientes_antes_qtd_inteira = dados_tela_mapa_precos_clientes

def dados_tela_mapa_precos_clientes(q="", limite=300, pagina=1):
    dados = _dados_tela_mapa_precos_clientes_antes_qtd_inteira(
        q=q,
        limite=limite,
        pagina=pagina,
    )
    return _aplicar_quantidades_inteiras_tela_mapa(dados)

