from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any


_PRIORIDADE_EMPRESA = {
    "MEDBOX": 0,
    "OSINFO": 1,
    "CONCORRENTE": 2,
}


def decimal_lance(valor: Any, padrao: str = "0") -> Decimal:
    """Converte valores monetários BR/US sem arredondar prematuramente."""
    if valor is None:
        return Decimal(padrao)
    if isinstance(valor, Decimal):
        return valor
    texto = str(valor).strip().replace("R$", "").replace("%", "").replace(" ", "")
    if not texto:
        return Decimal(padrao)
    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    try:
        return Decimal(texto)
    except (InvalidOperation, ValueError, TypeError):
        return Decimal(padrao)


def _empresa_concorrente(nome: Any) -> str:
    texto = str(nome or "").strip().upper()
    return texto or "CONCORRENTE"


def calcular_persistencia_item(item: dict[str, Any]) -> dict[str, Any]:
    """Calcula o resultado persistido sem confiar em status/vencedor do frontend.

    Regras:
    - autoridade é sempre o backend;
    - desempate: MEDBOX > OSINFO > concorrente;
    - quantidade <= 0 é neutra;
    - preço MedBox informado no payload é preservado;
    - vitória usa o menor valor vencedor, sem arredondar antes da multiplicação.
    """
    quantidade = decimal_lance(item.get("quantidade"))
    preco_osinfo = decimal_lance(item.get("preco_osinfo"))
    menor_lance = decimal_lance(item.get("menor_preco_ofertado", item.get("menor_lance")))
    preco_medbox = decimal_lance(item.get("preco_medbox"))
    empresa_lance = _empresa_concorrente(item.get("empresa_melhor_lance"))

    if quantidade <= 0:
        return {
            "quantidade": quantidade,
            "preco_osinfo": preco_osinfo,
            "menor_lance": menor_lance,
            "preco_medbox": preco_medbox,
            "empresa_vencedora": "",
            "menor_valor_vencedor": Decimal("0"),
            "venceu_medbox": 0,
            "status_lance": "FORA DA COTACAO",
            "valor_unitario": Decimal("0"),
            "valor_total": Decimal("0"),
        }

    candidatos: list[tuple[Decimal, int, str]] = []
    if preco_medbox > 0:
        candidatos.append((preco_medbox, _PRIORIDADE_EMPRESA["MEDBOX"], "MEDBOX"))
    if preco_osinfo > 0:
        candidatos.append((preco_osinfo, _PRIORIDADE_EMPRESA["OSINFO"], "OSINFO"))
    if menor_lance > 0:
        candidatos.append((menor_lance, _PRIORIDADE_EMPRESA["CONCORRENTE"], empresa_lance))

    if not candidatos:
        return {
            "quantidade": quantidade,
            "preco_osinfo": preco_osinfo,
            "menor_lance": menor_lance,
            "preco_medbox": preco_medbox,
            "empresa_vencedora": "",
            "menor_valor_vencedor": Decimal("0"),
            "venceu_medbox": 0,
            "status_lance": "SEM PRECO",
            "valor_unitario": Decimal("0"),
            "valor_total": Decimal("0"),
        }

    menor_valor, _, empresa_vencedora = min(candidatos, key=lambda candidato: (candidato[0], candidato[1]))
    venceu_medbox = int(empresa_vencedora == "MEDBOX")
    valor_unitario = menor_valor if venceu_medbox else Decimal("0")
    valor_total = quantidade * valor_unitario if venceu_medbox else Decimal("0")

    return {
        "quantidade": quantidade,
        "preco_osinfo": preco_osinfo,
        "menor_lance": menor_lance,
        "preco_medbox": preco_medbox,
        "empresa_vencedora": empresa_vencedora,
        "menor_valor_vencedor": menor_valor,
        "venceu_medbox": venceu_medbox,
        "status_lance": "MEDBOX VENCE" if venceu_medbox else "NEGOCIAR",
        "valor_unitario": valor_unitario,
        "valor_total": valor_total,
    }


def calcular_total_geral(itens_calculados: list[dict[str, Any]]) -> Decimal:
    return sum((decimal_lance(item.get("valor_total")) for item in itens_calculados), Decimal("0"))
