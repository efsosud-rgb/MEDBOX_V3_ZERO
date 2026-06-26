"""
Processamento intermediario ANVISA Medicamentos Registrados
FASE 2.2 — Sem alteracao de dicionario final, banco, fonte interna ou SKU_MASTER.
"""

import csv
import json
import os
import re
import sys
import html
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Caminhos
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent.parent
ARQUIVO_BRUTO = ROOT / "data/dicionario_mestre/bruto/anvisa/anvisa_medicamentos_registrados_original.csv"
DIR_PROCESSADO = ROOT / "data/dicionario_mestre/processado"
ARQUIVO_NORMALIZADO = DIR_PROCESSADO / "anvisa_medicamentos_registrados_normalizado.csv"
ARQUIVO_PERFIL = DIR_PROCESSADO / "perfil_anvisa_medicamentos_registrados.csv"
ARQUIVO_RELATORIO = DIR_PROCESSADO / "relatorio_processamento_anvisa_medicamentos_registrados.md"
ARQUIVO_HISTORICO = DIR_PROCESSADO / "historico_capturas_fontes.csv"

FONTE = "ANVISA_MEDICAMENTOS_REGISTRADOS"
VERSAO_FONTE = "DADOS_ABERTOS_MEDICAMENTOS"
ARQUIVO_ORIGEM_REL = "data/dicionario_mestre/bruto/anvisa/anvisa_medicamentos_registrados_original.csv"
DATA_PROCESSAMENTO = datetime.now().strftime("%Y-%m-%d")

# Colunas obrigatorias do intermediario
COLUNAS_SAIDA = [
    "id_registro_processamento",
    "fonte",
    "versao_fonte",
    "arquivo_origem",
    "linha_origem",
    "nome_produto",
    "principio_ativo",
    "principio_ativo_normalizado",
    "empresa_detentora",
    "cnpj_empresa",
    "numero_registro",
    "categoria_regulatoria",
    "tipo_produto",
    "situacao_registro",
    "data_registro",
    "data_validade",
    "processo",
    "classe_terapeutica",
    "forma_farmaceutica",
    "concentracao",
    "apresentacao",
    "via_uso",
    "restricao_prescricao",
    "tarja",
    "campo_original_json",
    "status_processamento",
    "motivo_status",
]

# Mapeamento de colunas brutas para padronizadas
MAPA_COLUNAS = {
    "TIPO_PRODUTO": "tipo_produto",
    "NOME_PRODUTO": "nome_produto",
    "DATA_FINALIZACAO_PROCESSO": "data_registro",
    "CATEGORIA_REGULATORIA": "categoria_regulatoria",
    "NUMERO_REGISTRO_PRODUTO": "numero_registro",
    "DATA_VENCIMENTO_REGISTRO": "data_validade",
    "NUMERO_PROCESSO": "processo",
    "CLASSE_TERAPEUTICA": "classe_terapeutica",
    "EMPRESA_DETENTORA_REGISTRO": "_empresa_raw",
    "SITUACAO_REGISTRO": "situacao_registro",
    "PRINCIPIO_ATIVO": "principio_ativo",
}

# Colunas esperadas que nao existem no bruto
COLUNAS_AUSENTES = [
    "forma_farmaceutica",
    "concentracao",
    "apresentacao",
    "via_uso",
    "restricao_prescricao",
    "tarja",
]


# ---------------------------------------------------------------------------
# Utilitarios
# ---------------------------------------------------------------------------

def detectar_encoding(caminho: Path) -> str:
    tentativas = ["utf-8-sig", "utf-8", "cp1252", "latin-1"]
    for enc in tentativas:
        try:
            with open(caminho, "r", encoding=enc, errors="strict") as f:
                f.readline()
            return enc
        except (UnicodeDecodeError, LookupError):
            continue
    return "latin-1"


def limpar_campo(valor: str) -> str:
    if not valor:
        return ""
    return html.unescape(valor.strip())


def extrair_cnpj_empresa(campo_raw: str):
    campo_raw = limpar_campo(campo_raw)
    if not campo_raw:
        return "", ""
    m = re.match(r"^(\d{14})\s*-\s*(.+)$", campo_raw)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return "", campo_raw


def normalizar_principio_ativo(pa: str) -> str:
    if not pa:
        return ""
    return pa.strip().upper()


def determinar_status(row: dict):
    nome = row.get("nome_produto", "").strip()
    pa = row.get("principio_ativo", "").strip()
    num = row.get("numero_registro", "").strip()
    if nome or pa or num:
        return "OK", ""
    return "REVISAR", "nome_produto, principio_ativo e numero_registro vazios"


# ---------------------------------------------------------------------------
# Processamento principal
# ---------------------------------------------------------------------------

def processar():
    print(f"[FASE 2.2] Iniciando processamento: {ARQUIVO_BRUTO}")
    assert ARQUIVO_BRUTO.exists(), f"ERRO: arquivo bruto nao encontrado: {ARQUIVO_BRUTO}"

    encoding_detectado = detectar_encoding(ARQUIVO_BRUTO)
    separador_detectado = ";"
    print(f"  Encoding detectado: {encoding_detectado}")

    registros_lidos = 0
    registros_exportados = 0
    registros_por_status = {"OK": 0, "REVISAR": 0, "ERRO_ESTRUTURA": 0}
    colunas_originais = []
    exemplos = []
    linhas_saida = []

    with open(ARQUIVO_BRUTO, "r", encoding=encoding_detectado, errors="replace", newline="") as f:
        reader = csv.DictReader(f, delimiter=separador_detectado, quotechar='"')
        colunas_originais = list(reader.fieldnames or [])

        for i, row in enumerate(reader, start=2):
            registros_lidos += 1

            if len(row) < len(colunas_originais):
                status_proc = "ERRO_ESTRUTURA"
                motivo = f"linha {i}: esperadas {len(colunas_originais)} colunas, encontradas {len(row)}"
            else:
                status_proc = None
                motivo = ""

            out = {c: "" for c in COLUNAS_SAIDA}
            out["id_registro_processamento"] = f"ANVREG_2026_{registros_lidos:06d}"
            out["fonte"] = FONTE
            out["versao_fonte"] = VERSAO_FONTE
            out["arquivo_origem"] = ARQUIVO_ORIGEM_REL
            out["linha_origem"] = str(i)

            original_limpo = {}
            for col_bruta, col_pad in MAPA_COLUNAS.items():
                val = limpar_campo(row.get(col_bruta, "") or "")
                original_limpo[col_bruta] = val
                if col_pad != "_empresa_raw":
                    out[col_pad] = val

            empresa_raw = limpar_campo(row.get("EMPRESA_DETENTORA_REGISTRO", "") or "")
            cnpj, nome_empresa = extrair_cnpj_empresa(empresa_raw)
            out["cnpj_empresa"] = cnpj
            out["empresa_detentora"] = nome_empresa

            out["principio_ativo_normalizado"] = normalizar_principio_ativo(out["principio_ativo"])

            for col in COLUNAS_AUSENTES:
                out[col] = ""

            out["campo_original_json"] = json.dumps(
                {k: (v or "") for k, v in row.items() if v is not None},
                ensure_ascii=False,
            )

            if status_proc == "ERRO_ESTRUTURA":
                out["status_processamento"] = "ERRO_ESTRUTURA"
                out["motivo_status"] = motivo
                registros_por_status["ERRO_ESTRUTURA"] += 1
            else:
                status_proc, motivo = determinar_status(out)
                out["status_processamento"] = status_proc
                out["motivo_status"] = motivo
                registros_por_status[status_proc] += 1

            linhas_saida.append(out)
            registros_exportados += 1

            if len(exemplos) < 10 and status_proc == "OK":
                exemplos.append(out)

    print(f"  Registros lidos: {registros_lidos}")
    print(f"  Registros exportados: {registros_exportados}")
    print(f"  Status: {registros_por_status}")

    # Escrever normalizado (UTF-8 com BOM)
    DIR_PROCESSADO.mkdir(parents=True, exist_ok=True)
    with open(ARQUIVO_NORMALIZADO, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUNAS_SAIDA, delimiter=";", quotechar='"', quoting=csv.QUOTE_MINIMAL)
        writer.writeheader()
        writer.writerows(linhas_saida)
    print(f"  Normalizado gravado: {ARQUIVO_NORMALIZADO}")

    # Validar colunas do normalizado
    with open(ARQUIVO_NORMALIZADO, "r", encoding="utf-8-sig", newline="") as f:
        reader_val = csv.reader(f, delimiter=";")
        header_val = next(reader_val)
        n_cols = len(header_val)
        anomalias = 0
        for li, row_val in enumerate(reader_val, start=2):
            if len(row_val) != n_cols:
                anomalias += 1
        if anomalias:
            print(f"  AVISO: {anomalias} linhas com numero de colunas diferente do esperado ({n_cols})")
        else:
            print(f"  Validacao OK: todas as linhas com {n_cols} colunas")

    # -----------------------------------------------------------------------
    # Perfil
    # -----------------------------------------------------------------------
    perfil_rows = []

    for col_bruta, col_pad in MAPA_COLUNAS.items():
        if col_pad == "_empresa_raw":
            col_pad = "empresa_detentora"
        existe = col_bruta in colunas_originais
        valores = [r.get(col_pad, "") for r in linhas_saida]
        vazios = sum(1 for v in valores if not v)
        preenchidos = len(valores) - vazios
        pct = f"{100 * preenchidos / len(valores):.1f}%" if valores else "0%"
        ex = [v for v in valores if v][:3]
        perfil_rows.append({
            "coluna_original": col_bruta,
            "coluna_padronizada": col_pad,
            "existe_no_bruto": "sim" if existe else "nao",
            "total_registros": len(valores),
            "vazios": vazios,
            "preenchidos": preenchidos,
            "percentual_preenchido": pct,
            "exemplos": " | ".join(str(e)[:80] for e in ex),
            "observacao": "",
        })

    campos_gerados = [
        ("id_registro_processamento", "id_registro_processamento"),
        ("fonte", "fonte"),
        ("versao_fonte", "versao_fonte"),
        ("arquivo_origem", "arquivo_origem"),
        ("linha_origem", "linha_origem"),
        ("principio_ativo_normalizado", "principio_ativo_normalizado"),
        ("cnpj_empresa", "cnpj_empresa"),
        ("campo_original_json", "campo_original_json"),
        ("status_processamento", "status_processamento"),
        ("motivo_status", "motivo_status"),
    ]
    for col_orig, col_pad in campos_gerados:
        valores = [r.get(col_pad, "") for r in linhas_saida]
        vazios = sum(1 for v in valores if not v)
        preenchidos = len(valores) - vazios
        pct = f"{100 * preenchidos / len(valores):.1f}%" if valores else "0%"
        ex = [v for v in valores if v][:3]
        perfil_rows.append({
            "coluna_original": "(gerada)",
            "coluna_padronizada": col_pad,
            "existe_no_bruto": "nao",
            "total_registros": len(valores),
            "vazios": vazios,
            "preenchidos": preenchidos,
            "percentual_preenchido": pct,
            "exemplos": " | ".join(str(e)[:80] for e in ex),
            "observacao": "coluna gerada no processamento",
        })

    for col in COLUNAS_AUSENTES:
        perfil_rows.append({
            "coluna_original": "(ausente no bruto)",
            "coluna_padronizada": col,
            "existe_no_bruto": "nao",
            "total_registros": registros_exportados,
            "vazios": registros_exportados,
            "preenchidos": 0,
            "percentual_preenchido": "0.0%",
            "exemplos": "",
            "observacao": "campo esperado nao presente no arquivo bruto",
        })

    perfil_cols = [
        "coluna_original", "coluna_padronizada", "existe_no_bruto",
        "total_registros", "vazios", "preenchidos", "percentual_preenchido",
        "exemplos", "observacao",
    ]
    with open(ARQUIVO_PERFIL, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=perfil_cols, delimiter=";", quotechar='"', quoting=csv.QUOTE_MINIMAL)
        writer.writeheader()
        writer.writerows(perfil_rows)
    print(f"  Perfil gravado: {ARQUIVO_PERFIL}")

    # -----------------------------------------------------------------------
    # Relatorio
    # -----------------------------------------------------------------------
    colunas_ausentes_str = ", ".join(COLUNAS_AUSENTES)
    colunas_orig_str = ", ".join(colunas_originais)

    exemplos_md = ""
    for idx, ex in enumerate(exemplos, 1):
        exemplos_md += f"\n### Exemplo {idx}\n"
        exemplos_md += f"- **nome_produto**: {ex['nome_produto']}\n"
        exemplos_md += f"- **principio_ativo**: {ex['principio_ativo']}\n"
        exemplos_md += f"- **numero_registro**: {ex['numero_registro']}\n"
        exemplos_md += f"- **empresa_detentora**: {ex['empresa_detentora']}\n"
        exemplos_md += f"- **cnpj_empresa**: {ex['cnpj_empresa']}\n"
        exemplos_md += f"- **situacao_registro**: {ex['situacao_registro']}\n"
        exemplos_md += f"- **categoria_regulatoria**: {ex['categoria_regulatoria']}\n"
        exemplos_md += f"- **status_processamento**: {ex['status_processamento']}\n"

    perfil_resumido = ""
    for p in perfil_rows:
        if p["existe_no_bruto"] == "sim":
            perfil_resumido += f"- `{p['coluna_padronizada']}`: {p['percentual_preenchido']} preenchido ({p['preenchidos']}/{p['total_registros']})\n"

    relatorio = f"""# Relatorio de Processamento — ANVISA Medicamentos Registrados
## FASE 2.2 — {DATA_PROCESSAMENTO}

## Objetivo
Processar o CSV bruto da ANVISA Medicamentos Registrados para um arquivo intermediario auditavel,
sem alterar dicionario final, sem banco, sem fonte interna e sem SKU_MASTER.

## Arquivo bruto usado
`{ARQUIVO_ORIGEM_REL}`

## Encoding detectado / usado
`{encoding_detectado}`

## Separador detectado / usado
`{separador_detectado}` (ponto e virgula)

## Totais
- Total de linhas no bruto (com cabecalho): {registros_lidos + 1}
- Total de registros lidos: {registros_lidos}
- Total de registros exportados: {registros_exportados}

## Colunas originais encontradas ({len(colunas_originais)})
{colunas_orig_str}

## Colunas padronizadas geradas ({len(COLUNAS_SAIDA)})
{", ".join(COLUNAS_SAIDA)}

## Colunas esperadas nao encontradas no bruto
{colunas_ausentes_str}
(mantidas vazias no intermediario)

## Contagem por status_processamento
- OK: {registros_por_status["OK"]}
- REVISAR: {registros_por_status["REVISAR"]}
- ERRO_ESTRUTURA: {registros_por_status["ERRO_ESTRUTURA"]}

## Perfil resumido de preenchimento (colunas do bruto)
{perfil_resumido}
## 10 exemplos processados
{exemplos_md}

## Riscos e pendencias
- Encoding: arquivo apresenta caracteres especiais (entidades HTML e acentuados). Tratamento via html.unescape e errors=replace.
- DATA_FINALIZACAO_PROCESSO mapeada como data_registro.
- DATA_VENCIMENTO_REGISTRO mapeada como data_validade.
- CNPJ extraido de EMPRESA_DETENTORA_REGISTRO por regex; sem CNPJ detectavel, campo fica vazio.
- Campos de forma_farmaceutica, concentracao, apresentacao, via_uso, restricao_prescricao e tarja ausentes no bruto.
- Registros REVISAR devem ser revisados na FASE 2.3.

## Confirmacoes de integridade
- **Dicionario final nao alterado**: dicionario_mestre_medbox.csv, dicionario_mestre_medicamentos.csv e dicionario_mestre_produtos_saude.csv nao foram lidos nem modificados.
- **Banco nao usado**: nenhuma conexao com banco de dados foi realizada.
- **Fonte interna nao usada**: data/dicionario_mestre/interno nao foi acessado.
- **SKU_MASTER nao aplicado**: uploads/SKU_MASTER_*.xlsx nao foi acessado.
- **Bruto preservado intacto**: arquivo bruto aberto somente em modo leitura.

## Proxima etapa recomendada
**FASE 2.3 — Auditoria do intermediario**
- Revisar registros com status REVISAR e ERRO_ESTRUTURA.
- Avaliar preenchimento dos campos de identificacao.
- Planejar cruzamento com dicionario final (somente leitura do intermediario).
"""
    ARQUIVO_RELATORIO.write_text(relatorio, encoding="utf-8")
    print(f"  Relatorio gravado: {ARQUIVO_RELATORIO}")

    # -----------------------------------------------------------------------
    # Atualizar historico
    # -----------------------------------------------------------------------
    ID_CAPTURA = "ANVISA_MEDICAMENTOS_REGISTRADOS_20260626"
    historico_linhas = []
    historico_cols = None

    with open(ARQUIVO_HISTORICO, "r", encoding="utf-8-sig", newline="") as f:
        reader_h = csv.DictReader(f, delimiter=";", quotechar='"')
        historico_cols = list(reader_h.fieldnames or [])
        for row_h in reader_h:
            if row_h.get("id_captura") == ID_CAPTURA:
                row_h["processado"] = "sim"
                row_h["mesclado_dicionario"] = "nao"
                row_h["observacao"] = "processado para CSV intermediario, sem mesclagem"
            historico_linhas.append(row_h)

    assert len(historico_cols) == 18, f"ERRO: historico com {len(historico_cols)} colunas (esperado 18)"

    with open(ARQUIVO_HISTORICO, "w", encoding="utf-8-sig", newline="") as f:
        writer_h = csv.DictWriter(f, fieldnames=historico_cols, delimiter=";", quotechar='"', quoting=csv.QUOTE_MINIMAL)
        writer_h.writeheader()
        writer_h.writerows(historico_linhas)
    print(f"  Historico atualizado: {ARQUIVO_HISTORICO}")

    return {
        "encoding": encoding_detectado,
        "separador": separador_detectado,
        "registros_lidos": registros_lidos,
        "registros_exportados": registros_exportados,
        "registros_por_status": registros_por_status,
        "colunas_originais": colunas_originais,
    }


if __name__ == "__main__":
    resultado = processar()
    print("\n[FASE 2.2] Processamento concluido.")
    print(f"  OK: {resultado['registros_por_status']['OK']}")
    print(f"  REVISAR: {resultado['registros_por_status']['REVISAR']}")
    print(f"  ERRO_ESTRUTURA: {resultado['registros_por_status']['ERRO_ESTRUTURA']}")
