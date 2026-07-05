"""Robô Gmail Cotações — orquestrador principal.

Modo suportado hoje: SOMENTE LOCAL (--somente-local + --manifesto-local).
Não há integração real com a Gmail API neste estágio (ver gmail_client.py)
— nenhum e-mail é lido, baixado ou enviado. --dry-run documenta a
intenção de não realizar nenhuma ação destrutiva/externa; os relatórios
locais (XLSX/TXT/CSV) são gerados normalmente mesmo em --dry-run, pois
gerar arquivo de relatório em disco não é uma ação destrutiva.

Exemplo (caso real HMAR 1006):
  python scripts/gmail_cotacoes/main.py --somente-local \\
      --manifesto-local data/gmail_cotacoes/amostras/manifesto_hmar_1006_real.json \\
      --saida data/gmail_cotacoes/relatorios/relatorio_hmar_1006_real.xlsx --dry-run
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import config
from correlacionador import calcular_score_email, cruzar_itens
from extrator_anexos import localizar_anexo
from gerador_relatorios import gerar_relatorios
from manifesto_local import carregar_manifesto
from parser_excel_cotacao import parse_excel_cotacao
from parser_pdf_oc import parse_pdf_oc
from parser_pdf_proposta import parse_pdf_proposta

logger = logging.getLogger("robo_gmail_cotacoes")


def _configurar_logging() -> None:
    config.LOGS_DIR.mkdir(parents=True, exist_ok=True)
    arquivo_log = config.LOGS_DIR / "robo_gmail_cotacoes.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(arquivo_log, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Robô Gmail Cotações MedBox — modo local")
    p.add_argument("--dry-run", action="store_true", help="Não realiza nenhuma ação destrutiva/externa (Gmail API não é chamada de qualquer forma nesta versão)")
    p.add_argument("--somente-local", action="store_true", help="Usa manifesto local em vez da Gmail API real")
    p.add_argument("--manifesto-local", type=str, default=None, help="Caminho do manifesto JSON local")
    p.add_argument("--pasta-amostras", type=str, default=str(config.AMOSTRAS_DIR), help="Pasta com os anexos reais/de amostra")
    p.add_argument("--saida", type=str, default=str(config.RELATORIOS_DIR / "relatorio.xlsx"), help="Caminho do XLSX de saída")
    p.add_argument("--limite-cotacoes", type=int, default=None, help="Limita quantos casos do manifesto são processados")
    p.add_argument("--limite-pedidos", type=int, default=None, help="Limita quantos itens da Ordem de Compra são considerados por caso")
    return p.parse_args(argv)


def _processar_caso(caso, pasta_amostras: Path, limite_pedidos: int | None) -> dict:
    avisos: list[str] = []

    caminho_excel = localizar_anexo(caso.arquivo_excel_cotacao_cliente, pasta_amostras)
    cotacao_excel = parse_excel_cotacao(caminho_excel)

    caminho_oc = localizar_anexo(caso.arquivo_pdf_ordem_compra, pasta_amostras)
    ordem_compra = parse_pdf_oc(caminho_oc)
    avisos.extend(ordem_compra.avisos)
    if limite_pedidos is not None:
        ordem_compra.itens = ordem_compra.itens[:limite_pedidos]

    proposta_pdf = None
    try:
        caminho_proposta = localizar_anexo(caso.arquivo_pdf_proposta, pasta_amostras)
        proposta_pdf = parse_pdf_proposta(caminho_proposta)
        avisos.extend(proposta_pdf.avisos)
    except Exception as exc:  # best-effort: nunca derruba o pipeline principal
        avisos.append(f"parser_pdf_proposta falhou (não bloqueante, fonte oficial é o Excel): {exc}")
        logger.warning("Falha ao processar PDF da proposta (%s): %s", caso.arquivo_pdf_proposta, exc)

    score_email = calcular_score_email(
        cliente=caso.cliente,
        categoria=caso.categoria,
        mes_referencia=caso.mes_referencia,
        numero_cotacao=caso.numero_cotacao,
        assunto_cotacao=caso.assunto_cotacao,
        assunto_pedido=caso.assunto_pedido,
        data_cotacao=str(cotacao_excel.data_pedido) if cotacao_excel.data_pedido else None,
        data_pedido=ordem_compra.data_oc,
        itens_cotados_desc=[i.descricao for i in cotacao_excel.itens],
        itens_oc_desc=[i.descricao for i in ordem_compra.itens],
        nomes_anexos=[caso.arquivo_pdf_proposta, caso.arquivo_excel_cotacao_cliente, caso.arquivo_pdf_ordem_compra],
    )

    cruzamento = cruzar_itens(cotacao_excel.itens, ordem_compra.itens)

    return {
        "caso": caso,
        "cotacao_excel": cotacao_excel,
        "ordem_compra": ordem_compra,
        "proposta_pdf": proposta_pdf,
        "score_email": score_email,
        "cruzamento": cruzamento,
        "avisos": avisos,
    }


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    _configurar_logging()

    if not args.somente_local:
        logger.error(
            "Modo Gmail real não está configurado nesta versão do robô. "
            "Rode novamente com --somente-local --manifesto-local <arquivo>."
        )
        return 2

    manifesto = args.manifesto_local
    if manifesto is None:
        padrao = config.AMOSTRAS_DIR / "manifesto_hmar_1006_real.json"
        if not padrao.exists():
            logger.error("Nenhum --manifesto-local informado e o padrão %s não existe.", padrao)
            return 2
        manifesto = str(padrao)

    logger.info("Modo: SOMENTE LOCAL | dry-run=%s | manifesto=%s", args.dry_run, manifesto)

    try:
        casos = carregar_manifesto(manifesto)
    except Exception as exc:
        logger.error("Falha ao carregar manifesto: %s", exc)
        return 1

    if args.limite_cotacoes is not None:
        casos = casos[: args.limite_cotacoes]

    pasta_amostras = Path(args.pasta_amostras)
    casos_processados = []
    for caso in casos:
        logger.info("Processando cotação %s (%s / %s)", caso.numero_cotacao, caso.vendedora, caso.cliente)
        try:
            resultado = _processar_caso(caso, pasta_amostras, args.limite_pedidos)
        except Exception as exc:
            logger.error("Falha ao processar caso %s: %s", caso.numero_cotacao, exc)
            continue
        casos_processados.append(resultado)

        for aviso in resultado["avisos"]:
            logger.warning("[%s] %s", caso.numero_cotacao, aviso)

    if not casos_processados:
        logger.error("Nenhum caso processado com sucesso — nenhum relatório será gerado.")
        return 1

    abas = gerar_relatorios(casos_processados, args.saida)

    logger.info("Relatório gerado em %s", args.saida)
    for nome_aba, linhas in abas.items():
        logger.info("  %s: %d linha(s)", nome_aba, len(linhas))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
