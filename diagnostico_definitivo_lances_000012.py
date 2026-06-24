import inspect
from core.banco import conectar
import app as medbox_app

numero = "MEDBOX-2026-000012"

print("=" * 120)
print("1) ENDPOINTS REGISTRADOS NO FLASK")
print("=" * 120)

for rule in medbox_app.app.url_map.iter_rules():
    rota = str(rule.rule)
    if rota in [
        "/cotacoes/lances/atualizar-cotacao/<numero_cotacao>",
        "/cotacoes/geradas/<numero_cotacao>/editar",
        "/cotacoes/lances/gerar-cotacao",
    ]:
        endpoint = rule.endpoint
        func = medbox_app.app.view_functions.get(endpoint)
        print("ROTA:", rota)
        print("ENDPOINT:", endpoint)
        print("FUNÇÃO:", getattr(func, "__name__", func))
        try:
            print("ARQUIVO:", inspect.getsourcefile(func))
            print("LINHA:", inspect.getsourcelines(func)[1])
        except Exception as e:
            print("Não foi possível inspecionar:", e)
        print("-" * 120)

print("\n" + "=" * 120)
print("2) COLUNAS REAIS DA TABELA cotacoes_geradas_itens")
print("=" * 120)

conn = conectar()
conn.row_factory = None
cur = conn.cursor()

cur.execute("PRAGMA table_info(cotacoes_geradas_itens)")
colunas_info = cur.fetchall()
colunas = [c[1] for c in colunas_info]

for c in colunas_info:
    print(c)

obrigatorias = [
    "categoria",
    "ultima_compra",
    "menor_custo_unitario",
    "fornecedor_menor_custo",
    "markup_atual",
    "preco_medbox_original",
    "preco_osinfo",
    "menor_lance",
    "empresa_melhor_lance",
]

print("\nCOLUNAS OBRIGATÓRIAS:")
for nome in obrigatorias:
    print(nome, "=", "EXISTE" if nome in colunas else "NÃO EXISTE")

print("\n" + "=" * 120)
print("3) DADOS SALVOS NA COTAÇÃO", numero)
print("=" * 120)

cur.execute("""
SELECT id
FROM cotacoes_geradas
WHERE numero_cotacao = ?
""", (numero,))

cot = cur.fetchone()

if not cot:
    print("ERRO: cotação não encontrada:", numero)
    conn.close()
    raise SystemExit

cotacao_id = cot[0]

cur.execute("""
SELECT *
FROM cotacoes_geradas_itens
WHERE cotacao_id = ?
ORDER BY item_numero
LIMIT 5
""", (cotacao_id,))

rows = cur.fetchall()
nomes_colunas = [d[0] for d in cur.description]

for row in rows:
    d = dict(zip(nomes_colunas, row))

    print("\n--- ITEM", d.get("item_numero"), "---")
    for campo in [
        "descricao_produto",
        "sku_master",
        "categoria",
        "quantidade",
        "preco_osinfo",
        "ultima_compra",
        "preco_medbox_original",
        "markup_atual",
        "menor_lance",
        "empresa_melhor_lance",
        "menor_custo_unitario",
        "fornecedor_menor_custo",
        "marca",
        "menor_origem",
        "menor_empresa",
        "menor_valor_comparativo",
        "valor_total_vencedor",
    ]:
        print(f"{campo}: {d.get(campo)}")

conn.close()

print("\n" + "=" * 120)
print("CONCLUSÃO AUTOMÁTICA")
print("=" * 120)

for row in rows[:1]:
    d = dict(zip(nomes_colunas, row))

    problemas = []

    if not d.get("categoria") or str(d.get("categoria")).upper() in ["NONE", "-", ""]:
        problemas.append("categoria não está persistida corretamente")

    if not d.get("ultima_compra") or float(d.get("ultima_compra") or 0) <= 0:
        problemas.append("ultima_compra não está persistida corretamente")

    if not d.get("menor_custo_unitario") or float(d.get("menor_custo_unitario") or 0) <= 0:
        problemas.append("menor_custo_unitario não está persistido corretamente")

    if not d.get("fornecedor_menor_custo") or str(d.get("fornecedor_menor_custo")).upper() in ["NONE", "-", ""]:
        problemas.append("fornecedor_menor_custo não está persistido corretamente")

    if problemas:
        print("O ERRO ESTÁ NO SALVAMENTO OU NO PAYLOAD ENVIADO AO BACKEND.")
        print("Problemas encontrados:")
        for p in problemas:
            print("-", p)
    else:
        print("O BANCO ESTÁ CORRETO. O ERRO ESTÁ NA FUNÇÃO QUE REABRE/MONTA A TELA DE EDIÇÃO.")
