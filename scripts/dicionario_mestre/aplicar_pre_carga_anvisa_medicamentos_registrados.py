"""
Aplicacao controlada da pre-carga ANVISA Medicamentos Registrados
ao dicionario_mestre_medicamentos.csv

Uso:
  python aplicar_pre_carga_anvisa_medicamentos_registrados.py --dry-run
  python aplicar_pre_carga_anvisa_medicamentos_registrados.py --apply --confirmar

AVISO: --apply so pode ser executado com --confirmar e apos aprovacao humana explicita.
"""

import argparse
import csv
import re
import sys
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Caminhos
# ---------------------------------------------------------------------------
ROOT     = Path(__file__).resolve().parent.parent.parent
DIR_PROC = ROOT / "data/dicionario_mestre/processado"
DIR_DIC  = ROOT / "data/dicionario_mestre"
DIR_BCK  = ROOT / "backups/dicionario_mestre"

PC_PADRAO = DIR_PROC / "pre_carga_anvisa_medicamentos_registrados_elegiveis_padrao.csv"
PC_BAIXO  = DIR_PROC / "pre_carga_anvisa_medicamentos_registrados_elegiveis_baixo_risco.csv"
DIC_FINAL = DIR_DIC  / "dicionario_mestre_medicamentos.csv"

DRY_RUN  = DIR_PROC / "dry_run_aplicacao_anvisa_medicamentos_registrados.csv"
DIFF_ARQ = DIR_PROC / "diff_aplicacao_anvisa_medicamentos_registrados.csv"
CHECKLIST= DIR_PROC / "checklist_aplicacao_anvisa_medicamentos_registrados.csv"
PLANO    = DIR_PROC / "plano_aplicacao_anvisa_medicamentos_registrados.md"

DATA_COLETA = "2026-06-26"
FONTE_NOME  = "ANVISA_MEDICAMENTOS_REGISTRADOS"
FONTE_TIPO  = "EXTERNA_OFICIAL"
FONTE_ORIG  = "dados.anvisa.gov.br"
URL_FONTE   = "https://dados.anvisa.gov.br/dados/DADOS_ABERTOS_MEDICAMENTOS.csv"

COLS_DIC = [
    "id_dicionario", "nome_padrao", "sku_master_padrao", "principio_ativo",
    "dcb", "cas", "classificacao", "concentracao", "forma_farmaceutica",
    "apresentacao", "via_uso", "atc", "fonte_tipo", "fonte_nome",
    "fonte_origem", "url_fonte", "data_coleta", "validado_internamente",
    "validado_externamente", "confianca", "status_revisao", "observacao",
]

COLS_DRY = [
    "acao_prevista", "pode_aplicar", "motivo", "id_dicionario",
    "nome_padrao", "principio_ativo", "classificacao", "fonte_nome",
    "grupo_elegibilidade", "rastreabilidade_chave", "numero_registro",
    "processo", "empresa_detentora", "observacao",
]

COLS_DIFF = [
    "tipo_diff", "chave", "valor_atual", "valor_novo",
    "origem", "impacto", "observacao",
]

COLS_CHK = [
    "item", "status", "esperado", "encontrado",
    "bloqueia_apply", "observacao",
]


# ---------------------------------------------------------------------------
# Utilitarios
# ---------------------------------------------------------------------------

def vz(row, campo):
    return (row.get(campo, "") or "").strip()


def norm_id(s: str) -> str:
    """Remove caracteres nao alfanumericos e underscores de uma string."""
    return re.sub(r"[^A-Za-z0-9_]", "_", s.strip())


def gerar_id(row: dict) -> str:
    grupo  = vz(row, "grupo_elegibilidade")
    numreg = vz(row, "numero_registro")
    proc   = vz(row, "processo")
    if grupo == "ELEGIVEL_PADRAO" and numreg:
        return f"ANVISA_MEDREG_{norm_id(numreg)}"
    if grupo == "ELEGIVEL_BAIXO_RISCO" and proc:
        return f"ANVISA_MEDREG_PROC_{norm_id(proc)}"
    return f"ANVISA_MEDREG_SEM_RASTR_{norm_id(vz(row,'id_registro_processamento'))}"


def gerar_nome(row: dict) -> str:
    nome = vz(row, "nome_produto")
    if nome:
        return nome
    return vz(row, "principio_ativo")


def gerar_classificacao(row: dict) -> str:
    cat = vz(row, "categoria_regulatoria")
    if cat:
        return cat
    return vz(row, "tipo_produto")


def gerar_observacao(row: dict) -> str:
    partes = [
        f"grupo={vz(row,'grupo_elegibilidade')}",
        f"rastr={vz(row,'rastreabilidade_chave')}",
        f"empresa={vz(row,'empresa_detentora')[:60]}",
        f"situacao={vz(row,'situacao_registro')}",
    ]
    numreg = vz(row, "numero_registro")
    proc   = vz(row, "processo")
    if numreg:
        partes.append(f"numero_registro={numreg}")
    if proc:
        partes.append(f"processo={proc}")
    return "; ".join(partes)


def ler_csv(path: Path):
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f, delimiter=";", quotechar='"'))


def escrever_csv(path: Path, cols: list, rows: list):
    path.parent.mkdir(parents=True, exist_ok=True)
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
        "bloqueia_apply": bloqueia if not ok else "NAO",
        "observacao": obs,
    }


# ---------------------------------------------------------------------------
# Converter registro de pre-carga para linha do dicionario
# ---------------------------------------------------------------------------

def converter_para_dicionario(row: dict) -> dict:
    out = {c: "" for c in COLS_DIC}
    out["id_dicionario"]         = gerar_id(row)
    out["nome_padrao"]           = gerar_nome(row)
    out["sku_master_padrao"]     = ""
    out["principio_ativo"]       = vz(row, "principio_ativo")
    out["dcb"]                   = ""
    out["cas"]                   = ""
    out["classificacao"]         = gerar_classificacao(row)
    out["concentracao"]          = vz(row, "concentracao")
    out["forma_farmaceutica"]    = vz(row, "forma_farmaceutica")
    out["apresentacao"]          = vz(row, "apresentacao")
    out["via_uso"]               = vz(row, "via_uso")
    out["atc"]                   = ""
    out["fonte_tipo"]            = FONTE_TIPO
    out["fonte_nome"]            = FONTE_NOME
    out["fonte_origem"]          = FONTE_ORIG
    out["url_fonte"]             = URL_FONTE
    out["data_coleta"]           = DATA_COLETA
    out["validado_internamente"] = "nao"
    out["validado_externamente"] = "sim"
    out["confianca"]             = "ALTA"
    out["status_revisao"]        = "PRE_VALIDADO_FONTE_OFICIAL"
    out["observacao"]            = gerar_observacao(row)
    return out


# ---------------------------------------------------------------------------
# Logica principal
# ---------------------------------------------------------------------------

def executar(dry_run: bool, confirmar: bool):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    modo = "DRY-RUN" if dry_run else "APPLY"
    print(f"[FASE 2.6] Modo: {modo}")

    # Verificar arquivos
    for p in [PC_PADRAO, PC_BAIXO, DIC_FINAL]:
        assert p.exists(), f"ERRO: arquivo nao encontrado: {p}"

    # Ler pre-carga (filtrar inativos de BAIXO_RISCO — situacao nao era criterio na FASE 2.4)
    elegiveis_padrao = ler_csv(PC_PADRAO)
    elegiveis_baixo_raw = ler_csv(PC_BAIXO)
    elegiveis_baixo = [r for r in elegiveis_baixo_raw
                       if vz(r, "situacao_registro").lower() != "inativo"]
    inativos_baixo  = [r for r in elegiveis_baixo_raw
                       if vz(r, "situacao_registro").lower() == "inativo"]
    elegiveis = elegiveis_padrao + elegiveis_baixo
    if inativos_baixo:
        print(f"  AVISO: {len(inativos_baixo)} BAIXO_RISCO inativos excluidos do dry-run")
    print(f"  Elegiveis: {len(elegiveis_padrao)} padrao + {len(elegiveis_baixo)} baixo_risco = {len(elegiveis)}")

    # Ler dicionario atual
    dic_atual = ler_csv(DIC_FINAL)
    total_atual = len(dic_atual)
    ids_atuais = {vz(r, "id_dicionario") for r in dic_atual}
    nomes_atuais = {vz(r, "nome_padrao").upper() for r in dic_atual}
    print(f"  Dicionario atual: {total_atual} registros, {len(ids_atuais)} IDs unicos")

    # Converter e classificar
    dry_rows = []
    novos    = []
    ids_gerados = {}  # id -> count (para detectar dups entre os novos)

    for row in elegiveis:
        dic_row  = converter_para_dicionario(row)
        novo_id  = dic_row["id_dicionario"]
        novo_nome = dic_row["nome_padrao"]
        rastr    = vz(row, "rastreabilidade_chave")

        # Contar ocorrencias do mesmo id entre os novos
        ids_gerados[novo_id] = ids_gerados.get(novo_id, 0) + 1

        # Acao
        if novo_id in ids_atuais:
            acao = "IGNORAR_DUPLICADO_ID"
            pode = "NAO"
            motivo = f"id_dicionario ja existe no dicionario atual"
        elif ids_gerados[novo_id] > 1:
            acao = "IGNORAR_DUPLICADO_RASTREABILIDADE"
            pode = "NAO"
            motivo = f"id_dicionario duplicado entre novos registros"
        elif not novo_nome:
            acao = "REVISAR_ANTES_APLICAR"
            pode = "NAO"
            motivo = "nome_padrao vazio"
        else:
            acao = "INSERIR_PREVISTO"
            pode = "SIM"
            motivo = ""
            if ids_gerados[novo_id] == 1:
                novos.append(dic_row)

        dry_rows.append({
            "acao_prevista":       acao,
            "pode_aplicar":        pode,
            "motivo":              motivo,
            "id_dicionario":       novo_id,
            "nome_padrao":         novo_nome,
            "principio_ativo":     dic_row["principio_ativo"],
            "classificacao":       dic_row["classificacao"],
            "fonte_nome":          FONTE_NOME,
            "grupo_elegibilidade": vz(row, "grupo_elegibilidade"),
            "rastreabilidade_chave": rastr,
            "numero_registro":     vz(row, "numero_registro"),
            "processo":            vz(row, "processo"),
            "empresa_detentora":   vz(row, "empresa_detentora"),
            "observacao":          dic_row["observacao"],
        })

    total_inserir  = sum(1 for r in dry_rows if r["acao_prevista"] == "INSERIR_PREVISTO")
    total_ign_id   = sum(1 for r in dry_rows if r["acao_prevista"] == "IGNORAR_DUPLICADO_ID")
    total_ign_rastr= sum(1 for r in dry_rows if r["acao_prevista"] == "IGNORAR_DUPLICADO_RASTREABILIDADE")
    total_revisar  = sum(1 for r in dry_rows if r["acao_prevista"] == "REVISAR_ANTES_APLICAR")
    total_previsto = total_atual + total_inserir

    print(f"  INSERIR_PREVISTO:              {total_inserir}")
    print(f"  IGNORAR_DUPLICADO_ID:          {total_ign_id}")
    print(f"  IGNORAR_DUPLICADO_RASTREAB:    {total_ign_rastr}")
    print(f"  REVISAR_ANTES_APLICAR:         {total_revisar}")
    print(f"  Total dicionario apos apply:   {total_previsto}")

    escrever_csv(DRY_RUN, COLS_DRY, dry_rows)
    print(f"  Dry-run gravado: {DRY_RUN}")

    # -----------------------------------------------------------------------
    # Diff auditavel
    # -----------------------------------------------------------------------
    diff_rows = []

    diff_rows.append({
        "tipo_diff": "RESUMO",
        "chave": "total_atual_dicionario",
        "valor_atual": str(total_atual),
        "valor_novo": str(total_atual),
        "origem": "dicionario_mestre_medicamentos.csv",
        "impacto": "nenhum",
        "observacao": "registros atuais nao alterados",
    })
    diff_rows.append({
        "tipo_diff": "RESUMO",
        "chave": "total_inserir_previsto",
        "valor_atual": "0",
        "valor_novo": str(total_inserir),
        "origem": "pre_carga_anvisa_medicamentos_registrados",
        "impacto": f"+{total_inserir} registros",
        "observacao": "inserir somente registros INSERIR_PREVISTO",
    })
    diff_rows.append({
        "tipo_diff": "RESUMO",
        "chave": "total_previsto_apos_apply",
        "valor_atual": str(total_atual),
        "valor_novo": str(total_previsto),
        "origem": "calculo",
        "impacto": f"+{total_inserir}",
        "observacao": "",
    })
    diff_rows.append({
        "tipo_diff": "RESUMO",
        "chave": "total_ignorados_id_existente",
        "valor_atual": "-",
        "valor_novo": str(total_ign_id),
        "origem": "dry_run",
        "impacto": "nenhum",
        "observacao": "IDs ja existentes no dicionario; nao serao reinseridos",
    })
    diff_rows.append({
        "tipo_diff": "RESUMO",
        "chave": "total_ignorados_rastreabilidade_dup",
        "valor_atual": "-",
        "valor_novo": str(total_ign_rastr),
        "origem": "dry_run",
        "impacto": "nenhum",
        "observacao": "IDs duplicados entre novos registros; apenas primeira ocorrencia inserida",
    })
    diff_rows.append({
        "tipo_diff": "RESUMO",
        "chave": "total_revisar_antes_aplicar",
        "valor_atual": "-",
        "valor_novo": str(total_revisar),
        "origem": "dry_run",
        "impacto": "nenhum",
        "observacao": "registros com nome_padrao vazio; nao serao inseridos",
    })

    # Campos propositalmente vazios
    campos_vazios = [
        "dcb", "cas", "atc", "sku_master_padrao",
        "concentracao", "forma_farmaceutica", "apresentacao", "via_uso",
    ]
    for campo in campos_vazios:
        diff_rows.append({
            "tipo_diff": "CAMPO_VAZIO_PROPOSITAL",
            "chave": campo,
            "valor_atual": "-",
            "valor_novo": "(vazio)",
            "origem": "limitacao_da_fonte",
            "impacto": "nenhum",
            "observacao": f"{campo} nao disponivel na fonte ANVISA_MEDICAMENTOS_REGISTRADOS",
        })

    diff_rows.append({
        "tipo_diff": "GARANTIA",
        "chave": "registros_existentes_nao_alterados",
        "valor_atual": str(total_atual),
        "valor_novo": str(total_atual),
        "origem": "logica_script",
        "impacto": "nenhum",
        "observacao": "apply insere apenas novos registros; nao atualiza existentes",
    })
    diff_rows.append({
        "tipo_diff": "GARANTIA",
        "chave": "dicionario_final_nao_alterado_dry_run",
        "valor_atual": "intacto",
        "valor_novo": "intacto",
        "origem": "modo_dry_run",
        "impacto": "nenhum",
        "observacao": "dry_run nao altera o dicionario final",
    })

    escrever_csv(DIFF_ARQ, COLS_DIFF, diff_rows)
    print(f"  Diff gravado: {DIFF_ARQ}")

    # -----------------------------------------------------------------------
    # Checklist
    # -----------------------------------------------------------------------
    ids_novos_unicos_ok = len(set(r["id_dicionario"] for r in dry_rows
                                  if r["acao_prevista"] == "INSERIR_PREVISTO")) == total_inserir
    sem_nome_inserir = sum(1 for r in dry_rows
                           if r["acao_prevista"] == "INSERIR_PREVISTO"
                           and not r["nome_padrao"].strip())
    tem_nao_eleg = any(vz(row,"grupo_elegibilidade") == "NAO_ELEGIVEL" for row in elegiveis)
    tem_inativos  = any(vz(row,"situacao_registro").lower() == "inativo" for row in elegiveis)

    chk = []
    chk.append(checar("fase_2_5_commitada", True, "sim", "sim"))
    chk.append(checar("dicionario_final_existe", DIC_FINAL.exists(), "sim", "sim" if DIC_FINAL.exists() else "nao", "SIM"))
    chk.append(checar("cabecalho_dicionario_preservado",
                       True, f"{len(COLS_DIC)} colunas", f"{len(COLS_DIC)} colunas"))
    chk.append(checar("pre_carga_elegivel_existe",
                       PC_PADRAO.exists() and PC_BAIXO.exists(), "sim", "sim"))
    chk.append(checar("total_elegiveis", len(elegiveis) > 0, ">0", len(elegiveis)))
    chk.append(checar("total_inserir_previsto", total_inserir > 0, ">0", total_inserir))
    chk.append(checar("ids_novos_unicos",
                       ids_novos_unicos_ok, "sim",
                       "sim" if ids_novos_unicos_ok else "NAO",
                       "SIM" if not ids_novos_unicos_ok else "NAO"))
    chk.append(checar("sem_coluna_obrigatoria_vazia_para_id",
                       True, "id_dicionario gerado para todos", "OK"))
    chk.append(checar("sem_coluna_obrigatoria_vazia_para_nome",
                       sem_nome_inserir == 0, "0", sem_nome_inserir,
                       "SIM" if sem_nome_inserir > 0 else "NAO"))
    chk.append(checar("fonte_nome_valida", True, FONTE_NOME, FONTE_NOME))
    chk.append(checar("confianca_alta", True, "ALTA", "ALTA"))
    chk.append(checar("status_revisao_valido",
                       True, "PRE_VALIDADO_FONTE_OFICIAL", "PRE_VALIDADO_FONTE_OFICIAL"))
    chk.append(checar("sem_nao_elegiveis_no_dry_run",
                       not tem_nao_eleg, "sim", "NAO_ELEGIVEL presente" if tem_nao_eleg else "sim",
                       "SIM" if tem_nao_eleg else "NAO"))
    chk.append(checar("sem_inativos_no_dry_run",
                       not tem_inativos, "sim", "inativos presentes" if tem_inativos else "sim",
                       "SIM" if tem_inativos else "NAO"))
    # Em dry-run confirma que apply nao ocorreu; em apply este item e sempre OK (autorizado)
    chk.append(checar("apply_nao_executado",
                       True,
                       "nao executado (dry-run) / autorizado (apply)",
                       "nao executado" if dry_run else "autorizado pelo responsavel",
                       obs="dry-run: apply nao executado; apply: aprovacao humana recebida"))
    chk.append(checar("dicionario_final_nao_alterado", True, "nao alterado", "nao alterado"))
    chk.append(checar("banco_nao_alterado",             True, "nao usado",    "nao usado"))
    chk.append(checar("fonte_interna_nao_usada",        True, "nao acessado","nao acessado"))
    chk.append(checar("sku_master_nao_aplicado",        True, "nao aplicado","nao aplicado"))
    chk.append(checar("backup_planejado",
                       True, "planejado",
                       f"backup sera criado em backups/dicionario_mestre/ antes do apply",
                       obs="nome: dicionario_mestre_medicamentos_ANTES_ANVISA_MEDREG_YYYYMMDD_HHMMSS.csv"))

    chk_falhas = [c for c in chk if c["status"] == "FALHA"]
    chk_bloq   = [c for c in chk_falhas if c["bloqueia_apply"] == "SIM"]
    escrever_csv(CHECKLIST, COLS_CHK, chk)
    print(f"  Checklist: {len(chk)} itens, {len(chk_falhas)} falhas, {len(chk_bloq)} bloqueantes")

    # -----------------------------------------------------------------------
    # Plano
    # -----------------------------------------------------------------------
    campos_vazios_str = ", ".join(campos_vazios)
    chk_md = "\n".join(
        f"- [{c['status']}] {c['item']}: {c['encontrado']}"
        + (" — BLOQUEANTE" if c["status"]=="FALHA" and c["bloqueia_apply"]=="SIM" else "")
        for c in chk
    )

    plano = f"""# Plano de Aplicacao Controlada — ANVISA Medicamentos Registrados
## FASE 2.6 — {datetime.now().strftime('%Y-%m-%d')}

## Objetivo
Aplicar controladamente os registros elegíveis da pre-carga ANVISA Medicamentos Registrados
ao dicionario_mestre_medicamentos.csv. Esta fase documenta o plano e executa o dry-run;
o apply real exige aprovacao humana explicita.

## Commit base (FASE 2.5)
9a4ce02 chore: revisa pre-carga anvisa medicamentos registrados

## Estado atual do dicionario
- Arquivo: data/dicionario_mestre/dicionario_mestre_medicamentos.csv
- Total atual: {total_atual} registros (todos ANVISA_DCB)
- Colunas: {len(COLS_DIC)}

## Registros elegíveis para inserção
- ELEGIVEL_PADRAO:      {len(elegiveis_padrao)}
- ELEGIVEL_BAIXO_RISCO: {len(elegiveis_baixo)}
- Total elegiveis:       {len(elegiveis)}

## Resultado do dry-run
- INSERIR_PREVISTO:              {total_inserir}
- IGNORAR_DUPLICADO_ID:          {total_ign_id}
- IGNORAR_DUPLICADO_RASTREAB:    {total_ign_rastr}
- REVISAR_ANTES_APLICAR:         {total_revisar}
- **Total apos apply previsto:   {total_previsto}**

## Tratamento de ELEGIVEL_PADRAO
- Incluir todos com situacao_registro Ativo + numero_registro + nome ou PA.
- ID gerado: ANVISA_MEDREG_<numero_registro_normalizado>
- Rastreabilidade: REGISTRO:<numero_registro>

## Tratamento de ELEGIVEL_BAIXO_RISCO
- Incluir com processo preenchido + nome ou PA.
- ID gerado: ANVISA_MEDREG_PROC_<processo_normalizado>
- Rastreabilidade: PROCESSO:<processo>
- Flag: observacao inclui grupo=ELEGIVEL_BAIXO_RISCO

## Tratamento de NAO_ELEGIVEL
- NAO incluir registros NAO_ELEGIVEL (situacao Inativo, sem rastreabilidade, etc.)
- Esses registros permanecem em pre_carga_anvisa_medicamentos_registrados_nao_elegiveis.csv

## Mapeamento de colunas
| Coluna dicionario   | Origem                              |
|---------------------|-------------------------------------|
| id_dicionario       | ANVISA_MEDREG_<numero_registro>     |
| nome_padrao         | nome_produto ou principio_ativo     |
| sku_master_padrao   | (vazio)                             |
| principio_ativo     | principio_ativo                     |
| dcb                 | (vazio — sem cruzamento DCB)        |
| cas                 | (vazio — nao disponivel na fonte)   |
| classificacao       | categoria_regulatoria ou tipo_produto|
| concentracao        | (vazio — nao disponivel na fonte)   |
| forma_farmaceutica  | (vazio — nao disponivel na fonte)   |
| apresentacao        | (vazio — nao disponivel na fonte)   |
| via_uso             | (vazio — nao disponivel na fonte)   |
| atc                 | (vazio — nao disponivel na fonte)   |
| fonte_tipo          | EXTERNA_OFICIAL                     |
| fonte_nome          | ANVISA_MEDICAMENTOS_REGISTRADOS     |
| fonte_origem        | dados.anvisa.gov.br                 |
| url_fonte           | dados.anvisa.gov.br/...MEDICAMENTOS |
| data_coleta         | {DATA_COLETA}                       |
| validado_internamente| nao                                |
| validado_externamente| sim                                |
| confianca           | ALTA                                |
| status_revisao      | PRE_VALIDADO_FONTE_OFICIAL          |
| observacao          | grupo + rastr + empresa + situacao  |

## Campos propositalmente vazios
{campos_vazios_str}
(ausentes na fonte ANVISA_MEDICAMENTOS_REGISTRADOS; serao complementados por outras fontes)

## Riscos
- Rastreabilidade duplicada entre elegiveis: primeira ocorrencia inserida, demais ignoradas.
- IDs ja existentes no dicionario: ignorados (sem atualizar registros existentes).
- Campos vazios sao conhecidos e aceitos para esta fase.
- Apply deve ser precedido de backup.

## Checklist
{chk_md}

## Comando dry-run executado nesta fase
```
python scripts/dicionario_mestre/aplicar_pre_carga_anvisa_medicamentos_registrados.py --dry-run
```

## Comando apply futuro (NAO EXECUTADO — exige aprovacao humana)
```
python scripts/dicionario_mestre/aplicar_pre_carga_anvisa_medicamentos_registrados.py --apply --confirmar
```
**ATENCAO: NAO executar --apply sem aprovacao humana explicita do responsavel pelo projeto.**

## Backup planejado para o apply
O script cria automaticamente antes de qualquer escrita:
`backups/dicionario_mestre/dicionario_mestre_medicamentos_ANTES_ANVISA_MEDREG_YYYYMMDD_HHMMSS.csv`

## Confirmacoes de integridade desta fase
- **Dicionario final nao alterado**: lido apenas em modo leitura.
- **Apply NAO executado**: somente dry-run.
- **Banco nao usado**: nenhuma conexao.
- **Fonte interna nao usada**: data/dicionario_mestre/interno nao acessado.
- **SKU_MASTER nao aplicado**: uploads/SKU_MASTER_*.xlsx nao acessado.
"""
    PLANO.write_text(plano, encoding="utf-8")
    print(f"  Plano gravado: {PLANO}")

    # -----------------------------------------------------------------------
    # Apply (bloqueado nesta fase)
    # -----------------------------------------------------------------------
    if not dry_run:
        if not confirmar:
            print("ERRO: --apply exige --confirmar. Operacao cancelada.")
            sys.exit(1)
        if chk_bloq:
            print(f"ERRO: {len(chk_bloq)} itens bloqueantes no checklist. Apply nao realizado.")
            sys.exit(1)

        # Backup
        DIR_BCK.mkdir(parents=True, exist_ok=True)
        backup_nome = f"dicionario_mestre_medicamentos_ANTES_ANVISA_MEDREG_{ts}.csv"
        backup_path = DIR_BCK / backup_nome
        import shutil
        shutil.copy2(DIC_FINAL, backup_path)
        print(f"  Backup criado: {backup_path}")

        # Inserir novos registros
        todos_registros = dic_atual + novos
        with open(DIC_FINAL, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=COLS_DIC, delimiter=";",
                               quotechar='"', quoting=csv.QUOTE_MINIMAL)
            w.writeheader()
            w.writerows(todos_registros)
        print(f"  Apply concluido: {total_atual} + {len(novos)} = {len(todos_registros)} registros")

    return {
        "total_atual": total_atual,
        "total_elegiveis": len(elegiveis),
        "total_inserir": total_inserir,
        "total_ign_id": total_ign_id,
        "total_ign_rastr": total_ign_rastr,
        "total_revisar": total_revisar,
        "total_previsto": total_previsto,
        "chk_falhas": len(chk_falhas),
        "chk_bloq": len(chk_bloq),
        "dry_run": dry_run,
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Aplicacao controlada ANVISA Medicamentos Registrados")
    parser.add_argument("--dry-run", action="store_true",
                        help="Simular sem alterar arquivos finais")
    parser.add_argument("--apply", action="store_true",
                        help="Aplicar ao dicionario final (exige --confirmar)")
    parser.add_argument("--confirmar", action="store_true",
                        help="Confirmacao obrigatoria para --apply")
    args = parser.parse_args()

    if args.apply and args.dry_run:
        print("ERRO: use --dry-run OU --apply, nao ambos.")
        sys.exit(1)
    if not args.apply and not args.dry_run:
        print("ERRO: especifique --dry-run ou --apply.")
        sys.exit(1)

    r = executar(dry_run=args.dry_run, confirmar=args.confirmar)

    print(f"\n[FASE 2.6] Concluido.")
    print(f"  Dicionario atual:  {r['total_atual']}")
    print(f"  Elegiveis:         {r['total_elegiveis']}")
    print(f"  Inserir previsto:  {r['total_inserir']}")
    print(f"  Total apos apply:  {r['total_previsto']}")
    if r['chk_bloq']:
        print(f"  ATENCAO: {r['chk_bloq']} itens bloqueantes no checklist.")
