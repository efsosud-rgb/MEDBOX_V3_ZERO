"""
FASE 2.14B - Captura bruta controlada ANVISA MEDREG 100.

Consulta somente fontes oficiais ANVISA autorizadas, limitada a amostra local.
Nao salva HTML bruto, cookies, headers sensiveis ou screenshots.
Nao altera dicionario final, banco, fonte interna ou SKU_MASTER.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


BASE_DIR = Path(__file__).resolve().parents[2]
AMOSTRA_PATH = BASE_DIR / "data" / "dicionario_mestre" / "processado" / "amostra_medreg_100_para_captura.csv"
OUT_PATH = BASE_DIR / "data" / "dicionario_mestre" / "bruto" / "anvisa_medreg_100_captura_bruta.csv"
LOG_PATH = BASE_DIR / "data" / "dicionario_mestre" / "bruto" / "anvisa_medreg_100_log_captura.csv"

MAX_REGISTROS = 100
LIMITE_TESTE_PADRAO = 0
PAUSA_SEGUNDOS = 2.0
TIMEOUT_SEGUNDOS = 20
BLOQUEIO_CONSECUTIVO_LIMITE = 3

CONSULTAS_BASE = "https://consultas.anvisa.gov.br"
CONSULTAS_MEDICAMENTOS_URL = "https://consultas.anvisa.gov.br/#/medicamentos/"
BULARIO_URL = "https://consultas.anvisa.gov.br/#/bulario/"

OUTPUT_COLUMNS = [
    "registro_anvisa",
    "nome_produto_amostra",
    "principio_ativo_amostra",
    "dcb_amostra",
    "cas_amostra",
    "empresa_amostra",
    "fonte_consulta",
    "url_consulta",
    "status_captura",
    "forma_farmaceutica_bruta",
    "concentracao_bruta",
    "apresentacao_bruta",
    "via_uso_bruta",
    "nome_produto_bruto",
    "empresa_bruta",
    "principio_ativo_bruto",
    "observacao",
    "data_captura",
]

LOG_COLUMNS = ["registro_anvisa", "etapa", "status", "mensagem", "data_hora"]


class CaptureBlocked(RuntimeError):
    pass


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def read_amostra() -> list[dict[str, str]]:
    with AMOSTRA_PATH.open("r", encoding="utf-8-sig", newline="") as fh:
        rows = [{k: (v or "") for k, v in row.items()} for row in csv.DictReader(fh, delimiter=";")]
    if len(rows) > MAX_REGISTROS:
        raise ValueError(f"Amostra excede MAX_REGISTROS={MAX_REGISTROS}: {len(rows)}")
    return rows


def validate_amostra(rows: list[dict[str, str]]) -> None:
    if len(rows) != MAX_REGISTROS:
        raise ValueError(f"Amostra deve ter exatamente {MAX_REGISTROS} registros; encontrou {len(rows)}")
    if "registro_anvisa" not in rows[0]:
        raise ValueError("Amostra sem coluna registro_anvisa")
    invalid_origin = [r for r in rows if r.get("origem") != "ANVISA_MEDICAMENTOS_REGISTRADOS"]
    if invalid_origin:
        raise ValueError(f"Amostra contem origem inesperada em {len(invalid_origin)} registros")


def safe_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return " | ".join(safe_text(v) for v in value if safe_text(v))[:500]
    if isinstance(value, dict):
        return " | ".join(f"{k}:{safe_text(v)}" for k, v in value.items() if safe_text(v))[:500]
    return str(value).replace("\r", " ").replace("\n", " ").strip()[:500]


def build_candidate_urls(registro: str) -> list[str]:
    q = quote(registro)
    return [
        f"{CONSULTAS_BASE}/api/consulta/medicamento/produtos/{q}",
        f"{CONSULTAS_BASE}/api/consulta/medicamento/produtos?{urlencode({'numeroRegistro': registro})}",
        f"{CONSULTAS_BASE}/api/consulta/medicamento/produtos?{urlencode({'filter[numeroRegistro]': registro})}",
    ]


def official_get_json(url: str) -> tuple[str, Any | None, str]:
    if not url.startswith(CONSULTAS_BASE):
        raise ValueError(f"URL fora da fonte ANVISA autorizada: {url}")
    req = Request(
        url,
        headers={
            "Accept": "application/json, text/plain, */*",
            "User-Agent": "MEDBOX-Fase-2.14B-amostra-controlada/1.0",
            "Referer": CONSULTAS_MEDICAMENTOS_URL,
        },
        method="GET",
    )
    try:
        with urlopen(req, timeout=TIMEOUT_SEGUNDOS) as resp:
            status = getattr(resp, "status", 0) or 0
            ctype = resp.headers.get("Content-Type", "")
            body = resp.read(250_000)
    except HTTPError as exc:
        if exc.code in (401, 403, 429, 503):
            raise CaptureBlocked(f"HTTP {exc.code} em fonte ANVISA") from exc
        return "FALHA_HTTP", None, f"HTTP {exc.code}"
    except URLError as exc:
        return "FALHA_REDE", None, safe_text(exc.reason)
    except TimeoutError as exc:
        return "FALHA_TIMEOUT", None, safe_text(exc)

    text = body.decode("utf-8", errors="replace").strip()
    if status in (401, 403, 429, 503):
        raise CaptureBlocked(f"HTTP {status} em fonte ANVISA")
    if not text:
        return "SEM_RESULTADO", None, "resposta vazia"
    if "json" not in ctype.lower() and not text.startswith(("{", "[")):
        return "BLOQUEADO_OU_NAO_AUTOMATIZAVEL", None, f"resposta nao JSON ({ctype})"
    try:
        return "OK_HTTP", json.loads(text), "JSON recebido"
    except json.JSONDecodeError:
        return "BLOQUEADO_OU_NAO_AUTOMATIZAVEL", None, "JSON invalido ou pagina dinamica"


def find_first(data: Any, patterns: tuple[str, ...]) -> str:
    found: list[str] = []

    def walk(obj: Any, key_path: str = "") -> None:
        if len(found) >= 3:
            return
        if isinstance(obj, dict):
            for key, value in obj.items():
                key_norm = str(key).lower()
                if any(p in key_norm for p in patterns):
                    txt = safe_text(value)
                    if txt:
                        found.append(txt)
                walk(value, f"{key_path}.{key}" if key_path else str(key))
        elif isinstance(obj, list):
            for item in obj[:20]:
                walk(item, key_path)

    walk(data)
    return " | ".join(dict.fromkeys(found))[:500]


def has_useful_data(data: Any) -> bool:
    raw = json.dumps(data, ensure_ascii=False).lower()[:200_000]
    useful_terms = ["forma", "apresent", "concent", "via", "produto", "empresa", "principio", "registro"]
    return any(term in raw for term in useful_terms)


def capture_one(row: dict[str, str]) -> dict[str, str]:
    registro = row.get("registro_anvisa", "").strip()
    data_captura = now_iso()
    if not registro:
        return make_output(row, "ANVISA_CONSULTAS", CONSULTAS_MEDICAMENTOS_URL, "SEM_REGISTRO_ANVISA", "", {}, "registro ausente", data_captura)

    observations: list[str] = []
    for url in build_candidate_urls(registro):
        status, data, message = official_get_json(url)
        observations.append(f"{url}: {status} {message}")
        if status == "OK_HTTP" and data is not None:
            if not has_useful_data(data):
                continue
            return make_output(row, "ANVISA_CONSULTAS", url, "OK", "", data, message, data_captura)
        if status == "BLOQUEADO_OU_NAO_AUTOMATIZAVEL":
            return make_output(row, "ANVISA_CONSULTAS", url, status, "", {}, message, data_captura)
    return make_output(row, "ANVISA_CONSULTAS", CONSULTAS_MEDICAMENTOS_URL, "SEM_RESULTADO", "", {}, " ; ".join(observations), data_captura)


def make_output(row: dict[str, str], fonte: str, url: str, status: str, raw: str, data: Any, obs: str, data_captura: str) -> dict[str, str]:
    return {
        "registro_anvisa": row.get("registro_anvisa", ""),
        "nome_produto_amostra": row.get("nome_produto", ""),
        "principio_ativo_amostra": row.get("principio_ativo", ""),
        "dcb_amostra": row.get("dcb", ""),
        "cas_amostra": row.get("cas", ""),
        "empresa_amostra": row.get("empresa", ""),
        "fonte_consulta": fonte,
        "url_consulta": url,
        "status_captura": status,
        "forma_farmaceutica_bruta": find_first(data, ("forma",)) if data else "",
        "concentracao_bruta": find_first(data, ("concent",)) if data else "",
        "apresentacao_bruta": find_first(data, ("apresent",)) if data else "",
        "via_uso_bruta": find_first(data, ("via", "administr")) if data else "",
        "nome_produto_bruto": find_first(data, ("produto", "nome")) if data else "",
        "empresa_bruta": find_first(data, ("empresa", "detentor")) if data else "",
        "principio_ativo_bruto": find_first(data, ("principio", "ativo")) if data else "",
        "observacao": obs[:1000],
        "data_captura": data_captura,
    }


def log_row(logs: list[dict[str, str]], registro: str, etapa: str, status: str, mensagem: str) -> None:
    logs.append({
        "registro_anvisa": registro,
        "etapa": etapa,
        "status": status,
        "mensagem": mensagem[:1000],
        "data_hora": now_iso(),
    })


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, delimiter=";")
        writer.writeheader()
        writer.writerows(rows)


def run(limite: int) -> dict[str, Any]:
    rows = read_amostra()
    validate_amostra(rows)
    if limite < 0:
        raise ValueError("limite nao pode ser negativo")
    selected = rows[: min(limite or MAX_REGISTROS, MAX_REGISTROS)]
    outputs: list[dict[str, str]] = []
    logs: list[dict[str, str]] = []
    bloqueios_consecutivos = 0

    log_row(logs, "", "inicio", "OK", f"iniciando captura controlada com {len(selected)} registros")
    for idx, row in enumerate(selected, start=1):
        registro = row.get("registro_anvisa", "")
        log_row(logs, registro, "consulta_anvisa_consultas", "INICIADO", f"registro {idx}/{len(selected)}")
        try:
            captured = capture_one(row)
        except CaptureBlocked as exc:
            captured = make_output(row, "ANVISA_CONSULTAS", CONSULTAS_MEDICAMENTOS_URL, "BLOQUEADO_OU_NAO_AUTOMATIZAVEL", "", {}, safe_text(exc), now_iso())
        except Exception as exc:
            captured = make_output(row, "ANVISA_CONSULTAS", CONSULTAS_MEDICAMENTOS_URL, "FALHA", "", {}, safe_text(exc), now_iso())

        outputs.append(captured)
        log_row(logs, registro, "consulta_anvisa_consultas", captured["status_captura"], captured["observacao"])

        if captured["status_captura"] == "BLOQUEADO_OU_NAO_AUTOMATIZAVEL":
            bloqueios_consecutivos += 1
        else:
            bloqueios_consecutivos = 0

        if bloqueios_consecutivos >= BLOQUEIO_CONSECUTIVO_LIMITE:
            log_row(logs, registro, "parada_segura", "BLOQUEADO_OU_NAO_AUTOMATIZAVEL", "limite de bloqueios consecutivos atingido; captura interrompida sem insistir")
            break

        if idx < len(selected):
            time.sleep(PAUSA_SEGUNDOS)

    write_csv(OUT_PATH, OUTPUT_COLUMNS, outputs)
    write_csv(LOG_PATH, LOG_COLUMNS, logs)

    summary = {
        "amostra_total": len(rows),
        "limite_solicitado": limite or MAX_REGISTROS,
        "total_consultado": len(outputs),
        "ok": sum(1 for r in outputs if r["status_captura"] == "OK"),
        "sem_resultado": sum(1 for r in outputs if r["status_captura"] == "SEM_RESULTADO"),
        "falha": sum(1 for r in outputs if r["status_captura"].startswith("FALHA")),
        "bloqueado_ou_nao_automatizavel": sum(1 for r in outputs if r["status_captura"] == "BLOQUEADO_OU_NAO_AUTOMATIZAVEL"),
        "output_path": str(OUT_PATH.relative_to(BASE_DIR)),
        "log_path": str(LOG_PATH.relative_to(BASE_DIR)),
        "internet_restrita_fontes_anvisa": True,
        "dicionario_final_alterado": False,
        "banco_alterado": False,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Captura bruta controlada ANVISA MEDREG 100")
    parser.add_argument("--limite", type=int, default=LIMITE_TESTE_PADRAO, help="limite de registros; 0 usa MAX_REGISTROS")
    args = parser.parse_args()
    run(args.limite)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
