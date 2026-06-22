// ============================================================
// MEDBOX - Cotação Lances
// Arquivo extraído de templates/cotacao_lances.html
// Objetivo: centralizar JS sem alterar regra de negócio.
// ============================================================

/* ============================================================
   MEDBOX FINAL - LANCES / OAS / EDIÇÃO DE COTAÇÃO
   Único script ativo para gerar e salvar cotação OAS.
   ============================================================ */
(function () {
    const NUMERO_EDITANDO = window.MEDBOX_NUMERO_COTACAO_EDITANDO || "";

    function norm(txt) {
        return String(txt || "")
            .replace(/þ/g, "c")
            .replace(/Þ/g, "C")
            .replace(/ç/g, "c")
            .replace(/Ç/g, "C")
            .toUpperCase()
            .normalize("NFD")
            .replace(/[\u0300-\u036f]/g, "")
            .replace(/\s+/g, " ")
            .trim();
    }

    function parseValor(valor) {
        let txt = String(valor || "").trim();

        txt = txt.replace("R$", "").replace("%", "").trim();
        txt = txt.replace(/[^\d,.\-]/g, "");

        if (!txt) return 0;

        // Decimal com ponto vindo de input: 90.0, 9000.0, 2.41
        if (/^-?\d+\.\d+$/.test(txt) && !txt.includes(",")) {
            const n = parseFloat(txt);
            return isNaN(n) ? 0 : n;
        }

        // Formato BR: 2,10 ou 1.234,56
        if (txt.includes(",")) {
            txt = txt.replace(/\./g, "").replace(",", ".");
            const n = parseFloat(txt);
            return isNaN(n) ? 0 : n;
        }

        const n = parseFloat(txt);
        return isNaN(n) ? 0 : n;
    }

    function valorCelula(td) {
        if (!td) return "";

        const campo = td.querySelector("input, textarea, select");

        if (campo) {
            return campo.value || campo.getAttribute("value") || "";
        }

        return td.textContent || "";
    }

    function acharTabelaLances() {
        return Array.from(document.querySelectorAll("table")).find(function (table) {
            const headers = norm(
                Array.from(table.querySelectorAll("thead th"))
                    .map(th => th.textContent)
                    .join(" | ")
            );

            return headers.includes("DESCRICAO DO PRODUTO") &&
                   headers.includes("SKU MASTER") &&
                   headers.includes("PRECO OSINFO") &&
                   headers.includes("PRECO MEDBOX") &&
                   headers.includes("MENOR PRECO OFERTADO");
        });
    }

    function mapaColunas(table) {
        const mapa = {};

        Array.from(table.querySelectorAll("thead th")).forEach(function (th, idx) {
            const h = norm(th.textContent);

            if (h.includes("DESCRICAO DO PRODUTO")) mapa.descricao = idx;
            if (h.includes("SKU MASTER")) mapa.sku = idx;
            if (h.includes("CATEGORIA")) mapa.categoria = idx;
            if (h.includes("QUANTIDADE")) mapa.quantidade = idx;
            if (h.includes("PRECO OSINFO")) mapa.osinfo = idx;
            if (h.includes("ULT COMPRA")) mapa.ultima_compra = idx;
            if (h.includes("PRECO MEDBOX")) mapa.medbox = idx;
            if (h.includes("MARKUP")) mapa.markup = idx;
            if (h.includes("MENOR PRECO OFERTADO")) mapa.outra_valor = idx;
            if (h.includes("EMPRESA MELHOR LANCE")) mapa.outra_empresa = idx;
            if (h.includes("MENOR VALOR") || h.includes("VENCEDOR")) mapa.menor_valor = idx;
            if (h.includes("MENOR CUSTO ENCONTRADO")) mapa.menor_custo = idx;
            if (h.includes("FORNECEDOR MENOR CUSTO")) mapa.fornecedor = idx;
            if (h.includes("MARCA") || h.includes("FABRICANTE")) mapa.marca = idx;
            if (h.includes("STATUS")) mapa.status = idx;
        });

        return mapa;
    }

    function td(row, idx) {
        if (idx === undefined || idx === null) return null;
        return Array.from(row.children || [])[idx] || null;
    }

    function texto(row, mapa, chave) {
        return String(valorCelula(td(row, mapa[chave])) || "").trim();
    }

    function numero(row, mapa, chave) {
        return parseValor(valorCelula(td(row, mapa[chave])));
    }

    function coletarItensLances() {
        const table = acharTabelaLances();

        if (!table) {
            alert("Não encontrei a Grade de Lances correta.");
            return [];
        }

        const mapa = mapaColunas(table);
        const itens = [];

        Array.from(table.querySelectorAll("tbody tr")).forEach(function (row, idx) {
            const descricao = texto(row, mapa, "descricao");

            if (!descricao) return;

            itens.push({
                item: idx + 1,
                descricao_produto: descricao,
                descricao: descricao,
                sku_master: texto(row, mapa, "sku"),
                categoria: texto(row, mapa, "categoria"),
                marca_fabricante: texto(row, mapa, "marca"),
                marca: texto(row, mapa, "marca"),
                fornecedor_menor_custo: texto(row, mapa, "fornecedor"),
                status: texto(row, mapa, "status"),

                quantidade: numero(row, mapa, "quantidade"),
                preco_osinfo: numero(row, mapa, "osinfo"),
                preco_medbox: numero(row, mapa, "medbox"),
                menor_preco_ofertado: numero(row, mapa, "outra_valor"),
                menor_lance: numero(row, mapa, "outra_valor"),
                empresa_melhor_lance: texto(row, mapa, "outra_empresa"),
                menor_valor: numero(row, mapa, "menor_valor"),
                menor_custo_unitario: numero(row, mapa, "menor_custo")
            });
        });

        console.log("MEDBOX FINAL - PRIMEIRO ITEM:", itens[0]);
        console.log("MEDBOX FINAL - TOTAL ITENS:", itens.length);

        return itens;
    }

    function confirmarPrimeiroItem(itens, acao) {
        const p = itens[0] || {};

        return confirm(
            "CONFIRA ANTES DE " + acao + ":\n\n" +
            "Descrição: " + (p.descricao_produto || "") + "\n" +
            "Quantidade: " + p.quantidade + "\n" +
            "Preço OSINFO: " + p.preco_osinfo + "\n" +
            "Preço MedBox: " + p.preco_medbox + "\n" +
            "Preço Empresa Melhor Lance: " + p.menor_lance + "\n" +
            "Empresa Melhor Lance: " + p.empresa_melhor_lance + "\n\n" +
            "Clique OK se estiver correto."
        );
    }

    async function gerarCotacao(event) {
        event.preventDefault();
        event.stopPropagation();
        event.stopImmediatePropagation();

        const itens = coletarItensLances();

        if (!itens.length) {
            alert("Nenhum item encontrado para gerar a cotação.");
            return false;
        }

        if (!confirmarPrimeiroItem(itens, "GERAR")) return false;

        const cliente = (document.getElementById("clienteCotacaoGerada") || {}).value || "";
        const oas = (document.getElementById("oasCotacaoGerada") || {}).value || "";
        const projeto = (document.getElementById("projetoCotacaoGerada") || {}).value || "";
        const controle = (document.getElementById("controleClienteCotacaoGerada") || {}).value || "";

        const resp = await fetch("/cotacoes/lances/gerar-cotacao", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({
                cliente: cliente,
                cliente_orgao: cliente,
                oas: oas,
                projeto: projeto,
                controle_cliente: controle,
                itens: itens
            })
        });

        const data = await resp.json();

        if (!data.ok) {
            alert(data.erro || "Erro ao gerar cotação.");
            return false;
        }

        window.location.href = data.url;
        return false;
    }

    async function salvarAlteracoes(event) {
        event.preventDefault();
        event.stopPropagation();
        event.stopImmediatePropagation();

        const itens = coletarItensLances();

        if (!itens.length) {
            alert("Nenhum item encontrado para salvar.");
            return false;
        }

        if (!confirmarPrimeiroItem(itens, "SALVAR")) return false;

        const cliente = (document.getElementById("clienteCotacaoGerada") || {}).value || "";
        const oas = (document.getElementById("oasCotacaoGerada") || {}).value || "";
        const projeto = (document.getElementById("projetoCotacaoGerada") || {}).value || "";
        const controle = (document.getElementById("controleClienteCotacaoGerada") || {}).value || "";

        const resp = await fetch("/cotacoes/lances/atualizar-cotacao/" + NUMERO_EDITANDO, {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({
                cliente: cliente,
                cliente_orgao: cliente,
                oas: oas,
                projeto: projeto,
                controle_cliente: controle,
                itens: itens
            })
        });

        const data = await resp.json();

        if (!data.ok) {
            alert(data.erro || "Erro ao salvar alterações.");
            return false;
        }

        alert("Cotação " + NUMERO_EDITANDO + " salva com sucesso.");
        window.location.href = data.url;
        return false;
    }

    function instalarBotoes() {
        const btnGerar = document.getElementById("btnGerarCotacaoMedbox");

        if (btnGerar && btnGerar.dataset.medboxFinalOk !== "1") {
            const clone = btnGerar.cloneNode(true);
            clone.dataset.medboxFinalOk = "1";
            clone.type = "button";
            clone.addEventListener("click", gerarCotacao, true);
            btnGerar.parentNode.replaceChild(clone, btnGerar);
        }

        if (NUMERO_EDITANDO) {
            let btnSalvar = Array.from(document.querySelectorAll("button, a")).find(function (el) {
                return norm(el.textContent).includes("SALVAR ALTERACOES");
            });

            if (!btnSalvar) {
                btnSalvar = document.createElement("button");
                btnSalvar.type = "button";
                btnSalvar.textContent = "Salvar Alterações da Cotação";
                btnSalvar.style.background = "#ff9f1c";
                btnSalvar.style.color = "#fff";
                btnSalvar.style.border = "none";
                btnSalvar.style.borderRadius = "8px";
                btnSalvar.style.padding = "12px 18px";
                btnSalvar.style.fontWeight = "900";
                btnSalvar.style.cursor = "pointer";
                btnSalvar.style.margin = "10px 8px";

                const tabela = acharTabelaLances();
                if (tabela && tabela.parentElement) {
                    tabela.parentElement.insertBefore(btnSalvar, tabela);
                } else {
                    document.body.prepend(btnSalvar);
                }
            }

            if (btnSalvar.dataset.medboxFinalSalvarOk !== "1") {
                const cloneSalvar = btnSalvar.cloneNode(true);
                cloneSalvar.dataset.medboxFinalSalvarOk = "1";
                cloneSalvar.type = "button";
                cloneSalvar.addEventListener("click", salvarAlteracoes, true);
                btnSalvar.parentNode.replaceChild(cloneSalvar, btnSalvar);
            }
        }
    }

    document.addEventListener("DOMContentLoaded", instalarBotoes);
    window.addEventListener("load", instalarBotoes);
    setTimeout(instalarBotoes, 300);
    setTimeout(instalarBotoes, 1000);

    window.coletarItensParaCotacaoGerada = coletarItensLances;
    window.coletarItensEdicaoOAS = coletarItensLances;
    window.gerarCotacaoMedbox = gerarCotacao;

    console.log("MEDBOX FINAL - SCRIPT ÚNICO DE LANCES CARREGADO");
})();

/* ============================================================
   CORREÇÃO VISUAL DE QUANTIDADE
   - remove .0
   - corrige cotação reaberta salva x10
   ============================================================ */
(function () {
    function norm(txt) {
        return String(txt || "")
            .replace(/þ/g, "c")
            .replace(/Þ/g, "C")
            .replace(/ç/g, "c")
            .replace(/Ç/g, "C")
            .toUpperCase()
            .normalize("NFD")
            .replace(/[\u0300-\u036f]/g, "")
            .replace(/\s+/g, " ")
            .trim();
    }

    function parseNumero(valor) {
        let txt = String(valor || "").trim();
        txt = txt.replace("R$", "").replace("%", "").trim();
        txt = txt.replace(/[^\d,.\-]/g, "");

        if (!txt) return 0;

        if (txt.includes(",")) {
            txt = txt.replace(/\./g, "").replace(",", ".");
        }

        const n = parseFloat(txt);
        return isNaN(n) ? 0 : n;
    }

    function formatarQtd(qtd) {
        qtd = Number(qtd || 0);

        if (Number.isInteger(qtd)) {
            return String(qtd);
        }

        return String(qtd).replace(".", ",");
    }

    function acharTabelaLances() {
        return Array.from(document.querySelectorAll("table")).find(function (table) {
            const headers = norm(
                Array.from(table.querySelectorAll("thead th"))
                    .map(th => th.textContent)
                    .join(" | ")
            );

            return headers.includes("DESCRICAO DO PRODUTO") &&
                   headers.includes("QUANTIDADE") &&
                   headers.includes("PRECO OSINFO");
        });
    }

    function indiceQuantidade(table) {
        const ths = Array.from(table.querySelectorAll("thead th"));

        for (let i = 0; i < ths.length; i++) {
            if (norm(ths[i].textContent).includes("QUANTIDADE")) {
                return i;
            }
        }

        return null;
    }

    function corrigirQuantidadeVisual() {
        const table = acharTabelaLances();
        if (!table) return;

        const idx = indiceQuantidade(table);
        if (idx === null) return;

        Array.from(table.querySelectorAll("tbody tr")).forEach(function (row) {
            const td = Array.from(row.children || [])[idx];
            if (!td) return;

            const input = td.querySelector("input, textarea");
            if (!input) return;

            let qtd = parseNumero(input.value);

            // Corrige bug da cotação reaberta:
            // 900 -> 90, 10000 -> 1000, 20000 -> 2000.
            if (qtd >= 100 && qtd % 10 === 0) {
                qtd = qtd / 10;
            }

            input.value = formatarQtd(qtd);
        });
    }

    document.addEventListener("DOMContentLoaded", corrigirQuantidadeVisual);
    window.addEventListener("load", corrigirQuantidadeVisual);
    setTimeout(corrigirQuantidadeVisual, 300);
    setTimeout(corrigirQuantidadeVisual, 1000);
})();



// ============================================================
// MEDBOX - AUTOCOMPLETE SKU_MASTER
// Usa rota existente: /cotacoes/lances/sugerir-skus?q=
// Não altera gerar cotação, salvar cotação, quantidade ou layout.
// ============================================================
(function () {
    if (window.MEDBOX_AUTOCOMPLETE_SKU_ATIVO === true) {
        return;
    }
    window.MEDBOX_AUTOCOMPLETE_SKU_ATIVO = true;

    let caixaSugestoes = null;
    let inputAtual = null;
    let timerBusca = null;

    function criarCaixaSugestoes() {
        if (caixaSugestoes) {
            return caixaSugestoes;
        }

        caixaSugestoes = document.createElement("div");
        caixaSugestoes.id = "medboxSkuAutocompleteBox";
        caixaSugestoes.style.position = "absolute";
        caixaSugestoes.style.zIndex = "99999";
        caixaSugestoes.style.background = "#ffffff";
        caixaSugestoes.style.border = "1px solid #c8d7ea";
        caixaSugestoes.style.borderRadius = "8px";
        caixaSugestoes.style.boxShadow = "0 8px 24px rgba(15, 23, 42, 0.18)";
        caixaSugestoes.style.maxHeight = "280px";
        caixaSugestoes.style.overflowY = "auto";
        caixaSugestoes.style.minWidth = "420px";
        caixaSugestoes.style.display = "none";
        caixaSugestoes.style.fontSize = "12px";

        document.body.appendChild(caixaSugestoes);
        return caixaSugestoes;
    }

    function esconderSugestoes() {
        if (!caixaSugestoes) return;
        caixaSugestoes.innerHTML = "";
        caixaSugestoes.style.display = "none";
    }

    function posicionarCaixa(input) {
        const caixa = criarCaixaSugestoes();
        const r = input.getBoundingClientRect();

        caixa.style.left = (window.scrollX + r.left) + "px";
        caixa.style.top = (window.scrollY + r.bottom + 4) + "px";
        caixa.style.width = Math.max(r.width, 420) + "px";
    }

    function obterLinha(input) {
        return input.closest("tr");
    }

    function obterDescricaoDaLinha(input) {
        const row = obterLinha(input);
        if (!row) return "";

        const descricaoCell = row.children[1];
        if (!descricaoCell) return "";

        return (descricaoCell.textContent || "").trim();
    }

    function termoParaBusca(input) {
        const digitado = String(input.value || "").trim();

        if (digitado.length >= 2) {
            return digitado;
        }

        return obterDescricaoDaLinha(input);
    }

    function setInput(row, seletor, valor) {
        const input = row.querySelector(seletor);
        if (!input) return;

        input.value = valor || "";
        input.dispatchEvent(new Event("input", { bubbles: true }));
        input.dispatchEvent(new Event("change", { bubbles: true }));
    }

    function moeda(valor) {
        if (valor === null || valor === undefined || valor === "") return "";

        const n = Number(valor);

        if (isNaN(n)) return String(valor);

        return "R$ " + n.toFixed(2).replace(".", ",");
    }

    function aplicarSugestao(input, sugestao) {
        const row = obterLinha(input);
        if (!row) return;

        const sku =
            sugestao.sku_master ||
            sugestao.sku ||
            sugestao.produto_padrao ||
            sugestao.nome ||
            "";

        const categoria = sugestao.categoria || "";
        const fabricante = sugestao.marca_fabricante || sugestao.fabricante || sugestao.marca || "";
        const fornecedor = sugestao.fornecedor_menor_custo || sugestao.fornecedor || "";
        const custo = sugestao.menor_custo_unitario || sugestao.menor_custo || sugestao.preco || "";

        input.value = sku;
        input.dispatchEvent(new Event("input", { bubbles: true }));
        input.dispatchEvent(new Event("change", { bubbles: true }));

        setInput(row, ".categoria-input", categoria);
        setInput(row, ".fabricante-input", fabricante);
        setInput(row, ".fornecedor-input", fornecedor);

        if (custo) {
            setInput(row, ".custo-manual-input", moeda(custo));
        }

        const status = row.querySelector(".status-cell");
        if (status) {
            status.innerHTML = '<span class="status-badge status-ok">SKU SELECIONADO</span>';
        }

        esconderSugestoes();
    }

    function renderizarSugestoes(input, sugestoes) {
        const caixa = criarCaixaSugestoes();
        posicionarCaixa(input);

        caixa.innerHTML = "";

        if (!Array.isArray(sugestoes) || sugestoes.length === 0) {
            const vazio = document.createElement("div");
            vazio.textContent = "Nenhuma sugestão encontrada";
            vazio.style.padding = "10px 12px";
            vazio.style.color = "#667085";
            caixa.appendChild(vazio);
            caixa.style.display = "block";
            return;
        }

        sugestoes.slice(0, 12).forEach(function (sugestao) {
            const sku =
                sugestao.sku_master ||
                sugestao.sku ||
                sugestao.produto_padrao ||
                sugestao.nome ||
                "";

            const fabricante = sugestao.marca_fabricante || sugestao.fabricante || sugestao.marca || "";
            const categoria = sugestao.categoria || "";
            const fornecedor = sugestao.fornecedor_menor_custo || sugestao.fornecedor || "";
            const custo = sugestao.menor_custo_unitario || sugestao.menor_custo || sugestao.preco || "";
            const score = sugestao.score !== undefined ? sugestao.score : "";

            const item = document.createElement("div");
            item.style.padding = "9px 12px";
            item.style.cursor = "pointer";
            item.style.borderBottom = "1px solid #edf2f7";

            item.innerHTML =
                '<div style="font-weight:900;color:#003b5c;">' + sku + '</div>' +
                '<div style="font-size:11px;color:#667085;margin-top:2px;">' +
                (categoria ? 'Categoria: ' + categoria + ' | ' : '') +
                (fabricante ? 'Marca: ' + fabricante + ' | ' : '') +
                (fornecedor ? 'Fornecedor: ' + fornecedor + ' | ' : '') +
                (custo ? 'Custo: ' + moeda(custo) + ' | ' : '') +
                (score !== "" ? 'Score: ' + score : '') +
                '</div>';

            item.addEventListener("mousedown", function (event) {
                event.preventDefault();
                aplicarSugestao(input, sugestao);
            });

            item.addEventListener("mouseenter", function () {
                item.style.background = "#eaf3ff";
            });

            item.addEventListener("mouseleave", function () {
                item.style.background = "#ffffff";
            });

            caixa.appendChild(item);
        });

        caixa.style.display = "block";
    }

    async function buscarSugestoes(input) {
        inputAtual = input;

        const termo = termoParaBusca(input);

        if (!termo || termo.length < 2) {
            esconderSugestoes();
            return;
        }

        try {
            const resp = await fetch("/cotacoes/lances/sugerir-skus?q=" + encodeURIComponent(termo));
            const data = await resp.json();

            if (!data.ok) {
                renderizarSugestoes(input, []);
                return;
            }

            renderizarSugestoes(input, data.sugestoes || []);
        } catch (erro) {
            console.error("Erro no autocomplete SKU_MASTER:", erro);
            esconderSugestoes();
        }
    }

    function ehCampoSkuMaster(el) {
        return el &&
               el.classList &&
               el.classList.contains("sku-master-input");
    }

    document.addEventListener("focusin", function (event) {
        const input = event.target;

        if (!ehCampoSkuMaster(input)) return;

        clearTimeout(timerBusca);
        timerBusca = setTimeout(function () {
            buscarSugestoes(input);
        }, 150);
    });

    document.addEventListener("input", function (event) {
        const input = event.target;

        if (!ehCampoSkuMaster(input)) return;

        clearTimeout(timerBusca);
        timerBusca = setTimeout(function () {
            buscarSugestoes(input);
        }, 250);
    });

    document.addEventListener("keydown", function (event) {
        if (event.key === "Escape") {
            esconderSugestoes();
        }
    });

    document.addEventListener("click", function (event) {
        if (!caixaSugestoes) return;

        if (event.target === inputAtual || caixaSugestoes.contains(event.target)) {
            return;
        }

        esconderSugestoes();
    });

    window.addEventListener("scroll", function () {
        if (inputAtual && caixaSugestoes && caixaSugestoes.style.display !== "none") {
            posicionarCaixa(inputAtual);
        }
    }, true);

    window.addEventListener("resize", function () {
        if (inputAtual && caixaSugestoes && caixaSugestoes.style.display !== "none") {
            posicionarCaixa(inputAtual);
        }
    });

    console.log("MEDBOX autocomplete SKU_MASTER ativo.");
})();



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



// ============================================================
// MEDBOX - SALVAMENTO AUTORITATIVO DA GRADE DE LANCES
// Corrige envio de Últ. Compra da Cotação e demais campos.
// Não altera layout, não zera campos ao abrir.
// ============================================================
(function () {
    if (window.MEDBOX_SALVAR_LANCES_AUTORITATIVO === true) {
        return;
    }
    window.MEDBOX_SALVAR_LANCES_AUTORITATIVO = true;

    function parseBR(valor) {
        let txt = String(valor || "").trim();

        txt = txt.replace("R$", "")
                 .replace("%", "")
                 .replace(/\s+/g, "")
                 .replace(/[^\d,.\-]/g, "");

        if (!txt) return 0;

        if (txt.includes(",")) {
            txt = txt.replace(/\./g, "").replace(",", ".");
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

    function get(row, seletor) {
        const el = row.querySelector(seletor);
        return el ? el.value : "";
    }

    function set(row, seletor, valor) {
        const el = row.querySelector(seletor);
        if (!el) return;

        el.value = valor;
        el.dispatchEvent(new Event("input", { bubbles: true }));
        el.dispatchEvent(new Event("change", { bubbles: true }));
    }

    function descricaoLinha(row) {
        const cell = row.children[1];
        return cell ? String(cell.textContent || "").trim() : "";
    }

    function recalcularPrecoMedbox(row) {
        const custo = parseBR(get(row, ".custo-manual-input"));
        const markup = parseBR(get(row, ".markup-atual-input") || "80");

        if (custo <= 0) return parseBR(get(row, ".medbox-input"));

        const preco = custo * (1 + markup / 100);

        set(row, ".medbox-input", moedaBR(preco));

        return preco;
    }

    function coletarItensAutoritativo() {
        const rows = Array.from(document.querySelectorAll("#tabelaLances tbody tr"));
        const itens = [];

        rows.forEach(function (row, idx) {
            const descricao = descricaoLinha(row);

            if (!descricao) return;

            const precoMedbox = recalcularPrecoMedbox(row);

            itens.push({
                item: idx + 1,
                descricao_produto: descricao,
                descricao: descricao,

                sku_master: get(row, ".sku-master-input").trim(),
                categoria: get(row, ".categoria-input").trim(),

                quantidade: parseBR(get(row, ".qtd-input")),

                preco_osinfo: parseBR(get(row, ".osinfo-input")),

                // CAMPO QUE ESTAVA FALTANDO NO SALVAMENTO
                ultima_compra: parseBR(get(row, ".ultima-input")),

                preco_medbox: precoMedbox,
                markup_atual: parseBR(get(row, ".markup-atual-input") || "80"),

                menor_preco_ofertado: parseBR(get(row, ".concorrente-input")),
                menor_lance: parseBR(get(row, ".concorrente-input")),
                empresa_melhor_lance: get(row, ".empresa-input").trim(),

                menor_custo_unitario: parseBR(get(row, ".custo-manual-input")),
                fornecedor_menor_custo: get(row, ".fornecedor-input").trim(),

                marca_fabricante: get(row, ".fabricante-input").trim(),
                marca: get(row, ".fabricante-input").trim()
            });
        });

        console.log("MEDBOX SALVAR AUTORITATIVO - primeiro item:", itens[0]);
        return itens;
    }

    function numeroCotacaoEditando() {
        return window.MEDBOX_NUMERO_COTACAO_EDITANDO || "";
    }

    function dadosCabecalho() {
        const cliente = document.getElementById("clienteCotacaoGerada")?.value || "";
        const oas = document.getElementById("oasCotacaoGerada")?.value || "";
        const projeto = document.getElementById("projetoCotacaoGerada")?.value || "";
        const controle = document.getElementById("controleClienteCotacaoGerada")?.value || "";

        return {
            cliente: cliente,
            cliente_orgao: cliente,
            oas: oas,
            projeto: projeto,
            controle_cliente: controle
        };
    }

    function confirmarEnvio(itens, acao) {
        const p = itens[0] || {};

        return confirm(
            "CONFIRA ANTES DE " + acao + ":\n\n" +
            "Descrição: " + (p.descricao_produto || "") + "\n" +
            "Quantidade: " + p.quantidade + "\n" +
            "Preço OSINFO: " + p.preco_osinfo + "\n" +
            "Últ. Compra da Cotação: " + p.ultima_compra + "\n" +
            "Menor Custo Encontrado: " + p.menor_custo_unitario + "\n" +
            "Markup: " + p.markup_atual + "\n" +
            "Preço MedBox: " + p.preco_medbox + "\n" +
            "Menor Preço Ofertado: " + p.menor_lance + "\n" +
            "Empresa Melhor Lance: " + p.empresa_melhor_lance + "\n\n" +
            "Clique OK se estiver correto."
        );
    }

    async function salvarCotacaoEditada(event) {
        event.preventDefault();
        event.stopPropagation();
        event.stopImmediatePropagation();

        const numero = numeroCotacaoEditando();

        if (!numero) {
            alert("Nenhuma cotação em edição foi identificada.");
            return false;
        }

        const itens = coletarItensAutoritativo();

        if (!itens.length) {
            alert("Nenhum item encontrado para salvar.");
            return false;
        }

        if (!confirmarEnvio(itens, "SALVAR")) {
            return false;
        }

        const payload = {
            ...dadosCabecalho(),
            itens: itens
        };

        const resp = await fetch("/cotacoes/lances/atualizar-cotacao/" + numero, {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify(payload)
        });

        const data = await resp.json();

        if (!data.ok) {
            alert(data.erro || "Erro ao salvar alterações.");
            return false;
        }

        alert("Cotação " + numero + " salva com sucesso.");
        window.location.href = data.url;
        return false;
    }

    async function gerarCotacaoNova(event) {
        event.preventDefault();
        event.stopPropagation();
        event.stopImmediatePropagation();

        const itens = coletarItensAutoritativo();

        if (!itens.length) {
            alert("Nenhum item encontrado para gerar cotação.");
            return false;
        }

        if (!confirmarEnvio(itens, "GERAR")) {
            return false;
        }

        const payload = {
            ...dadosCabecalho(),
            itens: itens
        };

        const resp = await fetch("/cotacoes/lances/gerar-cotacao", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify(payload)
        });

        const data = await resp.json();

        if (!data.ok) {
            alert(data.erro || "Erro ao gerar cotação.");
            return false;
        }

        window.location.href = data.url;
        return false;
    }

    function textoNormalizado(txt) {
        return String(txt || "")
            .toUpperCase()
            .normalize("NFD")
            .replace(/[\u0300-\u036f]/g, "");
    }

    function instalarInterceptadores() {
        document.addEventListener("click", function (event) {
            const alvo = event.target.closest("button, a");
            if (!alvo) return;

            const texto = textoNormalizado(alvo.textContent || "");

            if (texto.includes("SALVAR ALTERACOES DA COTACAO")) {
                return salvarCotacaoEditada(event);
            }

            if (alvo.id === "btnGerarCotacaoMedbox" || texto.includes("GERAR COTACAO")) {
                return gerarCotacaoNova(event);
            }
        }, true);
    }

    instalarInterceptadores();

    window.MEDBOX_coletarItensAutoritativo = coletarItensAutoritativo;

    console.log("MEDBOX salvamento autoritativo de lances ativo.");
})();

