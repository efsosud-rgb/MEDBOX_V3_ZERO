"""
Processamento intermediario da ANVISA DCB.

Le o XLSX bruto oficial e gera CSV normalizado em UTF-8 com BOM.
Nao acessa internet, banco ou fontes internas.
Nao altera o arquivo bruto.
Nao mescla no Dicionario Mestre final.
Reexecutavel com segurança (sobrescreve saida anterior).
"""

import csv
import unicodedata
from datetime import date
from pathlib import Path

import openpyxl

# ── Caminhos ──────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[2]
XLSX_BRUTO = ROOT / "data/dicionario_mestre/bruto/anvisa/anvisa_dcb_lista_consolidada_in_439_2026_original.xlsx"
CSV_SAIDA = ROOT / "data/dicionario_mestre/processado/anvisa_dcb_normalizada.csv"
RELATORIO = ROOT / "data/dicionario_mestre/processado/relatorio_processamento_anvisa_dcb.md"

# ── Constantes da fonte ────────────────────────────────────────────────────────
FONTE = "ANVISA_DCB"
VERSAO_FONTE = "IN 439/2026"
STATUS_FONTE = "VIGENTE"
DATA_PROCESSAMENTO = date.today().isoformat()

# ── Colunas de saida ──────────────────────────────────────────────────────────
COLUNAS = [
    "id_registro",
    "fonte",
    "versao_fonte",
    "status_fonte",
    "termo_dcb",
    "termo_dcb_normalizado",
    "numero_cas",
    "tipo_registro",
    "observacao_fonte",
    "linha_origem",
    "arquivo_origem",
    "data_processamento",
    "status_processamento",
]

# ── Normalização de texto ──────────────────────────────────────────────────────
def normalizar(texto: str) -> str:
    """Maiusculas, sem acentos, espaços normalizados."""
    if not texto:
        return ""
    sem_acento = unicodedata.normalize("NFD", texto)
    sem_acento = "".join(c for c in sem_acento if unicodedata.category(c) != "Mn")
    return " ".join(sem_acento.upper().split())


# ── Leitura do XLSX ───────────────────────────────────────────────────────────
def ler_xlsx():
    wb = openpyxl.load_workbook(str(XLSX_BRUTO), read_only=True, data_only=True)
    aba = "Lista DCB Consolidada"
    ws = wb[aba]
    linhas = list(ws.iter_rows(values_only=True))
    wb.close()
    return aba, linhas


# ── Processamento ─────────────────────────────────────────────────────────────
def processar():
    assert XLSX_BRUTO.exists(), f"XLSX bruto nao encontrado: {XLSX_BRUTO}"

    aba, linhas = ler_xlsx()

    # L1 = título, L2 = cabeçalho, L3+ = dados, última linha pode ser vazia
    cabecalho_xlsx = linhas[1]  # linha 2 (índice 1)
    dados_brutos = linhas[2:]   # a partir da linha 3

    stats = {
        "total_linhas_xlsx": len(linhas),
        "total_linhas_dados_brutos": len(dados_brutos),
        "exportados": 0,
        "sem_termo": 0,
        "sem_cas": 0,
        "sem_classificacao": 0,
        "status_ok": 0,
        "status_incompleto": 0,
        "status_revisar": 0,
    }

    registros = []
    for idx_rel, row in enumerate(dados_brutos, start=1):
        linha_xlsx = idx_rel + 2  # linha real no XLSX (L1=titulo, L2=cabec, L3+=dados)

        # ignorar linhas completamente vazias
        if all(c is None for c in row):
            continue

        num_dcb = row[0]          # col A: Nº DCB (int ou None)
        termo = row[1]             # col B: DENOMINAÇÃO COMUM BRASILEIRA
        cas = row[2]               # col C: Nº CAS
        classificacao = row[3]     # col D: CLASSIFICAÇÃO
        historico = row[4]         # col E: HISTÓRICO

        termo_str = str(termo).strip() if termo is not None else ""
        cas_str = str(cas).strip() if cas is not None else ""
        classif_str = str(classificacao).strip() if classificacao is not None else ""
        hist_str = str(historico).strip() if historico is not None else ""
        id_reg = str(int(num_dcb)) if num_dcb is not None else f"L{linha_xlsx}"

        # semicolons dentro de campos — substituir por virgula para segurança do CSV
        termo_str = termo_str.replace(";", ",")
        cas_str = cas_str.replace(";", ",")
        classif_str = classif_str.replace(";", ",")
        hist_str = hist_str.replace(";", ",")

        # status_processamento
        if not termo_str:
            stats["sem_termo"] += 1
            status_proc = "REVISAR"
            stats["status_revisar"] += 1
        elif not cas_str and not classif_str:
            status_proc = "INCOMPLETO"
            stats["status_incompleto"] += 1
        else:
            status_proc = "OK"
            stats["status_ok"] += 1

        if not cas_str:
            stats["sem_cas"] += 1
        if not classif_str:
            stats["sem_classificacao"] += 1

        registros.append({
            "id_registro": id_reg,
            "fonte": FONTE,
            "versao_fonte": VERSAO_FONTE,
            "status_fonte": STATUS_FONTE,
            "termo_dcb": termo_str,
            "termo_dcb_normalizado": normalizar(termo_str),
            "numero_cas": cas_str,
            "tipo_registro": classif_str,
            "observacao_fonte": hist_str,
            "linha_origem": str(linha_xlsx),
            "arquivo_origem": str(XLSX_BRUTO.relative_to(ROOT)).replace("\\", "/"),
            "data_processamento": DATA_PROCESSAMENTO,
            "status_processamento": status_proc,
        })

    stats["exportados"] = len(registros)

    # ── Escrever CSV (UTF-8 com BOM, separador ";") ───────────────────────────
    CSV_SAIDA.parent.mkdir(parents=True, exist_ok=True)
    with CSV_SAIDA.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUNAS, delimiter=";", extrasaction="raise")
        writer.writeheader()
        writer.writerows(registros)

    print(f"CSV gerado: {CSV_SAIDA}")
    print(f"Registros exportados: {stats['exportados']}")
    print(f"Sem termo DCB: {stats['sem_termo']}")
    print(f"Sem CAS: {stats['sem_cas']}")
    print(f"Status OK: {stats['status_ok']} | INCOMPLETO: {stats['status_incompleto']} | REVISAR: {stats['status_revisar']}")

    # ── Gerar relatorio ───────────────────────────────────────────────────────
    primeiros_10 = registros[:10]
    linhas_exemplo = "\n".join(
        f"| {r['id_registro']} | {r['termo_dcb']} | {r['termo_dcb_normalizado']} "
        f"| {r['numero_cas']} | {r['tipo_registro']} | {r['status_processamento']} |"
        for r in primeiros_10
    )

    relatorio_md = f"""# Relatório de Processamento — ANVISA DCB
**Data:** {DATA_PROCESSAMENTO}
**Fase:** FASE 1.1 — Processamento intermediário ANVISA DCB

---

## Objetivo

Ler o XLSX bruto oficial da ANVISA DCB capturado na FASE 1 e gerar CSV normalizado intermediário,
sem mesclar em nenhum Dicionário Mestre e sem acessar banco ou fontes internas.

---

## Arquivo Bruto Lido

- **Caminho:** `{str(XLSX_BRUTO.relative_to(ROOT)).replace(chr(92), "/")}`
- **Versão:** {VERSAO_FONTE}
- **Status da fonte:** {STATUS_FONTE}
- **Total de linhas no XLSX (incluindo título e cabeçalho):** {stats["total_linhas_xlsx"]}

---

## Abas Encontradas

| Aba | Usada |
|-----|-------|
| Lista DCB Consolidada | Sim |

---

## Estrutura do XLSX

- **L1:** Título da planilha (ignorado)
- **L2:** Cabeçalho das colunas
- **L3 em diante:** Dados da lista DCB
- **Última linha:** Vazia (ignorada)

---

## Colunas Encontradas no XLSX

| Posição | Nome original | Mapeado para |
|---------|--------------|--------------|
| A | Nº DCB | id_registro |
| B | DENOMINAÇÃO COMUM BRASILEIRA | termo_dcb / termo_dcb_normalizado |
| C | Nº CAS | numero_cas |
| D | CLASSIFICAÇÃO | tipo_registro |
| E | HISTÓRICO | observacao_fonte |
| F–K | (vazias) | ignoradas |

---

## Totais

| Métrica | Valor |
|---------|-------|
| Linhas brutas no XLSX (total) | {stats["total_linhas_xlsx"]} |
| Linhas de dados processadas | {stats["total_linhas_dados_brutos"]} |
| Registros exportados | {stats["exportados"]} |
| Registros sem termo DCB | {stats["sem_termo"]} |
| Registros sem CAS | {stats["sem_cas"]} |
| Registros sem classificação | {stats["sem_classificacao"]} |
| Status OK | {stats["status_ok"]} |
| Status INCOMPLETO | {stats["status_incompleto"]} |
| Status REVISAR | {stats["status_revisar"]} |

---

## Primeiras 10 Linhas Normalizadas

| Nº DCB | Termo DCB | Normalizado | CAS | Tipo | Status |
|--------|-----------|-------------|-----|------|--------|
{linhas_exemplo}

---

## Confirmações de Integridade

- Nenhum banco de dados foi acessado ou alterado.
- Nenhum SQL foi executado.
- Nenhuma fonte interna foi consultada.
- Nenhum download adicional foi realizado.
- O arquivo XLSX bruto foi preservado sem edição.
- Nenhuma mesclagem no Dicionário Mestre foi executada.
- Nenhum SKU_MASTER foi aplicado.
- `app.py`, `core/`, `templates/`, `uploads/`, `backups/`, `.claude/` não foram alterados.

---

## Próxima Etapa Recomendada

Com o CSV intermediário validado, a próxima etapa é:
- validar amostra do CSV normalizado com revisão humana;
- definir mapeamento final de colunas para o Dicionário Mestre;
- somente então mesclar ao Dicionário Mestre, em etapa separada e autorizada.
"""
    with RELATORIO.open("w", encoding="utf-8") as f:
        f.write(relatorio_md)

    print(f"Relatorio gerado: {RELATORIO}")
    return stats


if __name__ == "__main__":
    processar()
