#!/usr/bin/env python3
"""Extrator somente leitura das fontes internas confiaveis do Dicionario Mestre MEDBOX.

O script apenas lê SQLite, CSV e XLSX em modo somente leitura e gera CSVs de
extração em ``data/dicionario_mestre/interno`` mais um relatório textual em
``data/dicionario_mestre/processado``.

Nenhuma escrita é feita no banco de dados.
"""

from __future__ import annotations

import csv
import sqlite3
import zipfile
import xml.etree.ElementTree as ET
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

try:
    from openpyxl import load_workbook
except Exception:  # pragma: no cover - import opcional
    load_workbook = None


BASE_DIR = Path(__file__).resolve().parents[2]
DB_PATH = BASE_DIR / "banco" / "medbox_v3.db"
UPLOAD_SKU_MASTER = BASE_DIR / "uploads" / "SKU_MASTER_2_0.xlsx"
UPLOAD_PRODUTOS = BASE_DIR / "uploads" / "PRODUTOS.xlsx"
AUDITORIA_LOTE = (
    BASE_DIR
    / "backups"
    / "auditoria_lote_piloto_sku_master_20260625_112310.csv"
)

OUT_INTERNO = BASE_DIR / "data" / "dicionario_mestre" / "interno"
OUT_PROCESSADO = BASE_DIR / "data" / "dicionario_mestre" / "processado"


@dataclass(frozen=True)
class FonteResultado:
    nome: str
    caminho: Path
    status: str
    linhas: int
    colunas: List[str]
    saida: Path | None = None
    aviso: str = ""


def _garantir_pastas() -> None:
    OUT_INTERNO.mkdir(parents=True, exist_ok=True)
    OUT_PROCESSADO.mkdir(parents=True, exist_ok=True)


def _abrir_sqlite_ro(path: Path) -> sqlite3.Connection:
    uri = f"file:{path.resolve().as_posix()}?mode=ro"
    return sqlite3.connect(uri, uri=True)


def _tabelas_sqlite(con: sqlite3.Connection) -> set[str]:
    linhas = con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    return {str(linha[0]) for linha in linhas}


def _colunas_tabela(con: sqlite3.Connection, tabela: str) -> List[str]:
    linhas = con.execute(f"PRAGMA table_info({tabela})").fetchall()
    return [str(linha[1]) for linha in linhas]


def _escrever_csv(destino: Path, colunas: Sequence[str], linhas: Iterable[Sequence[object]]) -> int:
    with destino.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(list(colunas))
        total = 0
        for linha in linhas:
            writer.writerow(["" if valor is None else str(valor) for valor in linha])
            total += 1
    return total


def _exportar_tabela_sqlite(con: sqlite3.Connection, tabela: str, destino: Path) -> Tuple[int, List[str]]:
    colunas = _colunas_tabela(con, tabela)
    if not colunas:
        _escrever_csv(destino, [], [])
        return 0, []
    cursor = con.execute(f"SELECT {', '.join(colunas)} FROM {tabela}")
    total = _escrever_csv(destino, colunas, cursor)
    return total, colunas


def _exportar_csv_origem(origem: Path, destino: Path) -> Tuple[int, List[str]]:
    if not origem.is_file():
        return 0, []
    with origem.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f, delimiter=";")
        try:
            colunas = next(reader)
        except StopIteration:
            _escrever_csv(destino, [], [])
            return 0, []
        linhas = list(reader)
    _escrever_csv(destino, colunas, linhas)
    return len(linhas), colunas


def _exportar_xlsx_primeira_aba(origem: Path, destino: Path) -> Tuple[int, List[str], str]:
    if load_workbook is not None:
        wb = load_workbook(origem, read_only=True, data_only=True)
        try:
            ws = wb[wb.sheetnames[0]]
            rows = ws.iter_rows(values_only=True)
            try:
                colunas = ["" if v is None else str(v) for v in next(rows)]
            except StopIteration:
                _escrever_csv(destino, [], [])
                return 0, [], ws.title
            total = _escrever_csv(destino, colunas, rows)
            return total, colunas, ws.title
        finally:
            wb.close()

    return _exportar_xlsx_stdlib_primeira_aba(origem, destino)


def _exportar_xlsx_melhor_aba(origem: Path, destino: Path, preferidas: Sequence[str]) -> Tuple[int, List[str], str]:
    if load_workbook is not None:
        wb = load_workbook(origem, read_only=True, data_only=True)
        try:
            aba = None
            for nome in preferidas:
                if nome in wb.sheetnames:
                    aba = wb[nome]
                    break
            if aba is None:
                aba = wb[wb.sheetnames[0]]
            rows = aba.iter_rows(values_only=True)
            try:
                colunas = ["" if v is None else str(v) for v in next(rows)]
            except StopIteration:
                _escrever_csv(destino, [], [])
                return 0, [], aba.title
            total = _escrever_csv(destino, colunas, rows)
            return total, colunas, aba.title
        finally:
            wb.close()

    return _exportar_xlsx_stdlib_melhor_aba(origem, destino, preferidas)


def _xlsx_ns(tag: str) -> str:
    return f"{{http://schemas.openxmlformats.org/spreadsheetml/2006/main}}{tag}"


def _xlsx_shared_strings(zf: zipfile.ZipFile) -> List[str]:
    if "xl/sharedStrings.xml" not in zf.namelist():
        return []
    root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
    strings: List[str] = []
    for si in root.findall(_xlsx_ns("si")):
        parts = []
        for node in si.iter():
            if node.tag == _xlsx_ns("t") and node.text is not None:
                parts.append(node.text)
        strings.append("".join(parts))
    return strings


def _xlsx_sheet_names(zf: zipfile.ZipFile) -> List[str]:
    root = ET.fromstring(zf.read("xl/workbook.xml"))
    rels = {}
    if "xl/_rels/workbook.xml.rels" in zf.namelist():
        rel_root = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
        for rel in rel_root:
            rels[rel.attrib.get("Id")] = rel.attrib.get("Target")
    nomes = []
    sheets = root.find(_xlsx_ns("sheets"))
    if sheets is not None:
        for sheet in sheets:
            target = rels.get(sheet.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"), "")
            nomes.append((sheet.attrib.get("name", ""), target))
    return [nome for nome, _ in nomes]


def _xlsx_sheet_target(zf: zipfile.ZipFile, nome_aba: str) -> Tuple[str, str]:
    root = ET.fromstring(zf.read("xl/workbook.xml"))
    rels = {}
    if "xl/_rels/workbook.xml.rels" in zf.namelist():
        rel_root = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
        for rel in rel_root:
            rels[rel.attrib.get("Id")] = rel.attrib.get("Target")
    sheets = root.find(_xlsx_ns("sheets"))
    if sheets is None:
        raise RuntimeError("workbook sem sheets")
    for sheet in sheets:
        if sheet.attrib.get("name") == nome_aba:
            rel_id = sheet.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
            target = rels.get(rel_id)
            if not target:
                raise RuntimeError(f"aba {nome_aba} sem target")
            if not target.startswith("xl/"):
                target = "xl/" + target.lstrip("/")
            return nome_aba, target
    raise RuntimeError(f"aba {nome_aba} nao encontrada")


def _xlsx_celula_valor(celula: ET.Element, shared_strings: Sequence[str]) -> str:
    tipo = celula.attrib.get("t")
    valor = celula.find(_xlsx_ns("v"))
    if tipo == "s" and valor is not None and valor.text is not None:
        idx = int(valor.text)
        return shared_strings[idx] if 0 <= idx < len(shared_strings) else ""
    if tipo == "inlineStr":
        texto = celula.find(f"{_xlsx_ns('is')}/{_xlsx_ns('t')}")
        return "" if texto is None or texto.text is None else texto.text
    if valor is None or valor.text is None:
        texto = celula.find(_xlsx_ns("is"))
        if texto is not None:
            partes = []
            for node in texto.iter():
                if node.tag == _xlsx_ns("t") and node.text is not None:
                    partes.append(node.text)
            return "".join(partes)
        return ""
    return valor.text


def _xlsx_iterar_linhas(zf: zipfile.ZipFile, target: str, shared_strings: Sequence[str]) -> Iterable[List[str]]:
    root = ET.fromstring(zf.read(target))
    sheet_data = root.find(_xlsx_ns("sheetData"))
    if sheet_data is None:
        return []
    for row in sheet_data.findall(_xlsx_ns("row")):
        valores: List[str] = []
        for celula in row.findall(_xlsx_ns("c")):
            referencia = celula.attrib.get("r", "")
            coluna = 0
            for ch in referencia:
                if ch.isalpha():
                    coluna = coluna * 26 + (ord(ch.upper()) - 64)
                else:
                    break
            while len(valores) < max(0, coluna - 1):
                valores.append("")
            valores.append(_xlsx_celula_valor(celula, shared_strings))
        yield valores


def _exportar_xlsx_stdlib_melhor_aba(origem: Path, destino: Path, preferidas: Sequence[str]) -> Tuple[int, List[str], str]:
    with zipfile.ZipFile(origem) as zf:
        nomes = _xlsx_sheet_names(zf)
        aba = next((nome for nome in preferidas if nome in nomes), nomes[0] if nomes else "")
        if not aba:
            _escrever_csv(destino, [], [])
            return 0, [], ""
        _, target = _xlsx_sheet_target(zf, aba)
        shared_strings = _xlsx_shared_strings(zf)
        linhas = list(_xlsx_iterar_linhas(zf, target, shared_strings))
    if not linhas:
        _escrever_csv(destino, [], [])
        return 0, [], aba
    colunas = ["" if v is None else str(v) for v in linhas[0]]
    total = _escrever_csv(destino, colunas, linhas[1:])
    return total, colunas, aba


def _exportar_xlsx_stdlib_primeira_aba(origem: Path, destino: Path) -> Tuple[int, List[str], str]:
    with zipfile.ZipFile(origem) as zf:
        nomes = _xlsx_sheet_names(zf)
        aba = nomes[0] if nomes else ""
        if not aba:
            _escrever_csv(destino, [], [])
            return 0, [], ""
        _, target = _xlsx_sheet_target(zf, aba)
        shared_strings = _xlsx_shared_strings(zf)
        linhas = list(_xlsx_iterar_linhas(zf, target, shared_strings))
    if not linhas:
        _escrever_csv(destino, [], [])
        return 0, [], aba
    colunas = ["" if v is None else str(v) for v in linhas[0]]
    total = _escrever_csv(destino, colunas, linhas[1:])
    return total, colunas, aba


def _formatar_lista(items: Sequence[str]) -> str:
    return ", ".join(items) if items else "-"


def main() -> int:
    _garantir_pastas()

    inicio = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    fontes_encontradas: List[str] = []
    fontes_ausentes: List[str] = []
    resultados: List[FonteResultado] = []
    avisos: List[str] = []

    tabelas_alvo = {
        "produtos": OUT_INTERNO / "produtos_extraidos.csv",
        "precos_fornecedores": OUT_INTERNO / "precos_fornecedores_extraidos.csv",
        "equivalencias": OUT_INTERNO / "equivalencias_extraidas.csv",
        "dicionario_termos": OUT_INTERNO / "dicionario_termos_extraido.csv",
        "dicionario_sinonimos": OUT_INTERNO / "dicionario_sinonimos_extraido.csv",
        "sku_master_regras": OUT_INTERNO / "sku_master_regras_extraidas.csv",
    }

    arquivos_alvo = {
        UPLOAD_SKU_MASTER: OUT_INTERNO / "sku_master_2_0_upload_extraido.csv",
        UPLOAD_PRODUTOS: OUT_INTERNO / "produtos_upload_extraido.csv",
        AUDITORIA_LOTE: OUT_INTERNO / "auditoria_lote_piloto_extraida.csv",
    }

    tabelas_existentes: set[str] = set()
    try:
        con = _abrir_sqlite_ro(DB_PATH)
    except Exception as exc:
        avisos.append(f"Banco nao disponivel em modo somente leitura: {exc}")
        con = None

    if con is not None:
        try:
            tabelas_existentes = _tabelas_sqlite(con)
        except Exception as exc:
            avisos.append(f"Falha ao listar tabelas via sqlite_master: {exc}")

    for tabela, destino in tabelas_alvo.items():
        if con is None or tabela not in tabelas_existentes:
            fontes_ausentes.append(f"sqlite:{tabela}")
            resultados.append(
                FonteResultado(
                    nome=tabela,
                    caminho=DB_PATH,
                    status="ausente",
                    linhas=0,
                    colunas=[],
                    saida=destino,
                    aviso="tabela nao encontrada",
                )
            )
            continue
        try:
            linhas, colunas = _exportar_tabela_sqlite(con, tabela, destino)
            fontes_encontradas.append(f"sqlite:{tabela}")
            resultados.append(
                FonteResultado(
                    nome=tabela,
                    caminho=DB_PATH,
                    status="extraida",
                    linhas=linhas,
                    colunas=colunas,
                    saida=destino,
                )
            )
        except Exception as exc:
            fontes_ausentes.append(f"sqlite:{tabela}")
            resultados.append(
                FonteResultado(
                    nome=tabela,
                    caminho=DB_PATH,
                    status="erro",
                    linhas=0,
                    colunas=[],
                    saida=destino,
                    aviso=str(exc),
                )
            )
            avisos.append(f"Falha ao exportar {tabela}: {exc}")

    if con is not None:
        con.close()

    for origem, destino in arquivos_alvo.items():
        if not origem.is_file():
            fontes_ausentes.append(str(origem))
            resultados.append(
                FonteResultado(
                    nome=origem.name,
                    caminho=origem,
                    status="ausente",
                    linhas=0,
                    colunas=[],
                    saida=destino,
                    aviso="arquivo nao encontrado",
                )
            )
            continue

        try:
            if origem.name.lower().endswith(".csv"):
                linhas, colunas = _exportar_csv_origem(origem, destino)
                sheet_info = ""
            else:
                if origem.name == UPLOAD_SKU_MASTER.name:
                    linhas, colunas, sheet_info = _exportar_xlsx_melhor_aba(
                        origem, destino, ["BD_Compras 2026", "Planilha1", "Sheet1"]
                    )
                elif origem.name == UPLOAD_PRODUTOS.name:
                    linhas, colunas, sheet_info = _exportar_xlsx_melhor_aba(
                        origem, destino, ["Produtos", "Planilha1", "Sheet1"]
                    )
                else:
                    linhas, colunas, sheet_info = _exportar_xlsx_primeira_aba(origem, destino)

                if sheet_info:
                    avisos.append(f"{origem.name}: aba usada = {sheet_info}")

            fontes_encontradas.append(str(origem))
            resultados.append(
                FonteResultado(
                    nome=origem.name,
                    caminho=origem,
                    status="extraida",
                    linhas=linhas,
                    colunas=colunas,
                    saida=destino,
                )
            )
        except Exception as exc:
            fontes_ausentes.append(str(origem))
            resultados.append(
                FonteResultado(
                    nome=origem.name,
                    caminho=origem,
                    status="erro",
                    linhas=0,
                    colunas=[],
                    saida=destino,
                    aviso=str(exc),
                )
            )
            avisos.append(f"Falha ao exportar {origem}: {exc}")

    relatorio = OUT_PROCESSADO / "relatorio_extracao_fontes_internas.txt"
    with relatorio.open("w", encoding="utf-8-sig", newline="") as f:
        f.write("RELATORIO DE EXTRACAO DE FONTES INTERNAS - DICIONARIO MESTRE MEDBOX\n")
        f.write(f"Data/hora: {inicio}\n")
        f.write(f"Banco lido: {DB_PATH}\n")
        f.write("Modo: somente leitura (SQLite URI read-only, arquivos apenas leitura)\n")
        f.write("\nFontes encontradas:\n")
        for item in fontes_encontradas:
            f.write(f"- {item}\n")
        if not fontes_encontradas:
            f.write("- nenhuma\n")
        f.write("\nFontes ausentes:\n")
        for item in fontes_ausentes:
            f.write(f"- {item}\n")
        if not fontes_ausentes:
            f.write("- nenhuma\n")
        f.write("\nArquivos CSV gerados:\n")
        for r in resultados:
            if r.saida is not None:
                f.write(f"- {r.saida}\n")
        f.write("\nLinhas e colunas exportadas:\n")
        for r in resultados:
            if r.saida is not None:
                f.write(
                    f"- {r.nome}: linhas={r.linhas}; colunas={_formatar_lista(r.colunas)}; status={r.status}\n"
                )
                if r.aviso:
                    f.write(f"  aviso: {r.aviso}\n")
        f.write("\nAvisos de seguranca:\n")
        if avisos:
            for aviso in avisos:
                f.write(f"- {aviso}\n")
        else:
            f.write("- nenhum aviso relevante\n")
        f.write("\nConfirmacao:\n")
        f.write("- nenhum SQL de escrita foi executado\n")

    print(f"Banco lido em modo somente leitura: {DB_PATH}")
    print(f"Relatorio gerado: {relatorio}")
    for r in resultados:
        if r.saida is not None:
            print(f"{r.saida} -> {r.linhas} linhas")
    print("Nenhum SQL de escrita foi executado.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
