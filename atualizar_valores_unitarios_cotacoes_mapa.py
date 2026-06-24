from pathlib import Path
from openpyxl import load_workbook

from core.banco import conectar
from core.mapa_precos_clientes import normalizar_texto_mapa, converter_float_mapa

ARQUIVOS = [
    ("VIVA RIO", Path("uploads/Cotacao_VivaRio.xlsx")),
    ("HD CID ADEMAR", Path("uploads/Cotacao_HD_Cid_Ademar.xlsx")),
    ("AFNE", Path("uploads/Cotacao_AFNE.xlsx")),
]

def detectar_colunas(cabecalhos):
    normalizados = [normalizar_texto_mapa(c) for c in cabecalhos]

    def achar(possiveis):
        for termo in possiveis:
            termo_n = normalizar_texto_mapa(termo)
            for idx, cab in enumerate(normalizados):
                if termo_n == cab or termo_n in cab:
                    return idx
        return None

    return {
        "categoria": achar(["CATEGORIA"]),
        "descricao": achar(["PRODUTO", "PRODUTOS", "DESCRICAO", "ITEM", "MATERIAL"]),
        "quantidade": achar(["QUANTIDADE", "QUANT", "QUANT.", "QTDE", "QTD"]),
        "valor_unitario": achar(["V UNIT", "V. UNIT", "VALOR UNITARIO", "VL UNIT", "PRECO UNITARIO", "PRECO", "VALOR"]),
    }

def ler_precos_arquivo(path):
    wb = load_workbook(path, data_only=True, read_only=True)
    ws = wb.active
    linhas = list(ws.iter_rows(values_only=True))
    wb.close()

    melhor = None

    for idx, row in enumerate(linhas[:30]):
        cabecalhos = [str(c or "").strip() for c in row]
        det = detectar_colunas(cabecalhos)

        score = 0
        if det["descricao"] is not None:
            score += 3
        if det["quantidade"] is not None:
            score += 2
        if det["valor_unitario"] is not None:
            score += 2
        if det["categoria"] is not None:
            score += 1

        if not melhor or score > melhor["score"]:
            melhor = {
                "idx": idx,
                "score": score,
                "det": det,
            }

    if not melhor or melhor["det"]["descricao"] is None or melhor["det"]["valor_unitario"] is None:
        raise RuntimeError(f"Não consegui detectar Produto e V. Unit em {path}")

    det = melhor["det"]
    mapa = {}

    for row in linhas[melhor["idx"] + 1:]:
        idx_desc = det["descricao"]
        idx_valor = det["valor_unitario"]

        if idx_desc >= len(row) or idx_valor >= len(row):
            continue

        descricao = normalizar_texto_mapa(row[idx_desc])
        valor = converter_float_mapa(row[idx_valor])

        if not descricao:
            continue

        mapa[descricao] = valor

    return mapa

conn = conectar()
conn.row_factory = None
cur = conn.cursor()

total_geral = 0

for cliente_nome, arquivo in ARQUIVOS:
    print("=" * 100)
    print("CLIENTE:", cliente_nome)
    print("ARQUIVO:", arquivo)
    print("=" * 100)

    if not arquivo.exists():
        print("Arquivo não encontrado. Pulando.")
        continue

    precos = ler_precos_arquivo(arquivo)

    com_preco = sum(1 for v in precos.values() if v > 0)
    sem_preco = sum(1 for v in precos.values() if v == 0)

    print("Itens lidos:", len(precos))
    print("Com preço:", com_preco)
    print("Sem preço:", sem_preco)

    atualizados = 0

    for descricao, valor in precos.items():
        if valor <= 0:
            continue

        cur.execute("""
            UPDATE cotacoes_clientes_mapa_itens
            SET valor_unitario = ?,
                valor_total = quantidade_total * ?
            WHERE id IN (
                SELECT i.id
                FROM cotacoes_clientes_mapa_itens i
                JOIN clientes_mapa_precos c ON c.id = i.cliente_id
                WHERE UPPER(TRIM(c.nome)) = UPPER(TRIM(?))
                  AND UPPER(TRIM(i.descricao_original)) = UPPER(TRIM(?))
            )
        """, (valor, valor, cliente_nome, descricao))

        atualizados += cur.rowcount

    print("Registros atualizados no banco:", atualizados)
    total_geral += atualizados

conn.commit()
conn.close()

print("\nOK: atualização concluída.")
print("Total geral atualizado:", total_geral)
