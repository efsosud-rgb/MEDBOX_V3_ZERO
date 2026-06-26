"""Diagnostico de apps externos e bibliotecas de extracao de dados.

FASE 2.14E-C: nao acessa internet, nao baixa bases, nao altera banco e nao
altera dicionarios finais. Apenas verifica comandos, caminhos locais e imports.
"""

from __future__ import annotations

import csv
import shutil
import subprocess
from importlib import metadata
from pathlib import Path

SAIDA = Path("data/dicionario_mestre/processado/diagnostico_apps_extracao_dados.csv")
JAVA_FALLBACKS = [
    Path(r"C:\Program Files\Eclipse Adoptium\jdk-21.0.11.10-hotspot\bin\java.exe"),
    Path(r"C:\Program Files\Java\jre-1.8\bin\java.exe"),
]
OPENREFINE_PATHS = [
    Path(r"C:\Users\admph\AppData\Local\Programs\OpenRefine\openrefine.exe"),
    Path(r"C:\Users\admph\AppData\Local\Programs\OpenRefine\refine.bat"),
]
TABULA_PATHS = [
    Path(r"C:\Users\admph\AppData\Local\Microsoft\WinGet\Packages\tabulapdf.tabula_Microsoft.Winget.Source_8wekyb3d8bbwe\tabula\tabula.exe"),
    Path(r"C:\Users\admph\AppData\Local\Microsoft\WinGet\Packages\tabulapdf.tabula_Microsoft.Winget.Source_8wekyb3d8bbwe\tabula\tabula.jar"),
]
DBEAVER_PATHS = [Path(r"C:\Users\admph\AppData\Local\DBeaver\dbeaver.exe")]


def executar(comando: list[str]) -> tuple[str, str]:
    try:
        resultado = subprocess.run(comando, capture_output=True, text=True, timeout=25, check=False)
    except FileNotFoundError as exc:
        return "PENDENTE", f"nao encontrado: {exc}"
    except Exception as exc:  # noqa: BLE001 - diagnostico deve registrar qualquer falha local
        return "PENDENTE", f"{type(exc).__name__}: {exc}"
    texto = " ".join((resultado.stdout + " " + resultado.stderr).split())
    return ("OK" if resultado.returncode == 0 else "PENDENTE", texto or f"returncode={resultado.returncode}")


def linha(ferramenta: str, tipo: str, status: str, resultado: str, observacao: str) -> dict[str, str]:
    return {
        "ferramenta": ferramenta,
        "tipo": tipo,
        "status": status,
        "versao_ou_resultado": resultado,
        "observacao": observacao,
    }


def verificar_comando(nome: str, tipo: str, comando: str, args: list[str] | None = None) -> dict[str, str]:
    caminho = shutil.which(comando)
    if not caminho:
        return linha(nome, tipo, "PENDENTE", f"{comando} nao encontrado no PATH", "Pode estar instalado fora do PATH.")
    status, resultado = executar([caminho, *(args or [])])
    return linha(nome, tipo, status, resultado, f"PATH: {caminho}")


def verificar_caminhos(nome: str, tipo: str, caminhos: list[Path]) -> dict[str, str]:
    existentes = [str(caminho) for caminho in caminhos if caminho.exists()]
    if existentes:
        return linha(nome, tipo, "OK", existentes[0], "Localizado fora do PATH; PATH permanente nao foi alterado.")
    return linha(nome, tipo, "PENDENTE", "nao localizado", "Nao encontrado nos caminhos esperados.")


def verificar_java() -> dict[str, str]:
    java_path = shutil.which("java")
    if java_path:
        status, resultado = executar([java_path, "-version"])
        return linha("Java", "sistema", status, resultado, f"PATH: {java_path}")
    for caminho in JAVA_FALLBACKS:
        if caminho.exists():
            status, resultado = executar([str(caminho), "-version"])
            return linha("Java", "sistema", status, resultado, f"Localizado fora do PATH: {caminho}")
    return linha("Java", "sistema", "PENDENTE", "java nao encontrado", "Nao encontrado no PATH nem nos caminhos esperados.")


def importar(nome: str, modulo: str, pacote: str | None = None) -> dict[str, str]:
    try:
        mod = __import__(modulo)
        try:
            versao = metadata.version(pacote or modulo)
        except metadata.PackageNotFoundError:
            versao = str(getattr(mod, "__version__", "importado"))
        return linha(nome, "python", "OK", versao, "Importacao local OK.")
    except Exception as exc:  # noqa: BLE001 - registrar falha sem interromper diagnostico
        return linha(nome, "python", "PENDENTE", f"{type(exc).__name__}: {exc}", "Importacao local falhou.")


def main() -> int:
    linhas = [
        verificar_comando("winget", "sistema", "winget", ["--version"]),
        verificar_java(),
        verificar_caminhos("OpenRefine", "app", OPENREFINE_PATHS),
        verificar_caminhos("Tabula Desktop", "app", TABULA_PATHS),
        verificar_caminhos("DBeaver Community", "app", DBEAVER_PATHS),
        importar("Excalibur", "excalibur", "excalibur-py"),
        importar("Camelot", "camelot", "camelot-py"),
        importar("pdfplumber", "pdfplumber", "pdfplumber"),
        importar("PyMuPDF", "fitz", "pymupdf"),
        importar("tabula-py", "tabula", "tabula-py"),
        importar("DuckDB", "duckdb", "duckdb"),
        importar("Playwright", "playwright", "playwright"),
    ]
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    with SAIDA.open("w", newline="", encoding="utf-8") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=["ferramenta", "tipo", "status", "versao_ou_resultado", "observacao"])
        escritor.writeheader()
        escritor.writerows(linhas)
    ok = sum(1 for item in linhas if item["status"] == "OK")
    pendentes = len(linhas) - ok
    print(f"diagnostico_apps_extracao_dados: OK={ok}; PENDENTE={pendentes}; arquivo={SAIDA}")
    for item in linhas:
        if item["status"] != "OK":
            print(f"PENDENTE {item['ferramenta']}: {item['versao_ou_resultado']} | {item['observacao']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
