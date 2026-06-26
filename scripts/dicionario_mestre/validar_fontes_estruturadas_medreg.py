"""Valida arquivos planejados de fontes estruturadas MEDREG.

FASE 2.14F: nao acessa internet e nao baixa dados. Como o download real ainda
nao foi autorizado, os arquivos planejados devem ficar como pendentes.
"""

from __future__ import annotations

import csv
from pathlib import Path

ROOT_BRUTO = Path("data/dicionario_mestre/bruto").resolve()
PLANO_CSV = Path("data/dicionario_mestre/processado/plano_download_fontes_estruturadas_medreg.csv")
SAIDA_CSV = Path("data/dicionario_mestre/processado/validacao_fontes_estruturadas_medreg.csv")


def destino_seguro(caminho: Path) -> bool:
    resolvido = caminho.resolve()
    try:
        resolvido.relative_to(ROOT_BRUTO)
    except ValueError:
        return False
    return True


def carregar_plano() -> list[dict[str, str]]:
    if not PLANO_CSV.exists():
        return []
    with PLANO_CSV.open("r", newline="", encoding="utf-8") as arquivo:
        return list(csv.DictReader(arquivo))


def validar() -> list[dict[str, str]]:
    linhas: list[dict[str, str]] = []
    plano = carregar_plano()
    if not plano:
        return [
            {
                "fonte_id": "plano_download",
                "caminho_esperado": str(PLANO_CSV),
                "status": "PENDENTE_PLANO_NAO_GERADO",
                "observacao": "Execute baixar_fontes_estruturadas_medreg.py em DRY_RUN antes da validacao.",
            }
        ]

    for fonte in plano:
        destino = Path(fonte["destino_planejado"])
        if not destino_seguro(destino):
            status = "ERRO_DESTINO_FORA_BRUTO"
            observacao = "Destino planejado fora de data/dicionario_mestre/bruto/."
        elif not destino.exists():
            status = "PENDENTE_ARQUIVO_NAO_BAIXADO"
            observacao = "Diretorio/arquivo ainda nao existe porque nenhum download real foi executado nesta fase."
        else:
            arquivos = [item for item in destino.rglob("*") if item.is_file()]
            if arquivos:
                status = "ARQUIVO_ENCONTRADO"
                observacao = f"{len(arquivos)} arquivo(s) encontrado(s) para validacao futura."
            else:
                status = "PENDENTE_ARQUIVO_NAO_BAIXADO"
                observacao = "Diretorio existe, mas nao ha arquivo baixado para validar."

        linhas.append(
            {
                "fonte_id": fonte["fonte_id"],
                "caminho_esperado": fonte["destino_planejado"],
                "status": status,
                "observacao": observacao,
            }
        )
    return linhas


def main() -> int:
    SAIDA_CSV.parent.mkdir(parents=True, exist_ok=True)
    linhas = validar()
    with SAIDA_CSV.open("w", newline="", encoding="utf-8") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=["fonte_id", "caminho_esperado", "status", "observacao"])
        escritor.writeheader()
        escritor.writerows(linhas)
    pendentes = sum(1 for linha in linhas if linha["status"].startswith("PENDENTE"))
    erros = sum(1 for linha in linhas if linha["status"].startswith("ERRO"))
    print(f"Validacao planejada: linhas={len(linhas)}; pendentes={pendentes}; erros={erros}; arquivo={SAIDA_CSV}")
    return 0 if erros == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
