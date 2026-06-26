"""Prepara plano de download estruturado multi-fonte MEDREG.

FASE 2.14F: por padrao roda em DRY_RUN e nao baixa bases.
Nao altera banco, nao altera dicionarios finais, nao usa fonte interna e nao
consulta ANVISA Consultas por registro.
"""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

DRY_RUN = True
MAX_BYTES_POR_FONTE = 100 * 1024 * 1024
TIMEOUT_SEGUNDOS = 60
PAUSA_SEGUNDOS = 2
ROOT_BRUTO = Path("data/dicionario_mestre/bruto").resolve()
PLANO_CSV = Path("data/dicionario_mestre/processado/plano_download_fontes_estruturadas_medreg.csv")
LOG_CSV = Path("data/dicionario_mestre/processado/log_download_fontes_estruturadas_medreg.csv")

FONTES = [
    {
        "id": "medicamentos_registrados_dados_gov_br",
        "nome": "Medicamentos registrados no Brasil / dados.gov.br",
        "url_pagina": "https://dados.gov.br/dados/conjuntos-dados/medicamentos-registrados-no-brasil",
        "tipo": "oficial_primaria_csv",
        "destino_planejado": "data/dicionario_mestre/bruto/medreg/medicamentos_registrados_brasil/",
        "baixar_nesta_fase": False,
        "observacao": "Fonte estruturada principal; download real deve ser autorizado na FASE 2.14G.",
    },
    {
        "id": "dados_abertos_anvisa",
        "nome": "Dados Abertos ANVISA",
        "url_pagina": "https://www.gov.br/anvisa/pt-br/acessoainformacao/dadosabertos",
        "tipo": "catalogo_oficial",
        "destino_planejado": "data/dicionario_mestre/bruto/anvisa/dados_abertos/",
        "baixar_nesta_fase": False,
        "observacao": "Catalogo oficial; selecionar bases especificas antes de baixar.",
    },
    {
        "id": "cmed_listas_precos",
        "nome": "CMED listas de precos",
        "url_pagina": "https://www.gov.br/anvisa/pt-br/assuntos/medicamentos/cmed/precos",
        "tipo": "oficial_complementar_xls_pdf_powerbi",
        "destino_planejado": "data/dicionario_mestre/bruto/cmed/listas_precos/",
        "baixar_nesta_fase": False,
        "observacao": "Complementar para apresentacao, concentracao comercial e codigo GGREM.",
    },
    {
        "id": "dcb_anvisa",
        "nome": "DCB ANVISA",
        "url_pagina": "https://www.gov.br/anvisa/pt-br/assuntos/farmacopeia/dcb",
        "tipo": "oficial_primaria_vocabulario",
        "destino_planejado": "data/dicionario_mestre/bruto/anvisa/dcb/",
        "baixar_nesta_fase": False,
        "observacao": "Referencia para DCB, CAS, sinonimos e principio ativo.",
    },
    {
        "id": "farmacopeia_vocabularios",
        "nome": "Farmacopeia/vocabularios controlados",
        "url_pagina": "https://www.gov.br/anvisa/pt-br/assuntos/farmacopeia/farmacopeia-brasileira",
        "tipo": "oficial_complementar_pdf_html",
        "destino_planejado": "data/dicionario_mestre/bruto/anvisa/farmacopeia_vocabularios/",
        "baixar_nesta_fase": False,
        "observacao": "Apoio para termos padronizados de forma farmaceutica e via de administracao.",
    },
    {
        "id": "bulario_eletronico_anvisa",
        "nome": "Bulario Eletronico ANVISA",
        "url_pagina": "https://www.gov.br/anvisa/pt-br/sistemas/bulario-eletronico",
        "tipo": "oficial_complementar_textual",
        "destino_planejado": "data/dicionario_mestre/bruto/anvisa/bulario/",
        "baixar_nesta_fase": False,
        "observacao": "Somente pagina/fonte complementar futura; sem captura textual nesta fase.",
    },
    {
        "id": "anvisa_consultas_fallback",
        "nome": "ANVISA Consultas fallback futuro",
        "url_pagina": "https://consultas.anvisa.gov.br/#/medicamentos/",
        "tipo": "fallback_individual_controlado",
        "destino_planejado": "data/dicionario_mestre/bruto/anvisa/consultas_fallback/",
        "baixar_nesta_fase": False,
        "observacao": "Nao consultar por registro nesta fase; fallback futuro lento e controlado.",
    },
]


def agora() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def destino_seguro(destino: str) -> bool:
    caminho = Path(destino).resolve()
    try:
        caminho.relative_to(ROOT_BRUTO)
    except ValueError:
        return False
    return True


def registrar_log(linhas: list[dict[str, str]], fonte_id: str, etapa: str, status: str, mensagem: str) -> None:
    linhas.append(
        {
            "data_hora": agora(),
            "fonte_id": fonte_id,
            "etapa": etapa,
            "status": status,
            "mensagem": mensagem,
        }
    )


def montar_plano() -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    plano: list[dict[str, str]] = []
    logs: list[dict[str, str]] = []

    for fonte in FONTES:
        fonte_id = fonte["id"]
        if not destino_seguro(fonte["destino_planejado"]):
            status = "ERRO_DESTINO_FORA_BRUTO"
            mensagem = "Destino planejado fora de data/dicionario_mestre/bruto/."
            registrar_log(logs, fonte_id, "validar_destino", "ERRO", mensagem)
        elif DRY_RUN:
            status = "DRY_RUN_PLANEJADO"
            mensagem = "DRY_RUN=True; nenhum download executado."
            registrar_log(logs, fonte_id, "montar_plano", "OK", mensagem)
        elif not fonte["baixar_nesta_fase"]:
            status = "NAO_AUTORIZADO_NESTA_FASE"
            mensagem = "Fonte mantida no plano, mas sem autorizacao de download."
            registrar_log(logs, fonte_id, "validar_autorizacao", "OK", mensagem)
        else:
            status = "PENDENTE_IMPLEMENTACAO_DOWNLOAD_CONTROLADO"
            mensagem = "Download real deve ser implementado fonte a fonte com autorizacao explicita."
            registrar_log(logs, fonte_id, "download", "NAO_EXECUTADO", mensagem)

        plano.append(
            {
                "fonte_id": fonte_id,
                "nome": fonte["nome"],
                "url_pagina": fonte["url_pagina"],
                "tipo": fonte["tipo"],
                "destino_planejado": fonte["destino_planejado"],
                "baixar_nesta_fase": str(fonte["baixar_nesta_fase"]),
                "status": status,
                "observacao": fonte["observacao"],
            }
        )

    return plano, logs


def escrever_csv(caminho: Path, linhas: list[dict[str, str]], campos: list[str]) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("w", newline="", encoding="utf-8") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=campos)
        escritor.writeheader()
        escritor.writerows(linhas)


def main() -> int:
    plano, logs = montar_plano()
    escrever_csv(
        PLANO_CSV,
        plano,
        ["fonte_id", "nome", "url_pagina", "tipo", "destino_planejado", "baixar_nesta_fase", "status", "observacao"],
    )
    escrever_csv(LOG_CSV, logs, ["data_hora", "fonte_id", "etapa", "status", "mensagem"])
    print(f"DRY_RUN={DRY_RUN}; fontes planejadas={len(plano)}; download_real_executado=False")
    print(f"Plano: {PLANO_CSV}")
    print(f"Log: {LOG_CSV}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
