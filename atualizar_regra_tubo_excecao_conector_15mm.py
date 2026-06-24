from pathlib import Path
from datetime import datetime
import shutil
import sqlite3

DB = Path("banco/medbox_v3.db")
BACKUP_DIR = Path("banco/backups")
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

backup = BACKUP_DIR / f"medbox_v3_backup_regra_tubo_medida_corrigida_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
shutil.copy2(DB, backup)

conn = sqlite3.connect(DB)
cur = conn.cursor()

cur.execute("""
UPDATE sku_master_regras
SET observacoes = COALESCE(observacoes, '') || char(10) || ?,
    exemplos_negativos = COALESCE(exemplos_negativos, '') || char(10) || ?
WHERE nome_regra = ?
""", (
    "REGRA APRENDIDA: em tubo endotraqueal, 'CONECTOR DE 15MM' não é medida do tubo. A medida principal deve priorizar Nº/N/TAM antes de qualquer MM solto.",
    "TUBO ENDOTRAQUEAL ... CONECTOR DE 15MM ... Nº 7.5 => medida correta 7,5MM, não 15MM.",
    "REGRA_TUBO_ENDOTRAQUEAL_C_BALAO_PVC_MEDIDA_VARIAVEL"
))

conn.commit()
conn.close()

print("Backup criado:", backup)
print("OK: memória da regra atualizada com a exceção CONECTOR 15MM.")
