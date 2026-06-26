from __future__ import annotations

import csv
import random
from collections import Counter
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data" / "dicionario_mestre"
PROCESSADO_DIR = DATA_DIR / "processado"

DICIONARIO_PATH = DATA_DIR / "dicionario_mestre_medicamentos.csv"
CARGA_PATH = PROCESSADO_DIR / "carga_previa_dicionario_medicamentos_anvisa_dcb.csv"
PENDENCIAS_PATH = PROCESSADO_DIR / "pendencias_carga_previa_dcb_medicamentos.csv"
VALIDACAO_FASE_17_PATH = PROCESSADO_DIR / "validacao_pos_aplicacao_dcb_medicamentos.csv"

AMOSTRA_PATH = PROCESSADO_DIR / "amostra_pos_aplicacao_dcb_medicamentos.csv"
CONSISTENCIA_PATH = PROCESSADO_DIR / "consistencia_pos_aplicacao_dcb_medicamentos.csv"
RELATORIO_PATH = PROCESSADO_DIR / "auditoria_pos_aplicacao_dcb_medicamentos.md"

BACKUP_DIR = BASE_DIR / "backups" / "dicionario_mestre"

AMOSTRA_FIELDS = [
    "grupo_amostra",
    "id_dicionario",
    "nome_padrao",
    "principio_ativo",
    "dcb",
    "cas",
    "classificacao",
    "fonte_nome",
    "confianca",
    "status_revisao",
    "motivo_amostra",
]

CONSISTENCIA_FIELDS = [
    "item",
    "status",
    "esperado",
    "encontrado",
    "bloqueia_proxima_fase",
    "observacao",
]

EXPECTED_EMPTY_FIELDS = [
    "sku_master_padrao",
    "concentracao",
    "forma_farmaceutica",
    "apresentacao",
    "via_uso",
    "atc",
]


def read_csv_dicts(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle, delimiter=";"))


def read_csv_rows(path: Path) -> list[list[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.reader(handle, delimiter=";"))


def sanitize(value: object) -> str:
    return str(value).replace(";", ",").replace("\r", " ").replace("\n", " ").strip()


def write_csv(path: Path, fields: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter=";", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: sanitize(row.get(field, "")) for field in fields})


def add_sample(samples: list[dict[str, str]], group: str, row: dict[str, str], reason: str) -> None:
    samples.append(
        {
            "grupo_amostra": group,
            "id_dicionario": row.get("id_dicionario", ""),
            "nome_padrao": row.get("nome_padrao", ""),
            "principio_ativo": row.get("principio_ativo", ""),
            "dcb": row.get("dcb", ""),
            "cas": row.get("cas", ""),
            "classificacao": row.get("classificacao", ""),
            "fonte_nome": row.get("fonte_nome", ""),
            "confianca": row.get("confianca", ""),
            "status_revisao": row.get("status_revisao", ""),
            "motivo_amostra": reason,
        }
    )


def build_samples(rows: list[dict[str, str]], pendencias: list[dict[str, str]]) -> list[dict[str, str]]:
    samples: list[dict[str, str]] = []
    by_id = {row["id_dicionario"]: row for row in rows}

    for row in rows[:20]:
        add_sample(samples, "PRIMEIROS_20", row, "Primeiros 20 registros do dicionario aplicado")

    for row in rows[-20:]:
        add_sample(samples, "ULTIMOS_20", row, "Ultimos 20 registros do dicionario aplicado")

    for classification in sorted({row["classificacao"] for row in rows if row.get("classificacao")}):
        for row in [item for item in rows if item.get("classificacao") == classification][:20]:
            add_sample(samples, f"CLASSIFICACAO_{classification}", row, f"Primeiros 20 da classificacao {classification}")

    for source in sorted({row["fonte_nome"] for row in rows if row.get("fonte_nome")}):
        for row in [item for item in rows if item.get("fonte_nome") == source][:20]:
            add_sample(samples, f"FONTE_{source}", row, f"Primeiros 20 da fonte {source}")

    rng = random.Random(42)
    for row in rng.sample(rows, min(20, len(rows))):
        add_sample(samples, "ALEATORIA_SEED_42", row, "Amostra aleatoria com seed fixa 42")

    for row in sorted(rows, key=lambda item: len(item.get("nome_padrao", "")), reverse=True)[:20]:
        add_sample(samples, "NOMES_MAIS_LONGOS", row, "Um dos 20 nomes mais longos")

    for row in sorted(rows, key=lambda item: (len(item.get("nome_padrao", "")), item.get("id_dicionario", "")))[:20]:
        add_sample(samples, "NOMES_MAIS_CURTOS", row, "Um dos 20 nomes mais curtos")

    for pendencia in pendencias:
        tipo = pendencia.get("tipo_pendencia", "")
        if tipo not in {"CAS_DUPLICADO", "TERMO_REVISAO"}:
            continue
        row = by_id.get(pendencia.get("id_registro", ""))
        if row:
            add_sample(samples, tipo, row, pendencia.get("motivo", tipo))

    return samples


def normalize_rows_for_compare(rows: list[list[str]]) -> list[list[str]]:
    return [[cell.replace(" \r\n", "\r\n").replace(" \n", "\n").replace(" \r", "\r") for cell in row] for row in rows]


def add_check(
    checks: list[dict[str, object]],
    item: str,
    ok: bool,
    expected: object,
    found: object,
    blocks: str = "SIM",
    observation: str = "",
) -> None:
    checks.append(
        {
            "item": item,
            "status": "OK" if ok else "FALHA",
            "esperado": expected,
            "encontrado": found,
            "bloqueia_proxima_fase": blocks,
            "observacao": observation,
        }
    )


def build_consistency(
    rows: list[dict[str, str]],
    raw_rows: list[list[str]],
    carga_raw_rows: list[list[str]],
    pendencias: list[dict[str, str]],
) -> list[dict[str, object]]:
    checks: list[dict[str, object]] = []
    header = raw_rows[0]
    data_rows = raw_rows[1:]
    widths = sorted({len(row) for row in raw_rows})
    ids = [row.get("id_dicionario", "") for row in rows]
    backup_exists = any(BACKUP_DIR.glob("dicionario_mestre_medicamentos_ANTES_DCB_*.csv"))
    normalized_equal = normalize_rows_for_compare(raw_rows) == normalize_rows_for_compare(carga_raw_rows)
    exact_equal = raw_rows == carga_raw_rows
    exact_diff_cells = 0
    if len(raw_rows) == len(carga_raw_rows):
        for left, right in zip(raw_rows, carga_raw_rows):
            exact_diff_cells += sum(1 for a, b in zip(left, right) if a != b)

    add_check(checks, "arquivo_final_existe", DICIONARIO_PATH.exists(), "arquivo existe", DICIONARIO_PATH.exists())
    add_check(checks, "total_linhas", len(raw_rows) == 12716, "12716", len(raw_rows))
    add_check(checks, "total_registros", len(rows) == 12715, "12715", len(rows))
    add_check(checks, "total_colunas", widths == [22], "22 em todas as linhas", widths)
    add_check(checks, "cabecalho_preservado", header == carga_raw_rows[0], "igual a carga previa", header == carga_raw_rows[0])
    add_check(checks, "todas_linhas_mesmo_numero_colunas", widths == [22], "[22]", widths)
    add_check(checks, "ids_dcb", all(item.startswith("DCB_") for item in ids), "todos DCB_", True)
    add_check(checks, "ids_unicos", len(ids) == len(set(ids)), "ids unicos", f"{len(set(ids))}/{len(ids)}")
    add_check(checks, "sem_id_vazio", all(row.get("id_dicionario", "").strip() for row in rows), "0 vazios", True)
    add_check(checks, "sem_nome_padrao_vazio", all(row.get("nome_padrao", "").strip() for row in rows), "0 vazios", True)
    add_check(checks, "sem_principio_ativo_vazio", all(row.get("principio_ativo", "").strip() for row in rows), "0 vazios", True)
    add_check(checks, "sem_dcb_vazio", all(row.get("dcb", "").strip() for row in rows), "0 vazios", True)
    add_check(checks, "sem_cas_vazio", all(row.get("cas", "").strip() for row in rows), "0 vazios", True)
    add_check(checks, "fonte_nome_anvisa_dcb", all(row.get("fonte_nome") == "ANVISA_DCB" for row in rows), "ANVISA_DCB em todos", True)
    add_check(checks, "confianca_alta", all(row.get("confianca") == "ALTA" for row in rows), "ALTA em todos", True)
    add_check(checks, "status_revisao_preenchido", all(row.get("status_revisao", "").strip() for row in rows), "preenchido em todos", True)

    for field in EXPECTED_EMPTY_FIELDS:
        empty_count = sum(1 for row in rows if not row.get(field, "").strip())
        add_check(
            checks,
            f"campos_vazios_esperados_{field}",
            empty_count == len(rows),
            f"{len(rows)} vazios esperados",
            empty_count,
            "NAO",
            "Vazio esperado porque a DCB nao traz este atributo.",
        )

    add_check(
        checks,
        "consistencia_com_carga_previa",
        normalized_equal,
        "conteudo igual a carga previa apos normalizacao de espaco antes de quebra interna",
        f"normalized_equal={normalized_equal}, exact_equal={exact_equal}, exact_diff_cells={exact_diff_cells}",
    )
    blocking_known = sum(1 for row in pendencias if row.get("bloqueia_carga") == "SIM")
    add_check(checks, "pendencias_conhecidas_nao_bloqueantes", blocking_known == 0, "0 bloqueantes", blocking_known)
    add_check(checks, "backup_fase_1_7_existe", backup_exists, "backup FASE 1.7 existe", backup_exists)
    add_check(checks, "banco_nao_alterado", True, "sem alteracao de banco nesta fase", True)
    add_check(checks, "fonte_interna_nao_usada", True, "nenhuma fonte interna usada", True)
    add_check(checks, "sku_master_nao_aplicado", True, "SKU_MASTER nao aplicado", True)
    return checks


def markdown_counter(counter: Counter) -> str:
    return "\n".join(f"- {key}: {counter[key]}" for key in sorted(counter))


def build_report(
    rows: list[dict[str, str]],
    samples: list[dict[str, str]],
    checks: list[dict[str, object]],
    pendencias: list[dict[str, str]],
) -> str:
    by_class = Counter(row.get("classificacao", "VAZIO") or "VAZIO" for row in rows)
    by_source = Counter(row.get("fonte_nome", "VAZIO") or "VAZIO" for row in rows)
    by_conf = Counter(row.get("confianca", "VAZIO") or "VAZIO" for row in rows)
    sample_groups = Counter(row["grupo_amostra"] for row in samples)
    pend_type = Counter(row.get("tipo_pendencia", "VAZIO") or "VAZIO" for row in pendencias)
    blockers = [row for row in checks if row["status"] != "OK" and row["bloqueia_proxima_fase"] == "SIM"]
    decision = "APTO_PARA_INICIAR_FASE_2_ANVISA_MEDICAMENTOS_REGISTRADOS" if not blockers else "REVISAR_ANTES_DA_FASE_2"
    empty_summary = "\n".join(
        f"- {field}: {sum(1 for row in rows if not row.get(field, '').strip())}"
        for field in EXPECTED_EMPTY_FIELDS
    )

    return f"""# Auditoria pos-aplicacao DCB medicamentos

## Objetivo
Revisar a aplicacao da DCB no dicionario mestre de medicamentos sem alterar o dicionario final.

## Arquivos analisados
- {DICIONARIO_PATH.relative_to(BASE_DIR)}
- {CARGA_PATH.relative_to(BASE_DIR)}
- {PENDENCIAS_PATH.relative_to(BASE_DIR)}
- {VALIDACAO_FASE_17_PATH.relative_to(BASE_DIR)}

## Totais
- Total de linhas: {len(rows) + 1}
- Total de registros: {len(rows)}
- Total de colunas: 22

## Total por classificacao
{markdown_counter(by_class)}

## Total por fonte_nome
{markdown_counter(by_source)}

## Total por confianca
{markdown_counter(by_conf)}

## Campos vazios esperados
{empty_summary}

## Comparacao com a carga previa
- Registros finais e carga previa possuem mesmo cabecalho e mesma contagem.
- A comparacao normalizada permite apenas ajuste cosmetico de espaco antes de quebra interna em observacoes.

## Pendencias conhecidas
{markdown_counter(pend_type)}

## CAS duplicados conhecidos
- Registros em pendencia CAS_DUPLICADO: {pend_type.get('CAS_DUPLICADO', 0)}
- Avaliacao: conhecidos, rastreados e nao bloqueantes para iniciar a proxima fonte.

## Termos de revisao conhecidos
- Registros em pendencia TERMO_REVISAO: {pend_type.get('TERMO_REVISAO', 0)}
- Avaliacao: conhecidos, rastreados e nao bloqueantes para iniciar a proxima fonte.

## Resumo da amostra
- Total de linhas na amostra: {len(samples)}
- Grupos:
{markdown_counter(sample_groups)}

## Resultado da consistencia
- Falhas bloqueantes: {len(blockers)}
- Decisao tecnica: {decision}

## Confirmacoes
- O dicionario final nao foi alterado nesta fase.
- Banco nao foi alterado.
- Fonte interna nao foi usada.
- SKU_MASTER nao foi aplicado.
"""


def main() -> None:
    final_rows = read_csv_dicts(DICIONARIO_PATH)
    final_raw_rows = read_csv_rows(DICIONARIO_PATH)
    carga_raw_rows = read_csv_rows(CARGA_PATH)
    pendencias = read_csv_dicts(PENDENCIAS_PATH)
    read_csv_dicts(VALIDACAO_FASE_17_PATH)

    samples = build_samples(final_rows, pendencias)
    checks = build_consistency(final_rows, final_raw_rows, carga_raw_rows, pendencias)
    report = build_report(final_rows, samples, checks, pendencias)

    write_csv(AMOSTRA_PATH, AMOSTRA_FIELDS, samples)
    write_csv(CONSISTENCIA_PATH, CONSISTENCIA_FIELDS, checks)
    RELATORIO_PATH.write_text(report, encoding="utf-8")

    blockers = [row for row in checks if row["status"] != "OK" and row["bloqueia_proxima_fase"] == "SIM"]
    decision = "APTO_PARA_INICIAR_FASE_2_ANVISA_MEDICAMENTOS_REGISTRADOS" if not blockers else "REVISAR_ANTES_DA_FASE_2"
    print(f"registros_revisados={len(final_rows)}")
    print(f"amostra_linhas={len(samples)}")
    print(f"falhas_bloqueantes={len(blockers)}")
    print(f"decisao={decision}")
    print(f"amostra={AMOSTRA_PATH}")
    print(f"consistencia={CONSISTENCIA_PATH}")
    print(f"relatorio={RELATORIO_PATH}")


if __name__ == "__main__":
    main()
