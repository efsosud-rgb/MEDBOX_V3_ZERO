from pathlib import Path
from datetime import datetime

path = Path("static/js/cotacao_lances.js")
js = path.read_text(encoding="utf-8", errors="ignore")

backup = path.with_suffix(path.suffix + ".bak_bloqueia_gerar_em_edicao_" + datetime.now().strftime("%Y%m%d_%H%M%S"))
backup.write_text(js, encoding="utf-8")
print(f"Backup criado: {backup}")

bloco = r'''

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
'''

if "MEDBOX - BLOQUEIO DEFINITIVO DE GERAÇÃO DUPLICADA EM EDIÇÃO" not in js:
    js = js.rstrip() + "\n\n" + bloco + "\n"
else:
    print("Bloco já existe. Não dupliquei.")

path.write_text(js, encoding="utf-8")
print("OK: bloqueio definitivo aplicado.")
