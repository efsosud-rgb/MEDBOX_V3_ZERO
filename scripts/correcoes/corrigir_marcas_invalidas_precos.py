#!/usr/bin/env python3
"""Prepara a limpeza segura de marcas invalidas em precos_fornecedores.

O modo padrao e DRY-RUN e nunca altera o banco. O modo de aplicacao existe
somente para uso futuro e exige, ao mesmo tempo, ``--apply`` e ``--confirmar``.

IMPORTANTE: ``NOVO_VALOR_MARCA`` permanece como ``None`` por decisao de
seguranca. Esse valor deve ser validado pelo responsavel antes de qualquer
execucao futura em modo APPLY.
"""

from __future__ import annotations

import argparse
import csv
import sqlite3
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple


BASE_DIR = Path(__file__).resolve().parents[2]
CAMINHO_BANCO = BASE_DIR / "banco" / "medbox_v3.db"
CAMINHO_CSV = (
    BASE_DIR / "scripts" / "diagnosticos" / "previa_marcas_suspeitas_precos.csv"
)
PASTA_BACKUPS = BASE_DIR / "backups"

BRANCH_ESPERADA = "melhoria/auditoria-sku-master-todos-produtos"
TOTAL_ESPERADO = 89
ACAO_PERMITIDA = "REMOVER_MARCA_INVALIDA"
MARCAS_PERMITIDAS = {"UN", "RL", "PR", "PT", "CX", "FL", "GL", "KT", "MT"}
MARCAS_BLOQUEADAS = {"SR"}
MAX_EXEMPLOS = 10

# Valor deliberadamente pendente de validacao humana antes do APPLY futuro.
# None significa que o UPDATE futuro gravara SQL NULL, nao string vazia.
NOVO_VALOR_MARCA = None


class ErroSeguranca(RuntimeError):
    """Falha de pre-condicao que deve abortar sem alterar o banco."""


@dataclass(frozen=True)
class RegistroCorrecao:
    preco_id: int
    produto_id: int
    produto_padrao: str
    sku_master: str
    fabricante_produto: str
    marca_antiga: str
    fornecedor: str


def _marca_compacta(valor: str) -> str:
    return "".join(str(valor or "").upper().split())


def _executar_git(*argumentos: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *argumentos],
        cwd=BASE_DIR,
        capture_output=True,
        text=True,
        check=False,
    )


def validar_git(modo_apply: bool) -> None:
    try:
        branch_resultado = _executar_git("branch", "--show-current")
    except FileNotFoundError as erro:
        if modo_apply:
            raise ErroSeguranca("Git nao esta disponivel; APPLY bloqueado.") from erro
        print("AVISO: Git nao esta disponivel; verificacao ignorada no DRY-RUN.")
        return

    if branch_resultado.returncode != 0:
        mensagem = branch_resultado.stderr.strip() or "falha ao consultar a branch"
        raise ErroSeguranca(f"Nao foi possivel validar a branch: {mensagem}")

    branch_atual = branch_resultado.stdout.strip()
    if branch_atual != BRANCH_ESPERADA:
        raise ErroSeguranca(
            f"Branch incorreta: {branch_atual!r}. Esperada: {BRANCH_ESPERADA!r}."
        )

    status_resultado = _executar_git("status", "--porcelain", "--untracked-files=all")
    if status_resultado.returncode != 0:
        mensagem = status_resultado.stderr.strip() or "falha ao consultar git status"
        raise ErroSeguranca(f"Nao foi possivel validar o Git: {mensagem}")

    status = status_resultado.stdout.strip()
    if status and modo_apply:
        raise ErroSeguranca(
            "Git status nao esta limpo; APPLY bloqueado.\n" + status
        )
    if status:
        print("AVISO: Git status nao esta limpo; permitido apenas porque e DRY-RUN.")
        for linha in status.splitlines():
            print(f"  {linha}")


def carregar_registros_csv() -> List[RegistroCorrecao]:
    if not CAMINHO_CSV.is_file():
        raise ErroSeguranca(f"CSV de previa nao encontrado: {CAMINHO_CSV}")

    campos_obrigatorios = {
        "preco_id",
        "produto_id",
        "produto_padrao",
        "sku_master",
        "fabricante_produto",
        "marca_preco_atual",
        "fornecedor",
        "sugestao_acao",
    }

    registros: List[RegistroCorrecao] = []
    with CAMINHO_CSV.open("r", encoding="utf-8-sig", newline="") as arquivo:
        leitor = csv.DictReader(arquivo, delimiter=";")
        campos_csv = set(leitor.fieldnames or [])
        ausentes = sorted(campos_obrigatorios - campos_csv)
        if ausentes:
            raise ErroSeguranca(
                "CSV sem campos obrigatorios: " + ", ".join(ausentes)
            )

        for numero_linha, linha in enumerate(leitor, start=2):
            acao = str(linha.get("sugestao_acao") or "").strip().upper()
            if acao != ACAO_PERMITIDA:
                continue

            marca_antiga = str(linha.get("marca_preco_atual") or "").strip()
            marca_compacta = _marca_compacta(marca_antiga)
            if marca_compacta in MARCAS_BLOQUEADAS:
                raise ErroSeguranca(
                    f"Linha {numero_linha}: SR/S R entrou no conjunto de aplicacao."
                )
            if marca_compacta not in MARCAS_PERMITIDAS:
                raise ErroSeguranca(
                    f"Linha {numero_linha}: marca inesperada para aplicacao: "
                    f"{marca_antiga!r}."
                )

            try:
                preco_id = int(str(linha.get("preco_id") or "").strip())
                produto_id = int(str(linha.get("produto_id") or "").strip())
            except ValueError as erro:
                raise ErroSeguranca(
                    f"Linha {numero_linha}: preco_id/produto_id invalido."
                ) from erro

            if preco_id <= 0 or produto_id <= 0:
                raise ErroSeguranca(
                    f"Linha {numero_linha}: IDs devem ser inteiros positivos."
                )

            registros.append(
                RegistroCorrecao(
                    preco_id=preco_id,
                    produto_id=produto_id,
                    produto_padrao=str(linha.get("produto_padrao") or ""),
                    sku_master=str(linha.get("sku_master") or ""),
                    fabricante_produto=str(linha.get("fabricante_produto") or ""),
                    marca_antiga=marca_antiga,
                    fornecedor=str(linha.get("fornecedor") or ""),
                )
            )

    if len(registros) != TOTAL_ESPERADO:
        raise ErroSeguranca(
            f"Contagem invalida: {len(registros)} registros; "
            f"esperados exatamente {TOTAL_ESPERADO}."
        )

    ids = [registro.preco_id for registro in registros]
    duplicados = sorted(
        preco_id for preco_id, total in Counter(ids).items() if total > 1
    )
    if duplicados:
        raise ErroSeguranca(
            "CSV contem preco_id duplicado: " + ", ".join(map(str, duplicados))
        )

    return registros


def conectar_somente_leitura() -> sqlite3.Connection:
    if not CAMINHO_BANCO.is_file():
        raise ErroSeguranca(f"Banco nao encontrado: {CAMINHO_BANCO}")

    uri = CAMINHO_BANCO.resolve().as_uri() + "?mode=ro"
    conexao = sqlite3.connect(uri, uri=True)
    conexao.row_factory = sqlite3.Row
    return conexao


def validar_estado_banco(
    conexao: sqlite3.Connection,
    registros: List[RegistroCorrecao],
) -> None:
    ids = [registro.preco_id for registro in registros]
    placeholders = ",".join("?" for _ in ids)
    linhas = conexao.execute(
        f"SELECT id, produto_id, marca FROM precos_fornecedores "
        f"WHERE id IN ({placeholders})",
        ids,
    ).fetchall()
    atuais = {int(linha["id"]): linha for linha in linhas}

    faltantes = sorted(set(ids) - set(atuais))
    if faltantes:
        raise ErroSeguranca(
            "preco_id nao encontrado no banco: " + ", ".join(map(str, faltantes))
        )

    divergencias: List[str] = []
    for registro in registros:
        atual = atuais[registro.preco_id]
        marca_atual = atual["marca"]
        produto_id_atual = int(atual["produto_id"])
        if produto_id_atual != registro.produto_id:
            divergencias.append(
                f"preco_id {registro.preco_id}: produto_id banco={produto_id_atual!r} "
                f"CSV={registro.produto_id!r}"
            )
        if marca_atual != registro.marca_antiga:
            divergencias.append(
                f"preco_id {registro.preco_id}: marca banco={marca_atual!r} "
                f"CSV={registro.marca_antiga!r}"
            )

    if divergencias:
        detalhes = "\n".join(f"  - {item}" for item in divergencias[:20])
        if len(divergencias) > 20:
            detalhes += f"\n  - ... e mais {len(divergencias) - 20} divergencias"
        raise ErroSeguranca("Banco divergiu da previa CSV:\n" + detalhes)


def imprimir_relatorio_dry_run(registros: List[RegistroCorrecao]) -> None:
    contagem_marcas = Counter(registro.marca_antiga for registro in registros)

    print("=" * 72)
    print("DRY-RUN - CORRECAO DE MARCAS INVALIDAS EM PRECOS_FORNECEDORES")
    print("=" * 72)
    print(f"Banco: {CAMINHO_BANCO}")
    print(f"CSV: {CAMINHO_CSV}")
    print(f"Registros que seriam alterados: {len(registros)}")
    print(f"Novo valor configurado: {NOVO_VALOR_MARCA!r} (SQL NULL)")
    print("\nTotal por marca atual:")
    for marca, total in sorted(contagem_marcas.items()):
        print(f"  {marca!r}: {total}")

    print("\nExemplos:")
    for registro in registros[:MAX_EXEMPLOS]:
        nome = registro.sku_master or registro.produto_padrao
        print(
            f"  preco_id={registro.preco_id} | produto_id={registro.produto_id} "
            f"| marca={registro.marca_antiga!r} | produto={nome}"
        )

    print("\nCONFIRMACAO: nenhum UPDATE foi executado; banco aberto somente leitura.")


def criar_backup(timestamp: str) -> Path:
    PASTA_BACKUPS.mkdir(parents=True, exist_ok=True)
    caminho_backup = (
        PASTA_BACKUPS
        / f"medbox_v3_antes_marcas_invalidas_{timestamp}.db"
    )
    if caminho_backup.exists():
        raise ErroSeguranca(f"Backup ja existe: {caminho_backup}")

    origem = conectar_somente_leitura()
    destino = sqlite3.connect(caminho_backup)
    try:
        origem.backup(destino)
    finally:
        destino.close()
        origem.close()

    if not caminho_backup.is_file() or caminho_backup.stat().st_size <= 0:
        raise ErroSeguranca("Backup nao foi criado corretamente.")
    return caminho_backup


def preparar_auditoria_pendente(
    registros: List[RegistroCorrecao],
    timestamp: str,
    data_hora: str,
) -> Tuple[Path, Path]:
    caminho_final = PASTA_BACKUPS / f"auditoria_marcas_invalidas_{timestamp}.csv"
    caminho_pendente = caminho_final.with_suffix(".csv.pending")
    if caminho_final.exists() or caminho_pendente.exists():
        raise ErroSeguranca("Arquivo de auditoria ja existe para este timestamp.")

    with caminho_pendente.open("x", encoding="utf-8-sig", newline="") as arquivo:
        escritor = csv.DictWriter(
            arquivo,
            fieldnames=["preco_id", "marca_antiga", "marca_nova", "data_hora"],
            delimiter=";",
        )
        escritor.writeheader()
        for registro in registros:
            escritor.writerow(
                {
                    "preco_id": registro.preco_id,
                    "marca_antiga": registro.marca_antiga,
                    "marca_nova": "NULL" if NOVO_VALOR_MARCA is None else NOVO_VALOR_MARCA,
                    "data_hora": data_hora,
                }
            )
    return caminho_pendente, caminho_final


def aplicar_correcao(registros: List[RegistroCorrecao]) -> None:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    data_hora = datetime.now().isoformat(timespec="seconds")
    caminho_backup = criar_backup(timestamp)
    caminho_pendente, caminho_auditoria = preparar_auditoria_pendente(
        registros, timestamp, data_hora
    )

    conexao: Optional[sqlite3.Connection] = None
    commit_concluido = False
    try:
        conexao = sqlite3.connect(CAMINHO_BANCO)
        conexao.row_factory = sqlite3.Row
        conexao.execute("BEGIN IMMEDIATE")
        validar_estado_banco(conexao, registros)

        atualizados = 0
        for registro in registros:
            cursor = conexao.execute(
                "UPDATE precos_fornecedores SET marca = ? "
                "WHERE id = ? AND marca = ?",
                (NOVO_VALOR_MARCA, registro.preco_id, registro.marca_antiga),
            )
            if cursor.rowcount != 1:
                raise ErroSeguranca(
                    f"preco_id {registro.preco_id}: UPDATE nao afetou exatamente 1 linha."
                )
            atualizados += cursor.rowcount

        if atualizados != TOTAL_ESPERADO:
            raise ErroSeguranca(
                f"Total atualizado invalido: {atualizados}; esperado {TOTAL_ESPERADO}."
            )

        conexao.commit()
        commit_concluido = True
    except Exception:
        if conexao is not None:
            conexao.rollback()
        if caminho_pendente.exists():
            caminho_pendente.unlink()
        raise
    finally:
        if conexao is not None:
            conexao.close()

    if commit_concluido:
        caminho_pendente.replace(caminho_auditoria)
        print(f"Backup criado: {caminho_backup}")
        print(f"Auditoria criada: {caminho_auditoria}")
        print(f"Registros atualizados: {TOTAL_ESPERADO}")


def criar_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Valida e, somente com confirmacao explicita, limpa marcas invalidas "
            "listadas na previa CSV."
        )
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Habilita o caminho de escrita. Sem este argumento o modo e DRY-RUN.",
    )
    parser.add_argument(
        "--confirmar",
        action="store_true",
        help="Confirmacao adicional obrigatoria para usar junto com --apply.",
    )
    return parser


def main() -> int:
    argumentos = criar_parser().parse_args()

    try:
        if argumentos.confirmar and not argumentos.apply:
            raise ErroSeguranca("--confirmar so pode ser usado junto com --apply.")
        if argumentos.apply and not argumentos.confirmar:
            raise ErroSeguranca("APPLY exige os argumentos --apply e --confirmar.")

        validar_git(modo_apply=argumentos.apply)
        registros = carregar_registros_csv()

        conexao = conectar_somente_leitura()
        try:
            validar_estado_banco(conexao, registros)
        finally:
            conexao.close()

        if not argumentos.apply:
            imprimir_relatorio_dry_run(registros)
            return 0

        aplicar_correcao(registros)
        return 0
    except ErroSeguranca as erro:
        print(f"ABORTADO COM SEGURANCA: {erro}", file=sys.stderr)
        print("Nenhuma alteracao foi aplicada por esta execucao.", file=sys.stderr)
        return 2
    except Exception as erro:
        print(f"ERRO INESPERADO: {erro}", file=sys.stderr)
        print("A execucao foi interrompida.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
