"""Download estruturado multi-fonte MEDREG.

Por padrao roda em DRY_RUN e apenas gera plano/log. Download real exige
--fonte <id> --executar e so esta implementado para fontes explicitamente
autorizadas fase a fase. Nao altera banco, nao altera dicionarios finais,
nao usa fonte interna e nao consulta ANVISA Consultas por registro.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

DRY_RUN = True
MAX_BYTES_POR_FONTE = 250 * 1024 * 1024
TIMEOUT_SEGUNDOS = 60
ROOT_BRUTO = Path("data/dicionario_mestre/bruto").resolve()
PLANO_CSV = Path("data/dicionario_mestre/processado/plano_download_fontes_estruturadas_medreg.csv")
LOG_CSV = Path("data/dicionario_mestre/processado/log_download_fontes_estruturadas_medreg.csv")
LOG_MEDICAMENTOS_CSV = Path("data/dicionario_mestre/processado/log_download_medicamentos_registrados_dados_gov.csv")
DESTINO_MEDICAMENTOS = Path("data/dicionario_mestre/bruto/medicamentos_registrados_dados_gov")
MANIFESTO_MEDICAMENTOS = DESTINO_MEDICAMENTOS / "manifesto_download.csv"
CKAN_API_MEDICAMENTOS = "https://dados.gov.br/dados/api/3/action/package_show?id=medicamentos-registrados-no-brasil"

FONTES = [
    {
        "id": "medicamentos_registrados_dados_gov",
        "aliases": ["medicamentos_registrados_dados_gov_br"],
        "nome": "Medicamentos registrados no Brasil / dados.gov.br",
        "url_pagina": "https://dados.gov.br/dados/conjuntos-dados/medicamentos-registrados-no-brasil",
        "tipo": "oficial_primaria_csv",
        "destino_planejado": str(DESTINO_MEDICAMENTOS),
        "baixar_nesta_fase": False,
        "observacao": "Fonte estruturada principal; download real autorizado apenas por --fonte e --executar.",
    },
    {
        "id": "dados_abertos_anvisa",
        "aliases": [],
        "nome": "Dados Abertos ANVISA",
        "url_pagina": "https://www.gov.br/anvisa/pt-br/acessoainformacao/dadosabertos",
        "tipo": "catalogo_oficial",
        "destino_planejado": "data/dicionario_mestre/bruto/anvisa/dados_abertos/",
        "baixar_nesta_fase": False,
        "observacao": "Catalogo oficial; selecionar bases especificas antes de baixar.",
    },
    {
        "id": "cmed_listas_precos",
        "aliases": [],
        "nome": "CMED listas de precos",
        "url_pagina": "https://www.gov.br/anvisa/pt-br/assuntos/medicamentos/cmed/precos",
        "tipo": "oficial_complementar_xls_pdf_powerbi",
        "destino_planejado": "data/dicionario_mestre/bruto/cmed/listas_precos/",
        "baixar_nesta_fase": False,
        "observacao": "Complementar para apresentacao, concentracao comercial e codigo GGREM.",
    },
    {
        "id": "dcb_anvisa",
        "aliases": [],
        "nome": "DCB ANVISA",
        "url_pagina": "https://www.gov.br/anvisa/pt-br/assuntos/farmacopeia/dcb",
        "tipo": "oficial_primaria_vocabulario",
        "destino_planejado": "data/dicionario_mestre/bruto/anvisa/dcb/",
        "baixar_nesta_fase": False,
        "observacao": "Referencia para DCB, CAS, sinonimos e principio ativo.",
    },
    {
        "id": "farmacopeia_vocabularios",
        "aliases": [],
        "nome": "Farmacopeia/vocabularios controlados",
        "url_pagina": "https://www.gov.br/anvisa/pt-br/assuntos/farmacopeia/farmacopeia-brasileira",
        "tipo": "oficial_complementar_pdf_html",
        "destino_planejado": "data/dicionario_mestre/bruto/anvisa/farmacopeia_vocabularios/",
        "baixar_nesta_fase": False,
        "observacao": "Apoio para termos padronizados de forma farmaceutica e via de administracao.",
    },
    {
        "id": "bulario_eletronico_anvisa",
        "aliases": [],
        "nome": "Bulario Eletronico ANVISA",
        "url_pagina": "https://www.gov.br/anvisa/pt-br/sistemas/bulario-eletronico",
        "tipo": "oficial_complementar_textual",
        "destino_planejado": "data/dicionario_mestre/bruto/anvisa/bulario/",
        "baixar_nesta_fase": False,
        "observacao": "Somente pagina/fonte complementar futura; sem captura textual nesta fase.",
    },
    {
        "id": "anvisa_consultas_fallback",
        "aliases": [],
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


def destino_seguro(destino: str | Path) -> bool:
    caminho = Path(destino).resolve()
    try:
        caminho.relative_to(ROOT_BRUTO)
    except ValueError:
        return False
    return True


def registrar_log(linhas: list[dict[str, str]], fonte_id: str, etapa: str, status: str, mensagem: str) -> None:
    linhas.append({"data_hora": agora(), "fonte_id": fonte_id, "etapa": etapa, "status": status, "mensagem": mensagem})


def registrar_log_simples(linhas: list[dict[str, str]], etapa: str, status: str, mensagem: str) -> None:
    linhas.append({"data_hora": agora(), "etapa": etapa, "status": status, "mensagem": mensagem})


def escrever_csv(caminho: Path, linhas: list[dict[str, str]], campos: list[str]) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("w", newline="", encoding="utf-8") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=campos)
        escritor.writeheader()
        escritor.writerows(linhas)


def normalizar_fonte(fonte_id: str | None) -> str | None:
    if not fonte_id:
        return None
    for fonte in FONTES:
        if fonte_id == fonte["id"] or fonte_id in fonte.get("aliases", []):
            return fonte["id"]
    return fonte_id


def fonte_por_id(fonte_id: str) -> dict[str, object] | None:
    fonte_id = normalizar_fonte(fonte_id) or fonte_id
    for fonte in FONTES:
        if fonte["id"] == fonte_id:
            return fonte
    return None


def montar_plano(fonte_selecionada: str | None = None, executar: bool = False) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    plano: list[dict[str, str]] = []
    logs: list[dict[str, str]] = []
    fonte_selecionada = normalizar_fonte(fonte_selecionada)

    for fonte in FONTES:
        fonte_id = str(fonte["id"])
        selecionada = fonte_selecionada == fonte_id if fonte_selecionada else False
        baixar_agora = bool(executar and selecionada and fonte_id == "medicamentos_registrados_dados_gov")

        if not destino_seguro(str(fonte["destino_planejado"])):
            status = "ERRO_DESTINO_FORA_BRUTO"
            mensagem = "Destino planejado fora de data/dicionario_mestre/bruto/."
            registrar_log(logs, fonte_id, "validar_destino", "ERRO", mensagem)
        elif baixar_agora:
            status = "DOWNLOAD_AUTORIZADO_PARA_FONTE_UNICA"
            mensagem = "Download real autorizado somente para medicamentos_registrados_dados_gov."
            registrar_log(logs, fonte_id, "validar_autorizacao", "OK", mensagem)
        elif DRY_RUN or not executar:
            status = "DRY_RUN_PLANEJADO"
            mensagem = "DRY_RUN=True ou --executar ausente; nenhum download executado."
            registrar_log(logs, fonte_id, "montar_plano", "OK", mensagem)
        else:
            status = "NAO_AUTORIZADO_NESTA_FASE"
            mensagem = "Fonte nao autorizada para download real nesta fase."
            registrar_log(logs, fonte_id, "validar_autorizacao", "OK", mensagem)

        plano.append(
            {
                "fonte_id": fonte_id,
                "nome": str(fonte["nome"]),
                "url_pagina": str(fonte["url_pagina"]),
                "tipo": str(fonte["tipo"]),
                "destino_planejado": str(fonte["destino_planejado"]),
                "baixar_nesta_fase": str(baixar_agora),
                "status": status,
                "observacao": str(fonte["observacao"]),
            }
        )
    return plano, logs


def nome_arquivo_seguro(url: str, fallback: str) -> str:
    nome = Path(urlparse(url).path).name or fallback
    nome = re.sub(r"[^A-Za-z0-9._-]+", "_", nome).strip("._")
    return nome or fallback


def recursos_dados_gov(logs: list[dict[str, str]]) -> list[dict[str, str]]:
    sessao = requests.Session()
    sessao.headers.update({"User-Agent": "MEDBOX_V3_ZERO ingestao controlada/2.14G-1"})
    registrar_log_simples(logs, "consultar_api_dados_gov", "INICIADO", CKAN_API_MEDICAMENTOS)
    resposta = sessao.get(CKAN_API_MEDICAMENTOS, timeout=TIMEOUT_SEGUNDOS)
    if resposta.ok:
        dados = resposta.json()
        recursos = dados.get("result", {}).get("resources", []) if dados.get("success") else []
        candidatos = []
        for recurso in recursos:
            url = recurso.get("url") or recurso.get("download_url")
            if not url:
                continue
            formato = (recurso.get("format") or Path(urlparse(url).path).suffix.lstrip(".")).lower()
            if formato in {"csv", "zip", "xls", "xlsx"} or url.lower().split("?")[0].endswith((".csv", ".zip", ".xls", ".xlsx")):
                candidatos.append({"url": url, "nome": recurso.get("name") or recurso.get("id") or "recurso_dados_gov", "formato": formato})
        if candidatos:
            registrar_log_simples(logs, "identificar_recursos", "OK", f"{len(candidatos)} recurso(s) estruturado(s) via API CKAN")
            return candidatos
        registrar_log_simples(logs, "identificar_recursos", "PENDENTE", "API CKAN sem recursos estruturados simples")
    else:
        registrar_log_simples(logs, "consultar_api_dados_gov", "PENDENTE", f"HTTP {resposta.status_code}")

    pagina = "https://dados.gov.br/dados/conjuntos-dados/medicamentos-registrados-no-brasil"
    registrar_log_simples(logs, "consultar_pagina_dados_gov", "INICIADO", pagina)
    resposta = sessao.get(pagina, timeout=TIMEOUT_SEGUNDOS)
    if not resposta.ok:
        registrar_log_simples(logs, "consultar_pagina_dados_gov", "PENDENTE", f"HTTP {resposta.status_code}")
        return []

    soup = BeautifulSoup(resposta.text, "html.parser")
    candidatos = []
    for link in soup.find_all("a", href=True):
        href = str(link["href"])
        if href.lower().split("?")[0].endswith((".csv", ".zip", ".xls", ".xlsx")):
            if href.startswith("/"):
                href = "https://dados.gov.br" + href
            candidatos.append({"url": href, "nome": link.get_text(" ", strip=True) or "recurso_dados_gov", "formato": Path(urlparse(href).path).suffix.lstrip(".").lower()})
    registrar_log_simples(logs, "identificar_recursos_pagina", "OK" if candidatos else "PENDENTE", f"{len(candidatos)} link(s) estruturado(s) encontrados")
    return candidatos


def baixar_arquivo(url: str, destino: Path, logs: list[dict[str, str]]) -> tuple[int, str]:
    sessao = requests.Session()
    sessao.headers.update({"User-Agent": "MEDBOX_V3_ZERO ingestao controlada/2.14G-1"})
    sha = hashlib.sha256()
    total = 0
    with sessao.get(url, stream=True, timeout=TIMEOUT_SEGUNDOS) as resposta:
        if not resposta.ok:
            raise RuntimeError(f"HTTP {resposta.status_code} ao baixar {url}")
        tamanho = resposta.headers.get("Content-Length")
        if tamanho and int(tamanho) > MAX_BYTES_POR_FONTE:
            raise RuntimeError(f"arquivo excede limite configurado: {tamanho} bytes")
        with destino.open("wb") as arquivo:
            for bloco in resposta.iter_content(chunk_size=1024 * 1024):
                if not bloco:
                    continue
                total += len(bloco)
                if total > MAX_BYTES_POR_FONTE:
                    raise RuntimeError(f"arquivo excede limite configurado: {total} bytes")
                sha.update(bloco)
                arquivo.write(bloco)
    registrar_log_simples(logs, "baixar_arquivo", "OK", f"{destino} ({total} bytes)")
    return total, sha.hexdigest()


def executar_medicamentos_registrados() -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    logs: list[dict[str, str]] = []
    manifesto: list[dict[str, str]] = []
    DESTINO_MEDICAMENTOS.mkdir(parents=True, exist_ok=True)

    recursos = recursos_dados_gov(logs)
    if not recursos:
        manifesto.append(
            {
                "data_hora": agora(),
                "fonte_id": "medicamentos_registrados_dados_gov",
                "nome_arquivo": "",
                "url_origem": "https://dados.gov.br/dados/conjuntos-dados/medicamentos-registrados-no-brasil",
                "caminho_local": "",
                "tamanho_bytes": "0",
                "sha256": "",
                "status": "PENDENTE_LINK_DOWNLOAD_NAO_LOCALIZADO",
                "observacao": "Pagina/API nao expuseram link estruturado simples; nenhuma fonte alternativa usada.",
            }
        )
        registrar_log_simples(logs, "download", "PENDENTE", "Nenhum link baixavel estruturado localizado")
        return manifesto, logs

    for indice, recurso in enumerate(recursos, start=1):
        url = recurso["url"]
        nome = nome_arquivo_seguro(url, f"medicamentos_registrados_{indice}.{recurso.get('formato') or 'dat'}")
        caminho = DESTINO_MEDICAMENTOS / nome
        if caminho.exists():
            caminho = DESTINO_MEDICAMENTOS / f"{caminho.stem}_{indice}{caminho.suffix}"
        try:
            tamanho, sha = baixar_arquivo(url, caminho, logs)
            status = "OK"
            observacao = f"Recurso baixado: {recurso.get('nome', '')}"
        except Exception as exc:  # noqa: BLE001 - registrar falha sem burlar ou buscar alternativa
            tamanho = 0
            sha = ""
            status = "PENDENTE_FALHA_DOWNLOAD"
            observacao = f"{type(exc).__name__}: {exc}"
            registrar_log_simples(logs, "baixar_arquivo", "PENDENTE", observacao)

        manifesto.append(
            {
                "data_hora": agora(),
                "fonte_id": "medicamentos_registrados_dados_gov",
                "nome_arquivo": nome,
                "url_origem": url,
                "caminho_local": str(caminho if status == "OK" else ""),
                "tamanho_bytes": str(tamanho),
                "sha256": sha,
                "status": status,
                "observacao": observacao,
            }
        )
    return manifesto, logs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download estruturado controlado MEDREG")
    parser.add_argument("--fonte", help="Fonte unica a executar")
    parser.add_argument("--executar", action="store_true", help="Executa download real somente para fonte autorizada")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    fonte = normalizar_fonte(args.fonte)
    plano, logs = montar_plano(fonte, args.executar)
    escrever_csv(PLANO_CSV, plano, ["fonte_id", "nome", "url_pagina", "tipo", "destino_planejado", "baixar_nesta_fase", "status", "observacao"])
    escrever_csv(LOG_CSV, logs, ["data_hora", "fonte_id", "etapa", "status", "mensagem"])

    if not args.executar:
        print(f"DRY_RUN={DRY_RUN}; fontes planejadas={len(plano)}; download_real_executado=False")
        return 0

    if fonte != "medicamentos_registrados_dados_gov":
        print("download_real_executado=False; fonte nao autorizada nesta fase")
        return 2

    manifesto, logs_especificos = executar_medicamentos_registrados()
    escrever_csv(
        MANIFESTO_MEDICAMENTOS,
        manifesto,
        ["data_hora", "fonte_id", "nome_arquivo", "url_origem", "caminho_local", "tamanho_bytes", "sha256", "status", "observacao"],
    )
    escrever_csv(LOG_MEDICAMENTOS_CSV, logs_especificos, ["data_hora", "etapa", "status", "mensagem"])
    ok = sum(1 for linha in manifesto if linha["status"] == "OK")
    pendentes = len(manifesto) - ok
    print(f"download_real_executado=True; fonte={fonte}; arquivos_ok={ok}; pendentes={pendentes}; destino={DESTINO_MEDICAMENTOS}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
