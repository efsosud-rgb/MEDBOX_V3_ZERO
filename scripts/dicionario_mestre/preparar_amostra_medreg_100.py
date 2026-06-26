"""
FASE 2.14A - Preparacao da amostra 100 MEDREG para captura futura.

Escopo:
- Le somente o dicionario mestre de medicamentos.
- Nao acessa internet.
- Nao executa scraping/crawler.
- Nao altera dicionario final, banco ou fontes internas.
- Gera apenas CSV de amostra para captura bruta futura.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
from pathlib import Path
from typing import Iterable


BASE_DIR = Path(__file__).resolve().parents[2]
SOURCE_PATH = BASE_DIR / "data" / "dicionario_mestre" / "dicionario_mestre_medicamentos.csv"
OUTPUT_PATH = BASE_DIR / "data" / "dicionario_mestre" / "processado" / "amostra_medreg_100_para_captura.csv"
TARGET_SIZE = 100
TARGET_SEM_DCB_CAS = 15

OUTPUT_COLUMNS = [
    "id_origem",
    "origem",
    "registro_anvisa",
    "nome_produto",
    "principio_ativo",
    "dcb",
    "cas",
    "empresa",
    "forma_farmaceutica_atual",
    "concentracao_atual",
    "apresentacao_atual",
    "via_uso_atual",
    "motivo_selecao",
    "status_preparacao",
]


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        sample = fh.read(4096)
        fh.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=";,\t,")
            delimiter = dialect.delimiter
        except csv.Error:
            delimiter = ";"
        reader = csv.DictReader(fh, delimiter=delimiter)
        rows = [{k: (v or "") for k, v in row.items()} for row in reader]
        return reader.fieldnames or [], rows


def extract_registro(row: dict[str, str]) -> str:
    explicit = (row.get("registro_anvisa") or row.get("numero_registro") or "").strip()
    if explicit:
        return explicit
    id_origem = (row.get("id_dicionario") or row.get("id_origem") or "").strip()
    match = re.match(r"ANVISA_MEDREG_(\d{6,})$", id_origem)
    if match:
        return match.group(1)
    obs = row.get("observacao", "")
    match = re.search(r"numero_registro=([0-9]{6,})", obs)
    if match:
        return match.group(1)
    return ""


def extract_empresa(row: dict[str, str]) -> str:
    for key in ("empresa", "empresa_detentora", "empresa_detentora_registro"):
        value = row.get(key, "").strip()
        if value:
            return value
    obs = row.get("observacao", "")
    match = re.search(r"empresa=([^;]+)", obs)
    if match:
        return match.group(1).strip()
    return ""


def stable_key(row: dict[str, str]) -> str:
    raw = "|".join([
        row.get("id_dicionario", ""),
        row.get("nome_padrao", ""),
        row.get("principio_ativo", ""),
    ])
    return hashlib.sha1(raw.encode("utf-8", errors="ignore")).hexdigest()


def is_medreg(row: dict[str, str]) -> bool:
    id_value = row.get("id_dicionario", "")
    fonte = row.get("fonte_nome", "")
    return id_value.startswith("ANVISA_MEDREG") or fonte == "ANVISA_MEDICAMENTOS_REGISTRADOS"


def has_dcb_cas(row: dict[str, str]) -> bool:
    return bool(row.get("dcb", "").strip()) and bool(row.get("cas", "").strip())


def target_fields_empty(row: dict[str, str]) -> bool:
    return not any(
        row.get(field, "").strip()
        for field in ("forma_farmaceutica", "concentracao", "apresentacao", "via_uso")
    )


def valid_registry(row: dict[str, str]) -> bool:
    return bool(re.fullmatch(r"\d{6,}", extract_registro(row)))


def select_diverse(rows: Iterable[dict[str, str]], limit: int) -> list[dict[str, str]]:
    selected: list[dict[str, str]] = []
    used_pa: set[str] = set()
    sorted_rows = sorted(rows, key=stable_key)

    for row in sorted_rows:
        pa = row.get("principio_ativo", "").strip().upper() or row.get("nome_padrao", "").strip().upper()
        if pa in used_pa:
            continue
        selected.append(row)
        used_pa.add(pa)
        if len(selected) >= limit:
            return selected

    seen_ids = {row.get("id_dicionario", "") for row in selected}
    for row in sorted_rows:
        row_id = row.get("id_dicionario", "")
        if row_id in seen_ids:
            continue
        selected.append(row)
        seen_ids.add(row_id)
        if len(selected) >= limit:
            break
    return selected


def output_row(row: dict[str, str], motivo: str) -> dict[str, str]:
    return {
        "id_origem": row.get("id_dicionario", ""),
        "origem": row.get("fonte_nome", "") or "ANVISA_MEDREG",
        "registro_anvisa": extract_registro(row),
        "nome_produto": row.get("nome_padrao", "") or row.get("nome_produto", ""),
        "principio_ativo": row.get("principio_ativo", ""),
        "dcb": row.get("dcb", ""),
        "cas": row.get("cas", ""),
        "empresa": extract_empresa(row),
        "forma_farmaceutica_atual": row.get("forma_farmaceutica", ""),
        "concentracao_atual": row.get("concentracao", ""),
        "apresentacao_atual": row.get("apresentacao", ""),
        "via_uso_atual": row.get("via_uso", ""),
        "motivo_selecao": motivo,
        "status_preparacao": "PREPARADO_CAPTURA_FUTURA",
    }


def main() -> int:
    if not SOURCE_PATH.exists():
        raise FileNotFoundError(f"Fonte nao encontrada: {SOURCE_PATH}")

    headers, rows = read_csv(SOURCE_PATH)
    medreg = [row for row in rows if is_medreg(row)]
    elegiveis = [row for row in medreg if valid_registry(row) and target_fields_empty(row)]
    com_dcb_cas = [row for row in elegiveis if has_dcb_cas(row)]
    sem_dcb_cas = [row for row in elegiveis if not has_dcb_cas(row)]

    qtd_sem = min(TARGET_SEM_DCB_CAS, len(sem_dcb_cas), TARGET_SIZE)
    qtd_com = min(TARGET_SIZE - qtd_sem, len(com_dcb_cas))

    selecionados_com = select_diverse(com_dcb_cas, qtd_com)
    selecionados_sem = select_diverse(sem_dcb_cas, qtd_sem)
    selected_ids = {row.get("id_dicionario", "") for row in selecionados_com + selecionados_sem}

    if len(selected_ids) < TARGET_SIZE:
        restante = [row for row in elegiveis if row.get("id_dicionario", "") not in selected_ids]
        complemento = select_diverse(restante, TARGET_SIZE - len(selected_ids))
    else:
        complemento = []

    output_rows: list[dict[str, str]] = []
    for row in selecionados_com:
        output_rows.append(output_row(row, "registro_valido_com_dcb_cas_campos_alvo_vazios"))
    for row in selecionados_sem:
        output_rows.append(output_row(row, "registro_valido_sem_dcb_cas_para_teste_de_falha"))
    for row in complemento:
        output_rows.append(output_row(row, "complemento_diversidade_amostra"))

    output_rows = output_rows[:TARGET_SIZE]
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=OUTPUT_COLUMNS, delimiter=";")
        writer.writeheader()
        writer.writerows(output_rows)

    summary = {
        "source_path": str(SOURCE_PATH.relative_to(BASE_DIR)),
        "output_path": str(OUTPUT_PATH.relative_to(BASE_DIR)),
        "headers_presentes": headers,
        "total_linhas_fonte": len(rows),
        "total_medreg": len(medreg),
        "total_elegiveis": len(elegiveis),
        "total_com_dcb_cas_elegiveis": len(com_dcb_cas),
        "total_sem_dcb_cas_elegiveis": len(sem_dcb_cas),
        "total_selecionados": len(output_rows),
        "selecionados_com_dcb_cas": sum(1 for row in output_rows if row["dcb"] and row["cas"]),
        "selecionados_sem_dcb_cas": sum(1 for row in output_rows if not (row["dcb"] and row["cas"])),
        "campos_alvo_preenchidos_na_amostra": sum(
            1 for row in output_rows
            if row["forma_farmaceutica_atual"] or row["concentracao_atual"] or row["apresentacao_atual"] or row["via_uso_atual"]
        ),
        "internet_acessada": False,
        "scraping_executado": False,
        "captura_bruta_executada": False,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
