import shutil
from pathlib import Path
from datetime import datetime

ROOT = Path(".").resolve()
REL = ROOT / "relatorio_organizar_raiz.txt"

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
    "organizar_raiz.py",
}

pastas_destino = [
    ROOT / "scripts" / "diagnosticos",
    ROOT / "scripts" / "aplicados",
    ROOT / "scripts" / "logs",
    ROOT / "scripts" / "previas",
]

for pasta in pastas_destino:
    pasta.mkdir(parents=True, exist_ok=True)

def classificar_py(nome):
    n = nome.lower()

    if nome in preservar:
        return None

    if n.startswith(("diagnosticar_", "verificar_", "gerar_relatorio_", "auditar_", "inspecionar_", "listar_")):
        return ROOT / "scripts" / "diagnosticos"

    if n.startswith(("previa_", "previsualizar_")):
        return ROOT / "scripts" / "previas"

    if n.startswith(("aplicar_", "corrigir_", "ajustar_", "normalizar_", "migrar_", "reparar_")):
        return ROOT / "scripts" / "aplicados"

    return None

def classificar_arquivo(p):
    nome = p.name

    if nome in preservar:
        return None

    if p.suffix.lower() == ".py":
        return classificar_py(nome)

    if p.suffix.lower() in {".txt", ".csv", ".log"}:
        return ROOT / "scripts" / "logs"

    return None

movidos = []
ignorados = []

for p in sorted(ROOT.iterdir(), key=lambda x: x.name.lower()):
    if p.is_dir():
        continue

    destino_dir = classificar_arquivo(p)

    if not destino_dir:
        ignorados.append(p.name)
        continue

    destino_dir.mkdir(parents=True, exist_ok=True)
    destino = destino_dir / p.name

    if destino.exists():
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        destino = destino_dir / f"{p.stem}__duplicado_{stamp}{p.suffix}"

    shutil.move(str(p), str(destino))
    movidos.append((p.name, str(destino.relative_to(ROOT))))

linhas = []
linhas.append("===== ORGANIZAÇÃO DA RAIZ MEDBOX_V3_ZERO =====")
linhas.append("")
linhas.append(f"Data/hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
linhas.append(f"Raiz: {ROOT}")
linhas.append("")
linhas.append("Arquivos apagados: NÃO")
linhas.append("Banco alterado: NÃO")
linhas.append("")
linhas.append(f"Total movido: {len(movidos)}")
linhas.append(f"Total ignorado/preservado: {len(ignorados)}")
linhas.append("")
linhas.append("===== ARQUIVOS MOVIDOS =====")

for origem, destino in movidos:
    linhas.append(f"{origem} -> {destino}")

linhas.append("")
linhas.append("===== ARQUIVOS PRESERVADOS OU REVISÃO MANUAL =====")

for nome in ignorados:
    linhas.append(nome)

linhas.append("")
linhas.append("===== DESTINOS =====")
linhas.append("scripts/diagnosticos/")
linhas.append("scripts/aplicados/")
linhas.append("scripts/logs/")
linhas.append("scripts/previas/")
linhas.append("")
linhas.append("VEREDITO: ORGANIZACAO_CONCLUIDA_SEM_APAGAR_ARQUIVOS")

REL.write_text("\n".join(linhas), encoding="utf-8")

print("\n".join(linhas))
print("")
print("Relatório:", REL)
