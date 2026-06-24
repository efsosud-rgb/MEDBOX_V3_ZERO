import sqlite3
from pathlib import Path
from datetime import datetime
import shutil

DB = Path("banco/medbox_v3.db")
BACKUP_DIR = Path("banco/backups")
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

backup = BACKUP_DIR / f"medbox_v3_backup_regra_tubo_endotraqueal_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
shutil.copy2(DB, backup)

conn = sqlite3.connect(DB)
cur = conn.cursor()

# Evita duplicar a mesma regra
cur.execute("""
SELECT id
FROM sku_master_regras
WHERE nome_regra = ?
LIMIT 1
""", ("REGRA_TUBO_ENDOTRAQUEAL_C_BALAO_PVC_MEDIDA_VARIAVEL",))

existe = cur.fetchone()

if existe:
    print("Regra já existia. ID:", existe[0])
else:
    cur.execute("""
    INSERT INTO sku_master_regras (
        nome_regra,
        familia,
        sku_master_padrao,
        categoria,
        fabricante,
        termos_equivalentes,
        termos_obrigatorios,
        especificacoes_obrigatorias,
        termos_proibidos,
        exemplos_positivos,
        exemplos_negativos,
        fonte_validacao,
        observacoes,
        usuario_validou,
        ativo
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "REGRA_TUBO_ENDOTRAQUEAL_C_BALAO_PVC_MEDIDA_VARIAVEL",
        "TUBO ENDOTRAQUEAL",
        "TUBO ENDOTRAQUEAL C/BALAO PVC {MEDIDA}",
        "CORRELATOS",
        "",
        """
OROTRAQUEAL=ENDOTRAQUEAL
TUBO OROTRAQUEAL=TUBO ENDOTRAQUEAL
CANULA ENDOTRAQUEAL=TUBO ENDOTRAQUEAL
POLIVINIL=PVC
POLI VINIL=PVC
CLORETO DE POLIVINILA=PVC
COM BALAO=C/BALAO
COM BALONETE=C/BALAO
BALONETE=C/BALAO
COM CUFF=C/BALAO
CUFF=C/BALAO
""".strip(),
        """
TUBO
ENDOTRAQUEAL|OROTRAQUEAL
C/BALAO|COM BALAO|BALONETE|CUFF
PVC|POLIVINIL|POLI VINIL|CLORETO DE POLIVINILA
MEDIDA
""".strip(),
        """
MEDIDA_MM
""".strip(),
        """
SEM BALAO
SEM BALONETE
SEM CUFF
S/BALAO
LATEX
SILICONE
""".strip(),
        """
TUBO OROTRAQUEAL COM BALAO POLIVINIL 8,5MM => TUBO ENDOTRAQUEAL C/BALAO PVC 8,5MM
TUBO ENDOTRAQUEAL COM BALONETE N° 7,5 => TUBO ENDOTRAQUEAL C/BALAO PVC 7,5MM
TUBO ENDOTRAQUEAL C/ BALAO TAM 9,0 => TUBO ENDOTRAQUEAL C/BALAO PVC 9,0MM
""".strip(),
        """
TUBO ENDOTRAQUEAL SEM BALONETE N° 3,0
TUBO ENDOTRAQUEAL S/ BALONETE N° 7,0
TUBO OROTRAQUEAL SEM BALAO POLIVINIL 4,0MM
TUBO ENDOTRAQUEAL COM BALONETE SILICONE 7,5MM
""".strip(),
        "VALIDADO PELO USUARIO NO FLUXO DE AUDITORIA SKU_MASTER",
        "Regra auditável para padronizar tubos endotraqueais/orotraqueais com balão/cuff/balonete em PVC/polivinil, mantendo a medida como especificação crítica variável. Não aplica em SEM BALAO, SEM CUFF, LATEX ou SILICONE.",
        "ERIC",
        1
    ))

    print("Regra cadastrada. ID:", cur.lastrowid)

conn.commit()
conn.close()

print("Backup criado:", backup)
print("OK: primeira regra validada cadastrada.")
