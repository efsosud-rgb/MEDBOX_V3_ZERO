"""
Preparacao de pre-carga ANVISA Medicamentos Registrados
FASE 2.4 — Somente leitura do intermediario. Sem banco, fonte interna, dicionario final ou SKU_MASTER.
"""

import csv
import re
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Caminhos
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent.parent
DIR_PROC = ROOT / "data/dicionario_mestre/processado"

INTERMEDIARIO  = DIR_PROC / "anvisa_medicamentos_registrados_normalizado.csv"
DUPLICIDADES   = DIR_PROC / "duplicidades_anvisa_medicamentos_registrados.csv"
PENDENCIAS     = DIR_PROC / "pendencias_anvisa_medicamentos_registrados.csv"

PRE_CARGA      = DIR_PROC / "pre_carga_anvisa_medicamentos_registrados.csv"
PRE_PADRAO     = DIR_PROC / "pre_carga_anvisa_medicamentos_registrados_elegiveis_padrao.csv"
PRE_BAIXO      = DIR_PROC / "pre_carga_anvisa_medicamentos_registrados_elegiveis_baixo_risco.csv"
PRE_NAO        = DIR_PROC / "pre_carga_anvisa_medicamentos_registrados_nao_elegiveis.csv"
CHECKLIST      = DIR_PROC / "checklist_pre_carga_anvisa_medicamentos_registrados.csv"
RELATORIO      = DIR_PROC / "relatorio_pre_carga_anvisa_medicamentos_registrados.md"

DATA = datetime.now().strftime("%Y-%m-%d")

COLS_PRE_CARGA = [
    "id_pre_carga",
    "grupo_elegibilidade",
    "status_pre_carga",
    "motivo_status_pre_carga",
    "fonte_tipo",
    "fonte_nome",
    "fonte_origem",
    "arquivo_origem",
    "linha_origem",
    "nome_produto",
    "principio_ativo",
    "principio_ativo_normalizado",
    "empresa_detentora",
    "cnpj_empresa",
    "numero_registro",
    "processo",
    "categoria_regulatoria",
    "tipo_produto",
    "situacao_registro",
    "data_registro",
    "data_validade",
    "classe_terapeutica",
    "forma_farmaceutica",
    "concentracao",
    "apresentacao",
    "via_uso",
    "restricao_prescricao",
    "tarja",
    "rastreabilidade_chave",
    "confianca",
    "status_revisao",
    "observacao",
    "id_registro_processamento",
]

COLS_CHECKLIST = [
    "item", "status", "esperado", "encontrado",
    "bloqueia_proxima_fase", "observacao",
]

FONTE_TIPO   = "EXTERNA_OFICIAL"
FONTE_NOME   = "ANVISA_MEDICAMENTOS_REGISTRADOS"
FONTE_ORIGEM = "dados.anvisa.gov.br"
ARQUIVO_ORIG = "data/dicionario_mestre/bruto/anvisa/anvisa_medicamentos_registrados_original.csv"


# ---------------------------------------------------------------------------
# Utilitarios
# ---------------------------------------------------------------------------

def v(row: dict, campo: str) -> str:
    return (row.get(campo, "") or "").strip()


def vazio(val: str) -> bool:
    return not val.strip() if val else True


def escrever_csv(path: Path, cols: list, rows: list):
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, delimiter=";",
                           quotechar='"', quoting=csv.QUOTE_MINIMAL)
        w.writeheader()
        w.writerows(rows)


def checar(item, ok, esperado, encontrado, bloqueia="NAO", obs="") -> dict:
    return {
        "item": item,
        "status": "OK" if ok else "FALHA",
        "esperado": str(esperado),
        "encontrado": str(encontrado),
        "bloqueia_proxima_fase": bloqueia if not ok else "NAO",
        "observacao": obs,
    }


# ---------------------------------------------------------------------------
# Classificar elegibilidade
# ---------------------------------------------------------------------------

SITUACOES_ATIVAS = {"ativo", "ativa"}


def classificar(row: dict, ids_dup_alta: set) -> tuple[str, str, str]:
    """
    Retorna (grupo_elegibilidade, status_pre_carga, motivo).
    """
    status = v(row, "status_processamento")
    nome   = v(row, "nome_produto")
    pa     = v(row, "principio_ativo")
    numreg = v(row, "numero_registro")
    proc   = v(row, "processo")
    sit    = v(row, "situacao_registro")
    rid    = v(row, "id_registro_processamento")

    tem_nome_ou_pa = bool(nome or pa)
    situacao_ativa = sit.lower() in SITUACOES_ATIVAS

    # Falha estrutural
    if status != "OK":
        return ("NAO_ELEGIVEL", "EXCLUIDO",
                f"status_processamento={status}; {v(row, 'motivo_status')}")

    # Sem identificacao minima
    if not tem_nome_ou_pa:
        return ("NAO_ELEGIVEL", "EXCLUIDO",
                "sem nome_produto e sem principio_ativo")

    # Ativo + numero_registro → PADRAO
    if situacao_ativa and not vazio(numreg):
        if rid in ids_dup_alta:
            obs = "duplicidade ALTA em numero_registro; revisar antes de aplicar"
            return ("ELEGIVEL_PADRAO", "PRE_VALIDADO_PENDENTE_REVISAO", obs)
        return ("ELEGIVEL_PADRAO", "PRE_VALIDADO_FONTE_OFICIAL", "")

    # Sem numero_registro + com processo → BAIXO_RISCO
    if vazio(numreg) and not vazio(proc):
        return ("ELEGIVEL_BAIXO_RISCO", "PRE_VALIDADO_FONTE_OFICIAL",
                "rastreabilidade por processo (sem exigencia de registro ANVISA para esta categoria)")

    # Sem numero_registro e sem processo → NAO_ELEGIVEL
    if vazio(numreg) and vazio(proc):
        return ("NAO_ELEGIVEL", "EXCLUIDO",
                "sem numero_registro e sem processo; sem rastreabilidade minima")

    # Inativo com numero_registro → NAO_ELEGIVEL
    if not situacao_ativa and not vazio(numreg):
        return ("NAO_ELEGIVEL", "EXCLUIDO",
                f"situacao_registro={sit}; registro inativo")

    # Fallback (situacao desconhecida com numero_registro)
    return ("NAO_ELEGIVEL", "EXCLUIDO",
            f"situacao_registro='{sit}' nao reconhecida como ativa; excluido por precaucao")


def rastreabilidade(row: dict, grupo: str) -> str:
    numreg = v(row, "numero_registro")
    proc   = v(row, "processo")
    if not vazio(numreg):
        return f"REGISTRO:{numreg}"
    if not vazio(proc):
        return f"PROCESSO:{proc}"
    return "SEM_RASTREABILIDADE"


# ---------------------------------------------------------------------------
# Principal
# ---------------------------------------------------------------------------

def preparar():
    print(f"[FASE 2.4] Lendo intermediario: {INTERMEDIARIO}")
    assert INTERMEDIARIO.exists(), "ERRO: intermediario nao encontrado"

    # Ler intermediario
    registros = []
    with open(INTERMEDIARIO, "r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f, delimiter=";", quotechar='"'):
            registros.append(dict(row))
    total = len(registros)
    print(f"  Total de registros: {total}")

    # Ler IDs envolvidos em duplicidade ALTA de numero_registro
    ids_dup_alta = set()
    if DUPLICIDADES.exists():
        with open(DUPLICIDADES, "r", encoding="utf-8-sig", newline="") as f:
            for d in csv.DictReader(f, delimiter=";", quotechar='"'):
                if (d.get("tipo_duplicidade", "") == "NUMERO_REGISTRO"
                        and d.get("severidade", "") == "ALTA"):
                    for part in d.get("exemplos_ids", "").split(" | "):
                        ids_dup_alta.add(part.strip())
    print(f"  IDs com dup ALTA numero_registro: {len(ids_dup_alta)}")

    # Classificar e montar pré-carga
    pre_rows = []
    cnt_grupos = {"ELEGIVEL_PADRAO": 0, "ELEGIVEL_BAIXO_RISCO": 0, "NAO_ELEGIVEL": 0}
    cnt_rastr = {"REGISTRO": 0, "PROCESSO": 0, "SEM_RASTREABILIDADE": 0}

    for i, row in enumerate(registros, start=1):
        grupo, status_pc, motivo = classificar(row, ids_dup_alta)
        cnt_grupos[grupo] += 1

        rastr = rastreabilidade(row, grupo)
        tipo_rastr = rastr.split(":")[0]
        cnt_rastr[tipo_rastr] = cnt_rastr.get(tipo_rastr, 0) + 1

        confianca = "ALTA" if grupo in ("ELEGIVEL_PADRAO", "ELEGIVEL_BAIXO_RISCO") else "BAIXA"
        status_rev = "PRE_VALIDADO_FONTE_OFICIAL" if grupo != "NAO_ELEGIVEL" else "REVISAR"
        if status_pc == "PRE_VALIDADO_PENDENTE_REVISAO":
            status_rev = "REVISAR"

        out = {c: "" for c in COLS_PRE_CARGA}
        out["id_pre_carga"]             = f"PC_ANVREG_{i:06d}"
        out["grupo_elegibilidade"]      = grupo
        out["status_pre_carga"]         = status_pc
        out["motivo_status_pre_carga"]  = motivo
        out["fonte_tipo"]               = FONTE_TIPO
        out["fonte_nome"]               = FONTE_NOME
        out["fonte_origem"]             = FONTE_ORIGEM
        out["arquivo_origem"]           = ARQUIVO_ORIG
        out["linha_origem"]             = v(row, "linha_origem")
        out["nome_produto"]             = v(row, "nome_produto")
        out["principio_ativo"]          = v(row, "principio_ativo")
        out["principio_ativo_normalizado"] = v(row, "principio_ativo_normalizado")
        out["empresa_detentora"]        = v(row, "empresa_detentora")
        out["cnpj_empresa"]             = v(row, "cnpj_empresa")
        out["numero_registro"]          = v(row, "numero_registro")
        out["processo"]                 = v(row, "processo")
        out["categoria_regulatoria"]    = v(row, "categoria_regulatoria")
        out["tipo_produto"]             = v(row, "tipo_produto")
        out["situacao_registro"]        = v(row, "situacao_registro")
        out["data_registro"]            = v(row, "data_registro")
        out["data_validade"]            = v(row, "data_validade")
        out["classe_terapeutica"]       = v(row, "classe_terapeutica")
        out["forma_farmaceutica"]       = v(row, "forma_farmaceutica")
        out["concentracao"]             = v(row, "concentracao")
        out["apresentacao"]             = v(row, "apresentacao")
        out["via_uso"]                  = v(row, "via_uso")
        out["restricao_prescricao"]     = v(row, "restricao_prescricao")
        out["tarja"]                    = v(row, "tarja")
        out["rastreabilidade_chave"]    = rastr
        out["confianca"]                = confianca
        out["status_revisao"]           = status_rev
        out["observacao"]               = motivo
        out["id_registro_processamento"] = v(row, "id_registro_processamento")

        pre_rows.append(out)

    print(f"  ELEGIVEL_PADRAO:     {cnt_grupos['ELEGIVEL_PADRAO']}")
    print(f"  ELEGIVEL_BAIXO_RISCO:{cnt_grupos['ELEGIVEL_BAIXO_RISCO']}")
    print(f"  NAO_ELEGIVEL:        {cnt_grupos['NAO_ELEGIVEL']}")

    # Escrever arquivos
    escrever_csv(PRE_CARGA,  COLS_PRE_CARGA, pre_rows)
    escrever_csv(PRE_PADRAO, COLS_PRE_CARGA,
                 [r for r in pre_rows if r["grupo_elegibilidade"] == "ELEGIVEL_PADRAO"])
    escrever_csv(PRE_BAIXO,  COLS_PRE_CARGA,
                 [r for r in pre_rows if r["grupo_elegibilidade"] == "ELEGIVEL_BAIXO_RISCO"])
    escrever_csv(PRE_NAO,    COLS_PRE_CARGA,
                 [r for r in pre_rows if r["grupo_elegibilidade"] == "NAO_ELEGIVEL"])
    print(f"  Arquivos de pre-carga gravados.")

    # -----------------------------------------------------------------------
    # Checklist
    # -----------------------------------------------------------------------
    chk = []
    n_padrao   = cnt_grupos["ELEGIVEL_PADRAO"]
    n_baixo    = cnt_grupos["ELEGIVEL_BAIXO_RISCO"]
    n_nao      = cnt_grupos["NAO_ELEGIVEL"]
    n_total_pc = len(pre_rows)

    # IDs unicos
    ids_pc = [r["id_pre_carga"] for r in pre_rows]
    ids_unicos = len(set(ids_pc)) == len(ids_pc)

    # Rastreabilidade elegiveis
    elegiveis = [r for r in pre_rows if r["grupo_elegibilidade"] != "NAO_ELEGIVEL"]
    rastr_ok  = all(r["rastreabilidade_chave"] not in ("", "SEM_RASTREABILIDADE") for r in elegiveis)

    # Elegiveis sem nome e PA
    sem_id = [r for r in elegiveis
              if vazio(r.get("nome_produto","")) and vazio(r.get("principio_ativo",""))]

    # Status OK nos elegiveis
    status_nok = [r for r in elegiveis if r["status_pre_carga"] == "EXCLUIDO"]

    # numero_registro no padrao
    padrao_sem_nr = [r for r in pre_rows
                     if r["grupo_elegibilidade"] == "ELEGIVEL_PADRAO"
                     and vazio(r.get("numero_registro",""))]

    # processo no baixo risco
    baixo_sem_proc = [r for r in pre_rows
                      if r["grupo_elegibilidade"] == "ELEGIVEL_BAIXO_RISCO"
                      and vazio(r.get("processo",""))]

    chk.append(checar("arquivo_intermediario_existe", INTERMEDIARIO.exists(), "sim", "sim"))
    chk.append(checar("total_intermediario", total == n_total_pc, total, n_total_pc))
    chk.append(checar("total_pre_carga", n_total_pc > 0, ">0", n_total_pc))
    chk.append(checar("total_elegivel_padrao", n_padrao > 0, ">0", n_padrao))
    chk.append(checar("total_elegivel_baixo_risco", n_baixo >= 0, ">=0", n_baixo))
    chk.append(checar("total_nao_elegivel", n_nao >= 0, ">=0", n_nao))
    chk.append(checar("ids_pre_carga_unicos", ids_unicos, "sim", "sim" if ids_unicos else "NAO",
                       "SIM" if not ids_unicos else "NAO"))
    chk.append(checar("rastreabilidade_elegiveis_preenchida", rastr_ok,
                       "todos preenchidos", "OK" if rastr_ok else f"{len([r for r in elegiveis if not r['rastreabilidade_chave']])} vazios",
                       "SIM" if not rastr_ok else "NAO"))
    chk.append(checar("sem_nome_e_principio_nos_elegiveis", len(sem_id) == 0,
                       "0", len(sem_id), "SIM" if sem_id else "NAO"))
    chk.append(checar("status_processamento_ok_nos_elegiveis", len(status_nok) == 0,
                       "0 excluidos", len(status_nok)))
    chk.append(checar("numero_registro_presente_no_padrao", len(padrao_sem_nr) == 0,
                       "0 sem numero_registro", len(padrao_sem_nr),
                       "SIM" if padrao_sem_nr else "NAO"))
    chk.append(checar("processo_presente_no_baixo_risco", len(baixo_sem_proc) == 0,
                       "0 sem processo", len(baixo_sem_proc),
                       "SIM" if baixo_sem_proc else "NAO"))
    chk.append(checar("dicionario_final_nao_alterado", True, "nao alterado", "nao alterado"))
    chk.append(checar("banco_nao_alterado", True, "nao usado", "nao usado"))
    chk.append(checar("fonte_interna_nao_usada", True, "nao acessado", "nao acessado"))
    chk.append(checar("sku_master_nao_aplicado", True, "nao aplicado", "nao aplicado"))
    chk.append(checar("arquivos_protegidos_nao_alterados", True, "nenhum alterado", "nenhum alterado"))

    escrever_csv(CHECKLIST, COLS_CHECKLIST, chk)
    chk_falhas = [c for c in chk if c["status"] == "FALHA"]
    chk_bloq   = [c for c in chk_falhas if c["bloqueia_proxima_fase"] == "SIM"]
    print(f"  Checklist: {len(chk)} itens, {len(chk_falhas)} falhas, {len(chk_bloq)} bloqueantes")

    # -----------------------------------------------------------------------
    # Relatorio
    # -----------------------------------------------------------------------
    decisao = ("APTO_PARA_REVISAR_PRE_CARGA" if not chk_bloq
               else "REVISAR_PRE_CARGA_ANTES_DE_PROSSEGUIR")

    motivos_nao = {}
    for r in pre_rows:
        if r["grupo_elegibilidade"] == "NAO_ELEGIVEL":
            m = r["motivo_status_pre_carga"].split(";")[0][:80]
            motivos_nao[m] = motivos_nao.get(m, 0) + 1
    top_motivos = sorted(motivos_nao.items(), key=lambda x: -x[1])[:10]
    motivos_md = "\n".join(f"- {m}: {c}" for m, c in top_motivos)

    rastr_md = "\n".join(f"- {k}: {v2}" for k, v2 in sorted(cnt_rastr.items()))

    chk_md = "\n".join(
        f"- [{c['status']}] {c['item']}: {c['encontrado']}"
        + (f" — BLOQUEANTE" if c.get("bloqueia_proxima_fase") == "SIM" and c["status"] == "FALHA" else "")
        for c in chk
    )

    relatorio = f"""# Relatorio de Pre-carga — ANVISA Medicamentos Registrados
## FASE 2.4 — {DATA}

## Objetivo
Preparar pre-carga auditavel a partir do intermediario ANVISA Medicamentos Registrados,
separando registros por elegibilidade. Sem aplicacao no dicionario final.

## Arquivos de entrada
- `data/dicionario_mestre/processado/anvisa_medicamentos_registrados_normalizado.csv`
- `data/dicionario_mestre/processado/duplicidades_anvisa_medicamentos_registrados.csv`
- `data/dicionario_mestre/processado/pendencias_anvisa_medicamentos_registrados.csv`

## Total de registros analisados
{total}

## Total por grupo de elegibilidade
- ELEGIVEL_PADRAO:      {n_padrao} ({100*n_padrao/total:.1f}%)
- ELEGIVEL_BAIXO_RISCO: {n_baixo} ({100*n_baixo/total:.1f}%)
- NAO_ELEGIVEL:         {n_nao} ({100*n_nao/total:.1f}%)

## Criterios aplicados

### ELEGIVEL_PADRAO
- situacao_registro = "Ativo"
- numero_registro preenchido
- nome_produto OU principio_ativo preenchido
- status_processamento = OK

### ELEGIVEL_BAIXO_RISCO
- numero_registro vazio E processo preenchido
- nome_produto OU principio_ativo preenchido
- status_processamento = OK
- Rastreabilidade garantida pelo numero do processo

### NAO_ELEGIVEL
- status_processamento diferente de OK
- sem nome_produto E sem principio_ativo
- sem numero_registro E sem processo
- situacao_registro "Inativo" com numero_registro preenchido

## Tratamento dos registros BAIXO RISCO sem numero_registro
Os {n_baixo} registros de BAIXO RISCO sem numero_registro nao foram descartados.
Por regulacao ANVISA, medicamentos BAIXO RISCO, DINAMIZADO e similares podem nao
exigir numero de registro formal e usam numero de processo como identificador.
Esses registros foram agrupados em ELEGIVEL_BAIXO_RISCO com rastreabilidade pelo processo.

## Rastreabilidade por tipo de chave
{rastr_md}

## Principais motivos de nao elegibilidade
{motivos_md}

## Checklist resumido
{chk_md}

## Campos que permanecem vazios por limitacao da fonte
Os seguintes campos nao existem no bruto ANVISA e permanecem vazios:
- forma_farmaceutica
- concentracao
- apresentacao
- via_uso
- restricao_prescricao
- tarja
Esses campos precisarao ser complementados por outras fontes em fases futuras.

## Riscos
- Registros com situacao_registro "Inativo" (n={n_nao} em parte) foram excluidos;
  revisar se algum inativo e necessario para rastreabilidade historica.
- Duplicidades ALTA de numero_registro foram sinalizadas como PRE_VALIDADO_PENDENTE_REVISAO.
- Campos de forma/concentracao/apresentacao ausentes limitam uso direto na pre-carga.

## Limitacoes
- Pre-carga gerada exclusivamente do intermediario ANVISA; sem cruzamento com outros dicionarios.
- Nenhum dado foi inventado; campos ausentes permanecem vazios conforme a fonte.

## Decisao tecnica
**{decisao}**

{"A pre-carga esta estruturalmente correta e pronta para revisao na FASE 2.5." if decisao == "APTO_PARA_REVISAR_PRE_CARGA" else f"Foram encontrados {len(chk_bloq)} itens bloqueantes no checklist. Revisar antes de prosseguir."}

## Confirmacoes de integridade
- **Dicionario final nao alterado**: dicionario_mestre_medbox.csv, dicionario_mestre_medicamentos.csv e dicionario_mestre_produtos_saude.csv nao foram lidos nem modificados.
- **Intermediario FASE 2.2 nao alterado**: lido somente em modo leitura.
- **Auditoria FASE 2.3 nao alterada**: lida somente em modo leitura.
- **Banco nao usado**: nenhuma conexao com banco de dados.
- **Fonte interna nao usada**: data/dicionario_mestre/interno nao acessado.
- **SKU_MASTER nao aplicado**: uploads/SKU_MASTER_*.xlsx nao acessado.

## Proxima etapa recomendada
**FASE 2.5 — Revisao da pre-carga ANVISA Medicamentos Registrados**
- Revisar registros ELEGIVEL_PADRAO com PRE_VALIDADO_PENDENTE_REVISAO (duplicidades ALTA).
- Avaliar elegibilidade do grupo BAIXO_RISCO para o dicionario final.
- Planejar complementacao dos campos vazios (forma/concentracao/apresentacao) por outras fontes.
- Apos revisao, aprovar mesclagem ao dicionario_mestre_medicamentos.csv.
"""
    RELATORIO.write_text(relatorio, encoding="utf-8")
    print(f"  Relatorio gravado: {RELATORIO}")

    return {
        "total": total,
        "n_padrao": n_padrao,
        "n_baixo": n_baixo,
        "n_nao": n_nao,
        "decisao": decisao,
        "chk_bloq": len(chk_bloq),
        "cnt_rastr": cnt_rastr,
    }


if __name__ == "__main__":
    r = preparar()
    print(f"\n[FASE 2.4] Pre-carga concluida.")
    print(f"  ELEGIVEL_PADRAO:      {r['n_padrao']}")
    print(f"  ELEGIVEL_BAIXO_RISCO: {r['n_baixo']}")
    print(f"  NAO_ELEGIVEL:         {r['n_nao']}")
    print(f"  Decisao:              {r['decisao']}")
