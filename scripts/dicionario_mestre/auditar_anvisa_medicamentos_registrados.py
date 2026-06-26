"""
Auditoria do intermediario ANVISA Medicamentos Registrados
FASE 2.3 — Somente leitura do intermediario. Sem banco, sem fonte interna, sem dicionario final.
"""

import csv
import json
import random
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Caminhos
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent.parent
DIR_PROC = ROOT / "data/dicionario_mestre/processado"

INTERMEDIARIO = DIR_PROC / "anvisa_medicamentos_registrados_normalizado.csv"
AMOSTRA       = DIR_PROC / "amostra_anvisa_medicamentos_registrados.csv"
AUDITORIA     = DIR_PROC / "auditoria_anvisa_medicamentos_registrados.md"
DUPLICIDADES  = DIR_PROC / "duplicidades_anvisa_medicamentos_registrados.csv"
PENDENCIAS    = DIR_PROC / "pendencias_anvisa_medicamentos_registrados.csv"

DATA = datetime.now().strftime("%Y-%m-%d")
RANDOM_SEED = 42

CAMPOS_CRITICOS = [
    "nome_produto", "principio_ativo", "empresa_detentora",
    "numero_registro", "situacao_registro",
    "forma_farmaceutica", "concentracao", "apresentacao",
]

COLS_AMOSTRA = [
    "grupo_amostra", "id_registro_processamento", "nome_produto",
    "principio_ativo", "empresa_detentora", "numero_registro",
    "situacao_registro", "forma_farmaceutica", "concentracao",
    "apresentacao", "status_processamento", "motivo_amostra",
]

COLS_DUP = [
    "tipo_duplicidade", "chave_duplicidade", "total_ocorrencias",
    "exemplos_ids", "exemplos_nome_produto", "exemplos_numero_registro",
    "severidade", "observacao",
]

COLS_PEND = [
    "id_registro_processamento", "tipo_pendencia", "campo",
    "valor_encontrado", "severidade", "bloqueia_pre_carga", "observacao",
]


# ---------------------------------------------------------------------------
# Utilitarios
# ---------------------------------------------------------------------------

def norm(v: str) -> str:
    return (v or "").strip().upper()


def vazio(v: str) -> bool:
    return not (v or "").strip()


def pct(n, total) -> str:
    return f"{100 * n / total:.1f}%" if total else "0%"


def amostra_row(grupo: str, r: dict, motivo: str) -> dict:
    return {
        "grupo_amostra": grupo,
        "id_registro_processamento": r.get("id_registro_processamento", ""),
        "nome_produto": r.get("nome_produto", ""),
        "principio_ativo": r.get("principio_ativo", ""),
        "empresa_detentora": r.get("empresa_detentora", ""),
        "numero_registro": r.get("numero_registro", ""),
        "situacao_registro": r.get("situacao_registro", ""),
        "forma_farmaceutica": r.get("forma_farmaceutica", ""),
        "concentracao": r.get("concentracao", ""),
        "apresentacao": r.get("apresentacao", ""),
        "status_processamento": r.get("status_processamento", ""),
        "motivo_amostra": motivo,
    }


def contar_vazios_por_linha(r: dict, campos: list) -> int:
    return sum(1 for c in campos if vazio(r.get(c, "")))


def escrever_csv(path: Path, cols: list, rows: list):
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, delimiter=";",
                           quotechar='"', quoting=csv.QUOTE_MINIMAL)
        w.writeheader()
        w.writerows(rows)


# ---------------------------------------------------------------------------
# Processamento principal
# ---------------------------------------------------------------------------

def auditar():
    print(f"[FASE 2.3] Lendo intermediario: {INTERMEDIARIO}")
    assert INTERMEDIARIO.exists(), "ERRO: intermediario nao encontrado"

    registros = []
    with open(INTERMEDIARIO, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, delimiter=";", quotechar='"')
        colunas = list(reader.fieldnames or [])
        for row in reader:
            registros.append(dict(row))

    total = len(registros)
    print(f"  Total de registros: {total}")
    print(f"  Total de colunas:   {len(colunas)}")

    # -----------------------------------------------------------------------
    # Contagens basicas
    # -----------------------------------------------------------------------
    cnt_status    = Counter(r.get("status_processamento", "") for r in registros)
    cnt_situacao  = Counter(r.get("situacao_registro", "")   for r in registros)
    cnt_tipo      = Counter(r.get("tipo_produto", "")        for r in registros)
    cnt_categoria = Counter(r.get("categoria_regulatoria", "") for r in registros)
    cnt_empresa   = Counter(r.get("empresa_detentora", "")   for r in registros)

    # -----------------------------------------------------------------------
    # Preenchimento por campo
    # -----------------------------------------------------------------------
    preenchimento = {}
    for col in colunas:
        preenchidos = sum(1 for r in registros if not vazio(r.get(col, "")))
        preenchimento[col] = preenchidos

    campos_100_vazios = [c for c, v in preenchimento.items() if v == 0]
    campos_criticos_pct = {c: preenchimento.get(c, 0) for c in CAMPOS_CRITICOS}

    # -----------------------------------------------------------------------
    # Registros com campos criticos vazios
    # -----------------------------------------------------------------------
    sem_nome      = [r for r in registros if vazio(r.get("nome_produto", ""))]
    sem_pa        = [r for r in registros if vazio(r.get("principio_ativo", ""))]
    sem_numreg    = [r for r in registros if vazio(r.get("numero_registro", ""))]
    sem_empresa   = [r for r in registros if vazio(r.get("empresa_detentora", ""))]
    sem_forma     = [r for r in registros if vazio(r.get("forma_farmaceutica", ""))]
    sem_conc      = [r for r in registros if vazio(r.get("concentracao", ""))]
    sem_apres     = [r for r in registros if vazio(r.get("apresentacao", ""))]
    sem_via       = [r for r in registros if vazio(r.get("via_uso", ""))]

    # -----------------------------------------------------------------------
    # Duplicidades
    # -----------------------------------------------------------------------
    dup_rows = []

    def analisar_duplicidade(tipo, chave_fn, sevfn, obs_fn, registros):
        grupos = defaultdict(list)
        for r in registros:
            chave = chave_fn(r)
            if chave:
                grupos[chave].append(r)
        duplicados = {k: v for k, v in grupos.items() if len(v) > 1}
        if not duplicados:
            return []
        result = []
        for chave, grupo in sorted(duplicados.items(), key=lambda x: -len(x[1]))[:500]:
            ids   = " | ".join(r.get("id_registro_processamento", "") for r in grupo[:5])
            nomes = " | ".join(r.get("nome_produto", "")              for r in grupo[:5])
            nums  = " | ".join(r.get("numero_registro", "")           for r in grupo[:5])
            result.append({
                "tipo_duplicidade": tipo,
                "chave_duplicidade": chave[:200],
                "total_ocorrencias": len(grupo),
                "exemplos_ids": ids[:300],
                "exemplos_nome_produto": nomes[:300],
                "exemplos_numero_registro": nums[:300],
                "severidade": sevfn(chave, grupo),
                "observacao": obs_fn(chave, grupo),
            })
        return result

    # Dup 1: numero_registro
    def sev_numreg(chave, grupo):
        nomes = set(r.get("nome_produto", "").strip() for r in grupo)
        return "ALTA" if len(nomes) > 1 else "MEDIA"

    dup_rows += analisar_duplicidade(
        "NUMERO_REGISTRO",
        lambda r: norm(r.get("numero_registro", "")),
        sev_numreg,
        lambda k, g: f"{len(g)} registros com mesmo numero_registro",
        registros,
    )

    # Dup 2: nome + pa + empresa
    dup_rows += analisar_duplicidade(
        "NOME_PA_EMPRESA",
        lambda r: "||".join([
            norm(r.get("nome_produto", "")),
            norm(r.get("principio_ativo", "")),
            norm(r.get("empresa_detentora", "")),
        ]),
        lambda k, g: "MEDIA",
        lambda k, g: f"{len(g)} registros com mesma combinacao nome+pa+empresa",
        registros,
    )

    # Dup 3: pa + concentracao + forma + apresentacao
    dup_rows += analisar_duplicidade(
        "PA_CONC_FORMA_APRES",
        lambda r: "||".join([
            norm(r.get("principio_ativo", "")),
            norm(r.get("concentracao", "")),
            norm(r.get("forma_farmaceutica", "")),
            norm(r.get("apresentacao", "")),
        ]),
        lambda k, g: "BAIXA",
        lambda k, g: f"{len(g)} registros com mesma combinacao pa+conc+forma+apres",
        registros,
    )

    # Dup 4: nome normalizado
    dup_rows += analisar_duplicidade(
        "NOME_NORMALIZADO",
        lambda r: norm(r.get("nome_produto", "")),
        lambda k, g: "BAIXA",
        lambda k, g: f"{len(g)} registros com mesmo nome_produto normalizado",
        registros,
    )

    # Dup 5: principio_ativo_normalizado
    dup_rows += analisar_duplicidade(
        "PA_NORMALIZADO",
        lambda r: norm(r.get("principio_ativo_normalizado", "")),
        lambda k, g: "BAIXA",
        lambda k, g: f"{len(g)} registros com mesmo principio_ativo_normalizado",
        registros,
    )

    escrever_csv(DUPLICIDADES, COLS_DUP, dup_rows)
    print(f"  Duplicidades: {len(dup_rows)} grupos")

    # IDs com numero_registro duplicado (severidade ALTA ou MEDIA)
    ids_dup_numreg_alta = set()
    for d in dup_rows:
        if d["tipo_duplicidade"] == "NUMERO_REGISTRO" and d["severidade"] == "ALTA":
            for part in d["exemplos_ids"].split(" | "):
                ids_dup_numreg_alta.add(part.strip())

    # -----------------------------------------------------------------------
    # Pendencias
    # -----------------------------------------------------------------------
    pend_rows = []

    # Status nao OK
    for r in registros:
        st = r.get("status_processamento", "")
        if st != "OK":
            pend_rows.append({
                "id_registro_processamento": r.get("id_registro_processamento", ""),
                "tipo_pendencia": "STATUS_PROCESSAMENTO_NAO_OK",
                "campo": "status_processamento",
                "valor_encontrado": st,
                "severidade": "ALTA",
                "bloqueia_pre_carga": "SIM",
                "observacao": r.get("motivo_status", ""),
            })

    # Campo critico vazio — bloqueia somente sem nome E sem PA
    for r in registros:
        sem_n = vazio(r.get("nome_produto", ""))
        sem_p = vazio(r.get("principio_ativo", ""))
        sem_nr = vazio(r.get("numero_registro", ""))
        sem_emp = vazio(r.get("empresa_detentora", ""))

        if sem_n:
            bloqueia = "SIM" if sem_p else "NAO"
            pend_rows.append({
                "id_registro_processamento": r.get("id_registro_processamento", ""),
                "tipo_pendencia": "NOME_PRODUTO_AUSENTE",
                "campo": "nome_produto",
                "valor_encontrado": "",
                "severidade": "ALTA" if sem_p else "MEDIA",
                "bloqueia_pre_carga": bloqueia,
                "observacao": "nome_produto vazio" + (" e principio_ativo vazio" if sem_p else ""),
            })

        if sem_p:
            pend_rows.append({
                "id_registro_processamento": r.get("id_registro_processamento", ""),
                "tipo_pendencia": "PRINCIPIO_ATIVO_AUSENTE",
                "campo": "principio_ativo",
                "valor_encontrado": "",
                "severidade": "MEDIA",
                "bloqueia_pre_carga": "NAO",
                "observacao": "principio_ativo vazio",
            })

        if sem_nr:
            pend_rows.append({
                "id_registro_processamento": r.get("id_registro_processamento", ""),
                "tipo_pendencia": "NUMERO_REGISTRO_AUSENTE",
                "campo": "numero_registro",
                "valor_encontrado": "",
                "severidade": "ALTA",
                "bloqueia_pre_carga": "SIM",
                "observacao": "numero_registro vazio impede rastreabilidade",
            })

        if sem_emp:
            pend_rows.append({
                "id_registro_processamento": r.get("id_registro_processamento", ""),
                "tipo_pendencia": "EMPRESA_AUSENTE",
                "campo": "empresa_detentora",
                "valor_encontrado": "",
                "severidade": "MEDIA",
                "bloqueia_pre_carga": "NAO",
                "observacao": "empresa_detentora vazia",
            })

        if vazio(r.get("forma_farmaceutica", "")):
            pend_rows.append({
                "id_registro_processamento": r.get("id_registro_processamento", ""),
                "tipo_pendencia": "FORMA_FARMACEUTICA_AUSENTE",
                "campo": "forma_farmaceutica",
                "valor_encontrado": "",
                "severidade": "BAIXA",
                "bloqueia_pre_carga": "NAO",
                "observacao": "campo ausente no bruto da ANVISA",
            })

        if vazio(r.get("concentracao", "")):
            pend_rows.append({
                "id_registro_processamento": r.get("id_registro_processamento", ""),
                "tipo_pendencia": "CONCENTRACAO_AUSENTE",
                "campo": "concentracao",
                "valor_encontrado": "",
                "severidade": "BAIXA",
                "bloqueia_pre_carga": "NAO",
                "observacao": "campo ausente no bruto da ANVISA",
            })

        if vazio(r.get("apresentacao", "")):
            pend_rows.append({
                "id_registro_processamento": r.get("id_registro_processamento", ""),
                "tipo_pendencia": "APRESENTACAO_AUSENTE",
                "campo": "apresentacao",
                "valor_encontrado": "",
                "severidade": "BAIXA",
                "bloqueia_pre_carga": "NAO",
                "observacao": "campo ausente no bruto da ANVISA",
            })

    # Numero_registro duplicado ALTA
    for rid in ids_dup_numreg_alta:
        pend_rows.append({
            "id_registro_processamento": rid,
            "tipo_pendencia": "NUMERO_REGISTRO_DUPLICADO",
            "campo": "numero_registro",
            "valor_encontrado": "",
            "severidade": "ALTA",
            "bloqueia_pre_carga": "SIM",
            "observacao": "numero_registro duplicado com dados divergentes",
        })

    total_pend = len(pend_rows)
    bloqueantes = sum(1 for p in pend_rows if p["bloqueia_pre_carga"] == "SIM")
    escrever_csv(PENDENCIAS, COLS_PEND, pend_rows)
    print(f"  Pendencias: {total_pend} (bloqueantes: {bloqueantes})")

    # -----------------------------------------------------------------------
    # Amostra
    # -----------------------------------------------------------------------
    amostra_rows = []
    ids_ja_na_amostra = set()

    def add_amostra(grupo, lista, motivo, limite=20):
        count = 0
        for r in lista:
            rid = r.get("id_registro_processamento", "")
            if rid not in ids_ja_na_amostra:
                amostra_rows.append(amostra_row(grupo, r, motivo))
                ids_ja_na_amostra.add(rid)
                count += 1
            if count >= limite:
                break

    # Primeiros 20
    add_amostra("PRIMEIROS_20", registros[:20], "primeiros registros do arquivo")
    # Ultimos 20
    add_amostra("ULTIMOS_20", registros[-20:], "ultimos registros do arquivo")
    # Aleatorios com seed fixa
    rng = random.Random(RANDOM_SEED)
    aleatorios = rng.sample(registros, min(20, total))
    add_amostra("ALEATORIOS_SEED42", aleatorios, "amostra aleatoria seed=42")

    # Por situacao_registro
    for sit in sorted(cnt_situacao.keys())[:5]:
        grupo_regs = [r for r in registros if r.get("situacao_registro", "") == sit]
        add_amostra(f"SITUACAO_{sit[:30]}", grupo_regs, f"situacao_registro={sit}")

    # Por tipo_produto
    for tp in sorted(cnt_tipo.keys())[:3]:
        grupo_regs = [r for r in registros if r.get("tipo_produto", "") == tp]
        add_amostra(f"TIPO_{tp[:30]}", grupo_regs, f"tipo_produto={tp}")

    # Com campos criticos vazios
    criticos_vazios = [r for r in registros
                       if vazio(r.get("nome_produto", "")) or vazio(r.get("principio_ativo", ""))]
    add_amostra("CRITICOS_VAZIOS", criticos_vazios, "nome_produto ou principio_ativo vazio")

    # Com maior quantidade de campos vazios
    todos_campos = [c for c in colunas if c not in ("campo_original_json",)]
    por_vazios = sorted(registros, key=lambda r: contar_vazios_por_linha(r, todos_campos), reverse=True)
    add_amostra("MAIS_CAMPOS_VAZIOS", por_vazios[:20], "maior quantidade de campos vazios")

    # Envolvidos em duplicidades numero_registro
    ids_dup = set()
    for d in dup_rows:
        if d["tipo_duplicidade"] == "NUMERO_REGISTRO":
            for part in d["exemplos_ids"].split(" | "):
                ids_dup.add(part.strip())
    dup_regs = [r for r in registros if r.get("id_registro_processamento", "") in ids_dup]
    add_amostra("DUP_NUMERO_REGISTRO", dup_regs, "envolvido em duplicidade de numero_registro")

    # Envolvidos em pendencias bloqueantes
    ids_bloq = set(p["id_registro_processamento"] for p in pend_rows if p["bloqueia_pre_carga"] == "SIM")
    bloq_regs = [r for r in registros if r.get("id_registro_processamento", "") in ids_bloq]
    add_amostra("PENDENCIA_BLOQUEANTE", bloq_regs, "registro com pendencia bloqueante")

    escrever_csv(AMOSTRA, COLS_AMOSTRA, amostra_rows)
    print(f"  Amostra: {len(amostra_rows)} registros")

    # -----------------------------------------------------------------------
    # Decisao tecnica
    # -----------------------------------------------------------------------
    decisao = "APTO_PARA_PREPARAR_PRE_CARGA" if bloqueantes == 0 else "REVISAR_ANTES_PRE_CARGA"

    # -----------------------------------------------------------------------
    # Relatorio
    # -----------------------------------------------------------------------
    top20_empresas = "\n".join(
        f"- {emp or '(vazio)'}: {cnt}" for emp, cnt in cnt_empresa.most_common(20)
    )
    criticos_pct_md = "\n".join(
        f"- `{c}`: {preenchimento.get(c, 0)}/{total} ({pct(preenchimento.get(c, 0), total)})"
        for c in CAMPOS_CRITICOS
    )
    status_md = "\n".join(f"- {k or '(vazio)'}: {v}" for k, v in cnt_status.most_common())
    sit_md    = "\n".join(f"- {k or '(vazio)'}: {v}" for k, v in cnt_situacao.most_common())
    tipo_md   = "\n".join(f"- {k or '(vazio)'}: {v}" for k, v in cnt_tipo.most_common())
    cat_md    = "\n".join(f"- {k or '(vazio)'}: {v}" for k, v in cnt_categoria.most_common(20))
    dup_resumo = Counter(d["tipo_duplicidade"] for d in dup_rows)
    dup_md = "\n".join(f"- {t}: {c} grupos de duplicidade" for t, c in dup_resumo.items()) if dup_resumo else "- Sem duplicidades encontradas"
    pend_tipos = Counter(p["tipo_pendencia"] for p in pend_rows)
    pend_md = "\n".join(f"- {t}: {c}" for t, c in pend_tipos.most_common())
    campos_vazios_md = ", ".join(campos_100_vazios) if campos_100_vazios else "nenhum"

    # Exemplos relevantes
    ex_rows = [r for r in registros if not vazio(r.get("nome_produto", "")) and not vazio(r.get("principio_ativo", ""))][:5]
    ex_md = ""
    for i, r in enumerate(ex_rows, 1):
        ex_md += f"\n### Exemplo {i}\n"
        for campo in ["nome_produto", "principio_ativo", "empresa_detentora",
                      "numero_registro", "situacao_registro", "categoria_regulatoria",
                      "status_processamento"]:
            ex_md += f"- **{campo}**: {r.get(campo, '')}\n"

    relatorio = f"""# Auditoria do Intermediario — ANVISA Medicamentos Registrados
## FASE 2.3 — {DATA}

## Objetivo
Auditar o arquivo intermediario da ANVISA Medicamentos Registrados para identificar qualidade,
duplicidades, campos vazios, padroes de dados e aptidao para preparar pre-carga futura.
Somente leitura. Nenhum arquivo foi alterado.

## Arquivo auditado
`data/dicionario_mestre/processado/anvisa_medicamentos_registrados_normalizado.csv`

## Totais
- Total de registros: {total}
- Total de colunas:   {len(colunas)}

## Contagem por status_processamento
{status_md}

## Contagem por situacao_registro
{sit_md}

## Contagem por tipo_produto
{tipo_md}

## Contagem por categoria_regulatoria (top 20)
{cat_md}

## Top 20 empresas detentoras
{top20_empresas}

## Preenchimento dos campos criticos
{criticos_pct_md}

## Campos 100% vazios
{campos_vazios_md}

## Registros com campos criticos ausentes
- Sem nome_produto:        {len(sem_nome)} ({pct(len(sem_nome), total)})
- Sem principio_ativo:     {len(sem_pa)} ({pct(len(sem_pa), total)})
- Sem numero_registro:     {len(sem_numreg)} ({pct(len(sem_numreg), total)})
- Sem empresa_detentora:   {len(sem_empresa)} ({pct(len(sem_empresa), total)})
- Sem forma_farmaceutica:  {len(sem_forma)} ({pct(len(sem_forma), total)}) — ausente no bruto
- Sem concentracao:        {len(sem_conc)} ({pct(len(sem_conc), total)}) — ausente no bruto
- Sem apresentacao:        {len(sem_apres)} ({pct(len(sem_apres), total)}) — ausente no bruto
- Sem via_uso:             {len(sem_via)} ({pct(len(sem_via), total)}) — ausente no bruto

## Resumo de duplicidades
{dup_md}

Arquivo completo: `data/dicionario_mestre/processado/duplicidades_anvisa_medicamentos_registrados.csv`

## Resumo de pendencias
{pend_md}

- **Total de pendencias**: {total_pend}
- **Pendencias bloqueantes**: {bloqueantes}

Arquivo completo: `data/dicionario_mestre/processado/pendencias_anvisa_medicamentos_registrados.csv`

## Exemplos relevantes
{ex_md}

## Riscos
- Campos forma_farmaceutica, concentracao, apresentacao e via_uso ausentes no bruto da ANVISA.
  Precisarao ser preenchidos por outras fontes ou processo manual na pre-carga.
- Duplicidades em numero_registro devem ser investigadas antes da mesclagem com o dicionario final.
- Registros sem numero_registro (se houver) sao de rastreabilidade reduzida.

## Limitacoes
- Auditoria realizada exclusivamente sobre o intermediario gerado na FASE 2.2.
- Nenhum cruzamento com dicionario final, SKU_MASTER ou fonte interna foi realizado.
- Campos ausentes no bruto permanecem vazios e nao indicam erro de processamento.

## Decisao tecnica
**{decisao}**

{"Nenhuma pendencia bloqueante foi identificada. O intermediario esta apto para iniciar a preparacao da pre-carga na FASE 2.4." if decisao == "APTO_PARA_PREPARAR_PRE_CARGA" else f"Foram identificadas {bloqueantes} pendencias bloqueantes. Revisar antes de prosseguir."}

## Confirmacoes de integridade
- **Dicionario final nao alterado**: dicionario_mestre_medbox.csv, dicionario_mestre_medicamentos.csv e dicionario_mestre_produtos_saude.csv nao foram lidos nem modificados.
- **Intermediario FASE 2.2 nao alterado**: arquivo lido em modo somente leitura.
- **Banco nao usado**: nenhuma conexao com banco de dados.
- **Fonte interna nao usada**: data/dicionario_mestre/interno nao foi acessado.
- **SKU_MASTER nao aplicado**: uploads/SKU_MASTER_*.xlsx nao foi acessado.

## Proxima etapa recomendada
**FASE 2.4 — Preparacao da pre-carga ANVISA Medicamentos Registrados**
- Definir criterios de elegibilidade (situacao_registro, tipo_produto, etc).
- Mapear campos do intermediario para o dicionario final.
- Gerar pre-dicionario de medicamentos ANVISA como rascunho auditavel.
- Nao mesclar ainda.
"""
    AUDITORIA.write_text(relatorio, encoding="utf-8")
    print(f"  Auditoria gravada: {AUDITORIA}")

    return {
        "total": total,
        "colunas": len(colunas),
        "cnt_status": dict(cnt_status),
        "total_dup_grupos": len(dup_rows),
        "total_pend": total_pend,
        "bloqueantes": bloqueantes,
        "decisao": decisao,
    }


if __name__ == "__main__":
    r = auditar()
    print(f"\n[FASE 2.3] Auditoria concluida.")
    print(f"  Registros:    {r['total']}")
    print(f"  Dup grupos:   {r['total_dup_grupos']}")
    print(f"  Pendencias:   {r['total_pend']}")
    print(f"  Bloqueantes:  {r['bloqueantes']}")
    print(f"  Decisao:      {r['decisao']}")
