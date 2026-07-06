from __future__ import annotations

import re
import unicodedata
from typing import Any


def normalizar_texto(valor: Any) -> str:
    texto = "" if valor is None else str(valor)
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(ch for ch in texto if not unicodedata.combining(ch))
    texto = texto.upper()
    texto = re.sub(r"[^A-Z0-9.]+", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()


def sigla_cliente(valor: Any) -> str:
    n = normalizar_texto(valor)
    if not n:
        return "SEM_CLIENTE"

    regras = [
        ("HMHP", ["HMHP", "HERCULANO PINHEIRO", "HOSPITAL MATERNIDADE HERCULANO"]),
        ("DSAN", ["DSAN", "DESAN", "DESAM", "DESENVOLVIMENTO DE ASSISTENCIA MULTIPLA"]),
        ("MLD", ["MLD", "LEILA DINIZ", "MATERNIDADE LEILA", "LEILA"]),
        ("ROCHA", ["ROCHA FARIA", "HOSPITAL MUNICIPAL ROCHA", "ROCHA"]),
        ("HMAR", ["HMAR", "ANGRA DOS REIS"]),
        ("HMMF", ["HMMF", "MULHER FERNANDO"]),
        ("HMSC", ["HMSC", "CARMELA DUTRA"]),
        ("GETULINHO", ["GETULINHO", "GETULIO VARGAS FILHO", "HGVF"]),
        ("ILPI", ["ILPI"]),
        ("PADI", ["PADI"]),
        ("RAPHAEL", ["RAPHAEL DE PAULA", "RAPHAEL"]),
        ("ITAGUAI", ["ITAGUAI"]),
        ("AFNE-GLORIA", ["AFNE GLORIA", "GLORIA"]),
        ("AFNE-COBIL", ["AFNE COBIL", "COBIL"]),
        ("CCE", ["CCE"]),
        ("CAP 3.2", ["CAP 3.2", "CAP32"]),
        ("CAP 3.3", ["CAP 3.3", "CAP33"]),
        ("ESTOQUE CENTRAL", ["ESTOQUE CENTRAL"]),
    ]

    for sigla, termos in regras:
        if any(t in n for t in termos):
            return sigla

    palavras_ignorar = {
        "HOSPITAL", "MUNICIPAL", "MATERNIDADE", "CENTRO", "DE", "DA", "DO",
        "DAS", "DOS", "UNIDADE", "CLINICA", "INSTITUTO"
    }
    palavras = [p for p in n.split() if p not in palavras_ignorar]
    if not palavras:
        return n[:18]
    if len(palavras) == 1:
        return palavras[0][:18]
    return " ".join(palavras[:2])[:24]


def cliente_match(filtro: Any, cliente: Any) -> bool:
    filtro_norm = normalizar_texto(filtro)
    if not filtro_norm:
        return True

    sigla_filtro = sigla_cliente(filtro)
    sigla_cliente_atual = sigla_cliente(cliente)
    cliente_norm = normalizar_texto(cliente)

    return (
        filtro_norm == sigla_cliente_atual
        or sigla_filtro == sigla_cliente_atual
        or filtro_norm in cliente_norm
        or filtro_norm in normalizar_texto(sigla_cliente_atual)
    )
