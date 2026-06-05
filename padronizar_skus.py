"""
padronizar_skus.py — MedBox V3
Usa o Groq (IA gratuita) para padronizar os SKU Masters dos produtos.
Continua de onde parou — não reprocessa produtos já padronizados.
"""

import sqlite3
import json
import time
import re
from pathlib import Path
from groq import Groq

# ============================================================
# CONFIGURAÇÃO
# ============================================================

GROQ_API_KEY = "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"
DB_PATH      = Path("banco/medbox_v3.db")
PROGRESSO    = Path("padronizar_progresso.json")

cliente = Groq(api_key=GROQ_API_KEY)

# ============================================================
# BANCO
# ============================================================

def conectar():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def buscar_produtos_pendentes(conn):
    """Retorna apenas produtos ainda não processados."""
    c = conn.cursor()

    # Carrega IDs já processados
    ids_processados = carregar_progresso()

    c.execute("""
        SELECT id, produto_padrao, fabricante, categoria
        FROM produtos
        WHERE ativo = 1
        ORDER BY produto_padrao
    """)
    todos = [dict(r) for r in c.fetchall()]

    # Filtra os já processados
    pendentes = [p for p in todos if p["id"] not in ids_processados]
    return pendentes


def atualizar_sku_master(conn, produto_id, novo_sku):
    c = conn.cursor()
    c.execute("UPDATE produtos SET produto_padrao = ? WHERE id = ?",
              (novo_sku.upper().strip(), produto_id))
    conn.commit()


def adicionar_equivalencia(conn, produto_id, descricao):
    descricao = descricao.upper().strip()
    if not descricao:
        return
    c = conn.cursor()
    c.execute("""SELECT id FROM equivalencias
        WHERE produto_id = ? AND UPPER(descricao_equivalente) = ?""",
        (produto_id, descricao))
    if not c.fetchone():
        c.execute("INSERT INTO equivalencias (produto_id, descricao_equivalente) VALUES (?,?)",
                  (produto_id, descricao))
        conn.commit()


def mesclar_produtos(conn, manter_id, remover_ids):
    c = conn.cursor()
    for rem_id in remover_ids:
        c.execute("UPDATE precos_fornecedores SET produto_id=? WHERE produto_id=?", (manter_id, rem_id))
        c.execute("UPDATE precos_fornecedores_historico SET produto_id=? WHERE produto_id=?", (manter_id, rem_id))
        c.execute("UPDATE equivalencias SET produto_id=? WHERE produto_id=?", (manter_id, rem_id))
        c.execute("UPDATE produtos SET ativo=0 WHERE id=?", (rem_id,))
    conn.commit()


# ============================================================
# PROGRESSO
# ============================================================

def carregar_progresso():
    if PROGRESSO.exists():
        with open(PROGRESSO, "r") as f:
            return set(json.load(f))
    return set()


def salvar_progresso(ids_processados):
    with open(PROGRESSO, "w") as f:
        json.dump(list(ids_processados), f)


# ============================================================
# IA — GROQ
# ============================================================

PROMPT_SISTEMA = """Você é um especialista em produtos médico-hospitalares e farmacêuticos do Brasil.

Sua tarefa é analisar uma lista de nomes de produtos e:
1. Identificar quais são o MESMO produto com nomes diferentes
2. Definir um SKU MASTER padronizado para cada grupo
3. Retornar o resultado em JSON

REGRAS para o SKU MASTER:
- Nome genérico, sem marca, sem fabricante
- Inclui: princípio ativo/tipo + concentração/tamanho + forma farmacêutica
- Exemplos corretos:
  - "SORO FISIOLOGICO 0,9% 500ML"
  - "AGULHA HIPODERMICA 40X12"
  - "SERINGA 10ML LUER SLIP S/AGULHA"
  - "LUVA NITRILICA S/PO M"
  - "DIPIRONA SODICA 500MG/ML 2ML"
  - "OMEPRAZOL 20MG"

FORMATO DE RESPOSTA (apenas JSON, sem texto adicional):
{
  "grupos": [
    {
      "sku_master": "NOME PADRONIZADO",
      "ids": [1, 2, 3],
      "id_principal": 1
    }
  ]
}

Se um produto não tem similar na lista, crie um grupo com apenas ele mesmo.
"""


def padronizar_lote(produtos_lote):
    lista = "\n".join([
        f"ID {p['id']}: {p['produto_padrao']} | Categoria: {p['categoria'] or 'N/A'}"
        for p in produtos_lote
    ])

    try:
        resposta = cliente.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": PROMPT_SISTEMA},
                {"role": "user", "content": f"Padronize estes produtos:\n\n{lista}"}
            ],
            temperature=0.1,
            max_tokens=4000
        )

        texto = resposta.choices[0].message.content.strip()
        texto = re.sub(r"```json\s*", "", texto)
        texto = re.sub(r"```\s*", "", texto)
        return json.loads(texto.strip())

    except Exception as e:
        erro = str(e)
        if "rate_limit_exceeded" in erro:
            return "LIMITE"
        print(f"  Erro: {erro[:100]}")
        return None


# ============================================================
# PROCESSAMENTO PRINCIPAL
# ============================================================

def processar():
    print("=" * 60)
    print("PADRONIZADOR DE SKU MASTER — MedBox V3")
    print("Usando Groq AI (gratuito) — continua de onde parou")
    print("=" * 60)

    conn = conectar()
    ids_processados = carregar_progresso()
    produtos = buscar_produtos_pendentes(conn)

    print(f"\nJá processados: {len(ids_processados)}")
    print(f"Pendentes     : {len(produtos)}")

    if not produtos:
        print("\n✅ Todos os produtos já foram processados!")
        conn.close()
        return

    print("Processando em lotes de 30 por vez...\n")

    TAMANHO_LOTE  = 30
    total_mesclados = 0

    for i in range(0, len(produtos), TAMANHO_LOTE):
        lote = produtos[i:i + TAMANHO_LOTE]
        num_lote   = (i // TAMANHO_LOTE) + 1
        total_lotes= (len(produtos) + TAMANHO_LOTE - 1) // TAMANHO_LOTE

        print(f"Lote {num_lote}/{total_lotes} ({len(lote)} produtos)...")

        resultado = padronizar_lote(lote)

        if resultado == "LIMITE":
            print("\n⚠️  Limite diário do Groq atingido!")
            print(f"   Progresso salvo. Rode novamente amanhã.")
            print(f"   Produtos processados nesta sessão: {len(ids_processados)}")
            salvar_progresso(ids_processados)
            conn.close()
            return

        if not resultado or "grupos" not in resultado:
            print(f"  Falhou — pulando lote")
            # Marca como processado para não repetir
            for p in lote:
                ids_processados.add(p["id"])
            salvar_progresso(ids_processados)
            continue

        ids_validos = {p["id"] for p in lote}

        for grupo in resultado["grupos"]:
            sku_master   = grupo.get("sku_master", "").strip().upper()
            ids          = grupo.get("ids", [])
            id_principal = grupo.get("id_principal")

            if not sku_master or not ids:
                continue

            ids_grupo = [id for id in ids if id in ids_validos]
            if not ids_grupo:
                continue

            if id_principal not in ids_grupo:
                id_principal = ids_grupo[0]

            ids_remover = [id for id in ids_grupo if id != id_principal]

            # Guarda nome antigo como equivalência
            prod_principal = next((p for p in lote if p["id"] == id_principal), None)
            if prod_principal:
                desc_antiga = prod_principal["produto_padrao"]
                if desc_antiga.upper() != sku_master:
                    adicionar_equivalencia(conn, id_principal, desc_antiga)

            atualizar_sku_master(conn, id_principal, sku_master)

            if ids_remover:
                for rem_id in ids_remover:
                    prod_rem = next((p for p in lote if p["id"] == rem_id), None)
                    if prod_rem:
                        adicionar_equivalencia(conn, id_principal, prod_rem["produto_padrao"])
                mesclar_produtos(conn, id_principal, ids_remover)
                total_mesclados += len(ids_remover)
                print(f"  ✓ '{sku_master}' — {len(ids_grupo)} produto(s)")

            # Marca todos do grupo como processados
            for id in ids_grupo:
                ids_processados.add(id)

        # Salva progresso após cada lote
        salvar_progresso(ids_processados)
        time.sleep(1)

    conn.close()

    print("\n" + "=" * 60)
    print(f"✅ Sessão concluída!")
    print(f"   Total processados : {len(ids_processados)}")
    print(f"   Mesclados         : {total_mesclados}")
    print("=" * 60)
    print("\nReinicie o Flask para ver as mudanças.")


if __name__ == "__main__":
    processar()