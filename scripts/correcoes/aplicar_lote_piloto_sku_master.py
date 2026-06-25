#!/usr/bin/env python3
"""Dry-run seguro para o lote piloto de normalizacao SKU_MASTER.

Modo padrao: DRY-RUN, sem escrita no banco.

Modo APPLY futuro: exige simultaneamente ``--apply`` e ``--confirmar``.
Nesta etapa o APPLY nao deve ser executado.

Escopo do APPLY futuro:
- atualizar somente ``produtos.sku_master``;
- nao tocar em ``descricao_original``;
- nao tocar em precos, historico, fabricante ou categoria;
- exigir backup, auditoria e transacao.
"""

from __future__ import annotations

import argparse
import csv
import re
import shutil
import sqlite3
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


BASE_DIR = Path(__file__).resolve().parents[2]
CAMINHO_BANCO = BASE_DIR / "banco" / "medbox_v3.db"
CAMINHO_CSV = (
    BASE_DIR
    / "scripts"
    / "diagnosticos"
    / "lote_piloto_normalizacao_sku_master.csv"
)
PASTA_BACKUPS = BASE_DIR / "backups"

TOTAL_ESPERADO = 50
MAX_EXEMPLOS = 50
TERMOS_PROIBIDOS_SKU = {"PREMIUM"}


class ErroSeguranca(RuntimeError):
    """Falha de pre-condicao que deve abortar sem alterar o banco."""


@dataclass(frozen=True)
class RegistroLote:
    produto_id: int
    descricao_atual: str
    origem_descricao: str
    sku_master_atual: str
    sku_master_sugerido: str
    score: str
    nivel_confianca: str
    origem_do_match: str
    fabricante_sugerido: str
    categoria_sugerida: str
    pode_propagar_fabricante: str
    pode_propagar_categoria: str
    decisao_usuario: str


def _limpar(valor: object) -> str:
    return str(valor or "").strip()


def _normalizar_texto(valor: object) -> str:
    texto = _limpar(valor).upper()
    return " ".join(texto.split())


def _normalizar_para_comparacao(valor: object) -> str:
    """Normaliza descricao para comparar CSV x banco sem pontuacao cosmetica."""

    texto = _normalizar_texto(valor)
    texto = re.sub(r"[^A-Z0-9%]+", " ", texto)
    return " ".join(texto.split())


def _eh_sim(valor: object) -> bool:
    return _normalizar_texto(valor) in {"SIM", "TRUE", "1", "YES"}


def _executar_git(*argumentos: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *argumentos],
        cwd=BASE_DIR,
        capture_output=True,
        text=True,
        check=False,
    )


def validar_git_para_apply() -> None:
    try:
        resultado = _executar_git("status", "--porcelain", "--untracked-files=all")
    except FileNotFoundError as erro:
        raise ErroSeguranca("Git nao esta disponivel; APPLY bloqueado.") from erro

    if resultado.returncode != 0:
        mensagem = resultado.stderr.strip() or "falha ao consultar git status"
        raise ErroSeguranca(f"Nao foi possivel validar o Git: {mensagem}")

    status = resultado.stdout.strip()
    if status:
        raise ErroSeguranca("Git status nao esta limpo; APPLY bloqueado.\n" + status)


def carregar_lote() -> List[RegistroLote]:
    if not CAMINHO_CSV.is_file():
        raise ErroSeguranca(f"CSV do lote piloto nao encontrado: {CAMINHO_CSV}")

    campos_obrigatorios = {
        "produto_id",
        "descricao_atual",
        "origem_descricao",
        "sku_master_atual",
        "sku_master_sugerido",
        "score",
        "nivel_confianca",
        "origem_do_match",
        "fabricante_sugerido",
        "categoria_sugerida",
        "pode_propagar_fabricante",
        "pode_propagar_categoria",
        "decisao_usuario",
    }

    registros: List[RegistroLote] = []
    with CAMINHO_CSV.open("r", encoding="utf-8-sig", newline="") as arquivo:
        leitor = csv.DictReader(arquivo, delimiter=";")
        campos_csv = set(leitor.fieldnames or [])
        ausentes = sorted(campos_obrigatorios - campos_csv)
        if ausentes:
            raise ErroSeguranca(
                "CSV sem campos obrigatorios: " + ", ".join(ausentes)
            )

        for numero_linha, linha in enumerate(leitor, start=2):
            try:
                produto_id = int(_limpar(linha.get("produto_id")))
            except ValueError as erro:
                raise ErroSeguranca(
                    f"Linha {numero_linha}: produto_id invalido."
                ) from erro

            registro = RegistroLote(
                produto_id=produto_id,
                descricao_atual=_limpar(linha.get("descricao_atual")),
                origem_descricao=_limpar(linha.get("origem_descricao")),
                sku_master_atual=_limpar(linha.get("sku_master_atual")),
                sku_master_sugerido=_limpar(linha.get("sku_master_sugerido")),
                score=_limpar(linha.get("score")),
                nivel_confianca=_limpar(linha.get("nivel_confianca")),
                origem_do_match=_limpar(linha.get("origem_do_match")),
                fabricante_sugerido=_limpar(linha.get("fabricante_sugerido")),
                categoria_sugerida=_limpar(linha.get("categoria_sugerida")),
                pode_propagar_fabricante=_limpar(
                    linha.get("pode_propagar_fabricante")
                ),
                pode_propagar_categoria=_limpar(
                    linha.get("pode_propagar_categoria")
                ),
                decisao_usuario=_limpar(linha.get("decisao_usuario")),
            )
            validar_linha_csv(numero_linha, registro)
            registros.append(registro)

    validar_lote_csv(registros)
    return registros


def validar_linha_csv(numero_linha: int, registro: RegistroLote) -> None:
    prefixo = f"Linha {numero_linha}:"

    if not registro.produto_id:
        raise ErroSeguranca(f"{prefixo} produto_id vazio.")

    if registro.sku_master_atual:
        raise ErroSeguranca(f"{prefixo} sku_master_atual deve estar vazio.")

    if not registro.sku_master_sugerido:
        raise ErroSeguranca(f"{prefixo} sku_master_sugerido vazio.")

    if registro.sku_master_sugerido != registro.sku_master_sugerido.upper():
        raise ErroSeguranca(f"{prefixo} sku_master_sugerido nao esta em maiusculas.")

    if registro.decisao_usuario:
        raise ErroSeguranca(f"{prefixo} decisao_usuario deve estar vazia.")

    if registro.fabricante_sugerido:
        raise ErroSeguranca(f"{prefixo} fabricante_sugerido deve estar vazio.")

    if registro.categoria_sugerida:
        raise ErroSeguranca(f"{prefixo} categoria_sugerida deve estar vazia.")

    if _eh_sim(registro.pode_propagar_fabricante):
        raise ErroSeguranca(f"{prefixo} pode_propagar_fabricante nao pode ser SIM.")

    if _eh_sim(registro.pode_propagar_categoria):
        raise ErroSeguranca(f"{prefixo} pode_propagar_categoria nao pode ser SIM.")

    sku_normalizado = _normalizar_texto(registro.sku_master_sugerido)
    if sku_normalizado.startswith("SKU PENDENTE"):
        raise ErroSeguranca(f"{prefixo} sku_master_sugerido inicia com SKU PENDENTE.")

    if sku_normalizado in TERMOS_PROIBIDOS_SKU:
        raise ErroSeguranca(f"{prefixo} sku_master_sugerido proibido: {sku_normalizado}.")

    if _normalizar_texto(registro.nivel_confianca) != "ALTA":
        raise ErroSeguranca(f"{prefixo} nivel_confianca deve ser ALTA.")


def validar_lote_csv(registros: Sequence[RegistroLote]) -> None:
    if len(registros) != TOTAL_ESPERADO:
        raise ErroSeguranca(
            f"Contagem invalida: {len(registros)} linhas; "
            f"esperadas exatamente {TOTAL_ESPERADO}."
        )

    ids = [registro.produto_id for registro in registros]
    duplicados = sorted({produto_id for produto_id in ids if ids.count(produto_id) > 1})
    if duplicados:
        raise ErroSeguranca(
            "produto_id duplicado no lote: " + ", ".join(map(str, duplicados))
        )


def conectar_banco_somente_leitura() -> sqlite3.Connection:
    if not CAMINHO_BANCO.is_file():
        raise ErroSeguranca(f"Banco nao encontrado: {CAMINHO_BANCO}")

    uri = CAMINHO_BANCO.resolve().as_posix()
    return sqlite3.connect(f"file:{uri}?mode=ro", uri=True)


def obter_colunas_produtos(conexao: sqlite3.Connection) -> List[str]:
    linhas = conexao.execute("PRAGMA table_info(produtos)").fetchall()
    colunas = [str(linha[1]) for linha in linhas]
    if not colunas:
        raise ErroSeguranca("Tabela produtos nao encontrada ou sem colunas.")
    return colunas


def validar_colunas_produtos(colunas: Sequence[str]) -> None:
    obrigatorias = {"id", "produto_padrao", "sku_master"}
    ausentes = sorted(obrigatorias - set(colunas))
    if ausentes:
        raise ErroSeguranca(
            "Tabela produtos sem colunas obrigatorias: " + ", ".join(ausentes)
        )


def buscar_produto(
    conexao: sqlite3.Connection,
    colunas: Sequence[str],
    produto_id: int,
) -> Optional[sqlite3.Row]:
    campos = ["id", "produto_padrao", "sku_master"]
    if "ativo" in colunas:
        campos.append("ativo")

    sql = f"SELECT {', '.join(campos)} FROM produtos WHERE id = ?"
    return conexao.execute(sql, (produto_id,)).fetchone()


def produto_ativo(produto: sqlite3.Row, colunas: Sequence[str]) -> bool:
    if "ativo" not in colunas:
        return True
    valor = produto["ativo"]
    if valor is None:
        return True
    if isinstance(valor, str):
        return _normalizar_texto(valor) not in {"0", "NAO", "NÃO", "FALSE", "INATIVO"}
    return int(valor) != 0


def descricoes_compativeis(descricao_csv: str, produto_padrao_banco: str) -> bool:
    csv_norm = _normalizar_para_comparacao(descricao_csv)
    banco_norm = _normalizar_para_comparacao(produto_padrao_banco)
    if not csv_norm or not banco_norm:
        return False
    if csv_norm == banco_norm:
        return True
    return csv_norm in banco_norm or banco_norm in csv_norm


def validar_banco(
    conexao: sqlite3.Connection,
    registros: Sequence[RegistroLote],
) -> Dict[int, str]:
    conexao.row_factory = sqlite3.Row
    colunas = obter_colunas_produtos(conexao)
    validar_colunas_produtos(colunas)

    descricoes_banco: Dict[int, str] = {}
    for registro in registros:
        produto = buscar_produto(conexao, colunas, registro.produto_id)
        if produto is None:
            raise ErroSeguranca(
                f"produto_id {registro.produto_id}: nao encontrado no banco."
            )

        if not produto_ativo(produto, colunas):
            raise ErroSeguranca(
                f"produto_id {registro.produto_id}: produto nao esta ativo."
            )

        sku_atual_banco = _limpar(produto["sku_master"])
        if sku_atual_banco:
            raise ErroSeguranca(
                f"produto_id {registro.produto_id}: sku_master no banco ja esta "
                f"preenchido com {sku_atual_banco!r}."
            )

        produto_padrao_banco = _limpar(produto["produto_padrao"])
        if not descricoes_compativeis(registro.descricao_atual, produto_padrao_banco):
            raise ErroSeguranca(
                f"produto_id {registro.produto_id}: produto_padrao no banco nao "
                f"bate com descricao_atual do CSV. banco={produto_padrao_banco!r}; "
                f"csv={registro.descricao_atual!r}."
            )

        descricoes_banco[registro.produto_id] = produto_padrao_banco

    return descricoes_banco


def imprimir_dry_run(registros: Sequence[RegistroLote]) -> None:
    print("=== DRY-RUN - LOTE PILOTO SKU_MASTER ===")
    print(f"CSV: {CAMINHO_CSV}")
    print(f"Banco: {CAMINHO_BANCO}")
    print(f"Total de linhas validadas: {len(registros)}")
    print(f"Produtos que seriam atualizados: {len(registros)}")
    print("Campo alvo futuro: produtos.sku_master")
    print("Campos NAO alterados: descricao_original, produto_padrao, fabricante, categoria, precos, historico.")
    print("")
    print("Produtos simulados:")
    for registro in registros[:MAX_EXEMPLOS]:
        print(
            f"- produto_id={registro.produto_id}: "
            f"{registro.descricao_atual} -> {registro.sku_master_sugerido}"
        )
    print("")
    print("DRY-RUN concluido: nenhum UPDATE foi executado.")
    print("Banco aberto somente leitura no DRY-RUN.")
    print("--apply nao foi executado.")


def criar_backup() -> Path:
    if not CAMINHO_BANCO.is_file():
        raise ErroSeguranca(f"Banco nao encontrado: {CAMINHO_BANCO}")

    PASTA_BACKUPS.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    destino = PASTA_BACKUPS / f"medbox_v3_antes_lote_piloto_sku_master_{timestamp}.db"
    shutil.copy2(CAMINHO_BANCO, destino)
    if not destino.is_file() or destino.stat().st_size == 0:
        raise ErroSeguranca(f"Falha ao criar backup valido: {destino}")
    return destino


def caminho_auditoria() -> Path:
    PASTA_BACKUPS.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return PASTA_BACKUPS / f"auditoria_lote_piloto_sku_master_{timestamp}.csv"


def escrever_auditoria(
    caminho: Path,
    registros: Iterable[RegistroLote],
    descricoes_banco: Dict[int, str],
) -> None:
    campos = [
        "data_hora",
        "produto_id",
        "produto_padrao_banco",
        "descricao_atual_csv",
        "sku_master_antigo",
        "sku_master_novo",
    ]
    agora = datetime.now().isoformat(timespec="seconds")
    with caminho.open("w", encoding="utf-8-sig", newline="") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=campos, delimiter=";")
        escritor.writeheader()
        for registro in registros:
            escritor.writerow(
                {
                    "data_hora": agora,
                    "produto_id": registro.produto_id,
                    "produto_padrao_banco": descricoes_banco.get(registro.produto_id, ""),
                    "descricao_atual_csv": registro.descricao_atual,
                    "sku_master_antigo": "",
                    "sku_master_novo": registro.sku_master_sugerido,
                }
            )


def aplicar(registros: Sequence[RegistroLote]) -> Tuple[Path, Path, int]:
    validar_git_para_apply()
    backup = criar_backup()
    auditoria = caminho_auditoria()

    conexao = sqlite3.connect(CAMINHO_BANCO)
    conexao.row_factory = sqlite3.Row
    try:
        descricoes_banco = validar_banco(conexao, registros)
        conexao.execute("BEGIN")
        atualizados = 0
        for registro in registros:
            cursor = conexao.execute(
                """
                UPDATE produtos
                   SET sku_master = ?
                 WHERE id = ?
                   AND (sku_master IS NULL OR TRIM(sku_master) = '')
                """,
                (registro.sku_master_sugerido, registro.produto_id),
            )
            if cursor.rowcount != 1:
                raise ErroSeguranca(
                    f"produto_id {registro.produto_id}: rowcount inesperado "
                    f"no UPDATE: {cursor.rowcount}."
                )
            atualizados += cursor.rowcount
        conexao.commit()
    except Exception:
        conexao.rollback()
        raise
    finally:
        conexao.close()

    escrever_auditoria(auditoria, registros, descricoes_banco)
    return backup, auditoria, atualizados


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Dry-run seguro para aplicar lote piloto de SKU_MASTER."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Aplica a correcao no banco. Exige tambem --confirmar.",
    )
    parser.add_argument(
        "--confirmar",
        action="store_true",
        help="Confirmacao extra obrigatoria para --apply.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)

    try:
        if args.confirmar and not args.apply:
            raise ErroSeguranca("--confirmar sozinho nao e permitido.")
        if args.apply and not args.confirmar:
            raise ErroSeguranca("APPLY exige --apply --confirmar.")

        registros = carregar_lote()

        if args.apply:
            backup, auditoria, atualizados = aplicar(registros)
            print("=== APPLY CONCLUIDO - LOTE PILOTO SKU_MASTER ===")
            print(f"Backup criado: {backup}")
            print(f"Auditoria criada: {auditoria}")
            print(f"Registros atualizados: {atualizados}")
            return 0

        with conectar_banco_somente_leitura() as conexao:
            validar_banco(conexao, registros)
        imprimir_dry_run(registros)
        return 0

    except ErroSeguranca as erro:
        print(f"ERRO DE SEGURANCA: {erro}", file=sys.stderr)
        print("Nenhuma alteracao foi aplicada.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
