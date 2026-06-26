"""Diagnostico das dependencias PDF/navegacao da FASE 2.14E-B.

Nao baixa bases, nao executa captura e nao acessa fontes externas. Apenas verifica
comandos locais, importacoes Python e existencia provavel do Chromium Playwright.
"""

from __future__ import annotations

import csv
import os
import shutil
import subprocess
from importlib import metadata
from pathlib import Path

SAIDA = Path("data/dicionario_mestre/processado/diagnostico_dependencias_pdf_navegacao.csv")
JAVA_FALLBACK = Path(r"C:\Program Files\Eclipse Adoptium\jdk-21.0.11.10-hotspot\bin\java.exe")
GS_DIRS = [Path(r"C:\Program Files\gs"), Path(r"C:\Program Files (x86)\gs")]


def executar(comando: list[str]) -> tuple[str, str]:
    try:
        resultado = subprocess.run(comando, capture_output=True, text=True, timeout=30, check=False)
    except FileNotFoundError as exc:
        return "PENDENTE", f"nao encontrado: {exc}"
    except Exception as exc:  # noqa: BLE001 - diagnostico deve registrar falhas locais
        return "PENDENTE", f"{type(exc).__name__}: {exc}"

    saida = " ".join((resultado.stdout + " " + resultado.stderr).split())
    if resultado.returncode == 0:
        return "OK", saida
    return "PENDENTE", saida or f"returncode={resultado.returncode}"


def diagnosticar_java() -> tuple[str, str, str]:
    java_path = shutil.which("java")
    if java_path:
        status, resultado = executar([java_path, "-version"])
        return status, resultado, f"java encontrado no PATH: {java_path}"
    if JAVA_FALLBACK.exists():
        status, resultado = executar([str(JAVA_FALLBACK), "-version"])
        return status, resultado, "java nao esta no PATH da sessao; verificado pelo caminho instalado"
    return "PENDENTE", "java nao encontrado", "Temurin foi tentado via winget; verificar instalacao/PATH"


def diagnosticar_ghostscript() -> tuple[str, str, str]:
    gs_path = shutil.which("gswin64c")
    if gs_path:
        status, resultado = executar([gs_path, "--version"])
        return status, resultado, f"gswin64c encontrado no PATH: {gs_path}"

    encontrados: list[Path] = []
    for pasta in GS_DIRS:
        if pasta.exists():
            encontrados.extend(pasta.rglob("gswin64c.exe"))
    if encontrados:
        status, resultado = executar([str(encontrados[0]), "--version"])
        return status, resultado, f"gswin64c encontrado fora do PATH: {encontrados[0]}"
    return "PENDENTE", "gswin64c nao encontrado", "winget nao encontrou ArtifexSoftware.GhostScript no catalogo local"


def importar(modulo: str, pacote: str | None = None) -> tuple[str, str, str]:
    try:
        mod = __import__(modulo)
        nome_pacote = pacote or modulo
        try:
            versao = metadata.version(nome_pacote)
        except metadata.PackageNotFoundError:
            versao = str(getattr(mod, "__version__", "importado"))
        return "OK", versao, "importacao local OK"
    except Exception as exc:  # noqa: BLE001 - registrar qualquer falha de importacao
        return "PENDENTE", f"{type(exc).__name__}: {exc}", "importacao local falhou"


def diagnosticar_chromium_playwright() -> tuple[str, str, str]:
    bases = []
    localappdata = os.environ.get("LOCALAPPDATA")
    if localappdata:
        bases.append(Path(localappdata) / "ms-playwright")
    env_path = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
    if env_path:
        bases.append(Path(env_path))

    candidatos: list[Path] = []
    for base in bases:
        if base.exists():
            candidatos.extend(base.glob("chromium*"))
            candidatos.extend(base.glob(".local-browsers/chromium*"))

    if candidatos:
        return "OK", str(candidatos[0]), "Chromium Playwright encontrado em cache local"
    return "PENDENTE", "Chromium Playwright nao encontrado em cache local conhecido", "executar playwright install chromium se necessario"


def main() -> int:
    linhas: list[dict[str, str]] = []

    checks = [
        ("java", diagnosticar_java),
        ("ghostscript", diagnosticar_ghostscript),
    ]
    for dependencia, funcao in checks:
        status, resultado, observacao = funcao()
        linhas.append({"dependencia": dependencia, "status": status, "versao_ou_resultado": resultado, "observacao": observacao})

    for dependencia, modulo, pacote in [
        ("camelot", "camelot", "camelot-py"),
        ("tabula", "tabula", "tabula-py"),
        ("fitz", "fitz", "pymupdf"),
        ("pdfplumber", "pdfplumber", "pdfplumber"),
        ("pypdf", "pypdf", "pypdf"),
        ("playwright", "playwright", "playwright"),
    ]:
        status, resultado, observacao = importar(modulo, pacote)
        linhas.append({"dependencia": dependencia, "status": status, "versao_ou_resultado": resultado, "observacao": observacao})

    status, resultado, observacao = diagnosticar_chromium_playwright()
    linhas.append({"dependencia": "playwright_chromium", "status": status, "versao_ou_resultado": resultado, "observacao": observacao})

    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    with SAIDA.open("w", newline="", encoding="utf-8") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=["dependencia", "status", "versao_ou_resultado", "observacao"])
        escritor.writeheader()
        escritor.writerows(linhas)

    ok = sum(1 for linha in linhas if linha["status"] == "OK")
    pendentes = len(linhas) - ok
    print(f"Diagnostico PDF/navegacao: OK={ok}; PENDENTE={pendentes}; arquivo={SAIDA}")
    for linha in linhas:
        if linha["status"] != "OK":
            print(f"PENDENTE {linha['dependencia']}: {linha['versao_ou_resultado']} | {linha['observacao']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
