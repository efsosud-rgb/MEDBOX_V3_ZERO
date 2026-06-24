from pathlib import Path
from datetime import datetime
import re

arquivos_backup = [
    Path("app.py"),
    Path("core/mapa_precos_clientes.py"),
    Path("templates/mapa_precos_clientes.html"),
]

for path in arquivos_backup:
    if path.exists():
        backup = path.with_suffix(path.suffix + ".bak_mapa_erp_v3_" + datetime.now().strftime("%Y%m%d_%H%M%S"))
        backup.write_text(path.read_text(encoding="utf-8", errors="ignore"), encoding="utf-8")
        print(f"Backup criado: {backup}")

# ============================================================
# 1) Atualiza core/mapa_precos_clientes.py
# ============================================================

core_path = Path("core/mapa_precos_clientes.py")
core_txt = core_path.read_text(encoding="utf-8", errors="ignore")

append_core = r'''

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

            sku_final = sku_normalizado or normalizar_texto_mapa(
                row.get("produto_padrao")
                or row.get("descricao_original")
            )

            categoria_final = normalizar_texto_mapa(
                row.get("categoria_produto")
                or row.get("categoria")
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
'''

if "FASE 3 - MAPA ERP" not in core_txt:
    core_txt = core_txt + append_core
    core_path.write_text(core_txt, encoding="utf-8")
    print("OK: Fase 3 adicionada ao core/mapa_precos_clientes.py")
else:
    print("AVISO: Fase 3 já estava no core")

# ============================================================
# 2) Atualiza app.py com endpoint para editar SKU/categoria
# ============================================================

app_path = Path("app.py")
app_txt = app_path.read_text(encoding="utf-8", errors="ignore")

rota_update = r'''

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
'''

if "def mapa_precos_clientes_atualizar_item()" not in app_txt:
    marcador = '@app.route("/importacoes")'
    if marcador not in app_txt:
        raise SystemExit("ERRO: marcador de /importacoes não encontrado.")
    app_txt = app_txt.replace(marcador, rota_update + "\n\n" + marcador)
    app_path.write_text(app_txt, encoding="utf-8")
    print("OK: endpoint atualizar item do mapa adicionado ao app.py")
else:
    print("AVISO: endpoint atualizar item já existia")

# ============================================================
# 3) Reescreve template do mapa
# ============================================================

tpl_path = Path("templates/mapa_precos_clientes.html")

tpl_path.write_text(r'''{% extends "base.html" %}

{% block title %}Mapa de Preços Clientes{% endblock %}
{% block subtitle %}Previsão de demanda mensal, preços por cliente e oportunidade de compra MedBox{% endblock %}

{% block content %}

<style>
    .mpc-grid {
        display: grid;
        grid-template-columns: repeat(4, minmax(160px, 1fr));
        gap: 14px;
        margin-bottom: 14px;
    }

    .mpc-card {
        background: linear-gradient(145deg, #ffffff, #eef4fb);
        border: 1px solid #d9e2ef;
        border-radius: 16px;
        padding: 15px;
        box-shadow: 8px 8px 18px rgba(15, 23, 42, 0.08), -6px -6px 18px rgba(255,255,255,0.9);
    }

    .mpc-card small {
        display: block;
        color: #64748b;
        font-size: 10px;
        text-transform: uppercase;
        font-weight: 800;
        margin-bottom: 8px;
    }

    .mpc-card strong {
        font-size: 22px;
        color: #0f172a;
    }

    .mpc-actions {
        display: flex;
        gap: 10px;
        margin-bottom: 14px;
        flex-wrap: wrap;
    }

    .mpc-btn {
        background: linear-gradient(145deg, #00557d, #003d5c);
        color: white;
        border: none;
        padding: 10px 14px;
        border-radius: 10px;
        font-weight: 800;
        text-decoration: none;
        display: inline-block;
        box-shadow: 0 5px 12px rgba(0,72,108,.24);
    }

    .mpc-btn.secondary {
        background: linear-gradient(145deg, #ef1235, #b8001e);
    }

    .mpc-panel {
        background: #f8fafc;
        border: 1px solid #d9e2ef;
        border-radius: 16px;
        overflow: hidden;
        box-shadow: 10px 10px 24px rgba(15, 23, 42, 0.10), -6px -6px 18px rgba(255,255,255,0.9);
    }

    .mpc-panel-header {
        padding: 13px 16px;
        border-bottom: 1px solid #d6e0ec;
        display: flex;
        justify-content: space-between;
        gap: 12px;
        align-items: center;
        background: linear-gradient(180deg, #ffffff, #edf3f9);
    }

    .mpc-panel-header h3 {
        margin: 0;
        color: #0f172a;
        font-size: 15px;
    }

    .mpc-table-wrap {
        overflow: auto;
        max-height: calc(100vh - 245px);
        border-top: 1px solid #dce6f1;
    }

    .mpc-table {
        width: max-content;
        min-width: 100%;
        border-collapse: separate;
        border-spacing: 0;
        font-size: 10.5px;
    }

    .mpc-table th {
        position: sticky;
        top: 0;
        background: #0f1b2d;
        color: white;
        z-index: 3;
        padding: 7px;
        border-right: 1px solid #2b3c59;
        border-bottom: 1px solid #2b3c59;
        white-space: nowrap;
        text-align: center;
        vertical-align: middle;
    }

    .mpc-table tr:nth-child(even) td {
        background-color: #f9fbfe;
    }

    .mpc-table td {
        padding: 6px 7px;
        border-right: 1px solid #d7dfeb;
        border-bottom: 1px solid #d7dfeb;
        background: white;
        white-space: nowrap;
        vertical-align: middle;
    }

    .col-categoria {
        width: 115px;
        min-width: 115px;
    }

    .col-descricao {
        width: 235px;
        min-width: 235px;
        max-width: 235px;
        white-space: normal !important;
        font-weight: 700;
        color: #0f172a;
    }

    .col-sku {
        width: 250px;
        min-width: 250px;
        max-width: 250px;
        white-space: normal !important;
    }

    .col-num {
        text-align: center;
        font-variant-numeric: tabular-nums;
    }

    .col-moeda {
        text-align: right;
        font-variant-numeric: tabular-nums;
        font-weight: 700;
    }

    .mpc-input {
        width: 100%;
        min-width: 90px;
        border: 1px solid #cbd5e1;
        border-radius: 8px;
        padding: 5px 7px;
        font-size: 10.5px;
        background: #ffffff;
    }

    .mpc-input.sku {
        min-width: 230px;
        font-weight: 700;
        color: #0f172a;
    }

    .mpc-input.cat {
        min-width: 105px;
        text-align: center;
        font-weight: 700;
    }

    .mpc-input.markup {
        width: 58px;
        min-width: 58px;
        text-align: center;
        font-weight: 800;
        color: #00486C;
    }

    .mpc-client-head {
        color: #0f172a !important;
        font-weight: 900;
        border-left: 2px solid rgba(15, 23, 42, .15);
    }

    .mpc-subhead {
        color: #0f172a !important;
        font-weight: 800;
    }

    {% set cores = [
        '#dbeafe', '#ffedd5', '#dcfce7', '#ede9fe', '#fee2e2',
        '#e0e7ff', '#fef3c7', '#ccfbf1', '#e2e8f0', '#fce7f3',
        '#d9f99d', '#cffafe', '#fae8ff', '#fde68a', '#e5e7eb'
    ] %}

    {% for cliente in dados.clientes_colunas %}
        .cliente-bg-{{ loop.index0 }} {
            background: {{ cores[loop.index0] }} !important;
        }

        .cliente-head-{{ loop.index0 }} {
            background: linear-gradient(145deg, {{ cores[loop.index0] }}, #ffffff) !important;
            color: #0f172a !important;
        }
    {% endfor %}

    .menor-cliente {
        color: #D80024 !important;
        font-weight: 900 !important;
    }

    .medbox-menor {
        color: #0046ff !important;
        font-weight: 900 !important;
    }

    .menor-preco-box {
        font-weight: 900;
        color: #0f172a;
    }

    .origem-menor {
        display: block;
        font-size: 9px;
        color: #64748b;
        margin-top: 2px;
    }

    .mpc-empty {
        padding: 28px;
        text-align: center;
        color: #64748b;
    }

    .mpc-chip-list {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        padding: 12px 16px;
        background: #f8fafc;
        border-top: 1px solid #e5edf7;
    }

    .mpc-chip {
        padding: 7px 10px;
        border-radius: 999px;
        background: #e0f2fe;
        color: #075985;
        font-weight: 800;
        font-size: 10px;
    }

    .mpc-chip.var {
        background: #fef3c7;
        color: #92400e;
    }
</style>

<div class="mpc-grid">
    <div class="mpc-card">
        <small>Clientes ativos</small>
        <strong>{{ dados.resumo_mapa.total_clientes }}</strong>
    </div>

    <div class="mpc-card">
        <small>Cotações lançadas</small>
        <strong>{{ dados.resumo_mapa.total_cotacoes }}</strong>
    </div>

    <div class="mpc-card">
        <small>Itens mapeados</small>
        <strong>{{ dados.resumo_mapa.total_itens }}</strong>
    </div>

    <div class="mpc-card">
        <small>Faturamento estimado mensal</small>
        <strong>{{ dados.resumo_mapa.faturamento_estimado_formatado }}</strong>
    </div>
</div>

<div class="mpc-actions">
    <a class="mpc-btn" href="/mapa-precos-clientes">Mapa Consolidado</a>
    <a class="mpc-btn secondary" href="/mapa-precos-clientes/importar">Importar Cotação Cliente</a>
</div>

<div class="mpc-panel">
    <div class="mpc-panel-header">
        <h3>MEDBOX | Mapa de Comparação de Preços por Cliente</h3>
        <span>SKU agrupado, demanda mensal e comparação de menor preço</span>
    </div>

    <div class="mpc-table-wrap">
        <table class="mpc-table">
            <thead>
                <tr>
                    <th rowspan="2">Categoria</th>
                    <th rowspan="2">Descrição do Produto</th>
                    <th rowspan="2">SKU_MASTER</th>
                    <th rowspan="2">Demanda<br>mensal total</th>
                    <th colspan="6">Compra 2026 MedBox</th>
                    <th rowspan="2">Menor<br>preço</th>
                    <th rowspan="2">Preço médio<br>clientes</th>
                    <th rowspan="2">Faturamento<br>estimado</th>

                    {% for cliente in dados.clientes_colunas %}
                        <th class="mpc-client-head cliente-head-{{ loop.index0 }}" colspan="2">{{ cliente.nome }}</th>
                    {% endfor %}
                </tr>

                <tr>
                    <th>Preço compra</th>
                    <th>% Markup</th>
                    <th>Fornecedor</th>
                    <th>Fabricante</th>
                    <th>Preço MedBox</th>
                    <th>Status</th>

                    {% for cliente in dados.clientes_colunas %}
                        <th class="mpc-subhead cliente-head-{{ loop.index0 }}">Quant. mês</th>
                        <th class="mpc-subhead cliente-head-{{ loop.index0 }}">Valor unit.</th>
                    {% endfor %}
                </tr>
            </thead>

            <tbody>
                {% if dados.itens %}
                    {% for item in dados.itens %}
                        <tr data-grupo-key="{{ item.grupo_key }}" data-preco-compra="{{ item.preco_compra or 0 }}">
                            <td class="col-categoria">
                                <input class="mpc-input cat categoria-input" value="{{ item.categoria }}" data-grupo-key="{{ item.grupo_key }}">
                            </td>

                            <td class="col-descricao" title="{{ item.descricao }}">
                                {{ item.descricao }}
                            </td>

                            <td class="col-sku">
                                <input
                                    class="mpc-input sku sku-input"
                                    list="lista-skus-master"
                                    value="{{ item.sku_master }}"
                                    data-grupo-key="{{ item.grupo_key }}"
                                    placeholder="Buscar SKU Master..."
                                >
                            </td>

                            <td class="col-num">{{ item.demanda_mensal_total_formatada }}</td>

                            <td class="col-moeda preco-compra">{{ item.preco_compra_formatado }}</td>

                            <td class="col-num">
                                <input class="mpc-input markup markup-input" value="{{ item.markup_percentual|int }}" data-preco-compra="{{ item.preco_compra or 0 }}">
                            </td>

                            <td>{{ item.fornecedor }}</td>
                            <td>{{ item.fabricante }}</td>

                            <td class="col-moeda preco-medbox {% if item.medbox_menor %}medbox-menor{% endif %}">
                                {{ item.preco_medbox_formatado }}
                            </td>

                            <td class="col-num status-menor">
                                {% if item.medbox_menor %}
                                    MEDBOX MENOR
                                {% elif item.menor_preco_origem %}
                                    {{ item.menor_preco_origem }}
                                {% endif %}
                            </td>

                            <td class="col-moeda">
                                <span class="menor-preco-box">{{ item.menor_preco_geral_formatado }}</span>
                                <span class="origem-menor">{{ item.menor_preco_origem }}</span>
                            </td>

                            <td class="col-moeda">{{ item.preco_medio_formatado }}</td>
                            <td class="col-moeda">{{ item.faturamento_formatado }}</td>

                            {% for cliente in dados.clientes_colunas %}
                                {% set celula = item.clientes.get(cliente.nome, {}) if item.clientes is defined else {} %}
                                <td class="col-num cliente-bg-{{ loop.index0 }}">
                                    {{ celula.quantidade_mensal_formatada or "" }}
                                </td>
                                <td class="col-moeda cliente-bg-{{ loop.index0 }} {% if celula.menor_cliente %}menor-cliente{% endif %}">
                                    {{ celula.valor_unitario_formatado or "" }}
                                </td>
                            {% endfor %}
                        </tr>
                    {% endfor %}
                {% else %}
                    <tr>
                        <td colspan="{{ 13 + (dados.clientes_colunas|length * 2) }}">
                            <div class="mpc-empty">
                                Nenhum item importado ainda. Importe uma cotação de cliente para preencher o mapa.
                            </div>
                        </td>
                    </tr>
                {% endif %}
            </tbody>
        </table>
    </div>

    <div class="mpc-chip-list">
        {% for cliente in dados.clientes_colunas %}
            <span class="mpc-chip {% if not cliente.fixo %}var{% endif %}">
                {{ cliente.nome }}
            </span>
        {% endfor %}
    </div>
</div>

<datalist id="lista-skus-master"></datalist>

<script>
function moedaBR(valor) {
    const numero = Number(valor || 0);
    return numero.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
}

function numeroDeMoedaBR(texto) {
    if (!texto) return 0;
    return Number(String(texto).replace('R$', '').replace(/\./g, '').replace(',', '.').replace(/[^\d.-]/g, '')) || 0;
}

async function carregarSugestoesSku(termo) {
    if (!termo || termo.length < 2) return;

    try {
        const resp = await fetch('/sku-master/skus-json?q=' + encodeURIComponent(termo));
        const data = await resp.json();
        const lista = document.getElementById('lista-skus-master');
        lista.innerHTML = '';

        const itens = data.skus || data.sugestoes || data || [];

        itens.slice(0, 30).forEach(item => {
            const valor = typeof item === 'string' ? item : (item.sku || item.sku_master || item.nome || '');
            if (!valor) return;
            const opt = document.createElement('option');
            opt.value = valor;
            lista.appendChild(opt);
        });
    } catch (e) {
        console.warn('Erro ao buscar SKUs', e);
    }
}

async function salvarCampoMapa(input) {
    const tr = input.closest('tr');
    const grupoKey = input.dataset.grupoKey || tr.dataset.grupoKey;

    const skuInput = tr.querySelector('.sku-input');
    const catInput = tr.querySelector('.categoria-input');

    const payload = {
        grupo_key: grupoKey,
        sku_master: skuInput ? skuInput.value : '',
        categoria: catInput ? catInput.value : ''
    };

    try {
        const resp = await fetch('/mapa-precos-clientes/atualizar-item', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        const data = await resp.json();

        if (!data.ok) {
            alert(data.erro || 'Não foi possível salvar.');
            return;
        }

        input.style.borderColor = '#16a34a';
        input.style.boxShadow = '0 0 0 2px rgba(22,163,74,.15)';
        setTimeout(() => {
            input.style.borderColor = '';
            input.style.boxShadow = '';
        }, 900);

    } catch (e) {
        alert('Erro ao salvar alteração no mapa.');
    }
}

function recalcularMarkup(input) {
    const tr = input.closest('tr');
    const precoCompra = Number(input.dataset.precoCompra || tr.dataset.precoCompra || 0);
    const markup = Number(String(input.value).replace(',', '.') || 0);
    const precoMedbox = precoCompra * (1 + markup / 100);

    const celPreco = tr.querySelector('.preco-medbox');
    if (celPreco) {
        celPreco.textContent = precoMedbox > 0 ? moedaBR(precoMedbox) : '';
    }

    // Recalcula menor preço visual da linha
    let menorValor = precoMedbox > 0 ? precoMedbox : Infinity;
    let menorOrigem = precoMedbox > 0 ? 'MEDBOX' : '';

    tr.querySelectorAll('td').forEach(td => td.classList.remove('menor-cliente'));
    if (celPreco) celPreco.classList.remove('medbox-menor');

    const valorClientes = [];
    tr.querySelectorAll('td.col-moeda').forEach(td => {
        if (td.classList.contains('preco-medbox')) return;
        const texto = td.textContent || '';
        if (!texto.includes('R$')) return;

        const valor = numeroDeMoedaBR(texto);
        if (valor > 0) {
            valorClientes.push({ td, valor });
            if (valor < menorValor) {
                menorValor = valor;
                menorOrigem = 'CLIENTE';
            }
        }
    });

    if (menorValor < Infinity) {
        if (menorOrigem === 'MEDBOX') {
            if (celPreco) celPreco.classList.add('medbox-menor');
        } else {
            const alvo = valorClientes.find(x => x.valor === menorValor);
            if (alvo) alvo.td.classList.add('menor-cliente');
        }
    }
}

document.querySelectorAll('.sku-input').forEach(input => {
    input.addEventListener('input', () => carregarSugestoesSku(input.value));
    input.addEventListener('change', () => salvarCampoMapa(input));
    input.addEventListener('blur', () => salvarCampoMapa(input));
});

document.querySelectorAll('.categoria-input').forEach(input => {
    input.addEventListener('change', () => salvarCampoMapa(input));
    input.addEventListener('blur', () => salvarCampoMapa(input));
});

document.querySelectorAll('.markup-input').forEach(input => {
    input.addEventListener('input', () => recalcularMarkup(input));
});
</script>

{% endblock %}
''', encoding="utf-8")

print("OK: template mapa_precos_clientes.html reescrito com layout ERP.")
