from pathlib import Path
from datetime import datetime
import re

HTML = Path("templates/sku_master_auditoria.html")

if not HTML.exists():
    raise FileNotFoundError(HTML)

texto = HTML.read_text(encoding="utf-8")

backup = HTML.with_name(
    HTML.name + ".bak_cadastro_rapido_sku_" + datetime.now().strftime("%Y%m%d_%H%M%S")
)
backup.write_text(texto, encoding="utf-8")

CSS = r'''
<style id="sku-cadastro-rapido-css">
.sku-quick-box {
    margin: 0 0 15px 0;
    padding: 12px;
    background: #f8fafc;
    border: 1px solid #dbe7f3;
    border-radius: 8px;
}

.sku-quick-title {
    font-size: 0.78rem;
    font-weight: 900;
    color: #00486C;
    text-transform: uppercase;
    margin-bottom: 8px;
}

.sku-quick-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin: 8px 0;
}

.sku-quick-btn {
    border: none;
    border-radius: 8px;
    padding: 7px 10px;
    font-size: 0.78rem;
    font-weight: 800;
    cursor: pointer;
    background: #00486C;
    color: #fff;
}

.sku-quick-btn.red {
    background: #D80024;
}

.sku-quick-btn.green {
    background: #15803d;
}

.sku-quick-btn.gray {
    background: #475569;
}

.sku-quick-grid {
    display: grid;
    grid-template-columns: 1fr auto;
    gap: 8px;
    align-items: end;
}

.sku-quick-grid input {
    width: 100%;
    padding: 8px;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    font-weight: 700;
    text-transform: uppercase;
}

.sku-quick-hint {
    font-size: 0.74rem;
    color: #64748b;
    margin-top: 6px;
    line-height: 1.35;
}
</style>
'''

BLOCO = r'''
            <div class="sku-quick-box" id="sku-cadastro-rapido-box">
                <div class="sku-quick-title">Cadastro rápido SKU_MASTER</div>

                <div class="sku-quick-actions">
                    <button type="button" class="sku-quick-btn gray" onclick="copiarDescricaoOriginalSku()">Copiar descrição original</button>
                    <button type="button" class="sku-quick-btn" onclick="usarDescricaoOriginalComoSku()">Usar descrição original como SKU_MASTER</button>
                    <button type="button" class="sku-quick-btn green" onclick="definirCategoriaRapidaSku('MEDICAMENTOS')">MEDICAMENTO</button>
                    <button type="button" class="sku-quick-btn green" onclick="definirCategoriaRapidaSku('CORRELATOS')">CORRELATO</button>
                </div>

                <label style="display:block; font-weight:700; margin-bottom:5px;">Descrição exata do fornecedor/fabricante</label>
                <div class="sku-quick-grid">
                    <input type="text" id="edit-descricao-exata-fornecedor" placeholder="Cole aqui a descrição exata do fabricante/fornecedor">
                    <button type="button" class="sku-quick-btn red" onclick="aplicarDescricaoExataNoSkuMaster()">Aplicar no SKU_MASTER</button>
                </div>

                <div class="sku-quick-hint">
                    Fluxo recomendado: copie a descrição original, pesquise fabricante/marca, cole a descrição exata validada, preencha fabricante e categoria, depois salve.
                </div>
            </div>
'''

JS = r'''
<script id="sku-cadastro-rapido-js">
(function () {
    function textoOriginalProduto() {
        const el = document.getElementById('display-produto-padrao');
        return (el && el.textContent ? el.textContent : '').trim().toUpperCase();
    }

    function setValor(id, valor) {
        const el = document.getElementById(id);
        if (!el) return;
        el.value = String(valor || '').trim().toUpperCase();
        el.dispatchEvent(new Event('change', { bubbles: true }));
    }

    window.copiarDescricaoOriginalSku = async function () {
        const texto = textoOriginalProduto();
        if (!texto) return;

        try {
            await navigator.clipboard.writeText(texto);
            alert('Descrição original copiada.');
        } catch (e) {
            const campo = document.getElementById('edit-descricao-exata-fornecedor');
            if (campo) {
                campo.value = texto;
                campo.select();
            }
            alert('Não consegui copiar automaticamente. A descrição foi colocada no campo para você copiar.');
        }
    };

    window.usarDescricaoOriginalComoSku = function () {
        const texto = textoOriginalProduto();
        if (!texto) return;

        setValor('edit-sku-master', texto);

        const campoExata = document.getElementById('edit-descricao-exata-fornecedor');
        if (campoExata && !campoExata.value) {
            campoExata.value = texto;
        }
    };

    window.aplicarDescricaoExataNoSkuMaster = function () {
        const campo = document.getElementById('edit-descricao-exata-fornecedor');
        const texto = campo ? campo.value.trim().toUpperCase() : '';

        if (!texto) {
            alert('Cole primeiro a descrição exata do fornecedor/fabricante.');
            return;
        }

        setValor('edit-sku-master', texto);
    };

    window.definirCategoriaRapidaSku = function (categoria) {
        setValor('edit-categoria', categoria);
    };

    const antigoAbrir = window.abrirModalEdicao;
    if (typeof antigoAbrir === 'function') {
        window.abrirModalEdicao = function (btn) {
            antigoAbrir(btn);

            const campoExata = document.getElementById('edit-descricao-exata-fornecedor');
            if (campoExata) {
                campoExata.value = '';
                setTimeout(() => campoExata.focus(), 150);
            }
        };
    }

    document.addEventListener('keydown', function (ev) {
        if (ev.ctrlKey && ev.key === 'Enter') {
            const modal = document.getElementById('modal-edicao');
            if (modal && modal.style.display !== 'none') {
                const form = document.getElementById('form-edicao');
                if (form) {
                    ev.preventDefault();
                    form.requestSubmit();
                }
            }
        }
    });
})();
</script>
'''

# Remove versões anteriores
texto = re.sub(r'\n<style id="sku-cadastro-rapido-css">.*?</style>', '', texto, flags=re.DOTALL)
texto = re.sub(r'\n<script id="sku-cadastro-rapido-js">.*?</script>', '', texto, flags=re.DOTALL)
texto = re.sub(r'\n\s*<div class="sku-quick-box" id="sku-cadastro-rapido-box">.*?</div>\s*</div>', lambda m: m.group(0), texto, flags=re.DOTALL)

# Insere CSS no início do template, após block content se existir
if "{% block content %}" in texto:
    texto = texto.replace("{% block content %}", "{% block content %}\n" + CSS, 1)
else:
    texto = CSS + "\n" + texto

# Insere bloco depois da referência fixa do produto
marcador = '''            <div style="margin-bottom:15px; padding:10px; background:#f8fafc; border:1px solid #e2e8f0; border-radius:4px;">
                <label style="display:block; font-weight:700; margin-bottom:2px; color:#64748b; font-size:0.75rem; text-transform:uppercase;">Produto Padrao (Referencia Fixa)</label>
                <div id="display-produto-padrao" style="font-weight:500; color:#334155;"></div>
            </div>'''

if marcador not in texto:
    raise RuntimeError("Não localizei o bloco Produto Padrao no modal. Não apliquei alteração para evitar quebrar a tela.")

texto = texto.replace(marcador, marcador + "\n" + BLOCO, 1)

# Insere JS antes do endblock
if "{% endblock %}" in texto:
    texto = texto.replace("{% endblock %}", JS + "\n{% endblock %}")
else:
    texto = texto + "\n" + JS

HTML.write_text(texto, encoding="utf-8")

print("Backup criado:", backup)
print("OK: Cadastro rápido adicionado ao modal da Auditoria SKU Master.")
print("Atalhos:")
print("- Copiar descrição original")
print("- Usar descrição original como SKU_MASTER")
print("- Campo descrição exata fornecedor/fabricante")
print("- Botões MEDICAMENTO/CORRELATO")
print("- CTRL + ENTER salva o modal")
