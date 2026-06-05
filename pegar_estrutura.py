import sqlite3

try:
    conn = sqlite3.connect("banco/medbox_v3.db")
    cursor = conn.cursor()
    
    # Busca a estrutura de criação de todas as tabelas
    cursor.execute("SELECT sql FROM sqlite_master WHERE type='table';")
    tabelas = cursor.fetchall()
    
    with open("estrutura_banco.txt", "w", encoding="utf-8") as f:
        for tabela in tabelas:
            if tabela[0]:
                f.write(tabela[0] + "\n")
                f.write("-" * 40 + "\n")
                
    print("Sucesso! O arquivo 'estrutura_banco.txt' foi gerado.")

except Exception as e:
    print(f"Erro ao acessar o banco: {e}")

finally:
    if 'conn' in locals():
        conn.close()