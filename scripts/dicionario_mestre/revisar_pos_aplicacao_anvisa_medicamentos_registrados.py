"""
FASE 2.7 — Revisão pós-aplicação ANVISA Medicamentos Registrados
Modo: READ-ONLY sobre dicionario_mestre_medicamentos.csv
Gera: consistencia, pendencias, amostra e auditoria MD.
NÃO altera o dicionário mestre.
"""

import csv
import random
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DICT_FILE = ROOT / "data/dicionario_mestre/dicionario_mestre_medicamentos.csv"
BACKUP_FILE = ROOT / "backups/dicionario_mestre/dicionario_mestre_medicamentos_ANTES_ANVISA_MEDREG_20260626_130122.csv"
PRE_CARGA_FILE = ROOT / "data/dicionario_mestre/processado/pre_carga_anvisa_medicamentos_registrados.csv"
DRY_RUN_FILE = ROOT / "data/dicionario_mestre/processado/dry_run_aplicacao_anvisa_medicamentos_registrados.csv"
PROCESSADO_DIR = ROOT / "data/dicionario_mestre/processado"
DOCS_DIR = ROOT / "docs"
DATA_COLETA = "2026-06-26"

CONSISTENCIA_OUT = PROCESSADO_DIR / "consistencia_pos_aplicacao_anvisa_medicamentos_registrados.csv"
PENDENCIAS_OUT = PROCESSADO_DIR / "pendencias_enriquecimento_anvisa_medicamentos_registrados.csv"
AMOSTRA_OUT = PROCESSADO_DIR / "amostra_pos_aplicacao_anvisa_medicamentos_registrados.csv"
AUDITORIA_OUT = DOCS_DIR / "auditoria_pos_aplicacao_anvisa_medicamentos_registrados.md"

ENC = "utf-8-sig"
SEP = ";"


def ler_csv(path):
    with open(path, encoding=ENC) as f:
        return list(csv.DictReader(f, delimiter=SEP))


def escrever_csv(path, fieldnames, rows):
    with open(path, "w", encoding=ENC, newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, delimiter=SEP)
        w.writeheader()
        w.writerows(rows)


def vz(row, col):
    return (row.get(col) or "").strip()


# ---------------------------------------------------------------------------
# 1. Carregar dados
# ---------------------------------------------------------------------------
print("Carregando dicionario mestre (read-only)...")
dict_rows = ler_csv(DICT_FILE)
print(f"  Total dict: {len(dict_rows):,}")

print("Carregando backup pre-apply...")
backup_rows = ler_csv(BACKUP_FILE)
print(f"  Total backup: {len(backup_rows):,}")

# Segmentar
dcb_rows = [r for r in dict_rows if vz(r, "fonte_tipo") == "INTERNA_DCB" or
            ("ANVISA_DCB" in vz(r, "fonte_nome") or vz(r, "fonte_origem") == "ANVISA_DCB")]
medreg_rows = [r for r in dict_rows if "ANVISA_MEDREG" in vz(r, "id_dicionario")]
dcb_rows_id = [r for r in dict_rows if "ANVISA_DCB" in vz(r, "id_dicionario") or
               vz(r, "fonte_nome") == "ANVISA_DCB"]

# Recalcular pela fonte_nome / fonte_origem para ser preciso
fonte_counter = Counter(vz(r, "fonte_nome") for r in dict_rows)
medreg_final = [r for r in dict_rows if "ANVISA_MEDREG_" in vz(r, "id_dicionario")]
dcb_final = [r for r in dict_rows if r not in medreg_final]

print(f"  ANVISA_MEDREG_* (inseridos): {len(medreg_final):,}")
print(f"  Restantes (DCB): {len(dcb_final):,}")

# ---------------------------------------------------------------------------
# 2. Consistência 23 itens
# ---------------------------------------------------------------------------
print("\nGerando checklist de consistência...")

ESPERADO_TOTAL = 23060
ESPERADO_BACKUP = 12715
ESPERADO_MEDREG = 10345
ESPERADO_PADRAO = 10301
ESPERADO_BAIXO = 44

id_duplicados = len(medreg_final) - len({vz(r, "id_dicionario") for r in medreg_final})
ids_medreg_unicos = {vz(r, "id_dicionario") for r in medreg_final}
ids_backup = {vz(r, "id_dicionario") for r in backup_rows}
colisao_id = len(ids_medreg_unicos & ids_backup)

fontes_indevidas = [r for r in medreg_final if vz(r, "fonte_tipo") != "EXTERNA_OFICIAL"]
confianca_erradas = [r for r in medreg_final if vz(r, "confianca") != "ALTA"]
status_errados = [r for r in medreg_final if vz(r, "status_revisao") != "PRE_VALIDADO_FONTE_OFICIAL"]
sem_rastreabilidade = [r for r in medreg_final
                       if "REGISTRO:" not in vz(r, "observacao") and "PROCESSO:" not in vz(r, "observacao")]
sem_nome = [r for r in medreg_final if not vz(r, "nome_padrao")]
sem_principio = [r for r in medreg_final if not vz(r, "principio_ativo")]
sem_id = [r for r in medreg_final if not vz(r, "id_dicionario")]
ids_formato_errado = [r for r in medreg_final
                      if not (vz(r, "id_dicionario").startswith("ANVISA_MEDREG_") or
                              vz(r, "id_dicionario").startswith("ANVISA_MEDREG_PROC_"))]
sem_data = [r for r in medreg_final if not vz(r, "data_coleta")]
sem_url = [r for r in medreg_final if not vz(r, "url_fonte")]
dcb_alterados = [r for r in backup_rows
                 if vz(r, "id_dicionario") not in {vz(x, "id_dicionario"): x for x in dict_rows}.get(
                     vz(r, "id_dicionario"), {}).items()]

# Verificar DCB intactos
backup_by_id = {vz(r, "id_dicionario"): r for r in backup_rows}
dict_by_id = {vz(r, "id_dicionario"): r for r in dict_rows}
dcb_alterados_real = 0
campos_check = ["nome_padrao", "principio_ativo", "fonte_nome", "fonte_tipo", "confianca"]
for bid, brow in backup_by_id.items():
    if bid in dict_by_id:
        drow = dict_by_id[bid]
        for col in campos_check:
            if vz(brow, col) != vz(drow, col):
                dcb_alterados_real += 1
                break
backup_ids_perdidos = len(set(backup_by_id.keys()) - set(dict_by_id.keys()))

# Contadores de tipo de ID
padrao_ids = [r for r in medreg_final if vz(r, "id_dicionario").startswith("ANVISA_MEDREG_") and
              not vz(r, "id_dicionario").startswith("ANVISA_MEDREG_PROC_")]
baixo_ids = [r for r in medreg_final if vz(r, "id_dicionario").startswith("ANVISA_MEDREG_PROC_")]

# Campos opcionais: quantos vazios nos medreg
campos_enriquecimento = ["forma_farmaceutica", "concentracao", "apresentacao", "via_uso", "dcb", "cas", "atc"]
vazios_por_campo = {c: sum(1 for r in medreg_final if not vz(r, c)) for c in campos_enriquecimento}


def chk(nome, ok, esperado, obtido, obs="", bloqueia="NAO"):
    status = "OK" if ok else "FALHA"
    return {
        "item": nome,
        "status": status,
        "bloqueia_qualidade": bloqueia if not ok else "NAO",
        "esperado": str(esperado),
        "obtido": str(obtido),
        "observacao": obs,
    }


consistencia = []
n = 0


def add(nome, ok, esp, obt, obs="", blq="NAO"):
    global n
    n += 1
    consistencia.append(chk(f"C{n:02d}_{nome}", ok, esp, obt, obs, blq))


add("total_dicionario", len(dict_rows) == ESPERADO_TOTAL, ESPERADO_TOTAL, len(dict_rows),
    "total de registros no dicionario pos-apply", "SIM")
add("backup_preservado", len(backup_rows) == ESPERADO_BACKUP, ESPERADO_BACKUP, len(backup_rows),
    "registros no backup pre-apply", "SIM")
add("medreg_inseridos", len(medreg_final) == ESPERADO_MEDREG, ESPERADO_MEDREG, len(medreg_final),
    "registros ANVISA_MEDREG_* no dicionario", "SIM")
add("soma_logica", len(dcb_final) + len(medreg_final) == ESPERADO_TOTAL,
    ESPERADO_TOTAL, len(dcb_final) + len(medreg_final),
    f"DCB={len(dcb_final)} + MEDREG={len(medreg_final)}", "SIM")
add("padrao_ids_count", len(padrao_ids) == ESPERADO_PADRAO, ESPERADO_PADRAO, len(padrao_ids),
    "registros com ID ANVISA_MEDREG_<numreg>", "NAO")
add("baixo_risco_ids_count", len(baixo_ids) == ESPERADO_BAIXO, ESPERADO_BAIXO, len(baixo_ids),
    "registros com ID ANVISA_MEDREG_PROC_<processo>", "NAO")
add("ids_unicos", id_duplicados == 0, 0, id_duplicados,
    "IDs duplicados nos registros MEDREG", "SIM")
add("colisao_ids_dcb", colisao_id == 0, 0, colisao_id,
    "IDs MEDREG que colidiram com IDs do backup DCB", "SIM")
add("backup_ids_preservados", backup_ids_perdidos == 0, 0, backup_ids_perdidos,
    "IDs do backup que nao aparecem no dicionario final", "SIM")
add("dcb_integros", dcb_alterados_real == 0, 0, dcb_alterados_real,
    "registros DCB com campos alterados (nome/principio/fonte/confianca)", "SIM")
add("fonte_tipo_correta", len(fontes_indevidas) == 0, 0, len(fontes_indevidas),
    "registros MEDREG com fonte_tipo != EXTERNA_OFICIAL", "SIM")
add("confianca_correta", len(confianca_erradas) == 0, 0, len(confianca_erradas),
    "registros MEDREG com confianca != ALTA", "SIM")
add("status_revisao_correto", len(status_errados) == 0, 0, len(status_errados),
    "registros MEDREG com status_revisao != PRE_VALIDADO_FONTE_OFICIAL", "SIM")
add("rastreabilidade_observacao", len(sem_rastreabilidade) == 0, 0, len(sem_rastreabilidade),
    "registros MEDREG sem REGISTRO: ou PROCESSO: no campo observacao", "SIM")
add("ids_formato_correto", len(ids_formato_errado) == 0, 0, len(ids_formato_errado),
    "IDs MEDREG com formato invalido", "SIM")
add("sem_nome_padrao", len(sem_nome) == 0, 0, len(sem_nome),
    "registros MEDREG sem nome_padrao", "SIM")
add("sem_principio_ativo", len(sem_principio) == 0, 0, len(sem_principio),
    "registros MEDREG sem principio_ativo", "NAO")
add("sem_id_dicionario", len(sem_id) == 0, 0, len(sem_id),
    "registros MEDREG com id_dicionario vazio", "SIM")
add("sem_data_coleta", len(sem_data) == 0, 0, len(sem_data),
    "registros MEDREG sem data_coleta", "NAO")
add("sem_url_fonte", len(sem_url) == 0, 0, len(sem_url),
    "registros MEDREG sem url_fonte", "NAO")

# Campos enriquecimento
total_medreg = len(medreg_final)
pct_ff = round(vazios_por_campo["forma_farmaceutica"] / total_medreg * 100, 1)
pct_dcb = round(vazios_por_campo["dcb"] / total_medreg * 100, 1)
add("forma_farmaceutica_vazia", True, "-",
    f"{vazios_por_campo['forma_farmaceutica']:,}/{total_medreg:,} ({pct_ff}%)",
    "campo a enriquecer em fase futura", "NAO")
add("dcb_vazio", True, "-",
    f"{vazios_por_campo['dcb']:,}/{total_medreg:,} ({pct_dcb}%)",
    "campo a enriquecer por cruzamento com ANVISA_DCB", "NAO")
add("atc_vazio", True, "-",
    f"{vazios_por_campo['atc']:,}/{total_medreg:,}",
    "campo a enriquecer por fontes externas", "NAO")

falhas = [c for c in consistencia if c["status"] == "FALHA"]
bloqueantes = [c for c in consistencia if c["bloqueia_qualidade"] == "SIM" and c["status"] == "FALHA"]

print(f"  Consistência: {len(consistencia)} itens, {len(falhas)} falhas, {len(bloqueantes)} bloqueantes")

campos_cons = ["item", "status", "bloqueia_qualidade", "esperado", "obtido", "observacao"]
escrever_csv(CONSISTENCIA_OUT, campos_cons, consistencia)
print(f"  -> {CONSISTENCIA_OUT.name}")

# ---------------------------------------------------------------------------
# 3. Pendências de enriquecimento
# ---------------------------------------------------------------------------
print("\nGerando pendências de enriquecimento...")
pendencias = []
for campo in campos_enriquecimento:
    qtd = vazios_por_campo[campo]
    pct = round(qtd / total_medreg * 100, 1)
    pendencias.append({
        "campo": campo,
        "qtd_vazios": qtd,
        "pct_vazios": f"{pct}%",
        "qtd_preenchidos": total_medreg - qtd,
        "pct_preenchidos": f"{round(100 - pct, 1)}%",
        "prioridade_enriquecimento": (
            "ALTA" if pct > 80 else "MEDIA" if pct > 30 else "BAIXA"
        ),
        "sugestao_fonte": {
            "forma_farmaceutica": "ANVISA Consultas / Bulario Eletronico",
            "concentracao": "ANVISA Consultas / Bulario Eletronico",
            "apresentacao": "ANVISA Consultas / Bulario Eletronico",
            "via_uso": "ANVISA Consultas / Bulario Eletronico",
            "dcb": "Cruzamento com registros ANVISA_DCB (nome_padrao ~ principio_ativo)",
            "cas": "PubChem / ChemSpider por principio_ativo",
            "atc": "WHO ATC Index por principio_ativo / DCB",
        }.get(campo, ""),
    })

campos_pend = ["campo", "qtd_vazios", "pct_vazios", "qtd_preenchidos", "pct_preenchidos",
               "prioridade_enriquecimento", "sugestao_fonte"]
escrever_csv(PENDENCIAS_OUT, campos_pend, pendencias)
print(f"  -> {PENDENCIAS_OUT.name}")

# ---------------------------------------------------------------------------
# 4. Amostra
# ---------------------------------------------------------------------------
print("\nGerando amostra...")
random.seed(42)
amostras = []

grupos = {
    "PADRAO_aleatorio": padrao_ids,
    "BAIXO_RISCO_todos": baixo_ids,
    "MEDREG_sem_principio": [r for r in medreg_final if not vz(r, "principio_ativo")],
    "MEDREG_com_dcb": [r for r in medreg_final if vz(r, "dcb")],
    "MEDREG_sem_forma_farmaceutica": [r for r in medreg_final if not vz(r, "forma_farmaceutica")],
}

for grupo, pool in grupos.items():
    n_amostrar = len(pool) if len(pool) <= 10 else 15
    selecionados = random.sample(pool, min(n_amostrar, len(pool))) if pool else []
    for r in selecionados:
        amostras.append({**{"grupo_amostra": grupo}, **r})

campos_am = ["grupo_amostra"] + list(dict_rows[0].keys()) if dict_rows else ["grupo_amostra"]
escrever_csv(AMOSTRA_OUT, campos_am, amostras)
print(f"  -> {AMOSTRA_OUT.name} ({len(amostras)} linhas)")

# ---------------------------------------------------------------------------
# 5. Relatório MD
# ---------------------------------------------------------------------------
print("\nGerando auditoria MD...")

now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
decisao = "APTO_PARA_PLANEJAR_ENRIQUECIMENTO" if not bloqueantes else "BLOQUEADO_FALHAS_CRITICAS"

# Tabela de pendências
tabela_pend = "\n".join(
    f"| {p['campo']} | {p['qtd_vazios']:,} | {p['pct_vazios']} | {p['prioridade_enriquecimento']} | {p['sugestao_fonte'][:55]} |"
    for p in pendencias
)

# Tabela de consistência (só falhas ou todos)
tabela_cons_linhas = "\n".join(
    f"| {c['item']} | {c['status']} | {c['bloqueia_qualidade']} | {c['esperado']} | {c['obtido']} |"
    for c in consistencia
)

fonte_dist = Counter(vz(r, "fonte_nome") for r in dict_rows)
fonte_dist_txt = "\n".join(f"- {k}: {v:,}" for k, v in sorted(fonte_dist.items(), key=lambda x: -x[1]))

auditoria_md = f"""# Auditoria Pós-Aplicação — ANVISA Medicamentos Registrados

**Data:** {now_str}
**Fase:** 2.7 — Revisão pós-aplicação
**Branch:** melhoria/auditoria-sku-master-todos-produtos
**Decisão final:** `{decisao}`

---

## 1. Sumário executivo

| Indicador | Valor |
|---|---|
| Total de registros no dicionário | {len(dict_rows):,} |
| Registros do backup (pré-apply) | {len(backup_rows):,} |
| Registros ANVISA_MEDREG inseridos | {len(medreg_final):,} |
| IDs tipo ANVISA_MEDREG_<numreg> (padrão) | {len(padrao_ids):,} |
| IDs tipo ANVISA_MEDREG_PROC_<processo> (baixo risco) | {len(baixo_ids):,} |
| Registros DCB preservados intactos | {dcb_alterados_real == 0} |
| Itens de consistência verificados | {len(consistencia)} |
| Falhas | {len(falhas)} |
| Falhas bloqueantes | {len(bloqueantes)} |

---

## 2. Checklist de consistência (23 itens)

| Item | Status | Bloqueia | Esperado | Obtido |
|---|---|---|---|---|
{tabela_cons_linhas}

---

## 3. Distribuição por fonte no dicionário final

{fonte_dist_txt}

---

## 4. Pendências de enriquecimento dos registros MEDREG

| Campo | Vazios | % Vazio | Prioridade | Fonte sugerida |
|---|---|---|---|---|
{tabela_pend}

### Estratégia de enriquecimento sugerida

1. **DCB** — cruzamento `principio_ativo` dos MEDREG contra `nome_padrao` / `principio_ativo` dos DCB existentes.
2. **Forma farmacêutica / Concentração / Apresentação** — FASE 2.8+ via ANVISA Consultas (registro → dados completos).
3. **Via de uso** — derivável parcialmente da forma farmacêutica; complementar por ANVISA Consultas.
4. **ATC** — WHO ATC Index por DCB ou princípio ativo (fase futura).
5. **CAS** — PubChem por princípio ativo (fase futura, menor prioridade).

---

## 5. Rastreabilidade dos IDs

- Padrão (ANVISA_MEDREG_<NUMREG>): {len(padrao_ids):,} registros — rastreados pelo número de registro ANVISA.
- Baixo risco (ANVISA_MEDREG_PROC_<PROCESSO>): {len(baixo_ids):,} registros — rastreados pelo número de processo.
- Registros sem rastreabilidade no campo `observacao`: {len(sem_rastreabilidade)}.

---

## 6. Integridade dos registros DCB originais

- Registros no backup: {len(backup_rows):,}
- IDs do backup perdidos no dicionário final: {backup_ids_perdidos}
- Registros DCB com campos alterados: {dcb_alterados_real}
- **Conclusão:** {'DCB 100% PRESERVADOS E INTACTOS' if dcb_alterados_real == 0 and backup_ids_perdidos == 0 else 'ATENCAO: verificar alteracoes'}

---

## 7. Arquivos gerados por esta fase

| Arquivo | Descrição |
|---|---|
| `processado/consistencia_pos_aplicacao_anvisa_medicamentos_registrados.csv` | {len(consistencia)} itens de consistência |
| `processado/pendencias_enriquecimento_anvisa_medicamentos_registrados.csv` | {len(pendencias)} campos a enriquecer |
| `processado/amostra_pos_aplicacao_anvisa_medicamentos_registrados.csv` | {len(amostras)} registros de amostra |
| `docs/auditoria_pos_aplicacao_anvisa_medicamentos_registrados.md` | Este relatório |

---

## 8. Decisão

**{decisao}**

{'Nenhuma falha bloqueante identificada. O dicionário está íntegro e os 10.345 registros ANVISA_MEDREG foram aplicados corretamente. A próxima etapa é planejar o enriquecimento dos campos vazios, priorizando forma_farmaceutica, concentracao e apresentacao via ANVISA Consultas.' if not bloqueantes else f'ATENÇÃO: {len(bloqueantes)} falha(s) bloqueante(s) identificada(s). Revisar antes de prosseguir.'}

---

*Gerado automaticamente por `revisar_pos_aplicacao_anvisa_medicamentos_registrados.py` — FASE 2.7*
"""

DOCS_DIR.mkdir(exist_ok=True)
AUDITORIA_OUT.write_text(auditoria_md, encoding="utf-8")
print(f"  -> {AUDITORIA_OUT.name}")

# ---------------------------------------------------------------------------
# 6. Resumo final
# ---------------------------------------------------------------------------
print("\n" + "=" * 60)
print("FASE 2.7 — RESUMO FINAL")
print("=" * 60)
print(f"  Total dict final:    {len(dict_rows):,}")
print(f"  Backup (pre-apply):  {len(backup_rows):,}")
print(f"  ANVISA_MEDREG:       {len(medreg_final):,}")
print(f"    PADRAO:            {len(padrao_ids):,}")
print(f"    BAIXO_RISCO:       {len(baixo_ids):,}")
print(f"  DCB alterados:       {dcb_alterados_real}")
print(f"  Consistencia:        {len(consistencia)} itens / {len(falhas)} falhas / {len(bloqueantes)} bloqueantes")
print(f"  Decisao:             {decisao}")
print(f"\n  READ-ONLY: dicionario_mestre_medicamentos.csv NAO FOI ALTERADO.")
print("=" * 60)
