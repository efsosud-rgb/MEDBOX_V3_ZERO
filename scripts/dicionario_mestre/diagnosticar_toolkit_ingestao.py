"""Diagnostico offline do toolkit de ingestao multi-fonte.

Este script apenas importa bibliotecas instaladas e grava um CSV de status.
Nao acessa internet, nao altera banco e nao altera dicionarios finais.
"""

from __future__ import annotations

import csv
import importlib
from importlib import metadata
from pathlib import Path

SAIDA = Path("data/dicionario_mestre/processado/diagnostico_toolkit_ingestao_multi_fonte.csv")

BIBLIOTECAS = [
    ("requests", "requests", "requests"),
    ("httpx", "httpx", "httpx"),
    ("tenacity", "tenacity", "tenacity"),
    ("tqdm", "tqdm", "tqdm"),
    ("dotenv", "dotenv", "python-dotenv"),
    ("pandas", "pandas", "pandas"),
    ("openpyxl", "openpyxl", "openpyxl"),
    ("pyxlsb", "pyxlsb", "pyxlsb"),
    ("fastexcel", "fastexcel", "fastexcel"),
    ("polars", "polars", "polars"),
    ("duckdb", "duckdb", "duckdb"),
    ("pyarrow", "pyarrow", "pyarrow"),
    ("bs4", "bs4", "beautifulsoup4"),
    ("lxml", "lxml", "lxml"),
    ("selectolax", "selectolax", "selectolax"),
    ("playwright", "playwright", "playwright"),
    ("fitz", "fitz", "pymupdf"),
    ("pdfplumber", "pdfplumber", "pdfplumber"),
    ("pypdf", "pypdf", "pypdf"),
    ("camelot", "camelot", "camelot-py"),
    ("tabula", "tabula", "tabula-py"),
    ("rapidfuzz", "rapidfuzz", "rapidfuzz"),
    ("unidecode", "unidecode", "Unidecode"),
    ("slugify", "slugify", "python-slugify"),
    ("regex", "regex", "regex"),
    ("jsonlines", "jsonlines", "jsonlines"),
    ("sqlite_utils", "sqlite_utils", "sqlite-utils"),
]


def versao(distribuicao: str, modulo: object) -> str:
    try:
        return metadata.version(distribuicao)
    except metadata.PackageNotFoundError:
        return str(getattr(modulo, "__version__", ""))


def diagnosticar() -> list[dict[str, str]]:
    linhas: list[dict[str, str]] = []
    for biblioteca, modulo_nome, distribuicao in BIBLIOTECAS:
        try:
            modulo = importlib.import_module(modulo_nome)
            linhas.append(
                {
                    "biblioteca": biblioteca,
                    "status": "OK",
                    "versao": versao(distribuicao, modulo),
                    "observacao": "importacao realizada sem acesso a internet",
                }
            )
        except Exception as exc:  # noqa: BLE001 - diagnostico deve registrar qualquer falha de importacao
            linhas.append(
                {
                    "biblioteca": biblioteca,
                    "status": "ERRO",
                    "versao": "",
                    "observacao": f"{type(exc).__name__}: {exc}",
                }
            )
    return linhas


def main() -> int:
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    linhas = diagnosticar()
    with SAIDA.open("w", newline="", encoding="utf-8") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=["biblioteca", "status", "versao", "observacao"])
        escritor.writeheader()
        escritor.writerows(linhas)

    total_ok = sum(1 for linha in linhas if linha["status"] == "OK")
    total_erro = len(linhas) - total_ok
    print(f"Diagnostico toolkit ingestao multi-fonte: OK={total_ok}; ERRO={total_erro}; arquivo={SAIDA}")
    for linha in linhas:
        if linha["status"] != "OK":
            print(f"ERRO {linha['biblioteca']}: {linha['observacao']}")
    return 0 if total_erro == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
