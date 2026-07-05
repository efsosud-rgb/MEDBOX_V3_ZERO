"""Teste de matching de itens — casos obrigatórios do robô Gmail Cotações.

Não depende de pytest (não está instalado neste ambiente). Roda com:
    python scripts/gmail_cotacoes/testar_matching_itens.py

Cobre exatamente os exemplos de "podem casar" / "não podem casar" da
especificação do robô, usando perfil_tecnico.py (perfil técnico) e
rapidfuzz (similaridade textual) — a mesma lógica usada em
correlacionador.cruzar_itens.
"""

from __future__ import annotations

import sys

from rapidfuzz import fuzz

from perfil_tecnico import comparar_perfis, extrair_perfil, normalizar_texto

NAO_PODEM_CASAR = [
    ("SERINGA 60ML", "SERINGA 20ML"),
    ("AGULHA 25X7", "AGULHA 40X12"),
    ("SONDA Nº 16", "SONDA Nº 18"),
    ("LUVA Nº 7.0", "LUVA Nº 8.0"),
    ("LUVA PEQUENO", "LUVA MEDIO"),
    ("SERINGA LUER SLIP 20ML", "SERINGA LUER LOCK 20ML"),
]

PODEM_CASAR = [
    ("CATETER IV JELCO N22", "CATETER IV JELCO Nº 22"),
    ("COLETOR PERFUROCORTANTE 13L", "COLETOR MATERIAL PERFUROCORTANTE 13 LITROS"),
    ("COMPRESSA CURATIVO CIRURGICO 25X28CM C/05", "COMPRESSA PARA CURATIVO CIRURGICO 25 X 28 CM C/05"),
    ("SONDA ASPIRAÇÃO TRAQUEAL N° 16", "SONDA ASPIRACAO TRAQUEAL Nº 16"),
]


def _testar_par(desc_a: str, desc_b: str) -> tuple[bool, list[str], float]:
    p1, p2 = extrair_perfil(desc_a), extrair_perfil(desc_b)
    conflito, motivos = comparar_perfis(p1, p2)
    similaridade = fuzz.token_sort_ratio(normalizar_texto(desc_a), normalizar_texto(desc_b))
    return conflito, motivos, similaridade


def main() -> int:
    falhas = 0
    total = 0

    print("== Itens que NÃO podem casar (deve haver CONFLITO TÉCNICO) ==")
    for a, b in NAO_PODEM_CASAR:
        total += 1
        conflito, motivos, sim = _testar_par(a, b)
        status = "OK" if conflito else "FALHOU"
        if not conflito:
            falhas += 1
        print(f"[{status}] '{a}' x '{b}' -> conflito={conflito} similaridade_texto={sim:.1f} motivos={motivos}")

    print("\n== Itens que PODEM casar (NÃO deve haver conflito técnico) ==")
    for a, b in PODEM_CASAR:
        total += 1
        conflito, motivos, sim = _testar_par(a, b)
        status = "OK" if not conflito else "FALHOU"
        if conflito:
            falhas += 1
        print(f"[{status}] '{a}' x '{b}' -> conflito={conflito} similaridade_texto={sim:.1f} motivos={motivos}")

    print(f"\n{total - falhas}/{total} casos corretos.")
    if falhas:
        print(f"FALHA: {falhas} caso(s) de matching não se comportaram como esperado.")
        return 1
    print("SUCESSO: todos os casos de matching se comportaram como esperado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
