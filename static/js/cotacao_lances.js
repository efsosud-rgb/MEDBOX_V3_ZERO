// ============================================================
// MEDBOX - DESATIVA BLOCOS ANTIGOS DE RECALCULO/AUTOCOMPLETE
// Mantem apenas o bloco final unico de lances ativo.
// ============================================================
(function () {
    window.MEDBOX_DESATIVA_BLOCOS_LANCES_ANTIGOS = true;
    window.MEDBOX_AUTOCOMPLETE_SKU_ATIVO = true;
    window.MEDBOX_FIX_SKU_MARKUP_PERSISTENCIA = true;
    window.MEDBOX_LANCES_AFNE_CANONICO = true;
    window.MEDBOX_LANCES_INDICADORES_CANONICOS = true;
    window.MEDBOX_LANCES_RECALCULO_DINAMICO_FINAL = true;
})();

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



// ============================================================
// MEDBOX - PAYLOAD DEFINITIVO DA GRADE DE LANCES
// Corrige definitivamente campos que não estavam persistindo:
// categoria, ultima_compra, menor_custo_unitario, fornecedor.
// ============================================================
(function () {
    if (window.MEDBOX_PAYLOAD_DEFINITIVO_LANCES === true) {
        return;
    }
    window.MEDBOX_PAYLOAD_DEFINITIVO_LANCES = true;

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
        return el ? String(el.value || "").trim() : "";
    }

    function set(row, seletor, valor) {
        const el = row.querySelector(seletor);
        if (!el) return;
        el.value = valor;
        el.dispatchEvent(new Event("input", { bubbles: true }));
        el.dispatchEvent(new Event("change", { bubbles: true }));
    }

    function descricao(row) {
        const cell = row.children[1];
        return cell ? String(cell.textContent || "").trim() : "";
    }

    function recalcularLinha(row) {
        const custo = parseBR(get(row, ".custo-manual-input"));
        const markup = parseBR(get(row, ".markup-atual-input") || "80");

        let precoMedbox = parseBR(get(row, ".medbox-input"));

        if (custo > 0) {
            precoMedbox = custo * (1 + markup / 100);
            set(row, ".medbox-input", moedaBR(precoMedbox));
        }

        return precoMedbox;
    }

    function fecharAutocomplete() {
        const boxes = [
            document.getElementById("medboxSkuAutocompleteBox"),
            document.getElementById("skuAutocompleteBoxFinal")
        ];

        boxes.forEach(function (box) {
            if (box) {
                box.innerHTML = "";
                box.style.display = "none";
            }
        });
    }

    function coletarLinha(row, idx) {
        const precoMedbox = recalcularLinha(row);

        return {
            item: idx + 1,
            descricao_produto: descricao(row),
            descricao: descricao(row),

            sku_master: get(row, ".sku-master-input"),
            categoria: get(row, ".categoria-input"),

            quantidade: parseBR(get(row, ".qtd-input")),

            preco_osinfo: parseBR(get(row, ".osinfo-input")),
            ultima_compra: parseBR(get(row, ".ultima-input")),

            preco_medbox: precoMedbox,
            markup_atual: parseBR(get(row, ".markup-atual-input") || "80"),

            menor_preco_ofertado: parseBR(get(row, ".concorrente-input")),
            menor_lance: parseBR(get(row, ".concorrente-input")),
            empresa_melhor_lance: get(row, ".empresa-input"),

            menor_custo_unitario: parseBR(get(row, ".custo-manual-input")),
            fornecedor_menor_custo: get(row, ".fornecedor-input"),

            marca_fabricante: get(row, ".fabricante-input"),
            marca: get(row, ".fabricante-input")
        };
    }

    function coletarItensDefinitivo() {
        const rows = Array.from(document.querySelectorAll("#tabelaLances tbody tr"));
        const itens = [];

        rows.forEach(function (row, idx) {
            const item = coletarLinha(row, idx);

            if (item.descricao_produto) {
                itens.push(item);
            }
        });

        console.log("MEDBOX PAYLOAD DEFINITIVO:", itens[0]);
        return itens;
    }

    function cabecalhoPayload() {
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

    function numeroEditando() {
        return window.MEDBOX_NUMERO_COTACAO_EDITANDO || "";
    }

    function confirmar(itens, acao) {
        const p = itens[0] || {};

        return confirm(
            "CONFIRA ANTES DE " + acao + ":\n\n" +
            "SKU: " + p.sku_master + "\n" +
            "Categoria: " + p.categoria + "\n" +
            "Quantidade: " + p.quantidade + "\n" +
            "Preço OSINFO: " + p.preco_osinfo + "\n" +
            "Últ. Compra da Cotação: " + p.ultima_compra + "\n" +
            "Menor Custo Encontrado: " + p.menor_custo_unitario + "\n" +
            "Fornecedor Menor Custo: " + p.fornecedor_menor_custo + "\n" +
            "Marca/Fabricante: " + p.marca_fabricante + "\n" +
            "Markup: " + p.markup_atual + "\n" +
            "Preço MedBox: " + p.preco_medbox + "\n\n" +
            "Clique OK se estiver correto."
        );
    }

    async function salvarEdicao(event) {
        event.preventDefault();
        event.stopPropagation();
        event.stopImmediatePropagation();

        const numero = numeroEditando();

        if (!numero) {
            alert("Nenhuma cotação em edição identificada.");
            return false;
        }

        const itens = coletarItensDefinitivo();

        if (!itens.length) {
            alert("Nenhum item encontrado para salvar.");
            return false;
        }

        if (!confirmar(itens, "SALVAR")) {
            return false;
        }

        const payload = {
            ...cabecalhoPayload(),
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

    async function gerarCotacao(event) {
        event.preventDefault();
        event.stopPropagation();
        event.stopImmediatePropagation();

        const itens = coletarItensDefinitivo();

        if (!itens.length) {
            alert("Nenhum item encontrado para gerar cotação.");
            return false;
        }

        if (!confirmar(itens, "GERAR")) {
            return false;
        }

        const payload = {
            ...cabecalhoPayload(),
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

    function normalizar(txt) {
        return String(txt || "")
            .toUpperCase()
            .normalize("NFD")
            .replace(/[\u0300-\u036f]/g, "");
    }

    // Captura no nível mais alto possível. Isso impede handlers antigos.
    window.addEventListener("click", function (event) {
        const alvo = event.target.closest("button, a");
        if (!alvo) return;

        const texto = normalizar(alvo.textContent || "");

        if (texto.includes("SALVAR ALTERACOES DA COTACAO")) {
            return salvarEdicao(event);
        }

        if (alvo.id === "btnGerarCotacaoMedbox" || texto.includes("GERAR COTACAO")) {
            return gerarCotacao(event);
        }
    }, true);

    document.addEventListener("change", function (event) {
        const campo = event.target;
        if (!campo || !campo.closest) return;

        const row = campo.closest("tr");
        if (!row) return;

        if (
            campo.matches(".sku-master-input") ||
            campo.matches(".custo-manual-input") ||
            campo.matches(".markup-atual-input")
        ) {
            setTimeout(function () {
                fecharAutocomplete();
                recalcularLinha(row);
            }, 100);
        }
    }, true);

    document.addEventListener("mousedown", function (event) {
        const box = document.getElementById("medboxSkuAutocompleteBox") ||
                    document.getElementById("skuAutocompleteBoxFinal");

        if (box && box.contains(event.target)) {
            setTimeout(fecharAutocomplete, 150);
        }
    }, true);

    window.MEDBOX_coletarItensDefinitivo = coletarItensDefinitivo;
    window.MEDBOX_coletarItensAutoritativo = coletarItensDefinitivo;
    window.coletarItensParaCotacaoGerada = coletarItensDefinitivo;
    window.coletarItensEdicaoOAS = coletarItensDefinitivo;

    console.log("MEDBOX PAYLOAD DEFINITIVO DE LANCES ATIVO");
})();



// ============================================================
// MEDBOX - BLOQUEIO DEFINITIVO DE GERAÇÃO DUPLICADA EM EDIÇÃO
// Em modo edição:
// - Gerar Cotação não cria nova cotação.
// - Salvar Alterações usa apenas o salvamento autoritativo.
// - Clona botões para remover eventos antigos.
// ============================================================
(function () {
    if (window.MEDBOX_BLOQUEIO_GERAR_DUPLICADO_EDICAO === true) {
        return;
    }
    window.MEDBOX_BLOQUEIO_GERAR_DUPLICADO_EDICAO = true;

    function numeroEditando() {
        return window.MEDBOX_NUMERO_COTACAO_EDITANDO || "";
    }

    function normalizar(txt) {
        return String(txt || "")
            .toUpperCase()
            .normalize("NFD")
            .replace(/[\u0300-\u036f]/g, "");
    }

    function botaoSalvar() {
        return Array.from(document.querySelectorAll("button, a")).find(function (el) {
            return normalizar(el.textContent || "").includes("SALVAR ALTERACOES DA COTACAO");
        });
    }

    function botaoGerar() {
        return document.getElementById("btnGerarCotacaoMedbox");
    }

    function coletar() {
        if (window.MEDBOX_coletarItensDefinitivo) {
            return window.MEDBOX_coletarItensDefinitivo();
        }

        if (window.MEDBOX_coletarItensAutoritativo) {
            return window.MEDBOX_coletarItensAutoritativo();
        }

        if (window.coletarItensParaCotacaoGerada) {
            return window.coletarItensParaCotacaoGerada();
        }

        alert("Erro: coletor definitivo de itens não encontrado.");
        return [];
    }

    function cabecalhoPayload() {
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

    function confirmar(itens) {
        const p = itens[0] || {};

        return confirm(
            "CONFIRA ANTES DE SALVAR:\n\n" +
            "SKU: " + p.sku_master + "\n" +
            "Categoria: " + p.categoria + "\n" +
            "Quantidade: " + p.quantidade + "\n" +
            "Preço OSINFO: " + p.preco_osinfo + "\n" +
            "Últ. Compra da Cotação: " + p.ultima_compra + "\n" +
            "Menor Custo Encontrado: " + p.menor_custo_unitario + "\n" +
            "Fornecedor Menor Custo: " + p.fornecedor_menor_custo + "\n" +
            "Marca/Fabricante: " + p.marca_fabricante + "\n" +
            "Markup: " + p.markup_atual + "\n" +
            "Preço MedBox: " + p.preco_medbox + "\n\n" +
            "Clique OK se estiver correto."
        );
    }

    async function salvarEdicaoFinal(event) {
        if (event) {
            event.preventDefault();
            event.stopPropagation();
            event.stopImmediatePropagation();
        }

        const numero = numeroEditando();

        if (!numero) {
            alert("Nenhuma cotação em edição identificada.");
            return false;
        }

        const itens = coletar();

        if (!itens.length) {
            alert("Nenhum item encontrado para salvar.");
            return false;
        }

        if (!confirmar(itens)) {
            return false;
        }

        const payload = {
            ...cabecalhoPayload(),
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

    function prepararBotoesEdicao() {
        const numero = numeroEditando();

        if (!numero) return;

        const btnGerar = botaoGerar();

        if (btnGerar && btnGerar.dataset.medboxBloqueadoEdicao !== "1") {
            const cloneGerar = btnGerar.cloneNode(true);
            cloneGerar.dataset.medboxBloqueadoEdicao = "1";
            cloneGerar.type = "button";
            cloneGerar.textContent = "Em edição: use Salvar Alterações";
            cloneGerar.style.opacity = "0.55";
            cloneGerar.style.cursor = "not-allowed";

            cloneGerar.addEventListener("click", function (event) {
                event.preventDefault();
                event.stopPropagation();
                event.stopImmediatePropagation();
                alert("Você está editando a cotação " + numero + ". Use o botão Salvar Alterações da Cotação.");
                return false;
            }, true);

            btnGerar.parentNode.replaceChild(cloneGerar, btnGerar);
        }

        const btnSalvar = botaoSalvar();

        if (btnSalvar && btnSalvar.dataset.medboxSalvarFinal !== "1") {
            const cloneSalvar = btnSalvar.cloneNode(true);
            cloneSalvar.dataset.medboxSalvarFinal = "1";
            cloneSalvar.type = "button";

            cloneSalvar.addEventListener("click", salvarEdicaoFinal, true);

            btnSalvar.parentNode.replaceChild(cloneSalvar, btnSalvar);
        }
    }

    window.addEventListener("click", function (event) {
        const numero = numeroEditando();
        if (!numero) return;

        const alvo = event.target.closest("button, a");
        if (!alvo) return;

        const texto = normalizar(alvo.textContent || "");

        if (texto.includes("SALVAR ALTERACOES DA COTACAO")) {
            return salvarEdicaoFinal(event);
        }

        if (alvo.id === "btnGerarCotacaoMedbox" || texto.includes("GERAR COTACAO")) {
            event.preventDefault();
            event.stopPropagation();
            event.stopImmediatePropagation();
            alert("Você está editando a cotação " + numero + ". Use o botão Salvar Alterações da Cotação.");
            return false;
        }
    }, true);

    document.addEventListener("DOMContentLoaded", prepararBotoesEdicao);
    window.addEventListener("load", prepararBotoesEdicao);
    setTimeout(prepararBotoesEdicao, 300);
    setTimeout(prepararBotoesEdicao, 1000);

    window.MEDBOX_salvarEdicaoFinal = salvarEdicaoFinal;

    console.log("MEDBOX bloqueio definitivo de geração duplicada em edição ativo.");
})();


// ============================================================
// MEDBOX - ENRIQUECIMENTO CANONICO LANCES AFNE
// Recalcula Preco MedBox por markup, preserva Preco OSINFO e
// aplica menor custo/fornecedor/marca retornados pelo backend.
// ============================================================
(function () {
    if (window.MEDBOX_LANCES_AFNE_CANONICO === true) return;
    window.MEDBOX_LANCES_AFNE_CANONICO = true;

    function parseBR(valor) {
        let txt = String(valor || "").trim()
            .replace("R$", "")
            .replace("%", "")
            .replace(/\s+/g, "")
            .replace(/[^\d,.\-]/g, "");
        if (!txt) return 0;
        if (txt.includes(",")) txt = txt.replace(/\./g, "").replace(",", ".");
        const n = parseFloat(txt);
        return Number.isFinite(n) ? n : 0;
    }

    function moedaPrecisa(valor) {
        const n = Number(valor || 0);
        if (!Number.isFinite(n)) return "";
        const precisa4 = Math.abs(n - Number(n.toFixed(2))) > 0.000001;
        return "R$ " + n.toLocaleString("pt-BR", {
            minimumFractionDigits: 2,
            maximumFractionDigits: precisa4 ? 4 : 2
        });
    }

    function get(row, selector) {
        const el = row ? row.querySelector(selector) : null;
        return el ? String(el.value || "").trim() : "";
    }

    function set(row, selector, value) {
        const el = row ? row.querySelector(selector) : null;
        if (!el) return;
        el.value = value || "";
        el.dispatchEvent(new Event("input", { bubbles: true }));
        el.dispatchEvent(new Event("change", { bubbles: true }));
    }

    function descricao(row) {
        const strong = row?.children?.[1]?.querySelector("strong");
        if (strong) return String(strong.textContent || "").trim();
        const cell = row?.children?.[1];
        return cell ? String(cell.textContent || "").trim() : "";
    }

    function aplicarDadosCusto(row, dados) {
        if (!row || !dados) return;

        const categoriaAtual = get(row, ".categoria-input");
        const categoria = categoriaAtual || dados.categoria || "";
        const custo = dados.menor_custo_unitario || dados.menor_custo || dados.menor_custo_encontrado || 0;
        const fornecedor = dados.fornecedor_menor_custo || dados.fornecedor || "";
        const marca = dados.marca_fabricante || dados.marca || dados.fabricante || "";

        if (categoria) set(row, ".categoria-input", categoria);
        if (fornecedor) set(row, ".fornecedor-input", fornecedor);
        if (marca) set(row, ".fabricante-input", marca);
        if (Number(custo) >= 0 && (dados.menor_custo_unitario !== undefined || dados.menor_custo !== undefined || dados.menor_custo_encontrado !== undefined)) {
            set(row, ".custo-manual-input", Number(custo) > 0 ? moedaPrecisa(custo) : "");
            row.dataset.custo = String(custo || 0);
            row.dataset.temPreco = Number(custo) > 0 ? "1" : "0";
        }

        recalcularLinhaCanonica(row);
    }

    function recalcularLinhaCanonica(row) {
        if (!row) return 0;
        const custo = parseBR(get(row, ".custo-manual-input"));
        const markup = parseBR(get(row, ".markup-atual-input") || "80");
        const preco = custo > 0 ? custo * (1 + markup / 100) : 0;
        if (preco > 0) set(row, ".medbox-input", moedaPrecisa(preco));
        return preco;
    }

    async function salvarSkuLinha(event) {
        const botao = event.target.closest(".btn-salvar-sku");
        if (!botao) return;

        event.preventDefault();
        event.stopPropagation();
        event.stopImmediatePropagation();

        const row = botao.closest("tr");
        if (!row) return false;

        const payload = {
            descricao_cotacao: descricao(row),
            sku_master: get(row, ".sku-master-input"),
            fornecedor: get(row, ".fornecedor-input"),
            fabricante: get(row, ".fabricante-input"),
            categoria: get(row, ".categoria-input")
        };

        if (!payload.sku_master) {
            alert("Informe o SKU Master antes de salvar.");
            return false;
        }

        const resp = await fetch("/cotacoes/lances/salvar-sku", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify(payload)
        });
        const data = await resp.json();
        if (!data.ok) {
            alert(data.erro || "Erro ao salvar SKU.");
            return false;
        }

        aplicarDadosCusto(row, data);
        const status = row.querySelector(".status-cell");
        if (status) status.innerHTML = '<span class="status-badge status-ok">SKU SELECIONADO</span>';
        return false;
    }

    function itemCanonico(row, idx) {
        const precoMedbox = recalcularLinhaCanonica(row);
        return {
            item: idx + 1,
            descricao_original: descricao(row),
            descricao_produto: descricao(row),
            descricao: descricao(row),
            sku_master: get(row, ".sku-master-input"),
            categoria: get(row, ".categoria-input"),
            unidade_compra: row.dataset.unidadeCompra || "",
            unidade: row.dataset.unidadeCompra || "",
            quantidade: parseBR(get(row, ".qtd-input")),
            preco_osinfo: parseBR(get(row, ".osinfo-input")),
            ultima_compra: parseBR(get(row, ".ultima-input")),
            preco_medbox: precoMedbox,
            markup_atual: parseBR(get(row, ".markup-atual-input") || "80"),
            menor_preco_ofertado: parseBR(get(row, ".concorrente-input")),
            menor_lance: parseBR(get(row, ".concorrente-input")),
            empresa_melhor_lance: get(row, ".empresa-input"),
            menor_custo_unitario: parseBR(get(row, ".custo-manual-input")),
            menor_custo_encontrado: parseBR(get(row, ".custo-manual-input")),
            fornecedor_menor_custo: get(row, ".fornecedor-input"),
            marca_fabricante: get(row, ".fabricante-input"),
            marca: get(row, ".fabricante-input")
        };
    }

    function coletarCanonico() {
        return Array.from(document.querySelectorAll("#tabelaLances tbody tr"))
            .map(itemCanonico)
            .filter((item) => item.descricao_produto);
    }

    document.addEventListener("click", salvarSkuLinha, true);
    document.addEventListener("input", function (event) {
        const campo = event.target;
        if (!campo || !campo.closest) return;
        if (campo.matches(".markup-atual-input") || campo.matches(".custo-manual-input")) {
            recalcularLinhaCanonica(campo.closest("tr"));
        }
    }, true);
    document.addEventListener("change", function (event) {
        const campo = event.target;
        if (!campo || !campo.closest) return;
        if (campo.matches(".markup-atual-input") || campo.matches(".custo-manual-input") || campo.matches(".sku-master-input")) {
            setTimeout(function () { recalcularLinhaCanonica(campo.closest("tr")); }, 50);
        }
    }, true);

    window.MEDBOX_recalcularLinhaLance = recalcularLinhaCanonica;
    window.MEDBOX_coletarItensDefinitivo = coletarCanonico;
    window.MEDBOX_coletarItensAutoritativo = coletarCanonico;
    window.coletarItensParaCotacaoGerada = coletarCanonico;
})();

// ============================================================
// MEDBOX - LANCES: INDICADORES, MOEDA BR E STATUS UNICO
// ============================================================
(function () {
    if (window.MEDBOX_LANCES_INDICADORES_CANONICOS === true) return;
    window.MEDBOX_LANCES_INDICADORES_CANONICOS = true;

    const moedaBR = new Intl.NumberFormat("pt-BR", {
        style: "currency",
        currency: "BRL",
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    });

    function parseNumeroBR(valor) {
        let txt = String(valor ?? "").trim()
            .replace("R$", "")
            .replace("%", "")
            .replace(/\s+/g, "")
            .replace(/[^\d,.-]/g, "");
        if (!txt) return 0;
        if (txt.includes(",")) txt = txt.replace(/\./g, "").replace(",", ".");
        const n = Number.parseFloat(txt);
        return Number.isFinite(n) ? n : 0;
    }

    function formatarMoedaBR(valor) {
        const n = Number(valor || 0);
        return moedaBR.format(Number.isFinite(n) ? n : 0);
    }

    function formatarMoedaEditavel(valor) {
        const n = Number(valor || 0);
        if (!Number.isFinite(n)) return "";
        const precisa4 = Math.abs(n - Number(n.toFixed(2))) > 0.000001;
        return "R$ " + n.toLocaleString("pt-BR", {
            minimumFractionDigits: 2,
            maximumFractionDigits: precisa4 ? 4 : 2
        });
    }

    function formatarQuantidadeCotacao(valor) {
        const n = parseNumeroBR(valor);
        if (!Number.isFinite(n) || n <= 0) return "";
        if (Number.isInteger(n)) return String(n);
        return String(n).replace(".", ",");
    }

    function get(row, selector) {
        const el = row ? row.querySelector(selector) : null;
        return el ? String(el.value || "").trim() : "";
    }

    function setValor(row, selector, value) {
        const el = row ? row.querySelector(selector) : null;
        if (el) el.value = value;
    }

    function setStatus(row, status, medboxVence) {
        row.dataset.status = status;
        row.dataset.medboxVence = medboxVence ? "1" : "0";
        row.classList.toggle("linha-revisar", status === "REVISAR SKU");
        row.classList.toggle("linha-sem-preco", status === "SEM PREÇO");
        row.classList.toggle("linha-ok", status !== "REVISAR SKU" && status !== "SEM PREÇO");
        const cell = row.querySelector(".status-cell");
        if (cell) {
            const classe = status.toLowerCase().replace(/\s+/g, "-").normalize("NFD").replace(/[\u0300-\u036f]/g, "");
            cell.innerHTML = '<span class="status-badge status-' + classe + '">' + status + '</span>';
        }
    }

    function avaliarResultadoItemLance(item) {
        let status;
        if (!item.sku_master) status = "REVISAR SKU";
        else if (!(item.menor_custo_encontrado > 0) || !(item.preco_medbox > 0)) status = "SEM PREÇO";
        else if (item.preco_osinfo > 0 && item.preco_medbox <= item.preco_osinfo) status = "MEDBOX VENCE";
        else status = "NEGOCIAR";
        return { status, medbox_vence: status === "MEDBOX VENCE", tem_preco: item.menor_custo_encontrado > 0 && item.preco_medbox > 0 };
    }

    function itemDaLinha(row) {
        const custo = parseNumeroBR(get(row, ".custo-manual-input"));
        const markup = parseNumeroBR(get(row, ".markup-atual-input") || "80");
        const precoMedbox = custo > 0 ? custo * (1 + markup / 100) : 0;
        const qtd = parseNumeroBR(get(row, ".qtd-input"));
        return {
            row,
            quantidade: qtd,
            sku_master: get(row, ".sku-master-input"),
            preco_osinfo: parseNumeroBR(get(row, ".osinfo-input")),
            preco_medbox: precoMedbox,
            markup_atual: markup,
            menor_custo_encontrado: custo,
            tem_preco: custo > 0 && precoMedbox > 0
        };
    }

    function recalcularLinha(row) {
        if (!row) return null;
        const item = itemDaLinha(row);
        setValor(row, ".qtd-input", formatarQuantidadeCotacao(item.quantidade));
        if (item.preco_medbox > 0) setValor(row, ".medbox-input", formatarMoedaBR(item.preco_medbox));
        else setValor(row, ".medbox-input", "");
        const avaliacao = avaliarResultadoItemLance(item);
        item.status = avaliacao.status;
        item.medbox_vence = avaliacao.medbox_vence;
        item.tem_preco = avaliacao.tem_preco;
        setStatus(row, avaliacao.status, avaliacao.medbox_vence);
        return item;
    }

    function linhasCotadas() {
        return Array.from(document.querySelectorAll("#tabelaLances tbody tr"))
            .map(recalcularLinha)
            .filter((item) => item && item.quantidade > 0);
    }

    function atualizarKpi(chave, valor) {
        const el = document.querySelector('[data-kpi="' + chave + '"]');
        if (el) el.textContent = valor;
    }

    function recalcularResumo() {
        const itens = linhasCotadas();
        const total = itens.length;
        const comSku = itens.filter((i) => !!i.sku_master).length;
        const revisar = itens.filter((i) => i.status === "REVISAR SKU").length;
        const comPreco = itens.filter((i) => i.tem_preco).length;
        const semPreco = itens.filter((i) => i.status === "SEM PREÇO").length;
        const ganhos = itens.filter((i) => i.medbox_vence).length;
        const negociar = itens.filter((i) => i.status === "NEGOCIAR").length;
        const totalGanho = itens
            .filter((i) => i.medbox_vence && i.preco_medbox >= 0)
            .reduce((acc, i) => acc + (i.quantidade * i.preco_medbox), 0);
        const pct = total ? (ganhos / total) * 100 : 0;

        atualizarKpi("total_itens", String(total));
        atualizarKpi("itens_com_sku", String(comSku));
        atualizarKpi("itens_revisar_sku", String(revisar));
        atualizarKpi("itens_com_preco_medbox", String(comPreco));
        atualizarKpi("itens_sem_preco", String(semPreco));
        atualizarKpi("itens_ganhos_medbox", String(ganhos));
        atualizarKpi("itens_competitivos", String(ganhos));
        atualizarKpi("percentual_itens_ganhos", pct.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + "%");
        atualizarKpi("itens_negociar", String(negociar));
        atualizarKpi("total_ganho_medbox", formatarMoedaBR(totalGanho));
        atualizarKpi("total_medbox", formatarMoedaBR(totalGanho));
    }

    const recalcularLinhaAnterior = window.MEDBOX_recalcularLinhaLance;
    window.parseNumeroBR = parseNumeroBR;
    window.formatarMoedaBR = formatarMoedaBR;
    window.formatarQuantidadeCotacao = formatarQuantidadeCotacao;
    window.avaliarResultadoItemLance = avaliarResultadoItemLance;
    window.MEDBOX_recalcularLinhaLance = function (row) {
        const item = recalcularLinha(row);
        recalcularResumo();
        return item ? item.preco_medbox : (typeof recalcularLinhaAnterior === "function" ? recalcularLinhaAnterior(row) : 0);
    };

    document.addEventListener("input", function (event) {
        const campo = event.target;
        if (!campo || !campo.closest) return;
        if (campo.matches(".markup-atual-input") || campo.matches(".custo-manual-input") || campo.matches(".sku-master-input")) {
            recalcularLinha(campo.closest("tr"));
            recalcularResumo();
        }
    }, true);

    document.addEventListener("change", function (event) {
        const campo = event.target;
        if (!campo || !campo.closest) return;
        if (campo.matches(".markup-atual-input") || campo.matches(".custo-manual-input") || campo.matches(".sku-master-input") || campo.matches(".qtd-input")) {
            recalcularLinha(campo.closest("tr"));
            recalcularResumo();
        }
    }, true);

    document.addEventListener("DOMContentLoaded", recalcularResumo);
    window.addEventListener("load", recalcularResumo);
    setTimeout(recalcularResumo, 300);
})();

// ============================================================
// MEDBOX - LANCES: RECALCULO DINAMICO FINAL
// Uma funcao para linha e uma funcao para resumo.
// ============================================================
(function () {
    if (window.MEDBOX_LANCES_RECALCULO_DINAMICO_FINAL === true) return;
    window.MEDBOX_LANCES_RECALCULO_DINAMICO_FINAL = true;

    const gradeSelector = "#tabelaLances";
    const camposRecalculo = [
        ".sku-master-input",
        ".qtd-input",
        ".osinfo-input",
        ".ultima-input",
        ".concorrente-input",
        ".custo-manual-input",
        ".markup-atual-input"
    ].join(",");

    const moedaFormatterBR = new Intl.NumberFormat("pt-BR", {
        style: "currency",
        currency: "BRL",
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    });

    function parseNumeroBR(valor) {
        let texto = String(valor ?? "").trim()
            .replace("R$", "")
            .replace("%", "")
            .replace(/\s+/g, "")
            .replace(/[^\d,.-]/g, "");
        if (!texto) return 0;
        if (texto.includes(",")) texto = texto.replace(/\./g, "").replace(",", ".");
        const numero = Number.parseFloat(texto);
        return Number.isFinite(numero) ? numero : 0;
    }

    function formatarMoedaBR(valor) {
        const numero = Number(valor || 0);
        return moedaFormatterBR.format(Number.isFinite(numero) ? numero : 0);
    }

    function formatarQuantidadeCotacao(valor) {
        const numero = parseNumeroBR(valor);
        if (!Number.isFinite(numero) || numero <= 0) return "";
        if (Number.isInteger(numero)) return String(numero);
        return String(numero).replace(".", ",");
    }

    function valor(linha, seletor) {
        const el = linha ? linha.querySelector(seletor) : null;
        return el ? String(el.value || "").trim() : "";
    }

    function definirValor(linha, seletor, novoValor) {
        const el = linha ? linha.querySelector(seletor) : null;
        if (el) el.value = novoValor ?? "";
    }

    function descricaoOriginal(linha) {
        const strong = linha?.children?.[1]?.querySelector("strong");
        return strong ? String(strong.textContent || "").trim() : "";
    }

    function avaliarResultadoItemLance(item) {
        let status;
        if (!item.sku_master) status = "REVISAR SKU";
        else if (!(item.menor_custo_encontrado > 0) || !(item.preco_medbox > 0)) status = "SEM PREÇO";
        else if (item.preco_osinfo > 0 && item.preco_medbox <= item.preco_osinfo) status = "MEDBOX VENCE";
        else status = "NEGOCIAR";
        return {
            status: status,
            medbox_vence: status === "MEDBOX VENCE",
            tem_preco: item.menor_custo_encontrado > 0 && item.preco_medbox > 0
        };
    }

    function classeStatus(status) {
        return String(status || "")
            .toLowerCase()
            .replace(/\s+/g, "-")
            .normalize("NFD")
            .replace(/[\u0300-\u036f]/g, "");
    }

    function aplicarStatus(linha, avaliacao) {
        linha.dataset.status = avaliacao.status;
        linha.dataset.medboxVence = avaliacao.medbox_vence ? "1" : "0";
        linha.dataset.temPreco = avaliacao.tem_preco ? "1" : "0";
        linha.classList.toggle("linha-revisar", avaliacao.status === "REVISAR SKU");
        linha.classList.toggle("linha-sem-preco", avaliacao.status === "SEM PREÇO");
        linha.classList.toggle("linha-ok", avaliacao.status !== "REVISAR SKU" && avaliacao.status !== "SEM PREÇO");
        const cell = linha.querySelector(".status-cell");
        if (cell) {
            cell.innerHTML = '<span class="status-badge status-' + classeStatus(avaliacao.status) + '">' + avaliacao.status + '</span>';
        }
    }

    function lerItemLinha(linha) {
        const menorCusto = parseNumeroBR(valor(linha, ".custo-manual-input"));
        const markup = parseNumeroBR(valor(linha, ".markup-atual-input") || "80");
        const precoMedbox = menorCusto > 0 ? menorCusto * (1 + markup / 100) : 0;
        return {
            linha: linha,
            descricao_original: descricaoOriginal(linha),
            sku_master: valor(linha, ".sku-master-input"),
            categoria: valor(linha, ".categoria-input"),
            quantidade: parseNumeroBR(valor(linha, ".qtd-input")),
            preco_osinfo: parseNumeroBR(valor(linha, ".osinfo-input")),
            ultima_compra: parseNumeroBR(valor(linha, ".ultima-input")),
            menor_preco_ofertado: parseNumeroBR(valor(linha, ".concorrente-input")),
            empresa_melhor_lance: valor(linha, ".empresa-input"),
            menor_custo_encontrado: menorCusto,
            markup_atual: markup,
            preco_medbox: precoMedbox,
            fornecedor_menor_custo: valor(linha, ".fornecedor-input"),
            marca_fabricante: valor(linha, ".fabricante-input")
        };
    }

    function recalcularLinhaLance(linha) {
        if (!linha) return null;
        const item = lerItemLinha(linha);
        const avaliacao = avaliarResultadoItemLance(item);
        item.status = avaliacao.status;
        item.medbox_vence = avaliacao.medbox_vence;
        item.tem_preco = avaliacao.tem_preco;

        linha.dataset.quantidade = String(item.quantidade || 0);
        linha.dataset.precoOsinfo = String(item.preco_osinfo || 0);
        linha.dataset.precoMedbox = String(item.preco_medbox || 0);
        linha.dataset.menorCusto = String(item.menor_custo_encontrado || 0);
        linha.dataset.markup = String(item.markup_atual || 0);
        linha.dataset.skuEncontrado = item.sku_master ? "1" : "0";
        linha.dataset.operacional = item.quantidade > 0 ? "1" : "0";

        if (item.quantidade > 0) definirValor(linha, ".qtd-input", formatarQuantidadeCotacao(item.quantidade));
        if (item.preco_medbox > 0) definirValor(linha, ".medbox-input", formatarMoedaBR(item.preco_medbox));
        else definirValor(linha, ".medbox-input", "");
        aplicarStatus(linha, avaliacao);
        return item;
    }

    function linhasDaGrade() {
        return Array.from(document.querySelectorAll(gradeSelector + " tbody tr"));
    }

    function atualizarKpi(chave, valorTexto) {
        const el = document.querySelector('[data-kpi="' + chave + '"]');
        if (el) el.textContent = valorTexto;
    }

    function recalcularResumoLances() {
        const itens = linhasDaGrade().map(recalcularLinhaLance).filter(Boolean);
        const cotados = itens.filter((item) => item.quantidade > 0);
        const total = cotados.length;
        const ganhos = cotados.filter((item) => item.medbox_vence).length;
        const totalGanho = cotados
            .filter((item) => item.medbox_vence)
            .reduce((acc, item) => acc + (item.quantidade * item.preco_medbox), 0);
        const percentual = total ? (ganhos / total) * 100 : 0;

        atualizarKpi("total_itens", String(total));
        atualizarKpi("itens_com_sku", String(cotados.filter((item) => !!item.sku_master).length));
        atualizarKpi("itens_revisar_sku", String(cotados.filter((item) => item.status === "REVISAR SKU").length));
        atualizarKpi("itens_com_preco_medbox", String(cotados.filter((item) => item.tem_preco).length));
        atualizarKpi("itens_sem_preco", String(cotados.filter((item) => item.status === "SEM PREÇO").length));
        atualizarKpi("itens_ganhos_medbox", String(ganhos));
        atualizarKpi("itens_competitivos", String(ganhos));
        atualizarKpi("percentual_itens_ganhos", percentual.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + "%");
        atualizarKpi("itens_negociar", String(cotados.filter((item) => item.status === "NEGOCIAR").length));
        atualizarKpi("total_ganho_medbox", formatarMoedaBR(totalGanho));
        atualizarKpi("total_medbox", formatarMoedaBR(totalGanho));
        return { total_itens: total, itens_ganhos_medbox: ganhos, total_ganho_medbox: totalGanho, percentual_itens_ganhos: percentual };
    }

    function aplicarDadosSku(linha, dados, preservarCategoriaManual) {
        if (!linha || !dados) return;
        const categoriaAtual = valor(linha, ".categoria-input");
        const categoriaNova = dados.categoria || "";
        const custo = dados.menor_custo_unitario ?? dados.menor_custo ?? dados.menor_custo_encontrado;
        if (!preservarCategoriaManual || !categoriaAtual) definirValor(linha, ".categoria-input", categoriaAtual || categoriaNova);
        if (dados.fornecedor_menor_custo || dados.fornecedor) definirValor(linha, ".fornecedor-input", dados.fornecedor_menor_custo || dados.fornecedor || "");
        if (dados.marca_fabricante || dados.marca || dados.fabricante) definirValor(linha, ".fabricante-input", dados.marca_fabricante || dados.marca || dados.fabricante || "");
        if (custo !== undefined && custo !== null && custo !== "") definirValor(linha, ".custo-manual-input", Number(custo) > 0 ? formatarMoedaBR(custo) : "");
        recalcularLinhaLance(linha);
        recalcularResumoLances();
    }

    function aoEditar(event) {
        const campo = event.target;
        if (!campo || !campo.closest) return;
        const linha = campo.closest(gradeSelector + " tbody tr");
        if (!linha) return;
        if (campo.matches(camposRecalculo)) {
            recalcularLinhaLance(linha);
            recalcularResumoLances();
        }
    }

    function aoMudar(event) {
        const campo = event.target;
        if (!campo || !campo.closest) return;
        const linha = campo.closest(gradeSelector + " tbody tr");
        if (!linha) return;
        if (campo.matches(".sku-sugestao-select")) {
            const opt = campo.selectedOptions && campo.selectedOptions[0];
            if (opt && opt.value) {
                definirValor(linha, ".sku-master-input", opt.value);
                aplicarDadosSku(linha, {
                    categoria: opt.dataset.categoria,
                    fornecedor_menor_custo: opt.dataset.fornecedor,
                    marca_fabricante: opt.dataset.fabricante,
                    menor_custo_unitario: opt.dataset.custo
                }, true);
            }
            return;
        }
        if (campo.matches(camposRecalculo + ",.categoria-input,.empresa-input,.fornecedor-input,.fabricante-input")) {
            recalcularLinhaLance(linha);
            recalcularResumoLances();
        }
    }

    document.addEventListener("input", aoEditar, true);
    document.addEventListener("change", aoMudar, true);
    document.addEventListener("click", function (event) {
        if (event.target && event.target.closest && event.target.closest(".btn-salvar-sku")) {
            setTimeout(recalcularResumoLances, 300);
        }
    }, true);

    window.parseNumeroBR = parseNumeroBR;
    window.formatarMoedaBR = formatarMoedaBR;
    window.formatarQuantidadeCotacao = formatarQuantidadeCotacao;
    window.avaliarResultadoItemLance = avaliarResultadoItemLance;
    window.recalcularLinhaLance = recalcularLinhaLance;
    window.recalcularResumoLances = recalcularResumoLances;
    window.MEDBOX_recalcularLinhaLance = recalcularLinhaLance;
    window.MEDBOX_recalcularResumoLances = recalcularResumoLances;
    window.MEDBOX_aplicarDadosSkuLance = aplicarDadosSku;

    document.addEventListener("DOMContentLoaded", recalcularResumoLances);
    window.addEventListener("load", recalcularResumoLances);
    setTimeout(recalcularResumoLances, 250);
})();

// ============================================================
// MEDBOX - LANCES OPERACIONAL UNICO
// Autocomplete, recalc de linha e resumo com Total Ganho por Menor Valor.
// ============================================================
(function () {
    if (window.MEDBOX_LANCES_OPERACIONAL_UNICO === true) return;
    window.MEDBOX_LANCES_OPERACIONAL_UNICO = true;

    const gradeSelector = "#tabelaLances";
    const moedaFormatterBR = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL", minimumFractionDigits: 2, maximumFractionDigits: 2 });
    let caixaSku = null;
    let inputSkuAtual = null;
    let timerSku = null;

    function parseNumeroBR(valor) {
        let texto = String(valor ?? "").trim().replace("R$", "").replace("%", "").replace(/\s+/g, "").replace(/[^\d,.-]/g, "");
        if (!texto) return 0;
        if (texto.includes(",")) texto = texto.replace(/\./g, "").replace(",", ".");
        const numero = Number.parseFloat(texto);
        return Number.isFinite(numero) ? numero : 0;
    }

    function formatarMoedaBR(valor) {
        const numero = Number(valor || 0);
        return moedaFormatterBR.format(Number.isFinite(numero) ? numero : 0);
    }

    function formatarQuantidadeCotacao(valor) {
        const numero = parseNumeroBR(valor);
        if (!Number.isFinite(numero) || numero <= 0) return "";
        return Number.isInteger(numero) ? String(numero) : String(numero).replace(".", ",");
    }

    function normalizarTexto(valor) {
        return String(valor || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/\s+/g, " ").trim().toUpperCase();
    }

    function empresaEhMedbox(valor) {
        const texto = normalizarTexto(valor);
        return texto === "MEDBOX" || texto === "MED BOX" || texto === "MEDBOX DISTRIBUIDORA" || texto === "MEDBOX DISTRIBUIDORA DE MEDICAMENTOS" || texto.startsWith("MEDBOX DISTRIBUIDORA");
    }

    function valor(linha, seletor) {
        const el = linha ? linha.querySelector(seletor) : null;
        return el ? String(el.value || "").trim() : "";
    }

    function definirValor(linha, seletor, novoValor) {
        const el = linha ? linha.querySelector(seletor) : null;
        if (el) el.value = novoValor ?? "";
    }

    function descricaoOriginal(linha) {
        const strong = linha?.children?.[1]?.querySelector("strong");
        return strong ? String(strong.textContent || "").trim() : "";
    }

    function calcularVencedor(item) {
        const opcoes = [];
        if (item.preco_osinfo > 0) opcoes.push({ origem: "OSINFO", empresa: "OSINFO", valor: item.preco_osinfo, prioridade: 2 });
        if (item.menor_preco_ofertado > 0) opcoes.push({ origem: "LANCE", empresa: item.empresa_melhor_lance || "LANCE GANHADOR", valor: item.menor_preco_ofertado, prioridade: 1 });
        if (item.preco_medbox > 0) opcoes.push({ origem: "MEDBOX", empresa: "MEDBOX", valor: item.preco_medbox, prioridade: 0 });
        if (!opcoes.length) return { origem: "", empresa: "", valor: 0, medbox_vence: false };
        opcoes.sort((a, b) => (a.valor - b.valor) || (a.prioridade - b.prioridade));
        const vencedor = opcoes[0];
        return { origem: vencedor.origem, empresa: vencedor.empresa, valor: vencedor.valor, medbox_vence: vencedor.origem === "MEDBOX" && empresaEhMedbox(vencedor.empresa) };
    }

    function avaliarResultadoItemLance(item) {
        if (!(item.quantidade > 0)) return { status: "FORA DA COTAÇÃO", medbox_vence: false, tem_preco: false };
        if (!item.sku_master) return { status: "REVISAR SKU", medbox_vence: false, tem_preco: false };
        if (!(item.menor_custo_encontrado > 0) || !(item.preco_medbox > 0)) return { status: "SEM PREÇO", medbox_vence: false, tem_preco: false };
        const vencedor = calcularVencedor(item);
        item.menor_valor_vencedor = vencedor.valor;
        item.empresa_vencedora = vencedor.empresa;
        return { status: vencedor.medbox_vence ? "MEDBOX VENCE" : "NEGOCIAR", medbox_vence: vencedor.medbox_vence, tem_preco: true };
    }

    function calcularValorGanhoItem(item) {
        if (!item.medbox_vence || !(item.quantidade > 0) || !(item.menor_valor_vencedor > 0) || !empresaEhMedbox(item.empresa_vencedora)) return 0;
        return item.quantidade * item.menor_valor_vencedor;
    }

    function classeStatus(status) {
        return String(status || "").toLowerCase().replace(/\s+/g, "-").normalize("NFD").replace(/[\u0300-\u036f]/g, "");
    }

    function aplicarStatus(linha, avaliacao) {
        linha.dataset.status = avaliacao.status;
        linha.dataset.medboxVence = avaliacao.medbox_vence ? "1" : "0";
        linha.dataset.temPreco = avaliacao.tem_preco ? "1" : "0";
        linha.classList.toggle("linha-fora-cotacao", avaliacao.status === "FORA DA COTAÇÃO");
        linha.classList.toggle("linha-revisar", avaliacao.status === "REVISAR SKU");
        linha.classList.toggle("linha-sem-preco", avaliacao.status === "SEM PREÇO");
        linha.classList.toggle("linha-ok", avaliacao.status !== "REVISAR SKU" && avaliacao.status !== "SEM PREÇO" && avaliacao.status !== "FORA DA COTAÇÃO");
        const cell = linha.querySelector(".status-cell");
        if (cell) cell.innerHTML = '<span class="status-badge status-' + classeStatus(avaliacao.status) + '">' + avaliacao.status + '</span>';
    }

    function atualizarMenorValor(linha, item) {
        const cell = linha.querySelector(".menor-valor-cell");
        if (!cell) return;
        const strong = cell.querySelector("strong");
        const small = cell.querySelector("small");
        if (strong) strong.textContent = item.menor_valor_vencedor > 0 ? formatarMoedaBR(item.menor_valor_vencedor) : "R$ 0,00";
        if (small) small.textContent = item.empresa_vencedora || "-";
    }

    function lerItemLinha(linha) {
        const menorCusto = parseNumeroBR(valor(linha, ".custo-manual-input"));
        const markup = parseNumeroBR(valor(linha, ".markup-atual-input") || "80");
        const precoMedbox = menorCusto > 0 ? menorCusto * (1 + markup / 100) : 0;
        return {
            linha,
            descricao_original: descricaoOriginal(linha),
            sku_master: valor(linha, ".sku-master-input"),
            categoria: valor(linha, ".categoria-input"),
            quantidade: parseNumeroBR(valor(linha, ".qtd-input")),
            preco_osinfo: parseNumeroBR(valor(linha, ".osinfo-input")),
            ultima_compra: parseNumeroBR(valor(linha, ".ultima-input")),
            menor_preco_ofertado: parseNumeroBR(valor(linha, ".concorrente-input")),
            empresa_melhor_lance: valor(linha, ".empresa-input"),
            menor_custo_encontrado: menorCusto,
            markup_atual: markup,
            preco_medbox: precoMedbox,
            fornecedor_menor_custo: valor(linha, ".fornecedor-input"),
            marca_fabricante: valor(linha, ".fabricante-input"),
            menor_valor_vencedor: 0,
            empresa_vencedora: ""
        };
    }

    function recalcularLinhaLance(linha) {
        if (!linha) return null;
        const item = lerItemLinha(linha);
        const avaliacao = avaliarResultadoItemLance(item);
        item.status = avaliacao.status;
        item.medbox_vence = avaliacao.medbox_vence;
        item.tem_preco = avaliacao.tem_preco;
        item.valor_ganho_medbox = calcularValorGanhoItem(item);

        linha.dataset.quantidade = String(item.quantidade || 0);
        linha.dataset.precoOsinfo = String(item.preco_osinfo || 0);
        linha.dataset.precoMedbox = String(item.preco_medbox || 0);
        linha.dataset.menorCusto = String(item.menor_custo_encontrado || 0);
        linha.dataset.menorValorVencedor = String(item.menor_valor_vencedor || 0);
        linha.dataset.empresaVencedora = item.empresa_vencedora || "";
        linha.dataset.valorGanhoMedbox = String(item.valor_ganho_medbox || 0);
        linha.dataset.operacional = item.quantidade > 0 ? "1" : "0";

        if (item.quantidade > 0) definirValor(linha, ".qtd-input", formatarQuantidadeCotacao(item.quantidade));
        if (item.preco_medbox > 0) definirValor(linha, ".medbox-input", formatarMoedaBR(item.preco_medbox));
        else definirValor(linha, ".medbox-input", "");
        atualizarMenorValor(linha, item);
        aplicarStatus(linha, avaliacao);
        return item;
    }

    function linhasDaGrade() {
        return Array.from(document.querySelectorAll(gradeSelector + " tbody tr"));
    }

    function atualizarKpi(chave, valorTexto) {
        const el = document.querySelector('[data-kpi="' + chave + '"]');
        if (el) el.textContent = valorTexto;
    }

    function recalcularResumoLances() {
        const itens = linhasDaGrade().map(recalcularLinhaLance).filter(Boolean);
        const cotados = itens.filter((item) => item.quantidade > 0);
        const ganhos = cotados.filter((item) => item.medbox_vence);
        const totalGanho = ganhos.reduce((acc, item) => acc + calcularValorGanhoItem(item), 0);
        const percentual = cotados.length ? (ganhos.length / cotados.length) * 100 : 0;
        atualizarKpi("total_itens", String(cotados.length));
        atualizarKpi("itens_com_sku", String(cotados.filter((item) => !!item.sku_master).length));
        atualizarKpi("itens_revisar_sku", String(cotados.filter((item) => item.status === "REVISAR SKU").length));
        atualizarKpi("itens_com_preco_medbox", String(cotados.filter((item) => item.tem_preco).length));
        atualizarKpi("itens_sem_preco", String(cotados.filter((item) => item.status === "SEM PREÇO").length));
        atualizarKpi("itens_ganhos_medbox", String(ganhos.length));
        atualizarKpi("itens_competitivos", String(ganhos.length));
        atualizarKpi("percentual_itens_ganhos", percentual.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + "%");
        atualizarKpi("itens_negociar", String(cotados.filter((item) => item.status === "NEGOCIAR").length));
        atualizarKpi("total_ganho_medbox", formatarMoedaBR(totalGanho));
        atualizarKpi("total_medbox", formatarMoedaBR(totalGanho));
        return { total_itens: cotados.length, itens_ganhos_medbox: ganhos.length, total_ganho_medbox: totalGanho, percentual_itens_ganhos: percentual };
    }

    function criarCaixaSku() {
        if (caixaSku) return caixaSku;
        caixaSku = document.createElement("div");
        caixaSku.id = "medboxSkuAutocompleteBox";
        caixaSku.style.position = "absolute";
        caixaSku.style.zIndex = "999999";
        caixaSku.style.background = "#fff";
        caixaSku.style.border = "1px solid #c8d7ea";
        caixaSku.style.borderRadius = "8px";
        caixaSku.style.boxShadow = "0 8px 24px rgba(15,23,42,.18)";
        caixaSku.style.maxHeight = "280px";
        caixaSku.style.overflowY = "auto";
        caixaSku.style.minWidth = "420px";
        caixaSku.style.display = "none";
        caixaSku.style.fontSize = "12px";
        document.body.appendChild(caixaSku);
        return caixaSku;
    }

    function esconderSugestoesSku() {
        if (!caixaSku) return;
        caixaSku.innerHTML = "";
        caixaSku.style.display = "none";
    }

    function posicionarCaixaSku(input) {
        const caixa = criarCaixaSku();
        const r = input.getBoundingClientRect();
        caixa.style.left = (window.scrollX + r.left) + "px";
        caixa.style.top = (window.scrollY + r.bottom + 4) + "px";
        caixa.style.width = Math.max(r.width, 420) + "px";
    }

    function aplicarSugestaoSku(linha, sugestao) {
        if (!linha || !sugestao) return;
        const sku = sugestao.sku_master || sugestao.sku || sugestao.produto_padrao || "";
        const categoriaAtual = valor(linha, ".categoria-input");
        definirValor(linha, ".sku-master-input", sku);
        if (!categoriaAtual && sugestao.categoria) definirValor(linha, ".categoria-input", sugestao.categoria);
        definirValor(linha, ".fornecedor-input", sugestao.fornecedor_menor_custo || sugestao.fornecedor || "");
        definirValor(linha, ".fabricante-input", sugestao.marca_fabricante || sugestao.marca || sugestao.fabricante || "");
        const custo = sugestao.menor_custo_unitario ?? sugestao.menor_custo ?? sugestao.preco;
        definirValor(linha, ".custo-manual-input", custo !== undefined && custo !== null && custo !== "" && Number(custo) > 0 ? formatarMoedaBR(custo) : "");
        recalcularLinhaLance(linha);
        recalcularResumoLances();
        esconderSugestoesSku();
    }

    function renderizarSugestoesSku(input, sugestoes) {
        const caixa = criarCaixaSku();
        posicionarCaixaSku(input);
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
        sugestoes.slice(0, 12).forEach((sugestao) => {
            const item = document.createElement("button");
            item.type = "button";
            item.style.display = "block";
            item.style.width = "100%";
            item.style.textAlign = "left";
            item.style.padding = "9px 12px";
            item.style.border = "0";
            item.style.borderBottom = "1px solid #edf2f7";
            item.style.background = "#fff";
            item.style.cursor = "pointer";
            const sku = sugestao.sku_master || sugestao.sku || sugestao.produto_padrao || "";
            const custo = sugestao.menor_custo_unitario ?? sugestao.menor_custo ?? sugestao.preco;
            item.innerHTML = '<strong style="color:#003b5c;">' + sku + '</strong><br><span style="font-size:11px;color:#667085;">' +
                (sugestao.categoria ? 'Categoria: ' + sugestao.categoria + ' | ' : '') +
                (sugestao.fornecedor_menor_custo || sugestao.fornecedor ? 'Fornecedor: ' + (sugestao.fornecedor_menor_custo || sugestao.fornecedor) + ' | ' : '') +
                (sugestao.marca_fabricante || sugestao.marca ? 'Marca: ' + (sugestao.marca_fabricante || sugestao.marca) + ' | ' : '') +
                (custo ? 'Custo: ' + formatarMoedaBR(custo) + ' | ' : 'Sem preço | ') +
                (sugestao.score !== undefined ? 'Score: ' + sugestao.score : '') + '</span>';
            item.addEventListener("mousedown", (event) => {
                event.preventDefault();
                aplicarSugestaoSku(input.closest("tr"), sugestao);
            });
            caixa.appendChild(item);
        });
        caixa.style.display = "block";
    }

    async function buscarSugestoesSku(input) {
        inputSkuAtual = input;
        const linha = input.closest("tr");
        const digitado = String(input.value || "").trim();
        const termo = digitado.length >= 2 ? digitado : descricaoOriginal(linha);
        if (!termo || termo.length < 2) { esconderSugestoesSku(); return; }
        try {
            const resp = await fetch("/cotacoes/lances/sugerir-skus?q=" + encodeURIComponent(termo), { method: "GET" });
            const data = await resp.json();
            renderizarSugestoesSku(input, data && data.ok ? (data.sugestoes || []) : []);
        } catch (erro) {
            console.error("Erro no autocomplete SKU_MASTER:", erro);
            esconderSugestoesSku();
        }
    }

    function aoInput(event) {
        const campo = event.target;
        if (!campo || !campo.closest) return;
        const linha = campo.closest(gradeSelector + " tbody tr");
        if (!linha) return;
        if (campo.matches(".sku-master-input")) {
            clearTimeout(timerSku);
            timerSku = setTimeout(() => buscarSugestoesSku(campo), 250);
        }
        if (campo.matches(".sku-master-input,.qtd-input,.osinfo-input,.ultima-input,.concorrente-input,.empresa-input,.custo-manual-input,.markup-atual-input")) {
            recalcularLinhaLance(linha);
            recalcularResumoLances();
        }
    }

    function aoChange(event) {
        const campo = event.target;
        if (!campo || !campo.closest) return;
        const linha = campo.closest(gradeSelector + " tbody tr");
        if (!linha) return;
        if (campo.matches(".sku-sugestao-select")) {
            const opt = campo.selectedOptions && campo.selectedOptions[0];
            if (opt && opt.value) aplicarSugestaoSku(linha, { sku_master: opt.value, categoria: opt.dataset.categoria, fornecedor_menor_custo: opt.dataset.fornecedor, marca_fabricante: opt.dataset.fabricante, menor_custo_unitario: opt.dataset.custo });
            return;
        }
        if (campo.matches(".sku-master-input,.qtd-input,.osinfo-input,.ultima-input,.concorrente-input,.empresa-input,.custo-manual-input,.markup-atual-input,.categoria-input,.fornecedor-input,.fabricante-input")) {
            recalcularLinhaLance(linha);
            recalcularResumoLances();
        }
    }

    document.addEventListener("input", aoInput, true);
    document.addEventListener("change", aoChange, true);
    document.addEventListener("focusin", (event) => {
        if (event.target && event.target.matches && event.target.matches(".sku-master-input")) {
            clearTimeout(timerSku);
            timerSku = setTimeout(() => buscarSugestoesSku(event.target), 150);
        }
    }, true);
    document.addEventListener("keydown", (event) => { if (event.key === "Escape") esconderSugestoesSku(); }, true);
    document.addEventListener("click", (event) => {
        if (!caixaSku) return;
        if (event.target === inputSkuAtual || caixaSku.contains(event.target)) return;
        esconderSugestoesSku();
    }, true);
    window.addEventListener("scroll", () => { if (inputSkuAtual && caixaSku && caixaSku.style.display !== "none") posicionarCaixaSku(inputSkuAtual); }, true);
    window.addEventListener("resize", () => { if (inputSkuAtual && caixaSku && caixaSku.style.display !== "none") posicionarCaixaSku(inputSkuAtual); });

    window.parseNumeroBR = parseNumeroBR;
    window.formatarMoedaBR = formatarMoedaBR;
    window.formatarQuantidadeCotacao = formatarQuantidadeCotacao;
    window.empresaEhMedbox = empresaEhMedbox;
    window.calcularValorGanhoItem = calcularValorGanhoItem;
    window.avaliarResultadoItemLance = avaliarResultadoItemLance;
    window.recalcularLinhaLance = recalcularLinhaLance;
    window.recalcularResumoLances = recalcularResumoLances;
    window.buscarSugestoesSku = buscarSugestoesSku;
    window.aplicarSugestaoSku = aplicarSugestaoSku;
    window.MEDBOX_recalcularLinhaLance = recalcularLinhaLance;
    window.MEDBOX_recalcularResumoLances = recalcularResumoLances;

    document.addEventListener("DOMContentLoaded", recalcularResumoLances);
    window.addEventListener("load", recalcularResumoLances);
    setTimeout(recalcularResumoLances, 250);
})();
