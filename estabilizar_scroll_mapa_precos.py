from pathlib import Path
from datetime import datetime
import re

path = Path("templates/mapa_precos_clientes.html")
txt = path.read_text(encoding="utf-8", errors="ignore")

backup = path.with_suffix(path.suffix + ".bak_estabiliza_scroll_mapa_" + datetime.now().strftime("%Y%m%d_%H%M%S"))
backup.write_text(txt, encoding="utf-8")
print(f"Backup criado: {backup}")

# Remove scripts antigos de sticky que estão causando deslocamento da tela.
padroes = [
    r'<script>\s*/\* MAPA ERP - STICKY FINAL CORRIGIDO \*/.*?</script>\s*',
    r'<script>\s*/\* ============================================================\s*MAPA ERP - COLUNAS FIXAS \+ FILTROS DE ORDENAÇÃO.*?</script>\s*',
]

removidos = 0
for p in padroes:
    txt, qtd = re.subn(p, "", txt, flags=re.S)
    removidos += qtd

print("Scripts sticky removidos:", removidos)

# CSS final para impedir rolagem horizontal da página e concentrar a rolagem no quadro da tabela.
css_final = r'''
    /* ============================================================
       MAPA ERP - SCROLL ESTÁVEL FINAL
       A página não rola para o lado.
       A rolagem horizontal fica somente dentro da área da tabela.
    ============================================================ */

    html,
    body {
        overflow-x: hidden !important;
        max-width: 100vw !important;
    }

    .content,
    .main-content,
    .page-content,
    main {
        overflow-x: hidden !important;
        max-width: 100% !important;
    }

    .mpc-panel {
        width: 100% !important;
        max-width: 100% !important;
        overflow: hidden !important;
        box-sizing: border-box !important;
    }

    .mpc-table-wrap {
        width: 100% !important;
        max-width: 100% !important;
        overflow-x: auto !important;
        overflow-y: auto !important;
        max-height: calc(100vh - 245px) !important;
        position: relative !important;
        border-top: 1px solid #dce6f1 !important;
        scrollbar-width: auto;
    }

    .mpc-table-wrap::-webkit-scrollbar {
        height: 14px;
        width: 14px;
    }

    .mpc-table-wrap::-webkit-scrollbar-track {
        background: #e5edf7;
        border-radius: 999px;
    }

    .mpc-table-wrap::-webkit-scrollbar-thumb {
        background: #00486C;
        border-radius: 999px;
        border: 3px solid #e5edf7;
    }

    .mpc-table {
        width: max-content !important;
        min-width: 100% !important;
        table-layout: fixed;
    }

    .mpc-table th {
        position: sticky !important;
        top: 0 !important;
        z-index: 30 !important;
    }

    .mpc-table thead tr:nth-child(2) th {
        top: 31px !important;
        z-index: 31 !important;
    }

    /* Remove qualquer sticky lateral antigo */
    .mpc-sticky-col {
        position: static !important;
        left: auto !important;
        z-index: auto !important;
        box-shadow: none !important;
    }

    .mpc-filter-btn {
        margin-left: 5px;
        width: 18px;
        height: 18px;
        border: 1px solid rgba(255,255,255,.55);
        border-radius: 5px;
        background: rgba(255,255,255,.20);
        color: #fff;
        font-size: 10px;
        cursor: pointer;
        font-weight: 900;
        vertical-align: middle;
    }

    .mpc-client-head .mpc-filter-btn,
    .mpc-subhead .mpc-filter-btn {
        color: #0f172a;
        border-color: rgba(15,23,42,.25);
        background: rgba(255,255,255,.75);
    }

    .mpc-filter-btn.active {
        background: #D80024 !important;
        color: #fff !important;
        border-color: #D80024 !important;
    }

    .mpc-sort-menu {
        position: fixed;
        min-width: 190px;
        background: #ffffff;
        border: 1px solid #cbd5e1;
        border-radius: 12px;
        box-shadow: 0 18px 38px rgba(15, 23, 42, .22);
        z-index: 99999;
        overflow: hidden;
        display: none;
    }

    .mpc-sort-menu button {
        display: block;
        width: 100%;
        border: none;
        background: white;
        padding: 10px 12px;
        text-align: left;
        font-size: 12px;
        font-weight: 800;
        cursor: pointer;
        color: #0f172a;
    }

    .mpc-sort-menu button:hover {
        background: #eff6ff;
    }

    .mpc-sort-menu .danger {
        color: #D80024;
    }
'''

if "MAPA ERP - SCROLL ESTÁVEL FINAL" not in txt:
    txt = txt.replace("</style>", css_final + "\n</style>", 1)
    print("CSS de scroll estável inserido.")
else:
    print("CSS de scroll estável já existia.")

# Script apenas para filtros/ordenação. Sem sticky lateral.
js_filtros = r'''
<script>
document.addEventListener('DOMContentLoaded', function() {
    const table = document.querySelector('.mpc-table');
    if (!table) return;

    const tbody = table.querySelector('tbody');
    if (!tbody) return;

    function textoCelula(td) {
        if (!td) return '';
        const input = td.querySelector('input, select, textarea');
        if (input) {
            if (input.tagName === 'SELECT') {
                return input.options[input.selectedIndex]?.text || input.value || '';
            }
            return input.value || '';
        }
        return td.innerText || td.textContent || '';
    }

    function numeroBR(valor) {
        let txt = String(valor || '').trim();

        if (!txt) return 0;

        txt = txt
            .replace(/\s/g, '')
            .replace(/R\$/gi, '')
            .replace(/[^\d,.\-]/g, '');

        if (!txt) return 0;

        if (txt.includes(',') && txt.includes('.')) {
            txt = txt.replace(/\./g, '').replace(',', '.');
        } else if (txt.includes(',')) {
            txt = txt.replace(',', '.');
        } else if ((txt.match(/\./g) || []).length === 1) {
            const partes = txt.split('.');
            if (partes[1] && partes[1].length === 3) {
                txt = partes.join('');
            }
        } else {
            txt = txt.replace(/\./g, '');
        }

        const n = Number(txt);
        return Number.isFinite(n) ? n : 0;
    }

    function headerToColumn(th) {
        const row = th.parentElement;
        const rows = Array.from(table.querySelectorAll('thead tr'));
        const rowIndex = rows.indexOf(row);
        const cells = Array.from(row.children);
        const idx = cells.indexOf(th);
        const texto = (th.innerText || '').toUpperCase();

        if (rowIndex === 0) {
            if (texto.includes('CATEGORIA')) return 0;
            if (texto.includes('DESCRIÇÃO') || texto.includes('DESCRICAO')) return 1;
            if (texto.includes('SKU')) return 2;
            if (texto.includes('DEMANDA')) return 3;
            if (texto.includes('MENOR')) return 10;
            if (texto.includes('MÉDIO') || texto.includes('MEDIO')) return 11;
            if (texto.includes('FATURAMENTO')) return 12;
            return null;
        }

        if (rowIndex === 1) {
            if (idx < 6) return 4 + idx;
            return 13 + (idx - 6);
        }

        return null;
    }

    function tipoColuna(colIndex) {
        const th = table.querySelector(`thead th[data-col-index="${colIndex}"]`);
        const thText = th ? (th.innerText || '').toUpperCase() : '';
        const primeiraLinha = tbody.querySelector('tr');
        const texto = textoCelula(primeiraLinha ? primeiraLinha.children[colIndex] : null);

        if (
            texto.includes('R$') ||
            thText.includes('QUANT') ||
            thText.includes('DEMANDA') ||
            thText.includes('PREÇO') ||
            thText.includes('PRECO') ||
            thText.includes('VALOR') ||
            thText.includes('FATURAMENTO') ||
            thText.includes('MARKUP')
        ) {
            return 'number';
        }

        if (/^-?\d{1,3}(\.\d{3})*(,\d+)?$/.test(texto)) return 'number';
        if (/^-?\d+([,.]\d+)?$/.test(texto)) return 'number';

        return 'text';
    }

    function linhasOrdenaveis() {
        return Array.from(tbody.querySelectorAll('tr')).filter(tr => tr.children.length > 3);
    }

    function ordenarTabela(colIndex, direcao) {
        const tipo = tipoColuna(colIndex);
        const linhas = linhasOrdenaveis();

        linhas.sort((a, b) => {
            const va = textoCelula(a.children[colIndex]);
            const vb = textoCelula(b.children[colIndex]);

            if (tipo === 'number') {
                const na = numeroBR(va);
                const nb = numeroBR(vb);
                return direcao === 'asc' ? na - nb : nb - na;
            }

            return direcao === 'asc'
                ? va.localeCompare(vb, 'pt-BR', { sensitivity: 'base' })
                : vb.localeCompare(va, 'pt-BR', { sensitivity: 'base' });
        });

        linhas.forEach(tr => tbody.appendChild(tr));

        document.querySelectorAll('.mpc-filter-btn').forEach(btn => btn.classList.remove('active'));

        const th = table.querySelector(`thead th[data-col-index="${colIndex}"]`);
        if (th) {
            const btn = th.querySelector('.mpc-filter-btn');
            if (btn) btn.classList.add('active');
        }
    }

    function criarMenu() {
        let menu = document.querySelector('.mpc-sort-menu');

        if (!menu) {
            menu = document.createElement('div');
            menu.className = 'mpc-sort-menu';
            menu.innerHTML = `
                <button data-dir="asc" data-kind="text">A → Z</button>
                <button data-dir="desc" data-kind="text">Z → A</button>
                <button data-dir="asc" data-kind="number">Menor → Maior</button>
                <button data-dir="desc" data-kind="number">Maior → Menor</button>
                <button class="danger" data-dir="clear">Fechar</button>
            `;
            document.body.appendChild(menu);
        }

        return menu;
    }

    function adicionarFiltros() {
        table.querySelectorAll('thead th').forEach(th => {
            if (th.querySelector('.mpc-filter-btn')) return;

            const colIndex = headerToColumn(th);
            if (colIndex === null || colIndex === undefined) return;

            th.dataset.colIndex = String(colIndex);

            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'mpc-filter-btn';
            btn.textContent = '⇅';
            btn.title = 'Ordenar';

            btn.addEventListener('click', ev => {
                ev.stopPropagation();

                const menu = criarMenu();
                const tipo = tipoColuna(colIndex);

                menu.querySelectorAll('button').forEach(item => {
                    const kind = item.dataset.kind;
                    item.style.display = (!kind || kind === tipo) ? 'block' : 'none';
                });

                const rect = btn.getBoundingClientRect();
                menu.style.left = rect.left + 'px';
                menu.style.top = (rect.bottom + 6) + 'px';
                menu.style.display = 'block';
                menu.dataset.colIndex = String(colIndex);
            });

            th.appendChild(btn);
        });
    }

    document.addEventListener('click', ev => {
        const menu = document.querySelector('.mpc-sort-menu');

        const item = ev.target.closest('.mpc-sort-menu button');
        if (item && menu) {
            const dir = item.dataset.dir;

            if (dir === 'clear') {
                menu.style.display = 'none';
                return;
            }

            const colIndex = Number(menu.dataset.colIndex || 0);
            ordenarTabela(colIndex, dir);
            menu.style.display = 'none';
            return;
        }

        if (menu && !menu.contains(ev.target) && !ev.target.classList.contains('mpc-filter-btn')) {
            menu.style.display = 'none';
        }
    });

    adicionarFiltros();
});
</script>
'''

if "MAPA ERP - FILTROS SEM STICKY LATERAL" not in js_filtros:
    js_filtros = js_filtros.replace(
        "<script>",
        "<script>\n/* MAPA ERP - FILTROS SEM STICKY LATERAL */",
        1
    )

if "MAPA ERP - FILTROS SEM STICKY LATERAL" not in txt:
    pos = txt.rfind("{% endblock %}")
    if pos == -1:
        raise SystemExit("ERRO: não encontrei endblock final.")
    txt = txt[:pos] + js_filtros + "\n" + txt[pos:]
    print("JS de filtros sem sticky lateral inserido.")
else:
    print("JS de filtros sem sticky lateral já existia.")

path.write_text(txt, encoding="utf-8")
print("OK: mapa estabilizado.")
