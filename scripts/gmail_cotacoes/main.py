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
from pathlib import Path

import config
from correlacionador import calcular_score_email, classificar_email_venda, cruzar_itens, extrair_marcadores_presentes
from extrator_anexos import localizar_anexo, parece_ordem_compra, salvar_anexo_gmail
from gerador_relatorios import gerar_relatorios
from manifesto_local import carregar_manifesto
from parser_excel_cotacao import parse_excel_cotacao
from parser_pdf_oc import parse_pdf_oc
from parser_pdf_proposta import parse_pdf_proposta
from parser_xlsx_oc import parse_xlsx_oc
from persistencia import calcular_hash_arquivo, caminho_relativo_projeto, montar_chave_dedupe, salvar_gmail_venda_oc, salvar_gmail_oc_itens, sincronizar_dashboard_vendas_historicas

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
                    choices=["listar-labels", "verificar-marcadores", "buscar-amostra", "baixar-anexos-amostra", "sincronizar-pedidos-dashboard"],
                    help="Ação de diagnóstico do modo --gmail-real")
    p.add_argument("--buscar-oc-por-texto", action="store_true", help="Usa busca textual por 'ordem de compra' na sincronização")
    p.add_argument("--marcador", type=str, default=None,
                    help="Restringe buscar-amostra/baixar-anexos-amostra a um marcador (JESSICA/STHEFANY/PAMELA/LAYANE/PEDIDO/CANCELADO). Padrão: todos")
    p.add_argument("--credentials-json", type=str, default=str(config.CREDENTIALS_PATH), help="Caminho do credentials.json OAuth")
    p.add_argument("--token-gmail", type=str, default=str(config.TOKEN_GMAIL_PATH), help="Caminho do token_gmail.json")

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


def _executar_modo_gmail_real(args: argparse.Namespace) -> int:
    if not args.dry_run:
        logger.error("--gmail-real exige --dry-run nesta fase (diagnóstico somente leitura).")
        return 2
    if args.limite_cotacoes is None and args.limite_pedidos is None:
        logger.error("--gmail-real exige limite explícito: --limite-cotacoes e/ou --limite-pedidos.")
        return 2
    if not args.acao_gmail:
        logger.error("--gmail-real exige --acao-gmail {listar-labels|verificar-marcadores|buscar-amostra|baixar-anexos-amostra}.")
        return 2

    from gmail_client import GmailClient, GmailClientError

    logger.info(
        "Modo: GMAIL REAL (SOMENTE LEITURA, escopo %s) | acao=%s | dry-run=%s | limite_cotacoes=%s | limite_pedidos=%s",
        config.GMAIL_READONLY_SCOPE, args.acao_gmail, args.dry_run, args.limite_cotacoes, args.limite_pedidos,
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

    if args.acao_gmail == "buscar-amostra":
        for nome in marcadores_alvo:
            label_id = resolucao.get(nome)
            if not label_id:
                logger.warning("Marcador '%s' não encontrado — pulando.", nome)
                continue
            emails = cliente.listar_emails_por_marcador(label_id, marcador_nome=nome, limite=limite_mensagens)
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

    if args.acao_gmail == "sincronizar-pedidos-dashboard":
        return _sincronizar_pedidos_dashboard(args, cliente)

    return 2


def _sincronizar_pedidos_dashboard(args, cliente) -> int:
    import base64
    from datetime import datetime

    limite = args.limite_cotacoes or 100
    query = ""
    if args.buscar_oc_por_texto:
        # Exemplo: "ordem de compra" after:2026/06/01 before:2026/07/01 has:attachment
        query = '"ordem de compra" has:attachment'
        logger.info("Buscando e-mails por query: %s", query)
        emails = cliente.buscar_emails_por_query(query, limite)
    else:
        marcador = args.marcador or "PEDIDO"
        label_id = cliente.resolver_labels([marcador]).get(marcador)
        if not label_id:
            logger.error("Marcador '%s' não encontrado.", marcador)
            return 1
        emails = cliente.listar_emails_por_marcador(label_id, marcador, limite)

    logger.info("Encontrados %d e-mail(s) para processar.", len(emails))

    # Agrupamento para Rule 9 (Deduplicação e Exclusão Determinística)
    # chave: (numero_oc, cliente, data_venda, valor_total)
    # valor: {'emails': [EmailGmail], 'excluido': bool, 'motivo': str}
    grupo_oc: dict[tuple, dict] = {}

    pasta_anexos = Path(config.ANEXOS_DIR)

    for e in emails:
        marcadores_presentes = extrair_marcadores_presentes(e.labels)
        tem_anexo_oc = any(parece_ordem_compra(n) for n in e.anexos)

        # Só prossegue se tiver algo que pareça OC (ou se estiver no marcador PEDIDO e quisermos investigar)
        if not tem_anexo_oc and config.MARCADOR_PEDIDO not in marcadores_presentes:
            continue

        # Baixar e processar anexos
        for nome_anexo in e.anexos:
            if not parece_ordem_compra(nome_anexo):
                continue

            is_xlsx = nome_anexo.lower().endswith(".xlsx")

            # Precisamos baixar o anexo para parsear
            # (Aqui simplificamos a lógica de download que já existe no cliente)
            # Nota: Em um cenário real, o cliente deveria ter um método 'baixar_anexo(msg_id, attachment_id)'
            # Vamos usar o que temos ou adaptar.

            # BUSCAR attachment_id
            msg_full = cliente._obter_mensagem(e.id_email)
            from gmail_client import _extrair_metadados_anexos
            anexos_meta = _extrair_metadados_anexos(msg_full.get("payload", {}))

            meta = next((m for m in anexos_meta if m["filename"] == nome_anexo), None)
            if not meta or not meta["attachment_id"]:
                continue

            dados = cliente._service.users().messages().attachments().get(
                userId="me", messageId=e.id_email, id=meta["attachment_id"],
            ).execute()
            conteudo = base64.urlsafe_b64decode(dados["data"])
            caminho = salvar_anexo_gmail(
                pasta_anexos=pasta_anexos, label="SINCRONIZACAO", message_id=e.id_email,
                nome_arquivo=nome_anexo, conteudo=conteudo,
            )

            hash_arq = calcular_hash_arquivo(caminho)

            ocs_extraidas = []
            if is_xlsx:
                try:
                    ocs_extraidas = parse_xlsx_oc(caminho)
                except Exception as exc:
                    logger.warning("Falha ao parsear XLSX %s: %s", nome_anexo, exc)
            else:
                try:
                    oc_pdf = parse_pdf_oc(caminho)
                    ocs_extraidas = [oc_pdf]
                except Exception as exc:
                    logger.warning("Falha ao parsear PDF %s: %s", nome_anexo, exc)

            for oc in ocs_extraidas:
                xlsx_parseado = is_xlsx and oc.numero_oc is not None
                classificacao = classificar_email_venda(
                    marcadores_presentes, True, anexo_xlsx=is_xlsx, xlsx_parseado=xlsx_parseado
                )

                # Rule 9: Identificador único da OC
                # (numero_oc, cliente, data, valor)
                # Normalizamos para garantir determinismo
                valor_oc = oc.valor_total_impresso if oc.valor_total_impresso is not None else oc.valor_total_calculado
                chave = (oc.numero_oc, oc.cliente, oc.data_oc, round(valor_oc, 2))

                if chave not in grupo_oc:
                    grupo_oc[chave] = {"emails": [], "excluido": False, "motivo": None, "oc": oc, "caminho": caminho, "hash": hash_arq, "meta": meta}

                grupo_oc[chave]["emails"].append(e)
                if classificacao.considerar_venda == "NAO" and classificacao.status_email == "CANCELADO":
                    grupo_oc[chave]["excluido"] = True
                    grupo_oc[chave]["motivo"] = classificacao.motivo_exclusao

    # Persistência
    total_vendas = 0
    for chave, dados_oc in grupo_oc.items():
        oc = dados_oc["oc"]

        # Ordenação determinística dos e-mails (Rule 9)
        dados_oc["emails"].sort(key=lambda x: x.id_email)
        e = dados_oc["emails"][0] # Pega o e-mail com menor ID como referência principal estável

        # Re-classifica considerando se algum e-mail do grupo está cancelado
        marcadores_grupo = set()
        for em in dados_oc["emails"]:
            marcadores_grupo.update(extrair_marcadores_presentes(em.labels))

        is_xlsx = dados_oc["caminho"].name.lower().endswith(".xlsx")
        xlsx_parseado = is_xlsx and oc.numero_oc is not None

        classificacao = classificar_email_venda(
            marcadores_grupo, True, anexo_xlsx=is_xlsx, xlsx_parseado=xlsx_parseado
        )

        if not args.dry_run:
            # TODO: Implementar salvar_gmail_venda_oc e tabelas extras
            # Por enquanto vamos usar o que temos
            valor_total_oc = oc.valor_total_impresso if oc.valor_total_impresso is not None else oc.valor_total_calculado

            registro = {
                "chave_dedupe": montar_chave_dedupe(e.id_email, dados_oc["meta"]["attachment_id"], dados_oc["caminho"].name, dados_oc["hash"]),
                "id_email": e.id_email,
                "thread_id": e.thread_id,
                "attachment_id": dados_oc["meta"]["attachment_id"],
                "assunto": e.assunto,
                "remetente": e.remetente,
                "data_email": e.data,
                "data_venda": oc.data_oc,
                "numero_oc": oc.numero_oc,
                "vendedora": classificacao.vendedora,
                "cliente": oc.cliente,
                "status_email": classificacao.status_email,
                "status_revisao": classificacao.status_revisao,
                "considerar_venda": classificacao.considerar_venda,
                "motivo_exclusao": classificacao.motivo_exclusao,
                "tem_marcador_pedido": "SIM" if config.MARCADOR_PEDIDO in marcadores_grupo else "NAO",
                "tem_marcador_cancelado": "SIM" if config.MARCADOR_CANCELADO in marcadores_grupo else "NAO",
                "tem_anexo_ordem_compra": "SIM",
                "nome_arquivo": dados_oc["caminho"].name,
                "caminho_anexo": caminho_relativo_projeto(dados_oc["caminho"]),
                "hash_arquivo": dados_oc["hash"],
                "tamanho_arquivo": dados_oc["caminho"].stat().st_size,
                "tipo_anexo": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" if is_xlsx else "application/pdf",
                "metodo_extracao": oc.metodo_extracao,
                "avisos_parser": "; ".join(oc.avisos),
                "quantidade_itens": len(oc.itens),
                "valor_total_oc": valor_total_oc,
                "valor_total_impresso": oc.valor_total_impresso,
                "valor_total_calculado": oc.valor_total_calculado,
                "origem_execucao": "SINCRONIZACAO_GMAIL",
            }
            id_venda = salvar_gmail_venda_oc(registro)
            registro["id"] = id_venda
            salvar_gmail_oc_itens(id_venda, oc.itens)
            sincronizar_dashboard_vendas_historicas(registro)
            if classificacao.considerar_venda == "SIM":
                total_vendas += 1
        else:
            if classificacao.considerar_venda == "SIM":
                total_vendas += 1
            logger.info("[DRY-RUN] Venda: OC %s | Cliente: %s | Valor: %s | Status: %s",
                        oc.numero_oc, oc.cliente, chave[3], classificacao.status_email)

    logger.info("Sincronização concluída. %d vendas confirmadas.", total_vendas)
    return 0


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
