"""Carrega o manifesto local (JSON) que descreve casos de teste "modo local".

Formato esperado (ver modelo_config_gmail_cotacoes.json e o manifesto real
do caso HMAR 1006 em data/gmail_cotacoes/amostras/manifesto_hmar_1006_real.json):

{
  "casos": [
    {
      "modo": "anexos_reais",
      "vendedora": "STHEFANY",
      "assunto_cotacao": "...",
      "assunto_pedido": "...",
      "cliente": "HMAR",
      "categoria": "CORRELATOS",
      "mes_referencia": "JULHO 26",
      "numero_cotacao": "2026.001006",
      "numero_oc": "008688",
      "arquivo_pdf_proposta": "PROPOSTA 1006 hmar.pdf",
      "arquivo_excel_cotacao_cliente": "NÃOEXCLUIRExportaçãodeCotaçãoV2_2026001006_4002_Orçamento.xlsx",
      "arquivo_pdf_ordem_compra": "Ordem de Compra.PDF"
    }
  ]
}
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class CasoManifesto:
    modo: str
    vendedora: str
    assunto_cotacao: str
    assunto_pedido: str
    cliente: str
    categoria: str
    mes_referencia: str
    numero_cotacao: str
    numero_oc: str
    arquivo_pdf_proposta: str
    arquivo_excel_cotacao_cliente: str
    arquivo_pdf_ordem_compra: str


_CAMPOS_OBRIGATORIOS = [
    "modo", "vendedora", "assunto_cotacao", "assunto_pedido", "cliente",
    "categoria", "mes_referencia", "numero_cotacao", "numero_oc",
    "arquivo_pdf_proposta", "arquivo_excel_cotacao_cliente", "arquivo_pdf_ordem_compra",
]


def carregar_manifesto(caminho: str | Path) -> list[CasoManifesto]:
    caminho = Path(caminho)
    if not caminho.exists():
        raise FileNotFoundError(f"Manifesto local não encontrado: {caminho}")

    with open(caminho, "r", encoding="utf-8") as f:
        dados = json.load(f)

    casos_json = dados.get("casos", [])
    if not casos_json:
        raise ValueError(f"Manifesto {caminho} não contém nenhum caso em 'casos'")

    casos: list[CasoManifesto] = []
    for i, caso in enumerate(casos_json):
        faltantes = [c for c in _CAMPOS_OBRIGATORIOS if c not in caso]
        if faltantes:
            raise ValueError(f"Caso #{i} do manifesto {caminho} sem campos obrigatórios: {faltantes}")
        casos.append(CasoManifesto(**{k: caso[k] for k in _CAMPOS_OBRIGATORIOS}))

    return casos
