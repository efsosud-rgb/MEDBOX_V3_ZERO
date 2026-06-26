"""Valida o download bruto de Medicamentos registrados / dados.gov.br.

Nao altera banco nem dicionarios finais. Apenas inspeciona arquivos em
 data/dicionario_mestre/bruto/medicamentos_registrados_dados_gov/.
"""

from __future__ import annotations

import csv
import zipfile
from pathlib import Path

DIRETORIO = Path("data/dicionario_mestre/bruto/medicamentos_registrados_dados_gov")
SAIDA = Path("data/dicionario_mestre/processado/validacao_medicamentos_registrados_dados_gov.csv")
COLUNAS_UTEIS = [
    "registro",
    "processo",
    "produto",
    "nome_produto",
    "principio_ativo",
    "empresa",
    "cnpj",
    "vencimento",
    "situacao",
    "categoria",
    "classe",
]


def normalizar(nome: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "_" for ch in nome).strip("_")


def detectar_formato(caminho: Path) -> str:
    sufixo = caminho.suffix.lower().lstrip(".")
    return sufixo or "desconhecido"


def abrir_csv(caminho: Path):
    for encoding in ("utf-8-sig", "latin1"):
        try:
            arquivo = caminho.open("r", newline="", encoding=encoding)
            amostra = arquivo.read(8192)
            arquivo.seek(0)
            try:
                dialecto = csv.Sniffer().sniff(amostra, delimiters=",;\t|")
            except csv.Error:
                dialecto = csv.excel
                if ";" in amostra:
                    dialecto.delimiter = ";"
            return arquivo, dialecto, encoding
        except UnicodeDecodeError:
            continue
    arquivo = caminho.open("r", newline="", encoding="utf-8", errors="replace")
    return arquivo, csv.excel, "utf-8-replace"


def validar_csv(caminho: Path) -> tuple[str, str, str, str]:
    arquivo, dialecto, encoding = abrir_csv(caminho)
    with arquivo:
        leitor = csv.reader(arquivo, dialecto)
        try:
            cabecalho = next(leitor)
        except StopIteration:
            return "0", "0", "", "CSV vazio"
        linhas = 1 + sum(1 for _ in leitor)
    colunas_norm = [normalizar(coluna) for coluna in cabecalho]
    uteis = []
    for alvo in COLUNAS_UTEIS:
        if any(alvo in coluna for coluna in colunas_norm):
            uteis.append(alvo)
    return str(linhas), str(len(cabecalho)), ";".join(uteis), f"encoding={encoding}; colunas={';'.join(cabecalho[:80])}"


def validar_zip(caminho: Path) -> tuple[str, str, str, str]:
    with zipfile.ZipFile(caminho) as pacote:
        nomes = pacote.namelist()
    formatos = sorted({Path(nome).suffix.lower().lstrip(".") or "sem_extensao" for nome in nomes})
    return "", str(len(nomes)), "", f"arquivos_zip={';'.join(nomes[:80])}; formatos={';'.join(formatos)}"


def validar_arquivo(caminho: Path) -> dict[str, str]:
    formato = detectar_formato(caminho)
    tamanho = caminho.stat().st_size
    status = "OK"
    linhas = ""
    colunas = ""
    principais = ""
    observacao = ""

    try:
        if formato == "csv":
            linhas, colunas, principais, observacao = validar_csv(caminho)
        elif formato == "zip":
            linhas, colunas, principais, observacao = validar_zip(caminho)
        elif formato in {"xls", "xlsx"}:
            status = "OK_FORMATO_PLANILHA_SEM_LEITURA_COMPLETA"
            observacao = "Planilha detectada; leitura detalhada fica para fase de processamento."
        else:
            status = "PENDENTE_FORMATO_NAO_ESTRUTURADO"
            observacao = "Formato nao validado nesta fase."
    except Exception as exc:  # noqa: BLE001 - registrar falha sem interromper demais arquivos
        status = "PENDENTE_ERRO_VALIDACAO"
        observacao = f"{type(exc).__name__}: {exc}"

    return {
        "arquivo": str(caminho),
        "status": status,
        "formato": formato,
        "tamanho_bytes": str(tamanho),
        "linhas_detectadas": linhas,
        "colunas_detectadas": colunas,
        "colunas_principais": principais,
        "observacao": observacao,
    }


def main() -> int:
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    arquivos = []
    if DIRETORIO.exists():
        arquivos = [item for item in DIRETORIO.iterdir() if item.is_file() and item.name != "manifesto_download.csv"]
    linhas = [validar_arquivo(arquivo) for arquivo in sorted(arquivos)]
    if not linhas:
        linhas.append(
            {
                "arquivo": str(DIRETORIO),
                "status": "PENDENTE_ARQUIVO_NAO_BAIXADO",
                "formato": "",
                "tamanho_bytes": "0",
                "linhas_detectadas": "",
                "colunas_detectadas": "",
                "colunas_principais": "",
                "observacao": "Nenhum arquivo bruto encontrado para validar.",
            }
        )

    with SAIDA.open("w", newline="", encoding="utf-8") as arquivo_csv:
        escritor = csv.DictWriter(
            arquivo_csv,
            fieldnames=["arquivo", "status", "formato", "tamanho_bytes", "linhas_detectadas", "colunas_detectadas", "colunas_principais", "observacao"],
        )
        escritor.writeheader()
        escritor.writerows(linhas)

    ok = sum(1 for linha in linhas if linha["status"].startswith("OK"))
    pendentes = len(linhas) - ok
    print(f"validacao_medicamentos_registrados: arquivos={len(linhas)}; ok={ok}; pendentes={pendentes}; saida={SAIDA}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
