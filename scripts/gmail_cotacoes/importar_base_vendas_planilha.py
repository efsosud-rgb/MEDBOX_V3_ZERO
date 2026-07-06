"""Importa a planilha normalizada de vendas Fev-Mai 2026 para o banco.

Lê data/dashboard_comercial/vendas_fev_mai_2026_normalizada_metas.xlsx e
grava em:
- dashboard_vendas_historicas  <- aba Vendas_Base_Normalizada
- dashboard_metas_vendedora    <- aba Metas_Vendedora_Jun
- dashboard_metas_cliente      <- aba Metas_Cliente_Jun

Idempotente (pode rodar várias vezes sem duplicar):
- dashboard_metas_vendedora/cliente têm índice único (ano, mes_num,
  vendedora/cliente) -> upsert nativo do SQLite (INSERT ... ON CONFLICT).
- dashboard_vendas_historicas não tem uma chave natural única (o mesmo
  cliente pode ter múltiplas linhas sem numero_oc, p.ex. "SEM OC") -> a
  cada execução, apaga só as linhas com fonte='PLANILHA_FEV_MAI_2026' e
  reinsere a partir da planilha. Não mexe em linhas de outras fontes
  (ex.: vendas que no futuro vierem do Gmail real, fonte diferente).

Não fala com o Gmail. Não altera nenhuma outra tabela do banco.
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import openpyxl

from core import banco

CAMINHO_PLANILHA = BASE_DIR / "data" / "dashboard_comercial" / "vendas_fev_mai_2026_normalizada_metas.xlsx"
FONTE_ESPERADA = "PLANILHA_FEV_MAI_2026"


def _ler_aba_como_dicts(ws) -> list[dict]:
    cabecalho = [c.value for c in ws[1]]
    linhas = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        if all(v is None for v in row):
            continue
        linhas.append(dict(zip(cabecalho, row)))
    return linhas


def importar_vendas_historicas(cursor, linhas: list[dict], agora: str) -> int:
    cursor.execute("DELETE FROM dashboard_vendas_historicas WHERE fonte = ?", (FONTE_ESPERADA,))
    for linha in linhas:
        cursor.execute(
            """INSERT INTO dashboard_vendas_historicas
               (ano, mes_num, mes_nome, vendedora, cliente, numero_oc, valor_vendido, fonte, criado_em, atualizado_em)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                linha["ano"], linha["mes_num"], linha.get("mes_nome"),
                linha["vendedora"], linha.get("cliente"), linha.get("numero_oc"),
                linha["valor_vendido"], linha.get("fonte") or FONTE_ESPERADA,
                agora, agora,
            ),
        )
    return len(linhas)


def importar_metas_vendedora(cursor, linhas: list[dict], agora: str) -> int:
    for linha in linhas:
        cursor.execute(
            """INSERT INTO dashboard_metas_vendedora
               (ano, mes_num, vendedora, media_fev_mai, meta_valor, percentual_meta, fonte, criado_em, atualizado_em)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(ano, mes_num, vendedora) DO UPDATE SET
                   media_fev_mai = excluded.media_fev_mai,
                   meta_valor = excluded.meta_valor,
                   percentual_meta = excluded.percentual_meta,
                   fonte = excluded.fonte,
                   atualizado_em = excluded.atualizado_em""",
            (
                linha["ano"], linha["mes_num"], linha["vendedora"],
                linha.get("media_fev_mai"), linha.get("meta_valor"), linha.get("percentual_meta"),
                linha.get("fonte") or FONTE_ESPERADA, agora, agora,
            ),
        )
    return len(linhas)


def importar_metas_cliente(cursor, linhas: list[dict], agora: str) -> int:
    for linha in linhas:
        cursor.execute(
            """INSERT INTO dashboard_metas_cliente
               (ano, mes_num, cliente, media_fev_mai, meta_valor, percentual_meta, fonte, criado_em, atualizado_em)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(ano, mes_num, cliente) DO UPDATE SET
                   media_fev_mai = excluded.media_fev_mai,
                   meta_valor = excluded.meta_valor,
                   percentual_meta = excluded.percentual_meta,
                   fonte = excluded.fonte,
                   atualizado_em = excluded.atualizado_em""",
            (
                linha["ano"], linha["mes_num"], linha["cliente"],
                linha.get("media_fev_mai"), linha.get("meta_valor"), linha.get("percentual_meta"),
                linha.get("fonte") or FONTE_ESPERADA, agora, agora,
            ),
        )
    return len(linhas)


def main() -> int:
    if not CAMINHO_PLANILHA.exists():
        print(f"ERRO: planilha não encontrada em {CAMINHO_PLANILHA}")
        return 1

    wb = openpyxl.load_workbook(CAMINHO_PLANILHA, data_only=True)
    abas_esperadas = ["Vendas_Base_Normalizada", "Metas_Vendedora_Jun", "Metas_Cliente_Jun"]
    faltando = [a for a in abas_esperadas if a not in wb.sheetnames]
    if faltando:
        print(f"ERRO: abas faltando na planilha: {faltando}")
        return 1

    vendas = _ler_aba_como_dicts(wb["Vendas_Base_Normalizada"])
    metas_vendedora = _ler_aba_como_dicts(wb["Metas_Vendedora_Jun"])
    metas_cliente = _ler_aba_como_dicts(wb["Metas_Cliente_Jun"])

    banco.criar_banco()
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = banco.conectar()
    cursor = conn.cursor()
    try:
        n_vendas = importar_vendas_historicas(cursor, vendas, agora)
        n_metas_vendedora = importar_metas_vendedora(cursor, metas_vendedora, agora)
        n_metas_cliente = importar_metas_cliente(cursor, metas_cliente, agora)
        conn.commit()
    finally:
        conn.close()

    print(f"Vendas históricas importadas: {n_vendas}")
    print(f"Metas por vendedora importadas: {n_metas_vendedora}")
    print(f"Metas por cliente importadas: {n_metas_cliente}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
