from pathlib import Path
from datetime import datetime
import re

APP = Path("app.py")
CORE = Path("core/mapa_precos_clientes.py")
HTML = Path("templates/mapa_precos_clientes.html")

for p in [APP, CORE, HTML]:
    if not p.exists():
        raise FileNotFoundError(p)

ts = datetime.now().strftime("%Y%m%d_%H%M%S")

for p in [APP, CORE, HTML]:
    backup = p.with_name(p.name + f".bak_mapa_leve_{ts}")
    backup.write_text(p.read_text(encoding="utf-8"), encoding="utf-8")
    print("Backup criado:", backup)

app_txt = APP.read_text(encoding="utf-8")
core_txt = CORE.read_text(encoding="utf-8")
html_txt = HTML.read_text(encoding="utf-8")

# ============================================================
# 1) app.py - rota passa filtros para o core
# ============================================================

app_txt = app_txt.replace(
'''@app.route("/mapa-precos-clientes")
def mapa_precos_clientes():
    from core.mapa_precos_clientes import dados_tela_mapa_precos_clientes

    dados = dados_tela_mapa_precos_clientes()

    return render_template(
        "mapa_precos_clientes.html",
        data_atual=DATA_ATUAL,
        resumo=resumo_dashboard(),
        dados=dados,
    )''',
'''@app.route("/mapa-precos-clientes")
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
    )'''
)

APP.write_text(app_txt, encoding="utf-8")


# ============================================================
# 2) core - limita renderização, mas mantém banco completo
# ============================================================

PATCH_CORE = r'''

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
'''

if "PATCH MAPA LEVE - RENDERIZAÇÃO LIMITADA" not in core_txt:
    core_txt = core_txt.rstrip() + "\n\n" + PATCH_CORE + "\n"

CORE.write_text(core_txt, encoding="utf-8")


# ============================================================
# 3) HTML - barra de busca/paginação acima da tabela
# ============================================================

BLOCO_FILTRO = r'''
<div class="mpc-panel mpc-filtro-leve">
    <form method="get" action="/mapa-precos-clientes" class="mpc-filtro-form">
        <div>
            <label>Pesquisar produto / SKU / categoria</label>
            <input
                type="text"
                name="q"
                value="{{ dados.filtros_mapa.q }}"
                placeholder="Ex.: soro 500ml, dipirona, luva, seringa..."
            >
        </div>

        <div>
            <label>Itens por página</label>
            <select name="limite">
                <option value="100" {% if dados.filtros_mapa.limite == 100 %}selected{% endif %}>100</option>
                <option value="300" {% if dados.filtros_mapa.limite == 300 %}selected{% endif %}>300</option>
                <option value="500" {% if dados.filtros_mapa.limite == 500 %}selected{% endif %}>500</option>
                <option value="1000" {% if dados.filtros_mapa.limite == 1000 %}selected{% endif %}>1000</option>
            </select>
        </div>

        <div class="mpc-filtro-botoes">
            <button type="submit" name="pagina" value="1">Filtrar</button>

            <button
                type="submit"
                name="pagina"
                value="{{ dados.filtros_mapa.pagina_anterior }}"
                {% if not dados.filtros_mapa.tem_anterior %}disabled{% endif %}
            >
                ◀ Anterior
            </button>

            <button
                type="submit"
                name="pagina"
                value="{{ dados.filtros_mapa.proxima_pagina }}"
                {% if not dados.filtros_mapa.tem_proxima %}disabled{% endif %}
            >
                Próxima ▶
            </button>

            <a href="/mapa-precos-clientes">Limpar</a>
        </div>

        <div class="mpc-filtro-info">
            Exibindo
            <strong>{{ dados.filtros_mapa.exibindo_inicio }}</strong>
            a
            <strong>{{ dados.filtros_mapa.exibindo_fim }}</strong>
            de
            <strong>{{ dados.filtros_mapa.total_filtrado }}</strong>
            produtos filtrados.
            Total geral:
            <strong>{{ dados.filtros_mapa.total_geral }}</strong>.
            Página
            <strong>{{ dados.filtros_mapa.pagina }}</strong>
            de
            <strong>{{ dados.filtros_mapa.total_paginas }}</strong>.
        </div>
    </form>
</div>
'''

CSS_FILTRO = r'''
<style id="mpc-filtro-leve-css">
.mpc-filtro-leve {
    margin: 14px 0 12px 0 !important;
    padding: 14px !important;
    background: #f8fafc !important;
    border: 1px solid #d9e2ef !important;
    border-radius: 14px !important;
}

.mpc-filtro-form {
    display: grid !important;
    grid-template-columns: minmax(260px, 1fr) 150px auto !important;
    gap: 12px !important;
    align-items: end !important;
}

.mpc-filtro-form label {
    display: block !important;
    font-size: 11px !important;
    font-weight: 800 !important;
    color: #334155 !important;
    margin-bottom: 4px !important;
    text-transform: uppercase !important;
}

.mpc-filtro-form input,
.mpc-filtro-form select {
    width: 100% !important;
    height: 36px !important;
    border: 1px solid #cbd5e1 !important;
    border-radius: 10px !important;
    padding: 7px 10px !important;
    font-size: 13px !important;
}

.mpc-filtro-botoes {
    display: flex !important;
    gap: 8px !important;
    align-items: center !important;
    flex-wrap: wrap !important;
}

.mpc-filtro-botoes button,
.mpc-filtro-botoes a {
    height: 36px !important;
    border: none !important;
    border-radius: 10px !important;
    padding: 8px 12px !important;
    background: #00486C !important;
    color: white !important;
    font-weight: 800 !important;
    text-decoration: none !important;
    cursor: pointer !important;
    font-size: 12px !important;
}

.mpc-filtro-botoes button:disabled {
    background: #94a3b8 !important;
    cursor: not-allowed !important;
}

.mpc-filtro-info {
    grid-column: 1 / -1 !important;
    font-size: 12px !important;
    color: #475569 !important;
    padding-top: 4px !important;
}
</style>
'''

# Remove versões anteriores se existirem
html_txt = re.sub(r'\n<div class="mpc-panel mpc-filtro-leve">.*?</div>\s*(?=<div class="mpc-panel">)', '\n', html_txt, flags=re.DOTALL)
html_txt = re.sub(r'\n<style id="mpc-filtro-leve-css">.*?</style>', '\n', html_txt, flags=re.DOTALL)

# Insere CSS após primeiro </style>
if "</style>" in html_txt:
    pos = html_txt.find("</style>") + len("</style>")
    html_txt = html_txt[:pos] + "\n" + CSS_FILTRO + html_txt[pos:]
else:
    html_txt = CSS_FILTRO + "\n" + html_txt

# Insere bloco antes da tabela principal
html_txt = html_txt.replace(
    '<div class="mpc-panel">\n    <div class="mpc-panel-header">\n        <h3>MEDBOX | Mapa de Comparação de Preços por Cliente</h3>',
    BLOCO_FILTRO + '\n\n<div class="mpc-panel">\n    <div class="mpc-panel-header">\n        <h3>MEDBOX | Mapa de Comparação de Preços por Cliente</h3>',
    1
)

HTML.write_text(html_txt, encoding="utf-8")

print("OK: mapa configurado para renderização leve.")
print("OK: tela inicial limitada a 300 itens.")
print("OK: pesquisa por produto/SKU/categoria adicionada.")
print("OK: paginação adicionada.")
