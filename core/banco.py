import sqlite3
import re
import unicodedata
from pathlib import Path
from datetime import datetime
from difflib import SequenceMatcher

BASE_DIR = Path(__file__).resolve().parents[1]
PASTA_BANCO = BASE_DIR / "banco"
PASTA_BANCO.mkdir(exist_ok=True)
DB_PATH = PASTA_BANCO / "medbox_v3.db"


# ============================================================
# CONEXÃO
# ============================================================

def conectar():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ============================================================
# NORMALIZAÇÕES
# ============================================================

def normalizar_texto(texto):
    if texto is None:
        return ""
    texto = str(texto).upper().strip()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = re.sub(r"\s+", " ", texto)
    return texto.strip()


def converter_float(valor):
    if valor is None:
        return 0.0
    texto = str(valor).strip().replace("R$", "").replace(" ", "")
    if "," in texto and "." in texto:
        texto = texto.replace(".", "").replace(",", ".")
    else:
        texto = texto.replace(",", ".")
    try:
        return float(texto)
    except Exception:
        return 0.0


def converter_data(data):
    if not data:
        return datetime.now().strftime("%Y-%m-%d")
    texto = str(data).strip()
    formatos = [
        "%Y-%m-%d", "%d/%m/%Y", "%d/%m/%Y %H:%M:%S",
        "%Y-%m-%d %H:%M:%S", "%d-%m-%Y",
    ]
    for fmt in formatos:
        try:
            return datetime.strptime(texto[:19], fmt).strftime("%Y-%m-%d")
        except Exception:
            pass
    try:
        return datetime.fromisoformat(texto[:19]).strftime("%Y-%m-%d")
    except Exception:
        return datetime.now().strftime("%Y-%m-%d")


# ============================================================
# GMAIL COTAÇÕES — VENDAS/OC
# ============================================================

def criar_tabela_gmail_vendas_oc(cursor):
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS gmail_vendas_oc (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chave_dedupe TEXT NOT NULL,
        id_email TEXT NOT NULL,
        thread_id TEXT,
        attachment_id TEXT,
        message_internal_date INTEGER,
        assunto TEXT,
        remetente TEXT,
        data_email TEXT,
        data_venda TEXT,
        numero_oc TEXT,
        vendedora TEXT NOT NULL,
        cliente TEXT,
        status_email TEXT NOT NULL,
        status_revisao TEXT,
        considerar_venda TEXT NOT NULL,
        motivo_exclusao TEXT,
        tem_marcador_pedido TEXT,
        tem_marcador_cancelado TEXT,
        tem_anexo_ordem_compra TEXT,
        nome_arquivo TEXT,
        caminho_anexo TEXT,
        hash_arquivo TEXT,
        tamanho_arquivo INTEGER,
        tipo_anexo TEXT,
        metodo_extracao TEXT,
        avisos_parser TEXT,
        quantidade_itens INTEGER,
        valor_total_oc REAL,
        valor_total_impresso REAL,
        valor_total_calculado REAL,
        divergencia_total REAL,
        erro_processamento TEXT,
        data_processamento TEXT NOT NULL,
        origem_execucao TEXT NOT NULL,
        criado_em TEXT NOT NULL,
        atualizado_em TEXT NOT NULL
    )""")

    cursor.execute("""
    CREATE UNIQUE INDEX IF NOT EXISTS idx_gmail_vendas_oc_chave_dedupe
    ON gmail_vendas_oc (chave_dedupe)
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_gmail_vendas_oc_data_venda ON gmail_vendas_oc (data_venda)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_gmail_vendas_oc_vendedora ON gmail_vendas_oc (vendedora)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_gmail_vendas_oc_cliente ON gmail_vendas_oc (cliente)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_gmail_vendas_oc_status_email ON gmail_vendas_oc (status_email)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_gmail_vendas_oc_considerar_venda ON gmail_vendas_oc (considerar_venda)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_gmail_vendas_oc_numero_oc ON gmail_vendas_oc (numero_oc)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_gmail_vendas_oc_id_email ON gmail_vendas_oc (id_email)")


# ============================================================
# CRIAÇÃO DO BANCO
# ============================================================

def criar_banco():
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS produtos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sku TEXT,
        produto_padrao TEXT,
        fabricante TEXT,
        categoria TEXT,
        ativo INTEGER DEFAULT 1,
        observacoes TEXT
    )""")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS fornecedores (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT,
        tipo TEXT,
        contato TEXT,
        email TEXT,
        telefone TEXT,
        ativo INTEGER DEFAULT 1
    )""")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS precos_fornecedores (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fornecedor_id INTEGER,
        produto_id INTEGER,
        descricao_original TEXT,
        codigo_fornecedor TEXT,
        marca TEXT,
        preco REAL,
        data_importacao TEXT,
        arquivo_origem TEXT
    )""")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS precos_fornecedores_historico (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fornecedor_id INTEGER,
        produto_id INTEGER,
        descricao_original TEXT,
        codigo_fornecedor TEXT,
        marca TEXT,
        preco REAL,
        data_importacao TEXT,
        arquivo_origem TEXT,
        origem_importacao TEXT,
        data_registro TEXT
    )""")

    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_precos_hist_produto_fornecedor
    ON precos_fornecedores_historico (produto_id, fornecedor_id, data_importacao)
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sinonimos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        termo TEXT,
        significado TEXT
    )""")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS equivalencias (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        produto_id INTEGER,
        descricao_equivalente TEXT
    )""")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS cotacoes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fornecedor_id INTEGER,
        data_importacao TEXT,
        arquivo_origem TEXT,
        total_itens INTEGER DEFAULT 0
    )""")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS auditoria_sku (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        produto_id INTEGER,
        campo TEXT,
        valor_antigo TEXT,
        valor_novo TEXT,
        data_hora TEXT,
        tipo_correcao TEXT,
        origem_correcao TEXT,
        usuario TEXT
    )""")

    criar_tabela_gmail_vendas_oc(cursor)

    # Migração: Adiciona colunas se não existirem
    try:
        cursor.execute("ALTER TABLE produtos ADD COLUMN observacoes TEXT")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE produtos ADD COLUMN sku_master TEXT")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE precos_fornecedores ADD COLUMN arquivo_origem TEXT")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE precos_fornecedores_historico ADD COLUMN arquivo_origem TEXT")
    except sqlite3.OperationalError:
        pass

    conn.commit()
    conn.close()
    print("BANCO MEDBOX V3 CRIADO/VERIFICADO COM SUCESSO")


# ============================================================
# DASHBOARD
# ============================================================

def resumo_dashboard():
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM produtos WHERE ativo = 1")
    produtos = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM fornecedores WHERE ativo = 1")
    fornecedores = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM precos_fornecedores")
    precos = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM cotacoes")
    cotacoes = cursor.fetchone()[0]

    try:
        cursor.execute("SELECT COUNT(*) FROM precos_fornecedores_historico")
        historico_precos = cursor.fetchone()[0]
    except Exception:
        historico_precos = 0

    cursor.execute("""
        SELECT p.produto_padrao, pf.preco
        FROM precos_fornecedores pf
        JOIN produtos p ON p.id = pf.produto_id
        WHERE pf.preco > 0
        ORDER BY pf.preco ASC
        LIMIT 1
    """)
    row = cursor.fetchone()
    menor_preco = f"R$ {row['preco']:.2f}".replace(".", ",") if row else "—"

    conn.close()

    return {
        "produtos": produtos,
        "fornecedores": fornecedores,
        "precos": precos,
        "cotacoes": cotacoes,
        "historico_precos": historico_precos,
        "menor_preco": menor_preco,
    }


# ============================================================
# FORNECEDORES
# ============================================================

def listar_fornecedores():
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM fornecedores WHERE ativo = 1 ORDER BY nome")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


def cadastrar_fornecedor(nome, tipo, contato="", email="", telefone=""):
    nome = normalizar_texto(nome)
    if not nome:
        return None
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM fornecedores WHERE UPPER(nome) = ?", (nome,))
    row = cursor.fetchone()
    if row:
        fid = row["id"]
        cursor.execute("""
            UPDATE fornecedores
            SET tipo = COALESCE(NULLIF(?, ''), tipo),
                contato = COALESCE(NULLIF(?, ''), contato),
                email = COALESCE(NULLIF(?, ''), email),
                telefone = COALESCE(NULLIF(?, ''), telefone),
                ativo = 1
            WHERE id = ?
        """, (tipo, contato, email, telefone, fid))
    else:
        cursor.execute("""
            INSERT INTO fornecedores (nome, tipo, contato, email, telefone, ativo)
            VALUES (?, ?, ?, ?, ?, 1)
        """, (nome, tipo or "Distribuidor", contato.strip(),
              email.strip(), telefone.strip()))
        fid = cursor.lastrowid
    conn.commit()
    conn.close()
    return fid


def excluir_fornecedor(fornecedor_id):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("UPDATE fornecedores SET ativo = 0 WHERE id = ?", (fornecedor_id,))
    conn.commit()
    conn.close()


# ============================================================
# PRODUTOS
# ============================================================

def listar_produtos_simples():
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, produto_padrao FROM produtos WHERE ativo = 1 ORDER BY produto_padrao"
    )
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


# ============================================================
# SINÔNIMOS MÉDICOS
# ============================================================

SINONIMOS_MEDICOS = {
    "SORO FISIOLOGICO": ["CLORETO DE SODIO 0,9%", "CLORETO DE SODIO 0.9%",
                         "NACL 0,9%", "NACL 0.9%", "SF 0,9%", "SF 0.9%",
                         "FISIOLOGICO 0,9%", "SOLUCAO FISIOLOGICA"],
    "CLORETO DE SODIO 0,9%": ["SORO FISIOLOGICO", "SF 0,9%", "NACL 0,9%",
                               "FISIOLOGICO 0,9%", "SOLUCAO FISIOLOGICA"],
    "SF 0,9%": ["SORO FISIOLOGICO", "CLORETO DE SODIO 0,9%"],
    "SORO GLICOSADO": ["GLICOSE 5%", "GLICOSE 10%", "SG 5%", "SG 10%",
                       "SOLUCAO GLICOSADA"],
    "GLICOSE 5%": ["SORO GLICOSADO 5%", "SG 5%", "SOLUCAO GLICOSADA 5%"],
    "GLICOSE 10%": ["SORO GLICOSADO 10%", "SG 10%", "SOLUCAO GLICOSADA 10%"],
    "RINGER LACTATO": ["RINGER C/ LACTATO", "RINGER COM LACTATO",
                       "SOLUCAO DE RINGER", "LACTATO DE RINGER"],
    "RINGER": ["RINGER LACTATO", "RINGER C/ LACTATO"],
    "AGUA DESTILADA": ["AGUA P/ INJECAO", "AGUA PARA INJECAO",
                       "AGUA BIDESTILADA", "AD INJ", "AGUA INJ"],
    "AGUA P/ INJECAO": ["AGUA DESTILADA", "AGUA BIDESTILADA", "AD INJ"],
    "AGUA BIDESTILADA": ["AGUA DESTILADA", "AGUA P/ INJECAO"],
    "DIPIRONA": ["METAMIZOL", "NOVALGINA", "DIPIRONA SODICA", "METAMIZOL SODICO"],
    "PARACETAMOL": ["ACETAMINOFENO", "TYLENOL", "PARACETAMOL SODICO"],
    "IBUPROFENO": ["IBUPIRAC", "ADVIL", "MOTRIN"],
    "AMOXICILINA": ["AMOXIL", "AMOXICILINA TRIIDRATADA"],
    "AZITROMICINA": ["ZITHROMAX", "AZITROMICINA DI-HIDRATADA"],
    "CIPROFLOXACINO": ["CIPROFLOXACIN", "CIPRO"],
    "CEFTRIAXONA": ["ROCEFIN", "CEFTRIAXONA SODICA"],
    "AMPICILINA": ["AMPICILINA SODICA", "BINOTAL"],
    "ADRENALINA": ["EPINEFRINA", "ADRENALINA TARTARATO"],
    "EPINEFRINA": ["ADRENALINA"],
    "NORADRENALINA": ["NOREPINEFRINA", "NORADRENALINA BITARTARATO"],
    "DOPAMINA": ["DOPAMINA CLORIDRATO"],
    "ATROPINA": ["ATROPINA SULFATO"],
    "HEPARINA": ["HEPARINA SODICA", "HEPARINA CALCICA"],
    "VARFARINA": ["VARFARIN", "COUMADIN"],
    "DEXAMETASONA": ["DECADRON", "DEXAMETASONA FOSFATO"],
    "HIDROCORTISONA": ["SOLU-CORTEF", "HIDROCORTISONA SUCCINATO"],
    "METILPREDNISOLONA": ["SOLU-MEDROL", "DEPO-MEDROL"],
    "LIDOCAINA": ["XILOCAINA", "LIDOCAINA CLORIDRATO"],
    "BUPIVACAINA": ["MARCAINE", "BUPIVACAINA CLORIDRATO"],
    "KETAMINA": ["KETALAR", "KETAMINA CLORIDRATO"],
    "PROPOFOL": ["DIPRIVAN"],
    "MIDAZOLAM": ["DORMONID"],
    "FENTANIL": ["FENTANIL CITRATO"],
    "SUCCINILCOLINA": ["SUXAMETONIO", "QUELICIN"],
    "VITAMINA C": ["ACIDO ASCORBICO", "ASCORBATO DE SODIO"],
    "VITAMINA B12": ["CIANOCOBALAMINA"],
    "ACIDO FOLICO": ["FOLATO", "VITAMINA B9"],
    "OMEPRAZOL": ["LOSEC", "OMEPRAZOL SODICO"],
    "ONDANSETRONA": ["ZOFRAN", "ONDANSETRONA CLORIDRATO"],
    "FUROSEMIDA": ["LASIX", "FUROSEMIDE"],
    "MANITOL": ["MANITOL 20%"],
    "SERINGA": ["SERINGA DESCARTAVEL", "SERINGA DISP"],
    "AGULHA": ["AGULHA HIPORDERMICA", "AGULHA HIPODERMICA", "AGULHA DESC"],
    "LUVA NITRILICA": ["LUVA DE NITRILO", "LUVA NITRILO"],
    "LUVA LATEX": ["LUVA DE LATEX", "LUVA PROCEDIMENTO"],
    "CATETER": ["CATETER INTRAVENOSO", "CATETER IV", "CATETER PERIFERICO"],
    "SCALP": ["ESCALPE", "BUTTERFLY", "AGULHA BUTTERFLY"],
    "EQUIPO": ["EQUIPO DE SORO", "EQUIPO MACROGOTAS", "EQUIPO MICROGOTAS"],
    "SONDA FOLEY": ["CATETER DE FOLEY", "SONDA VESICAL"],
    "SONDA NASOGASTRICA": ["SONDA GASTRICA", "SONDA DE LEVINE"],
}


def expandir_com_sinonimos(termo):
    termo_upper = normalizar_texto(termo)
    termos_extras = set()

    for chave, sinonimos in SINONIMOS_MEDICOS.items():
        chave_norm = normalizar_texto(chave)
        if chave_norm in termo_upper:
            for sino in sinonimos:
                sino_norm = normalizar_texto(sino)
                novo_termo = termo_upper.replace(chave_norm, sino_norm)
                termos_extras.add(novo_termo)
            continue
        for sino in sinonimos:
            sino_norm = normalizar_texto(sino)
            if sino_norm in termo_upper:
                novo_termo = termo_upper.replace(sino_norm, chave_norm)
                termos_extras.add(novo_termo)
                for outro_sino in sinonimos:
                    if outro_sino != sino:
                        outro_norm = normalizar_texto(outro_sino)
                        novo_termo2 = termo_upper.replace(sino_norm, outro_norm)
                        termos_extras.add(novo_termo2)
                break

    return list(termos_extras)


# ============================================================
# BUSCA INTELIGENTE
# ============================================================

def gerar_variacoes(termo):
    termo = normalizar_texto(termo)
    variacoes = set()
    variacoes.add(termo)

    termo_norm = re.sub(r'\s*[xX]\s*', 'X', termo)
    variacoes.add(termo_norm)

    padrao_medida = re.findall(r'(\d+[\.,]?\d*)\s*X\s*(\d+[\.,]?\d*)', termo_norm)
    for a, b in padrao_medida:
        variacoes.add(f"{a}X{b}")
        variacoes.add(f"{b}X{a}")
        variacoes.add(f"{a} X {b}")
        variacoes.add(f"{b} X {a}")
        a2 = a.replace('.', ',')
        b2 = b.replace('.', ',')
        variacoes.add(f"{a2}X{b2}")
        variacoes.add(f"{b2}X{a2}")

    abreviacoes = {
        'AGULHA': ['AG', 'AG.'], 'AG': ['AGULHA', 'AG.'], 'AG.': ['AGULHA', 'AG'],
        'CENTIMETRO': ['CM'], 'CM': ['CENTIMETRO'],
        'MILIMETRO': ['MM'], 'MM': ['MILIMETRO'],
        'MILILITRO': ['ML'], 'ML': ['MILILITRO'],
        'COMPRIMIDO': ['COMP', 'CP'], 'COMP': ['COMPRIMIDO', 'CP'],
        'AMPOLA': ['AMP', 'AP'], 'AMP': ['AMPOLA', 'AP'], 'AP': ['AMPOLA', 'AMP'],
        'FRASCO': ['FR'], 'FR': ['FRASCO'],
        'SOLUCAO': ['SOL'], 'SOL': ['SOLUCAO'],
        'INJETAVEL': ['INJ'], 'INJ': ['INJETAVEL'],
        'CAIXA': ['CX'], 'CX': ['CAIXA'],
        'UNIDADE': ['UN', 'UNI'], 'UN': ['UNIDADE', 'UNI'],
    }

    palavras = termo.split()
    for i, palavra in enumerate(palavras):
        if palavra in abreviacoes:
            for abrev in abreviacoes[palavra]:
                nova = palavras.copy()
                nova[i] = abrev
                variacoes.add(' '.join(nova))

    return list(variacoes)


def buscar_ids_por_palavra(cursor, palavra):
    ids = set()
    like = f"%{palavra}%"

    cursor.execute("""
        SELECT DISTINCT p.id FROM produtos p
        WHERE UPPER(p.produto_padrao) LIKE ? AND p.ativo = 1
    """, (like,))
    for r in cursor.fetchall():
        ids.add(r["id"])

    cursor.execute("""
        SELECT DISTINCT p.id FROM produtos p
        WHERE UPPER(p.fabricante) LIKE ? AND p.ativo = 1
    """, (like,))
    for r in cursor.fetchall():
        ids.add(r["id"])

    cursor.execute("""
        SELECT DISTINCT p.id FROM produtos p
        JOIN equivalencias e ON e.produto_id = p.id
        WHERE UPPER(e.descricao_equivalente) LIKE ? AND p.ativo = 1
    """, (like,))
    for r in cursor.fetchall():
        ids.add(r["id"])

    cursor.execute("""
        SELECT DISTINCT p.id FROM produtos p
        JOIN precos_fornecedores pf ON pf.produto_id = p.id
        WHERE UPPER(pf.descricao_original) LIKE ? AND p.ativo = 1
    """, (like,))
    for r in cursor.fetchall():
        ids.add(r["id"])

    cursor.execute("""
        SELECT DISTINCT p.id FROM produtos p
        JOIN precos_fornecedores pf ON pf.produto_id = p.id
        WHERE UPPER(pf.marca) LIKE ? AND p.ativo = 1
    """, (like,))
    for r in cursor.fetchall():
        ids.add(r["id"])

    cursor.execute("""
        SELECT DISTINCT p.id FROM produtos p
        JOIN precos_fornecedores pf ON pf.produto_id = p.id
        JOIN fornecedores f ON f.id = pf.fornecedor_id
        WHERE UPPER(f.nome) LIKE ? AND p.ativo = 1
    """, (like,))
    for r in cursor.fetchall():
        ids.add(r["id"])

    return ids


def buscar_ids_por_termo(cursor, termo):
    ids = set()
    ids.update(buscar_ids_por_palavra(cursor, termo))

    palavras = [p for p in termo.split() if len(p) >= 3]
    if len(palavras) >= 2:
        sets = [buscar_ids_por_palavra(cursor, p) for p in palavras]
        ids_intersecao = sets[0]
        for s in sets[1:]:
            ids_intersecao = ids_intersecao.intersection(s)
        ids.update(ids_intersecao)

    return ids


def buscar_produto(termo):
    conn = conectar()
    cursor = conn.cursor()

    variacoes = gerar_variacoes(termo)
    termos_sinonimos = expandir_com_sinonimos(termo)
    for ts in termos_sinonimos:
        variacoes.extend(gerar_variacoes(ts))
    variacoes = list(set(variacoes))

    todos_ids = set()
    for variacao in variacoes:
        ids = buscar_ids_por_termo(cursor, variacao)
        todos_ids.update(ids)

    if not todos_ids:
        conn.close()
        return []

    placeholders = ','.join(['?' for _ in todos_ids])
    cursor.execute(f"""
        SELECT id, sku, produto_padrao, fabricante, categoria
        FROM produtos
        WHERE id IN ({placeholders}) AND ativo = 1
    """, list(todos_ids))
    produtos = [dict(r) for r in cursor.fetchall()]

    resultado = []
    for produto in produtos:
        cursor.execute("""
            SELECT pf.preco, pf.descricao_original,
                   pf.codigo_fornecedor, pf.marca,
                   pf.data_importacao, f.nome AS fornecedor,
                   f.id AS fornecedor_id
            FROM precos_fornecedores pf
            JOIN fornecedores f ON f.id = pf.fornecedor_id
            WHERE pf.produto_id = ?
            AND pf.data_importacao = (
                SELECT MAX(pf2.data_importacao)
                FROM precos_fornecedores pf2
                WHERE pf2.produto_id = pf.produto_id
                AND pf2.fornecedor_id = pf.fornecedor_id
            )
            ORDER BY pf.preco ASC
            LIMIT 10
        """, (produto["id"],))
        precos = [dict(r) for r in cursor.fetchall()]

        for p in precos:
            p["data_cotacao"] = p.get("data_importacao", "")
            p["condicao"] = ""
            p["tendencia"] = "novo"
            p["variacao"] = 0
            p["historico"] = []

        try:
            cursor.execute("""
                SELECT preco, data_importacao
                FROM precos_fornecedores_historico
                WHERE produto_id = ? AND preco > 0
                ORDER BY data_importacao ASC
                LIMIT 12
            """, (produto["id"],))
            historico_precos = [dict(h) for h in cursor.fetchall()]
        except Exception:
            historico_precos = []

        produto["sku_master"]         = produto.get("produto_padrao", "")
        produto["apresentacao"]       = ""
        produto["concentracao"]       = ""
        produto["forma"]              = ""
        produto["unidade_compra"]     = "UN"
        produto["score_busca"]        = 90
        produto["origem_busca"]       = "banco"
        produto["precos"]             = precos
        produto["menor_preco"]        = precos[0]["preco"] if precos else None
        produto["fornecedor_menor"]   = precos[0]["fornecedor"] if precos else "—"
        produto["historico_precos"]   = historico_precos
        produto["tem_historico_real"] = len(historico_precos) >= 2

        if produto.get("fabricante") in (None, "", "NONE"):
            produto["fabricante"] = precos[0]["marca"] if precos else ""

        if precos:
            resultado.append(produto)

    resultado.sort(key=lambda x: x["menor_preco"] or 9999)
    conn.close()
    return resultado[:10]


def listar_sugestoes_busca(termo, limite=8):
    if not termo or len(termo) < 2:
        return []

    conn = conectar()
    cursor = conn.cursor()
    termo_norm = normalizar_texto(termo)
    like = f"%{termo_norm}%"

    palavras = [p for p in termo_norm.split() if len(p) >= 3]
    sugestoes = set()

    if len(palavras) >= 2:
        sets = []
        for palavra in palavras:
            cursor.execute("""
                SELECT DISTINCT produto_padrao FROM produtos
                WHERE UPPER(produto_padrao) LIKE ? AND ativo = 1
            """, (f"%{palavra}%",))
            sets.append({r[0] for r in cursor.fetchall()})

        if sets:
            resultado = sets[0]
            for s in sets[1:]:
                resultado = resultado.intersection(s)
            sugestoes.update(resultado)
    else:
        cursor.execute("""
            SELECT DISTINCT produto_padrao FROM produtos
            WHERE UPPER(produto_padrao) LIKE ? AND ativo = 1
            ORDER BY produto_padrao
            LIMIT ?
        """, (like, limite))
        for r in cursor.fetchall():
            sugestoes.add(r[0])

        cursor.execute("""
            SELECT DISTINCT p.produto_padrao
            FROM produtos p
            JOIN precos_fornecedores pf ON pf.produto_id = p.id
            WHERE UPPER(pf.descricao_original) LIKE ? AND p.ativo = 1
            LIMIT ?
        """, (like, limite))
        for r in cursor.fetchall():
            sugestoes.add(r[0])

        cursor.execute("""
            SELECT DISTINCT p.produto_padrao
            FROM produtos p
            JOIN equivalencias e ON e.produto_id = p.id
            WHERE UPPER(e.descricao_equivalente) LIKE ? AND p.ativo = 1
            LIMIT ?
        """, (like, limite))
        for r in cursor.fetchall():
            sugestoes.add(r[0])

    conn.close()
    return sorted(list(sugestoes))[:limite]


# ============================================================
# EQUIVALÊNCIAS
# ============================================================

def listar_equivalencias(produto_id=None):
    conn = conectar()
    cursor = conn.cursor()
    if produto_id:
        cursor.execute("""
            SELECT e.*, p.produto_padrao FROM equivalencias e
            JOIN produtos p ON p.id = e.produto_id WHERE e.produto_id = ?
        """, (produto_id,))
    else:
        cursor.execute("""
            SELECT e.*, p.produto_padrao FROM equivalencias e
            JOIN produtos p ON p.id = e.produto_id ORDER BY p.produto_padrao
        """)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


def adicionar_equivalencia(produto_id, descricao):
    descricao = normalizar_texto(descricao)
    if not descricao:
        return
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id FROM equivalencias
        WHERE produto_id = ? AND UPPER(descricao_equivalente) = ?
    """, (produto_id, descricao))
    if not cursor.fetchone():
        cursor.execute("""
            INSERT INTO equivalencias (produto_id, descricao_equivalente)
            VALUES (?, ?)
        """, (produto_id, descricao))
    conn.commit()
    conn.close()


def excluir_equivalencia(equivalencia_id):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM equivalencias WHERE id = ?", (equivalencia_id,))
    conn.commit()
    conn.close()


# ============================================================
# COTAÇÕES
# ============================================================

def registrar_cotacao(fornecedor_id, arquivo_origem, total_itens, data_importacao=None):
    data = converter_data(data_importacao or datetime.now().strftime("%Y-%m-%d"))
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO cotacoes (fornecedor_id, data_importacao, arquivo_origem, total_itens)
        VALUES (?, ?, ?, ?)
    """, (fornecedor_id, data, arquivo_origem, total_itens))
    conn.commit()
    conn.close()


def listar_cotacoes():
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT c.*, f.nome AS fornecedor_nome FROM cotacoes c
        LEFT JOIN fornecedores f ON f.id = c.fornecedor_id
        ORDER BY c.data_importacao DESC, c.id DESC
    """)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


# ============================================================
# REGISTRO DE PREÇOS
# ============================================================

def registrar_preco_fornecedor(
    fornecedor_id, produto_id, descricao_original,
    codigo_fornecedor="", marca="", preco=0,
    data_importacao=None, arquivo_origem="", origem_importacao="IMPORTACAO",
    conn_existente=None
):
    preco = converter_float(preco)
    if preco <= 0:
        return

    data_importacao    = converter_data(data_importacao)
    descricao_original = normalizar_texto(descricao_original)
    codigo_fornecedor  = str(codigo_fornecedor or "").strip()
    marca              = normalizar_texto(marca)
    arquivo_origem     = str(arquivo_origem or "").strip()
    origem_importacao  = normalizar_texto(origem_importacao or "IMPORTACAO")

    conn = conn_existente or conectar()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, preco, data_importacao, marca, codigo_fornecedor, arquivo_origem, descricao_original
        FROM precos_fornecedores
        WHERE fornecedor_id = ? AND produto_id = ? AND data_importacao = ?
    """, (fornecedor_id, produto_id, data_importacao))

    existente = cursor.fetchone()

    if existente:
        # Só arquiva no histórico e atualiza se houver mudança real
        mudou = (
            preco != existente["preco"] or
            marca != existente["marca"] or
            codigo_fornecedor != existente["codigo_fornecedor"] or
            descricao_original != existente["descricao_original"]
        )

        if mudou:
            try:
                cursor.execute("""
                    INSERT INTO precos_fornecedores_historico (
                        fornecedor_id, produto_id, descricao_original,
                        codigo_fornecedor, marca, preco, data_importacao,
                        arquivo_origem, origem_importacao, data_registro
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    fornecedor_id, produto_id, existente["descricao_original"],
                    existente["codigo_fornecedor"], existente["marca"],
                    existente["preco"], existente["data_importacao"],
                    existente["arquivo_origem"], "SOBREPOSTO",
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                ))
            except Exception:
                pass

            cursor.execute("""
                UPDATE precos_fornecedores
                SET preco = ?, marca = ?, codigo_fornecedor = ?,
                    descricao_original = ?, arquivo_origem = ?
                WHERE id = ?
            """, (preco, marca, codigo_fornecedor, descricao_original,
                  arquivo_origem, existente["id"]))
    else:
        cursor.execute("""
            SELECT id, data_importacao FROM precos_fornecedores
            WHERE fornecedor_id = ? AND produto_id = ?
        """, (fornecedor_id, produto_id))

        geral = cursor.fetchone()

        if geral:
            if data_importacao >= geral["data_importacao"]:
                cursor.execute("""
                    SELECT preco, data_importacao, marca, codigo_fornecedor, arquivo_origem, descricao_original
                    FROM precos_fornecedores WHERE id = ?
                """, (geral["id"],))
                velho = cursor.fetchone()

                mudou = (
                    preco != velho["preco"] or
                    marca != velho["marca"] or
                    codigo_fornecedor != velho["codigo_fornecedor"] or
                    descricao_original != velho["descricao_original"]
                )

                if mudou:
                    try:
                        cursor.execute("""
                            INSERT INTO precos_fornecedores_historico (
                                fornecedor_id, produto_id, descricao_original,
                                codigo_fornecedor, marca, preco, data_importacao,
                                arquivo_origem, origem_importacao, data_registro
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            fornecedor_id, produto_id, velho["descricao_original"],
                            velho["codigo_fornecedor"], velho["marca"],
                            velho["preco"], velho["data_importacao"],
                            velho["arquivo_origem"], "SOBREPOSTO_NOVA_DATA",
                            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        ))
                    except Exception:
                        pass

                    cursor.execute("""
                        UPDATE precos_fornecedores
                        SET preco = ?, data_importacao = ?,
                            marca = ?, codigo_fornecedor = ?,
                            descricao_original = ?, arquivo_origem = ?
                        WHERE id = ?
                    """, (preco, data_importacao, marca,
                          codigo_fornecedor, descricao_original,
                          arquivo_origem, geral["id"]))
            else:
                # Preço importado é mais antigo que o atual — vai direto para histórico
                try:
                    cursor.execute("""
                        INSERT INTO precos_fornecedores_historico (
                            fornecedor_id, produto_id, descricao_original,
                            codigo_fornecedor, marca, preco, data_importacao,
                            arquivo_origem, origem_importacao, data_registro
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        fornecedor_id, produto_id, descricao_original,
                        codigo_fornecedor, marca, preco, data_importacao,
                        arquivo_origem, "IMPORTACAO_ANTIGA",
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    ))
                except Exception:
                    pass
        else:
            cursor.execute("""
                INSERT INTO precos_fornecedores (
                    fornecedor_id, produto_id, descricao_original,
                    codigo_fornecedor, marca, preco, data_importacao,
                    arquivo_origem
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                fornecedor_id, produto_id, descricao_original,
                codigo_fornecedor, marca, preco, data_importacao,
                arquivo_origem
            ))

    if not conn_existente:
        conn.commit()
        conn.close()


# ============================================================
# EXECUÇÃO DIRETA
# ============================================================

if __name__ == "__main__":
    criar_banco()