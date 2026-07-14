# -*- coding: utf-8 -*-
"""Testes focados para lances: quantidade, indicadores, moeda e mojibake.

Executar com:
    python tests\\lances_layout_indicadores_test.py
"""
from pathlib import Path
import importlib.util
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
MOD_PATH = ROOT / "core" / "cotacao_lances_v2.py"
TEMPLATE_PATH = ROOT / "templates" / "cotacao_lances.html"
JS_PATH = ROOT / "static" / "js" / "cotacao_lances.js"

spec = importlib.util.spec_from_file_location("cotacao_lances_v2_test", MOD_PATH)
lances = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lances)


def _patch_backend_sem_banco():
    def candidato(desc, score_minimo=72):
        desc_up = desc.upper()
        if "REVISAR" in desc_up:
            return None, 40
        sku = "SKU VENCE"
        if "NEGOCIAR" in desc_up:
            sku = "SKU NEGOCIAR"
        if "SEM PRECO" in desc_up:
            sku = "SKU SEM PRECO"
        return {"sku_master_exibicao": sku, "produto_padrao": sku, "categoria": "CORRELATOS", "fabricante": "FAB"}, 99

    def menor_custo(sku_master, conn_existente=None):
        if sku_master == "SKU SEM PRECO":
            return {"encontrado": False, "sku_master": sku_master}
        custo = 10 if sku_master == "SKU VENCE" else 20
        return {
            "encontrado": True,
            "sku_master": sku_master,
            "menor_custo": custo,
            "fornecedor": "FORNECEDOR TESTE",
            "marca": "MARCA TESTE",
            "categoria": "CORRELATOS",
            "produto_id": 1,
            "preco_id": 2,
            "data_preco": "",
            "descricao_fornecedor": "",
        }

    lances._montar_indice_rapido_lances = lambda: None
    lances.encontrar_sku_automatico_rapido_lances = candidato
    lances.buscar_menor_custo_por_sku_master = menor_custo


def _item(desc, qtd, preco):
    return {
        "descricao_original": desc,
        "descricao_cotacao": desc,
        "categoria": "CORRELATOS",
        "unidade_compra": "UNID",
        "quantidade": qtd,
        "quantidade_raw": qtd,
        "preco_osinfo": preco,
        "ultima_compra": 0,
        "menor_lance": 0,
        "empresa_melhor_lance": "",
    }


def test_backend_indicadores():
    _patch_backend_sem_banco()
    descricao = "PRODUTO VENCE ORIGINAL"
    itens = [
        _item(descricao, 7000.0, 30),
        _item("PRODUTO NEGOCIAR", 10000, 15),
        _item("PRODUTO SEM PRECO", 5, 30),
        _item("PRODUTO REVISAR", 8, 30),
        _item("ZERO", 0, 30),
        _item("VAZIO", "", 30),
        _item("NEGATIVO", -1, 30),
    ]
    analise = lances.analisar_itens_lances(itens, markup_percentual=80)
    resumo = analise["resumo"]

    assert analise["total_linhas_arquivo"] == 7
    assert analise["total_itens_com_quantidade"] == 4
    assert analise["total_ignorados_quantidade_zero"] == 1
    assert analise["total_ignorados_quantidade_vazia"] == 1
    assert analise["total_ignorados_quantidade_invalida"] == 1
    assert len(analise["itens"]) == 4
    assert analise["itens"][0]["descricao_original"] == descricao
    assert analise["itens"][0]["quantidade_formatada"] == "7000"
    assert lances.formatar_quantidade_cotacao(10000) == "10000"
    assert analise["itens"][0]["preco_osinfo"] == 30
    assert analise["itens"][0]["status"] == "MEDBOX VENCE"
    assert analise["itens"][1]["status"] == "NEGOCIAR"
    assert analise["itens"][2]["status"] == "SEM PRE\u00c7O"
    assert analise["itens"][3]["status"] == "REVISAR SKU"
    assert resumo["total_itens"] == 4
    assert resumo["itens_ganhos_medbox"] == 1
    assert resumo["percentual_itens_ganhos_formatado"] == "25,00%"
    assert resumo["total_ganho_medbox"] == 126000.0
    assert resumo["total_ganho_medbox_formatado"] == "R$ 126.000,00"


def test_moeda_e_parse_js_presentes():
    js = JS_PATH.read_text(encoding="utf-8")
    assert "function parseNumeroBR" in js
    assert "function formatarMoedaBR" in js
    assert "Intl.NumberFormat" in js and "pt-BR" in js
    assert lances.moeda_br(1234.56) == "R$ 1.234,56"
    assert lances._lances_float_decimal("R$ 1.234,56", "0") == 1234.56
    assert lances._lances_float_decimal("0,2075", "0") == 0.2075


def test_template_sem_mojibake_e_com_campos_novos():
    html = TEMPLATE_PATH.read_text(encoding="utf-8")
    proibidos = ["\u00c3\u00a7", "\u00c3\u00a3", "\u00c3\u00a9", "\u00c3\u0087", "\u00c3\u0083", "\u00c2", "\u00e2\u20ac", "\ufffd", "\u0102"]
    for padrao in proibidos:
        assert padrao not in html, f"padrao de mojibake encontrado: {padrao!r}"
    esperados = [
        "COTA\u00c7\u00c3O - LANCES",
        "Cr\u00edtica operacional item a item",
        "Descri\u00e7\u00e3o do Produto",
        "Cota\u00e7\u00e3o original",
        "Pre\u00e7o OSINFO",
        "\u00dalt. Compra da Cota\u00e7\u00e3o",
        "A\u00e7\u00e3o SKU",
        "Itens ganhos MedBox",
        "% itens ganhos",
        "Total ganho MedBox",
        "data-medbox-vence",
        "step=\"1\"",
    ]
    for texto in esperados:
        assert texto in html, texto


def test_regra_backend_compartilhada_com_js():
    casos = [
        ({"sku_master": "", "sku_encontrado": False, "menor_custo_encontrado": 10, "preco_medbox": 18, "preco_osinfo": 20, "quantidade": 1}, "REVISAR SKU", False),
        ({"sku_master": "SKU", "sku_encontrado": True, "menor_custo_encontrado": 0, "preco_medbox": 0, "preco_osinfo": 20, "quantidade": 1}, "SEM PRE\u00c7O", False),
        ({"sku_master": "SKU", "sku_encontrado": True, "menor_custo_encontrado": 10, "preco_medbox": 18, "preco_osinfo": 20, "quantidade": 1}, "MEDBOX VENCE", True),
        ({"sku_master": "SKU", "sku_encontrado": True, "menor_custo_encontrado": 10, "preco_medbox": 20, "preco_osinfo": 20, "quantidade": 1}, "MEDBOX VENCE", True),
        ({"sku_master": "SKU", "sku_encontrado": True, "menor_custo_encontrado": 10, "preco_medbox": 21, "preco_osinfo": 20, "quantidade": 1}, "NEGOCIAR", False),
        ({"sku_master": "SKU", "sku_encontrado": True, "menor_custo_encontrado": 10, "preco_medbox": 10, "preco_osinfo": 10, "quantidade": 1}, "MEDBOX VENCE", True),
        ({"sku_master": "SKU", "sku_encontrado": True, "menor_custo_encontrado": 0, "preco_medbox": 0, "preco_osinfo": 10, "quantidade": 1}, "SEM PRE\u00c7O", False),
    ]
    for item, status, vence in casos:
        resultado = lances.avaliar_resultado_item_lance(item)
        assert resultado["status"] == status
        assert resultado["medbox_vence"] is vence

    _patch_backend_sem_banco()
    analise = lances.analisar_itens_lances([
        _item("PRODUTO VENCE", 0, 30),
        _item("PRODUTO VENCE", 1, 30),
    ], markup_percentual=80)
    assert len(analise["itens"]) == 1
    assert analise["total_ignorados_quantidade_zero"] == 1


def test_total_ganho_usa_menor_valor_vencedor():
    item = {
        "quantidade": 10,
        "medbox_vence": True,
        "menor_valor_vencedor": 7,
        "empresa_vencedora": "MEDBOX",
        "preco_medbox": 9,
    }
    assert lances.calcular_valor_ganho_item(item) == 70
    item["empresa_vencedora"] = "OUTRA EMPRESA"
    assert lances.calcular_valor_ganho_item(item) == 0
    item["empresa_vencedora"] = "MEDBOX DISTRIBUIDORA DE MEDICAMENTOS"
    assert lances.calcular_valor_ganho_item(item) == 70
    item["menor_valor_vencedor"] = 0
    assert lances.calcular_valor_ganho_item(item) == 0


if __name__ == "__main__":
    test_backend_indicadores()
    test_moeda_e_parse_js_presentes()
    test_template_sem_mojibake_e_com_campos_novos()
    test_regra_backend_compartilhada_com_js()
    print("OK: lances_layout_indicadores_test passou")