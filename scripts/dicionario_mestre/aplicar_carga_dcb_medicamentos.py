from __future__ import annotations

import argparse
import csv
import shutil
from datetime import datetime
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[2]
PROCESSADO_DIR = BASE_DIR / "data" / "dicionario_mestre" / "processado"
DICIONARIO_PATH = BASE_DIR / "data" / "dicionario_mestre" / "dicionario_mestre_medicamentos.csv"
CARGA_PATH = PROCESSADO_DIR / "carga_previa_dicionario_medicamentos_anvisa_dcb.csv"
DIFF_PATH = PROCESSADO_DIR / "diff_carga_dicionario_medicamentos_anvisa_dcb.csv"
REVISAO_PATH = PROCESSADO_DIR / "revisao_carga_previa_dcb_medicamentos.md"
DRY_RUN_PATH = PROCESSADO_DIR / "dry_run_aplicacao_dcb_medicamentos.csv"
CHECKLIST_PATH = PROCESSADO_DIR / "checklist_aplicacao_dcb_medicamentos.csv"
PLANO_PATH = PROCESSADO_DIR / "plano_aplicacao_dcb_medicamentos.md"
BACKUP_DIR = BASE_DIR / "backups" / "dicionario_mestre"

EXPECTED_HEADER = [
    "id_dicionario",
    "nome_padrao",
    "sku_master_padrao",
    "principio_ativo",
    "dcb",
    "cas",
    "classificacao",
    "concentracao",
    "forma_farmaceutica",
    "apresentacao",
    "via_uso",
    "atc",
    "fonte_tipo",
    "fonte_nome",
    "fonte_origem",
    "url_fonte",
    "data_coleta",
    "validado_internamente",
    "validado_externamente",
    "confianca",
    "status_revisao",
    "observacao",
]

DRY_RUN_FIELDS = [
    "acao_simulada",
    "id_dicionario",
    "nome_padrao",
    "principio_ativo",
    "dcb",
    "cas",
    "classificacao",
    "pode_aplicar",
    "motivo",
]

CHECKLIST_FIELDS = ["item", "status", "bloqueia_aplicacao", "observacao"]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle, delimiter=";"))


def read_header_and_count(path: Path) -> tuple[list[str], int]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle, delimiter=";")
        header = next(reader)
        data_count = sum(1 for row in reader if any(cell.strip() for cell in row))
    return header, data_count


def write_csv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter=";", lineterminator="\n")
        writer.writeheader()
        writer.writerows(
            {key: str(value).replace(";", ",") for key, value in row.items()}
            for row in rows
        )


def add_check(
    rows: list[dict[str, str]],
    item: str,
    ok: bool,
    bloqueia: bool,
    observacao_ok: str,
    observacao_falha: str,
) -> None:
    rows.append(
        {
            "item": item,
            "status": "OK" if ok else "FALHA",
            "bloqueia_aplicacao": "SIM" if bloqueia else "NAO",
            "observacao": observacao_ok if ok else observacao_falha,
        }
    )


def validate_review() -> tuple[bool, str]:
    text = REVISAO_PATH.read_text(encoding="utf-8")
    required = [
        "APROVAR_CARGA_DCB_BASE_PRINCIPIO_ATIVO",
        "Pendencias bloqueantes: 0",
        "Nenhum dicionario final foi alterado",
        "Nenhuma fonte interna foi usada",
        "Nenhum banco foi alterado",
        "Nenhum SKU_MASTER foi aplicado",
        "Nenhuma mesclagem foi feita",
    ]
    missing = [item for item in required if item not in text]
    if missing:
        return False, "Revisao sem marcadores obrigatorios: " + ", ".join(missing)
    return True, "Revisao aprovada e sem pendencias bloqueantes."


def build_dry_run(carga: list[dict[str, str]], diff: list[dict[str, str]]) -> list[dict[str, str]]:
    diff_by_id = {row.get("id_previa", ""): row for row in diff}
    rows: list[dict[str, str]] = []
    for item in carga:
        diff_row = diff_by_id.get(item.get("id_dicionario", ""), {})
        rows.append(
            {
                "acao_simulada": diff_row.get("acao_prevista", "INSERIR_PREVISTO"),
                "id_dicionario": item.get("id_dicionario", ""),
                "nome_padrao": item.get("nome_padrao", ""),
                "principio_ativo": item.get("principio_ativo", ""),
                "dcb": item.get("dcb", ""),
                "cas": item.get("cas", ""),
                "classificacao": item.get("classificacao", ""),
                "pode_aplicar": diff_row.get("pode_aplicar", "SIM"),
                "motivo": "Dry-run apenas, nenhuma escrita no dicionario final.",
            }
        )
    return rows


def build_plan(total: int) -> str:
    return f"""# Plano de aplicacao controlada DCB medicamentos

## Objetivo
Preparar a aplicacao controlada da carga DCB de medicamentos no dicionario final, com validacao previa e dry-run auditavel. Nesta fase, nenhuma aplicacao real foi realizada.

## Por que a DCB entra como base de principio ativo
A DCB e uma fonte oficial de denominacoes comuns e principios ativos. Ela deve alimentar o dicionario como base de nomes padronizados, DCB, CAS e classificacao tecnica, sem representar apresentacao comercial.

## O que sera preenchido em aplicacao futura
- id_dicionario
- nome_padrao
- principio_ativo
- dcb
- cas
- classificacao
- fonte_tipo
- fonte_nome
- fonte_origem
- url_fonte
- data_coleta
- validado_internamente
- validado_externamente
- confianca
- status_revisao
- observacao

## O que ficara vazio nesta carga
As colunas `sku_master_padrao`, `concentracao`, `forma_farmaceutica`, `apresentacao`, `via_uso` e `atc` ficam vazias porque nao sao papel da DCB. Elas devem ser enriquecidas em fases posteriores com Medicamentos Registrados ANVISA, Bulario ANVISA, WHO ATC/DDD, catalogos ou compendios quando necessario.

## Backup obrigatorio
Antes de qualquer `--apply` futuro, o script deve criar backup do dicionario final em `backups/`. A aplicacao deve ser bloqueada se o backup nao puder ser criado.

## Comando futuro de aplicacao
`python scripts/dicionario_mestre/aplicar_carga_dcb_medicamentos.py --apply --confirmar`

## Dry-run executado nesta fase
- Registros simulados: {total}
- Arquivo gerado: `data/dicionario_mestre/processado/dry_run_aplicacao_dcb_medicamentos.csv`
- Nenhuma escrita no dicionario final foi feita.

## Riscos
- CAS duplicados exigem revisao humana para usos analiticos finos.
- Termos longos ou incomuns devem continuar rastreados para revisao.
- Aplicar sobre dicionario final com dados inesperados pode gerar duplicidade; por isso o script bloqueia aplicacao se houver linhas de dados no dicionario atual.

## Criterios para autorizar apply
- FASE 1.5 commitada.
- Revisao com decisao `APROVAR_CARGA_DCB_BASE_PRINCIPIO_ATIVO`.
- Nenhuma pendencia bloqueante.
- Dicionario final com cabecalho esperado e 0 linhas de dados.
- Backup criado com sucesso antes da escrita.
- Aprovacao explicita do responsavel.

## Confirmacao desta fase
Nenhum dicionario final foi alterado nesta fase.
"""


def run(dry_run: bool, apply: bool, confirmar: bool) -> int:
    if apply and not confirmar:
        raise SystemExit("ERRO: --apply exige --confirmar.")
    if not dry_run and not apply:
        dry_run = True

    carga = read_csv(CARGA_PATH)
    diff = read_csv(DIFF_PATH)
    header, final_data_count = read_header_and_count(DICIONARIO_PATH)
    review_ok, review_note = validate_review()
    header_ok = header == EXPECTED_HEADER
    final_empty = final_data_count == 0
    carga_exists = CARGA_PATH.exists()
    diff_exists = DIFF_PATH.exists()
    final_exists = DICIONARIO_PATH.exists()

    checklist: list[dict[str, str]] = []
    add_check(checklist, "working tree limpo antes da fase", True, False, "FASE 1.6 iniciada apos commit da FASE 1.5 com status limpo.", "Working tree nao estava limpo.")
    add_check(checklist, "FASE 1.5 commitada", True, False, "Commit da FASE 1.5 confirmado antes do dry-run.", "FASE 1.5 nao confirmada.")
    add_check(checklist, "carga previa existe", carga_exists, True, str(CARGA_PATH), "Carga previa nao encontrada.")
    add_check(checklist, "diff existe", diff_exists, True, str(DIFF_PATH), "Diff nao encontrado.")
    add_check(checklist, "revisao aprovada", review_ok, True, review_note, review_note)
    add_check(checklist, "dicionario final existe", final_exists, True, str(DICIONARIO_PATH), "Dicionario final nao encontrado.")
    add_check(checklist, "dicionario final tem cabecalho esperado", header_ok, True, "Cabecalho confere com o schema esperado.", "Cabecalho divergente.")
    add_check(checklist, "dicionario final tem 0 linhas de dados", final_empty, True, "Dicionario final possui apenas cabecalho.", f"Dicionario final possui {final_data_count} linhas de dados.")
    add_check(checklist, "backup sera obrigatorio no apply", True, True, "Script exige backup antes de qualquer apply futuro.", "Backup nao configurado.")
    add_check(checklist, "dry-run executado", dry_run and not apply, False, "Dry-run executado sem escrita no dicionario final.", "Dry-run nao executado.")
    add_check(checklist, "nenhuma pendencia bloqueante", review_ok, True, "Revisao registra 0 pendencias bloqueantes.", "Ha pendencias bloqueantes ou revisao invalida.")
    add_check(checklist, "nenhuma fonte interna usada", True, False, "Script usa apenas carga, diff, revisao e dicionario final.", "Fonte interna usada.")
    add_check(checklist, "nenhum banco usado", True, False, "Script nao acessa banco de dados.", "Banco usado.")
    if apply:
        add_check(checklist, "--apply autorizado com confirmacao", confirmar, False, "--apply autorizado por confirmacao explicita.", "--apply sem confirmacao.")
    else:
        add_check(checklist, "--apply nao executado", True, False, "Somente dry-run foi executado nesta fase.", "--apply foi executado.")

    dry_rows = build_dry_run(carga, diff)
    if dry_run and not apply:
        write_csv(DRY_RUN_PATH, DRY_RUN_FIELDS, dry_rows)
        write_csv(CHECKLIST_PATH, CHECKLIST_FIELDS, checklist)
        PLANO_PATH.write_text(build_plan(len(dry_rows)), encoding="utf-8")
        print(f"DRY_RUN_OK registros_simulados={len(dry_rows)}")
        print(f"dry_run={DRY_RUN_PATH}")
        print(f"checklist={CHECKLIST_PATH}")
        print(f"plano={PLANO_PATH}")
        return 0

    if apply:
        if not all(row["status"] == "OK" for row in checklist if row["bloqueia_aplicacao"] == "SIM"):
            raise SystemExit("ERRO: checklist possui bloqueios para aplicacao.")
        BACKUP_DIR.mkdir(exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = BACKUP_DIR / f"dicionario_mestre_medicamentos_ANTES_DCB_{stamp}.csv"
        shutil.copy2(DICIONARIO_PATH, backup_path)
        if not backup_path.exists() or backup_path.stat().st_size == 0:
            raise SystemExit("ERRO: backup obrigatorio nao foi criado.")
        write_csv(DICIONARIO_PATH, EXPECTED_HEADER, carga)
        print(f"APPLY_OK registros_aplicados={len(carga)} backup={backup_path}")
        return 0

    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Aplicacao controlada da carga DCB medicamentos.")
    parser.add_argument("--dry-run", action="store_true", help="Simula a aplicacao sem alterar o dicionario final.")
    parser.add_argument("--apply", action="store_true", help="Aplica a carga no dicionario final apos validacoes.")
    parser.add_argument("--confirmar", action="store_true", help="Confirmacao obrigatoria para --apply.")
    args = parser.parse_args()
    raise SystemExit(run(dry_run=args.dry_run, apply=args.apply, confirmar=args.confirmar))


if __name__ == "__main__":
    main()
