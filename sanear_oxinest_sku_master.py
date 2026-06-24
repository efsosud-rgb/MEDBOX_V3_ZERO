from core.banco import conectar

SKU = "OXINEST 4 MG/ML FR 1OML - OXIBUPROCAINA"

conn = conectar()
conn.row_factory = None
cur = conn.cursor()

cur.execute("PRAGMA table_info(produtos)")
cols = {row[1] for row in cur.fetchall()}

if "sku_corrigido" not in cols:
    cur.execute("ALTER TABLE produtos ADD COLUMN sku_corrigido INTEGER DEFAULT 0")

if "corrigido_em" not in cols:
    cur.execute("ALTER TABLE produtos ADD COLUMN corrigido_em TEXT")

cur.execute("""
    SELECT id, produto_padrao, sku_master, fabricante, categoria, ativo
    FROM produtos
    WHERE UPPER(TRIM(COALESCE(sku_master, ''))) = UPPER(TRIM(?))
       OR UPPER(TRIM(COALESCE(produto_padrao, ''))) = UPPER(TRIM(?))
    ORDER BY 
        CASE WHEN sku IS NOT NULL AND TRIM(sku) != '' THEN 0 ELSE 1 END,
        id
""", (SKU, SKU))

rows = cur.fetchall()

print("Produtos encontrados:")
for r in rows:
    print(r)

if not rows:
    print("Nenhum produto encontrado.")
    raise SystemExit

destino_id = rows[0][0]
fabricante = rows[0][3] or "CRISTALIA"
categoria = rows[0][4] or "MEDICAMENTOS"

print("\nDestino escolhido:", destino_id)

for r in rows[1:]:
    origem_id = r[0]

    cur.execute("UPDATE precos_fornecedores SET produto_id = ? WHERE produto_id = ?", (destino_id, origem_id))
    print("Preços migrados de", origem_id, ":", cur.rowcount)

    cur.execute("UPDATE equivalencias SET produto_id = ? WHERE produto_id = ?", (destino_id, origem_id))
    print("Equivalências migradas de", origem_id, ":", cur.rowcount)

    cur.execute("""
        UPDATE produtos
        SET ativo = 0,
            sku_corrigido = 1,
            corrigido_em = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (origem_id,))
    print("Produto inativado:", origem_id, "linhas:", cur.rowcount)

cur.execute("""
    UPDATE produtos
    SET sku_master = ?,
        fabricante = ?,
        categoria = ?,
        sku_corrigido = 1,
        corrigido_em = CURRENT_TIMESTAMP,
        ativo = 1
    WHERE id = ?
""", (SKU, fabricante, categoria, destino_id))

cur.execute("""
    UPDATE precos_fornecedores
    SET marca = ?
    WHERE produto_id = ?
      AND (marca IS NULL OR TRIM(marca) = '')
""", (fabricante, destino_id))

print("Preços com marca preenchida:", cur.rowcount)

conn.commit()
conn.close()

print("\nOK: saneamento OXINEST concluído.")
