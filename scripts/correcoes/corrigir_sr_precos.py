#!/usr/bin/env python3
"""Dry-run seguro para aplicar a decisao aprovada dos 13 registros SR.

Modo padrao: DRY-RUN, sem escrita no banco.

Modo APPLY futuro: exige simultaneamente ``--apply`` e ``--confirmar``.
Nesta etapa o APPLY nao deve ser executado.
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
from typing import Dict, Iterable, List, Optional, Tuple


BASE_DIR = Path(__file__).resolve().parents[2]
CAMINHO_BANCO = BASE_DIR / "banco" / "medbox_v3.db"
CAMINHO_CSV = BASE_DIR / "scripts" / "diagnosticos" / "decisao_manual_sr.csv"
PASTA_BACKUPS = BASE_DIR / "backups"

TOTAL_ESPERADO = 13
TOTAL_SALDANHA = 4
TOTAL_NULL = 9
MARCA_SR_COMPACTA = "SR"
MARCA_SALDANHA = "SALDANHA RODRIGUES"
DECISAO_SALDANHA = "MANTER_OU_CONFIRMAR_SALDANHA_RODRIGUES"
DECISAO_NULL = "REMOVER_SR_COMO_MARCA_INVALIDA"
MAX_EXEMPLOS = 20

IDS_SALDANHA_ESPERADOS = {1025, 1026, 1027, 1028}
IDS_NULL_ESPERADOS = {1022, 1030, 1031, 1032, 1034, 1036, 1037, 1038, 1041}

DECISOES_USUARIO_COMPATIVEIS = {
    DECISAO_SALDANHA: {
        "",
        DECISAO_SALDANHA,
        "MANTER",
        "CONFIRMAR",
        "CONFIRMAR_SALDANHA_RODRIGUES",
        MARCA_SALDANHA,
    },
    DECISAO_NULL: {
        "",
        DECISAO_NULL,
        "REMOVER",
        "REMOVER_SR",
        "NULL",
        "NULO",
        "REMOVER_MARCA_INVALIDA",
    },
}


class ErroSeguranca(RuntimeError):
    """Falha de pre-condicao que deve abortar sem alterar o banco."""


@dataclass(frozen=True)
class RegistroSR:
    preco_id: int
    produto_id: int
    produto_padrao: str
    sku_master: str
    fabricante_produto: str
    marca_preco_atual: str
    fornecedor: str
    preco: str
    data_importacao: str
    descricao_original: str
    decisao_recomendada: str
    decisao_usuario: str

    @property
    def marca_nova(self) -> Optional[str]:
        if self.decisao_recomendada == DECISAO_SALDANHA:
            return MARCA_SALDANHA
        if self.decisao_recomendada == DECISAO_NULL:
            return None
        raise ErroSeguranca(
            f"preco_id {self.preco_id}: decisao sem marca nova definida."
        )


def _compactar(valor: str) -> str:
    return "".join(str(valor or "").upper().split())


def _normalizar_decisao(valor: str) -> str:
    return str(valor or "").strip().upper()


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


def carregar_csv() -> List[RegistroSR]:
    if not CAMINHO_CSV.is_file():
        raise ErroSeguranca(f"CSV de decisao manual nao encontrado: {CAMINHO_CSV}")

    campos_obrigatorios = {
        "preco_id",
        "produto_id",
        "produto_padrao",
        "sku_master",
        "fabricante_produto",
        "marca_preco_atual",
        "fornecedor",
        "preco",
        "data_importacao",
        "descricao_original",
        "decisao_recomendada",
        "decisao_usuario",
    }

    registros: List[RegistroSR] = []
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
                preco_id = int(str(linha.get("preco_id") or "").strip())
                produto_id = int(str(linha.get("produto_id") or "").strip())
            except ValueError as erro:
                raise ErroSeguranca(
                    f"Linha {numero_linha}: preco_id/produto_id invalido."
                ) from erro

            decisao_recomendada = _normalizar_decisao(
                str(linha.get("decisao_recomendada") or "")
            )
            if decisao_recomendada not in {DECISAO_SALDANHA, DECISAO_NULL}:
                raise ErroSeguranca(
                    f"Linha {numero_linha}: decisao_recomendada inesperada: "
                    f"{decisao_recomendada!r}."
                )

            decisao_usuario = _normalizar_decisao(
                str(linha.get("decisao_usuario") or "")
            )
            if decisao_usuario not in DECISOES_USUARIO_COMPATIVEIS[decisao_recomendada]:
                raise ErroSeguranca(
                    f"Linha {numero_linha}: decisao_usuario={decisao_usuario!r} "
                    f"incompativel com {decisao_recomendada!r}."
                )

            marca_preco_atual = str(linha.get("marca_preco_atual") or "").strip()
            if _compactar(marca_preco_atual) != MARCA_SR_COMPACTA:
                raise ErroSeguranca(
                    f"Linha {numero_linha}: marca_preco_atual nao e SR: "
                    f"{marca_preco_atual!r}."
                )

            registros.append(
                RegistroSR(
                    preco_id=preco_id,
                    produto_id=produto_id,
                    produto_padrao=str(linha.get("produto_padrao") or ""),
                    sku_master=str(linha.get("sku_master") or ""),
                    fabricante_produto=str(linha.get("fabricante_produto") or "").strip(),
                    marca_preco_atual=marca_preco_atual,
                    fornecedor=str(linha.get("fornecedor") or ""),
                    preco=str(linha.get("preco") or ""),
                    data_importacao=str(linha.get("data_importacao") or ""),
                    descricao_original=str(linha.get("descricao_original") or ""),
                    decisao_recomendada=decisao_recomendada,
                    decisao_usuario=decisao_usuario,
                )
            )

    validar_registros_csv(registros)
    return registros


def validar_registros_csv(registros: List[RegistroSR]) -> None:
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

    ids_saldanha = {
        registro.preco_id
        for registro in registros
        if registro.decisao_recomendada == DECISAO_SALDANHA
    }
    ids_null = {
        registro.preco_id
        for registro in registros
        if registro.decisao_recomendada == DECISAO_NULL
    }

    if ids_saldanha != IDS_SALDANHA_ESPERADOS:
        raise ErroSeguranca(
            "IDs para SALDANHA RODRIGUES divergentes. "
            f"Atual={sorted(ids_saldanha)} esperado={sorted(IDS_SALDANHA_ESPERADOS)}"
        )
    if ids_null != IDS_NULL_ESPERADOS:
        raise ErroSeguranca(
            "IDs para NULL divergentes. "
            f"Atual={sorted(ids_null)} esperado={sorted(IDS_NULL_ESPERADOS)}"
        )

    if len(ids_saldanha) != TOTAL_SALDANHA or len(ids_null) != TOTAL_NULL:
        raise ErroSeguranca(
            f"Totais invalidos: SALDANHA={len(ids_saldanha)}, NULL={len(ids_null)}."
        )

    for registro in registros:
        fabricante = registro.fabricante_produto.strip().upper()
        if registro.decisao_recomendada == DECISAO_SALDANHA:
            if fabricante != MARCA_SALDANHA:
                raise ErroSeguranca(
                    f"preco_id {registro.preco_id}: fabricante deveria ser "
                    f"SALDANHA RODRIGUES, mas e {registro.fabricante_produto!r}."
                )
        elif fabricante == MARCA_SALDANHA:
            raise ErroSeguranca(
                f"preco_id {registro.preco_id}: registro para NULL nao pode ter "
                "fabricante_produto SALDANHA RODRIGUES."
            )


def conectar_somente_leitura() -> sqlite3.Connection:
    if not CAMINHO_BANCO.is_file():
        raise ErroSeguranca(f"Banco nao encontrado: {CAMINHO_BANCO}")

    uri = CAMINHO_BANCO.resolve().as_uri() + "?mode=ro"
    conexao = sqlite3.connect(uri, uri=True)
    conexao.row_factory = sqlite3.Row
    return conexao


def validar_estado_banco(
    conexao: sqlite3.Connection,
    registros: List[RegistroSR],
) -> None:
    ids = [registro.preco_id for registro in registros]
    placeholders = ",".join("?" for _ in ids)
    linhas = conexao.execute(
        "SELECT id, produto_id, marca FROM precos_fornecedores "
        f"WHERE id IN ({placeholders})",
        ids,
    ).fetchall()
    atuais: Dict[int, sqlite3.Row] = {int(linha["id"]): linha for linha in linhas}

    faltantes = sorted(set(ids) - set(atuais))
    if faltantes:
        raise ErroSeguranca(
            "preco_id nao encontrado no banco: " + ", ".join(map(str, faltantes))
        )

    divergencias: List[str] = []
    for registro in registros:
        atual = atuais[registro.preco_id]
        produto_id_atual = int(atual["produto_id"])
        marca_atual = atual["marca"]
        if produto_id_atual != registro.produto_id:
            divergencias.append(
                f"preco_id {registro.preco_id}: produto_id banco={produto_id_atual!r} "
                f"CSV={registro.produto_id!r}"
            )
        if _compactar(str(marca_atual or "")) != MARCA_SR_COMPACTA:
            divergencias.append(
                f"preco_id {registro.preco_id}: marca banco={marca_atual!r}; "
                "esperado SR/S R"
            )

    if divergencias:
        detalhes = "\n".join(f"  - {item}" for item in divergencias[:20])
        raise ErroSeguranca("Banco divergiu da decisao CSV:\n" + detalhes)


def filtrar_por_decisao(
    registros: Iterable[RegistroSR],
    decisao: str,
) -> List[RegistroSR]:
    return [registro for registro in registros if registro.decisao_recomendada == decisao]


def imprimir_relatorio_dry_run(registros: List[RegistroSR]) -> None:
    saldanha = filtrar_por_decisao(registros, DECISAO_SALDANHA)
    nulls = filtrar_por_decisao(registros, DECISAO_NULL)

    print("=" * 72)
    print("DRY-RUN - CORRECAO MANUAL APROVADA DE SR EM PRECOS_FORNECEDORES")
    print("=" * 72)
    print(f"Banco: {CAMINHO_BANCO}")
    print(f"CSV: {CAMINHO_CSV}")
    print(f"Registros validados: {len(registros)}")
    print(f"Atualizariam para SALDANHA RODRIGUES: {len(saldanha)}")
    print(f"Atualizariam para NULL: {len(nulls)}")

    print("\n4 registros que seriam atualizados para SALDANHA RODRIGUES:")
    for registro in saldanha[:MAX_EXEMPLOS]:
        nome = registro.sku_master or registro.produto_padrao
        print(
            f"  preco_id={registro.preco_id} | produto_id={registro.produto_id} "
            f"| fabricante={registro.fabricante_produto} | produto={nome}"
        )

    print("\n9 registros que seriam atualizados para NULL:")
    for registro in nulls[:MAX_EXEMPLOS]:
        nome = registro.sku_master or registro.produto_padrao
        print(
            f"  preco_id={registro.preco_id} | produto_id={registro.produto_id} "
            f"| fabricante={registro.fabricante_produto} | produto={nome}"
        )

    print("\nCONFIRMACAO: nenhum UPDATE foi executado; banco aberto somente leitura.")


def criar_backup(timestamp: str) -> Path:
    PASTA_BACKUPS.mkdir(parents=True, exist_ok=True)
    caminho_backup = PASTA_BACKUPS / f"medbox_v3_antes_correcao_sr_{timestamp}.db"
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


def preparar_auditoria(
    registros: List[RegistroSR],
    timestamp: str,
    data_hora: str,
) -> Tuple[Path, Path]:
    caminho_final = PASTA_BACKUPS / f"auditoria_correcao_sr_{timestamp}.csv"
    caminho_pendente = caminho_final.with_suffix(".csv.pending")
    if caminho_final.exists() or caminho_pendente.exists():
        raise ErroSeguranca("Arquivo de auditoria ja existe para este timestamp.")

    with caminho_pendente.open("x", encoding="utf-8-sig", newline="") as arquivo:
        escritor = csv.DictWriter(
            arquivo,
            fieldnames=[
                "preco_id",
                "produto_id",
                "marca_antiga",
                "marca_nova",
                "decisao_recomendada",
                "data_hora",
            ],
            delimiter=";",
        )
        escritor.writeheader()
        for registro in registros:
            marca_nova = registro.marca_nova
            escritor.writerow(
                {
                    "preco_id": registro.preco_id,
                    "produto_id": registro.produto_id,
                    "marca_antiga": registro.marca_preco_atual,
                    "marca_nova": "NULL" if marca_nova is None else marca_nova,
                    "decisao_recomendada": registro.decisao_recomendada,
                    "data_hora": data_hora,
                }
            )
    return caminho_pendente, caminho_final


def aplicar_correcao(registros: List[RegistroSR]) -> None:
    validar_git_para_apply()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    data_hora = datetime.now().isoformat(timespec="seconds")

    caminho_backup = criar_backup(timestamp)
    caminho_pendente, caminho_auditoria = preparar_auditoria(
        registros, timestamp, data_hora
    )

    conexao: Optional[sqlite3.Connection] = None
    try:
        conexao = sqlite3.connect(CAMINHO_BANCO)
        conexao.row_factory = sqlite3.Row
        conexao.execute("BEGIN IMMEDIATE")
        validar_estado_banco(conexao, registros)

        atualizados = 0
        for registro in registros:
            cursor = conexao.execute(
                "UPDATE precos_fornecedores SET marca = ? "
                "WHERE id = ? AND UPPER(REPLACE(TRIM(COALESCE(marca, '')), ' ', '')) = ?",
                (registro.marca_nova, registro.preco_id, MARCA_SR_COMPACTA),
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
    except Exception:
        if conexao is not None:
            conexao.rollback()
        if caminho_pendente.exists():
            caminho_pendente.unlink()
        raise
    finally:
        if conexao is not None:
            conexao.close()

    caminho_pendente.replace(caminho_auditoria)
    print(f"Backup criado: {caminho_backup}")
    print(f"Auditoria criada: {caminho_auditoria}")
    print(f"Registros atualizados: {TOTAL_ESPERADO}")


def criar_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Valida e, somente com confirmacao explicita futura, aplica a decisao "
            "manual aprovada para os 13 registros SR."
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

        registros = carregar_csv()

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
