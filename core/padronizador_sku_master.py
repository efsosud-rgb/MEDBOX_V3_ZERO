"""
core/padronizador_sku_master.py
Robot de padronizacao SKU Master e populacao da base de produtos.

SEGURO:
- Nunca apaga dados nem dropa tabelas.
- Desativacao de fantasmas usa ativo=0 (reversivel).
- Cria backup automatico antes de qualquer escrita.
- Modo --dry-run simula sem alterar nada.

Fases:
  1. Indices de performance (via adicionar_indices.py)
  2. Atribuicao de codigos SKU (UPDATE onde sku IS NULL ou '')
  3. Desativacao de produtos fantasmas (dups sem preco e sem fabricante)
  4. Processamento do SKU_MASTER_2_0.xlsx:
     a. Extrai mapeamento descricao -> SKU_MASTER das linhas preenchidas
     b. Para cada linha: encontra ou cria produto, registra preco, adiciona equivalencia
  5. Limpeza de nomes contaminados (repeticao / excesso de tokens)

Uso:
    python core/padronizador_sku_master.py --dry-run   # simula, nao altera nada
    python core/padronizador_sku_master.py             # executa de verdade
"""

import re
import shutil
import sqlite3
import sys
import unicodedata
from collections import defaultdict
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
DB_PATH = BASE_DIR / "banco" / "medbox_v3.db"
PASTA_BACKUPS = BASE_DIR / "banco" / "backups"
SKU_MASTER_XLSX = BASE_DIR / "uploads" / "SKU_MASTER_2_0.xlsx"

NOVA_LINEA_ID = 1  # id do fornecedor NOVA LINEA no banco

MAPA_CATEGORIA = {
    "medicamento": "MEDICAMENTO",
    "correlato": "CORRELATO",
    "material hospitalar": "MATERIAL HOSPITALAR",
    "sutura": "SUTURA",
    "otc": "OTC",
    "oftalmo": "OFTALMO",
    "pediatria": "PEDIATRIA",
    "genericos": "GENERICOO",
    "genericos": "GENERICOO",
}

DRY_RUN = "--dry-run" in sys.argv


# ============================================================
# UTILITARIOS
# ============================================================

def _norm(texto):
    texto = str(texto or "").strip().upper()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(ch for ch in texto if not unicodedata.combining(ch))
    texto = re.sub(r"[^A-Z0-9%+/,.-]+", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()


def _limpar_contaminacao(produto_padrao):
    """Remove texto de fornecedor/marca appended ao nome padrao."""
    texto = _norm(produto_padrao)

    # Remove prefixo 'SKU PENDENTE - '
    texto = re.sub(r"^SKU PENDENTE\s*-?\s*", "", texto)
    # Remove numero de item no inicio (ex: '15693 SORO GLICOSADO ...')
    texto = re.sub(r"^\d{3,}\s+", "", texto)
    # Remove tudo apos AP/FR/AMP seguido de fabricante
    texto = re.sub(r"\b(AP|AMP|FR|FA)\s+[A-Z][A-Z0-9]+(\s.*)?$", "", texto)
    # Remove tudo apos CX, CAIXA
    texto = re.sub(r"\b(CX|CAIXA)\b.*$", "", texto)
    # Remove tudo apos LOTE, VALIDADE
    texto = re.sub(r"\b(LOTE|LT|VAL|VALIDADE)\b.*$", "", texto)
    texto = re.sub(r"\s+", " ", texto).strip(" -,.")

    # Detecta e remove repeticao de prefixo (contaminacao por duplicacao)
    palavras = texto.split()
    for tamanho in range(2, min(6, len(palavras) // 2 + 1)):
        inicio = " ".join(palavras[:tamanho])
        restante = " ".join(palavras[tamanho:])
        if inicio and inicio in restante:
            texto = inicio
            break

    return texto[:80].strip()


def _esta_contaminado(produto_padrao):
    texto = _norm(produto_padrao)
    palavras = texto.split()

    if len(texto) > 55:
        return True
    if len(palavras) > 8:
        return True

    if len(palavras) >= 4:
        for tamanho in range(2, min(5, len(palavras) // 2 + 1)):
            inicio = " ".join(palavras[:tamanho])
            restante = " ".join(palavras[tamanho:])
            if inicio and inicio in restante:
                return True

    return False


def _normalizar_valor(texto):
    if texto is None:
        return 0.0
    s = str(texto).strip().replace("R$", "").replace(" ", "")
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(",", ".")
    try:
        return float(s)
    except (ValueError, TypeError):
        return 0.0


def _normalizar_data(texto):
    if not texto:
        return datetime.now().strftime("%Y-%m-%d")
    s = str(texto).strip()
    for fmt in ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(s[:len(fmt)], fmt).strftime("%Y-%m-%d")
        except (ValueError, IndexError):
            continue
    return datetime.now().strftime("%Y-%m-%d")


def _normalizar_categoria(texto):
    if not texto:
        return ""
    t = str(texto).strip().lower()
    return MAPA_CATEGORIA.get(t, str(texto).strip().upper())


def _log(msg, nivel="INFO"):
    prefixo = "[DRY-RUN] " if DRY_RUN else ""
    print(f"{prefixo}[{nivel}] {msg}")


# ============================================================
# CONEXAO
# ============================================================

def _conectar():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


# ============================================================
# FASE 1 — INDICES
# ============================================================

def fase1_indices(conn):
    _log("=== FASE 1: Indices de performance ===")
    indices = [
        ("idx_produtos_ativo_padrao",
         "CREATE INDEX IF NOT EXISTS idx_produtos_ativo_padrao ON produtos(ativo, produto_padrao)"),
        ("idx_produtos_ativo_fabricante",
         "CREATE INDEX IF NOT EXISTS idx_produtos_ativo_fabricante ON produtos(ativo, fabricante)"),
        ("idx_produtos_ativo_sku",
         "CREATE INDEX IF NOT EXISTS idx_produtos_ativo_sku ON produtos(ativo, sku)"),
        ("idx_precos_produto_fornecedor_data",
         "CREATE INDEX IF NOT EXISTS idx_precos_produto_fornecedor_data "
         "ON precos_fornecedores(produto_id, fornecedor_id, data_importacao)"),
        ("idx_precos_produto",
         "CREATE INDEX IF NOT EXISTS idx_precos_produto ON precos_fornecedores(produto_id)"),
        ("idx_precos_fornecedor",
         "CREATE INDEX IF NOT EXISTS idx_precos_fornecedor ON precos_fornecedores(fornecedor_id)"),
        ("idx_equivalencias_produto",
         "CREATE INDEX IF NOT EXISTS idx_equivalencias_produto ON equivalencias(produto_id)"),
    ]
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='index'")
    existentes = {row[0] for row in cur.fetchall()}
    criados = 0
    for nome, sql in indices:
        if DRY_RUN:
            status = "ja existe" if nome in existentes else "seria criado"
            _log(f"  {status}: {nome}")
        else:
            cur.execute(sql)
            if nome not in existentes:
                criados += 1
    if not DRY_RUN:
        conn.commit()
    _log(f"  {criados} indices criados (total planejados: {len(indices)})")


# ============================================================
# FASE 2 — CODIGOS SKU
# ============================================================

def fase2_sku_codes(conn):
    _log("=== FASE 2: Atribuicao de codigos SKU ===")
    cur = conn.cursor()
    cur.execute("SELECT id FROM produtos WHERE sku IS NULL OR sku = '' ORDER BY id")
    sem_sku = [row[0] for row in cur.fetchall()]
    _log(f"  Produtos sem codigo SKU: {len(sem_sku)}")

    if not sem_sku:
        _log("  Nenhum produto sem SKU — fase ignorada.")
        return 0

    if DRY_RUN:
        exemplo = [f"MB{i:05d}" for i in sem_sku[:3]]
        _log(f"  Exemplos de codigos a atribuir: {exemplo} ...")
        return len(sem_sku)

    atualizados = 0
    for produto_id in sem_sku:
        codigo = f"MB{produto_id:05d}"
        cur.execute("UPDATE produtos SET sku = ? WHERE id = ? AND (sku IS NULL OR sku = '')",
                    (codigo, produto_id))
        if cur.rowcount:
            atualizados += 1
    conn.commit()
    _log(f"  {atualizados} produtos receberam codigo SKU (formato MB{sem_sku[0]:05d}..MB{sem_sku[-1]:05d})")
    return atualizados


# ============================================================
# FASE 3 — FANTASMAS
# ============================================================

def fase3_desativar_fantasmas(conn):
    _log("=== FASE 3: Desativacao de produtos fantasmas ===")
    cur = conn.cursor()

    # Encontra grupos de produto_padrao duplicados
    cur.execute("""
        SELECT UPPER(TRIM(produto_padrao)) AS chave, COUNT(*) AS total
        FROM produtos
        WHERE ativo = 1
        GROUP BY UPPER(TRIM(produto_padrao))
        HAVING COUNT(*) > 1
    """)
    grupos_dup = {row["chave"]: row["total"] for row in cur.fetchall()}
    _log(f"  Grupos de produto_padrao duplicados: {len(grupos_dup)}")

    fantasmas = []
    for chave in grupos_dup:
        cur.execute("""
            SELECT p.id, p.produto_padrao, p.fabricante, p.ativo,
                   COUNT(pf.id) AS n_precos
            FROM produtos p
            LEFT JOIN precos_fornecedores pf ON pf.produto_id = p.id
            WHERE UPPER(TRIM(p.produto_padrao)) = ? AND p.ativo = 1
            GROUP BY p.id
            ORDER BY COUNT(pf.id) DESC, p.id ASC
        """, (chave,))
        membros = [dict(row) for row in cur.fetchall()]
        # O primeiro tem mais precos — e o "real". Os restantes sem preco e sem fab sao fantasmas.
        for membro in membros[1:]:
            if membro["n_precos"] == 0 and not (membro["fabricante"] or "").strip():
                fantasmas.append(membro["id"])

    _log(f"  Fantasmas identificados (sem preco, sem fabricante, nome duplicado): {len(fantasmas)}")

    if not fantasmas:
        return 0

    if DRY_RUN:
        _log(f"  [dry-run] Seriam desativados: ids={fantasmas[:10]}{'...' if len(fantasmas) > 10 else ''}")
        return len(fantasmas)

    ph = ",".join("?" for _ in fantasmas)
    cur.execute(f"UPDATE produtos SET ativo = 0 WHERE id IN ({ph})", fantasmas)
    conn.commit()
    _log(f"  {cur.rowcount} fantasmas desativados (ativo=0)")
    return cur.rowcount


# ============================================================
# FASE 4 — PROCESSA SKU_MASTER_2_0.xlsx
# ============================================================

def _construir_mapa_sku(df):
    """Constroi dict normalizado(descricao) -> sku_master a partir das linhas preenchidas."""
    mapa = {}
    col_desc = "Descrição do Produto"
    col_sku = "SKU_MASTER"

    if col_desc not in df.columns or col_sku not in df.columns:
        return mapa

    for _, row in df.iterrows():
        sku = str(row.get(col_sku) or "").strip()
        desc = str(row.get(col_desc) or "").strip()
        if sku and sku.lower() != "nan" and desc and desc.lower() != "nan":
            chave = _norm(desc)
            if chave:
                mapa[chave] = _norm(sku)
    return mapa


def _buscar_sku_para_descricao(descricao, mapa_sku):
    """Busca no mapa. Primeiro exato, depois por prefixo do descricao."""
    chave = _norm(descricao)
    if chave in mapa_sku:
        return mapa_sku[chave], "exato"

    # Tenta com apenas os primeiros 50 chars normalizados
    chave_curta = chave[:50]
    for k, v in mapa_sku.items():
        if k.startswith(chave_curta) or chave_curta.startswith(k[:50]):
            return v, "prefixo"

    return None, None


def _buscar_produto_por_padrao(cur, produto_padrao):
    chave = _norm(produto_padrao)
    cur.execute(
        "SELECT id, produto_padrao, ativo FROM produtos WHERE UPPER(TRIM(produto_padrao)) = ?",
        (chave,)
    )
    row = cur.fetchone()
    return dict(row) if row else None


def _criar_produto(cur, produto_padrao, categoria="", fabricante=""):
    produto_padrao = _norm(produto_padrao)
    if not produto_padrao:
        return None
    cur.execute(
        "INSERT INTO produtos (produto_padrao, categoria, fabricante, ativo) VALUES (?, ?, ?, 1)",
        (produto_padrao, categoria, fabricante)
    )
    novo_id = cur.lastrowid
    codigo = f"MB{novo_id:05d}"
    cur.execute("UPDATE produtos SET sku = ? WHERE id = ?", (codigo, novo_id))
    return novo_id


def _registrar_equivalencia(cur, produto_id, descricao):
    desc_norm = _norm(descricao)
    if not desc_norm:
        return False
    cur.execute(
        "SELECT id FROM equivalencias WHERE produto_id = ? AND UPPER(descricao_equivalente) = ?",
        (produto_id, desc_norm)
    )
    if cur.fetchone():
        return False
    cur.execute(
        "INSERT INTO equivalencias (produto_id, descricao_equivalente) VALUES (?, ?)",
        (produto_id, desc_norm)
    )
    return True


def _registrar_preco(cur, fornecedor_id, produto_id, descricao, marca, preco, data):
    desc_norm = _norm(descricao)
    marca_norm = _norm(marca)
    if preco <= 0:
        return False

    cur.execute(
        "SELECT id, data_importacao FROM precos_fornecedores "
        "WHERE fornecedor_id = ? AND produto_id = ? AND UPPER(descricao_original) = ?",
        (fornecedor_id, produto_id, desc_norm)
    )
    existente = cur.fetchone()
    if existente:
        if data >= existente["data_importacao"]:
            cur.execute(
                "UPDATE precos_fornecedores SET preco=?, data_importacao=?, marca=? WHERE id=?",
                (preco, data, marca_norm, existente["id"])
            )
        return False  # ja existia
    else:
        cur.execute(
            "INSERT INTO precos_fornecedores "
            "(fornecedor_id, produto_id, descricao_original, marca, preco, data_importacao) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (fornecedor_id, produto_id, desc_norm, marca_norm, preco, data)
        )
        return True  # novo


def fase4_processar_xlsx(conn):
    _log("=== FASE 4: Processamento do SKU_MASTER_2_0.xlsx ===")

    if not SKU_MASTER_XLSX.exists():
        _log(f"  AVISO: arquivo nao encontrado: {SKU_MASTER_XLSX}", "WARN")
        return

    try:
        import pandas as pd
    except ImportError:
        _log("  ERRO: pandas nao disponivel.", "ERROR")
        return

    df = pd.read_excel(SKU_MASTER_XLSX, dtype=str)
    df = df.fillna("")
    _log(f"  Arquivo lido: {len(df)} linhas x {len(df.columns)} colunas")

    # Renomeia colunas com encoding problema
    rename = {}
    for col in df.columns:
        col_norm = _norm(col)
        if "DESCRI" in col_norm and "PRODUTO" in col_norm:
            rename[col] = "Descrição do Produto"
        elif col_norm in ("RAZAO SOCIAL DO FORNECEDOR", "FORNECEDOR"):
            rename[col] = "FORNECEDOR"
        elif "SKU" in col_norm and "MASTER" in col_norm:
            rename[col] = "SKU_MASTER"
        elif "VALOR" in col_norm and "UNIT" in col_norm:
            rename[col] = "Valor Unitário"
        elif "DATA" in col_norm and "LAN" in col_norm:
            rename[col] = "Data lançamento"
        elif col_norm in ("MARCA", "MARCA FABRICANTE"):
            rename[col] = "MARCA"
        elif col_norm == "CATEGORIA":
            rename[col] = "CATEGORIA"
    df = df.rename(columns=rename)

    mapa_sku = _construir_mapa_sku(df)
    _log(f"  Mapeamentos descricao->SKU_MASTER extraidos das linhas preenchidas: {len(mapa_sku)}")

    cur = conn.cursor()

    contadores = {
        "linhas": 0,
        "sem_desc": 0,
        "sku_do_mapa": 0,
        "sku_oficial": 0,
        "sku_limpeza": 0,
        "produtos_encontrados": 0,
        "produtos_criados": 0,
        "precos_novos": 0,
        "equivalencias_novas": 0,
        "precos_atualizados": 0,
        "sem_preco": 0,
    }

    sys.path.insert(0, str(BASE_DIR))
    from core.auditoria_sku_master import sugerir_sku_medbox_oficial

    for _, row in df.iterrows():
        contadores["linhas"] += 1

        desc_raw = str(row.get("Descrição do Produto") or "").strip()
        if not desc_raw or desc_raw.lower() == "nan":
            contadores["sem_desc"] += 1
            continue

        marca = str(row.get("MARCA") or "").strip()
        categoria = _normalizar_categoria(str(row.get("CATEGORIA") or "").strip())
        preco = _normalizar_valor(row.get("Valor Unitário"))
        data = _normalizar_data(row.get("Data lançamento"))

        if preco <= 0:
            contadores["sem_preco"] += 1
            continue

        # 1. Tenta resolver o SKU_MASTER desta linha
        # Nivel de confianca: "alto" cria produto se nao existe; "baixo" apenas adiciona preco se ja existe
        sku_master_linha = _norm(str(row.get("SKU_MASTER") or ""))
        confianca_resolucao = "baixo"

        if sku_master_linha and sku_master_linha != "NAN":
            target_padrao = sku_master_linha
            confianca_resolucao = "alto"
            contadores["sku_do_mapa"] += 1
        else:
            # 2. Busca no mapa (das linhas preenchidas)
            target_padrao, _ = _buscar_sku_para_descricao(desc_raw, mapa_sku)

            if target_padrao:
                confianca_resolucao = "alto"
                contadores["sku_do_mapa"] += 1
            else:
                # 3. sugerir_sku_medbox_oficial (soros, glicose, ondansetrona, etc.)
                sugerido, conf_oficial = sugerir_sku_medbox_oficial(desc_raw)
                if sugerido and conf_oficial >= 88:
                    target_padrao = _norm(sugerido)
                    confianca_resolucao = "alto"
                    contadores["sku_oficial"] += 1
                else:
                    # 4. Limpeza por regex — confianca baixa: apenas adiciona preco se produto ja existe
                    target_padrao = _limpar_contaminacao(desc_raw)
                    confianca_resolucao = "baixo"
                    contadores["sku_limpeza"] += 1

        if not target_padrao:
            continue

        # 2. Encontra ou cria o produto no banco
        # Produtos so sao criados quando a confianca da resolucao e alta
        if DRY_RUN:
            produto = _buscar_produto_por_padrao(cur, target_padrao)
            if produto:
                contadores["produtos_encontrados"] += 1
                contadores["precos_novos"] += 1
                contadores["equivalencias_novas"] += 1
            elif confianca_resolucao == "alto":
                contadores["produtos_criados"] += 1
                contadores["precos_novos"] += 1
            # baixa confianca + nao encontrado: apenas conta como descartado
            continue

        produto = _buscar_produto_por_padrao(cur, target_padrao)
        if produto:
            produto_id = produto["id"]
            contadores["produtos_encontrados"] += 1
            if not produto.get("ativo"):
                cur.execute("UPDATE produtos SET ativo=1 WHERE id=?", (produto_id,))
        elif confianca_resolucao == "alto":
            produto_id = _criar_produto(cur, target_padrao, categoria,
                                        _norm(marca) if marca else "")
            if not produto_id:
                continue
            contadores["produtos_criados"] += 1
        else:
            # Baixa confianca e produto nao existe — nao cria registro especulativo
            continue

        # 3. Registra preco
        novo_preco = _registrar_preco(cur, NOVA_LINEA_ID, produto_id,
                                      desc_raw, marca, preco, data)
        if novo_preco:
            contadores["precos_novos"] += 1
        else:
            contadores["precos_atualizados"] += 1

        # 4. Registra equivalencia (descricao original como sinonimo)
        desc_norm = _norm(desc_raw)
        padrao_norm = _norm(target_padrao)
        if desc_norm != padrao_norm:
            if _registrar_equivalencia(cur, produto_id, desc_raw):
                contadores["equivalencias_novas"] += 1

    if not DRY_RUN:
        conn.commit()

    _log(f"  Linhas processadas:      {contadores['linhas']}")
    _log(f"  Sem descricao/preco:     {contadores['sem_desc'] + contadores['sem_preco']}")
    _log(f"  SKU do mapa xlsx:        {contadores['sku_do_mapa']}")
    _log(f"  SKU por dicionario medbox:{contadores['sku_oficial']}")
    _log(f"  SKU por limpeza regex:   {contadores['sku_limpeza']}")
    _log(f"  Produtos encontrados:    {contadores['produtos_encontrados']}")
    _log(f"  Produtos criados:        {contadores['produtos_criados']}")
    _log(f"  Precos novos:            {contadores['precos_novos']}")
    _log(f"  Precos atualizados:      {contadores['precos_atualizados']}")
    _log(f"  Equivalencias novas:     {contadores['equivalencias_novas']}")
    return contadores


# ============================================================
# FASE 5 — LIMPEZA DE NOMES CONTAMINADOS
# ============================================================

def fase5_limpar_contaminados(conn):
    _log("=== FASE 5: Limpeza de nomes contaminados ===")
    cur = conn.cursor()

    # Busca produtos com produto_padrao contaminado e sem conflito de nome
    cur.execute("""
        SELECT p.id, p.produto_padrao, p.fabricante,
               COUNT(pf.id) AS n_precos
        FROM produtos p
        LEFT JOIN precos_fornecedores pf ON pf.produto_id = p.id
        WHERE p.ativo = 1
        GROUP BY p.id
        HAVING n_precos > 0
        ORDER BY p.produto_padrao
    """)
    produtos_com_preco = [dict(r) for r in cur.fetchall()]

    # Conjunto de nomes limpos existentes (para detectar colisoes)
    cur.execute("SELECT UPPER(TRIM(produto_padrao)) FROM produtos WHERE ativo=1")
    nomes_existentes = {row[0] for row in cur.fetchall()}

    corrigidos = 0
    sem_mudanca = 0
    colisoes = 0

    for p in produtos_com_preco:
        pp = p["produto_padrao"]
        if not _esta_contaminado(pp):
            sem_mudanca += 1
            continue

        limpo = _limpar_contaminacao(pp)
        # So aplica se o resultado for realmente mais curto E abaixo do limiar de contaminacao
        if not limpo or limpo == _norm(pp) or len(limpo) >= len(_norm(pp)) or len(limpo) > 70:
            sem_mudanca += 1
            continue

        # Verifica colisao: se o nome limpo ja pertence a OUTRO produto
        if limpo in nomes_existentes and limpo != _norm(pp):
            colisoes += 1
            _log(f"  COLISAO ignorada: '{pp}' -> '{limpo}' (nome ja existe)", "WARN")
            continue

        if DRY_RUN:
            _log(f"  SERIA ATUALIZADO: id={p['id']} '{pp[:50]}' -> '{limpo}'")
            corrigidos += 1
            continue

        cur.execute(
            "UPDATE produtos SET produto_padrao = ? WHERE id = ? AND produto_padrao = ?",
            (limpo, p["id"], pp)
        )
        if cur.rowcount:
            nomes_existentes.discard(_norm(pp))
            nomes_existentes.add(limpo)
            corrigidos += 1

    if not DRY_RUN and corrigidos:
        conn.commit()

    _log(f"  Contaminados corrigidos:    {corrigidos}")
    _log(f"  Sem mudanca necessaria:     {sem_mudanca}")
    _log(f"  Colisoes ignoradas:         {colisoes}")
    return corrigidos


# ============================================================
# MAIN
# ============================================================

def _criar_backup():
    PASTA_BACKUPS.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    destino = PASTA_BACKUPS / f"medbox_v3_backup_padronizador_{ts}.db"
    shutil.copy2(DB_PATH, destino)
    return destino


def main():
    if not DB_PATH.exists():
        print(f"ERRO: banco nao encontrado: {DB_PATH}")
        sys.exit(1)

    print("=" * 60)
    print("PADRONIZADOR SKU MASTER — MEDBOX V3 ZERO")
    print(f"Modo: {'DRY-RUN (simulacao)' if DRY_RUN else 'EXECUCAO REAL'}")
    print(f"Banco: {DB_PATH}")
    print("=" * 60)

    if not DRY_RUN:
        backup = _criar_backup()
        print(f"Backup criado: {backup}\n")

    conn = _conectar()

    try:
        fase1_indices(conn)
        print()
        fase2_sku_codes(conn)
        print()
        fase3_desativar_fantasmas(conn)
        print()
        fase4_processar_xlsx(conn)
        print()
        fase5_limpar_contaminados(conn)
    finally:
        conn.close()

    print()
    print("=" * 60)
    print("CONCLUIDO.")
    if DRY_RUN:
        print("Execute sem --dry-run para aplicar as alteracoes.")
    print("=" * 60)


if __name__ == "__main__":
    main()
