"""Configuração central do robô Gmail Cotações.

Não contém credenciais. Caminhos, pesos de score e limiares de
classificação ficam aqui e podem ser sobrepostos por um JSON externo
(ver modelo_config_gmail_cotacoes.json).
"""

from __future__ import annotations

import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]

DATA_DIR = BASE_DIR / "data" / "gmail_cotacoes"
AMOSTRAS_DIR = DATA_DIR / "amostras"
ANEXOS_DIR = DATA_DIR / "anexos"
RELATORIOS_DIR = DATA_DIR / "relatorios"
CSV_DIR = RELATORIOS_DIR / "csv"
LOGS_DIR = BASE_DIR / "logs" / "gmail_cotacoes"

VENDEDORAS = ["JESSICA", "STHEFANY", "PAMELA", "LAYANE"]
MARCADOR_PEDIDO = "PEDIDO"
MARCADOR_CANCELADO = "CANCELADO"
MARCADOR_RESOLVER = "RESOLVER"
MARCADOR_REVISAO = "REVISAO"
MARCADORES_OBRIGATORIOS = VENDEDORAS + [MARCADOR_PEDIDO, MARCADOR_CANCELADO, MARCADOR_RESOLVER, MARCADOR_REVISAO]

# Vendedora usada quando um e-mail tem PEDIDO + OC mas nenhum marcador de
# vendedora (JESSICA/STHEFANY/PAMELA/LAYANE) — nunca adivinhada por PDF,
# cliente ou assunto. Ver correlacionador.classificar_email_venda.
SEM_VENDEDORA = "SEM_VENDEDORA"

# Gmail API — modo SOMENTE LEITURA. Nunca ampliar este escopo sem revisar
# gmail_client.py inteiro (o cliente valida ativamente que o token só tem
# este escopo e recusa prosseguir se detectar qualquer escopo a mais).
GMAIL_READONLY_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
CREDENTIALS_PATH = BASE_DIR / "credentials.json"
TOKEN_GMAIL_PATH = BASE_DIR / "token_gmail.json"

# Pesos do score composto de correlação e-mail cotação <-> e-mail pedido.
# A soma não precisa ser 1.0 — o total é normalizado em correlacionador.py.
PESOS_SCORE_EMAIL = {
    "cliente": 0.28,
    "categoria": 0.14,
    "mes": 0.14,
    "numero_cotacao": 0.20,
    "assunto": 0.12,
    "data": 0.07,
    "itens": 0.05,
}

# Limiares de classificação de CONFIANCA_CORRELACAO_EMAIL (score 0-100)
LIMIAR_CONFIANCA_ALTA = 80
LIMIAR_CONFIANCA_MEDIA = 55
LIMIAR_CONFIANCA_BAIXA = 35
# Abaixo de LIMIAR_CONFIANCA_BAIXA -> REVISAR

# Janela de dias considerada "próxima" ao comparar datas de e-mails
JANELA_DIAS_PROXIMIDADE = 30

# Valor mínimo (R$) para um item PERDIDO entrar em ITENS_CRITICOS_PERDIDOS
VALOR_CRITICO_PERDIDO = 2000.0

# Limiar de similaridade textual (rapidfuzz, 0-100) para considerar dois
# itens como possível match antes da checagem do perfil técnico.
LIMIAR_SIMILARIDADE_TEXTO = 78
LIMIAR_SIMILARIDADE_REVISAR = 60

COLUNAS_RELATORIO_COTACOES = [
    "VENDEDORA", "CLIENTE", "CATEGORIA", "COTACAO", "MES_REFERENCIA",
    "DATA_COTACAO", "NUMERO_OC", "DATA_OC", "DATA_VENDA",
    "TOTAL_ITENS_COTADOS", "TOTAL_ITENS_GANHOS", "TOTAL_ITENS_PERDIDOS",
    "TOTAL_ITENS_NAO_COTADOS", "TOTAL_ITENS_REVISAR",
    "PERC_ITENS_GANHOS", "PERC_ITENS_NAO_COTADOS",
    "VALOR_TOTAL_COTACAO", "VALOR_TOTAL_GANHO", "DIFERENCA_VALOR", "PERC_DIFERENCA",
    "SCORE_EMAIL_TOTAL", "SCORE_EMAIL_ASSUNTO", "SCORE_EMAIL_CLIENTE",
    "SCORE_EMAIL_CATEGORIA", "SCORE_EMAIL_MES", "SCORE_EMAIL_DATA", "SCORE_EMAIL_ITENS",
    "CONFIANCA_CORRELACAO_EMAIL", "MOTIVO_CORRELACAO_EMAIL",
    "TEM_MARCADOR_PEDIDO", "TEM_MARCADOR_CANCELADO", "TEM_ANEXO_ORDEM_COMPRA",
    "STATUS_EMAIL", "CONSIDERAR_VENDA", "MOTIVO_EXCLUSAO", "STATUS_REVISAO",
    "LINK_EMAIL_COTACAO", "LINK_EMAIL_PEDIDO",
]

COLUNAS_CRUZAMENTO_ITENS = [
    "VENDEDORA", "CLIENTE", "CATEGORIA", "COTACAO", "NUMERO_OC",
    "ITEM_COTACAO", "DESCRICAO_COTADA", "UNIDADE", "QTD_COTADA",
    "VALOR_UNITARIO_COTADO", "VALOR_TOTAL_COTADO",
    "ITEM_OC", "DESCRICAO_OC", "QTD_GANHA", "VALOR_UNITARIO_GANHO", "VALOR_TOTAL_GANHO",
    "STATUS_ITEM", "SCORE_COMPARACAO", "SCORE_TEXTO", "SCORE_TECNICO",
    "CONFLITO_TECNICO", "CONFIANCA_MATCH_ITEM", "MOTIVO_MATCH_ITEM",
]


def _mkdirs() -> None:
    for d in (AMOSTRAS_DIR, ANEXOS_DIR, RELATORIOS_DIR, CSV_DIR, LOGS_DIR):
        d.mkdir(parents=True, exist_ok=True)


def carregar_config_externa(caminho: Path | str | None = None) -> dict:
    """Carrega overrides de um JSON externo (modelo_config_gmail_cotacoes.json ou cópia do usuário).

    Retorna {} se o arquivo não existir. Nunca lança para arquivo ausente.
    """
    if caminho is None:
        caminho = Path(__file__).with_name("modelo_config_gmail_cotacoes.json")
    caminho = Path(caminho)
    if not caminho.exists():
        return {}
    with open(caminho, "r", encoding="utf-8") as f:
        return json.load(f)


_mkdirs()
