from flask import Flask, render_template, request, redirect, url_for, flash
from datetime import datetime
from pathlib import Path

from core.banco import (
    criar_banco, resumo_dashboard, conectar,
    listar_fornecedores, cadastrar_fornecedor, excluir_fornecedor,
    listar_sugestoes_busca,
    listar_equivalencias, adicionar_equivalencia, excluir_equivalencia,
    listar_produtos_simples, listar_cotacoes
)
from core.busca_inteligente import buscar_produto_inteligente
from core.formatadores import moeda_br
from core.importador_sku import importar_sku_master

app = Flask(__name__)
app.secret_key = "medbox_v3_zero"

criar_banco()

BASE_DIR = Path(__file__).resolve().parent
PASTA_UPLOADS = BASE_DIR / "uploads"
PASTA_UPLOADS.mkdir(exist_ok=True)

DATA_ATUAL = datetime.now().strftime("%d/%m/%Y")


def contar_produtos():
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM produtos WHERE ativo = 1")
    total = cursor.fetchone()[0]
    conn.close()
    return total


def formatar_resultados_busca(resultados):
    for item in resultados:
        menor_preco = item.get("menor_preco")
        item["menor_preco_formatado"] = moeda_br(menor_preco)
        origem_catalogo = item.get("fabricante") or item.get("marca") or "Catálogo"
        item["origem_catalogo"] = origem_catalogo
        item["origem_catalogo_formatada"] = (
            f"{origem_catalogo} (catálogo)"
            if origem_catalogo != "Catálogo"
            else origem_catalogo
        )
        item["fornecedor_menor_formatado"] = (
            item.get("fornecedor_menor") if item.get("precos") else "-"
        )

        for preco in item.get("precos", []):
            valor = preco.get("preco")
            preco["preco_formatado"] = moeda_br(valor)
            if valor is not None and menor_preco is not None:
                preco["diferenca_formatada"] = moeda_br(valor - menor_preco)
            else:
                preco["diferenca_formatada"] = "-"

        for historico in item.get("historico_precos", []):
            historico["preco_formatado"] = moeda_br(historico.get("preco"))

    return resultados


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
    if termo:
        resultados = buscar_produto_inteligente(termo, limite=20)
        resultados = formatar_resultados_busca(resultados)
        sugestoes = listar_sugestoes_busca(termo)
    return render_template(
        "busca.html",
        data_atual=DATA_ATUAL,
        resumo=resumo_dashboard(),
        termo=termo,
        resultados=resultados,
        sugestoes=sugestoes
    )


@app.route("/produtos")
def produtos():
    return render_template(
        "produtos.html",
        data_atual=DATA_ATUAL,
        resumo=resumo_dashboard(),
        total_produtos=contar_produtos()
    )


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
        return f"Erro ao importar: {erro}"


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


if __name__ == "__main__":
    print("MEDBOX V3 rodando em http://127.0.0.1:5000")
    app.run(debug=True)
