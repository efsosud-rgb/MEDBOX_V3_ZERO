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
        backup = path.with_suffix(path.suffix + ".bak_mapa_precos_v4_" + datetime.now().strftime("%Y%m%d_%H%M%S"))
        backup.write_text(path.read_text(encoding="utf-8", errors="ignore"), encoding="utf-8")
        print(f"Backup criado: {backup}")

# ============================================================
# 1) Atualiza core/mapa_precos_clientes.py
# ============================================================

core_path = Path("core/mapa_precos_clientes.py")
core_txt = core_path.read_text(encoding="utf-8", errors="ignore")

append_core = r'''

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

            categoria_final = normalizar_texto_mapa(
                row.get("categoria_produto")
                or row.get("categoria")
                or ""
            )

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
'''

if "FASE 4 - EDIÇÃO COMPLETA DO MAPA" not in core_txt:
    core_txt = core_txt + append_core
    core_path.write_text(core_txt, encoding="utf-8")
    print("OK: Fase 4 adicionada ao core/mapa_precos_clientes.py")
else:
    print("AVISO: Fase 4 já existia no core")

# ============================================================
# 2) Atualiza app.py com endpoint valor unitário
# ============================================================

app_path = Path("app.py")
app_txt = app_path.read_text(encoding="utf-8", errors="ignore")

rota_valor = r'''

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
'''

if "def mapa_precos_clientes_atualizar_valor_cliente()" not in app_txt:
    marcador = '@app.route("/importacoes")'
    if marcador not in app_txt:
        raise SystemExit("ERRO: marcador de /importacoes não encontrado no app.py.")
    app_txt = app_txt.replace(marcador, rota_valor + "\n\n" + marcador)
    app_path.write_text(app_txt, encoding="utf-8")
    print("OK: endpoint atualizar valor do cliente adicionado ao app.py")
else:
    print("AVISO: endpoint atualizar valor cliente já existia")

# ============================================================
# 3) Ajusta template
# ============================================================

tpl_path = Path("templates/mapa_precos_clientes.html")
tpl_txt = tpl_path.read_text(encoding="utf-8", errors="ignore")

# Categoria input -> select
tpl_txt = tpl_txt.replace(
'''<input class="mpc-input cat categoria-input" value="{{ item.categoria }}" data-grupo-key="{{ item.grupo_key }}">''',
'''<select class="mpc-input cat categoria-input" data-grupo-key="{{ item.grupo_key }}">
                                    <option value="">REVISAR</option>
                                    <option value="MEDICAMENTOS" {% if item.categoria == "MEDICAMENTOS" %}selected{% endif %}>MEDICAMENTOS</option>
                                    <option value="CORRELATOS" {% if item.categoria == "CORRELATOS" %}selected{% endif %}>CORRELATOS</option>
                                </select>'''
)

# Valor unitário cliente passa a ser input editável
tpl_txt = tpl_txt.replace(
'''<td class="col-moeda cliente-bg-{{ loop.index0 }} {% if celula.menor_cliente %}menor-cliente{% endif %}">
                                    {{ celula.valor_unitario_formatado or "" }}
                                </td>''',
'''<td class="col-moeda cliente-bg-{{ loop.index0 }} {% if celula.menor_cliente %}menor-cliente{% endif %}">
                                    {% if celula.cliente_id %}
                                        <input
                                            class="mpc-input valor-cliente-input {% if celula.menor_cliente %}menor-cliente{% endif %}"
                                            value="{{ celula.valor_unitario_formatado or '' }}"
                                            data-grupo-key="{{ item.grupo_key }}"
                                            data-cliente-id="{{ celula.cliente_id }}"
                                            placeholder="R$ 0,00"
                                        >
                                    {% endif %}
                                </td>'''
)

# Se salvar SKU, recarrega para buscar preço fornecedor/fabricante e reagrupar
tpl_txt = tpl_txt.replace(
'''        input.style.borderColor = '#16a34a';
        input.style.boxShadow = '0 0 0 2px rgba(22,163,74,.15)';
        setTimeout(() => {
            input.style.borderColor = '';
            input.style.boxShadow = '';
        }, 900);''',
'''        input.style.borderColor = '#16a34a';
        input.style.boxShadow = '0 0 0 2px rgba(22,163,74,.15)';

        if (input.classList.contains('sku-input')) {
            setTimeout(() => window.location.reload(), 500);
            return;
        }

        setTimeout(() => {
            input.style.borderColor = '';
            input.style.boxShadow = '';
        }, 900);'''
)

# Substitui função recalcularMarkup por versão correta
inicio = tpl_txt.find("function recalcularMarkup(input) {")
fim = tpl_txt.find("document.querySelectorAll('.sku-input')", inicio)

if inicio != -1 and fim != -1:
    nova_funcao = r'''function recalcularLinhaMenorPreco(tr) {
    const precoMedboxCel = tr.querySelector('.preco-medbox');
    const menorBox = tr.querySelector('.menor-preco-box');
    const origemBox = tr.querySelector('.origem-menor');
    const statusBox = tr.querySelector('.status-menor');

    let precoMedbox = numeroDeMoedaBR(precoMedboxCel ? precoMedboxCel.textContent : '');
    let menorValor = precoMedbox > 0 ? precoMedbox : Infinity;
    let menorOrigem = precoMedbox > 0 ? 'MEDBOX' : '';

    if (precoMedboxCel) precoMedboxCel.classList.remove('medbox-menor');

    tr.querySelectorAll('.valor-cliente-input').forEach(input => {
        input.classList.remove('menor-cliente');

        const valor = numeroDeMoedaBR(input.value);
        if (valor > 0 && valor < menorValor) {
            menorValor = valor;
            menorOrigem = input.closest('td').dataset.clienteNome || 'CLIENTE';
        }
    });

    if (menorValor === Infinity) {
        if (menorBox) menorBox.textContent = '';
        if (origemBox) origemBox.textContent = '';
        if (statusBox) statusBox.textContent = '';
        return;
    }

    if (menorBox) menorBox.textContent = moedaBR(menorValor);
    if (origemBox) origemBox.textContent = menorOrigem;
    if (statusBox) statusBox.textContent = menorOrigem === 'MEDBOX' ? 'MEDBOX MENOR' : menorOrigem;

    if (menorOrigem === 'MEDBOX') {
        if (precoMedboxCel) precoMedboxCel.classList.add('medbox-menor');
    } else {
        tr.querySelectorAll('.valor-cliente-input').forEach(input => {
            const valor = numeroDeMoedaBR(input.value);
            if (valor > 0 && valor === menorValor) {
                input.classList.add('menor-cliente');
            }
        });
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

    recalcularLinhaMenorPreco(tr);
}

async function salvarValorCliente(input) {
    const payload = {
        grupo_key: input.dataset.grupoKey,
        cliente_id: input.dataset.clienteId,
        valor_unitario: input.value
    };

    try {
        const resp = await fetch('/mapa-precos-clientes/atualizar-valor-cliente', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        const data = await resp.json();

        if (!data.ok) {
            alert(data.erro || 'Não foi possível salvar o valor unitário.');
            return;
        }

        input.value = data.valor_unitario_formatado || '';
        input.style.borderColor = '#16a34a';
        input.style.boxShadow = '0 0 0 2px rgba(22,163,74,.15)';
        recalcularLinhaMenorPreco(input.closest('tr'));

        setTimeout(() => {
            input.style.borderColor = '';
            input.style.boxShadow = '';
        }, 900);

    } catch (e) {
        alert('Erro ao salvar valor unitário do cliente.');
    }
}

'''
    tpl_txt = tpl_txt[:inicio] + nova_funcao + tpl_txt[fim:]
    print("OK: JS de markup/menor preço substituído")
else:
    print("AVISO: função recalcularMarkup não encontrada para substituição")

# adiciona listeners valor cliente
tpl_txt = tpl_txt.replace(
'''document.querySelectorAll('.markup-input').forEach(input => {
    input.addEventListener('input', () => recalcularMarkup(input));
});''',
'''document.querySelectorAll('.markup-input').forEach(input => {
    input.addEventListener('input', () => recalcularMarkup(input));
});

document.querySelectorAll('.valor-cliente-input').forEach(input => {
    input.addEventListener('change', () => salvarValorCliente(input));
    input.addEventListener('blur', () => {
        if (input.value && !String(input.value).includes('R$')) {
            const valor = numeroDeMoedaBR(input.value);
            input.value = valor > 0 ? moedaBR(valor) : '';
        }
    });
});'''
)

tpl_path.write_text(tpl_txt, encoding="utf-8")
print("OK: template atualizado para V4")

print("\nOK: Patch V4 aplicado.")
