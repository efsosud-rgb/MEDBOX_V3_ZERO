import sqlite3
import json
import logging
import traceback
from flask import Flask, Response, render_template, request, redirect, url_for, flash, jsonify
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode
from werkzeug.utils import secure_filename

from core.banco import (
    criar_banco, resumo_dashboard, conectar,
    listar_fornecedores, cadastrar_fornecedor, excluir_fornecedor,
    listar_sugestoes_busca,
    listar_equivalencias, adicionar_equivalencia, excluir_equivalencia,
    listar_produtos_simples, listar_cotacoes
)
from core.lances_cotacao import importar_lances_cotacao
from core.busca_inteligente import (
    buscar_produto_inteligente,
    buscar_produtos_por_fornecedor,
)
from core.auditoria_sku_master import (
    FILTROS as FILTROS_AUDITORIA_SKU,
    GRUPOS_SUGESTOES as GRUPOS_SUGESTOES_SKU,
    aplicar_correcao_sku_master,
    aplicar_correcao_manual_sku_master,
    aplicar_lote_correcoes_sku_master,
    gerar_auditoria_sku_master,
    gerar_csv_auditoria_sku_master,
    gerar_csv_sugestoes_sku_master,
    gerar_sugestoes_sku_master,
    previsualizar_lote_correcoes_sku_master,
    buscar_produtos_afetados_cascata,
    salvar_edicao_manual_produto,
    excluir_produto_logico,
)
from core.cotacao_lances_v2 import analisar_arquivo_cotacao, analisar_itens_manuais_lance, configurar_logger_cotacao, salvar_sku_rapido_lances, sugerir_skus_lances
from core.formatadores import moeda_br
from core.importador_sku import importar_sku_master

app = Flask(__name__)
app.secret_key = "medbox_v3_zero"

criar_banco()

BASE_DIR = Path(__file__).resolve().parent
PASTA_UPLOADS = BASE_DIR / "uploads"
PASTA_UPLOADS.mkdir(exist_ok=True)
PASTA_UPLOADS_LANCES = PASTA_UPLOADS / "cotacoes_lances"
PASTA_UPLOADS_LANCES.mkdir(exist_ok=True)

LOG_PATH = BASE_DIR / "debug_importacao.txt"

DATA_ATUAL = datetime.now().strftime("%d/%m/%Y")


def _criar_logger_requisicao() -> logging.Logger:
    logger = logging.getLogger("importacao")
    logger.setLevel(logging.DEBUG)

    for handler in logger.handlers[:]:
        handler.close()
        logger.removeHandler(handler)

    file_handler = logging.FileHandler(LOG_PATH, mode="w", encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)

    formatter = logging.Formatter(
        fmt="%(asctime)s.%(msecs)03d | %(message)s",
        datefmt="%H:%M:%S",
    )
    file_handler.setFormatter(formatter)

    class FlushFileHandler(logging.FileHandler):
        def emit(self, record):
            super().emit(record)
            self.flush()

    logger.handlers = []
    fh = FlushFileHandler(LOG_PATH, mode="w", encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(formatter)
    logger.addHandler(fh)
    logger.propagate = False

    return logger


def contar_produtos():
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM produtos WHERE ativo = 1")
    total = cursor.fetchone()[0]
    conn.close()
    return total


@app.route("/")
def dashboard():
    resumo = resumo_dashboard()
    return render_template(
        "dashboard.html",
        data_atual=DATA_ATUAL,
        resumo=resumo,
        total_produtos=contar_produtos()
    )


@app.route("/busca")
def busca():
    termo = request.args.get("q", "").strip()
    resultados = []
    sugestoes = []
    modo_busca = "produto"
    fornecedor_encontrado = None
    if termo:
        resultado_fornecedor = buscar_produtos_por_fornecedor(termo, limite=50)
        if resultado_fornecedor:
            modo_busca = "fornecedor"
            fornecedor_encontrado = resultado_fornecedor["fornecedor"]
            resultados = resultado_fornecedor["resultados"]
        else:
            resultados = buscar_produto_inteligente(termo, limite=20)
        for item in resultados:
            item["menor_preco_formatado"] = moeda_br(item.get("menor_preco"))
            if not item.get("tem_preco"):
                item["fornecedor_menor_formatado"] = "-"
                item["origem_catalogo"] = (
                    item.get("fabricante")
                    or (item.get("precos") or [{}])[0].get("marca")
                    or "Catalogo"
                )
                item["origem_catalogo_formatada"] = f"{item['origem_catalogo']} (catalogo)"
            else:
                item["fornecedor_menor_formatado"] = item.get("fornecedor_menor") or "-"
                item["origem_catalogo"] = ""
                item["origem_catalogo_formatada"] = ""
            for preco in item.get("precos", []):
                preco["preco_formatado"] = moeda_br(preco.get("preco"))
        sugestoes = listar_sugestoes_busca(termo)
    return render_template(
        "busca.html",
        data_atual=DATA_ATUAL,
        resumo=resumo_dashboard(),
        termo=termo,
        resultados=resultados,
        sugestoes=sugestoes,
        modo_busca=modo_busca,
        fornecedor_encontrado=fornecedor_encontrado
    )


@app.route("/produtos")
def produtos():
    return render_template(
        "produtos.html",
        data_atual=DATA_ATUAL,
        resumo=resumo_dashboard(),
        total_produtos=contar_produtos()
    )


@app.route("/sku-master/auditoria")
def sku_master_auditoria():
    q = request.args.get("q", "").strip()
    page = int(request.args.get("page", 1))
    # 'filtro' parameter is now ignored to focus on universal keyword search
    auditoria = gerar_auditoria_sku_master(filtro="todos", q=q, pagina=page, limite=50)
    return render_template(
        "sku_master_auditoria.html",
        data_atual=DATA_ATUAL,
        resumo=resumo_dashboard(),
        auditoria=auditoria,
        filtros=FILTROS_AUDITORIA_SKU,
    )


@app.route("/sku-master/auditoria.csv")
def sku_master_auditoria_csv():
    q = request.args.get("q", "").strip()
    conteudo = gerar_csv_auditoria_sku_master(filtro="todos", q=q)
    nome_arquivo = f"auditoria_sku_master.csv"
    return Response(
        conteudo,
        content_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename={nome_arquivo}"
        },
    )


@app.route("/sku-master/sugestoes")
def sku_master_sugestoes():
    grupo = request.args.get("grupo", "todos")
    sugestoes = gerar_sugestoes_sku_master(grupo=grupo, limite=250)
    return render_template(
        "sku_master_sugestoes.html",
        data_atual=DATA_ATUAL,
        resumo=resumo_dashboard(),
        sugestoes=sugestoes,
        grupos=GRUPOS_SUGESTOES_SKU,
    )


@app.route("/sku-master/sugestoes.csv")
def sku_master_sugestoes_csv():
    grupo = request.args.get("grupo", "todos")
    conteudo = gerar_csv_sugestoes_sku_master(grupo=grupo)
    nome_arquivo = f"sugestoes_sku_master_{grupo}.csv"
    return Response(
        conteudo,
        content_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename={nome_arquivo}"
        },
    )


@app.route("/sku-master/sugestoes/aplicar", methods=["POST"])
def sku_master_sugestoes_aplicar():
    grupo = request.form.get("grupo", "todos")
    try:
        resultado = aplicar_correcao_sku_master(
            produto_origem_id=request.form.get("produto_origem_id"),
            produto_destino_id=request.form.get("produto_destino_id"),
            sku_sugerido=request.form.get("sku_sugerido"),
            origem_sugestao=request.form.get("origem_sugestao"),
            usuario="compras",
        )
        flash(
            "Correcao aplicada: "
            f"{resultado['precos_migrados']} precos e "
            f"{resultado['equivalencias_migradas']} equivalencias migrados."
        )
    except Exception as erro:
        flash(f"Correcao nao aplicada: {erro}")
    return redirect(url_for("sku_master_sugestoes", grupo=grupo))


@app.route("/sku-master/sugestoes/aplicar-manual", methods=["POST"])
def sku_master_sugestoes_aplicar_manual():
    grupo = request.form.get("grupo", "todos")
    try:
        resultado = aplicar_correcao_manual_sku_master(
            produto_origem_id=request.form.get("produto_origem_id"),
            sku_manual=request.form.get("sku_manual"),
            usuario="compras",
        )
        acao_destino = "criado" if resultado["destino_criado"] else "existente"
        flash(
            "Correcao manual aplicada: "
            f"SKU destino {acao_destino}, "
            f"{resultado['precos_migrados']} precos e "
            f"{resultado['equivalencias_migradas']} equivalencias migrados."
        )
    except Exception as erro:
        flash(f"Correcao manual nao aplicada: {erro}")
    return redirect(url_for("sku_master_sugestoes", grupo=grupo))


def _itens_lote_do_formulario():
    itens = []
    for valor in request.form.getlist("itens_lote"):
        itens.append(json.loads(valor))
    return itens


@app.route("/sku-master/sugestoes/lote/previsualizar", methods=["POST"])
def sku_master_sugestoes_lote_previsualizar():
    grupo = request.form.get("grupo", "todos")
    try:
        itens = _itens_lote_do_formulario()
        preview = previsualizar_lote_correcoes_sku_master(itens)
        return render_template(
            "sku_master_lote_preview.html",
            data_atual=DATA_ATUAL,
            resumo=resumo_dashboard(),
            grupo=grupo,
            preview=preview,
        )
    except Exception as erro:
        flash(f"Lote nao pode ser previsualizado: {erro}")
        return redirect(url_for("sku_master_sugestoes", grupo=grupo))


@app.route("/sku-master/sugestoes/lote/aplicar", methods=["POST"])
def sku_master_sugestoes_lote_aplicar():
    grupo = request.form.get("grupo", "todos")
    try:
        itens = _itens_lote_do_formulario()
        resultado = aplicar_lote_correcoes_sku_master(itens, usuario="compras")
        flash(
            "Lote aplicado: "
            f"{resultado['total_itens']} itens, "
            f"{resultado['precos_migrados']} precos e "
            f"{resultado['equivalencias_migradas']} equivalencias migrados."
        )
    except Exception as erro:
        flash(f"Lote nao aplicado: {erro}")
    return redirect(url_for("sku_master_sugestoes", grupo=grupo))


@app.route("/importar_sku_master", methods=["POST"])
def importar_sku_master_rota():
    arquivo = request.files.get("arquivo")
    if not arquivo or arquivo.filename == "":
        return "Nenhum arquivo selecionado."
    caminho = PASTA_UPLOADS / arquivo.filename
    arquivo.save(caminho)
    try:
        importar_sku_master(caminho)
        return redirect(url_for("produtos"))
    except Exception as erro:
        return f"Erro ao importar SKU Master: {erro}"


@app.route("/fornecedores")
def fornecedores():
    return render_template(
        "fornecedores.html",
        data_atual=DATA_ATUAL,
        resumo=resumo_dashboard(),
        fornecedores=listar_fornecedores()
    )


@app.route("/fornecedores/cadastrar", methods=["POST"])
def cadastrar_fornecedor_rota():
    nome = request.form.get("nome", "").strip()
    tipo = request.form.get("tipo", "").strip()
    contato = request.form.get("contato", "").strip()
    email = request.form.get("email", "").strip()
    telefone = request.form.get("telefone", "").strip()
    if nome:
        cadastrar_fornecedor(nome, tipo, contato, email, telefone)
    return redirect(url_for("fornecedores"))


@app.route("/fornecedores/excluir/<int:fornecedor_id>", methods=["POST"])
def excluir_fornecedor_rota(fornecedor_id):
    excluir_fornecedor(fornecedor_id)
    return redirect(url_for("fornecedores"))


@app.route("/cotacoes")
def cotacoes():
    return render_template(
        "cotacoes.html",
        data_atual=DATA_ATUAL,
        resumo=resumo_dashboard(),
        cotacoes=listar_cotacoes(),
        fornecedores=listar_fornecedores()
    )




def analise_lances_vazia(markup_percentual=80):
    return {
        "arquivo": "",
        "itens_extraidos": 0,
        "total_linhas_arquivo": 0,
        "total_itens_com_quantidade": 0,
        "total_ignorados_quantidade_zero": 0,
        "total_ignorados_quantidade_vazia": 0,
        "total_ignorados_quantidade_invalida": 0,
        "markup_percentual": float(markup_percentual or 80),
        "itens": [],
        "resumo": {
            "total_itens": 0,
            "itens_com_sku": 0,
            "itens_revisar_sku": 0,
            "itens_com_preco_medbox": 0,
            "itens_sem_preco": 0,
            "itens_competitivos": 0,
            "itens_ganhos_medbox": 0,
            "percentual_itens_ganhos": 0,
            "percentual_itens_ganhos_formatado": "0,00%",
            "itens_negociar": 0,
            "total_medbox": 0,
            "total_medbox_formatado": "R$ 0,00",
            "total_ganho_medbox": 0,
            "total_ganho_medbox_formatado": "R$ 0,00",
            "total_menor_lance": 0,
            "total_menor_lance_formatado": "R$ 0,00",
        }
    }


@app.route("/cotacoes/lances")
def cotacoes_lances():
    return render_template(
        "cotacao_lances.html",
        data_atual=DATA_ATUAL,
        resumo=resumo_dashboard(),
        analise=analise_lances_vazia(80),
        erro=None,
        arquivo_nome="",
        markup_percentual=80,
    )


@app.route("/cotacoes/lances/importar", methods=["POST"])
def importar_cotacao_lances():
    log = _criar_logger_requisicao()
    configurar_logger_cotacao(log)

    log.debug("=" * 70)
    log.debug("INICIO: Rota /cotacoes/lances/importar chamada")
    log.debug("=" * 70)

    arquivo = request.files.get("arquivo")
    markup_percentual = request.form.get("markup_percentual", 80)

    log.debug(f"Arquivo recebido: {arquivo}")
    log.debug(f"Nome do arquivo : {arquivo.filename if arquivo else 'None'}")
    log.debug(f"Markup          : {markup_percentual}")

    if not arquivo or arquivo.filename == "":
        log.debug("ERRO: Nenhum arquivo selecionado")
        return render_template(
            "cotacao_lances.html",
            data_atual=DATA_ATUAL,
            resumo=resumo_dashboard(),
            analise=None,
            erro="Nenhum arquivo selecionado.",
            arquivo_nome="",
            markup_percentual=markup_percentual,
        ), 400

    nome_seguro = secure_filename(arquivo.filename)
    caminho = PASTA_UPLOADS_LANCES / nome_seguro
    log.debug(f"Salvando arquivo em: {caminho}")
    arquivo.save(caminho)
    tamanho = caminho.stat().st_size
    log.debug(f"Arquivo salvo. Tamanho: {tamanho} bytes ({tamanho / 1024:.1f} KB)")

    try:
        log.debug("Chamando analisar_arquivo_cotacao() ...")
        analise = analisar_arquivo_cotacao(caminho, markup_percentual=markup_percentual)
        total_itens = len(analise.get("itens", []))
        log.debug(f"analisar_arquivo_cotacao() concluiu. Total de itens: {total_itens}")
        log.debug("Renderizando template cotacao_lances.html ...")
        resposta = render_template(
            "cotacao_lances.html",
            data_atual=DATA_ATUAL,
            resumo=resumo_dashboard(),
            analise=analise,
            erro=None,
            arquivo_nome=arquivo.filename,
            markup_percentual=analise["markup_percentual"],
        )
        log.debug("Template renderizado. Enviando resposta ao cliente.")
        return resposta

    except Exception as erro:
        log.debug(f"EXCECAO capturada: {type(erro).__name__}: {erro}")
        log.debug("Traceback completo:")
        log.debug(traceback.format_exc())
        return render_template(
            "cotacao_lances.html",
            data_atual=DATA_ATUAL,
            resumo=resumo_dashboard(),
            analise=None,
            erro=str(erro),
            arquivo_nome=arquivo.filename,
            markup_percentual=markup_percentual,
        ), 400






@app.route("/cotacoes/lances/sugerir-skus")
def sugerir_skus_lances_rota():
    termo = request.args.get("q", "")
    try:
        sugestoes = sugerir_skus_lances(termo, limite=12)
        return jsonify({
            "ok": True,
            "sugestoes": sugestoes
        })
    except Exception as exc:
        return jsonify({
            "ok": False,
            "erro": str(exc),
            "sugestoes": []
        }), 500

@app.route("/cotacoes/lances/adicionar-itens", methods=["POST"])
def adicionar_itens_manuais_lances():
    """
    Adiciona vários itens manuais à Grade de Lances sem alterar o layout da tabela.
    Retorna JSON para o frontend anexar as linhas na grade atual.
    """
    texto_itens = request.form.get("texto_itens", "")
    markup_percentual = request.form.get("markup_percentual", 80)

    try:
        analise = analisar_itens_manuais_lance(
            texto_itens,
            markup_percentual=markup_percentual
        )

        if not analise.get("itens"):
            return jsonify({
                "ok": False,
                "erro": "Nenhum item válido foi informado."
            }), 400

        return jsonify({
            "ok": True,
            "analise": analise
        })

    except Exception as exc:
        return jsonify({
            "ok": False,
            "erro": str(exc)
        }), 500


# =========================================================
# COTAÇÕES GERADAS - LANCES
# =========================================================

EMPRESA_MEDBOX_COTACAO = {
    "razao_social": "MEDBOX DISTRIBUIDORA DE MEDICAMENTOS E MATERIAL HOSPITALAR LTDA",
    "cnpj": "37.141.903/0001-00",
    "endereco": "AV. PREFEITO ISOLDAKSON CRUZ DE BRITO, 158",
    "bairro": "VILA MARGARIDA",
    "cidade_uf": "ITAGUAÍ/RJ",
    "cep": "23.825-840",
    "email": "contato.medbox@gmail.com",
    "telefone": "(21) 2687-4954",
}


def moeda_float_lances(valor):
    valor = str(valor or "").strip()
    valor = valor.replace("R$", "").replace(" ", "")

    if not valor:
        return 0.0

    if "," in valor:
        valor = valor.replace(".", "").replace(",", ".")

    try:
        return float(valor)
    except Exception:
        return 0.0


def moeda_br_lances(valor):
    try:
        valor = float(valor or 0)
    except Exception:
        valor = 0.0

    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def garantir_tabelas_cotacoes_geradas():
    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS cotacoes_geradas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            numero_cotacao TEXT UNIQUE NOT NULL,
            data_emissao TEXT NOT NULL,
            cliente TEXT,
            empresa_nome TEXT,
            empresa_cnpj TEXT,
            empresa_endereco TEXT,
            empresa_email TEXT,
            empresa_telefone TEXT,
            validade_dias INTEGER DEFAULT 7,
            total_geral REAL DEFAULT 0,
            criado_em TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS cotacoes_geradas_itens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cotacao_id INTEGER NOT NULL,
            item_numero INTEGER,
            descricao_produto TEXT,
            sku_master TEXT,
            marca TEXT,
            quantidade REAL DEFAULT 0,
            valor_unitario REAL DEFAULT 0,
            valor_total REAL DEFAULT 0,
            venceu_medbox INTEGER DEFAULT 0,
            status_lance TEXT,
            FOREIGN KEY(cotacao_id) REFERENCES cotacoes_geradas(id)
        )
    """)

    conn.commit()
    conn.close()


def proximo_numero_cotacao():
    garantir_tabelas_cotacoes_geradas()

    ano = datetime.now().year
    prefixo = f"MEDBOX-{ano}-"

    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
        SELECT numero_cotacao
        FROM cotacoes_geradas
        WHERE numero_cotacao LIKE ?
        ORDER BY id DESC
        LIMIT 1
    """, (prefixo + "%",))

    row = cur.fetchone()
    conn.close()

    if not row:
        sequencial = 1
    else:
        ultimo = row[0] if not isinstance(row, sqlite3.Row) else row["numero_cotacao"]
        try:
            sequencial = int(str(ultimo).split("-")[-1]) + 1
        except Exception:
            sequencial = 1

    return f"{prefixo}{sequencial:06d}"


def carregar_cotacao_gerada(numero_cotacao):
    garantir_tabelas_cotacoes_geradas()

    conn = conectar()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM cotacoes_geradas
        WHERE numero_cotacao = ?
        LIMIT 1
    """, (numero_cotacao,))

    cotacao = cur.fetchone()

    if not cotacao:
        conn.close()
        return None, []

    cur.execute("""
        SELECT *
        FROM cotacoes_geradas_itens
        WHERE cotacao_id = ?
        ORDER BY item_numero ASC, id ASC
    """, (cotacao["id"],))

    itens = cur.fetchall()
    conn.close()

    return dict(cotacao), [dict(i) for i in itens]


@app.route("/cotacoes/lances/gerar-cotacao", methods=["POST"])
def gerar_cotacao_lances():
    garantir_tabelas_cotacoes_geradas()

    try:
        payload = request.get_json(force=True) or {}
        itens_payload = payload.get("itens") or []
        cliente = str(payload.get("cliente") or "").strip().upper()

        if not itens_payload:
            return jsonify({
                "ok": False,
                "erro": "Nenhum item foi enviado para gerar a cotação."
            }), 400

        numero = proximo_numero_cotacao()
        data_emissao = datetime.now().strftime("%d/%m/%Y")

        itens_final = []
        total_geral = 0.0

        for idx, item in enumerate(itens_payload, start=1):
            quantidade = moeda_float_lances(item.get("quantidade"))
            preco_medbox = moeda_float_lances(item.get("preco_medbox"))
            vencedor = str(item.get("vencedor") or "").upper()
            status = str(item.get("status") or "").upper()

            venceu_medbox = 1 if ("MEDBOX" in vencedor or status == "COMPETITIVO") and preco_medbox > 0 else 0

            valor_unitario = preco_medbox if venceu_medbox else 0.0
            valor_total = quantidade * valor_unitario

            total_geral += valor_total

            itens_final.append({
                "item_numero": idx,
                "descricao_produto": str(item.get("descricao_produto") or "").strip().upper(),
                "sku_master": str(item.get("sku_master") or "").strip().upper(),
                "marca": str(item.get("marca") or "").strip().upper(),
                "quantidade": quantidade,
                "valor_unitario": valor_unitario,
                "valor_total": valor_total,
                "venceu_medbox": venceu_medbox,
                "status_lance": status,
            })

        conn = conectar()
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO cotacoes_geradas (
                numero_cotacao,
                data_emissao,
                cliente,
                empresa_nome,
                empresa_cnpj,
                empresa_endereco,
                empresa_email,
                empresa_telefone,
                validade_dias,
                total_geral
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            numero,
            data_emissao,
            cliente,
            EMPRESA_MEDBOX_COTACAO["razao_social"],
            EMPRESA_MEDBOX_COTACAO["cnpj"],
            f'{EMPRESA_MEDBOX_COTACAO["endereco"]} - {EMPRESA_MEDBOX_COTACAO["bairro"]} - {EMPRESA_MEDBOX_COTACAO["cidade_uf"]} - CEP {EMPRESA_MEDBOX_COTACAO["cep"]}',
            EMPRESA_MEDBOX_COTACAO["email"],
            EMPRESA_MEDBOX_COTACAO["telefone"],
            7,
            total_geral,
        ))

        cotacao_id = cur.lastrowid

        for item in itens_final:
            cur.execute("""
                INSERT INTO cotacoes_geradas_itens (
                    cotacao_id,
                    item_numero,
                    descricao_produto,
                    sku_master,
                    marca,
                    quantidade,
                    valor_unitario,
                    valor_total,
                    venceu_medbox,
                    status_lance
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                cotacao_id,
                item["item_numero"],
                item["descricao_produto"],
                item["sku_master"],
                item["marca"],
                item["quantidade"],
                item["valor_unitario"],
                item["valor_total"],
                item["venceu_medbox"],
                item["status_lance"],
            ))

        conn.commit()
        conn.close()

        return jsonify({
            "ok": True,
            "numero_cotacao": numero,
            "url": url_for("abrir_cotacao_gerada", numero_cotacao=numero)
        })

    except Exception as exc:
        return jsonify({
            "ok": False,
            "erro": str(exc)
        }), 500


@app.route("/cotacoes/geradas")
def cotacoes_geradas():
    garantir_tabelas_cotacoes_geradas()

    busca = str(request.args.get("q") or "").strip().upper()

    conn = conectar()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    if busca:
        cur.execute("""
            SELECT *
            FROM cotacoes_geradas
            WHERE numero_cotacao LIKE ?
            ORDER BY id DESC
            LIMIT 50
        """, (f"%{busca}%",))
    else:
        cur.execute("""
            SELECT *
            FROM cotacoes_geradas
            ORDER BY id DESC
            LIMIT 50
        """)

    cotacoes = [dict(r) for r in cur.fetchall()]
    conn.close()

    if busca and len(cotacoes) == 1 and cotacoes[0]["numero_cotacao"] == busca:
        return redirect(url_for("abrir_cotacao_gerada", numero_cotacao=busca))

    return render_template(
        "cotacao_gerada.html",
        modo="lista",
        cotacoes=cotacoes,
        busca=busca,
        empresa=EMPRESA_MEDBOX_COTACAO,
        data_atual=DATA_ATUAL,
        resumo=resumo_dashboard(),
    )


@app.route("/cotacoes/geradas/<numero_cotacao>")
def abrir_cotacao_gerada(numero_cotacao):
    cotacao, itens = carregar_cotacao_gerada(numero_cotacao)

    if not cotacao:
        flash("Cotação não encontrada.", "erro")
        return redirect(url_for("cotacoes_geradas"))

    total_formatado = moeda_br_lances(cotacao.get("total_geral", 0))

    for item in itens:
        item["valor_unitario_formatado"] = moeda_br_lances(item.get("valor_unitario", 0))
        item["valor_total_formatado"] = moeda_br_lances(item.get("valor_total", 0))

    return render_template(
        "cotacao_gerada.html",
        modo="detalhe",
        cotacao=cotacao,
        itens=itens,
        empresa=EMPRESA_MEDBOX_COTACAO,
        total_formatado=total_formatado,
        data_atual=DATA_ATUAL,
        resumo=resumo_dashboard(),
    )


@app.route("/cotacoes/lances/salvar-sku", methods=["POST"])
def cotacoes_lances_salvar_sku():
    data = request.get_json(force=True) or {}

    resultado = salvar_sku_rapido_lances(
        descricao_cotacao=data.get("descricao_cotacao", ""),
        sku_master=data.get("sku_master", ""),
        fornecedor=data.get("fornecedor", ""),
        fabricante=data.get("fabricante", ""),
        categoria=data.get("categoria", ""),
    )

    return resultado

@app.route("/cotacoes/importar", methods=["POST"])
def importar_cotacao_rota():
    arquivo = request.files.get("arquivo")
    fornecedor_id = request.form.get("fornecedor_id")
    if not arquivo or arquivo.filename == "":
        return "Nenhum arquivo selecionado."
    if not fornecedor_id:
        return "Selecione um fornecedor."
    caminho = PASTA_UPLOADS / arquivo.filename
    arquivo.save(caminho)
    try:
        from core.importador_cotacao import importar_cotacao
        importar_cotacao(caminho, int(fornecedor_id))
        return redirect(url_for("cotacoes"))
    except Exception as erro:
        return f"Erro ao importar cotação: {erro}"


@app.route("/equivalencias")
def equivalencias():
    return render_template(
        "equivalencias.html",
        data_atual=DATA_ATUAL,
        resumo=resumo_dashboard(),
        equivalencias=listar_equivalencias(),
        produtos=listar_produtos_simples()
    )


@app.route("/equivalencias/adicionar", methods=["POST"])
def adicionar_equivalencia_rota():
    produto_id = request.form.get("produto_id")
    descricao = request.form.get("descricao", "").strip()
    if produto_id and descricao:
        adicionar_equivalencia(int(produto_id), descricao)
    return redirect(url_for("equivalencias"))


@app.route("/equivalencias/excluir/<int:equivalencia_id>", methods=["POST"])
def excluir_equivalencia_rota(equivalencia_id):
    excluir_equivalencia(equivalencia_id)
    return redirect(url_for("equivalencias"))




# ============================================================
# MAPA DE PREÇOS CLIENTES
# ============================================================

@app.route("/mapa-precos-clientes")
def mapa_precos_clientes():
    from core.mapa_precos_clientes import dados_tela_mapa_precos_clientes

    q = request.args.get("q", "").strip()
    limite = request.args.get("limite", "300").strip()
    pagina = request.args.get("pagina", "1").strip()

    dados = dados_tela_mapa_precos_clientes(q=q, limite=limite, pagina=pagina)

    return render_template(
        "mapa_precos_clientes.html",
        data_atual=DATA_ATUAL,
        resumo=resumo_dashboard(),
        dados=dados,
    )


@app.route("/mapa-precos-clientes/importar")
def mapa_precos_clientes_importar():
    from core.mapa_precos_clientes import listar_clientes_mapa_precos, listar_cotacoes_mapa_precos

    sucesso = request.args.get("sucesso", "").strip()
    erro = request.args.get("erro", "").strip()

    return render_template(
        "mapa_precos_clientes_importar.html",
        data_atual=DATA_ATUAL,
        resumo=resumo_dashboard(),
        clientes=listar_clientes_mapa_precos(),
        cotacoes=listar_cotacoes_mapa_precos(),
        sucesso=sucesso,
        erro=erro,
    )




@app.route("/mapa-precos-clientes/importar", methods=["POST"])
def mapa_precos_clientes_importar_post():
    arquivo = request.files.get("arquivo")
    cliente_id = request.form.get("cliente_id", "").strip()
    nome_cliente_novo = request.form.get("nome_cliente_novo", "").strip()
    meses_referencia = request.form.get("meses_referencia", "1").strip()
    data_referencia = request.form.get("data_referencia", "").strip()
    observacao = request.form.get("observacao", "").strip()

    if not arquivo or arquivo.filename == "":
        return redirect(url_for("mapa_precos_clientes_importar") + "?erro=Nenhum arquivo selecionado.")

    if not cliente_id and not nome_cliente_novo:
        return redirect(url_for("mapa_precos_clientes_importar") + "?erro=Selecione um cliente ou informe novo cliente.")

    caminho = PASTA_UPLOADS / secure_filename(arquivo.filename)
    arquivo.save(caminho)

    try:
        from core.mapa_precos_clientes import importar_cotacao_cliente_mapa

        resultado = importar_cotacao_cliente_mapa(
            caminho=caminho,
            cliente_id=cliente_id or None,
            nome_cliente_novo=nome_cliente_novo,
            meses_referencia=meses_referencia,
            data_referencia=data_referencia,
            observacao=observacao,
        )

        msg = (
            f"Cotação importada com sucesso. "
            f"Itens: {resultado['total_importado']} | "
            f"Sem SKU: {resultado['total_sem_sku']} | "
            f"Meses: {resultado['meses_referencia']}"
        )

        return redirect(url_for("mapa_precos_clientes_importar") + "?" + urlencode({"sucesso": msg}))

    except Exception as erro:
        return redirect(url_for("mapa_precos_clientes_importar") + "?" + urlencode({"erro": str(erro)}))




@app.route("/mapa-precos-clientes/atualizar-item", methods=["POST"])
def mapa_precos_clientes_atualizar_item():
    try:
        data = request.get_json(force=True) or {}

        from core.mapa_precos_clientes import atualizar_item_mapa_precos

        resultado = atualizar_item_mapa_precos(
            grupo_key=data.get("grupo_key", ""),
            sku_master=data.get("sku_master", ""),
            categoria=data.get("categoria", ""),
        )

        return jsonify(resultado)

    except Exception as erro:
        return jsonify({
            "ok": False,
            "erro": str(erro),
        }), 400




@app.route("/mapa-precos-clientes/skus-json")
def mapa_precos_clientes_skus_json():
    termo = request.args.get("q", "").strip().upper()

    conn = conectar()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    if termo:
        cur.execute("""
            SELECT DISTINCT TRIM(sku_master) AS sku
            FROM produtos
            WHERE ativo = 1
              AND sku_master IS NOT NULL
              AND TRIM(sku_master) != ''
              AND UPPER(sku_master) LIKE ?
            ORDER BY sku_master
            LIMIT 50
        """, (f"%{termo}%",))
    else:
        cur.execute("""
            SELECT DISTINCT TRIM(sku_master) AS sku
            FROM produtos
            WHERE ativo = 1
              AND sku_master IS NOT NULL
              AND TRIM(sku_master) != ''
            ORDER BY sku_master
            LIMIT 50
        """)

    skus = [row["sku"] for row in cur.fetchall() if row["sku"]]
    conn.close()

    return jsonify({
        "ok": True,
        "skus": skus,
    })




@app.route("/mapa-precos-clientes/atualizar-valor-cliente", methods=["POST"])
def mapa_precos_clientes_atualizar_valor_cliente():
    try:
        data = request.get_json(force=True) or {}

        from core.mapa_precos_clientes import atualizar_valor_cliente_mapa

        resultado = atualizar_valor_cliente_mapa(
            grupo_key=data.get("grupo_key", ""),
            cliente_id=data.get("cliente_id"),
            valor_unitario=data.get("valor_unitario", 0),
        )

        return jsonify(resultado)

    except Exception as erro:
        return jsonify({
            "ok": False,
            "erro": str(erro),
        }), 400


@app.route("/importacoes")
def importacoes():
    return render_template(
        "importacoes.html",
        data_atual=DATA_ATUAL,
        resumo=resumo_dashboard(),
        fornecedores=listar_fornecedores(),
        cotacoes=listar_cotacoes()
    )


@app.route("/importacoes/importar", methods=["POST"])
def importar_fornecedor_rota():
    arquivo = request.files.get("arquivo")
    nome_fornecedor = request.form.get("nome_fornecedor", "").strip()
    tipo_fornecedor = request.form.get("tipo_fornecedor", "Distribuidor").strip()
    fornecedor_id = request.form.get("fornecedor_id", "").strip()

    if not arquivo or arquivo.filename == "":
        return "Nenhum arquivo selecionado."
    if not nome_fornecedor and not fornecedor_id:
        return "Informe o fornecedor."

    caminho = PASTA_UPLOADS / arquivo.filename
    arquivo.save(caminho)

    try:
        if fornecedor_id:
            fid = int(fornecedor_id)
            conn = conectar()
            cursor = conn.cursor()
            cursor.execute("SELECT nome, tipo FROM fornecedores WHERE id = ?", (fid,))
            row = cursor.fetchone()
            conn.close()
            if not row:
                return "Fornecedor não encontrado."
            nome_fornecedor = row["nome"]
            tipo_fornecedor = row["tipo"]
        else:
            cadastrar_fornecedor(nome_fornecedor, tipo_fornecedor)
            conn = conectar()
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM fornecedores ORDER BY id DESC LIMIT 1")
            row = cursor.fetchone()
            conn.close()
            if not row:
                return "Erro ao localizar fornecedor cadastrado."
            fid = row["id"]

        from core.importador_universal import importar_arquivo_fornecedor
        total = importar_arquivo_fornecedor(caminho, fid, nome_fornecedor, tipo_fornecedor)
        return redirect(url_for("importacoes") + f"?sucesso={total}&nome={nome_fornecedor}")

    except Exception as erro:
        query = urlencode({"erro": str(erro)})
        return redirect(url_for("importacoes") + f"?{query}")


@app.route("/importacoes/importar_xml", methods=["POST"])
def importar_xml_nfe_rota():
    arquivo = request.files.get("arquivo_xml")
    if not arquivo or arquivo.filename == "":
        return "Nenhum arquivo XML selecionado."
    caminho = PASTA_UPLOADS / arquivo.filename
    arquivo.save(caminho)
    try:
        from core.importador_xml_nfe import importar_xml_nfe
        resultado = importar_xml_nfe(caminho)
        total = resultado.get("itens_importados", 0)
        fornecedor = resultado.get("fornecedor", "XML NF-e")
        return redirect(url_for("importacoes") + f"?sucesso={total}&nome={fornecedor}")
    except Exception as erro:
        return f"Erro ao importar XML NF-e: {erro}"




@app.route("/importacoes/manual", methods=["POST"])
def importar_itens_manuais_fornecedor():
    """
    Lançamento manual de itens cotados por fornecedor.

    Objetivo:
    - cadastrar/localizar fornecedor;
    - cadastrar/localizar produto;
    - salvar SKU Master, fabricante e categoria;
    - registrar preço na base de fornecedores;
    - registrar o lançamento no histórico de importações.
    """
    data = request.get_json(force=True) or {}

    fornecedor_id = str(data.get("fornecedor_id") or "").strip()
    nome_fornecedor = str(data.get("nome_fornecedor") or "").strip()
    tipo_fornecedor = str(data.get("tipo_fornecedor") or "Distribuidor").strip() or "Distribuidor"
    itens = data.get("itens") or []

    if not fornecedor_id and not nome_fornecedor:
        return jsonify({"ok": False, "erro": "Informe ou selecione um fornecedor."}), 400

    if not itens:
        return jsonify({"ok": False, "erro": "Informe ao menos um item."}), 400

    from core.banco import cadastrar_fornecedor, registrar_preco_fornecedor, registrar_cotacao, normalizar_texto, converter_float

    conn = conectar()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    try:
        if fornecedor_id:
            fid = int(fornecedor_id)
            cur.execute("SELECT id, nome, tipo FROM fornecedores WHERE id = ? AND ativo = 1", (fid,))
            fornecedor = cur.fetchone()

            if not fornecedor:
                conn.close()
                return jsonify({"ok": False, "erro": "Fornecedor selecionado não encontrado."}), 404

            nome_fornecedor_final = fornecedor["nome"]
            tipo_fornecedor_final = fornecedor["tipo"] or tipo_fornecedor
        else:
            conn.close()
            fid = cadastrar_fornecedor(nome_fornecedor, tipo_fornecedor)
            conn = conectar()
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            nome_fornecedor_final = normalizar_texto(nome_fornecedor)
            tipo_fornecedor_final = tipo_fornecedor

        total_salvo = 0
        erros = []

        for idx, item in enumerate(itens, start=1):
            descricao = normalizar_texto(item.get("descricao"))
            sku_master = normalizar_texto(item.get("sku_master") or descricao)
            fabricante = normalizar_texto(item.get("fabricante"))
            categoria = normalizar_texto(item.get("categoria"))
            codigo_fornecedor = str(item.get("codigo_fornecedor") or "").strip()
            preco = converter_float(item.get("preco_unitario"))
            observacao = str(item.get("observacao") or "").strip()

            if not descricao:
                erros.append(f"Item {idx}: descrição vazia.")
                continue

            if preco <= 0:
                erros.append(f"Item {idx}: preço unitário inválido.")
                continue

            # Localiza produto por SKU Master ou produto padrão.
            cur.execute("""
                SELECT id
                FROM produtos
                WHERE ativo = 1
                  AND (
                        UPPER(COALESCE(sku_master, '')) = UPPER(?)
                        OR UPPER(COALESCE(produto_padrao, '')) = UPPER(?)
                  )
                ORDER BY id
                LIMIT 1
            """, (sku_master, descricao))

            produto = cur.fetchone()

            if produto:
                produto_id = produto["id"]

                cur.execute("""
                    UPDATE produtos
                    SET sku_master = COALESCE(NULLIF(?, ''), sku_master),
                        fabricante = COALESCE(NULLIF(?, ''), fabricante),
                        categoria = COALESCE(NULLIF(?, ''), categoria),
                        observacoes = COALESCE(NULLIF(?, ''), observacoes),
                        ativo = 1
                    WHERE id = ?
                """, (
                    sku_master,
                    fabricante,
                    categoria,
                    observacao,
                    produto_id,
                ))
            else:
                cur.execute("""
                    INSERT INTO produtos (
                        sku,
                        produto_padrao,
                        sku_master,
                        fabricante,
                        categoria,
                        ativo,
                        observacoes
                    )
                    VALUES (?, ?, ?, ?, ?, 1, ?)
                """, (
                    sku_master,
                    descricao,
                    sku_master,
                    fabricante,
                    categoria,
                    observacao,
                ))
                produto_id = cur.lastrowid

            registrar_preco_fornecedor(
                fornecedor_id=fid,
                produto_id=produto_id,
                descricao_original=descricao,
                codigo_fornecedor=codigo_fornecedor,
                marca=fabricante,
                preco=preco,
                arquivo_origem="LANCAMENTO MANUAL",
                origem_importacao="MANUAL_FORNECEDOR",
                conn_existente=conn,
            )

            total_salvo += 1

        conn.commit()
        conn.close()

        if total_salvo > 0:
            registrar_cotacao(
                fornecedor_id=fid,
                arquivo_origem="LANCAMENTO MANUAL",
                total_itens=total_salvo,
            )

        return jsonify({
            "ok": True,
            "mensagem": f"{total_salvo} item(ns) manual(is) salvo(s) para {nome_fornecedor_final}.",
            "total": total_salvo,
            "fornecedor": nome_fornecedor_final,
            "erros": erros[:10],
            "url": url_for("importacoes") + f"?sucesso={total_salvo}&nome={nome_fornecedor_final}",
        })

    except Exception as erro:
        try:
            conn.rollback()
            conn.close()
        except Exception:
            pass

        return jsonify({"ok": False, "erro": str(erro)}), 500


@app.route("/historico")
def historico():
    return render_template(
        "placeholder.html",
        data_atual=DATA_ATUAL,
        resumo=resumo_dashboard(),
        titulo="Histórico de Preços",
        subtitulo="Consulta de evolução de preços por produto e fornecedor."
    )


@app.route("/relatorios")
def relatorios():
    return render_template(
        "placeholder.html",
        data_atual=DATA_ATUAL,
        resumo=resumo_dashboard(),
        titulo="Relatórios",
        subtitulo="Análises de compras, economia, fornecedores e oportunidades."
    )


@app.route("/configuracoes")
def configuracoes():
    return render_template(
        "placeholder.html",
        data_atual=DATA_ATUAL,
        resumo=resumo_dashboard(),
        titulo="Configurações",
        subtitulo="Parâmetros do sistema MedBox V3."
    )


@app.route("/sku-master/marcas-json")
def sku_master_marcas_json():
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(
        """SELECT DISTINCT fabricante FROM produtos
           WHERE ativo = 1 AND fabricante IS NOT NULL AND TRIM(fabricante) != ''
           ORDER BY fabricante"""
    )
    marcas = [row["fabricante"] for row in cursor.fetchall()]
    conn.close()
    return Response(json.dumps(marcas, ensure_ascii=False), content_type="application/json")


@app.route("/sku-master/categorias-json")
def sku_master_categorias_json():
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(
        """SELECT DISTINCT categoria FROM produtos
           WHERE ativo = 1 AND categoria IS NOT NULL AND TRIM(categoria) != ''
           ORDER BY categoria"""
    )
    categorias = [row["categoria"] for row in cursor.fetchall()]
    conn.close()
    return Response(json.dumps(categorias, ensure_ascii=False), content_type="application/json")


@app.route("/sku-master/auditoria/preview-cascata", methods=["POST"])
def sku_master_auditoria_preview_cascata():
    data = request.get_json(force=True) or {}
    produto_id = data.get("produto_id")
    tipos = data.get("tipos", [])

    todos_afetados = []
    ids_vistos = set()

    for tipo in tipos:
        afetados = buscar_produtos_afetados_cascata(produto_id, tipo)
        for a in afetados:
            if a["id"] not in ids_vistos:
                todos_afetados.append(a)
                ids_vistos.add(a["id"])

    return Response(
        json.dumps({"total": len(todos_afetados), "itens": todos_afetados}, ensure_ascii=False),
        content_type="application/json",
    )


@app.route("/sku-master/auditoria/salvar-edicao", methods=["POST"])
def sku_master_auditoria_salvar_edicao():
    data = request.get_json(force=True) or {}
    produto_id = data.get("produto_id")
    dados = data.get("dados", {})
    opcoes_cascata = data.get("opcoes_cascata", [])
    ids_cascata_selecionados = data.get("ids_cascata_selecionados")

    try:
        resultado = salvar_edicao_manual_produto(
            produto_id=produto_id,
            dados_novos=dados,
            opcoes_cascata=opcoes_cascata,
            ids_cascata_selecionados=ids_cascata_selecionados,
            usuario="compras"
        )
        return Response(
            json.dumps(resultado, ensure_ascii=False),
            content_type="application/json",
        )
    except Exception as e:
        return Response(
            json.dumps({"ok": False, "erro": str(e)}, ensure_ascii=False),
            content_type="application/json",
        ), 400


@app.route("/sku-master/auditoria/excluir/<int:produto_id>", methods=["POST"])
def sku_master_auditoria_excluir(produto_id):
    try:
        resultado = excluir_produto_logico(
            produto_id=produto_id,
            usuario="compras"
        )
        return Response(
            json.dumps(resultado, ensure_ascii=False),
            content_type="application/json",
        )
    except Exception as e:
        return Response(
            json.dumps({"ok": False, "erro": str(e)}, ensure_ascii=False),
            content_type="application/json",
        ), 400


@app.route("/sku-master/auditoria/salvar-sku-ajax", methods=["POST"])
def sku_master_auditoria_salvar_sku_ajax():
    data = request.get_json(force=True) or {}
    produto_id = data.get("produto_id")
    sku_manual = str(data.get("sku_manual", "")).strip()
    try:
        resultado = aplicar_correcao_manual_sku_master(
            produto_origem_id=produto_id,
            sku_manual=sku_manual,
            usuario="compras",
        )
        acao = "criado" if resultado["destino_criado"] else "existente"
        return Response(
            json.dumps({
                "ok": True,
                "mensagem": (
                    f"SKU salvo: destino {acao}, "
                    f"{resultado['precos_migrados']} precos e "
                    f"{resultado['equivalencias_migradas']} equivalencias migrados."
                ),
                "sku_novo": sku_manual,
            }, ensure_ascii=False),
            content_type="application/json",
        )
    except Exception as e:
        return Response(
            json.dumps({"ok": False, "erro": str(e)}, ensure_ascii=False),
            content_type="application/json",
        )


@app.route("/sku-master/auditoria/corrigir-todos", methods=["POST"])
def sku_master_auditoria_corrigir_todos():
    itens_raw = request.form.get("itens", "[]")
    try:
        itens = json.loads(itens_raw)
        aplicados = 0
        erros = []
        for item in itens:
            pid = item.get("produto_id")
            sku = str(item.get("sku_manual", "")).strip()
            if not sku:
                continue
            try:
                aplicar_correcao_manual_sku_master(
                    produto_origem_id=pid,
                    sku_manual=sku,
                    usuario="compras",
                )
                aplicados += 1
            except Exception as e:
                erros.append(f"id={pid}: {str(e)[:60]}")
        msg = f"Corrigir Todos: {aplicados} SKU(s) aplicado(s)."
        if erros:
            msg += f" {len(erros)} erro(s): " + "; ".join(erros[:3])
        flash(msg)
    except Exception as e:
        flash(f"Erro em Corrigir Todos: {e}")
    return redirect(url_for("sku_master_auditoria"))


@app.route("/sku-master/skus-json")
def sku_master_skus_json():
    conn = conectar()
    cursor = conn.cursor()
    # Use COALESCE to prioritize sku_master over produto_padrao in suggestions
    cursor.execute(
        """SELECT DISTINCT COALESCE(NULLIF(TRIM(sku_master), ''), produto_padrao) as sku
           FROM produtos
           WHERE ativo = 1
           ORDER BY sku"""
    )
    skus = [row["sku"] for row in cursor.fetchall() if row["sku"]]
    conn.close()
    return Response(json.dumps(skus, ensure_ascii=False), content_type="application/json")


@app.route("/sku-master/auditoria/salvar-sku", methods=["POST"])
def sku_master_auditoria_salvar_sku():
    produto_id = request.form.get("produto_id")
    sku_manual = request.form.get("sku_manual", "").strip()
    try:
        resultado = aplicar_correcao_manual_sku_master(
            produto_origem_id=produto_id,
            sku_manual=sku_manual,
            usuario="compras",
        )
        acao = "criado" if resultado["destino_criado"] else "existente"
        flash(
            f"SKU salvo: destino {acao}, "
            f"{resultado['precos_migrados']} precos e "
            f"{resultado['equivalencias_migradas']} equivalencias migrados."
        )
    except Exception as erro:
        flash(f"Erro ao salvar SKU: {erro}")
    return redirect(url_for("sku_master_auditoria"))




# ============================================================
# OVERRIDE FINAL - COTAÇÃO GERADA COM OSINFO x LANCE x MEDBOX
# ============================================================

def _medbox_float_cotacao_gerada(valor, padrao=0.0):
    try:
        if valor is None:
            return padrao

        if isinstance(valor, (int, float)):
            return float(valor)

        texto = str(valor).strip()
        texto = texto.replace("R$", "").replace("%", "").strip()

        if not texto:
            return padrao

        texto = texto.replace(".", "").replace(",", ".")

        return float(texto)
    except Exception:
        return padrao


def _medbox_moeda_cotacao_gerada(valor):
    valor = _medbox_float_cotacao_gerada(valor, 0.0)
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _medbox_calcular_disputa_cotacao(preco_osinfo=0, menor_lance=0, preco_medbox=0, empresa_melhor_lance=""):
    preco_osinfo = _medbox_float_cotacao_gerada(preco_osinfo)
    menor_lance = _medbox_float_cotacao_gerada(menor_lance)
    preco_medbox = _medbox_float_cotacao_gerada(preco_medbox)

    opcoes = []

    if preco_osinfo > 0:
        opcoes.append(("OSINFO", "OSINFO", preco_osinfo))

    if menor_lance > 0:
        opcoes.append(("LANCE", empresa_melhor_lance or "LANCE GANHADOR", menor_lance))

    if preco_medbox > 0:
        opcoes.append(("MEDBOX", "MEDBOX", preco_medbox))

    if not opcoes:
        return {
            "menor_origem": "-",
            "menor_empresa": "-",
            "menor_valor": 0.0,
            "medbox_vencedora": False,
        }

    opcoes.sort(key=lambda x: x[2])
    origem, empresa, valor = opcoes[0]

    return {
        "menor_origem": origem,
        "menor_empresa": empresa,
        "menor_valor": valor,
        "medbox_vencedora": origem == "MEDBOX",
    }


def _medbox_garantir_colunas_cotacao_gerada():
    try:
        garantir_tabelas_cotacoes_geradas()
    except Exception:
        pass

    conn = conectar()
    cur = conn.cursor()

    cur.execute("PRAGMA table_info(cotacoes_geradas_itens)")
    existentes = {row[1] for row in cur.fetchall()}

    novas_colunas = {
        "preco_osinfo": "REAL DEFAULT 0",
        "menor_lance": "REAL DEFAULT 0",
        "preco_medbox_original": "REAL DEFAULT 0",
        "empresa_melhor_lance": "TEXT",
        "menor_origem": "TEXT",
        "menor_empresa": "TEXT",
        "menor_valor_comparativo": "REAL DEFAULT 0",
        "medbox_vencedora": "INTEGER DEFAULT 0",
    }

    for coluna, tipo in novas_colunas.items():
        if coluna not in existentes:
            cur.execute(f"ALTER TABLE cotacoes_geradas_itens ADD COLUMN {coluna} {tipo}")

    conn.commit()
    conn.close()


def _medbox_enriquecer_cotacao_gerada(cotacao):
    if not cotacao:
        return cotacao

    itens = cotacao.get("itens", [])

    for item in itens:
        preco_osinfo = _medbox_float_cotacao_gerada(item.get("preco_osinfo", 0))
        menor_lance = _medbox_float_cotacao_gerada(item.get("menor_lance", 0))
        preco_medbox_original = _medbox_float_cotacao_gerada(
            item.get("preco_medbox_original", item.get("valor_unitario", 0))
        )
        menor_valor = _medbox_float_cotacao_gerada(item.get("menor_valor_comparativo", 0))

        item["preco_osinfo"] = preco_osinfo
        item["menor_lance"] = menor_lance
        item["preco_medbox_original"] = preco_medbox_original
        item["menor_valor_comparativo"] = menor_valor

        item["preco_osinfo_formatado"] = _medbox_moeda_cotacao_gerada(preco_osinfo)
        item["menor_lance_formatado"] = _medbox_moeda_cotacao_gerada(menor_lance)
        item["preco_medbox_original_formatado"] = _medbox_moeda_cotacao_gerada(preco_medbox_original)
        item["menor_valor_comparativo_formatado"] = _medbox_moeda_cotacao_gerada(menor_valor)

        if not item.get("menor_origem"):
            disputa = _medbox_calcular_disputa_cotacao(
                preco_osinfo=preco_osinfo,
                menor_lance=menor_lance,
                preco_medbox=preco_medbox_original,
                empresa_melhor_lance=item.get("empresa_melhor_lance", "")
            )
            item.update(disputa)

    return cotacao


def gerar_cotacao_lances_v2_comparativo():
    _medbox_garantir_colunas_cotacao_gerada()

    dados = request.get_json(silent=True) or {}

    itens = dados.get("itens", [])
    cliente = str(dados.get("cliente") or dados.get("cliente_orgao") or "").strip().upper()
    oas = str(dados.get("oas") or "").strip().upper()
    projeto = str(dados.get("projeto") or "").strip().upper()
    controle_cliente = str(dados.get("controle_cliente") or dados.get("controle") or "").strip().upper()

    if not cliente:
        cliente = "-"

    cliente_exibicao = cliente

    extras = []
    if oas:
        extras.append(f"OAS: {oas}")
    if projeto:
        extras.append(f"PROJETO: {projeto}")
    if controle_cliente:
        extras.append(f"CONTROLE CLIENTE: {controle_cliente}")

    if extras:
        cliente_exibicao = cliente + " | " + " | ".join(extras)

    if not itens:
        return jsonify({"ok": False, "erro": "Nenhum item encontrado para gerar cotação."}), 400

    numero_cotacao = proximo_numero_cotacao()
    data_emissao = datetime.now().strftime("%d/%m/%Y")

    conn = conectar()
    cur = conn.cursor()

    total_geral = 0.0

    cur.execute("""
        INSERT INTO cotacoes_geradas (
            numero_cotacao,
            data_emissao,
            cliente,
            empresa_nome,
            empresa_cnpj,
            empresa_endereco,
            empresa_email,
            empresa_telefone,
            validade_dias,
            total_geral
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        numero_cotacao,
        data_emissao,
        cliente_exibicao,
        EMPRESA_MEDBOX_COTACAO.get("nome"),
        EMPRESA_MEDBOX_COTACAO.get("cnpj"),
        EMPRESA_MEDBOX_COTACAO.get("endereco"),
        EMPRESA_MEDBOX_COTACAO.get("email"),
        EMPRESA_MEDBOX_COTACAO.get("telefone"),
        7,
        0.0,
    ))

    cotacao_id = cur.lastrowid

    for idx, item in enumerate(itens, start=1):
        descricao = str(item.get("descricao_produto") or item.get("descricao") or "").strip().upper()
        sku_master = str(item.get("sku_master") or "").strip().upper()
        marca = str(item.get("marca_fabricante") or item.get("marca") or "").strip().upper()

        quantidade = _medbox_float_cotacao_gerada(item.get("quantidade"), 0.0)
        preco_osinfo = _medbox_float_cotacao_gerada(item.get("preco_osinfo"), 0.0)
        menor_lance = _medbox_float_cotacao_gerada(
            item.get("menor_preco_ofertado", item.get("menor_lance", 0.0)),
            0.0
        )
        preco_medbox = _medbox_float_cotacao_gerada(item.get("preco_medbox"), 0.0)

        empresa_melhor_lance = str(item.get("empresa_melhor_lance") or "").strip().upper()

        disputa = _medbox_calcular_disputa_cotacao(
            preco_osinfo=preco_osinfo,
            menor_lance=menor_lance,
            preco_medbox=preco_medbox,
            empresa_melhor_lance=empresa_melhor_lance
        )

        medbox_vencedora = bool(disputa.get("medbox_vencedora"))

        # Regra aprovada:
        # Só entra valor unitário na proposta se a MedBox for a menor oferta.
        valor_unitario = preco_medbox if medbox_vencedora else 0.0
        valor_total = valor_unitario * quantidade

        total_geral += valor_total

        cur.execute("""
            INSERT INTO cotacoes_geradas_itens (
                cotacao_id,
                item_numero,
                descricao_produto,
                sku_master,
                marca,
                quantidade,
                valor_unitario,
                valor_total,
                venceu_medbox,
                status_lance,
                preco_osinfo,
                menor_lance,
                preco_medbox_original,
                empresa_melhor_lance,
                menor_origem,
                menor_empresa,
                menor_valor_comparativo,
                medbox_vencedora
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            cotacao_id,
            idx,
            descricao,
            sku_master,
            marca,
            quantidade,
            valor_unitario,
            valor_total,
            1 if medbox_vencedora else 0,
            str(item.get("status") or "").strip().upper(),
            preco_osinfo,
            menor_lance,
            preco_medbox,
            empresa_melhor_lance,
            disputa.get("menor_origem"),
            disputa.get("menor_empresa"),
            disputa.get("menor_valor"),
            1 if medbox_vencedora else 0,
        ))

    cur.execute("""
        UPDATE cotacoes_geradas
        SET total_geral = ?
        WHERE id = ?
    """, (total_geral, cotacao_id))

    conn.commit()
    conn.close()

    return jsonify({
        "ok": True,
        "numero_cotacao": numero_cotacao,
        "url": f"/cotacoes/geradas/{numero_cotacao}"
    })


try:
    app.view_functions["gerar_cotacao_lances"] = gerar_cotacao_lances_v2_comparativo
    print("OK: rota gerar_cotacao_lances sobrescrita com comparativo OSINFO x LANCE x MEDBOX.")
except Exception as e:
    print("AVISO: não consegui sobrescrever gerar_cotacao_lances:", e)





# ============================================================
# OVERRIDE FINAL CORRIGIDO - COTAÇÃO GERADA COM COMPARATIVO
# Compatível com retorno: cotacao, itens
# ============================================================

try:
    _carregar_cotacao_gerada_original_tuple = carregar_cotacao_gerada

    def carregar_cotacao_gerada(numero_cotacao):
        _medbox_garantir_colunas_cotacao_gerada()

        resultado = _carregar_cotacao_gerada_original_tuple(numero_cotacao)

        if not resultado:
            return resultado

        # O app original usa: cotacao, itens = carregar_cotacao_gerada(...)
        if isinstance(resultado, tuple):
            cotacao, itens = resultado
        else:
            cotacao = resultado
            itens = resultado.get("itens", []) if isinstance(resultado, dict) else []

        conn = conectar()
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        cur.execute("""
            SELECT i.*
            FROM cotacoes_geradas_itens i
            JOIN cotacoes_geradas c ON c.id = i.cotacao_id
            WHERE c.numero_cotacao = ?
            ORDER BY i.item_numero
        """, (numero_cotacao,))

        itens_db = [dict(row) for row in cur.fetchall()]
        conn.close()

        if itens_db:
            itens = itens_db

        itens_enriquecidos = []

        for item in itens:
            if not isinstance(item, dict):
                try:
                    item = dict(item)
                except Exception:
                    continue

            preco_osinfo = _medbox_float_cotacao_gerada(item.get("preco_osinfo", 0))
            menor_lance = _medbox_float_cotacao_gerada(item.get("menor_lance", 0))
            preco_medbox_original = _medbox_float_cotacao_gerada(
                item.get("preco_medbox_original", item.get("valor_unitario", 0))
            )

            disputa = _medbox_calcular_disputa_cotacao(
                preco_osinfo=preco_osinfo,
                menor_lance=menor_lance,
                preco_medbox=preco_medbox_original,
                empresa_melhor_lance=item.get("empresa_melhor_lance", "")
            )

            item["preco_osinfo"] = preco_osinfo
            item["menor_lance"] = menor_lance
            item["preco_medbox_original"] = preco_medbox_original
            item["menor_origem"] = item.get("menor_origem") or disputa.get("menor_origem")
            item["menor_empresa"] = item.get("menor_empresa") or disputa.get("menor_empresa")
            item["menor_valor_comparativo"] = _medbox_float_cotacao_gerada(
                item.get("menor_valor_comparativo", disputa.get("menor_valor", 0))
            )
            item["medbox_vencedora"] = bool(item.get("medbox_vencedora") or disputa.get("medbox_vencedora"))

            item["preco_osinfo_formatado"] = _medbox_moeda_cotacao_gerada(preco_osinfo)
            item["menor_lance_formatado"] = _medbox_moeda_cotacao_gerada(menor_lance)
            item["preco_medbox_original_formatado"] = _medbox_moeda_cotacao_gerada(preco_medbox_original)
            item["menor_valor_comparativo_formatado"] = _medbox_moeda_cotacao_gerada(item["menor_valor_comparativo"])

            # Garante formatos antigos também.
            item["valor_unitario_formatado"] = _medbox_moeda_cotacao_gerada(item.get("valor_unitario", 0))
            item["valor_total_formatado"] = _medbox_moeda_cotacao_gerada(item.get("valor_total", 0))

            itens_enriquecidos.append(item)

        return cotacao, itens_enriquecidos

    print("OK: carregar_cotacao_gerada corrigido para retorno tuple.")

except Exception as e:
    print("AVISO: não consegui aplicar override corrigido de carregar_cotacao_gerada:", e)





# ============================================================
# OVERRIDE FINAL - TOTAL CONSIDERANDO LANCE VENCEDOR
# Compatível com cotação gerada com ou sem OSINFO
# ============================================================

try:
    _carregar_cotacao_gerada_original_total_vencedor = carregar_cotacao_gerada

    def carregar_cotacao_gerada(numero_cotacao):
        resultado = _carregar_cotacao_gerada_original_total_vencedor(numero_cotacao)

        if not resultado:
            return resultado

        if isinstance(resultado, tuple):
            cotacao, itens = resultado
        else:
            cotacao = resultado
            itens = resultado.get("itens", []) if isinstance(resultado, dict) else []

        itens_corrigidos = []

        for item in itens:
            if not isinstance(item, dict):
                try:
                    item = dict(item)
                except Exception:
                    continue

            quantidade = _medbox_float_cotacao_gerada(item.get("quantidade", 0))
            preco_osinfo = _medbox_float_cotacao_gerada(item.get("preco_osinfo", 0))
            menor_lance = _medbox_float_cotacao_gerada(item.get("menor_lance", 0))
            preco_medbox = _medbox_float_cotacao_gerada(
                item.get("preco_medbox_original", item.get("valor_unitario", 0))
            )

            disputa = _medbox_calcular_disputa_cotacao(
                preco_osinfo=preco_osinfo,
                menor_lance=menor_lance,
                preco_medbox=preco_medbox,
                empresa_melhor_lance=item.get("empresa_melhor_lance", "")
            )

            menor_valor = _medbox_float_cotacao_gerada(
                item.get("menor_valor_comparativo", disputa.get("menor_valor", 0))
            )

            total_vencedor = menor_valor * quantidade

            item["preco_osinfo"] = preco_osinfo
            item["menor_lance"] = menor_lance
            item["preco_medbox_original"] = preco_medbox
            item["menor_origem"] = item.get("menor_origem") or disputa.get("menor_origem")
            item["menor_empresa"] = item.get("menor_empresa") or disputa.get("menor_empresa")
            item["menor_valor_comparativo"] = menor_valor
            item["valor_total_vencedor"] = total_vencedor

            item["preco_osinfo_formatado"] = _medbox_moeda_cotacao_gerada(preco_osinfo)
            item["menor_lance_formatado"] = _medbox_moeda_cotacao_gerada(menor_lance)
            item["preco_medbox_original_formatado"] = _medbox_moeda_cotacao_gerada(preco_medbox)
            item["menor_valor_comparativo_formatado"] = _medbox_moeda_cotacao_gerada(menor_valor)
            item["valor_total_vencedor_formatado"] = _medbox_moeda_cotacao_gerada(total_vencedor)

            item["valor_unitario_formatado"] = _medbox_moeda_cotacao_gerada(item.get("valor_unitario", 0))
            item["valor_total_formatado"] = _medbox_moeda_cotacao_gerada(item.get("valor_total", 0))

            itens_corrigidos.append(item)

        return cotacao, itens_corrigidos

    print("OK: total considerando lance vencedor aplicado.")

except Exception as e:
    print("AVISO: não consegui aplicar total considerando lance vencedor:", e)





# ============================================================
# OVERRIDE DEFINITIVO - GERAÇÃO DE COTAÇÃO OAS / LANCES
# Salva OSINFO, MedBox, Outra Empresa e total pelo menor lance.
# ============================================================

def _oas_float(valor, padrao=0.0):
    try:
        if valor is None:
            return padrao

        if isinstance(valor, (int, float)):
            return float(valor)

        txt = str(valor).strip()
        txt = txt.replace("R$", "").replace("%", "").strip()

        if not txt:
            return padrao

        txt = txt.replace(".", "").replace(",", ".")
        return float(txt)
    except Exception:
        return padrao


def _oas_moeda(valor):
    valor = _oas_float(valor, 0.0)
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _oas_garantir_colunas():
    try:
        garantir_tabelas_cotacoes_geradas()
    except Exception:
        pass

    conn = conectar()
    cur = conn.cursor()

    cur.execute("PRAGMA table_info(cotacoes_geradas_itens)")
    existentes = {row[1] for row in cur.fetchall()}

    colunas = {
        "preco_osinfo": "REAL DEFAULT 0",
        "menor_lance": "REAL DEFAULT 0",
        "preco_medbox_original": "REAL DEFAULT 0",
        "empresa_melhor_lance": "TEXT",
        "menor_origem": "TEXT",
        "menor_empresa": "TEXT",
        "menor_valor_comparativo": "REAL DEFAULT 0",
        "valor_total_vencedor": "REAL DEFAULT 0",
        "medbox_vencedora": "INTEGER DEFAULT 0",
    }

    for nome, tipo in colunas.items():
        if nome not in existentes:
            cur.execute(f"ALTER TABLE cotacoes_geradas_itens ADD COLUMN {nome} {tipo}")

    conn.commit()
    conn.close()


def _oas_disputa(preco_osinfo, preco_medbox, menor_lance, empresa_lance):
    preco_osinfo = _oas_float(preco_osinfo)
    preco_medbox = _oas_float(preco_medbox)
    menor_lance = _oas_float(menor_lance)

    opcoes = []

    if preco_osinfo > 0:
        opcoes.append(("OSINFO", "OSINFO", preco_osinfo))

    if preco_medbox > 0:
        opcoes.append(("MEDBOX", "MEDBOX", preco_medbox))

    if menor_lance > 0:
        opcoes.append(("OUTRA_EMPRESA", empresa_lance or "OUTRA EMPRESA", menor_lance))

    if not opcoes:
        return {
            "menor_origem": "-",
            "menor_empresa": "-",
            "menor_valor": 0.0,
            "medbox_vencedora": False,
        }

    opcoes.sort(key=lambda x: x[2])
    origem, empresa, valor = opcoes[0]

    return {
        "menor_origem": origem,
        "menor_empresa": empresa,
        "menor_valor": valor,
        "medbox_vencedora": origem == "MEDBOX",
    }


def gerar_cotacao_lances_oas_definitiva():
    _oas_garantir_colunas()

    dados = request.get_json(silent=True) or {}
    itens = dados.get("itens", [])

    cliente = str(dados.get("cliente") or dados.get("cliente_orgao") or "").strip().upper()
    oas = str(dados.get("oas") or "").strip().upper()
    projeto = str(dados.get("projeto") or "").strip().upper()
    controle_cliente = str(dados.get("controle_cliente") or "").strip().upper()

    if not cliente:
        cliente = "-"

    cliente_exibicao = cliente
    extras = []

    if oas:
        extras.append(f"OAS: {oas}")
    if projeto:
        extras.append(f"PROJETO: {projeto}")
    if controle_cliente:
        extras.append(f"CONTROLE CLIENTE: {controle_cliente}")

    if extras:
        cliente_exibicao = cliente + " | " + " | ".join(extras)

    if not itens:
        return jsonify({"ok": False, "erro": "Nenhum item encontrado para gerar cotação."}), 400

    numero_cotacao = proximo_numero_cotacao()
    data_emissao = datetime.now().strftime("%d/%m/%Y")

    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO cotacoes_geradas (
            numero_cotacao,
            data_emissao,
            cliente,
            empresa_nome,
            empresa_cnpj,
            empresa_endereco,
            empresa_email,
            empresa_telefone,
            validade_dias,
            total_geral
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        numero_cotacao,
        data_emissao,
        cliente_exibicao,
        EMPRESA_MEDBOX_COTACAO.get("nome"),
        EMPRESA_MEDBOX_COTACAO.get("cnpj"),
        EMPRESA_MEDBOX_COTACAO.get("endereco"),
        EMPRESA_MEDBOX_COTACAO.get("email"),
        EMPRESA_MEDBOX_COTACAO.get("telefone"),
        7,
        0.0,
    ))

    cotacao_id = cur.lastrowid
    total_geral = 0.0

    for idx, item in enumerate(itens, start=1):
        descricao = str(item.get("descricao_produto") or item.get("descricao") or "").strip().upper()
        sku_master = str(item.get("sku_master") or "").strip().upper()
        marca = str(item.get("marca_fabricante") or item.get("marca") or "").strip().upper()

        quantidade = _oas_float(item.get("quantidade"), 0.0)

        preco_osinfo = _oas_float(item.get("preco_osinfo"), 0.0)
        preco_medbox = _oas_float(item.get("preco_medbox"), 0.0)
        menor_lance = _oas_float(item.get("menor_preco_ofertado", item.get("menor_lance", 0.0)), 0.0)

        empresa_lance = str(item.get("empresa_melhor_lance") or "").strip().upper()

        disputa = _oas_disputa(
            preco_osinfo=preco_osinfo,
            preco_medbox=preco_medbox,
            menor_lance=menor_lance,
            empresa_lance=empresa_lance
        )

        menor_valor = disputa["menor_valor"]
        total_vencedor = menor_valor * quantidade

        # Valor da proposta MedBox só entra quando MedBox for vencedora.
        valor_unitario = preco_medbox if disputa["medbox_vencedora"] else 0.0
        valor_total = valor_unitario * quantidade

        total_geral += valor_total

        cur.execute("""
            INSERT INTO cotacoes_geradas_itens (
                cotacao_id,
                item_numero,
                descricao_produto,
                sku_master,
                marca,
                quantidade,
                valor_unitario,
                valor_total,
                venceu_medbox,
                status_lance,
                preco_osinfo,
                menor_lance,
                preco_medbox_original,
                empresa_melhor_lance,
                menor_origem,
                menor_empresa,
                menor_valor_comparativo,
                valor_total_vencedor,
                medbox_vencedora
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            cotacao_id,
            idx,
            descricao,
            sku_master,
            marca,
            quantidade,
            valor_unitario,
            valor_total,
            1 if disputa["medbox_vencedora"] else 0,
            str(item.get("status") or "").strip().upper(),
            preco_osinfo,
            menor_lance,
            preco_medbox,
            empresa_lance,
            disputa["menor_origem"],
            disputa["menor_empresa"],
            menor_valor,
            total_vencedor,
            1 if disputa["medbox_vencedora"] else 0,
        ))

    cur.execute("""
        UPDATE cotacoes_geradas
        SET total_geral = ?
        WHERE id = ?
    """, (total_geral, cotacao_id))

    conn.commit()
    conn.close()

    return jsonify({
        "ok": True,
        "numero_cotacao": numero_cotacao,
        "url": f"/cotacoes/geradas/{numero_cotacao}"
    })


try:
    app.view_functions["gerar_cotacao_lances"] = gerar_cotacao_lances_oas_definitiva
    print("OK: rota gerar_cotacao_lances sobrescrita para OAS definitiva.")
except Exception as e:
    print("AVISO: não consegui sobrescrever rota gerar_cotacao_lances:", e)


# Enriquecimento de itens ao abrir cotação
try:
    _carregar_cotacao_gerada_original_oas_final = carregar_cotacao_gerada

    def carregar_cotacao_gerada(numero_cotacao):
        _oas_garantir_colunas()

        resultado = _carregar_cotacao_gerada_original_oas_final(numero_cotacao)

        if not resultado:
            return resultado

        if isinstance(resultado, tuple):
            cotacao, itens = resultado
        else:
            cotacao = resultado
            itens = resultado.get("itens", []) if isinstance(resultado, dict) else []

        conn = conectar()
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        cur.execute("""
            SELECT i.*
            FROM cotacoes_geradas_itens i
            JOIN cotacoes_geradas c ON c.id = i.cotacao_id
            WHERE c.numero_cotacao = ?
            ORDER BY i.item_numero
        """, (numero_cotacao,))

        itens_db = [dict(row) for row in cur.fetchall()]
        conn.close()

        if itens_db:
            itens = itens_db

        novos = []

        for item in itens:
            if not isinstance(item, dict):
                try:
                    item = dict(item)
                except Exception:
                    continue

            qtd = _oas_float(item.get("quantidade"), 0)
            osinfo = _oas_float(item.get("preco_osinfo"), 0)
            medbox = _oas_float(item.get("preco_medbox_original", item.get("valor_unitario", 0)), 0)
            outra = _oas_float(item.get("menor_lance"), 0)

            disputa = _oas_disputa(osinfo, medbox, outra, item.get("empresa_melhor_lance", ""))

            menor_valor = _oas_float(item.get("menor_valor_comparativo", disputa["menor_valor"]), 0)
            total_vencedor = _oas_float(item.get("valor_total_vencedor", menor_valor * qtd), 0)

            item["preco_osinfo"] = osinfo
            item["preco_medbox_original"] = medbox
            item["menor_lance"] = outra
            item["menor_origem"] = item.get("menor_origem") or disputa["menor_origem"]
            item["menor_empresa"] = item.get("menor_empresa") or disputa["menor_empresa"]
            item["menor_valor_comparativo"] = menor_valor
            item["valor_total_vencedor"] = total_vencedor

            item["preco_osinfo_formatado"] = _oas_moeda(osinfo)
            item["preco_medbox_original_formatado"] = _oas_moeda(medbox)
            item["menor_lance_formatado"] = _oas_moeda(outra)
            item["menor_valor_comparativo_formatado"] = _oas_moeda(menor_valor)
            item["valor_total_vencedor_formatado"] = _oas_moeda(total_vencedor)
            item["valor_unitario_formatado"] = _oas_moeda(item.get("valor_unitario", 0))
            item["valor_total_formatado"] = _oas_moeda(item.get("valor_total", 0))

            novos.append(item)

        return cotacao, novos

    print("OK: carregar_cotacao_gerada enriquecido para OAS definitiva.")

except Exception as e:
    print("AVISO: não consegui enriquecer carregar_cotacao_gerada:", e)





# ============================================================
# OVERRIDE FINAL - REABRIR / EDITAR COTAÇÃO GERADA
# ============================================================

def _edit_float(valor, padrao=0.0):
    try:
        if valor is None:
            return padrao

        if isinstance(valor, (int, float)):
            return float(valor)

        txt = str(valor).strip()
        txt = txt.replace("R$", "").replace("%", "").strip()

        if not txt:
            return padrao

        if "," in txt:
            txt = txt.replace(".", "").replace(",", ".")

        return float(txt)
    except Exception:
        return padrao


def _edit_moeda(valor):
    valor = _edit_float(valor, 0.0)
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _edit_garantir_colunas():
    try:
        garantir_tabelas_cotacoes_geradas()
    except Exception:
        pass

    conn = conectar()
    cur = conn.cursor()

    cur.execute("PRAGMA table_info(cotacoes_geradas_itens)")
    existentes = {row[1] for row in cur.fetchall()}

    colunas = {
        "preco_osinfo": "REAL DEFAULT 0",
        "menor_lance": "REAL DEFAULT 0",
        "preco_medbox_original": "REAL DEFAULT 0",
        "empresa_melhor_lance": "TEXT",
        "menor_origem": "TEXT",
        "menor_empresa": "TEXT",
        "menor_valor_comparativo": "REAL DEFAULT 0",
        "valor_total_vencedor": "REAL DEFAULT 0",
        "medbox_vencedora": "INTEGER DEFAULT 0",
    }

    for coluna, tipo in colunas.items():
        if coluna not in existentes:
            cur.execute(f"ALTER TABLE cotacoes_geradas_itens ADD COLUMN {coluna} {tipo}")

    conn.commit()
    conn.close()


def _edit_calcular_disputa(preco_osinfo, preco_medbox, menor_lance, empresa_lance):
    preco_osinfo = _edit_float(preco_osinfo)
    preco_medbox = _edit_float(preco_medbox)
    menor_lance = _edit_float(menor_lance)

    opcoes = []

    if preco_osinfo > 0:
        opcoes.append(("OSINFO", "OSINFO", preco_osinfo))

    if preco_medbox > 0:
        opcoes.append(("MEDBOX", "MEDBOX", preco_medbox))

    if menor_lance > 0:
        opcoes.append(("OUTRA_EMPRESA", empresa_lance or "OUTRA EMPRESA", menor_lance))

    if not opcoes:
        return "-", "-", 0.0, False

    opcoes.sort(key=lambda x: x[2])
    origem, empresa, valor = opcoes[0]

    return origem, empresa, valor, origem == "MEDBOX"


def _edit_montar_item_lance(row, idx):
    item = dict(row)

    quantidade = _edit_float(item.get("quantidade"), 0)
    preco_osinfo = _edit_float(item.get("preco_osinfo"), 0)
    preco_medbox = _edit_float(item.get("preco_medbox_original", item.get("valor_unitario", 0)), 0)
    menor_lance = _edit_float(item.get("menor_lance"), 0)
    menor_custo = _edit_float(item.get("menor_custo_unitario", 0), 0)

    origem, empresa, menor_valor, medbox_vencedora = _edit_calcular_disputa(
        preco_osinfo,
        preco_medbox,
        menor_lance,
        item.get("empresa_melhor_lance", "")
    )

    return {
        "item": idx,
        "codigo_cliente": "",
        "descricao_produto": item.get("descricao_produto", ""),
        "descricao_cotacao": item.get("descricao_produto", ""),
        "unidade": "",
        "quantidade": quantidade,
        "sku_master": item.get("sku_master", ""),
        "sku_encontrado": bool(item.get("sku_master")),
        "score": 0,
        "sugestoes_sku": [],
        "categoria": item.get("categoria", ""),
        "descricao_fornecedor": "",
        "preco_osinfo": preco_osinfo,
        "ultima_compra": 0,
        "preco_medbox": preco_medbox,
        "markup_atual": 80,
        "menor_preco_ofertado": menor_lance,
        "empresa_melhor_lance": item.get("empresa_melhor_lance", ""),
        "menor_valor": menor_valor,
        "menor_valor_nome": empresa,
        "menor_origem": origem,
        "menor_custo_unitario": menor_custo if menor_custo else None,
        "fornecedor_menor_custo": item.get("fornecedor_menor_custo", ""),
        "marca_fabricante": item.get("marca", ""),
        "status": item.get("status_lance") or ("MEDBOX VENCE" if medbox_vencedora else "NEGOCIAR" if origem in ["OSINFO", "OUTRA_EMPRESA"] else "REVISAR SKU"),
        "tem_preco": bool(preco_medbox),
        "preco_osinfo_formatado": _edit_moeda(preco_osinfo),
        "ultima_compra_formatada": _edit_moeda(0),
        "preco_medbox_formatado": _edit_moeda(preco_medbox),
        "menor_preco_ofertado_formatado": _edit_moeda(menor_lance),
        "menor_valor_formatado": _edit_moeda(menor_valor),
        "menor_custo_unitario_formatado": _edit_moeda(menor_custo) if menor_custo else "-",
        "total_medbox": preco_medbox * quantidade,
        "total_osinfo": preco_osinfo * quantidade,
        "total_ultima_compra": 0,
        "total_menor_valor": menor_valor * quantidade,
    }


@app.route("/cotacoes/geradas/<numero_cotacao>/editar")
def editar_cotacao_gerada(numero_cotacao):
    _edit_garantir_colunas()

    conn = conectar()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM cotacoes_geradas
        WHERE numero_cotacao = ?
    """, (numero_cotacao,))

    cotacao = cur.fetchone()

    if not cotacao:
        conn.close()
        return f"Cotação {numero_cotacao} não encontrada.", 404

    cur.execute("""
        SELECT *
        FROM cotacoes_geradas_itens
        WHERE cotacao_id = ?
        ORDER BY item_numero
    """, (cotacao["id"],))

    itens_db = cur.fetchall()
    conn.close()

    itens = [
        _edit_montar_item_lance(row, idx)
        for idx, row in enumerate(itens_db, start=1)
    ]

    analise = {
        "arquivo": f"EDITANDO {numero_cotacao}",
        "itens_extraidos": len(itens),
        "markup_percentual": 80,
        "itens": itens,
        "resumo": montar_resumo_lances(itens) if "montar_resumo_lances" in globals() else {
            "total_itens": len(itens),
            "itens_com_sku": 0,
            "itens_revisar_sku": 0,
            "itens_com_preco_medbox": 0,
            "itens_sem_preco": 0,
            "itens_competitivos": 0,
            "itens_ganhos_medbox": 0,
            "percentual_itens_ganhos": 0,
            "percentual_itens_ganhos_formatado": "0,00%",
            "itens_negociar": 0,
            "total_medbox": 0,
            "total_medbox_formatado": "R$ 0,00",
            "total_ganho_medbox": 0,
            "total_ganho_medbox_formatado": "R$ 0,00",
        }
    }

    return render_template(
        "cotacao_lances.html",
        data_atual=DATA_ATUAL,
        resumo=resumo_dashboard(),
        analise=analise,
        erro=None,
        arquivo_nome=f"EDITANDO {numero_cotacao}",
        markup_percentual=80,
        numero_cotacao_editando=numero_cotacao,
        modo_edicao_cotacao=True,
    )


@app.route("/cotacoes/lances/atualizar-cotacao/<numero_cotacao>", methods=["POST"])
def atualizar_cotacao_gerada(numero_cotacao):
    _edit_garantir_colunas()

    dados = request.get_json(silent=True) or {}
    itens = dados.get("itens", [])

    cliente = str(dados.get("cliente") or dados.get("cliente_orgao") or "").strip().upper()
    oas = str(dados.get("oas") or "").strip().upper()
    projeto = str(dados.get("projeto") or "").strip().upper()
    controle_cliente = str(dados.get("controle_cliente") or "").strip().upper()

    extras = []
    if oas:
        extras.append(f"OAS: {oas}")
    if projeto:
        extras.append(f"PROJETO: {projeto}")
    if controle_cliente:
        extras.append(f"CONTROLE CLIENTE: {controle_cliente}")

    cliente_exibicao = cliente or "-"
    if extras:
        cliente_exibicao = cliente_exibicao + " | " + " | ".join(extras)

    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
        SELECT id
        FROM cotacoes_geradas
        WHERE numero_cotacao = ?
    """, (numero_cotacao,))

    row = cur.fetchone()

    if not row:
        conn.close()
        return jsonify({"ok": False, "erro": f"Cotação {numero_cotacao} não encontrada."}), 404

    cotacao_id = row[0]

    cur.execute("DELETE FROM cotacoes_geradas_itens WHERE cotacao_id = ?", (cotacao_id,))

    total_geral = 0.0

    for idx, item in enumerate(itens, start=1):
        descricao = str(item.get("descricao_produto") or item.get("descricao") or "").strip().upper()
        sku_master = str(item.get("sku_master") or "").strip().upper()
        marca = str(item.get("marca_fabricante") or item.get("marca") or "").strip().upper()
        quantidade = _edit_float(item.get("quantidade"), 0)

        preco_osinfo = _edit_float(item.get("preco_osinfo"), 0)
        preco_medbox = _edit_float(item.get("preco_medbox"), 0)
        menor_lance = _edit_float(item.get("menor_preco_ofertado", item.get("menor_lance", 0)), 0)
        empresa_lance = str(item.get("empresa_melhor_lance") or "").strip().upper()

        menor_origem, menor_empresa, menor_valor, medbox_vencedora = _edit_calcular_disputa(
            preco_osinfo,
            preco_medbox,
            menor_lance,
            empresa_lance
        )

        valor_unitario = preco_medbox if medbox_vencedora else 0.0
        valor_total = valor_unitario * quantidade
        valor_total_vencedor = menor_valor * quantidade

        total_geral += valor_total

        cur.execute("""
            INSERT INTO cotacoes_geradas_itens (
                cotacao_id,
                item_numero,
                descricao_produto,
                sku_master,
                marca,
                quantidade,
                valor_unitario,
                valor_total,
                venceu_medbox,
                status_lance,
                preco_osinfo,
                menor_lance,
                preco_medbox_original,
                empresa_melhor_lance,
                menor_origem,
                menor_empresa,
                menor_valor_comparativo,
                valor_total_vencedor,
                medbox_vencedora
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            cotacao_id,
            idx,
            descricao,
            sku_master,
            marca,
            quantidade,
            valor_unitario,
            valor_total,
            1 if medbox_vencedora else 0,
            str(item.get("status") or "").strip().upper(),
            preco_osinfo,
            menor_lance,
            preco_medbox,
            empresa_lance,
            menor_origem,
            menor_empresa,
            menor_valor,
            valor_total_vencedor,
            1 if medbox_vencedora else 0,
        ))

    cur.execute("""
        UPDATE cotacoes_geradas
        SET cliente = ?,
            total_geral = ?
        WHERE id = ?
    """, (cliente_exibicao, total_geral, cotacao_id))

    conn.commit()
    conn.close()

    return jsonify({
        "ok": True,
        "numero_cotacao": numero_cotacao,
        "url": f"/cotacoes/geradas/{numero_cotacao}"
    })





# ============================================================
# OVERRIDE FINAL - MODELO OAS NA COTAÇÃO GERADA
# Regra:
# - Se houver preço OSINFO em qualquer item, usa modelo OAS.
# - Mostra OSINFO, MedBox, Outra Empresa.
# - Destaca o menor preço.
# - Total do item = quantidade x menor preço.
# ============================================================

def _oas_final_float(valor, padrao=0.0):
    try:
        if valor is None:
            return padrao

        if isinstance(valor, (int, float)):
            return float(valor)

        texto = str(valor).strip()
        texto = texto.replace("R$", "").replace("%", "").strip()

        if not texto:
            return padrao

        texto = texto.replace(" ", "")

        # Formato BR: 1.234,56
        if "," in texto:
            texto = texto.replace(".", "").replace(",", ".")

        return float(texto)
    except Exception:
        return padrao


def _oas_final_moeda(valor):
    valor = _oas_final_float(valor, 0.0)
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _oas_final_garantir_colunas():
    try:
        garantir_tabelas_cotacoes_geradas()
    except Exception:
        pass

    conn = conectar()
    cur = conn.cursor()

    cur.execute("PRAGMA table_info(cotacoes_geradas_itens)")
    existentes = {row[1] for row in cur.fetchall()}

    colunas = {
        "preco_osinfo": "REAL DEFAULT 0",
        "menor_lance": "REAL DEFAULT 0",
        "preco_medbox_original": "REAL DEFAULT 0",
        "empresa_melhor_lance": "TEXT",
        "menor_origem": "TEXT",
        "menor_empresa": "TEXT",
        "menor_valor_comparativo": "REAL DEFAULT 0",
        "valor_total_vencedor": "REAL DEFAULT 0",
        "medbox_vencedora": "INTEGER DEFAULT 0",
    }

    for coluna, tipo in colunas.items():
        if coluna not in existentes:
            cur.execute(f"ALTER TABLE cotacoes_geradas_itens ADD COLUMN {coluna} {tipo}")

    conn.commit()
    conn.close()


def _oas_final_calcular_menor(preco_osinfo, preco_medbox, preco_outra_empresa, empresa_outra):
    opcoes = []

    preco_osinfo = _oas_final_float(preco_osinfo, 0.0)
    preco_medbox = _oas_final_float(preco_medbox, 0.0)
    preco_outra_empresa = _oas_final_float(preco_outra_empresa, 0.0)

    if preco_osinfo > 0:
        opcoes.append(("OSINFO", "OSINFO", preco_osinfo))

    if preco_medbox > 0:
        opcoes.append(("MEDBOX", "MEDBOX", preco_medbox))

    if preco_outra_empresa > 0:
        opcoes.append(("OUTRA_EMPRESA", empresa_outra or "OUTRA EMPRESA", preco_outra_empresa))

    if not opcoes:
        return "-", "-", 0.0

    opcoes.sort(key=lambda x: x[2])
    return opcoes[0]


try:
    _carregar_cotacao_gerada_original_oas_modelo_final = carregar_cotacao_gerada

    def carregar_cotacao_gerada(numero_cotacao):
        _oas_final_garantir_colunas()

        resultado = _carregar_cotacao_gerada_original_oas_modelo_final(numero_cotacao)

        if not resultado:
            return resultado

        if isinstance(resultado, tuple):
            cotacao, itens = resultado
        else:
            cotacao = resultado
            itens = resultado.get("itens", []) if isinstance(resultado, dict) else []

        conn = conectar()
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        cur.execute("""
            SELECT i.*
            FROM cotacoes_geradas_itens i
            JOIN cotacoes_geradas c ON c.id = i.cotacao_id
            WHERE c.numero_cotacao = ?
            ORDER BY i.item_numero
        """, (numero_cotacao,))

        itens_db = [dict(row) for row in cur.fetchall()]
        conn.close()

        if itens_db:
            itens = itens_db

        itens_corrigidos = []
        tem_osinfo = False

        for item in itens:
            if not isinstance(item, dict):
                try:
                    item = dict(item)
                except Exception:
                    continue

            quantidade = _oas_final_float(item.get("quantidade"), 0.0)

            preco_osinfo = _oas_final_float(item.get("preco_osinfo"), 0.0)
            preco_medbox = _oas_final_float(
                item.get("preco_medbox_original", item.get("valor_unitario", 0.0)),
                0.0
            )
            preco_outra_empresa = _oas_final_float(item.get("menor_lance"), 0.0)
            empresa_outra = str(item.get("empresa_melhor_lance") or "").strip().upper()

            if preco_osinfo > 0:
                tem_osinfo = True

            menor_origem, menor_empresa, menor_valor = _oas_final_calcular_menor(
                preco_osinfo,
                preco_medbox,
                preco_outra_empresa,
                empresa_outra
            )

            valor_total_vencedor = quantidade * menor_valor

            item["preco_osinfo"] = preco_osinfo
            item["preco_medbox_original"] = preco_medbox
            item["preco_outra_empresa"] = preco_outra_empresa
            item["menor_lance"] = preco_outra_empresa
            item["empresa_melhor_lance"] = empresa_outra

            item["menor_origem"] = menor_origem
            item["menor_empresa"] = menor_empresa
            item["menor_valor_comparativo"] = menor_valor
            item["valor_total_vencedor"] = valor_total_vencedor

            item["destaque_osinfo"] = menor_origem == "OSINFO"
            item["destaque_medbox"] = menor_origem == "MEDBOX"
            item["destaque_outra"] = menor_origem == "OUTRA_EMPRESA"

            item["preco_osinfo_formatado"] = _oas_final_moeda(preco_osinfo)
            item["preco_medbox_formatado"] = _oas_final_moeda(preco_medbox)
            item["preco_medbox_original_formatado"] = _oas_final_moeda(preco_medbox)
            item["preco_outra_empresa_formatado"] = _oas_final_moeda(preco_outra_empresa)
            item["menor_lance_formatado"] = _oas_final_moeda(preco_outra_empresa)
            item["menor_valor_comparativo_formatado"] = _oas_final_moeda(menor_valor)
            item["valor_total_vencedor_formatado"] = _oas_final_moeda(valor_total_vencedor)

            item["valor_unitario_formatado"] = _oas_final_moeda(item.get("valor_unitario", 0.0))
            item["valor_total_formatado"] = _oas_final_moeda(item.get("valor_total", 0.0))

            itens_corrigidos.append(item)

        # Compatível com dict e sqlite Row convertido.
        try:
            cotacao = dict(cotacao)
        except Exception:
            pass

        try:
            cotacao["tem_osinfo"] = tem_osinfo
        except Exception:
            pass

        return cotacao, itens_corrigidos

    print("OK: carregar_cotacao_gerada aplicado com modelo OAS final.")

except Exception as e:
    print("AVISO: não consegui aplicar modelo OAS final:", e)





# ============================================================
# OVERRIDE DEFINITIVO - ATUALIZAR COTAÇÃO OAS EXISTENTE
# Corrige:
# - Quantidade multiplicando por 100
# - OSINFO salvando 0
# - Lance outra empresa salvando 0
# - Empresa melhor lance vazia
# ============================================================

def _upd_oas_float(valor, padrao=0.0):
    try:
        if valor is None:
            return padrao

        if isinstance(valor, (int, float)):
            return float(valor)

        txt = str(valor).strip()
        txt = txt.replace("R$", "").replace("%", "").strip()
        txt = txt.replace(" ", "")

        if not txt:
            return padrao

        # Formato BR: 1.234,56 ou 2,10
        if "," in txt:
            txt = txt.replace(".", "").replace(",", ".")
            return float(txt)

        # Formato decimal normal: 9000.0 ou 2.41
        return float(txt)
    except Exception:
        return padrao


def _upd_oas_garantir_colunas():
    try:
        garantir_tabelas_cotacoes_geradas()
    except Exception:
        pass

    conn = conectar()
    cur = conn.cursor()

    cur.execute("PRAGMA table_info(cotacoes_geradas_itens)")
    existentes = {row[1] for row in cur.fetchall()}

    colunas = {
        "preco_osinfo": "REAL DEFAULT 0",
        "menor_lance": "REAL DEFAULT 0",
        "preco_medbox_original": "REAL DEFAULT 0",
        "empresa_melhor_lance": "TEXT",
        "menor_origem": "TEXT",
        "menor_empresa": "TEXT",
        "menor_valor_comparativo": "REAL DEFAULT 0",
        "valor_total_vencedor": "REAL DEFAULT 0",
        "medbox_vencedora": "INTEGER DEFAULT 0",
    }

    for coluna, tipo in colunas.items():
        if coluna not in existentes:
            cur.execute(f"ALTER TABLE cotacoes_geradas_itens ADD COLUMN {coluna} {tipo}")

    conn.commit()
    conn.close()


def _upd_oas_disputa(preco_osinfo, preco_medbox, menor_lance, empresa_lance):
    opcoes = []

    if preco_osinfo > 0:
        opcoes.append(("OSINFO", "OSINFO", preco_osinfo))

    if preco_medbox > 0:
        opcoes.append(("MEDBOX", "MEDBOX", preco_medbox))

    if menor_lance > 0:
        opcoes.append(("OUTRA_EMPRESA", empresa_lance or "OUTRA EMPRESA", menor_lance))

    if not opcoes:
        return "-", "-", 0.0, False

    opcoes.sort(key=lambda x: x[2])
    origem, empresa, valor = opcoes[0]

    return origem, empresa, valor, origem == "MEDBOX"


def atualizar_cotacao_gerada_oas_final(numero_cotacao):
    _upd_oas_garantir_colunas()

    dados = request.get_json(silent=True) or {}
    itens = dados.get("itens", [])

    if not itens:
        return jsonify({"ok": False, "erro": "Nenhum item recebido para atualizar."}), 400

    cliente = str(dados.get("cliente") or dados.get("cliente_orgao") or "").strip().upper()
    oas = str(dados.get("oas") or "").strip().upper()
    projeto = str(dados.get("projeto") or "").strip().upper()
    controle_cliente = str(dados.get("controle_cliente") or "").strip().upper()

    extras = []
    if oas:
        extras.append(f"OAS: {oas}")
    if projeto:
        extras.append(f"PROJETO: {projeto}")
    if controle_cliente:
        extras.append(f"CONTROLE CLIENTE: {controle_cliente}")

    cliente_exibicao = cliente or "-"
    if extras:
        cliente_exibicao = cliente_exibicao + " | " + " | ".join(extras)

    conn = conectar()
    cur = conn.cursor()

    cur.execute("SELECT id FROM cotacoes_geradas WHERE numero_cotacao = ?", (numero_cotacao,))
    row = cur.fetchone()

    if not row:
        conn.close()
        return jsonify({"ok": False, "erro": f"Cotação {numero_cotacao} não encontrada."}), 404

    cotacao_id = row[0]

    cur.execute("DELETE FROM cotacoes_geradas_itens WHERE cotacao_id = ?", (cotacao_id,))

    total_medbox = 0.0

    for idx, item in enumerate(itens, start=1):
        descricao = str(item.get("descricao_produto") or item.get("descricao") or "").strip().upper()
        sku_master = str(item.get("sku_master") or "").strip().upper()
        marca = str(item.get("marca_fabricante") or item.get("marca") or "").strip().upper()

        quantidade = _upd_oas_float(item.get("quantidade"), 0.0)
        preco_osinfo = _upd_oas_float(item.get("preco_osinfo"), 0.0)
        preco_medbox = _upd_oas_float(item.get("preco_medbox"), 0.0)
        menor_lance = _upd_oas_float(item.get("menor_preco_ofertado", item.get("menor_lance", 0.0)), 0.0)
        empresa_lance = str(item.get("empresa_melhor_lance") or "").strip().upper()

        menor_origem, menor_empresa, menor_valor, medbox_vencedora = _upd_oas_disputa(
            preco_osinfo,
            preco_medbox,
            menor_lance,
            empresa_lance
        )

        valor_total_vencedor = quantidade * menor_valor

        # Proposta MedBox só contabiliza no total MedBox se for vencedora.
        valor_unitario = preco_medbox if medbox_vencedora else 0.0
        valor_total = quantidade * valor_unitario

        total_medbox += valor_total

        cur.execute("""
            INSERT INTO cotacoes_geradas_itens (
                cotacao_id,
                item_numero,
                descricao_produto,
                sku_master,
                marca,
                quantidade,
                valor_unitario,
                valor_total,
                venceu_medbox,
                status_lance,
                preco_osinfo,
                menor_lance,
                preco_medbox_original,
                empresa_melhor_lance,
                menor_origem,
                menor_empresa,
                menor_valor_comparativo,
                valor_total_vencedor,
                medbox_vencedora
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            cotacao_id,
            idx,
            descricao,
            sku_master,
            marca,
            quantidade,
            valor_unitario,
            valor_total,
            1 if medbox_vencedora else 0,
            str(item.get("status") or "").strip().upper(),
            preco_osinfo,
            menor_lance,
            preco_medbox,
            empresa_lance,
            menor_origem,
            menor_empresa,
            menor_valor,
            valor_total_vencedor,
            1 if medbox_vencedora else 0,
        ))

    cur.execute("""
        UPDATE cotacoes_geradas
        SET cliente = ?,
            total_geral = ?
        WHERE id = ?
    """, (cliente_exibicao, total_medbox, cotacao_id))

    conn.commit()
    conn.close()

    return jsonify({
        "ok": True,
        "numero_cotacao": numero_cotacao,
        "url": f"/cotacoes/geradas/{numero_cotacao}"
    })


try:
    app.view_functions["atualizar_cotacao_gerada"] = atualizar_cotacao_gerada_oas_final
    print("OK: rota atualizar_cotacao_gerada substituída pela versão OAS final.")
except Exception as e:
    print("AVISO: não consegui substituir atualizar_cotacao_gerada:", e)





# ============================================================
# OVERRIDE FINAL - CORRIGE QUANTIDADE E REABERTURA DA COTAÇÃO
# ============================================================

def _qtd_corrigir_quantidade(valor):
    """
    Corrige quantidades que foram gravadas erradas multiplicadas por 10.000.
    Exemplo:
    900000 -> 90
    10000000 -> 1000
    60000000 -> 6000

    Regra de segurança:
    Só divide por 10.000 quando o número é muito alto e múltiplo claro.
    """
    try:
        qtd = float(valor or 0)
    except Exception:
        return 0.0

    if qtd >= 100000 and qtd % 10000 == 0:
        return qtd / 10000

    return qtd


def _qtd_float(valor, padrao=0.0):
    try:
        if valor is None:
            return padrao

        if isinstance(valor, (int, float)):
            return float(valor)

        txt = str(valor).strip()
        txt = txt.replace("R$", "").replace("%", "").strip()
        txt = txt.replace(" ", "")

        if not txt:
            return padrao

        if "," in txt:
            txt = txt.replace(".", "").replace(",", ".")

        return float(txt)
    except Exception:
        return padrao


def _qtd_moeda(valor):
    valor = _qtd_float(valor, 0.0)
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _qtd_disputa(preco_osinfo, preco_medbox, menor_lance, empresa_lance):
    preco_osinfo = _qtd_float(preco_osinfo, 0)
    preco_medbox = _qtd_float(preco_medbox, 0)
    menor_lance = _qtd_float(menor_lance, 0)

    opcoes = []

    if preco_osinfo > 0:
        opcoes.append(("OSINFO", "OSINFO", preco_osinfo))

    if preco_medbox > 0:
        opcoes.append(("MEDBOX", "MEDBOX", preco_medbox))

    if menor_lance > 0:
        opcoes.append(("OUTRA_EMPRESA", empresa_lance or "OUTRA EMPRESA", menor_lance))

    if not opcoes:
        return "-", "-", 0.0, False

    opcoes.sort(key=lambda x: x[2])
    origem, empresa, valor = opcoes[0]

    return origem, empresa, valor, origem == "MEDBOX"


def _qtd_garantir_colunas():
    try:
        garantir_tabelas_cotacoes_geradas()
    except Exception:
        pass

    conn = conectar()
    cur = conn.cursor()

    cur.execute("PRAGMA table_info(cotacoes_geradas_itens)")
    existentes = {row[1] for row in cur.fetchall()}

    colunas = {
        "preco_osinfo": "REAL DEFAULT 0",
        "menor_lance": "REAL DEFAULT 0",
        "preco_medbox_original": "REAL DEFAULT 0",
        "empresa_melhor_lance": "TEXT",
        "menor_origem": "TEXT",
        "menor_empresa": "TEXT",
        "menor_valor_comparativo": "REAL DEFAULT 0",
        "valor_total_vencedor": "REAL DEFAULT 0",
        "medbox_vencedora": "INTEGER DEFAULT 0",
    }

    for coluna, tipo in colunas.items():
        if coluna not in existentes:
            cur.execute(f"ALTER TABLE cotacoes_geradas_itens ADD COLUMN {coluna} {tipo}")

    conn.commit()
    conn.close()


# Reabre a cotação corrigindo quantidades exageradas e mantendo preços salvos.
def _qtd_montar_item_lance_edicao(row, idx):
    item = dict(row)

    quantidade = _qtd_corrigir_quantidade(item.get("quantidade", 0))

    preco_osinfo = _qtd_float(item.get("preco_osinfo"), 0)
    preco_medbox = _qtd_float(item.get("preco_medbox_original", item.get("valor_unitario", 0)), 0)
    menor_lance = _qtd_float(item.get("menor_lance"), 0)
    empresa_lance = str(item.get("empresa_melhor_lance") or "").strip().upper()

    menor_origem, menor_empresa, menor_valor, medbox_vencedora = _qtd_disputa(
        preco_osinfo,
        preco_medbox,
        menor_lance,
        empresa_lance
    )

    return {
        "item": idx,
        "codigo_cliente": "",
        "descricao_produto": item.get("descricao_produto", ""),
        "descricao_cotacao": item.get("descricao_produto", ""),
        "unidade": "",
        "quantidade": quantidade,
        "sku_master": item.get("sku_master", ""),
        "sku_encontrado": bool(item.get("sku_master")),
        "score": 0,
        "sugestoes_sku": [],
        "categoria": item.get("categoria", ""),
        "descricao_fornecedor": "",
        "preco_osinfo": preco_osinfo,
        "ultima_compra": 0,
        "preco_medbox": preco_medbox,
        "markup_atual": 80,
        "menor_preco_ofertado": menor_lance,
        "empresa_melhor_lance": empresa_lance,
        "menor_valor": menor_valor,
        "menor_valor_nome": menor_empresa,
        "menor_origem": menor_origem,
        "menor_custo_unitario": None,
        "fornecedor_menor_custo": item.get("fornecedor_menor_custo", ""),
        "marca_fabricante": item.get("marca", ""),
        "status": item.get("status_lance") or ("MEDBOX VENCE" if medbox_vencedora else "NEGOCIAR" if menor_origem in ["OSINFO", "OUTRA_EMPRESA"] else "SEM PREÇO"),
        "tem_preco": bool(preco_medbox),
        "preco_osinfo_formatado": _qtd_moeda(preco_osinfo),
        "ultima_compra_formatada": _qtd_moeda(0),
        "preco_medbox_formatado": _qtd_moeda(preco_medbox),
        "menor_preco_ofertado_formatado": _qtd_moeda(menor_lance),
        "menor_valor_formatado": _qtd_moeda(menor_valor),
        "menor_custo_unitario_formatado": "-",
        "total_medbox": preco_medbox * quantidade,
        "total_osinfo": preco_osinfo * quantidade,
        "total_ultima_compra": 0,
        "total_menor_valor": menor_valor * quantidade,
    }


def editar_cotacao_gerada_corrigida(numero_cotacao):
    _qtd_garantir_colunas()

    conn = conectar()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("SELECT * FROM cotacoes_geradas WHERE numero_cotacao = ?", (numero_cotacao,))
    cotacao = cur.fetchone()

    if not cotacao:
        conn.close()
        return f"Cotação {numero_cotacao} não encontrada.", 404

    cur.execute("""
        SELECT *
        FROM cotacoes_geradas_itens
        WHERE cotacao_id = ?
        ORDER BY item_numero
    """, (cotacao["id"],))

    itens_db = cur.fetchall()
    conn.close()

    itens = [
        _qtd_montar_item_lance_edicao(row, idx)
        for idx, row in enumerate(itens_db, start=1)
    ]

    try:
        resumo_lances = montar_resumo_lances(itens)
    except Exception:
        resumo_lances = {
            "total_itens": len(itens),
            "itens_com_sku": 0,
            "itens_revisar_sku": 0,
            "itens_com_preco_medbox": 0,
            "itens_sem_preco": 0,
            "itens_competitivos": 0,
            "itens_ganhos_medbox": 0,
            "percentual_itens_ganhos": 0,
            "percentual_itens_ganhos_formatado": "0,00%",
            "itens_negociar": 0,
            "total_medbox": 0,
            "total_medbox_formatado": "R$ 0,00",
            "total_ganho_medbox": 0,
            "total_ganho_medbox_formatado": "R$ 0,00",
        }

    analise = {
        "arquivo": f"EDITANDO {numero_cotacao}",
        "itens_extraidos": len(itens),
        "markup_percentual": 80,
        "itens": itens,
        "resumo": resumo_lances,
    }

    return render_template(
        "cotacao_lances.html",
        data_atual=DATA_ATUAL,
        resumo=resumo_dashboard(),
        analise=analise,
        erro=None,
        arquivo_nome=f"EDITANDO {numero_cotacao}",
        markup_percentual=80,
        numero_cotacao_editando=numero_cotacao,
        modo_edicao_cotacao=True,
    )


def atualizar_cotacao_gerada_corrigida(numero_cotacao):
    _qtd_garantir_colunas()

    dados = request.get_json(silent=True) or {}
    itens = dados.get("itens", [])

    if not itens:
        return jsonify({"ok": False, "erro": "Nenhum item recebido para atualizar."}), 400

    cliente = str(dados.get("cliente") or dados.get("cliente_orgao") or "").strip().upper()
    cliente_exibicao = cliente or "-"

    conn = conectar()
    cur = conn.cursor()

    cur.execute("SELECT id FROM cotacoes_geradas WHERE numero_cotacao = ?", (numero_cotacao,))
    row = cur.fetchone()

    if not row:
        conn.close()
        return jsonify({"ok": False, "erro": f"Cotação {numero_cotacao} não encontrada."}), 404

    cotacao_id = row[0]

    cur.execute("DELETE FROM cotacoes_geradas_itens WHERE cotacao_id = ?", (cotacao_id,))

    total_medbox = 0.0

    for idx, item in enumerate(itens, start=1):
        descricao = str(item.get("descricao_produto") or item.get("descricao") or "").strip().upper()
        sku_master = str(item.get("sku_master") or "").strip().upper()
        marca = str(item.get("marca_fabricante") or item.get("marca") or "").strip().upper()

        # Aqui NÃO multiplicamos. Apenas lemos o número recebido.
        quantidade = _qtd_float(item.get("quantidade"), 0)
        preco_osinfo = _qtd_float(item.get("preco_osinfo"), 0)
        preco_medbox = _qtd_float(item.get("preco_medbox"), 0)
        menor_lance = _qtd_float(item.get("menor_preco_ofertado", item.get("menor_lance", 0)), 0)
        empresa_lance = str(item.get("empresa_melhor_lance") or "").strip().upper()

        menor_origem, menor_empresa, menor_valor, medbox_vencedora = _qtd_disputa(
            preco_osinfo,
            preco_medbox,
            menor_lance,
            empresa_lance
        )

        valor_total_vencedor = quantidade * menor_valor
        valor_unitario = preco_medbox if medbox_vencedora else 0.0
        valor_total = quantidade * valor_unitario

        total_medbox += valor_total

        cur.execute("""
            INSERT INTO cotacoes_geradas_itens (
                cotacao_id,
                item_numero,
                descricao_produto,
                sku_master,
                marca,
                quantidade,
                valor_unitario,
                valor_total,
                venceu_medbox,
                status_lance,
                preco_osinfo,
                menor_lance,
                preco_medbox_original,
                empresa_melhor_lance,
                menor_origem,
                menor_empresa,
                menor_valor_comparativo,
                valor_total_vencedor,
                medbox_vencedora
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            cotacao_id,
            idx,
            descricao,
            sku_master,
            marca,
            quantidade,
            valor_unitario,
            valor_total,
            1 if medbox_vencedora else 0,
            str(item.get("status") or "").strip().upper(),
            preco_osinfo,
            menor_lance,
            preco_medbox,
            empresa_lance,
            menor_origem,
            menor_empresa,
            menor_valor,
            valor_total_vencedor,
            1 if medbox_vencedora else 0,
        ))

    cur.execute("""
        UPDATE cotacoes_geradas
        SET cliente = ?,
            total_geral = ?
        WHERE id = ?
    """, (cliente_exibicao, total_medbox, cotacao_id))

    conn.commit()
    conn.close()

    return jsonify({
        "ok": True,
        "numero_cotacao": numero_cotacao,
        "url": f"/cotacoes/geradas/{numero_cotacao}"
    })


try:
    app.view_functions["editar_cotacao_gerada"] = editar_cotacao_gerada_corrigida
    print("OK: rota editar_cotacao_gerada corrigida.")
except Exception as e:
    print("AVISO editar:", e)

try:
    app.view_functions["atualizar_cotacao_gerada"] = atualizar_cotacao_gerada_corrigida
    print("OK: rota atualizar_cotacao_gerada corrigida.")
except Exception as e:
    print("AVISO atualizar:", e)





# ============================================================
# OVERRIDE FINAL - NORMALIZAR QUANTIDADE DE COTAÇÃO REABERTA
# Corrige cotações salvas com quantidade x10 e remove .0 visual.
# ============================================================

def _normalizar_qtd_reaberta(valor):
    try:
        qtd = float(valor or 0)
    except Exception:
        return 0.0

    # Correção de bug anterior:
    # 900 -> 90
    # 10000 -> 1000
    # 20000 -> 2000
    # 60000 -> 6000
    #
    # Só aplica em números inteiros múltiplos de 10.
    if qtd >= 100 and qtd % 10 == 0:
        return qtd / 10

    return qtd


def _formatar_qtd_visual(valor):
    try:
        qtd = float(valor or 0)
    except Exception:
        return valor

    if qtd.is_integer():
        return str(int(qtd))

    return str(qtd).replace(".", ",")


try:
    _editar_cotacao_gerada_original_qtd_final = editar_cotacao_gerada

    def editar_cotacao_gerada(numero_cotacao):
        resposta = _editar_cotacao_gerada_original_qtd_final(numero_cotacao)
        return resposta

    print("OK: hook de edição preservado.")

except Exception as e:
    print("AVISO hook edição:", e)





# ============================================================
# MEDBOX - FIX DEFINITIVO PERSISTÊNCIA LANCES / SKU / MARKUP
# Mantém rota existente e substitui endpoint com cálculo autoritativo.
# ============================================================

def _fix_lance_float(valor, padrao=0.0):
    try:
        if valor is None:
            return padrao

        if isinstance(valor, (int, float)):
            return float(valor)

        txt = str(valor).strip()
        txt = txt.replace("R$", "").replace("%", "").strip()
        txt = "".join(ch for ch in txt if ch.isdigit() or ch in ",.-")

        if not txt:
            return padrao

        if "," in txt:
            txt = txt.replace(".", "").replace(",", ".")

        return float(txt)
    except Exception:
        return padrao


def _fix_lance_moeda(valor):
    valor = _fix_lance_float(valor, 0)
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _fix_lance_garantir_colunas():
    conn = conectar()
    cur = conn.cursor()

    try:
        garantir_tabelas_cotacoes_geradas()
    except Exception:
        pass

    cur.execute("PRAGMA table_info(cotacoes_geradas_itens)")
    existentes = {row[1] for row in cur.fetchall()}

    colunas = {
        "categoria": "TEXT",
        "fornecedor_menor_custo": "TEXT",
        "menor_custo_unitario": "REAL DEFAULT 0",
        "markup_atual": "REAL DEFAULT 80",
        "ultima_compra": "REAL DEFAULT 0",
        "preco_osinfo": "REAL DEFAULT 0",
        "menor_lance": "REAL DEFAULT 0",
        "preco_medbox_original": "REAL DEFAULT 0",
        "empresa_melhor_lance": "TEXT",
        "menor_origem": "TEXT",
        "menor_empresa": "TEXT",
        "menor_valor_comparativo": "REAL DEFAULT 0",
        "valor_total_vencedor": "REAL DEFAULT 0",
        "medbox_vencedora": "INTEGER DEFAULT 0",
    }

    for nome, tipo in colunas.items():
        if nome not in existentes:
            cur.execute(f"ALTER TABLE cotacoes_geradas_itens ADD COLUMN {nome} {tipo}")

    conn.commit()
    conn.close()


def _fix_lance_disputa(preco_osinfo, preco_medbox, menor_lance, empresa_lance):
    opcoes = []

    if preco_osinfo > 0:
        opcoes.append(("OSINFO", "OSINFO", preco_osinfo))

    if preco_medbox > 0:
        opcoes.append(("MEDBOX", "MEDBOX", preco_medbox))

    if menor_lance > 0:
        opcoes.append(("OUTRA_EMPRESA", empresa_lance or "OUTRA EMPRESA", menor_lance))

    if not opcoes:
        return "-", "-", 0.0, False

    opcoes.sort(key=lambda x: x[2])
    origem, empresa, valor = opcoes[0]

    return origem, empresa, valor, origem == "MEDBOX"


def _fix_lance_montar_item_edicao(row, idx):
    def g(nome, padrao=None):
        try:
            return row[nome]
        except Exception:
            return padrao

    quantidade = _fix_lance_float(g("quantidade"), 0)
    preco_osinfo = _fix_lance_float(g("preco_osinfo"), 0)
    ultima_compra = _fix_lance_float(g("ultima_compra"), 0)
    menor_lance = _fix_lance_float(g("menor_lance"), 0)
    preco_medbox = _fix_lance_float(g("preco_medbox_original", g("valor_unitario", 0)), 0)
    menor_custo = _fix_lance_float(g("menor_custo_unitario"), 0)
    markup = _fix_lance_float(g("markup_atual"), 80)

    # Se existe custo salvo e preço MedBox não existe, reconstrói.
    if menor_custo > 0 and preco_medbox <= 0:
        preco_medbox = menor_custo * (1 + markup / 100)

    menor_origem, menor_empresa, menor_valor, medbox_vencedora = _fix_lance_disputa(
        preco_osinfo,
        preco_medbox,
        menor_lance,
        g("empresa_melhor_lance", "")
    )

    return {
        "item": idx,
        "item_numero": g("item_numero", idx),
        "descricao_produto": g("descricao_produto", ""),
        "sku_master": g("sku_master", ""),
        "categoria": g("categoria", ""),
        "quantidade": quantidade,
        "preco_osinfo": preco_osinfo,
        "preco_osinfo_formatado": _fix_lance_moeda(preco_osinfo),
        "ultima_compra": ultima_compra,
        "ultima_compra_formatada": _fix_lance_moeda(ultima_compra),
        "preco_medbox": preco_medbox,
        "preco_medbox_formatado": _fix_lance_moeda(preco_medbox),
        "markup_atual": markup,
        "menor_preco_ofertado": menor_lance,
        "menor_preco_ofertado_formatado": _fix_lance_moeda(menor_lance),
        "empresa_melhor_lance": g("empresa_melhor_lance", ""),
        "menor_valor": menor_valor,
        "menor_valor_formatado": _fix_lance_moeda(menor_valor),
        "menor_valor_nome": menor_empresa,
        "menor_custo_unitario": menor_custo,
        "menor_custo_unitario_formatado": _fix_lance_moeda(menor_custo) if menor_custo > 0 else "",
        "fornecedor_menor_custo": g("fornecedor_menor_custo", ""),
        "marca_fabricante": g("marca", ""),
        "marca": g("marca", ""),
        "sku_encontrado": bool(g("sku_master", "")),
        "tem_preco": preco_medbox > 0,
        "status": "SKU SELECIONADO" if g("sku_master", "") else "REVISAR SKU",
        "score": 0,
        "sugestoes_sku": [],
    }


def editar_cotacao_gerada_fix_persistencia(numero_cotacao):
    _fix_lance_garantir_colunas()

    conn = conectar()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("SELECT * FROM cotacoes_geradas WHERE numero_cotacao = ?", (numero_cotacao,))
    cotacao = cur.fetchone()

    if not cotacao:
        conn.close()
        flash(f"Cotação {numero_cotacao} não encontrada.")
        return redirect(url_for("listar_cotacoes_geradas"))

    cur.execute("""
        SELECT *
        FROM cotacoes_geradas_itens
        WHERE cotacao_id = ?
        ORDER BY item_numero
    """, (cotacao["id"],))

    rows = cur.fetchall()
    conn.close()

    itens = [_fix_lance_montar_item_edicao(row, idx) for idx, row in enumerate(rows, start=1)]

    try:
        resumo_lances = montar_resumo_lances(itens)
    except Exception:
        resumo_lances = {
            "total_itens": len(itens),
            "itens_com_sku": sum(1 for i in itens if i.get("sku_master")),
            "itens_revisar_sku": sum(1 for i in itens if not i.get("sku_master")),
            "itens_com_preco_medbox": sum(1 for i in itens if _fix_lance_float(i.get("preco_medbox")) > 0),
            "itens_sem_preco": sum(1 for i in itens if _fix_lance_float(i.get("preco_medbox")) <= 0),
            "itens_competitivos": 0,
            "itens_ganhos_medbox": 0,
            "percentual_itens_ganhos": 0,
            "percentual_itens_ganhos_formatado": "0,00%",
            "itens_negociar": 0,
            "total_medbox": 0,
            "total_medbox_formatado": "R$ 0,00",
            "total_ganho_medbox": 0,
            "total_ganho_medbox_formatado": "R$ 0,00",
        }

    analise = {
        "arquivo": f"EDITANDO {numero_cotacao}",
        "itens_extraidos": len(itens),
        "markup_percentual": 80,
        "itens": itens,
        "resumo": resumo_lances,
    }

    return render_template(
        "cotacao_lances.html",
        data_atual=DATA_ATUAL,
        resumo=resumo_dashboard(),
        analise=analise,
        erro=None,
        arquivo_nome=f"EDITANDO {numero_cotacao}",
        markup_percentual=80,
        numero_cotacao_editando=numero_cotacao,
        modo_edicao_cotacao=True,
    )


def atualizar_cotacao_gerada_fix_persistencia(numero_cotacao):
    _fix_lance_garantir_colunas()

    dados = request.get_json(silent=True) or {}
    itens = dados.get("itens", [])

    if not itens:
        return jsonify({"ok": False, "erro": "Nenhum item recebido para atualizar."}), 400

    cliente = str(dados.get("cliente") or dados.get("cliente_orgao") or "").strip().upper()
    cliente_exibicao = cliente or "-"

    conn = conectar()
    cur = conn.cursor()

    cur.execute("SELECT id FROM cotacoes_geradas WHERE numero_cotacao = ?", (numero_cotacao,))
    row = cur.fetchone()

    if not row:
        conn.close()
        return jsonify({"ok": False, "erro": f"Cotação {numero_cotacao} não encontrada."}), 404

    cotacao_id = row[0]
    cur.execute("DELETE FROM cotacoes_geradas_itens WHERE cotacao_id = ?", (cotacao_id,))

    total_medbox = 0.0

    for idx, item in enumerate(itens, start=1):
        descricao = str(item.get("descricao_produto") or item.get("descricao") or "").strip().upper()
        sku_master = str(item.get("sku_master") or "").strip().upper()
        categoria = str(item.get("categoria") or "").strip().upper()
        marca = str(item.get("marca_fabricante") or item.get("marca") or "").strip().upper()
        fornecedor = str(item.get("fornecedor_menor_custo") or "").strip().upper()

        quantidade = _fix_lance_float(item.get("quantidade"), 0)
        preco_osinfo = _fix_lance_float(item.get("preco_osinfo"), 0)
        ultima_compra = _fix_lance_float(item.get("ultima_compra"), 0)
        menor_lance = _fix_lance_float(item.get("menor_preco_ofertado", item.get("menor_lance", 0)), 0)
        menor_custo = _fix_lance_float(item.get("menor_custo_unitario"), 0)
        markup = _fix_lance_float(item.get("markup_atual"), 80)

        preco_medbox = _fix_lance_float(item.get("preco_medbox"), 0)
        if menor_custo > 0:
            preco_medbox = menor_custo * (1 + markup / 100)

        empresa_lance = str(item.get("empresa_melhor_lance") or "").strip().upper()

        menor_origem, menor_empresa, menor_valor, medbox_vencedora = _fix_lance_disputa(
            preco_osinfo,
            preco_medbox,
            menor_lance,
            empresa_lance
        )

        valor_total_vencedor = quantidade * menor_valor
        valor_unitario = preco_medbox if medbox_vencedora else 0.0
        valor_total = quantidade * valor_unitario
        total_medbox += valor_total

        cur.execute("""
            INSERT INTO cotacoes_geradas_itens (
                cotacao_id,
                item_numero,
                descricao_produto,
                sku_master,
                marca,
                quantidade,
                valor_unitario,
                valor_total,
                venceu_medbox,
                status_lance,
                categoria,
                fornecedor_menor_custo,
                menor_custo_unitario,
                markup_atual,
                ultima_compra,
                preco_osinfo,
                menor_lance,
                preco_medbox_original,
                empresa_melhor_lance,
                menor_origem,
                menor_empresa,
                menor_valor_comparativo,
                valor_total_vencedor,
                medbox_vencedora
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            cotacao_id,
            idx,
            descricao,
            sku_master,
            marca,
            quantidade,
            valor_unitario,
            valor_total,
            1 if medbox_vencedora else 0,
            "SKU SELECIONADO" if sku_master else "REVISAR SKU",
            categoria,
            fornecedor,
            menor_custo,
            markup,
            ultima_compra,
            preco_osinfo,
            menor_lance,
            preco_medbox,
            empresa_lance,
            menor_origem,
            menor_empresa,
            menor_valor,
            valor_total_vencedor,
            1 if medbox_vencedora else 0,
        ))

    cur.execute("""
        UPDATE cotacoes_geradas
        SET cliente = ?, total_geral = ?
        WHERE id = ?
    """, (cliente_exibicao, total_medbox, cotacao_id))

    conn.commit()
    conn.close()

    return jsonify({
        "ok": True,
        "numero_cotacao": numero_cotacao,
        "url": f"/cotacoes/geradas/{numero_cotacao}"
    })


# Substitui os endpoints já registrados sem recriar rotas.
try:
    for _rule in list(app.url_map.iter_rules()):
        if str(_rule.rule) == "/cotacoes/geradas/<numero_cotacao>/editar":
            app.view_functions[_rule.endpoint] = editar_cotacao_gerada_fix_persistencia

        if str(_rule.rule) == "/cotacoes/lances/atualizar-cotacao/<numero_cotacao>":
            app.view_functions[_rule.endpoint] = atualizar_cotacao_gerada_fix_persistencia

    print("OK: endpoints de edição/salvamento de cotação substituídos pelo fix definitivo.")
except Exception as _exc:
    print("AVISO: não foi possível substituir endpoints de lances:", _exc)





# ============================================================
# PATCH AUDITORIA SKU MASTER - BUSCA DESCRIÇÕES FORNECEDOR
# Sugere descrições reais da base considerando especificações
# como dosagem, tamanho, volume, cor, material, nº e referência.
# ============================================================

def _aud_sku_norm_txt(valor):
    import re
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
    texto = texto.replace("N°", "Nº").replace("NO.", "Nº").replace("NUMERO", "Nº")
    texto = re.sub(r"[^A-Z0-9%º/,.+\- X]+", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


def _aud_sku_tokens(valor):
    import re
    texto = _aud_sku_norm_txt(valor)
    ignorar = {
        "DE", "DA", "DO", "DAS", "DOS", "COM", "SEM", "PARA", "POR", "VIA",
        "USO", "ADULTO", "INFANTIL", "PEDIATRICO", "MARCA", "GENERICO",
        "IMPORTADO", "MANIPULADO", "UND", "UN", "UNIDADE"
    }
    return [t for t in re.split(r"\s+", texto) if len(t) >= 2 and t not in ignorar]


def _aud_sku_specs(valor):
    import re
    texto = _aud_sku_norm_txt(valor)
    specs = set()

    # Medidas, dosagens e volumes
    for m in re.findall(r"\b\d+(?:[,.]\d+)?\s*(?:MG|G|MCG|ML|L|UI|U|CM|MM|M|FR|G|GA|GZ)\b", texto):
        specs.add(re.sub(r"\s+", "", m.replace(",", ".")))

    # Tamanhos compostos: 13X4,5 | 25X7 | 8,5MM | 20CMX30CM
    for m in re.findall(r"\b\d+(?:[,.]\d+)?\s*X\s*\d+(?:[,.]\d+)?(?:\s*(?:MM|CM|M))?\b", texto):
        specs.add(re.sub(r"\s+", "", m.replace(",", ".")))

    # Nº / número / FR / gauge solto
    for m in re.findall(r"(?:Nº|N|NO)\s*\.?\s*\d+(?:[,.]\d+)?", texto):
        specs.add(re.sub(r"\s+", "", m.replace(",", ".")))

    # Referências
    for m in re.findall(r"REF\.?\s*[:\-]?\s*[A-Z0-9/\-.]+", texto):
        specs.add(m.replace(" ", ""))

    # Palavras técnicas que mudam o produto
    termos_criticos = [
        "COM BALAO", "SEM BALAO", "C/ BALAO", "S/ BALAO",
        "LATEX", "SILICONE", "PVC", "POLIURETANO",
        "AZUL", "PRETO", "VERDE", "ROSA", "BRANCO",
        "OPACO", "TRANSPARENTE",
        "2 VIAS", "3 VIAS", "DUAS VIAS", "TRES VIAS",
        "DRENAVEL", "FECHADA", "ABERTA",
        "ESTERIL", "NAO ESTERIL",
    ]
    for termo in termos_criticos:
        if termo in texto:
            specs.add(termo)

    return specs


def _aud_sku_score(descricao_base, candidato):
    base_norm = _aud_sku_norm_txt(descricao_base)
    cand_norm = _aud_sku_norm_txt(candidato)

    base_tokens = set(_aud_sku_tokens(base_norm))
    cand_tokens = set(_aud_sku_tokens(cand_norm))

    if not base_tokens or not cand_tokens:
        return 0, ["SEM_TOKENS"]

    inter = base_tokens.intersection(cand_tokens)
    uniao = base_tokens.union(cand_tokens)
    score_tokens = (len(inter) / max(1, len(uniao))) * 70

    base_specs = _aud_sku_specs(base_norm)
    cand_specs = _aud_sku_specs(cand_norm)

    alertas = []

    if base_specs:
        specs_iguais = base_specs.intersection(cand_specs)
        specs_faltando = base_specs.difference(cand_specs)
        specs_extras = cand_specs.difference(base_specs)

        score_specs = (len(specs_iguais) / max(1, len(base_specs))) * 30

        if specs_faltando:
            alertas.append("ESPEC_FALTANDO: " + ", ".join(sorted(list(specs_faltando))[:5]))
        if specs_extras:
            alertas.append("ESPEC_EXTRA: " + ", ".join(sorted(list(specs_extras))[:5]))
    else:
        score_specs = 15
        if cand_specs:
            alertas.append("CANDIDATO_TEM_ESPECIFICACAO_EXTRA")

    score = int(round(score_tokens + score_specs))

    # Penaliza candidatos que parecem parecidos, mas têm especificações conflitantes.
    if alertas:
        score = max(0, score - 15)

    # Bônus quando o começo bate.
    base_inicio = " ".join(_aud_sku_tokens(base_norm)[:3])
    cand_inicio = " ".join(_aud_sku_tokens(cand_norm)[:3])
    if base_inicio and base_inicio == cand_inicio:
        score += 10

    return min(100, score), alertas


@app.route("/sku-master/auditoria/descricoes-fornecedor-json")
def sku_master_auditoria_descricoes_fornecedor_json():
    produto_id = request.args.get("produto_id", "").strip()
    descricao = request.args.get("descricao", "").strip()
    limite = 30

    conn = conectar()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    if produto_id and not descricao:
        row = cur.execute("""
            SELECT produto_padrao, sku_master
            FROM produtos
            WHERE id = ?
            LIMIT 1
        """, (produto_id,)).fetchone()
        if row:
            descricao = row["produto_padrao"] or row["sku_master"] or ""

    descricao_norm = _aud_sku_norm_txt(descricao)
    tokens = _aud_sku_tokens(descricao_norm)
    principais = tokens[:5]

    candidatos = []

    # Busca em preços de fornecedores: descrição real mais útil para preencher o campo.
    where = []
    params = []
    for termo in principais:
        where.append("UPPER(COALESCE(pf.descricao_original, '')) LIKE ?")
        params.append(f"%{termo}%")

    where_sql = " OR ".join(where) if where else "1=1"

    try:
        rows = cur.execute(f"""
            SELECT
                pf.produto_id,
                pf.descricao_original,
                pf.marca,
                pf.preco,
                pf.fornecedor_id,
                f.nome AS fornecedor,
                p.sku_master,
                p.fabricante,
                p.categoria
            FROM precos_fornecedores pf
            LEFT JOIN fornecedores f ON f.id = pf.fornecedor_id
            LEFT JOIN produtos p ON p.id = pf.produto_id
            WHERE pf.descricao_original IS NOT NULL
              AND TRIM(pf.descricao_original) <> ''
              AND ({where_sql})
            ORDER BY pf.id DESC
            LIMIT 800
        """, params).fetchall()
    except Exception:
        rows = []

    vistos = set()

    for r in rows:
        desc_cand = str(r["descricao_original"] or "").strip()
        chave = _aud_sku_norm_txt(desc_cand)
        if not chave or chave in vistos:
            continue
        vistos.add(chave)

        score, alertas = _aud_sku_score(descricao, desc_cand)
        if score < 35:
            continue

        marca = str(r["marca"] or r["fabricante"] or "").strip().upper()
        sku = str(r["sku_master"] or "").strip().upper()

        candidatos.append({
            "origem": "PRECO_FORNECEDOR",
            "descricao": desc_cand.upper(),
            "sku_master": sku,
            "marca": marca,
            "categoria": str(r["categoria"] or "").strip().upper(),
            "fornecedor": str(r["fornecedor"] or "").strip().upper(),
            "preco": float(r["preco"] or 0),
            "score": score,
            "alertas": alertas,
        })

    # Complementa com produtos já cadastrados.
    where = []
    params = []
    for termo in principais:
        where.append("(UPPER(COALESCE(produto_padrao, '')) LIKE ? OR UPPER(COALESCE(sku_master, '')) LIKE ?)")
        params.extend([f"%{termo}%", f"%{termo}%"])

    where_sql = " OR ".join(where) if where else "1=1"

    try:
        rows_prod = cur.execute(f"""
            SELECT id, produto_padrao, sku_master, fabricante, categoria
            FROM produtos
            WHERE ativo = 1
              AND ({where_sql})
            ORDER BY id DESC
            LIMIT 500
        """, params).fetchall()
    except Exception:
        rows_prod = []

    for r in rows_prod:
        desc_cand = str(r["sku_master"] or r["produto_padrao"] or "").strip()
        chave = "PROD::" + _aud_sku_norm_txt(desc_cand)
        if not desc_cand or chave in vistos:
            continue
        vistos.add(chave)

        score, alertas = _aud_sku_score(descricao, desc_cand)
        if score < 35:
            continue

        candidatos.append({
            "origem": "PRODUTOS",
            "descricao": desc_cand.upper(),
            "sku_master": str(r["sku_master"] or "").strip().upper(),
            "marca": str(r["fabricante"] or "").strip().upper(),
            "categoria": str(r["categoria"] or "").strip().upper(),
            "fornecedor": "",
            "preco": 0,
            "score": score,
            "alertas": alertas,
        })

    conn.close()

    candidatos.sort(key=lambda x: (
        -x["score"],
        0 if x.get("sku_master") else 1,
        0 if not x.get("alertas") else 1,
        x["descricao"]
    ))

    return jsonify({
        "ok": True,
        "descricao_base": descricao,
        "total": len(candidatos[:limite]),
        "itens": candidatos[:limite],
    })


if __name__ == "__main__":
    print("MEDBOX V3 rodando em http://127.0.0.1:5000")
    app.run(debug=True)

# ============================================================
# LANCES DE COTAÇÃO
# ============================================================

@app.route("/lances-cotacao")
def lances_cotacao():
    return render_template("lances_cotacao.html", resultado=None, erro=None)


@app.route("/lances-cotacao/importar", methods=["POST"])
def lances_cotacao_importar():
    from pathlib import Path
    from flask import request
    import os
    from werkzeug.utils import secure_filename

    arquivo = request.files.get("arquivo")
    markup = request.form.get("markup", "1.50")

    if not arquivo or not arquivo.filename:
        return render_template("lances_cotacao.html", resultado=None, erro="Nenhum arquivo enviado.")

    uploads_dir = Path("uploads/lances_cotacao")
    uploads_dir.mkdir(parents=True, exist_ok=True)

    nome = secure_filename(arquivo.filename)
    caminho = uploads_dir / nome
    arquivo.save(caminho)

    try:
        resultado = importar_lances_cotacao(caminho, markup_padrao=markup)
        return render_template("lances_cotacao.html", resultado=resultado, erro=None)
    except Exception as exc:
        return render_template("lances_cotacao.html", resultado=None, erro=f"Erro ao importar cotação: {exc}")
