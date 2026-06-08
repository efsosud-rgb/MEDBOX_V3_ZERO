"""
core/analisar_correspondencias.py
Fase 2 — Análise de correspondências entre produtos existentes e BASE_PRODUTOS.

Abre o banco em modo SOMENTE LEITURA. Não grava nada.

Uso:
    python core/analisar_correspondencias.py
    python core/analisar_correspondencias.py --banco banco/medbox_v3_teste.db
    python core/analisar_correspondencias.py --jaccard 0.75   # altera limiar de similaridade

Saída:
    relatorios/correspondencias_fase2.csv
"""

import csv
import re
import sqlite3
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

# ── Configuração ─────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parents[1]
DB_PADRAO = BASE_DIR / "banco" / "medbox_v3_teste.db"
PASTA_RELATORIOS = BASE_DIR / "relatorios"
CSV_SAIDA = PASTA_RELATORIOS / "correspondencias_fase2.csv"
LIMIAR_JACCARD = 0.8
# ─────────────────────────────────────────────────────────────────────────────


def normalizar_chave(texto: str) -> str:
    """
    Normalização melhorada:
    1. Troca separadores \\ / - por espaço (mantém os tokens separados).
    2. Converte para maiúsculas.
    3. Remove acentos (NFD → filtra Mn).
    4. Remove pontuação restante (mantém letras, dígitos e espaços).
    5. Colapsa espaços múltiplos.
    """
    texto = str(texto).strip()
    # Passo 1: separadores → espaço
    texto = re.sub(r"[\\\/\-]", " ", texto)
    # Passo 2: maiúsculas
    texto = texto.upper()
    # Passo 3: remove acentos
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    # Passo 4: remove pontuação restante
    texto = re.sub(r"[^A-Z0-9\s]", "", texto)
    # Passo 5: colapsa espaços
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


def _tokens(chave: str) -> frozenset:
    return frozenset(chave.split())


def jaccard(set_a: frozenset, set_b: frozenset) -> float:
    if not set_a and not set_b:
        return 1.0
    uniao = set_a | set_b
    if not uniao:
        return 0.0
    return len(set_a & set_b) / len(uniao)


def _parse_args():
    args = sys.argv[1:]
    db_path = DB_PADRAO
    limiar = LIMIAR_JACCARD

    i = 0
    while i < len(args):
        if args[i] == "--banco" and i + 1 < len(args):
            db_path = Path(args[i + 1])
            i += 2
        elif args[i] == "--jaccard" and i + 1 < len(args):
            try:
                limiar = float(args[i + 1])
            except ValueError:
                print(f"AVISO: valor inválido para --jaccard: {args[i + 1]}. Usando {LIMIAR_JACCARD}.")
            i += 2
        else:
            i += 1

    return db_path, limiar


def carregar_produtos(conn: sqlite3.Connection):
    """Retorna (existentes, base_produtos) como listas de dicts."""
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, produto_padrao
        FROM produtos
        WHERE origem != 'BASE_PRODUTOS'
          AND produto_padrao IS NOT NULL
          AND TRIM(produto_padrao) != ''
    """)
    existentes = [{"id": row[0], "produto": row[1]} for row in cursor.fetchall()]

    cursor.execute("""
        SELECT id, produto_padrao
        FROM produtos
        WHERE origem = 'BASE_PRODUTOS'
          AND produto_padrao IS NOT NULL
          AND TRIM(produto_padrao) != ''
    """)
    base = [{"id": row[0], "produto": row[1]} for row in cursor.fetchall()]

    return existentes, base


def construir_indice_invertido(existentes_norm):
    """
    indice: token → set de índices em existentes_norm
    Permite encontrar candidatos com pelo menos 1 token em comum.
    """
    indice = defaultdict(set)
    for idx, item in enumerate(existentes_norm):
        for token in item["tokens"]:
            indice[token].add(idx)
    return indice


def classificar(base_norm, existentes_norm, indice, limiar):
    """
    Para cada produto da base retorna um dict com o melhor match.
    Estratégia:
      - EXATO: chave idêntica à de algum existente (O(1) via dict)
      - SIMILAR: Jaccard ≥ limiar, calculado apenas sobre candidatos com ≥1 token em comum
      - NOVO: sem correspondência
    """
    # Índice de chave exata: chave → primeiro item existente com essa chave
    chave_para_existente = {}
    for item in existentes_norm:
        chave_para_existente.setdefault(item["chave"], item)

    resultados = []

    for item_b in base_norm:
        chave_b = item_b["chave"]
        tokens_b = item_b["tokens"]

        # Tenta match EXATO
        if chave_b in chave_para_existente:
            match = chave_para_existente[chave_b]
            resultados.append({
                "id_base": item_b["id"],
                "produto_base": item_b["produto"],
                "id_existente": match["id"],
                "produto_existente": match["produto"],
                "chave_normalizada": chave_b,
                "tipo_match": "EXATO",
                "score_similaridade": 1.0,
            })
            continue

        # Candidatos via índice invertido
        candidatos_idx = set()
        for token in tokens_b:
            candidatos_idx.update(indice.get(token, set()))

        melhor_score = 0.0
        melhor = None

        for idx in candidatos_idx:
            item_e = existentes_norm[idx]
            score = jaccard(tokens_b, item_e["tokens"])
            if score > melhor_score:
                melhor_score = score
                melhor = item_e

        if melhor and melhor_score >= limiar:
            resultados.append({
                "id_base": item_b["id"],
                "produto_base": item_b["produto"],
                "id_existente": melhor["id"],
                "produto_existente": melhor["produto"],
                "chave_normalizada": chave_b,
                "tipo_match": "SIMILAR",
                "score_similaridade": round(melhor_score, 4),
            })
        else:
            resultados.append({
                "id_base": item_b["id"],
                "produto_base": item_b["produto"],
                "id_existente": None,
                "produto_existente": None,
                "chave_normalizada": chave_b,
                "tipo_match": "NOVO",
                "score_similaridade": round(melhor_score, 4) if melhor else 0.0,
            })

    return resultados


def exportar_csv(resultados, caminho: Path) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    colunas = [
        "id_base", "produto_base", "id_existente", "produto_existente",
        "chave_normalizada", "tipo_match", "score_similaridade",
    ]
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=colunas)
        writer.writeheader()
        writer.writerows(resultados)


def imprimir_relatorio(existentes, base, resultados, limiar, db_path):
    total_existentes = len(existentes)
    total_base = len(base)
    exatos = [r for r in resultados if r["tipo_match"] == "EXATO"]
    similares = [r for r in resultados if r["tipo_match"] == "SIMILAR"]
    novos = [r for r in resultados if r["tipo_match"] == "NOVO"]

    # Faixas de score para SIMILAR
    faixas = {
        "0.80–0.89": [r for r in similares if 0.80 <= r["score_similaridade"] < 0.90],
        "0.90–0.99": [r for r in similares if 0.90 <= r["score_similaridade"] < 1.00],
        "1.00":      [r for r in similares if r["score_similaridade"] == 1.00],
    }

    sep = "=" * 58
    print(f"\n{sep}")
    print("  RELATÓRIO — FASE 2: ANÁLISE DE CORRESPONDÊNCIAS")
    print(sep)
    print(f"  Banco analisado : {db_path}")
    print(f"  Limiar Jaccard  : {limiar}")
    print(sep)
    print(f"  Produtos existentes (não BASE_PRODUTOS) : {total_existentes:>6}")
    print(f"  Produtos da base (BASE_PRODUTOS)        : {total_base:>6}")
    print(sep)
    print(f"  Matches EXATO                           : {len(exatos):>6}")
    print(f"  Matches SIMILAR (Jaccard ≥ {limiar})     : {len(similares):>6}")
    for faixa, items in faixas.items():
        if items:
            print(f"    • score {faixa:<12}                : {len(items):>6}")
    print(f"  NOVOS (sem correspondência)             : {len(novos):>6}")
    print(sep)
    print(f"  CSV gerado em: {CSV_SAIDA.relative_to(BASE_DIR)}")
    print(f"{sep}\n")


def main() -> None:
    db_path, limiar = _parse_args()

    if not db_path.exists():
        print(f"ERRO: banco não encontrado: {db_path}")
        sys.exit(1)

    # Abre em modo somente leitura via URI
    uri = f"file:{db_path.resolve()}?mode=ro"
    try:
        conn = sqlite3.connect(uri, uri=True)
    except sqlite3.OperationalError as exc:
        print(f"ERRO ao abrir o banco: {exc}")
        sys.exit(1)

    print(f"Carregando produtos de {db_path.name}...")
    existentes, base = carregar_produtos(conn)
    conn.close()

    if not existentes:
        print("AVISO: nenhum produto existente encontrado (origem != 'BASE_PRODUTOS').")
    if not base:
        print("AVISO: nenhum produto da base encontrado (origem = 'BASE_PRODUTOS').")
        sys.exit(0)

    print(f"  {len(existentes)} existentes | {len(base)} da base")
    print("Normalizando chaves...")

    existentes_norm = [
        {
            "id": p["id"],
            "produto": p["produto"],
            "chave": normalizar_chave(p["produto"]),
            "tokens": _tokens(normalizar_chave(p["produto"])),
        }
        for p in existentes
    ]

    base_norm = [
        {
            "id": p["id"],
            "produto": p["produto"],
            "chave": normalizar_chave(p["produto"]),
            "tokens": _tokens(normalizar_chave(p["produto"])),
        }
        for p in base
    ]

    print("Construindo índice invertido...")
    indice = construir_indice_invertido(existentes_norm)

    print("Classificando correspondências...")
    resultados = classificar(base_norm, existentes_norm, indice, limiar)

    exportar_csv(resultados, CSV_SAIDA)
    imprimir_relatorio(existentes, base, resultados, limiar, db_path)


if __name__ == "__main__":
    main()
