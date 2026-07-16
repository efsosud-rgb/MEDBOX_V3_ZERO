from decimal import Decimal

import pytest

from core.lances_persistencia import calcular_persistencia_item, calcular_total_geral


def item(**kwargs):
    base = {
        "quantidade": 1,
        "preco_osinfo": 0,
        "menor_lance": 0,
        "preco_medbox": 0,
        "empresa_melhor_lance": "",
        "status": "FALSO",
        "vencedor": "FALSO",
    }
    base.update(kwargs)
    return base


def test_backend_ignora_status_e_vencedor_do_frontend():
    resultado = calcular_persistencia_item(item(quantidade=10, preco_osinfo=20, preco_medbox=18, status="NEGOCIAR", vencedor="OSINFO"))
    assert resultado["venceu_medbox"] == 1
    assert resultado["valor_unitario"] == Decimal("18")
    assert resultado["valor_total"] == Decimal("180")


@pytest.mark.parametrize(
    ("dados", "empresa"),
    [
        ({"preco_medbox": 10, "preco_osinfo": 10}, "MEDBOX"),
        ({"preco_medbox": 10, "menor_lance": 10, "empresa_melhor_lance": "ABC"}, "MEDBOX"),
        ({"preco_osinfo": 10, "menor_lance": 10, "empresa_melhor_lance": "ABC"}, "OSINFO"),
    ],
)
def test_desempate_medbox_osinfo_concorrente(dados, empresa):
    resultado = calcular_persistencia_item(item(**dados))
    assert resultado["empresa_vencedora"] == empresa


def test_quantidade_zero_e_neutra():
    resultado = calcular_persistencia_item(item(quantidade=0, preco_medbox=1, preco_osinfo=10))
    assert resultado["venceu_medbox"] == 0
    assert resultado["valor_total"] == 0
    assert resultado["status_lance"] == "FORA DA COTACAO"


def test_preco_medbox_manual_e_preservado():
    resultado = calcular_persistencia_item(item(quantidade=2, preco_medbox="12,3456", preco_osinfo=20))
    assert resultado["preco_medbox"] == Decimal("12.3456")
    assert resultado["valor_total"] == Decimal("24.6912")


def test_derrota_nao_entra_no_total():
    venceu = calcular_persistencia_item(item(quantidade=2, preco_medbox=10, preco_osinfo=20))
    perdeu = calcular_persistencia_item(item(quantidade=3, preco_medbox=12, preco_osinfo=10))
    assert perdeu["valor_total"] == 0
    assert calcular_total_geral([venceu, perdeu]) == Decimal("20")


def test_fixture_afne_total_119461_60():
    entradas = [
        item(quantidade=10000, preco_medbox="0.1188", preco_osinfo="0.2075"),
        item(quantidade=500, preco_medbox="20.556", preco_osinfo=30),
        item(quantidade=2000, preco_medbox="53.93844", preco_osinfo=60),
        item(quantidade=10, preco_medbox="0.01", preco_osinfo="0.02"),
        item(quantidade=1, preco_medbox="118.62", preco_osinfo=200),
    ]
    calculados = [calcular_persistencia_item(entrada) for entrada in entradas]
    assert sum(resultado["venceu_medbox"] for resultado in calculados) == 5
    assert calcular_total_geral(calculados).quantize(Decimal("0.01")) == Decimal("119461.60")
