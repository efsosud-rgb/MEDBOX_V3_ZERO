"""Robô Gmail Cotações — orquestrador principal.

Dois modos, mutuamente exclusivos:

1. --somente-local + --manifesto-local (Fase 1, inalterado): processa um
   manifesto JSON local com anexos já em disco. Nenhuma chamada de rede.

2. --gmail-real + --acao-gmail (Fase 2): diagnóstico SOMENTE LEITURA
   contra a Gmail API real (escopo gmail.readonly). Nunca envia, altera,
   arquiva ou apaga e-mail algum — ver gmail_client.py. Sempre exige
   --dry-run e pelo menos um limite explícito (--limite-cotacoes e/ou
   --limite-pedidos), para nunca processar a caixa inteira por acidente.

Exemplo modo local (caso real HMAR 1006):
  python scripts/gmail_cotacoes/main.py --somente-local \\
      --manifesto-local data/gmail_cotacoes/amostras/manifesto_hmar_1006_real.json \\
      --saida data/gmail_cotacoes/relatorios/relatorio_hmar_1006_real.xlsx --dry-run

Exemplos modo Gmail real (diagnóstico):
  python scripts/gmail_cotacoes/main.py --gmail-real --dry-run --limite-cotacoes 1 \\
      --acao-gmail listar-labels

  python scripts/gmail_cotacoes/main.py --gmail-real --dry-run --limite-cotacoes 1 \\
      --acao-gmail verificar-marcadores

  python scripts/gmail_cotacoes/main.py --gmail-real --dry-run --limite-cotacoes 1 \\
      --acao-gmail buscar-amostra --marcador STHEFANY

  python scripts/gmail_cotacoes/main.py --gmail-real --dry-run --limite-cotacoes 1 --limite-pedidos 1 \\
      --acao-gmail baixar-anexos-amostra --marcador PEDIDO
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date, datetime
from pathlib import Path

import config
from correlacionador import calcular_score_email, classificar_email_venda, cruzar_itens, extrair_marcadores_presentes
from extrator_anexos import localizar_anexo, parece_ordem_compra
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
    p = argparse.ArgumentParser(description="Robô Gmail Cotações MedBox")
    p.add_argument("--dry-run", action="store_true", help="Nenhuma ação destrutiva/externa além de leitura")
    p.add_argument("--somente-local", action="store_true", help="Usa manifesto local em vez da Gmail API real")
    p.add_argument("--manifesto-local", type=str, default=None, help="Caminho do manifesto JSON local")
    p.add_argument("--pasta-amostras", type=str, default=str(config.AMOSTRAS_DIR), help="Pasta com os anexos reais/de amostra")
    p.add_argument("--saida", type=str, default=str(config.RELATORIOS_DIR / "relatorio.xlsx"), help="Caminho do XLSX de saída")
    p.add_argument("--limite-cotacoes", type=int, default=None, help="Modo local: limita casos do manifesto. Modo Gmail real: limita mensagens buscadas por marcador")
    p.add_argument("--limite-pedidos", type=int, default=None, help="Modo local: limita itens da OC considerados. Modo Gmail real: limita anexos baixados por mensagem")

    p.add_argument("--gmail-real", action="store_true", help="Ativa diagnóstico SOMENTE LEITURA contra a Gmail API real (nunca envia/altera/apaga nada)")
    p.add_argument("--acao-gmail", type=str, default=None,
                    choices=["listar-labels", "verificar-marcadores", "buscar-amostra", "baixar-anexos-amostra", "contar-por-periodo", "sincronizar-pedidos-dashboard"],
                    help="Ação de diagnóstico do modo --gmail-real")
    p.add_argument("--marcador", type=str, default=None,
                    help="Restringe buscar-amostra/baixar-anexos-amostra a um marcador (JESSICA/STHEFANY/PAMELA/LAYANE/PEDIDO/CANCELADO). Padrão: todos")
    p.add_argument("--data-inicio", type=str, default=None,
                    help="Filtro pela data do e-mail no Gmail, formato YYYY-MM-DD (nao altera DATA_VENDA da OC)")
    p.add_argument("--data-fim", type=str, default=None,
                    help="Filtro pela data do e-mail no Gmail, formato YYYY-MM-DD, inclusivo (nao altera DATA_VENDA da OC)")
    p.add_argument("--salvar-dashboard", action="store_true",
                    help="Grava vendas/itens no dashboard local. Nunca altera Gmail.")
    p.add_argument("--credentials-json", type=str, default=str(config.CREDENTIALS_PATH), help="Caminho do credentials.json OAuth")
    p.add_argument("--token-gmail", type=str, default=str(config.TOKEN_GMAIL_PATH), help="Caminho do token_gmail.json")

    return p.parse_args(argv)


def _validar_periodo_datas(data_inicio: str | None, data_fim: str | None) -> None:
    try:
        inicio = date.fromisoformat(data_inicio) if data_inicio else None
        fim = date.fromisoformat(data_fim) if data_fim else None
    except ValueError as exc:
        raise ValueError("Datas devem usar o formato YYYY-MM-DD.") from exc
    if inicio and fim and inicio > fim:
        raise ValueError("--data-inicio nao pode ser maior que --data-fim.")


def _vendedora_de_classificacao(marcadores_presentes: set[str]) -> str:
    for vendedora in config.VENDEDORAS:
        if vendedora in marcadores_presentes:
            return vendedora
    return config.SEM_VENDEDORA


def _montar_registro_oc_gmail(email, anexo: dict, oc, classificacao) -> dict:
    from persistencia import calcular_hash_arquivo, caminho_relativo_projeto, montar_chave_dedupe

    caminho = anexo["caminho"]
    hash_arquivo = calcular_hash_arquivo(caminho)
    valor_total_oc = oc.valor_total_impresso if oc.valor_total_impresso is not None else oc.valor_total_calculado
    divergencia_total = None
    if oc.valor_total_impresso is not None:
        divergencia_total = round(oc.valor_total_calculado - oc.valor_total_impresso, 2)
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    return {
        "chave_dedupe": montar_chave_dedupe(email.id_email, anexo.get("attachment_id"), anexo.get("filename"), hash_arquivo),
        "id_email": email.id_email,
        "thread_id": email.thread_id,
        "attachment_id": anexo.get("attachment_id"),
        "message_internal_date": None,
        "assunto": email.assunto,
        "remetente": email.remetente,
        "data_email": email.data,
        "data_venda": oc.data_oc,
        "numero_oc": oc.numero_oc,
        "vendedora": classificacao.vendedora,
        "cliente": oc.cliente,
        "status_email": classificacao.status_email,
        "status_revisao": classificacao.status_revisao,
        "considerar_venda": classificacao.considerar_venda,
        "motivo_exclusao": classificacao.motivo_exclusao,
        "tem_marcador_pedido": "SIM" if classificacao.tem_marcador_pedido else "NAO",
        "tem_marcador_cancelado": "SIM" if classificacao.tem_marcador_cancelado else "NAO",
        "tem_anexo_ordem_compra": "SIM",
        "nome_arquivo": anexo.get("filename") or caminho.name,
        "caminho_anexo": caminho_relativo_projeto(caminho),
        "hash_arquivo": hash_arquivo,
        "tamanho_arquivo": anexo.get("size") or caminho.stat().st_size,
        "tipo_anexo": anexo.get("mime_type") or "application/pdf",
        "metodo_extracao": oc.metodo_extracao,
        "avisos_parser": "; ".join(oc.avisos) if oc.avisos else "",
        "quantidade_itens": len(oc.itens),
        "valor_total_oc": valor_total_oc,
        "valor_total_impresso": oc.valor_total_impresso,
        "valor_total_calculado": oc.valor_total_calculado,
        "divergencia_total": divergencia_total,
        "erro_processamento": "",
        "data_processamento": agora,
        "origem_execucao": "GMAIL_REAL_PEDIDOS_SYNC",
    }


def _montar_registro_erro_oc(email, anexo: dict, marcadores_presentes: set[str], erro: Exception) -> dict:
    from persistencia import calcular_hash_arquivo, caminho_relativo_projeto, montar_chave_dedupe

    caminho = anexo["caminho"]
    hash_arquivo = calcular_hash_arquivo(caminho)
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    tem_cancelado = config.MARCADOR_CANCELADO in marcadores_presentes
    return {
        "chave_dedupe": montar_chave_dedupe(email.id_email, anexo.get("attachment_id"), anexo.get("filename"), hash_arquivo),
        "id_email": email.id_email,
        "thread_id": email.thread_id,
        "attachment_id": anexo.get("attachment_id"),
        "message_internal_date": None,
        "assunto": email.assunto,
        "remetente": email.remetente,
        "data_email": email.data,
        "data_venda": None,
        "numero_oc": None,
        "vendedora": _vendedora_de_classificacao(marcadores_presentes),
        "cliente": None,
        "status_email": "CANCELADO" if tem_cancelado else "ERRO_PROCESSAMENTO_OC",
        "status_revisao": "" if tem_cancelado else "REVISAR_PARSER_OC",
        "considerar_venda": "NAO",
        "motivo_exclusao": "MARCADOR_CANCELADO" if tem_cancelado else "ERRO_PROCESSAMENTO_OC",
        "tem_marcador_pedido": "SIM" if config.MARCADOR_PEDIDO in marcadores_presentes else "NAO",
        "tem_marcador_cancelado": "SIM" if tem_cancelado else "NAO",
        "tem_anexo_ordem_compra": "SIM",
        "nome_arquivo": anexo.get("filename") or caminho.name,
        "caminho_anexo": caminho_relativo_projeto(caminho),
        "hash_arquivo": hash_arquivo,
        "tamanho_arquivo": anexo.get("size") or caminho.stat().st_size,
        "tipo_anexo": anexo.get("mime_type") or "application/pdf",
        "metodo_extracao": "",
        "avisos_parser": "",
        "quantidade_itens": 0,
        "valor_total_oc": None,
        "valor_total_impresso": None,
        "valor_total_calculado": None,
        "divergencia_total": None,
        "erro_processamento": str(erro),
        "data_processamento": agora,
        "origem_execucao": "GMAIL_REAL_PEDIDOS_SYNC",
    }


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


def _executar_modo_local(args: argparse.Namespace) -> int:
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


def _sincronizar_pedidos_dashboard(cliente, args: argparse.Namespace, label_id: str) -> int:
    from gmail_client import montar_query_gmail_periodo
    from persistencia import (
        existe_gmail_venda_oc,
        salvar_dashboard_venda_historica_gmail,
        salvar_gmail_oc_itens,
        salvar_gmail_venda_oc,
    )

    if args.marcador != config.MARCADOR_PEDIDO:
        logger.error("sincronizar-pedidos-dashboard exige --marcador PEDIDO.")
        return 2
    if not args.limite_pedidos or args.limite_pedidos <= 0:
        logger.error("sincronizar-pedidos-dashboard exige --limite-pedidos positivo.")
        return 2
    if not args.data_inicio or not args.data_fim:
        logger.error("sincronizar-pedidos-dashboard exige --data-inicio e --data-fim.")
        return 2
    if args.salvar_dashboard and args.dry_run:
        logger.error("Use --salvar-dashboard OU --dry-run, nao os dois juntos.")
        return 2

    query = montar_query_gmail_periodo(args.marcador, args.data_inicio, args.data_fim)
    emails = cliente.listar_emails_por_marcador(
        label_id,
        marcador_nome=args.marcador,
        limite=args.limite_pedidos,
        data_inicio=args.data_inicio,
        data_fim=args.data_fim,
    )
    stats = {
        "emails": len(emails), "anexos_baixados": 0, "ocs_reconhecidas": 0,
        "vendas_gravadas": 0, "itens_gravados": 0, "erros": 0,
        "atualizadas": 0, "novas": 0,
    }
    logger.info("Query Gmail: %s", query)
    logger.info(
        "Sincronizacao PEDIDO: periodo=%s a %s | limite=%d | emails=%d | salvar_dashboard=%s",
        args.data_inicio, args.data_fim, args.limite_pedidos, len(emails), args.salvar_dashboard,
    )

    for email in emails:
        logger.info("Email: id=%s data=%s assunto=%r", email.id_email, email.data, email.assunto)
        marcadores_presentes = extrair_marcadores_presentes(email.labels)
        anexos = cliente.baixar_anexos_mensagem(
            message_id=email.id_email,
            label_nome=args.marcador,
            pasta_anexos=Path(config.ANEXOS_DIR),
            somente_ordem_compra=True,
        )
        stats["anexos_baixados"] += len(anexos)
        if not anexos:
            logger.warning("  Nenhum anexo de Ordem de Compra reconhecido por nome.")
            continue

        for anexo in anexos:
            caminho = anexo["caminho"]
            logger.info("  Anexo OC baixado: %s", caminho)
            try:
                oc = parse_pdf_oc(caminho)
                stats["ocs_reconhecidas"] += 1
                classificacao = classificar_email_venda(marcadores_presentes, tem_anexo_ordem_compra=True)
                registro = _montar_registro_oc_gmail(email, anexo, oc, classificacao)
                logger.info(
                    "  OC=%s DATA_VENDA=%s cliente=%r vendedora=%s status=%s considerar=%s valor=%s itens=%d metodo=%s",
                    oc.numero_oc, oc.data_oc, oc.cliente, classificacao.vendedora, classificacao.status_email,
                    classificacao.considerar_venda, registro["valor_total_oc"], len(oc.itens), oc.metodo_extracao,
                )
                for aviso in oc.avisos:
                    logger.warning("  Aviso parser OC: %s", aviso)
            except Exception as exc:
                stats["erros"] += 1
                logger.warning("  Falha ao parsear OC %s: %s", caminho.name, exc)
                registro = _montar_registro_erro_oc(email, anexo, marcadores_presentes, exc)
                oc = None

            if not args.salvar_dashboard:
                continue

            ja_existia = existe_gmail_venda_oc(registro["chave_dedupe"])
            venda_oc_id = salvar_gmail_venda_oc(registro)
            stats["vendas_gravadas"] += 1
            if ja_existia:
                stats["atualizadas"] += 1
            else:
                stats["novas"] += 1

            if oc is not None and registro["status_email"] == "VENDA_CONFIRMADA" and registro["considerar_venda"] == "SIM":
                salvar_dashboard_venda_historica_gmail(registro)
                stats["itens_gravados"] += salvar_gmail_oc_itens(venda_oc_id, registro, oc.itens)

    logger.info(
        "Resumo sincronizacao: emails=%d anexos_baixados=%d ocs_reconhecidas=%d vendas_gravadas=%d novas=%d atualizadas=%d itens_gravados=%d erros=%d",
        stats["emails"], stats["anexos_baixados"], stats["ocs_reconhecidas"], stats["vendas_gravadas"],
        stats["novas"], stats["atualizadas"], stats["itens_gravados"], stats["erros"],
    )
    logger.info("Gmail nao foi alterado. Nenhum label/e-mail foi enviado, apagado, movido ou respondido.")
    if not args.salvar_dashboard:
        logger.info("--salvar-dashboard nao informado: nada foi gravado no banco.")
    return 0


def _executar_modo_gmail_real(args: argparse.Namespace) -> int:
    if not args.dry_run and args.acao_gmail != "sincronizar-pedidos-dashboard":
        logger.error("--gmail-real exige --dry-run nesta fase (diagnóstico somente leitura).")
        return 2
    if args.limite_cotacoes is None and args.limite_pedidos is None:
        logger.error("--gmail-real exige limite explícito: --limite-cotacoes e/ou --limite-pedidos.")
        return 2
    if not args.acao_gmail:
        logger.error("--gmail-real exige --acao-gmail {listar-labels|verificar-marcadores|buscar-amostra|baixar-anexos-amostra|contar-por-periodo|sincronizar-pedidos-dashboard}.")
        return 2
    try:
        _validar_periodo_datas(args.data_inicio, args.data_fim)
    except ValueError as exc:
        logger.error("%s", exc)
        return 2

    from gmail_client import GmailClient, GmailClientError, montar_query_gmail_periodo

    logger.info(
        "Modo: GMAIL REAL (SOMENTE LEITURA, escopo %s) | acao=%s | dry-run=%s | limite_cotacoes=%s | limite_pedidos=%s | data_inicio=%s | data_fim=%s",
        config.GMAIL_READONLY_SCOPE, args.acao_gmail, args.dry_run, args.limite_cotacoes, args.limite_pedidos,
        args.data_inicio or "-", args.data_fim or "-",
    )

    try:
        cliente = GmailClient(credentials_path=args.credentials_json, token_path=args.token_gmail)
    except GmailClientError as exc:
        logger.error("Não foi possível conectar à Gmail API: %s", exc)
        return 1

    if args.acao_gmail == "listar-labels":
        labels = cliente.listar_labels()
        logger.info("Total de labels na conta: %d", len(labels))
        for label in labels:
            logger.info("  label: %s (id=%s)", label["name"], label["id"])
        return 0

    if args.acao_gmail == "verificar-marcadores":
        resolucao = cliente.resolver_labels(config.MARCADORES_OBRIGATORIOS)
        encontrados = {k: v for k, v in resolucao.items() if v}
        faltando = [k for k, v in resolucao.items() if not v]
        for nome, label_id in encontrados.items():
            logger.info("  OK: marcador '%s' encontrado (label_id=%s)", nome, label_id)
        for nome in faltando:
            logger.warning("  FALTANDO: marcador '%s' não encontrado entre os labels da conta", nome)
        return 0 if not faltando else 1

    marcadores_alvo = [args.marcador] if args.marcador else config.MARCADORES_OBRIGATORIOS
    limite_mensagens = args.limite_cotacoes or args.limite_pedidos or 1
    resolucao = cliente.resolver_labels(marcadores_alvo)

    if args.acao_gmail == "sincronizar-pedidos-dashboard":
        label_id = resolucao.get(config.MARCADOR_PEDIDO)
        if not label_id:
            logger.error("Marcador PEDIDO nao encontrado.")
            return 1
        return _sincronizar_pedidos_dashboard(cliente, args, label_id)

    if args.acao_gmail == "contar-por-periodo":
        for nome in marcadores_alvo:
            label_id = resolucao.get(nome)
            if not label_id:
                logger.warning("Marcador '%s' não encontrado — pulando.", nome)
                continue
            query = montar_query_gmail_periodo(nome, args.data_inicio, args.data_fim)
            emails = cliente.listar_emails_por_marcador(
                label_id, marcador_nome=nome, limite=limite_mensagens,
                data_inicio=args.data_inicio, data_fim=args.data_fim,
            )
            logger.info("Query Gmail: %s", query)
            logger.info("Marcador: %s | periodo: %s a %s | limite=%d | retornados=%d",
                        nome, args.data_inicio or "-", args.data_fim or "-", limite_mensagens, len(emails))
            for e in emails:
                logger.info("  id=%s thread=%s data=%s assunto=%r", e.id_email, e.thread_id, e.data, e.assunto)
        logger.info("Diagnóstico concluído: Gmail não alterado, nenhum anexo baixado, nada persistido.")
        return 0

    if args.acao_gmail == "buscar-amostra":
        for nome in marcadores_alvo:
            label_id = resolucao.get(nome)
            if not label_id:
                logger.warning("Marcador '%s' não encontrado — pulando.", nome)
                continue
            query = montar_query_gmail_periodo(nome, args.data_inicio, args.data_fim)
            logger.info("Query Gmail: %s", query)
            emails = cliente.listar_emails_por_marcador(
                label_id, marcador_nome=nome, limite=limite_mensagens,
                data_inicio=args.data_inicio, data_fim=args.data_fim,
            )
            logger.info("Marcador '%s': %d e-mail(s) encontrados (limite=%d)", nome, len(emails), limite_mensagens)
            for e in emails:
                logger.info(
                    "  id=%s thread=%s assunto=%r remetente=%r data=%s anexos=%s link=%s",
                    e.id_email, e.thread_id, e.assunto, e.remetente, e.data, e.anexos, e.link,
                )
                marcadores_presentes = extrair_marcadores_presentes(e.labels)
                tem_anexo_oc = any(parece_ordem_compra(nome_anexo) for nome_anexo in e.anexos)
                classificacao = classificar_email_venda(marcadores_presentes, tem_anexo_oc)
                logger.info(
                    "    VENDEDORA=%s TEM_MARCADOR_PEDIDO=%s TEM_MARCADOR_CANCELADO=%s "
                    "TEM_ANEXO_ORDEM_COMPRA=%s STATUS_EMAIL=%s CONSIDERAR_VENDA=%s "
                    "MOTIVO_EXCLUSAO=%s STATUS_REVISAO=%s DATA_VENDA=%s",
                    classificacao.vendedora, classificacao.tem_marcador_pedido, classificacao.tem_marcador_cancelado,
                    classificacao.tem_anexo_ordem_compra, classificacao.status_email, classificacao.considerar_venda,
                    classificacao.motivo_exclusao or "-", classificacao.status_revisao or "-",
                    "indisponível (anexo não baixado nesta ação — use baixar-anexos-amostra)",
                )
        return 0

    if args.acao_gmail == "baixar-anexos-amostra":
        pasta_anexos = Path(config.ANEXOS_DIR)
        limite_anexos = args.limite_pedidos
        for nome in marcadores_alvo:
            label_id = resolucao.get(nome)
            if not label_id:
                logger.warning("Marcador '%s' não encontrado — pulando.", nome)
                continue
            caminhos = cliente.baixar_anexos_amostra(
                label_id=label_id, label_nome=nome, pasta_anexos=pasta_anexos,
                limite_mensagens=limite_mensagens, limite_anexos_por_mensagem=limite_anexos,
            )
            logger.info("Marcador '%s': %d anexo(s) baixado(s) para %s", nome, len(caminhos), pasta_anexos)
            for caminho in caminhos:
                logger.info("  salvo: %s", caminho)
                if parece_ordem_compra(caminho.name):
                    try:
                        oc = parse_pdf_oc(caminho)
                        logger.info(
                            "    OC reconhecida: numero_oc=%s DATA_VENDA=%s (metodo=%s)",
                            oc.numero_oc, oc.data_oc, oc.metodo_extracao,
                        )
                        for aviso in oc.avisos:
                            logger.warning("    aviso parser OC: %s", aviso)
                    except Exception as exc:
                        logger.warning("    Falha ao parsear possível OC %s: %s", caminho.name, exc)
        return 0

    return 2


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    _configurar_logging()

    if args.gmail_real and args.somente_local:
        logger.error("Escolha apenas um modo: --somente-local OU --gmail-real, não os dois.")
        return 2

    if args.gmail_real:
        return _executar_modo_gmail_real(args)

    if args.somente_local:
        return _executar_modo_local(args)

    logger.error(
        "Nenhum modo informado. Rode com --somente-local --manifesto-local <arquivo> "
        "ou --gmail-real --dry-run --acao-gmail <acao> (com limite explícito)."
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
