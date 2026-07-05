"""Persiste no banco os PDFs de Ordem de Compra JÁ BAIXADOS localmente.

NÃO fala com o Gmail — só lê arquivos que já existem em
data/gmail_cotacoes/anexos/<label>/<message_id>/, parseia com
parser_pdf_oc.py e grava em gmail_vendas_oc via persistencia.py.

Uso:
    .venv\\Scripts\\python.exe scripts/gmail_cotacoes/persistir_dashboard_local.py --limite 2 --salvar-dashboard

Sem --salvar-dashboard, roda em modo de conferência (mostra o que seria
gravado) e recusa gravar no banco.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

import config
from extrator_anexos import parece_ordem_compra
from parser_pdf_oc import parse_pdf_oc
from persistencia import calcular_hash_arquivo, caminho_relativo_projeto, montar_chave_dedupe, salvar_gmail_venda_oc

# Vendedora conhecida por message_id — sobrepõe o nome da subpasta de label
# quando os dois divergem (ex.: mensagem no marcador PEDIDO cuja vendedora
# real, confirmada em teste anterior de buscar-amostra, é LAYANE).
VENDEDORA_CONHECIDA = {
    "19f24864f5278c56": "STHEFANY",
    "19f2882c810825d5": "LAYANE",
}


def _resolver_vendedora(label: str, message_id: str) -> str:
    if message_id in VENDEDORA_CONHECIDA:
        return VENDEDORA_CONHECIDA[message_id]
    if label in config.VENDEDORAS:
        return label
    return config.SEM_VENDEDORA


def _descobrir_mensagens_com_oc(pasta_anexos: Path) -> list[tuple[str, str, Path]]:
    """Retorna [(label, message_id, caminho_pdf)] — 1 arquivo por mensagem
    (o de nome mais curto/canônico, para manter chave_dedupe estável entre
    execuções mesmo havendo cópias '_2', '_3' de downloads repetidos)."""
    encontrados: list[tuple[str, str, Path]] = []
    if not pasta_anexos.exists():
        return encontrados

    for pasta_label in sorted(pasta_anexos.iterdir()):
        if not pasta_label.is_dir():
            continue
        for pasta_mensagem in sorted(pasta_label.iterdir()):
            if not pasta_mensagem.is_dir():
                continue
            candidatos = sorted(
                (f for f in pasta_mensagem.iterdir() if f.is_file() and parece_ordem_compra(f.name)),
                key=lambda f: (len(f.name), f.name),
            )
            if candidatos:
                encontrados.append((pasta_label.name, pasta_mensagem.name, candidatos[0]))

    return encontrados


def _montar_registro(label: str, message_id: str, caminho_pdf: Path) -> dict:
    vendedora = _resolver_vendedora(label, message_id)
    oc = parse_pdf_oc(caminho_pdf)

    hash_arquivo = calcular_hash_arquivo(caminho_pdf)
    valor_total_oc = oc.valor_total_impresso if oc.valor_total_impresso is not None else oc.valor_total_calculado
    divergencia_total = None
    if oc.valor_total_impresso is not None:
        divergencia_total = round(oc.valor_total_calculado - oc.valor_total_impresso, 2)

    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    return {
        "chave_dedupe": montar_chave_dedupe(message_id, None, caminho_pdf.name, hash_arquivo),
        "id_email": message_id,
        "thread_id": None,
        "attachment_id": None,
        "message_internal_date": None,
        "assunto": None,
        "remetente": None,
        "data_email": None,
        "data_venda": oc.data_oc,
        "numero_oc": oc.numero_oc,
        "vendedora": vendedora,
        "cliente": oc.cliente,
        "status_email": "VENDA_CONFIRMADA",
        "status_revisao": "REVISAR_VENDEDORA" if vendedora == config.SEM_VENDEDORA else "",
        "considerar_venda": "SIM",
        "motivo_exclusao": "",
        "tem_marcador_pedido": "SIM",
        "tem_marcador_cancelado": "NAO",
        "tem_anexo_ordem_compra": "SIM",
        "nome_arquivo": caminho_pdf.name,
        "caminho_anexo": caminho_relativo_projeto(caminho_pdf),
        "hash_arquivo": hash_arquivo,
        "tamanho_arquivo": caminho_pdf.stat().st_size,
        "tipo_anexo": "application/pdf",
        "metodo_extracao": oc.metodo_extracao,
        "avisos_parser": "; ".join(oc.avisos) if oc.avisos else "",
        "quantidade_itens": len(oc.itens),
        "valor_total_oc": valor_total_oc,
        "valor_total_impresso": oc.valor_total_impresso,
        "valor_total_calculado": oc.valor_total_calculado,
        "divergencia_total": divergencia_total,
        "erro_processamento": "",
        "data_processamento": agora,
        "origem_execucao": "PDF_LOCAL_VALIDADO",
    }


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Persiste PDFs de OC já baixados localmente em gmail_vendas_oc (sem tocar Gmail)")
    p.add_argument("--limite", type=int, default=None, help="Limita quantas mensagens conhecidas são processadas")
    p.add_argument("--salvar-dashboard", action="store_true", help="Grava de fato no banco. Sem esta flag, só mostra o que seria gravado.")
    p.add_argument("--pasta-anexos", type=str, default=str(config.ANEXOS_DIR), help="Pasta com os anexos já baixados")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    pasta_anexos = Path(args.pasta_anexos)

    mensagens = _descobrir_mensagens_com_oc(pasta_anexos)
    if args.limite is not None:
        mensagens = mensagens[: args.limite]

    if not mensagens:
        print(f"Nenhum PDF de Ordem de Compra encontrado em {pasta_anexos}.")
        return 1

    print(f"Encontradas {len(mensagens)} mensagem(ns) com OC reconhecida em {pasta_anexos}:")

    registros = []
    for label, message_id, caminho_pdf in mensagens:
        print(f"  - {label}/{message_id}/{caminho_pdf.name}")
        try:
            registro = _montar_registro(label, message_id, caminho_pdf)
        except Exception as exc:
            print(f"    ERRO ao parsear: {exc}")
            continue
        registros.append(registro)
        print(f"    numero_oc={registro['numero_oc']} data_venda={registro['data_venda']} "
              f"vendedora={registro['vendedora']} cliente={registro['cliente']} "
              f"valor_total_oc={registro['valor_total_oc']} itens={registro['quantidade_itens']} "
              f"metodo={registro['metodo_extracao']}")
        if registro["avisos_parser"]:
            print(f"    avisos: {registro['avisos_parser']}")

    if not args.salvar_dashboard:
        print("\n--salvar-dashboard não informado — NADA foi gravado no banco (modo de conferência).")
        return 0

    total_salvos = 0
    for registro in registros:
        id_salvo = salvar_gmail_venda_oc(registro)
        total_salvos += 1
        print(f"Gravado: id={id_salvo} chave_dedupe={registro['chave_dedupe'][:12]}...")

    print(f"\n{total_salvos} registro(s) gravado(s) em gmail_vendas_oc.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
