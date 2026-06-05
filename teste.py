import sqlite3
conn = sqlite3.connect('banco/medbox_v3.db')
c = conn.cursor()
c.execute("SELECT produto_padrao FROM produtos WHERE produto_padrao LIKE '%CLORETO%' LIMIT 5")
print([r[0] for r in c.fetchall()])