import importlib
import sqlite3
import sys
import types
from decimal import Decimal
from pathlib import Path

import pytest


@pytest.fixture()
def app_temporario(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db = tmp_path / "lances_rotas.db"

    import core.banco as banco

    monkeypatch.setattr(banco, "DB_PATH", db)
    sys.modules.pop("app", None)
    modulo_lances_legado = types.ModuleType("core.lances_cotacao")
    modulo_lances_legado.importar_lances_cotacao = lambda *args, **kwargs: None
    monkeypatch.setitem(sys.modules, "core.lances_cotacao", modulo_lances_legado)
    app_mod = importlib.import_module("app")

    def conectar_tmp():
        conn = sqlite3.connect(db)
        conn.row_factory = sqlite3.Row
        return conn

    monkeypatch.setattr(app_mod, "conectar", conectar_tmp)
    monkeypatch.setattr(app_mod, "proximo_numero_cotacao", lambda: "TMP-0001")
    app_mod.app.config.update(TESTING=True)
    yield app_mod, db
    sys.modules.pop("app", None)


def consultar_cotacao(db: Path, numero: str = "TMP-0001"):
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cotacao = cur.execute(
        "SELECT * FROM cotacoes_geradas WHERE numero_cotacao = ?",
        (numero,),
    ).fetchone()
    itens = cur.execute(
        """
        SELECT *
        FROM cotacoes_geradas_itens
        WHERE cotacao_id = ?
        ORDER BY item_numero
        """,
        (cotacao["id"],),
    ).fetchall()
    conn.close()
    return dict(cotacao), [dict(item) for item in itens]


def gerar(client, itens):
    resposta = client.post(
        "/cotacoes/lances/gerar-cotacao",
        json={"cliente": "cliente teste", "itens": itens},
    )
    assert resposta.status_code == 200, resposta.get_data(as_text=True)
    dados = resposta.get_json()
    assert dados["ok"] is True
    return dados


def item(**kwargs):
    base = {
        "descricao_produto": "ITEM TESTE",
        "sku_master": "SKU TESTE",
        "marca": "MARCA",
        "quantidade": 1,
        "preco_osinfo": 0,
        "menor_lance": 0,
        "preco_medbox": 0,
        "empresa_melhor_lance": "CONCORRENTE",
        "status": "MEDBOX VENCE",
        "vencedor": "MEDBOX",
    }
    base.update(kwargs)
    return base


def test_gerar_cotacao_recalcula_sem_status_vencedor(app_temporario):
    app_mod, db = app_temporario
    client = app_mod.app.test_client()

    gerar(client, [item(quantidade=10, preco_medbox="8.50", preco_osinfo="10.00", status="NEGOCIAR", vencedor="OSINFO")])

    cotacao, itens = consultar_cotacao(db)
    assert Decimal(str(cotacao["total_geral"])) == Decimal("85.0")
    assert itens[0]["venceu_medbox"] == 1
    assert Decimal(str(itens[0]["valor_unitario"])) == Decimal("8.5")
    assert Decimal(str(itens[0]["valor_total"])) == Decimal("85.0")
    assert itens[0]["status_lance"] == "MEDBOX VENCE"


def test_payload_falsificado_nao_forca_vitoria_medbox(app_temporario):
    app_mod, db = app_temporario
    client = app_mod.app.test_client()

    gerar(client, [item(quantidade=3, preco_medbox=12, preco_osinfo=10, status="MEDBOX VENCE", vencedor="MEDBOX")])

    cotacao, itens = consultar_cotacao(db)
    assert Decimal(str(cotacao["total_geral"])) == Decimal("0.0")
    assert itens[0]["venceu_medbox"] == 0
    assert Decimal(str(itens[0]["valor_unitario"])) == Decimal("0.0")
    assert Decimal(str(itens[0]["valor_total"])) == Decimal("0.0")
    assert itens[0]["menor_empresa"] == "OSINFO"


@pytest.mark.parametrize(
    ("payload", "vence_medbox", "empresa"),
    [
        ({"preco_medbox": 10, "preco_osinfo": 10}, 1, "MEDBOX"),
        ({"preco_medbox": 10, "menor_lance": 10, "empresa_melhor_lance": "ABC"}, 1, "MEDBOX"),
        ({"preco_osinfo": 10, "menor_lance": 10, "empresa_melhor_lance": "ABC", "preco_medbox": 0}, 0, "OSINFO"),
    ],
)
def test_empates_usam_prioridade_medbox_osinfo_concorrente(app_temporario, payload, vence_medbox, empresa):
    app_mod, db = app_temporario
    client = app_mod.app.test_client()

    gerar(client, [item(quantidade=2, **payload)])

    _, itens = consultar_cotacao(db)
    assert itens[0]["venceu_medbox"] == vence_medbox
    assert itens[0]["menor_empresa"] == empresa


def test_quantidade_zero_e_neutra(app_temporario):
    app_mod, db = app_temporario
    client = app_mod.app.test_client()

    gerar(client, [item(quantidade=0, preco_medbox=1, preco_osinfo=10)])

    cotacao, itens = consultar_cotacao(db)
    assert Decimal(str(cotacao["total_geral"])) == Decimal("0.0")
    assert itens[0]["venceu_medbox"] == 0
    assert itens[0]["medbox_vencedora"] == 0
    assert itens[0]["status_lance"] == "FORA DA COTACAO"
    assert Decimal(str(itens[0]["valor_total"])) == Decimal("0.0")


def test_criacao_e_atualizacao_produzem_mesma_persistencia(app_temporario):
    app_mod, db = app_temporario
    client = app_mod.app.test_client()
    itens_payload = [
        item(descricao_produto="VENCE", quantidade=2, preco_medbox=9, preco_osinfo=10),
        item(descricao_produto="PERDE", quantidade=3, preco_medbox=12, preco_osinfo=10),
        item(descricao_produto="ZERO", quantidade=0, preco_medbox=1, preco_osinfo=10),
    ]

    gerar(client, itens_payload)
    cotacao_criada, itens_criados = consultar_cotacao(db)

    resposta = client.post(
        "/cotacoes/lances/atualizar-cotacao/TMP-0001",
        json={"cliente": "cliente teste", "itens": itens_payload},
    )
    assert resposta.status_code == 200, resposta.get_data(as_text=True)
    assert resposta.get_json()["ok"] is True

    cotacao_atualizada, itens_atualizados = consultar_cotacao(db)
    assert Decimal(str(cotacao_atualizada["total_geral"])) == Decimal(str(cotacao_criada["total_geral"]))
    campos = ["valor_unitario", "valor_total", "venceu_medbox", "status_lance", "menor_empresa", "menor_valor_comparativo"]
    assert [{campo: item[campo] for campo in campos} for item in itens_atualizados] == [
        {campo: item[campo] for campo in campos} for item in itens_criados
    ]


def test_fixture_afne_cinco_vitorias_total_119461_60(app_temporario):
    app_mod, db = app_temporario
    client = app_mod.app.test_client()
    itens_payload = [
        item(descricao_produto="ITEM 2", quantidade=10000, preco_medbox="0.1188", preco_osinfo="0.2075"),
        item(descricao_produto="ITEM 3", quantidade=500, preco_medbox="20.556", preco_osinfo=30),
        item(descricao_produto="ITEM 8", quantidade=2000, preco_medbox="53.93844", preco_osinfo=60),
        item(descricao_produto="ITEM 12", quantidade=10, preco_medbox="0.01", preco_osinfo="0.02"),
        item(descricao_produto="ITEM 37", quantidade=1, preco_medbox="118.62", preco_osinfo=200),
    ]

    gerar(client, itens_payload)

    cotacao, itens = consultar_cotacao(db)
    assert sum(item["venceu_medbox"] for item in itens) == 5
    assert Decimal(str(cotacao["total_geral"])).quantize(Decimal("0.01")) == Decimal("119461.60")
