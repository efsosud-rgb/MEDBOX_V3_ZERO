import sqlite3
import sys
import tempfile
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

stub_lances = types.ModuleType("core.lances_cotacao")
stub_lances.importar_lances_cotacao = lambda *args, **kwargs: []
sys.modules.setdefault("core.lances_cotacao", stub_lances)

import app as medbox_app


def conectar_tmp_factory(db_path):
    def conectar_tmp():
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn
    return conectar_tmp


def payload_item(descricao, quantidade, preco_osinfo, preco_medbox, menor_lance=0, empresa_lance="", sku="SKU TESTE", status="FALSO", vencedor="OUTRA"):
    return {
        "descricao_original": descricao,
        "descricao_produto": descricao,
        "sku_master": sku,
        "categoria": "CORRELATOS",
        "quantidade": quantidade,
        "preco_osinfo": preco_osinfo,
        "preco_medbox": preco_medbox,
        "menor_preco_ofertado": menor_lance,
        "empresa_melhor_lance": empresa_lance,
        "menor_custo_unitario": 0,
        "markup_atual": 80,
        "fornecedor_menor_custo": "FORN TESTE",
        "marca_fabricante": "MARCA TESTE",
        "status": status,
        "vencedor": vencedor,
    }


def buscar_cotacao(conn, numero):
    cur = conn.cursor()
    cur.execute("SELECT * FROM cotacoes_geradas WHERE numero_cotacao = ?", (numero,))
    cot = cur.fetchone()
    cur.execute("SELECT * FROM cotacoes_geradas_itens WHERE cotacao_id = ? ORDER BY item_numero", (cot["id"],))
    return cot, cur.fetchall()


def post_gerar(client, itens):
    resp = client.post("/cotacoes/lances/gerar-cotacao", json={"cliente": "TESTE", "itens": itens})
    assert resp.status_code == 200, resp.get_data(as_text=True)
    data = resp.get_json()
    assert data["ok"] is True
    return data["numero_cotacao"]


def post_atualizar(client, numero, itens):
    resp = client.post(f"/cotacoes/lances/atualizar-cotacao/{numero}", json={"cliente": "TESTE", "itens": itens})
    assert resp.status_code == 200, resp.get_data(as_text=True)
    data = resp.get_json()
    assert data["ok"] is True


def cinco_vencedores_afne_fixture():
    return [
        payload_item("AGULHA 40 X 12", 10000, 0.2075, 0.1188),
        payload_item("ALGODAO HIDROFILO", 500, 30, 20.556),
        payload_item("AVENTAL DESCARTAVEL", 2000, 60, 53.93844),
        payload_item("CATETER FEMURAL", 10, 0.02, 0.01),
        payload_item("KIT MARCAPASSO", 1, 200, 118.62),
    ]


def main():
    original_conectar = medbox_app.conectar
    with tempfile.TemporaryDirectory() as td:
        db_path = Path(td) / "persistencia_lances.db"
        medbox_app.conectar = conectar_tmp_factory(db_path)
        try:
            medbox_app._pr53_garantir_colunas_lances()
            client = medbox_app.app.test_client()

            # Payload sem vencedor/status e com status/vencedor falsificados: backend recalcula.
            numero = post_gerar(client, [payload_item("MEDBOX VENCE", 10, 20, 18, status="NEGOCIAR", vencedor="OSINFO")])
            conn = medbox_app.conectar()
            cot, itens = buscar_cotacao(conn, numero)
            assert round(cot["total_geral"], 2) == 180.00
            assert itens[0]["venceu_medbox"] == 1
            assert itens[0]["valor_unitario"] == 18
            assert itens[0]["valor_total"] == 180
            assert itens[0]["status_lance"] == "MEDBOX VENCE"
            assert itens[0]["menor_valor_comparativo"] == 18
            conn.close()

            # Derrota: valor ganho zerado, preservando informativos.
            numero_derrota = post_gerar(client, [payload_item("DERROTA", 3, 10, 12, menor_lance=9, empresa_lance="CONCORRENTE")])
            conn = medbox_app.conectar()
            cot, itens = buscar_cotacao(conn, numero_derrota)
            assert cot["total_geral"] == 0
            assert itens[0]["venceu_medbox"] == 0
            assert itens[0]["valor_unitario"] == 0
            assert itens[0]["valor_total"] == 0
            assert itens[0]["preco_osinfo"] == 10
            assert itens[0]["menor_lance"] == 9
            assert itens[0]["preco_medbox_original"] == 12
            conn.close()

            # Empates: MEDBOX > OSINFO > concorrente.
            numero_empate_osinfo = post_gerar(client, [payload_item("EMPATE OSINFO", 2, 10, 10)])
            numero_empate_lance = post_gerar(client, [payload_item("EMPATE LANCE", 2, 15, 10, menor_lance=10, empresa_lance="CONCORRENTE")])
            conn = medbox_app.conectar()
            for numero_empate in [numero_empate_osinfo, numero_empate_lance]:
                cot, itens = buscar_cotacao(conn, numero_empate)
                assert cot["total_geral"] == 20
                assert itens[0]["venceu_medbox"] == 1
                assert itens[0]["valor_unitario"] == 10
                assert itens[0]["valor_total"] == 20
            conn.close()

            # Quantidade zero: neutra.
            numero_zero = post_gerar(client, [payload_item("ZERO", 0, 10, 1)])
            conn = medbox_app.conectar()
            cot, itens = buscar_cotacao(conn, numero_zero)
            status_zero = itens[0]["status_lance"]
            conn.close()
            assert cot["total_geral"] == 0
            assert itens[0]["venceu_medbox"] == 0
            assert itens[0]["valor_total"] == 0
            assert status_zero.startswith("FORA DA COTA")

            # Fixture AFNE: 5 vitorias e total esperado.
            numero_afne = post_gerar(client, cinco_vencedores_afne_fixture())
            conn = medbox_app.conectar()
            cot, itens = buscar_cotacao(conn, numero_afne)
            assert len([i for i in itens if i["venceu_medbox"] == 1]) == 5
            assert round(cot["total_geral"], 2) == 119461.60
            assert round(sum(i["valor_total"] for i in itens), 2) == 119461.60
            conn.close()

            # Atualizacao usa mesma regra da criacao.
            post_atualizar(client, numero_afne, cinco_vencedores_afne_fixture())
            conn = medbox_app.conectar()
            cot, itens = buscar_cotacao(conn, numero_afne)
            assert len([i for i in itens if i["venceu_medbox"] == 1]) == 5
            assert round(cot["total_geral"], 2) == 119461.60
            assert round(sum(i["valor_total"] for i in itens), 2) == 119461.60
            conn.close()
        finally:
            medbox_app.conectar = original_conectar

    print("OK: lances_persistencia_cotacao_test passou")


if __name__ == "__main__":
    main()
