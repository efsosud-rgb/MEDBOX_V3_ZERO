
import re
import sqlite3
from pathlib import Path
from functools import lru_cache


def caminho_banco_padrao():
    return Path(__file__).resolve().parent.parent / "banco" / "medbox_v3.db"


def remover_acentos(txt):
    txt = str(txt or "")
    mapa = {
        "Á": "A", "À": "A", "Ã": "A", "Â": "A", "Ä": "A",
        "É": "E", "Ê": "E", "È": "E", "Ë": "E",
        "Í": "I", "Ì": "I", "Î": "I", "Ï": "I",
        "Ó": "O", "Ô": "O", "Õ": "O", "Ò": "O", "Ö": "O",
        "Ú": "U", "Ù": "U", "Û": "U", "Ü": "U",
        "Ç": "C",
        "á": "a", "à": "a", "ã": "a", "â": "a", "ä": "a",
        "é": "e", "ê": "e", "è": "e", "ë": "e",
        "í": "i", "ì": "i", "î": "i", "ï": "i",
        "ó": "o", "ô": "o", "õ": "o", "ò": "o", "ö": "o",
        "ú": "u", "ù": "u", "û": "u", "ü": "u",
        "ç": "c",
    }
    for a, b in mapa.items():
        txt = txt.replace(a, b)
    return txt


def normalizar_termo(txt):
    txt = remover_acentos(txt).upper()
    txt = txt.replace("\\", "/")
    txt = re.sub(r"\s+", " ", txt).strip()
    return txt


@lru_cache(maxsize=8)
def carregar_sinonimos_ativos(db_path=None):
    db = Path(db_path) if db_path else caminho_banco_padrao()

    if not db.exists():
        return []

    try:
        conn = sqlite3.connect(db)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        existe = cur.execute("""
            SELECT name
            FROM sqlite_master
            WHERE type='table'
              AND name='dicionario_sinonimos'
        """).fetchone()

        if not existe:
            conn.close()
            return []

        rows = cur.execute("""
            SELECT termo_origem, termo_destino, familia, tipo_equivalencia, usar_no_sku_master
            FROM dicionario_sinonimos
            WHERE ativo = 1
            ORDER BY LENGTH(termo_origem) DESC
        """).fetchall()

        conn.close()

        saida = []
        for r in rows:
            origem = normalizar_termo(r["termo_origem"])
            destino = normalizar_termo(r["termo_destino"])
            familia = normalizar_termo(r["familia"])
            tipo = str(r["tipo_equivalencia"] or "").upper()
            usar = int(r["usar_no_sku_master"] or 0)

            if origem and destino:
                saida.append({
                    "origem": origem,
                    "destino": destino,
                    "familia": familia,
                    "tipo": tipo,
                    "usar_no_sku_master": usar,
                })

        return saida

    except Exception:
        return []


def aplicar_sinonimos_dicionario(txt, familia=None, db_path=None):
    texto = normalizar_termo(txt)
    familia_norm = normalizar_termo(familia) if familia else ""

    sinonimos = carregar_sinonimos_ativos(str(db_path) if db_path else None)

    for s in sinonimos:
        origem = s["origem"]
        destino = s["destino"]
        fam = s["familia"]

        # Se a regra tem família específica e foi informada família, respeita.
        if familia_norm and fam and fam != familia_norm:
            continue

        # Substituição com borda para evitar trocar pedaços dentro de palavras.
        padrao = r"(?<![A-Z0-9])" + re.escape(origem) + r"(?![A-Z0-9])"
        texto = re.sub(padrao, destino, texto)

    texto = re.sub(r"\s+", " ", texto).strip()
    return texto
