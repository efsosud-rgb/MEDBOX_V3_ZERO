"""Localização e cópia de anexos entre pastas locais do robô.

Em modo --somente-local os "anexos" já existem em disco (pasta de
amostras) — localizar_anexo/copiar_para_anexos só resolvem caminhos e
copiam entre pastas locais, sem tocar no Gmail.

Em modo --gmail-real, salvar_anexo_gmail grava em disco os bytes que
gmail_client.py já baixou da API (esta função não faz nenhuma chamada de
rede), em uma subpasta por marcador e por mensagem, sem nunca sobrescrever
um arquivo existente.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from perfil_tecnico import normalizar_texto

_RE_TERMO_OC_ISOLADO = re.compile(r"\bOC\b")


class AnexoNaoEncontradoError(FileNotFoundError):
    pass


def parece_ordem_compra(nome_arquivo: str) -> bool:
    """Heurística por NOME do arquivo — usada quando o anexo ainda não foi
    baixado/parseado (ex.: ação buscar-amostra, que só lista metadados).
    Não confunde com a extração real de dados feita por parser_pdf_oc.py.
    """
    nome_norm = normalizar_texto(Path(nome_arquivo).stem)
    if "ORDEM DE COMPRA" in nome_norm or "ORDEM COMPRA" in nome_norm:
        return True
    return bool(_RE_TERMO_OC_ISOLADO.search(nome_norm))


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


def salvar_anexo_gmail(pasta_anexos: Path, label: str, message_id: str, nome_arquivo: str, conteudo: bytes) -> Path:
    """Grava um anexo já baixado da Gmail API em data/gmail_cotacoes/anexos/<label>/<message_id>/.

    Nunca sobrescreve: se o nome já existir na subpasta, acrescenta um
    sufixo numérico (_2, _3, ...) até achar um nome livre.
    """
    destino_dir = pasta_anexos / label / message_id
    destino_dir.mkdir(parents=True, exist_ok=True)

    caminho = Path(nome_arquivo)
    base, ext = caminho.stem, caminho.suffix
    destino = destino_dir / nome_arquivo
    contador = 2
    while destino.exists():
        destino = destino_dir / f"{base}_{contador}{ext}"
        contador += 1

    destino.write_bytes(conteudo)
    return destino
