import sqlite3
import shutil
from pathlib import Path
from datetime import datetime

DB = Path("banco/medbox_v3.db")
BACKUP_DIR = Path("banco/backups")
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

backup = BACKUP_DIR / f"medbox_v3_backup_regra_tubo_sem_material_bloqueia_aramado_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
shutil.copy2(DB, backup)

conn = sqlite3.connect(DB)
cur = conn.cursor()

REGRA = "REGRA_TUBO_ENDOTRAQUEAL_C_BALAO_SEM_MATERIAL_MEDIDA_VARIAVEL"

cur.execute("""
UPDATE sku_master_regras
SET termos_proibidos = COALESCE(termos_proibidos, '') || char(10) || ?,
    exemplos_negativos = COALESCE(exemplos_negativos, '') || char(10) || ?,
    observacoes = COALESCE(observacoes, '') || char(10) || ?
WHERE nome_regra = ?
""", (
    "ARAMADO\nREFORCADO\nFLEXOMETALICO\nFLEXO METALICO",
    "TUBO ENDOTRAQUEAL ARAMADO N 7,0 COM CUFF => não aplicar regra comum; precisa de regra própria ARAMADO.",
    "REGRA APRENDIDA: tubo endotraqueal ARAMADO/REFORCADO/FLEXOMETALICO é família diferente da regra comum sem material.",
    REGRA
))

conn.commit()
conn.close()

print("Backup criado:", backup)
print("OK: regra atualizada para bloquear ARAMADO/REFORCADO/FLEXOMETALICO.")
