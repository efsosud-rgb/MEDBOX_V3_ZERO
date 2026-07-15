import sqlite3
from pathlib import Path

import pytest
from openpyxl import Workbook

import core.cotacao_lances_v2 as lances


def criar_banco_temporario(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.executescript(
        """
        CREATE TABLE produtos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sku TEXT,
            produto_padrao TEXT,
            sku_master TEXT,
            fabricante TEXT,
            categoria TEXT,
            ativo INTEGER DEFAULT 1
        );
        CREATE TABLE fornecedores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT,
            ativo INTEGER DEFAULT 1
        );
        CREATE TABLE precos_fornecedores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fornecedor_id INTEGER,
            produto_id INTEGER,
            descricao_original TEXT,
            marca TEXT,
            preco REAL,
            data_importacao TEXT,
            ativo INTEGER DEFAULT 1
        );
        CREATE TABLE equivalencias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            produto_id INTEGER,
            descricao_equivalente TEXT,
            sku_master TEXT,
            origem TEXT,
            ativo INTEGER DEFAULT 1
        );
        """
    )
    cur.execute("INSERT INTO fornecedores (nome, ativo) VALUES ('FORN ALFA', 1)")
    forn1 = cur.lastrowid
    cur.execute("INSERT INTO fornecedores (nome, ativo) VALUES ('FORN BETA', 1)")
    forn2 = cur.lastrowid

    cur.execute(
        "INSERT INTO produtos (produto_padrao, sku_master, fabricante, categoria, ativo) VALUES (?, ?, ?, ?, 1)",
        ("AGULHA 40 X 12 A", "AGULHA 40 X 12", "FAB A", "CORRELATOS"),
    )
    ag1 = cur.lastrowid
    cur.execute(
        "INSERT INTO produtos (produto_padrao, sku_master, fabricante, categoria, ativo) VALUES (?, ?, ?, ?, 1)",
        ("AGULHA 40 X 12 B", "AGULHA 40 X 12", "FAB B", "CORRELATOS"),
    )
    ag2 = cur.lastrowid
    cur.execute(
        "INSERT INTO produtos (produto_padrao, sku_master, fabricante, categoria, ativo) VALUES (?, ?, ?, ?, 1)",
        ("CATETER G20", "CATETER VENOSO G20", "FAB CAT", "CORRELATOS"),
    )
    cat = cur.lastrowid
    cur.execute(
        "INSERT INTO produtos (produto_padrao, sku_master, fabricante, categoria, ativo) VALUES (?, ?, ?, ?, 1)",
        ("SKU SEM PRECO", "SKU SEM PRECO", "FAB SEM", "CORRELATOS"),
    )
    cur.execute(
        "INSERT INTO produtos (produto_padrao, sku_master, fabricante, categoria, ativo) VALUES (?, ?, ?, ?, 1)",
        ("ABSORVENTE GERIATRICO", "ABSORVENTE GERIATRICO", "FAB ABS", "HIGIENE"),
    )
    abs_id = cur.lastrowid

    precos = [
        (forn1, ag1, "AGULHA CARA", "MARCA CARA", 0.30, "2026-01-01"),
        (forn2, ag2, "AGULHA BARATA", "MARCA BARATA", 0.21, "2026-01-02"),
        (forn1, cat, "CATETER G20", "", 1.10, "2026-01-03"),
        (forn1, abs_id, "ABSORVENTE", "MARCA ABS", 0.20, "2026-01-04"),
    ]
    cur.executemany(
        "INSERT INTO precos_fornecedores (fornecedor_id, produto_id, descricao_original, marca, preco, data_importacao) VALUES (?, ?, ?, ?, ?, ?)",
        precos,
    )
    conn.commit()
    conn.close()


def criar_xlsx(path: Path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "SOLICITAÇÃO DE COMPRA"
    ws.append(["Categoria", "Descrição do Produto", "Unidade de Compra", "Quantidade", "Valor Unitário"])
    ws.append(["Correlatos", "ABSORVENTE HIGIÊNICO GERIATRICO", "UNID", 7000, 0.395])
    ws.append(["Correlatos", "AGULHA 40 X 12", "UNID", 10000, 0.2075])
    ws.append(["Correlatos", "CATETER VENOSO G20", "UNID", 2000, 1.7404])
    ws.append(["Correlatos", "SKU SEM PRECO", "UNID", 0, None])
    ws.append(["", "CATETER VENOSO G20", "UNID", 1, 2.5])
    wb.save(path)
    wb.close()


@pytest.fixture
def ambiente_afne(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db = tmp_path / "lances_teste.db"
    xlsx = tmp_path / "fixture_lances.xlsx"
    criar_banco_temporario(db)
    criar_xlsx(xlsx)

    def conectar_tmp():
        conn = sqlite3.connect(db)
        conn.row_factory = sqlite3.Row
        return conn

    monkeypatch.setattr(lances, "conectar", conectar_tmp)
    lances.limpar_cache_lances()
    yield xlsx
    lances.limpar_cache_lances()


def test_fluxo_canonico_afne_com_banco_temporario(ambiente_afne: Path):
    itens = lances.extrair_itens_arquivo(ambiente_afne)
    assert len(itens) == 5
    assert itens[0]["categoria"] == "CORRELATOS"
    assert itens[0]["descricao_cotacao"] == "ABSORVENTE HIGIÊNICO GERIATRICO"
    assert itens[0]["unidade_compra"] == "UNID"
    assert itens[0]["quantidade"] == 7000
    assert itens[0]["preco_osinfo"] == 0.395
    assert itens[1]["preco_osinfo"] == 0.2075
    assert itens[3]["quantidade"] == 0
    assert itens[3]["preco_osinfo"] == ""

    custo = lances.buscar_menor_custo_por_sku_master("AGULHA 40 X 12")
    assert custo["encontrado"] is True
    assert custo["menor_custo"] == 0.21
    assert custo["fornecedor"] == "FORN BETA"
    assert custo["marca"] == "MARCA BARATA"
    assert custo["categoria"] == "CORRELATOS"

    sem_preco = lances.buscar_menor_custo_por_sku_master("SKU SEM PRECO")
    assert sem_preco["encontrado"] is False

    analise = lances.analisar_itens_lances(itens, markup_percentual=80, score_minimo=20)
    assert len(analise["itens"]) == 4
    assert analise["total_linhas_arquivo"] == 5
    assert analise["total_itens_com_quantidade"] == 4
    assert analise["total_ignorados_quantidade_zero"] == 1

    agulha = next(i for i in analise["itens"] if i["descricao_produto"] == "AGULHA 40 X 12")
    assert agulha["categoria"] == "CORRELATOS"
    assert agulha["menor_custo_unitario"] == 0.21
    assert agulha["fornecedor_menor_custo"] == "FORN BETA"
    assert agulha["marca_fabricante"] == "MARCA BARATA"
    assert round(agulha["preco_medbox"], 4) == 0.378
    assert agulha["preco_osinfo"] == 0.2075

    cat = next(i for i in analise["itens"] if i["descricao_produto"] == "CATETER VENOSO G20")
    assert cat["preco_osinfo"] == 1.7404
    assert cat["marca_fabricante"] == "FAB CAT"
    assert not any(i["descricao_produto"] == "SKU SEM PRECO" for i in analise["itens"])

    salvo = lances.salvar_sku_rapido_lances(
        descricao_cotacao="descricao manual preservada",
        sku_master="AGULHA 40 X 12",
        categoria="CORRELATOS",
    )
    assert salvo["ok"] is True
    assert salvo["menor_custo_unitario"] == 0.21
    assert salvo["fornecedor_menor_custo"] == "FORN BETA"
    assert salvo["marca_fabricante"] == "MARCA BARATA"

    markup_50 = lances.analisar_itens_lances([itens[1]], markup_percentual=50, score_minimo=20)["itens"][0]
    assert round(markup_50["preco_medbox"], 4) == 0.315
