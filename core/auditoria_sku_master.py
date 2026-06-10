import csv
import io
import re
import sqlite3
import unicodedata
from collections import defaultdict
from pathlib import Path

from rapidfuzz import fuzz


BASE_DIR = Path(__file__).resolve().parent.parent
CAMINHO_BANCO = BASE_DIR / "banco" / "medbox_v3.db"

CLASSIFICACOES = {
    "LIMPO",
    "SUSPEITO",
    "CONTAMINADO_FORTE",
    "SKU_PENDENTE",
    "DUPLICADO",
}

FILTROS = {
    "todos": "",
    "limpo": "LIMPO",
    "suspeito": "SUSPEITO",
    "contaminado_forte": "CONTAMINADO_FORTE",
    "sku_pendente": "SKU_PENDENTE",
    "duplicado": "DUPLICADO",
}

MARCAS_FINAIS_SUSPEITAS = {
    "EQUIPLEX",
    "FARMACE",
    "HALEXISTAR",
    "SAMTEC",
    "HIPOLABOR",
    "CRISTALIA",
    "TEUTO",
    "MEDIX",
    "THEOTO",
    "SOL",
    "CARE",
}


def _conectar_leitura():
    caminho = CAMINHO_BANCO.as_posix()
    return sqlite3.connect(f"file:{caminho}?mode=ro", uri=True)


def _normalizar(texto):
    texto = str(texto or "").strip().upper()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(ch for ch in texto if not unicodedata.combining(ch))
    texto = re.sub(r"[^A-Z0-9%+/,.-]+", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()


def _tokens(texto):
    return _normalizar(texto).split()


def _assinatura_sku(texto):
    texto = _normalizar(texto)
    texto = re.sub(r"\bSKU PENDENTE\b\s*-?\s*", "", texto)
    texto = re.sub(r"\b(AP|FR|CX|C/|COM|UN|UND|PC|L|LT|VAL|VALIDADE|LOTE)\b.*$", "", texto)
    texto = re.sub(r"\b\d{4,}\b", "", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    palavras = texto.split()
    return " ".join(palavras[:8])


def _motivos_sku(produto_padrao, descricoes_originais):
    texto = _normalizar(produto_padrao)
    palavras = texto.split()
    motivos = []

    if texto.startswith("SKU PENDENTE"):
        motivos.append("sku_pendente")

    if len(palavras) > 8:
        motivos.append("excesso_tokens")

    if len(texto) > 55:
        motivos.append("muito_longo")

    if len(palavras) >= 4:
        metade = max(2, len(palavras) // 2)
        inicio = " ".join(palavras[:metade])
        restante = " ".join(palavras[metade:])
        if inicio and inicio in restante:
            motivos.append("repeticao_termo_base")
        prefixo_curto = " ".join(palavras[:2])
        prefixo_medio = " ".join(palavras[:3])
        restante_curto = " ".join(palavras[2:])
        if prefixo_curto and prefixo_curto in restante_curto:
            motivos.append("repeticao_termo_base")
        if prefixo_medio and prefixo_medio in restante:
            motivos.append("repeticao_termo_base")

    if re.search(r"\bAP\s+[A-Z0-9]+$", texto):
        marca_final = palavras[-1] if palavras else ""
        if marca_final in MARCAS_FINAIS_SUSPEITAS or len(marca_final) >= 4:
            motivos.append("marca_fabricante_no_fim")

    for descricao in descricoes_originais:
        if _normalizar(descricao) == texto:
            motivos.append("igual_descricao_original")
            break

    return sorted(set(motivos))


def _classificar(produto, motivos, duplicado):
    if duplicado:
        return "DUPLICADO"
    if "sku_pendente" in motivos:
        return "SKU_PENDENTE"
    motivos_fortes = {
        "excesso_tokens",
        "muito_longo",
        "repeticao_termo_base",
        "marca_fabricante_no_fim",
    }
    if motivos_fortes.intersection(motivos):
        return "CONTAMINADO_FORTE"
    if motivos:
        return "SUSPEITO"
    return "LIMPO"


def _sugerir_sku_limpo(produto, indice_limpos):
    assinatura = _assinatura_sku(produto.get("produto_padrao"))
    if not assinatura:
        return ""

    chave = assinatura.split()[0] if assinatura.split() else ""
    produtos_limpos = indice_limpos.get(chave, [])
    if not produtos_limpos:
        return ""

    candidatos = []
    for limpo in produtos_limpos:
        if limpo["id"] == produto["id"]:
            continue
        score = fuzz.token_set_ratio(assinatura, limpo["assinatura"])
        if score >= 92:
            candidatos.append((score, len(_tokens(limpo["produto_padrao"])), limpo["produto_padrao"]))

    if not candidatos:
        return ""

    candidatos.sort(key=lambda item: (-item[0], item[1], item[2]))
    return candidatos[0][2]


def gerar_auditoria_sku_master(filtro="todos", limite=200):
    filtro = filtro if filtro in FILTROS else "todos"
    limite = max(1, int(limite or 200))

    conn = _conectar_leitura()
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, sku, produto_padrao, fabricante, categoria, ativo
            FROM produtos
            ORDER BY produto_padrao
            """
        )
        produtos = [dict(row) for row in cursor.fetchall()]

        cursor.execute(
            """
            SELECT produto_id, descricao_original
            FROM precos_fornecedores
            """
        )
        descricoes_por_produto = defaultdict(list)
        total_precos = defaultdict(int)
        for row in cursor.fetchall():
            produto_id = row["produto_id"]
            total_precos[produto_id] += 1
            if row["descricao_original"]:
                descricoes_por_produto[produto_id].append(row["descricao_original"])

        cursor.execute(
            """
            SELECT produto_id, COUNT(*) AS total
            FROM equivalencias
            GROUP BY produto_id
            """
        )
        total_equivalencias = {
            row["produto_id"]: row["total"]
            for row in cursor.fetchall()
        }
    finally:
        conn.close()

    grupos_normalizados = defaultdict(list)
    for produto in produtos:
        chave = _normalizar(produto.get("produto_padrao"))
        if chave:
            grupos_normalizados[chave].append(produto["id"])

    ids_duplicados = {
        produto_id
        for ids in grupos_normalizados.values()
        if len(ids) > 1
        for produto_id in ids
    }
    total_grupos_duplicados = sum(1 for ids in grupos_normalizados.values() if len(ids) > 1)

    pre_classificados = []
    for produto in produtos:
        motivos = _motivos_sku(
            produto.get("produto_padrao"),
            descricoes_por_produto.get(produto["id"], []),
        )
        duplicado = produto["id"] in ids_duplicados
        classificacao = _classificar(produto, motivos, duplicado)
        pre_classificados.append({
            **produto,
            "classificacao": classificacao,
            "motivo": ", ".join(motivos) if motivos else "-",
            "motivos_lista": motivos,
            "total_precos": total_precos.get(produto["id"], 0),
            "total_equivalencias": total_equivalencias.get(produto["id"], 0),
            "sugestao_sku_limpo": "",
        })

    produtos_limpos = [
        {
            **item,
            "assinatura": _assinatura_sku(item["produto_padrao"]),
        }
        for item in pre_classificados
        if item["classificacao"] == "LIMPO"
    ]
    indice_limpos = defaultdict(list)
    for item in produtos_limpos:
        chave = item["assinatura"].split()[0] if item["assinatura"].split() else ""
        if chave:
            indice_limpos[chave].append(item)

    itens = pre_classificados

    contadores = {classificacao: 0 for classificacao in CLASSIFICACOES}
    for item in itens:
        contadores[item["classificacao"]] += 1

    classificacao_filtro = FILTROS[filtro]
    itens_filtrados = [
        item for item in itens
        if not classificacao_filtro or item["classificacao"] == classificacao_filtro
    ]
    itens_limitados = itens_filtrados[:limite]
    for item in itens_limitados:
        if item["classificacao"] != "LIMPO":
            item["sugestao_sku_limpo"] = _sugerir_sku_limpo(item, indice_limpos)

    return {
        "filtro": filtro,
        "contadores": {
            "total_produtos": len(produtos),
            "total_limpos": contadores["LIMPO"],
            "total_suspeitos": contadores["SUSPEITO"],
            "total_contaminados_fortes": contadores["CONTAMINADO_FORTE"],
            "total_sku_pendente": contadores["SKU_PENDENTE"],
            "total_duplicados": contadores["DUPLICADO"],
            "total_grupos_duplicados": total_grupos_duplicados,
            "total_filtrado": len(itens_filtrados),
        },
        "itens": itens_limitados,
        "total_sem_limite": len(itens_filtrados),
    }


def gerar_csv_auditoria_sku_master(filtro="todos"):
    auditoria = gerar_auditoria_sku_master(filtro=filtro, limite=1000000)
    buffer = io.StringIO()
    campos = [
        "produto_id",
        "produto_padrao",
        "fabricante",
        "categoria",
        "classificacao",
        "motivo",
        "sugestao_sku_limpo",
        "total_precos",
        "total_equivalencias",
    ]
    writer = csv.DictWriter(buffer, fieldnames=campos, extrasaction="ignore")
    writer.writeheader()
    for item in auditoria["itens"]:
        writer.writerow({
            "produto_id": item["id"],
            "produto_padrao": item["produto_padrao"],
            "fabricante": item["fabricante"],
            "categoria": item["categoria"],
            "classificacao": item["classificacao"],
            "motivo": item["motivo"],
            "sugestao_sku_limpo": item["sugestao_sku_limpo"],
            "total_precos": item["total_precos"],
            "total_equivalencias": item["total_equivalencias"],
        })
    return buffer.getvalue()
