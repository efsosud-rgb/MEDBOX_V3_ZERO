import json
import logging
import traceback
from flask import Flask, Response, render_template, request, redirect, url_for, flash
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
from core.cotacao_lances import analisar_arquivo_cotacao, configurar_logger_cotacao
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
    filtro = request.args.get("filtro", "todos")
    auditoria = gerar_auditoria_sku_master(filtro=filtro, limite=250)
    return render_template(
        "sku_master_auditoria.html",
        data_atual=DATA_ATUAL,
        resumo=resumo_dashboard(),
        auditoria=auditoria,
        filtros=FILTROS_AUDITORIA_SKU,
    )


@app.route("/sku-master/auditoria.csv")
def sku_master_auditoria_csv():
    filtro = request.args.get("filtro", "todos")
    conteudo = gerar_csv_auditoria_sku_master(filtro=filtro)
    nome_arquivo = f"auditoria_sku_master_{filtro}.csv"
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


@app.route("/cotacoes/lances")
def cotacoes_lances():
    return render_template(
        "cotacao_lances.html",
        data_atual=DATA_ATUAL,
        resumo=resumo_dashboard(),
        analise=None,
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
    ids_cascata_selecionados = data.get("ids_cascata_selecionados", [])

    try:
        resultado = salvar_edicao_manual_produto(
            produto_id=produto_id,
            dados_novos=dados,
            opcoes_cascata=opcoes_cascata,
            usuario="compras",
            ids_cascata_selecionados=ids_cascata_selecionados
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
    filtro = request.form.get("filtro", "todos")
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
    return redirect(url_for("sku_master_auditoria", filtro=filtro))


@app.route("/sku-master/skus-json")
def sku_master_skus_json():
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT DISTINCT COALESCE(NULLIF(TRIM(sku_master), ''), produto_padrao) as sugestao
        FROM produtos
        WHERE ativo = 1
        ORDER BY sugestao
        """
    )
    skus = [row["sugestao"] for row in cursor.fetchall()]
    conn.close()
    return Response(json.dumps(skus, ensure_ascii=False), content_type="application/json")


@app.route("/sku-master/auditoria/salvar-sku", methods=["POST"])
def sku_master_auditoria_salvar_sku():
    produto_id = request.form.get("produto_id")
    sku_manual = request.form.get("sku_manual", "").strip()
    filtro = request.form.get("filtro", "todos")
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
    return redirect(url_for("sku_master_auditoria", filtro=filtro))


if __name__ == "__main__":
    print("MEDBOX V3 rodando em http://127.0.0.1:5000")
    app.run(debug=True)