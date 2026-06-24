from pathlib import Path

base = Path("DIAG_MAPA_PRECOS_CLIENTES")

arquivos = [
    "03_app_buscas.txt",
    "02_core_mapa_precos_clientes.txt",
    "04_templates_encontrados.txt",
    "TPL_mapa_precos_clientes.html.txt",
    "TPL_mapa_precos_clientes_importar.html.txt",
    "06_busca_global_sku_autocomplete.txt",
]

saida = []

for nome in arquivos:
    path = base / nome
    saida.append("=" * 120)
    saida.append(nome)
    saida.append("=" * 120)

    if path.exists():
        saida.append(path.read_text(encoding="utf-8", errors="ignore"))
    else:
        saida.append(f"ARQUIVO NÃO ENCONTRADO: {path}")

    saida.append("\n\n")

out = Path("DIAGNOSTICO_MAPA_PRECOS_CLIENTES_RESUMIDO.txt")
out.write_text("\n".join(saida), encoding="utf-8")

print("OK: gerado DIAGNOSTICO_MAPA_PRECOS_CLIENTES_RESUMIDO.txt")
