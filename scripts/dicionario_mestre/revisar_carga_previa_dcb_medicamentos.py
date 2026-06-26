from __future__ import annotations

import csv
import random
from collections import Counter, defaultdict
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[2]
PROCESSADO_DIR = BASE_DIR / "data" / "dicionario_mestre" / "processado"

CARGA_PATH = PROCESSADO_DIR / "carga_previa_dicionario_medicamentos_anvisa_dcb.csv"
DIFF_PATH = PROCESSADO_DIR / "diff_carga_dicionario_medicamentos_anvisa_dcb.csv"
DUPLICIDADES_PATH = PROCESSADO_DIR / "duplicidades_previa_dcb_medicamentos.csv"
TERMOS_REVISAO_PATH = PROCESSADO_DIR / "termos_revisao_previa_dcb_medicamentos.csv"

AMOSTRA_PATH = PROCESSADO_DIR / "amostra_carga_previa_dcb_medicamentos.csv"
PENDENCIAS_PATH = PROCESSADO_DIR / "pendencias_carga_previa_dcb_medicamentos.csv"
RELATORIO_PATH = PROCESSADO_DIR / "revisao_carga_previa_dcb_medicamentos.md"

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

PENDENCIA_FIELDS = [
    "tipo_pendencia",
    "severidade",
    "bloqueia_carga",
    "id_registro",
    "termo",
    "cas",
    "coluna_afetada",
    "motivo",
    "acao_recomendada",
]

COLUNAS_SEM_EQUIVALENTE = [
    "sku_master_padrao",
    "concentracao",
    "forma_farmaceutica",
    "apresentacao",
    "via_uso",
    "atc",
]

FONTES_POSTERIORES = (
    "Medicamentos Registrados ANVISA, Bulario ANVISA, WHO ATC/DDD, "
    "catalogos ou compendios quando necessario"
)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle, delimiter=";"))


def write_csv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter=";", lineterminator="\n")
        writer.writeheader()
        writer.writerows(
            {
                key: str(value).replace(";", ",")
                for key, value in row.items()
            }
            for row in rows
        )


def by_id(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {row["id_dicionario"]: row for row in rows}


def append_sample(samples: list[dict[str, str]], grupo: str, row: dict[str, str], motivo: str) -> None:
    samples.append(
        {
            "grupo_amostra": grupo,
            "id_dicionario": row.get("id_dicionario", ""),
            "nome_padrao": row.get("nome_padrao", ""),
            "principio_ativo": row.get("principio_ativo", ""),
            "dcb": row.get("dcb", ""),
            "cas": row.get("cas", ""),
            "classificacao": row.get("classificacao", ""),
            "fonte_nome": row.get("fonte_nome", ""),
            "confianca": row.get("confianca", ""),
            "status_revisao": row.get("status_revisao", ""),
            "motivo_amostra": motivo,
        }
    )


def build_samples(
    carga: list[dict[str, str]],
    diff: list[dict[str, str]],
    duplicidades: list[dict[str, str]],
    termos_revisao: list[dict[str, str]],
) -> list[dict[str, str]]:
    samples: list[dict[str, str]] = []
    carga_by_id = by_id(carga)
    subcategoria_by_id = {row["id_previa"]: row.get("subcategoria_sugerida", "") for row in diff}

    for row in carga[:20]:
        append_sample(samples, "PRIMEIROS_20", row, "Primeiros 20 registros da carga previa")

    for classificacao in sorted({row.get("classificacao", "") for row in carga if row.get("classificacao", "")}):
        grupo_rows = [row for row in carga if row.get("classificacao", "") == classificacao]
        for row in grupo_rows[:20]:
            append_sample(
                samples,
                f"CLASSIFICACAO_{classificacao}",
                row,
                f"Primeiros 20 registros da classificacao {classificacao}",
            )

    subcategorias = sorted({value for value in subcategoria_by_id.values() if value})
    for subcategoria in subcategorias:
        ids = [row["id_previa"] for row in diff if row.get("subcategoria_sugerida", "") == subcategoria]
        for id_previa in ids[:20]:
            row = carga_by_id.get(id_previa)
            if row:
                append_sample(
                    samples,
                    f"SUBCATEGORIA_{subcategoria}",
                    row,
                    f"Primeiros 20 registros da subcategoria {subcategoria}",
                )

    ids_duplicados: list[str] = []
    for row in duplicidades:
        ids_duplicados.extend([item for item in row.get("ids_previa", "").split("|") if item])
    for id_previa in ids_duplicados:
        row = carga_by_id.get(id_previa)
        if row:
            append_sample(samples, "CAS_DUPLICADO", row, "Registro ligado a CAS duplicado")

    for termo in termos_revisao:
        row = carga_by_id.get(termo.get("id_previa", ""))
        if row:
            append_sample(
                samples,
                "TERMO_REVISAO",
                row,
                termo.get("motivo_revisao", "Termo indicado para revisao"),
            )

    rng = random.Random(42)
    for row in rng.sample(carga, min(20, len(carga))):
        append_sample(samples, "ALEATORIA_SEED_42", row, "Amostra aleatoria com seed fixa 42")

    for row in sorted(carga, key=lambda item: len(item.get("nome_padrao", "")), reverse=True)[:20]:
        append_sample(samples, "NOMES_MAIS_LONGOS", row, "Um dos 20 nomes padronizados mais longos")

    for row in sorted(carga, key=lambda item: (len(item.get("nome_padrao", "")), item.get("id_dicionario", "")))[:20]:
        append_sample(samples, "NOMES_MAIS_CURTOS", row, "Um dos 20 nomes padronizados mais curtos")

    return samples


def build_pendencias(
    carga: list[dict[str, str]],
    duplicidades: list[dict[str, str]],
    termos_revisao: list[dict[str, str]],
) -> list[dict[str, str]]:
    pendencias: list[dict[str, str]] = []
    carga_by_id = by_id(carga)

    for item in duplicidades:
        ids = [value for value in item.get("ids_previa", "").split("|") if value]
        for id_previa in ids:
            row = carga_by_id.get(id_previa, {})
            pendencias.append(
                {
                    "tipo_pendencia": "CAS_DUPLICADO",
                    "severidade": "MEDIA",
                    "bloqueia_carga": "NAO",
                    "id_registro": id_previa,
                    "termo": row.get("nome_padrao", ""),
                    "cas": row.get("cas", item.get("chave", "")),
                    "coluna_afetada": "cas",
                    "motivo": "Mesmo CAS aparece em mais de um registro.",
                    "acao_recomendada": "Revisar agrupamento antes de uso analitico fino, nao bloqueia carga DCB como base de principio ativo.",
                }
            )

    for item in termos_revisao:
        id_previa = item.get("id_previa", "")
        row = carga_by_id.get(id_previa, {})
        motivo = item.get("motivo_revisao", "Termo indicado para revisao")
        pendencias.append(
            {
                "tipo_pendencia": "TERMO_REVISAO",
                "severidade": "MEDIA",
                "bloqueia_carga": "NAO",
                "id_registro": id_previa,
                "termo": row.get("nome_padrao", item.get("termo_oficial", "")),
                "cas": row.get("cas", item.get("numero_cas", "")),
                "coluna_afetada": "nome_padrao",
                "motivo": f"{motivo}: termo longo, caractere incomum ou outro motivo registrado.",
                "acao_recomendada": "Revisar humanamente a grafia e o contexto; nao bloqueia carga DCB como base de principio ativo.",
            }
        )

    for coluna in COLUNAS_SEM_EQUIVALENTE:
        pendencias.append(
            {
                "tipo_pendencia": "COLUNA_SEM_EQUIVALENTE_DCB",
                "severidade": "BAIXA",
                "bloqueia_carga": "NAO",
                "id_registro": "",
                "termo": "",
                "cas": "",
                "coluna_afetada": coluna,
                "motivo": "Coluna estrutural sem equivalente direto na DCB; pendencia esperada.",
                "acao_recomendada": (
                    "Nao bloqueia a carga DCB como base de principio ativo. Preencher em fases "
                    f"posteriores com: {FONTES_POSTERIORES}."
                ),
            }
        )

    return pendencias


def count_rows_by_type(rows: list[dict[str, str]], field: str) -> Counter:
    return Counter(row.get(field, "") or "VAZIO" for row in rows)


def markdown_counter(counter: Counter) -> str:
    return "\n".join(f"- {key}: {counter[key]}" for key in sorted(counter))


def build_report(
    carga: list[dict[str, str]],
    diff: list[dict[str, str]],
    duplicidades: list[dict[str, str]],
    termos_revisao: list[dict[str, str]],
    samples: list[dict[str, str]],
    pendencias: list[dict[str, str]],
) -> str:
    total_bloqueantes = sum(1 for row in pendencias if row.get("bloqueia_carga") == "SIM")
    decisao = "REVISAR_ANTES_DE_APLICAR" if total_bloqueantes else "APROVAR_CARGA_DCB_BASE_PRINCIPIO_ATIVO"
    acoes = count_rows_by_type(diff, "acao_prevista")
    pendencias_tipo = count_rows_by_type(pendencias, "tipo_pendencia")
    pendencias_severidade = count_rows_by_type(pendencias, "severidade")
    sample_groups = count_rows_by_type(samples, "grupo_amostra")

    return f"""# Revisao da carga previa DCB medicamentos

## Objetivo
Revisar a carga previa DCB antes de qualquer aplicacao no dicionario final, com foco em CAS duplicados, termos para revisao, colunas sem equivalente direto na DCB e decisao tecnica sobre uso como base de principios ativos.

## Arquivos analisados
- {CARGA_PATH.relative_to(BASE_DIR)}
- {DIFF_PATH.relative_to(BASE_DIR)}
- {DUPLICIDADES_PATH.relative_to(BASE_DIR)}
- {TERMOS_REVISAO_PATH.relative_to(BASE_DIR)}

## Totais
- Total de registros na carga: {len(carga)}
- Total de acoes previstas no diff: {len(diff)}
- Acoes previstas por tipo:
{markdown_counter(acoes)}
- Total de pendencias: {len(pendencias)}
- Pendencias bloqueantes: {total_bloqueantes}

## Pendencias por tipo
{markdown_counter(pendencias_tipo)}

## Pendencias por severidade
{markdown_counter(pendencias_severidade)}

## Pendencias que bloqueiam carga
{"- Nenhuma pendencia bloqueante identificada." if total_bloqueantes == 0 else "- Ha pendencias bloqueantes; revisar antes de aplicar."}

## Colunas sem equivalente na DCB
As colunas `sku_master_padrao`, `concentracao`, `forma_farmaceutica`, `apresentacao`, `via_uso` e `atc` permanecem vazias por desenho da carga previa. A DCB identifica denominacoes comuns e principios ativos, mas nao descreve apresentacao comercial completa. Essas lacunas nao bloqueiam a carga DCB como base de principio ativo.

Fontes recomendadas para fases posteriores:
- Medicamentos Registrados ANVISA
- Bulario ANVISA
- WHO ATC/DDD
- Catalogos ou compendios, quando necessario

## CAS duplicados
- Linhas de grupos de duplicidade analisadas: {len(duplicidades)}
- Registros de carga ligados a CAS duplicados: {sum(1 for row in pendencias if row.get("tipo_pendencia") == "CAS_DUPLICADO")}
- Avaliacao: CAS duplicados exigem revisao humana para uso analitico fino, pois podem representar sais, formas, substancias relacionadas ou referencias compartilhadas. Nao bloqueiam a carga como base de principio ativo.

## Termos para revisao
- Termos recebidos para revisao: {len(termos_revisao)}
- Pendencias TERMO_REVISAO geradas: {sum(1 for row in pendencias if row.get("tipo_pendencia") == "TERMO_REVISAO")}
- Avaliacao: os termos devem ser revisados por tamanho, caracteres incomuns ou motivo registrado, mas permanecem rastreados a fonte oficial ANVISA DCB e nao bloqueiam a carga base.

## Resumo da amostra
- Total de linhas na amostra: {len(samples)}
- Grupos de amostra:
{markdown_counter(sample_groups)}

## Decisao tecnica recomendada
{decisao}

A DCB deve entrar no Dicionario Mestre como base de principios ativos e denominacoes oficiais, nao como apresentacao comercial. Concentracao, forma farmaceutica, apresentacao, via de uso e ATC devem ser enriquecidos em fases posteriores com fontes apropriadas.

## Confirmacoes
- Nenhum dicionario final foi alterado.
- Nenhuma fonte interna foi usada.
- Nenhum banco foi alterado.
- Nenhum SKU_MASTER foi aplicado.
- Nenhuma mesclagem foi feita.
"""


def main() -> None:
    carga = read_csv(CARGA_PATH)
    diff = read_csv(DIFF_PATH)
    duplicidades = read_csv(DUPLICIDADES_PATH)
    termos_revisao = read_csv(TERMOS_REVISAO_PATH)

    samples = build_samples(carga, diff, duplicidades, termos_revisao)
    pendencias = build_pendencias(carga, duplicidades, termos_revisao)
    report = build_report(carga, diff, duplicidades, termos_revisao, samples, pendencias)

    write_csv(AMOSTRA_PATH, AMOSTRA_FIELDS, samples)
    write_csv(PENDENCIAS_PATH, PENDENCIA_FIELDS, pendencias)
    RELATORIO_PATH.write_text(report, encoding="utf-8")

    total_bloqueantes = sum(1 for row in pendencias if row.get("bloqueia_carga") == "SIM")
    decisao = "REVISAR_ANTES_DE_APLICAR" if total_bloqueantes else "APROVAR_CARGA_DCB_BASE_PRINCIPIO_ATIVO"
    print(f"registros_carga={len(carga)}")
    print(f"acoes_previstas={len(diff)}")
    print(f"pendencias={len(pendencias)}")
    print(f"pendencias_bloqueantes={total_bloqueantes}")
    print(f"decisao={decisao}")
    print(f"amostra={AMOSTRA_PATH}")
    print(f"pendencias_csv={PENDENCIAS_PATH}")
    print(f"relatorio={RELATORIO_PATH}")


if __name__ == "__main__":
    main()
