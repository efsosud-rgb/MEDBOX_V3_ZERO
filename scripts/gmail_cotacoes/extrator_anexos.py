"""Localização e cópia de anexos entre pastas locais do robô.

Em modo --somente-local os "anexos" já existem em disco (pasta de
amostras). Este módulo só resolve caminhos e copia para
data/gmail_cotacoes/anexos/ quando necessário — não baixa nada da
internet nem do Gmail.
"""

from __future__ import annotations

import shutil
from pathlib import Path


class AnexoNaoEncontradoError(FileNotFoundError):
    pass


def localizar_anexo(nome_arquivo: str, pasta_busca: Path) -> Path:
    """Procura `nome_arquivo` diretamente dentro de `pasta_busca` (sem recursão)."""
    candidato = pasta_busca / nome_arquivo
    if candidato.exists():
        return candidato

    # Busca case-insensitive / tolerante a diferenças de espaço, já que nomes
    # reais de anexo de e-mail variam bastante (maiúsculas, .PDF vs .pdf etc.).
    alvo_norm = nome_arquivo.strip().casefold()
    if pasta_busca.exists():
        for arquivo in pasta_busca.iterdir():
            if arquivo.is_file() and arquivo.name.strip().casefold() == alvo_norm:
                return arquivo

    raise AnexoNaoEncontradoError(
        f"Anexo '{nome_arquivo}' não encontrado em {pasta_busca}"
    )


def copiar_para_anexos(caminho_origem: Path, pasta_anexos: Path) -> Path:
    pasta_anexos.mkdir(parents=True, exist_ok=True)
    destino = pasta_anexos / caminho_origem.name
    if destino.resolve() == caminho_origem.resolve():
        return destino
    shutil.copy2(caminho_origem, destino)
    return destino
