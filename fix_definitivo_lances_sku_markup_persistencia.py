from pathlib import Path
from datetime import datetime

# ============================================================
# 1) FRONTEND - static/js/cotacao_lances.js
# ============================================================

js_path = Path("static/js/cotacao_lances.js")
js = js_path.read_text(encoding="utf-8", errors="ignore")

backup_js = js_path.with_suffix(js_path.suffix + ".bak_fix_persistencia_markup_" + datetime.now().strftime("%Y%m%d_%H%M%S"))
backup_js.write_text(js, encoding="utf-8")
print(f"Backup JS criado: {backup_js}")

js_fix = r'''

// ============================================================
// MEDBOX - FIX DEFINITIVO SKU / MARKUP / PREÇO MEDBOX / PERSISTÊNCIA
// Regras:
// - Não zera campos ao abrir a tela.
// - Recalcula somente a linha editada.
// - Fecha autocomplete após seleção.
// - Envia custo, markup, fornecedor e preço calculado ao backend.
// ============================================================
(function () {
    if (window.MEDBOX_FIX_SKU_MARKUP_PERSISTENCIA === true) {
        return;
    }
    window.MEDBOX_FIX_SKU_MARKUP_PERSISTENCIA = true;

    function parseBR(valor) {
        let txt = String(valor || "").trim();
        txt = txt.replace("R$", "")
                 .replace("%", "")
                 .replace(/\s+/g, "")
                 .replace(/[^\d,.\-]/g, "");

        if (!txt) return 0;

        if (txt.includes(",")) {
            txt = txt.replace(/\./g, "").replace(",", ".");
            const n = parseFloat(txt);
            return isNaN(n) ? 0 : n;
        }

        const n = parseFloat(txt);
        return isNaN(n) ? 0 : n;
    }

    function moedaBR(valor) {
        const n = Number(valor || 0);
        return "R$ " + n.toLocaleString("pt-BR", {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        });
    }

    function valorInput(row, seletor) {
        const el = row ? row.querySelector(seletor) : null;
        return el ? el.value : "";
    }

    function setValor(row, seletor, valor) {
        const el = row ? row.querySelector(seletor) : null;
        if (!el) return;
        el.value = valor;
        el.dispatchEvent(new Event("input", { bubbles: true }));
        el.dispatchEvent(new Event("change", { bubbles: true }));
    }

    function recalcularLinha(row) {
        if (!row) return;

        const custo = parseBR(valorInput(row, ".custo-manual-input"));
        const markup = parseBR(valorInput(row, ".markup-atual-input") || "80");

        const medbox = row.querySelector(".medbox-input");
        if (!medbox) return;

        // Só calcula se houver custo real. Não zera ao abrir tela.
        if (custo > 0) {
            const preco = custo * (1 + (markup / 100));
            medbox.value = moedaBR(preco);
            medbox.setAttribute("readonly", "readonly");
            medbox.dispatchEvent(new Event("input", { bubbles: true }));
            medbox.dispatchEvent(new Event("change", { bubbles: true }));
        }
    }

    function fecharAutocomplete() {
        const box = document.getElementById("medboxSkuAutocompleteBox") ||
                    document.getElementById("skuAutocompleteBoxFinal");

        if (box) {
            box.innerHTML = "";
            box.style.display = "none";
        }
    }

    function formatarCampoMoedaAoSair(campo) {
        if (!campo) return;
        const n = parseBR(campo.value);
        campo.value = moedaBR(n);
    }

    function formatarMarkupAoSair(campo) {
        if (!campo) return;
        const n = parseBR(campo.value || "0");
        campo.value = n.toLocaleString("pt-BR", {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        }) + "%";
    }

    function prepararCampoParaEdicao(campo) {
        if (!campo) return;

        if (
            campo.matches(".money-input") ||
            campo.matches(".custo-manual-input") ||
            campo.matches(".concorrente-input") ||
            campo.matches(".osinfo-input") ||
            campo.matches(".ultima-input")
        ) {
            const n = parseBR(campo.value);
            campo.value = n > 0 ? String(n).replace(".", ",") : "";
            setTimeout(function () {
                try { campo.select(); } catch (e) {}
            }, 20);
        }

        if (campo.matches(".markup-atual-input")) {
            const n = parseBR(campo.value || "80");
            campo.type = "text";
            campo.value = String(n).replace(".", ",");
            setTimeout(function () {
                try { campo.select(); } catch (e) {}
            }, 20);
        }
    }

    function itemDaLinha(row, idx) {
        const get = (sel) => {
            const el = row.querySelector(sel);
            return el ? el.value : "";
        };

        const descCell = row.children[1];
        const descricao = descCell ? (descCell.textContent || "").trim() : "";

        const custo = parseBR(get(".custo-manual-input"));
        const markup = parseBR(get(".markup-atual-input") || "80");
        let precoMedbox = parseBR(get(".medbox-input"));

        if (custo > 0) {
            precoMedbox = custo * (1 + (markup / 100));
        }

        return {
            item: idx + 1,
            descricao_produto: descricao,
            descricao: descricao,
            sku_master: get(".sku-master-input").trim(),
            categoria: get(".categoria-input").trim(),
            quantidade: parseBR(get(".qtd-input")),
            preco_osinfo: parseBR(get(".osinfo-input")),
            ultima_compra: parseBR(get(".ultima-input")),
            preco_medbox: precoMedbox,
            markup_atual: markup,
            menor_preco_ofertado: parseBR(get(".concorrente-input")),
            menor_lance: parseBR(get(".concorrente-input")),
            empresa_melhor_lance: get(".empresa-input").trim(),
            menor_custo_unitario: custo,
            fornecedor_menor_custo: get(".fornecedor-input").trim(),
            marca_fabricante: get(".fabricante-input").trim(),
            marca: get(".fabricante-input").trim()
        };
    }

    function coletarItensDefinitivo() {
        const rows = Array.from(document.querySelectorAll("#tabelaLances tbody tr"));
        const itens = [];

        rows.forEach(function (row, idx) {
            recalcularLinha(row);

            const item = itemDaLinha(row, idx);
            if (item.descricao_produto) {
                itens.push(item);
            }
        });

        console.log("MEDBOX coleta definitiva primeiro item:", itens[0]);
        return itens;
    }

    function instalarEventosFix() {
        document.addEventListener("mousedown", function (event) {
            const box = document.getElementById("medboxSkuAutocompleteBox") ||
                        document.getElementById("skuAutocompleteBoxFinal");

            if (box && box.contains(event.target)) {
                const row = event.target.closest("tr") || document.activeElement?.closest("tr");
                setTimeout(function () {
                    fecharAutocomplete();

                    const ativo = document.activeElement;
                    const linha = row || ativo?.closest("tr");

                    if (linha) {
                        recalcularLinha(linha);
                    }
                }, 150);
            }
        }, true);

        document.addEventListener("change", function (event) {
            const campo = event.target;
            if (!campo || !campo.closest) return;

            const row = campo.closest("tr");

            if (
                campo.matches(".sku-master-input") ||
                campo.matches(".custo-manual-input") ||
                campo.matches(".markup-atual-input")
            ) {
                setTimeout(function () {
                    fecharAutocomplete();
                    recalcularLinha(row);
                }, 150);
            }
        }, true);

        document.addEventListener("input", function (event) {
            const campo = event.target;
            if (!campo || !campo.closest) return;

            if (
                campo.matches(".custo-manual-input") ||
                campo.matches(".markup-atual-input")
            ) {
                recalcularLinha(campo.closest("tr"));
            }
        }, true);

        document.addEventListener("focusin", function (event) {
            prepararCampoParaEdicao(event.target);
        }, true);

        document.addEventListener("focusout", function (event) {
            const campo = event.target;
            if (!campo || !campo.closest) return;

            const row = campo.closest("tr");

            if (
                campo.matches(".money-input") ||
                campo.matches(".custo-manual-input") ||
                campo.matches(".concorrente-input") ||
                campo.matches(".osinfo-input") ||
                campo.matches(".ultima-input")
            ) {
                formatarCampoMoedaAoSair(campo);
            }

            if (campo.matches(".markup-atual-input")) {
                formatarMarkupAoSair(campo);
            }

            if (
                campo.matches(".custo-manual-input") ||
                campo.matches(".markup-atual-input")
            ) {
                recalcularLinha(row);
            }
        }, true);
    }

    instalarEventosFix();

    window.coletarItensParaCotacaoGerada = coletarItensDefinitivo;
    window.coletarItensEdicaoOAS = coletarItensDefinitivo;
    window.MEDBOX_coletarItensDefinitivo = coletarItensDefinitivo;
    window.MEDBOX_recalcularLinhaLance = recalcularLinha;

    console.log("MEDBOX fix definitivo SKU/markup/persistência ativo.");
})();
'''

if "MEDBOX - FIX DEFINITIVO SKU / MARKUP / PREÇO MEDBOX / PERSISTÊNCIA" not in js:
    js = js.rstrip() + "\n\n" + js_fix + "\n"
else:
    print("Fix JS já existia. Não dupliquei.")

js_path.write_text(js, encoding="utf-8")
print("OK: JS corrigido.")


# ============================================================
# 2) BACKEND - app.py
# ============================================================

app_path = Path("app.py")
app = app_path.read_text(encoding="utf-8", errors="ignore")

backup_app = app_path.with_suffix(app_path.suffix + ".bak_fix_persistencia_lances_" + datetime.now().strftime("%Y%m%d_%H%M%S"))
backup_app.write_text(app, encoding="utf-8")
print(f"Backup APP criado: {backup_app}")

backend_fix = r'''

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
        "ultima_compra_formatada": _fix_lance_moeda(0),
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
            "itens_negociar": 0,
            "total_medbox": 0,
            "total_medbox_formatado": "R$ 0,00",
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
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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

'''

if "MEDBOX - FIX DEFINITIVO PERSISTÊNCIA LANCES / SKU / MARKUP" not in app:
    marcador = 'if __name__ == "__main__":'
    if marcador in app:
        app = app.replace(marcador, backend_fix + "\n\n" + marcador, 1)
    else:
        app = app.rstrip() + "\n\n" + backend_fix + "\n"
else:
    print("Fix backend já existia. Não dupliquei.")

app_path.write_text(app, encoding="utf-8")
print("OK: backend corrigido.")
