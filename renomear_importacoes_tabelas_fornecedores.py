from pathlib import Path
from datetime import datetime

arquivos = [
    Path("templates/base.html"),
    Path("templates/importacoes.html"),
]

for path in arquivos:
    if not path.exists():
        raise SystemExit(f"ERRO: arquivo não encontrado: {path}")

    texto = path.read_text(encoding="utf-8", errors="ignore")

    backup = path.with_suffix(path.suffix + ".bak_renomeia_importacoes_" + datetime.now().strftime("%Y%m%d_%H%M%S"))
    backup.write_text(texto, encoding="utf-8")
    print(f"Backup criado: {backup}")

    if path.name == "base.html":
        texto = texto.replace(
            '<span class="nav-icon">⇩</span> Importações',
            '<span class="nav-icon">⇩</span> Importar Tabelas Fornecedores'
        )

    if path.name == "importacoes.html":
        texto = texto.replace(
            "{% block title %}Importações{% endblock %}",
            "{% block title %}Importar Tabelas Fornecedores{% endblock %}"
        )

        texto = texto.replace(
            "{% block subtitle %}Importe tabelas de preços de qualquer fornecedor ou fabricante.{% endblock %}",
            "{% block subtitle %}Importe tabelas de preços de fornecedores, distribuidores, fabricantes e XML de NF-e.{% endblock %}"
        )

        texto = texto.replace(
            "<h3>Importar Tabela de Preços</h3>",
            "<h3>Importar Tabela de Preços de Fornecedor</h3>"
        )

    path.write_text(texto, encoding="utf-8")

print("OK: módulo Importações renomeado visualmente para Importar Tabelas Fornecedores.")
