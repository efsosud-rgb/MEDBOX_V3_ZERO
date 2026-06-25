"""
Gera prévia auditável de integração da ANVISA DCB para o formato futuro
do dicionário de medicamentos.

Entrada:  data/dicionario_mestre/processado/anvisa_dcb_normalizada.csv
Saída:    data/dicionario_mestre/processado/pre_dicionario_medicamentos_anvisa_dcb.csv
          data/dicionario_mestre/processado/relatorio_previa_dicionario_medicamentos_anvisa_dcb.md

Não acessa internet, banco ou fontes internas.
Não altera dicionários finais.
Reexecutável com segurança.
"""

import csv
from collections import Counter
from datetime import datetime
from pathlib import Path

# ── Caminhos ──────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[2]
CSV_ENTRADA = ROOT / "data/dicionario_mestre/processado/anvisa_dcb_normalizada.csv"
CSV_SAIDA   = ROOT / "data/dicionario_mestre/processado/pre_dicionario_medicamentos_anvisa_dcb.csv"
RELATORIO   = ROOT / "data/dicionario_mestre/processado/relatorio_previa_dicionario_medicamentos_anvisa_dcb.md"

# ── Mapeamento de subcategoria ─────────────────────────────────────────────────
SUBCATEGORIA = {
    "IFA": "INSUMO FARMACEUTICO ATIVO",
    "INF": "INSUMO FARMACEUTICO",
    "BIO": "BIOLOGICO",
    "EXA": "EXTRATO",
    "HOM": "HOMEOPATICO",
    "PM":  "PRODUTO MANUTENCAO",
    "RAD": "RADIOFARMACO",
}

# ── Colunas de saída ──────────────────────────────────────────────────────────
COLUNAS = [
    "id_previa",
    "fonte",
    "versao_fonte",
    "status_fonte",
    "tipo_item",
    "termo_oficial",
    "termo_normalizado",
    "numero_cas",
    "classificacao_dcb",
    "historico_dcb",
    "categoria_medbox_sugerida",
    "subcategoria_sugerida",
    "uso_sugerido_no_dicionario",
    "confianca_fonte",
    "status_validacao",
    "motivo_status",
    "arquivo_origem",
    "linha_origem",
    "data_geracao",
]


def gerar():
    assert CSV_ENTRADA.exists(), f"Arquivo de entrada nao encontrado: {CSV_ENTRADA}"

    data_geracao = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    arquivo_origem = str(CSV_ENTRADA.relative_to(ROOT)).replace("\\", "/")

    # ── Leitura ───────────────────────────────────────────────────────────────
    with CSV_ENTRADA.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, delimiter=";")
        entrada = list(reader)

    total_lidos = len(entrada)

    # ── Geração dos registros de prévia ───────────────────────────────────────
    registros = []
    for row in entrada:
        id_reg      = row.get("id_registro", "").strip()
        termo       = row.get("termo_dcb", "").strip()
        normalizado = row.get("termo_dcb_normalizado", "").strip()
        cas         = row.get("numero_cas", "").strip()
        classif     = row.get("tipo_registro", "").strip()
        historico   = row.get("observacao_fonte", "").strip()
        linha_orig  = row.get("linha_origem", "").strip()

        # id_previa com zero à esquerda
        try:
            id_previa = f"DCB_{int(id_reg):06d}"
        except (ValueError, TypeError):
            id_previa = f"DCB_{id_reg}"

        # subcategoria com base na classificação oficial
        subcategoria = SUBCATEGORIA.get(classif, "REVISAR")

        # status_validacao
        if termo and cas:
            status_val = "PRE_VALIDADO_FONTE_OFICIAL"
            motivo     = "FONTE_OFICIAL_ANVISA_DCB_COMPLETA"
        else:
            status_val = "REVISAR"
            motivo     = "AUSENCIA_TERMO_OU_CAS"

        registros.append({
            "id_previa":                   id_previa,
            "fonte":                       "ANVISA_DCB",
            "versao_fonte":                "IN 439/2026",
            "status_fonte":                "VIGENTE",
            "tipo_item":                   "DCB",
            "termo_oficial":               termo,
            "termo_normalizado":           normalizado,
            "numero_cas":                  cas,
            "classificacao_dcb":           classif,
            "historico_dcb":               historico,
            "categoria_medbox_sugerida":   "MEDICAMENTO",
            "subcategoria_sugerida":       subcategoria,
            "uso_sugerido_no_dicionario":  "BASE_PRINCIPIO_ATIVO",
            "confianca_fonte":             "ALTA",
            "status_validacao":            status_val,
            "motivo_status":               motivo,
            "arquivo_origem":              arquivo_origem,
            "linha_origem":                linha_orig,
            "data_geracao":                data_geracao,
        })

    # ── Escrever CSV ──────────────────────────────────────────────────────────
    CSV_SAIDA.parent.mkdir(parents=True, exist_ok=True)
    with CSV_SAIDA.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUNAS, delimiter=";", extrasaction="raise")
        writer.writeheader()
        writer.writerows(registros)

    # ── Estatísticas ──────────────────────────────────────────────────────────
    cnt_classif   = Counter(r["classificacao_dcb"] for r in registros)
    cnt_subcat    = Counter(r["subcategoria_sugerida"] for r in registros)
    cnt_status    = Counter(r["status_validacao"] for r in registros)

    print(f"Registros lidos:     {total_lidos}")
    print(f"Registros exportados:{len(registros)}")
    print(f"Por classificacao:   {dict(sorted(cnt_classif.items()))}")
    print(f"Por subcategoria:    {dict(sorted(cnt_subcat.items()))}")
    print(f"Por status:          {dict(cnt_status.items())}")

    # ── Relatório ─────────────────────────────────────────────────────────────
    def tabela_contagem(cnt):
        return "\n".join(
            f"| {k} | {v} |" for k, v in sorted(cnt.items(), key=lambda x: -x[1])
        )

    exemplos = "\n".join(
        f"| {r['id_previa']} | {r['termo_oficial']} | {r['termo_normalizado']} "
        f"| {r['numero_cas']} | {r['classificacao_dcb']} | {r['subcategoria_sugerida']} "
        f"| {r['status_validacao']} |"
        for r in registros[:10]
    )

    relatorio_md = f"""# Relatório de Prévia — Dicionário de Medicamentos ANVISA DCB
**Data:** {data_geracao[:10]}
**Fase:** FASE 1.2 — Prévia de integração DCB para medicamentos

---

## Objetivo

Gerar prévia auditável de integração da ANVISA DCB para o formato futuro do dicionário de
medicamentos, sem alterar o dicionário final. Serve como base para revisão humana antes
de qualquer decisão de mesclagem.

---

## Arquivos

| | Caminho |
|--|---------|
| Entrada | `{arquivo_origem}` |
| Saída   | `data/dicionario_mestre/processado/pre_dicionario_medicamentos_anvisa_dcb.csv` |

---

## Totais

| Métrica | Valor |
|---------|-------|
| Registros lidos | {total_lidos} |
| Registros exportados | {len(registros)} |
| Todos preservados | {'Sim' if total_lidos == len(registros) else 'NÃO'} |

---

## Contagem por Classificação DCB

| Classificação | Registros |
|--------------|-----------|
{tabela_contagem(cnt_classif)}

---

## Contagem por Subcategoria Sugerida

| Subcategoria | Registros |
|-------------|-----------|
{tabela_contagem(cnt_subcat)}

---

## Contagem por Status de Validação

| Status | Registros |
|--------|-----------|
{tabela_contagem(cnt_status)}

---

## Primeiros 10 Exemplos

| ID Prévia | Termo Oficial | Normalizado | CAS | Classif. | Subcategoria | Status |
|-----------|--------------|-------------|-----|----------|--------------|--------|
{exemplos}

---

## Confirmações de Integridade

- Nenhum banco de dados foi acessado ou alterado.
- Nenhum SQL foi executado.
- Nenhuma fonte interna foi consultada.
- Nenhum download foi realizado.
- Nenhum dicionário final foi alterado (`dicionario_mestre_medbox.csv`,
  `dicionario_mestre_medicamentos.csv`, `dicionario_mestre_produtos_saude.csv`).
- Nenhum SKU_MASTER foi aplicado.
- `app.py`, `core/`, `templates/`, `uploads/`, `backups/`, `.claude/` não foram alterados.
- Todos os {total_lidos} registros da DCB normalizada foram preservados na prévia.

---

## Próxima Etapa Recomendada

Revisar amostra da prévia (`pre_dicionario_medicamentos_anvisa_dcb.csv`) antes de
decidir se será aplicada ao `dicionario_mestre_medicamentos.csv`. A aplicação deve
ocorrer em etapa separada, com autorização explícita, e nunca de forma automática.
"""
    with RELATORIO.open("w", encoding="utf-8") as f:
        f.write(relatorio_md)

    print(f"Relatorio gerado: {RELATORIO}")
    return {
        "total_lidos": total_lidos,
        "total_exportados": len(registros),
        "cnt_classif": cnt_classif,
        "cnt_subcat": cnt_subcat,
        "cnt_status": cnt_status,
    }


if __name__ == "__main__":
    gerar()
