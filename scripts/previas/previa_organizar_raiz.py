import os
from pathlib import Path
from datetime import datetime

ROOT = Path(".").resolve()
REL = ROOT / "previa_organizar_raiz.txt"

preservar = {
    "app.py",
    "requirements.txt",
    "README.md",
    "AGENTS.md",
    "CLAUDE.md",
    "RETOMAR.md",
    "padronizar_skus.py",
    "corrigir_marcas.py",
    "gerar_skus.py",
}

pastas_ignorar = {
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    "env",
    "core",
    "templates",
    "static",
    "uploads",
    "banco",
    "scripts",
    "tests",
    "blueprints",
}

def classificar_py(nome):
    n = nome.lower()

    if nome in preservar:
        return "PRESERVAR"

    if n.startswith(("diagnosticar_", "verificar_", "gerar_relatorio_", "auditar_", "inspecionar_", "listar_")):
        return "scripts/diagnosticos"

    if n.startswith(("previa_", "previsualizar_")):
        return "scripts/previas"

    if n.startswith(("aplicar_", "corrigir_", "ajustar_", "normalizar_", "migrar_", "reparar_")):
        return "scripts/aplicados"

    return "REVISAR_MANUALMENTE"

def classificar_arquivo(p):
    nome = p.name

    if nome in preservar:
        return "PRESERVAR"

    if p.suffix.lower() == ".py":
        return classificar_py(nome)

    if p.suffix.lower() in {".txt", ".csv", ".log"}:
        return "scripts/logs"

    if p.suffix.lower() in {".bak", ".old"}:
        return "scripts/backups_manuais"

    return "IGNORAR"

linhas = []
linhas.append("===== PRÉVIA ORGANIZAÇÃO DA RAIZ =====")
linhas.append("")
linhas.append(f"Data/hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
linhas.append(f"Raiz analisada: {ROOT}")
linhas.append("")
linhas.append("Banco alterado: NÃO")
linhas.append("Arquivos movidos: NÃO")
linhas.append("")

contagem = {}

for p in sorted(ROOT.iterdir(), key=lambda x: x.name.lower()):
    if p.is_dir():
        if p.name in pastas_ignorar:
            continue
        destino = "REVISAR_DIRETORIO"
    else:
        destino = classificar_arquivo(p)

    if destino in {"IGNORAR", "PRESERVAR"}:
        continue

    contagem[destino] = contagem.get(destino, 0) + 1
    linhas.append(f"{p.name} -> {destino}/")

linhas.append("")
linhas.append("===== RESUMO =====")
for destino, qtd in sorted(contagem.items()):
    linhas.append(f"{destino}: {qtd}")

linhas.append("")
linhas.append("===== OBSERVAÇÃO =====")
linhas.append("Esta é apenas uma prévia. Nenhum arquivo foi movido.")
linhas.append("Arquivos em REVISAR_MANUALMENTE não serão movidos automaticamente sem validação.")
linhas.append("")
linhas.append("VEREDITO: PREVIA_GERADA_SEM_ALTERAR_ARQUIVOS")

REL.write_text("\n".join(linhas), encoding="utf-8")

print("\n".join(linhas))
print("")
print("Relatório:", REL)
