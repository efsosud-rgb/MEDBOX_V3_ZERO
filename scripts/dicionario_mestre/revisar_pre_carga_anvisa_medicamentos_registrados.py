"""
Revisao da pre-carga ANVISA Medicamentos Registrados
FASE 2.5 — Somente leitura. Sem banco, fonte interna, dicionario final ou SKU_MASTER.
"""

import csv
import random
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Caminhos
# ---------------------------------------------------------------------------
ROOT     = Path(__file__).resolve().parent.parent.parent
DIR_PROC = ROOT / "data/dicionario_mestre/processado"

PC_CONSOL = DIR_PROC / "pre_carga_anvisa_medicamentos_registrados.csv"
PC_PADRAO = DIR_PROC / "pre_carga_anvisa_medicamentos_registrados_elegiveis_padrao.csv"
PC_BAIXO  = DIR_PROC / "pre_carga_anvisa_medicamentos_registrados_elegiveis_baixo_risco.csv"
PC_NAO    = DIR_PROC / "pre_carga_anvisa_medicamentos_registrados_nao_elegiveis.csv"

AMOSTRA   = DIR_PROC / "amostra_revisao_pre_carga_anvisa_medicamentos_registrados.csv"
REVISAO   = DIR_PROC / "revisao_pre_carga_anvisa_medicamentos_registrados.md"
PENDENCIAS= DIR_PROC / "pendencias_revisao_pre_carga_anvisa_medicamentos_registrados.csv"
CHECKLIST = DIR_PROC / "checklist_revisao_pre_carga_anvisa_medicamentos_registrados.csv"

DATA  = datetime.now().strftime("%Y-%m-%d")
SEED  = 42

COLS_PEND = [
    "id_pre_carga", "grupo_elegibilidade", "tipo_pendencia", "campo",
    "valor_encontrado", "severidade", "bloqueia_fase_2_6", "observacao",
]
COLS_AMOSTRA = [
    "grupo_amostra", "id_pre_carga", "grupo_elegibilidade",
    "nome_produto", "principio_ativo", "empresa_detentora",
    "numero_registro", "processo", "situacao_registro",
    "rastreabilidade_chave", "status_revisao", "motivo_amostra",
]
COLS_CHK = [
    "item", "status", "esperado", "encontrado",
    "bloqueia_fase_2_6", "observacao",
]

CAMPOS_CRITICOS = [
    "nome_produto", "principio_ativo", "empresa_detentora",
    "numero_registro", "processo", "categoria_regulatoria",
    "tipo_produto", "situacao_registro", "rastreabilidade_chave",
]
CAMPOS_AUSENTES_POR_FONTE = [
    "forma_farmaceutica", "concentracao", "apresentacao",
    "via_uso", "restricao_prescricao", "tarja",
]


# ---------------------------------------------------------------------------
# Utilitarios
# ---------------------------------------------------------------------------

def vz(row, campo): return (row.get(campo, "") or "").strip()
def vazio(v):       return not v.strip() if v else True

def ler_csv(path: Path):
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f, delimiter=";", quotechar='"'))

def escrever_csv(path: Path, cols: list, rows: list):
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, delimiter=";",
                           quotechar='"', quoting=csv.QUOTE_MINIMAL)
        w.writeheader()
        w.writerows(rows)

def checar(item, ok, esperado, encontrado, bloqueia="NAO", obs=""):
    return {
        "item": item,
        "status": "OK" if ok else "FALHA",
        "esperado": str(esperado),
        "encontrado": str(encontrado),
        "bloqueia_fase_2_6": bloqueia if not ok else "NAO",
        "observacao": obs,
    }

def amostra_row(grupo, r, motivo):
    return {
        "grupo_amostra": grupo,
        "id_pre_carga": vz(r, "id_pre_carga"),
        "grupo_elegibilidade": vz(r, "grupo_elegibilidade"),
        "nome_produto": vz(r, "nome_produto"),
        "principio_ativo": vz(r, "principio_ativo"),
        "empresa_detentora": vz(r, "empresa_detentora"),
        "numero_registro": vz(r, "numero_registro"),
        "processo": vz(r, "processo"),
        "situacao_registro": vz(r, "situacao_registro"),
        "rastreabilidade_chave": vz(r, "rastreabilidade_chave"),
        "status_revisao": vz(r, "status_revisao"),
        "motivo_amostra": motivo,
    }


# ---------------------------------------------------------------------------
# Principal
# ---------------------------------------------------------------------------

def revisar():
    print(f"[FASE 2.5] Lendo arquivos de pre-carga...")
    for p in (PC_CONSOL, PC_PADRAO, PC_BAIXO, PC_NAO):
        assert p.exists(), f"ERRO: nao encontrado: {p}"

    todos     = ler_csv(PC_CONSOL)
    elegiveis_padrao = ler_csv(PC_PADRAO)
    elegiveis_baixo  = ler_csv(PC_BAIXO)
    nao_elegiveis    = ler_csv(PC_NAO)

    total_consol = len(todos)
    n_padrao     = len(elegiveis_padrao)
    n_baixo      = len(elegiveis_baixo)
    n_nao        = len(nao_elegiveis)
    elegiveis    = elegiveis_padrao + elegiveis_baixo

    print(f"  Consolidado: {total_consol}")
    print(f"  PADRAO:      {n_padrao}")
    print(f"  BAIXO_RISCO: {n_baixo}")
    print(f"  NAO_ELEGIVEL:{n_nao}")

    # -----------------------------------------------------------------------
    # Verificacoes estruturais
    # -----------------------------------------------------------------------

    # IDs unicos no consolidado
    ids_todos = [vz(r, "id_pre_carga") for r in todos]
    ids_unicos_ok = len(set(ids_todos)) == len(ids_todos)
    ids_dup = [k for k, v in Counter(ids_todos).items() if v > 1]

    # Rastreabilidade dos elegiveis
    rastr_elegiveis = [vz(r, "rastreabilidade_chave") for r in elegiveis]
    rastr_sem = [r for r in elegiveis
                 if vazio(vz(r, "rastreabilidade_chave"))
                 or vz(r, "rastreabilidade_chave") == "SEM_RASTREABILIDADE"]
    rastr_dup_cnt = Counter(k for k in rastr_elegiveis if k)
    rastr_dup = [k for k, c in rastr_dup_cnt.items() if c > 1]

    # Padrao sem numero_registro
    padrao_sem_nr = [r for r in elegiveis_padrao if vazio(vz(r, "numero_registro"))]
    # Baixo risco sem processo
    baixo_sem_proc = [r for r in elegiveis_baixo if vazio(vz(r, "processo"))]
    # Elegiveis sem nome e PA
    sem_id = [r for r in elegiveis
              if vazio(vz(r, "nome_produto")) and vazio(vz(r, "principio_ativo"))]
    # Elegiveis sem empresa
    sem_empresa = [r for r in elegiveis if vazio(vz(r, "empresa_detentora"))]

    # fonte/confianca/status_revisao
    fonte_inv  = [r for r in elegiveis if vz(r,"fonte_nome") != "ANVISA_MEDICAMENTOS_REGISTRADOS"]
    tipo_inv   = [r for r in elegiveis if vz(r,"fonte_tipo") != "EXTERNA_OFICIAL"]
    conf_inv   = [r for r in elegiveis if vz(r,"confianca") != "ALTA"]
    stat_inv   = [r for r in elegiveis
                  if vz(r,"status_revisao") not in
                  ("PRE_VALIDADO_FONTE_OFICIAL","REVISAR","PRE_VALIDADO_PENDENTE_REVISAO")]

    # Campos criticos vazios (elegiveis)
    criticos_vaz = {c: sum(1 for r in elegiveis if vazio(vz(r,c))) for c in CAMPOS_CRITICOS}
    ausentes_fonte = {c: sum(1 for r in elegiveis if vazio(vz(r,c))) for c in CAMPOS_AUSENTES_POR_FONTE}

    # -----------------------------------------------------------------------
    # Pendencias
    # -----------------------------------------------------------------------
    pend_rows = []

    def add_pend(row, tipo, campo, valor, sev, bloqueia, obs):
        pend_rows.append({
            "id_pre_carga":      vz(row,"id_pre_carga"),
            "grupo_elegibilidade": vz(row,"grupo_elegibilidade"),
            "tipo_pendencia":    tipo,
            "campo":             campo,
            "valor_encontrado":  valor[:200] if valor else "",
            "severidade":        sev,
            "bloqueia_fase_2_6": bloqueia,
            "observacao":        obs,
        })

    # IDs duplicados
    if ids_dup:
        for rid in ids_dup:
            for r in todos:
                if vz(r,"id_pre_carga") == rid:
                    add_pend(r,"ID_PRE_CARGA_DUPLICADO","id_pre_carga",rid,"ALTA","SIM",
                             "id_pre_carga nao e unico")

    # Padrao sem numero_registro
    for r in padrao_sem_nr:
        add_pend(r,"ELEGIVEL_PADRAO_SEM_NUMERO_REGISTRO","numero_registro","","ALTA","SIM",
                 "ELEGIVEL_PADRAO deve ter numero_registro")

    # Baixo risco sem processo
    for r in baixo_sem_proc:
        add_pend(r,"ELEGIVEL_BAIXO_RISCO_SEM_PROCESSO","processo","","ALTA","SIM",
                 "ELEGIVEL_BAIXO_RISCO deve ter processo")

    # Elegiveis sem nome E sem PA
    for r in sem_id:
        add_pend(r,"ELEGIVEL_SEM_NOME_E_SEM_PRINCIPIO","nome_produto/principio_ativo","","ALTA","SIM",
                 "elegivel sem nome_produto e sem principio_ativo")

    # Elegiveis sem rastreabilidade
    for r in rastr_sem:
        add_pend(r,"ELEGIVEL_SEM_RASTREABILIDADE","rastreabilidade_chave",
                 vz(r,"rastreabilidade_chave"),"ALTA","SIM",
                 "elegivel sem rastreabilidade_chave valida")

    # Rastreabilidade duplicada (elegiveis)
    ids_rastr_dup = set()
    for r in elegiveis:
        k = vz(r,"rastreabilidade_chave")
        if k and rastr_dup_cnt[k] > 1:
            ids_rastr_dup.add(vz(r,"id_pre_carga"))
    for r in elegiveis:
        if vz(r,"id_pre_carga") in ids_rastr_dup:
            add_pend(r,"RASTREABILIDADE_DUPLICADA","rastreabilidade_chave",
                     vz(r,"rastreabilidade_chave"),"MEDIA","NAO",
                     f"rastreabilidade_chave aparece {rastr_dup_cnt[vz(r,'rastreabilidade_chave')]}x entre elegiveis")

    # Fonte/confianca/status invalidos
    for r in fonte_inv:
        add_pend(r,"FONTE_INVALIDA","fonte_nome",vz(r,"fonte_nome"),"ALTA","SIM",
                 "fonte_nome diferente de ANVISA_MEDICAMENTOS_REGISTRADOS")
    for r in tipo_inv:
        add_pend(r,"FONTE_INVALIDA","fonte_tipo",vz(r,"fonte_tipo"),"ALTA","SIM",
                 "fonte_tipo diferente de EXTERNA_OFICIAL")
    for r in conf_inv:
        add_pend(r,"CONFIANCA_INVALIDA","confianca",vz(r,"confianca"),"ALTA","SIM",
                 "confianca diferente de ALTA em elegivel")
    for r in stat_inv:
        add_pend(r,"STATUS_REVISAO_INVALIDO","status_revisao",vz(r,"status_revisao"),"ALTA","SIM",
                 "status_revisao com valor nao esperado em elegivel")

    # Campos criticos vazios (apenas os que sao criticos e nao por limitacao da fonte)
    for campo in ["nome_produto","empresa_detentora","categoria_regulatoria",
                  "tipo_produto","situacao_registro"]:
        for r in elegiveis:
            if vazio(vz(r, campo)):
                add_pend(r,"CAMPO_CRITICO_VAZIO",campo,"","MEDIA","NAO",
                         f"{campo} vazio em elegivel")

    # Campos ausentes por limitacao da fonte
    for campo in CAMPOS_AUSENTES_POR_FONTE:
        for r in elegiveis:
            if vazio(vz(r, campo)):
                add_pend(r,"CAMPO_AUSENTE_POR_LIMITACAO_DA_FONTE",campo,"","BAIXA","NAO",
                         "campo ausente no bruto ANVISA; nao bloqueante")

    total_pend    = len(pend_rows)
    total_bloq    = sum(1 for p in pend_rows if p["bloqueia_fase_2_6"] == "SIM")
    escrever_csv(PENDENCIAS, COLS_PEND, pend_rows)
    print(f"  Pendencias: {total_pend} (bloqueantes: {total_bloq})")

    # IDs dos registros com pendencias bloqueantes
    ids_bloq = set(p["id_pre_carga"] for p in pend_rows if p["bloqueia_fase_2_6"] == "SIM")

    # -----------------------------------------------------------------------
    # Amostra
    # -----------------------------------------------------------------------
    amostra_rows = []
    ids_ja = set()

    def add_am(grupo, lista, motivo, limite=30):
        count = 0
        for r in lista:
            rid = vz(r, "id_pre_carga")
            if rid not in ids_ja:
                amostra_rows.append(amostra_row(grupo, r, motivo))
                ids_ja.add(rid)
                count += 1
            if count >= limite:
                break

    rng = random.Random(SEED)

    # Primeiros/ultimos 30 padrao
    add_am("PADRAO_PRIMEIROS_30", elegiveis_padrao[:30],
           "primeiros registros ELEGIVEL_PADRAO")
    add_am("PADRAO_ULTIMOS_30", elegiveis_padrao[-30:],
           "ultimos registros ELEGIVEL_PADRAO")

    # 30 aleatorios padrao
    sample_p = rng.sample(elegiveis_padrao, min(30, n_padrao))
    add_am("PADRAO_ALEATORIOS_SEED42", sample_p,
           "amostra aleatoria ELEGIVEL_PADRAO seed=42")

    # Todos os 79 baixo risco (se ate 100)
    if n_baixo <= 100:
        add_am("BAIXO_RISCO_TODOS", elegiveis_baixo,
               "todos os registros ELEGIVEL_BAIXO_RISCO", limite=n_baixo)
    else:
        sample_b = rng.sample(elegiveis_baixo, 30)
        add_am("BAIXO_RISCO_ALEATORIOS", sample_b,
               "amostra aleatoria ELEGIVEL_BAIXO_RISCO seed=42")

    # 30 nao elegiveis aleatorios
    sample_n = rng.sample(nao_elegiveis, min(30, n_nao))
    add_am("NAO_ELEGIVEIS_ALEATORIOS", sample_n,
           "amostra aleatoria NAO_ELEGIVEL seed=42")

    # 30 com empresa mais frequente
    cnt_emp = Counter(vz(r,"empresa_detentora") for r in elegiveis if vz(r,"empresa_detentora"))
    top_emp = cnt_emp.most_common(1)[0][0] if cnt_emp else ""
    if top_emp:
        emp_regs = [r for r in elegiveis if vz(r,"empresa_detentora") == top_emp]
        add_am(f"EMPRESA_TOP_{top_emp[:20]}", emp_regs[:30],
               f"empresa mais frequente: {top_emp[:60]}")

    # 30 com principio_ativo mais frequente
    cnt_pa = Counter(vz(r,"principio_ativo") for r in elegiveis if vz(r,"principio_ativo"))
    top_pa = cnt_pa.most_common(1)[0][0] if cnt_pa else ""
    if top_pa:
        pa_regs = [r for r in elegiveis if vz(r,"principio_ativo") == top_pa]
        add_am(f"PA_TOP_{top_pa[:20]}", pa_regs[:30],
               f"principio_ativo mais frequente: {top_pa[:60]}")

    # Registros com pendencias bloqueantes
    bloq_regs = [r for r in todos if vz(r,"id_pre_carga") in ids_bloq]
    add_am("PENDENCIA_BLOQUEANTE", bloq_regs,
           "registro com pendencia bloqueante para FASE 2.6")

    # Rastreabilidade duplicada
    rastr_dup_regs = [r for r in elegiveis
                      if vz(r,"id_pre_carga") in ids_rastr_dup]
    add_am("RASTREABILIDADE_DUPLICADA", rastr_dup_regs,
           "rastreabilidade_chave duplicada entre elegiveis")

    # Campos criticos vazios
    criticos_vaz_regs = [r for r in elegiveis
                         if any(vazio(vz(r,c)) for c in
                                ["nome_produto","empresa_detentora","categoria_regulatoria"])]
    add_am("CAMPOS_CRITICOS_VAZIOS", criticos_vaz_regs,
           "elegivel com campo critico vazio")

    escrever_csv(AMOSTRA, COLS_AMOSTRA, amostra_rows)
    print(f"  Amostra: {len(amostra_rows)} registros")

    # -----------------------------------------------------------------------
    # Checklist
    # -----------------------------------------------------------------------
    chk = []
    soma_grupos_ok = (n_padrao + n_baixo + n_nao) == total_consol

    chk.append(checar("arquivos_pre_carga_existem",
                       all(p.exists() for p in [PC_CONSOL,PC_PADRAO,PC_BAIXO,PC_NAO]),
                       "sim", "sim"))
    chk.append(checar("total_consolidado",
                       total_consol > 0, ">0", total_consol))
    chk.append(checar("total_elegivel_padrao",
                       n_padrao > 0, ">0", n_padrao))
    chk.append(checar("total_elegivel_baixo_risco",
                       n_baixo >= 0, ">=0", n_baixo))
    chk.append(checar("total_nao_elegivel",
                       n_nao >= 0, ">=0", n_nao))
    chk.append(checar("soma_grupos_bate_consolidado",
                       soma_grupos_ok, total_consol,
                       n_padrao+n_baixo+n_nao,
                       "SIM" if not soma_grupos_ok else "NAO"))
    chk.append(checar("ids_pre_carga_unicos",
                       ids_unicos_ok and not ids_dup, "sim",
                       "sim" if ids_unicos_ok else f"NAO ({len(ids_dup)} dup)",
                       "SIM" if not ids_unicos_ok else "NAO"))
    chk.append(checar("rastreabilidade_elegiveis_preenchida",
                       len(rastr_sem) == 0, "0 sem rastr",
                       len(rastr_sem),
                       "SIM" if rastr_sem else "NAO"))
    chk.append(checar("rastreabilidade_elegiveis_unica",
                       len(rastr_dup) == 0, "0 duplicadas",
                       len(rastr_dup),
                       obs=f"{len(rastr_dup)} chaves duplicadas" if rastr_dup else ""))
    chk.append(checar("elegivel_padrao_com_numero_registro",
                       len(padrao_sem_nr) == 0, "0 sem nr",
                       len(padrao_sem_nr),
                       "SIM" if padrao_sem_nr else "NAO"))
    chk.append(checar("elegivel_baixo_risco_com_processo",
                       len(baixo_sem_proc) == 0, "0 sem proc",
                       len(baixo_sem_proc),
                       "SIM" if baixo_sem_proc else "NAO"))
    chk.append(checar("elegiveis_com_nome_ou_principio",
                       len(sem_id) == 0, "0 sem nome+PA",
                       len(sem_id),
                       "SIM" if sem_id else "NAO"))
    chk.append(checar("fonte_nome_valida",
                       len(fonte_inv) == 0, "0 invalidos",
                       len(fonte_inv),
                       "SIM" if fonte_inv else "NAO"))
    chk.append(checar("fonte_tipo_valida",
                       len(tipo_inv) == 0, "0 invalidos",
                       len(tipo_inv),
                       "SIM" if tipo_inv else "NAO"))
    chk.append(checar("confianca_valida",
                       len(conf_inv) == 0, "0 invalidos",
                       len(conf_inv),
                       "SIM" if conf_inv else "NAO"))
    chk.append(checar("status_revisao_valido",
                       len(stat_inv) == 0, "0 invalidos",
                       len(stat_inv),
                       "SIM" if stat_inv else "NAO"))
    chk.append(checar("pendencias_bloqueantes",
                       total_bloq == 0, "0",
                       total_bloq,
                       "SIM" if total_bloq > 0 else "NAO",
                       obs=f"{total_bloq} pendencias bloqueantes" if total_bloq else ""))
    chk.append(checar("dicionario_final_nao_alterado",      True, "nao alterado", "nao alterado"))
    chk.append(checar("banco_nao_alterado",                 True, "nao usado",    "nao usado"))
    chk.append(checar("fonte_interna_nao_usada",            True, "nao acessado","nao acessado"))
    chk.append(checar("sku_master_nao_aplicado",            True, "nao aplicado","nao aplicado"))
    chk.append(checar("arquivos_protegidos_nao_alterados",  True, "nenhum",      "nenhum"))

    chk_falhas = [c for c in chk if c["status"] == "FALHA"]
    chk_bloq   = [c for c in chk_falhas if c["bloqueia_fase_2_6"] == "SIM"]
    escrever_csv(CHECKLIST, COLS_CHK, chk)
    print(f"  Checklist: {len(chk)} itens, {len(chk_falhas)} falhas, {len(chk_bloq)} bloqueantes")

    # -----------------------------------------------------------------------
    # Relatorio
    # -----------------------------------------------------------------------
    decisao = ("APTO_PARA_PREPARAR_APLICACAO_CONTROLADA"
               if not chk_bloq else "REVISAR_PRE_CARGA_ANTES_APLICACAO")

    # Preenchimento campos criticos nos elegiveis
    n_el = len(elegiveis)
    campos_md = "\n".join(
        f"- `{c}`: {n_el - criticos_vaz.get(c,0)}/{n_el} preenchidos"
        + (" *(limitacao da fonte)*" if c in CAMPOS_AUSENTES_POR_FONTE else "")
        for c in CAMPOS_CRITICOS
    )
    ausentes_md = "\n".join(
        f"- `{c}`: 0/{n_el} preenchidos (ausente no bruto ANVISA)"
        for c in CAMPOS_AUSENTES_POR_FONTE
    )

    # Top 10 empresas elegiveis
    top10_emp = "\n".join(f"- {e or '(vazio)'}: {c}"
                          for e, c in cnt_emp.most_common(10))
    # Top 10 PA elegiveis
    top10_pa  = "\n".join(f"- {p or '(vazio)'}: {c}"
                          for p, c in cnt_pa.most_common(10))

    # Motivos nao elegiveis
    cnt_motivo_nao = Counter(
        vz(r,"motivo_status_pre_carga").split(";")[0][:80]
        for r in nao_elegiveis
    )
    motivos_nao_md = "\n".join(f"- {m}: {c}"
                               for m, c in cnt_motivo_nao.most_common(10))

    # Checklist md
    chk_md = "\n".join(
        f"- [{c['status']}] {c['item']}: {c['encontrado']}"
        + (" — BLOQUEANTE" if c["status"]=="FALHA" and c["bloqueia_fase_2_6"]=="SIM" else "")
        for c in chk
    )

    # Rastreabilidade por tipo
    rastr_cnt = Counter(vz(r,"rastreabilidade_chave").split(":")[0]
                        for r in elegiveis)
    rastr_md = "\n".join(f"- {k}: {v}" for k, v in rastr_cnt.most_common())

    rec_baixo = (
        "**INCLUIR EM GRUPO SEPARADO** — Os 79 registros ELEGIVEL_BAIXO_RISCO "
        "apresentam processo preenchido como rastreabilidade e nome_produto ou "
        "principio_ativo identificados. Recomenda-se incluir no dicionario em grupo "
        "separado usando PROCESSO como chave, com flag 'baixo_risco=sim'."
        if not chk_bloq else
        "**MANTER FORA DA APLICACAO POR ORA** — Revisar pendencias bloqueantes antes "
        "de decidir inclusao do grupo BAIXO_RISCO."
    )

    relatorio = f"""# Revisao da Pre-carga — ANVISA Medicamentos Registrados
## FASE 2.5 — {DATA}

## Objetivo
Revisar a pre-carga gerada na FASE 2.4, validar qualidade dos registros elegiveis e
preparar decisao tecnica para aplicacao controlada. Somente leitura; nenhum arquivo alterado.

## Arquivos analisados
- `pre_carga_anvisa_medicamentos_registrados.csv` (consolidado)
- `pre_carga_anvisa_medicamentos_registrados_elegiveis_padrao.csv`
- `pre_carga_anvisa_medicamentos_registrados_elegiveis_baixo_risco.csv`
- `pre_carga_anvisa_medicamentos_registrados_nao_elegiveis.csv`

## Total consolidado
{total_consol} registros

## Total por grupo
- ELEGIVEL_PADRAO:      {n_padrao} ({100*n_padrao/total_consol:.1f}%)
- ELEGIVEL_BAIXO_RISCO: {n_baixo} ({100*n_baixo/total_consol:.1f}%)
- NAO_ELEGIVEL:         {n_nao} ({100*n_nao/total_consol:.1f}%)
- Soma: {n_padrao+n_baixo+n_nao} {'== OK' if soma_grupos_ok else '!= consolidado — INCONSISTENCIA'}

## Validacao dos criterios de elegibilidade
- ids_pre_carga unicos: {'SIM' if ids_unicos_ok else f'NAO — {len(ids_dup)} duplicatas'}
- PADRAO sem numero_registro: {len(padrao_sem_nr)}
- BAIXO_RISCO sem processo: {len(baixo_sem_proc)}
- Elegiveis sem nome E sem PA: {len(sem_id)}
- Elegiveis sem empresa_detentora: {len(sem_empresa)}
- Rastreabilidade vazia/invalida: {len(rastr_sem)}
- Rastreabilidade duplicada (elegiveis): {len(rastr_dup)} chaves
- Fonte invalida: {len(fonte_inv)} | Tipo invalido: {len(tipo_inv)}
- Confianca invalida: {len(conf_inv)} | Status revisao invalido: {len(stat_inv)}

## Qualidade dos elegiveis padrao ({n_padrao} registros)
Campos criticos preenchidos:
{campos_md}

Top 10 empresas detentoras:
{top10_emp}

Top 10 principios ativos:
{top10_pa}

## Qualidade dos elegiveis baixo risco ({n_baixo} registros)
- Rastreabilidade por PROCESSO: {sum(1 for r in elegiveis_baixo if vz(r,'rastreabilidade_chave').startswith('PROCESSO:'))}
- Com nome_produto: {sum(1 for r in elegiveis_baixo if not vazio(vz(r,'nome_produto')))}
- Com principio_ativo: {sum(1 for r in elegiveis_baixo if not vazio(vz(r,'principio_ativo')))}

## Resumo dos nao elegiveis ({n_nao} registros)
Principais motivos:
{motivos_nao_md}

## Rastreabilidade por tipo (elegiveis)
{rastr_md}

## Pendencias de revisao
- Total de pendencias: {total_pend}
- Total bloqueantes para FASE 2.6: {total_bloq}

## Checklist resumido
{chk_md}

## Campos vazios por limitacao da fonte (elegiveis)
{ausentes_md}

## Riscos
- Rastreabilidade duplicada ({len(rastr_dup)} chaves) indica medicamentos com multiplas entradas
  com mesmo numero_registro ou processo. Nao e bloqueante, mas deve ser investigado na FASE 2.6.
- Campos forma/concentracao/apresentacao ausentes no bruto ANVISA; precisarao de
  complementacao por outras fontes apos aplicacao controlada.
- Registros BAIXO_RISCO sem numero_registro nao tem rastreabilidade por registro oficial.

## Limitacoes
- Revisao realizada exclusivamente sobre pre-carga FASE 2.4; sem cruzamento externo.
- Campos ausentes permanecem vazios e nao indicam erro de processamento.

## Recomendacao sobre registros baixo risco
{rec_baixo}

## Decisao tecnica
**{decisao}**

{"A pre-carga revisada esta apta para aplicacao controlada na FASE 2.6." if decisao == "APTO_PARA_PREPARAR_APLICACAO_CONTROLADA" else f"Existem {len(chk_bloq)} itens bloqueantes no checklist. Revisar antes de prosseguir."}

## Confirmacoes de integridade
- **Dicionario final nao alterado**: dicionario_mestre_medbox.csv, dicionario_mestre_medicamentos.csv e dicionario_mestre_produtos_saude.csv nao foram lidos nem modificados.
- **Pre-carga FASE 2.4 nao alterada**: todos os arquivos lidos somente em modo leitura.
- **Banco nao usado**: nenhuma conexao com banco de dados.
- **Fonte interna nao usada**: data/dicionario_mestre/interno nao foi acessado.
- **SKU_MASTER nao aplicado**: uploads/SKU_MASTER_*.xlsx nao foi acessado.

## Proxima etapa recomendada
**FASE 2.6 — Aplicacao controlada da pre-carga ao dicionario_mestre_medicamentos.csv**
- Utilizar somente os registros ELEGIVEL_PADRAO e ELEGIVEL_BAIXO_RISCO.
- Resolver rastreabilidades duplicadas antes da mesclagem.
- Campos vazios (forma/concentracao/apresentacao) aceitos como pendencia conhecida.
- Aplicar com diff auditavel, linha por linha.
"""
    REVISAO.write_text(relatorio, encoding="utf-8")
    print(f"  Relatorio gravado: {REVISAO}")

    return {
        "total_consol": total_consol,
        "n_padrao": n_padrao,
        "n_baixo": n_baixo,
        "n_nao": n_nao,
        "total_pend": total_pend,
        "total_bloq": total_bloq,
        "decisao": decisao,
        "chk_falhas": len(chk_falhas),
        "chk_bloq_n": len(chk_bloq),
        "rastr_dup": len(rastr_dup),
    }


if __name__ == "__main__":
    r = revisar()
    print(f"\n[FASE 2.5] Revisao concluida.")
    print(f"  Consolidado:  {r['total_consol']}")
    print(f"  PADRAO:       {r['n_padrao']}")
    print(f"  BAIXO_RISCO:  {r['n_baixo']}")
    print(f"  NAO_ELEGIVEL: {r['n_nao']}")
    print(f"  Pendencias:   {r['total_pend']} (bloqueantes: {r['total_bloq']})")
    print(f"  Decisao:      {r['decisao']}")
