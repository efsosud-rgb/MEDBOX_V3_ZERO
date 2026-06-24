import sqlite3
import shutil
from pathlib import Path
from datetime import datetime

DB = Path("banco/medbox_v3.db")
BACKUP_DIR = Path("banco/backups")
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

backup = BACKUP_DIR / f"medbox_v3_backup_unificar_tubo_c_cuff_sem_pvc_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
shutil.copy2(DB, backup)

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

rows = cur.execute("""
SELECT id, produto_padrao, sku_master, categoria, fabricante, observacoes
FROM produtos
WHERE UPPER(COALESCE(sku_master,'')) LIKE 'TUBO ENDOTRAQUEAL C/CUFF PVC %'
ORDER BY id
""").fetchall()

try:
    conn.execute("BEGIN")

    for r in rows:
        sku_antigo = r["sku_master"] or ""
        sku_novo = sku_antigo.replace("TUBO ENDOTRAQUEAL C/CUFF PVC ", "TUBO ENDOTRAQUEAL C/CUFF ")

        obs_antiga = r["observacoes"] or ""
        nota = (
            f"SKU_MASTER unificado em {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}: "
            f"PVC removido do SKU_MASTER porque não diferencia comercialmente este produto. "
            f"SKU anterior: {sku_antigo}."
        )
        obs_nova = (obs_antiga + "\n" + nota).strip() if obs_antiga else nota

        cur.execute("""
        UPDATE produtos
        SET sku_master = ?,
            observacoes = ?
        WHERE id = ?
        """, (sku_novo, obs_nova, r["id"]))

        cur.execute("""
        INSERT INTO sku_master_regras_aplicacoes (
            regra_id,
            produto_id,
            descricao_original,
            sku_master_anterior,
            sku_master_aplicado,
            categoria_anterior,
            categoria_aplicada,
            fabricante_anterior,
            fabricante_aplicado,
            motivo,
            confianca,
            aplicado_por
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            1,
            r["id"],
            r["produto_padrao"] or "",
            sku_antigo,
            sku_novo,
            r["categoria"] or "",
            r["categoria"] or "",
            r["fabricante"] or "",
            r["fabricante"] or "",
            "UNIFICACAO_MANUAL_APROVADA_PELO_USUARIO_REMOVER_PVC_DO_SKU_MASTER",
            "REGRA_VALIDADA_USUARIO",
            "ERIC"
        ))

    cur.execute("""
    UPDATE sku_master_regras
    SET sku_master_padrao = 'TUBO ENDOTRAQUEAL C/CUFF {MEDIDA}',
        observacoes = COALESCE(observacoes, '') || char(10) || ?,
        exemplos_positivos = COALESCE(exemplos_positivos, '') || char(10) || ?
    WHERE familia = 'TUBO ENDOTRAQUEAL'
    """, (
        "REGRA APRENDIDA: PVC/POLIVINIL/CLORETO DE POLIVINILA não diferencia SKU_MASTER para TUBO ENDOTRAQUEAL C/CUFF. Padronizar como TUBO ENDOTRAQUEAL C/CUFF {MEDIDA}.",
        "TUBO OROTRAQUEAL COM BALAO POLIVINIL 8,5MM => TUBO ENDOTRAQUEAL C/CUFF 8,5MM"
    ))

    conn.commit()

except Exception as e:
    conn.rollback()
    conn.close()
    raise SystemExit(f"ERRO: rollback executado. Motivo: {e}")

print("Backup criado:", backup)
print("Itens unificados:", len(rows))
print("")
print("Verificação pós-unificação:")

for r in cur.execute("""
SELECT id, produto_padrao, sku_master, categoria
FROM produtos
WHERE id IN (6207,6208,6209,10624,11095,11096,11097)
ORDER BY id
"""):
    print(f"ID {r['id']} | {r['sku_master']} | {r['categoria']}")

print("")
print("Contagem:")
q1 = cur.execute("""
SELECT COUNT(*) total
FROM produtos
WHERE UPPER(COALESCE(sku_master,'')) LIKE 'TUBO ENDOTRAQUEAL C/CUFF PVC%'
""").fetchone()["total"]

q2 = cur.execute("""
SELECT COUNT(*) total
FROM produtos
WHERE UPPER(COALESCE(sku_master,'')) LIKE 'TUBO ENDOTRAQUEAL C/CUFF%'
""").fetchone()["total"]

print("Ainda com C/CUFF PVC:", q1)
print("Total C/CUFF:", q2)

conn.close()
