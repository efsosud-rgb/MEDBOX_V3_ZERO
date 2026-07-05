"""Parser da Proposta Comercial MedBox (PDF).

AVISO DE CONFIABILIDADE (leia antes de usar este módulo como fonte de
verdade): o layout desta proposta comercial quebra descrições longas em
várias linhas de forma irregular, e a extração de texto (tanto via
pdftotext quanto, presumivelmente, via pdfplumber em modo texto simples)
embaralha a ordem vertical dos números de preço/quantidade entre itens
vizinhos. Isso foi validado no caso real HMAR 1006: tentar emparelhar
sequencialmente todos os tokens monetários da tabela (a mesma técnica que
funciona de forma exata para a Ordem de Compra, ver parser_pdf_oc.py)
diverge da planilha de cotação (fonte confiável) a partir do item ~10,
porque um único item com valor "R$ -" (zero) já desalinha tudo que vem
depois.

Por isso este parser:
- extrai os tokens monetários de forma LOCAL a cada bloco de item (não em
  fila global), o que limita o dano de qualquer linha ruidosa a apenas
  aquele item, em vez de desalinhar os itens seguintes;
- sempre marca confianca_extracao="BAIXA" nos itens (nunca "ALTA");
- não é usado como fonte de itens cotados no pipeline principal — essa
  fonte é o Excel de cotação (parser_excel_cotacao.py), que é um export
  estruturado e não sofre desse problema. Ver scripts/gmail_cotacoes/README.md.

Este módulo ainda é útil para: conferir metadados (cliente, datas, valor
total da proposta) contra o que está no manifesto/Excel, e para uma
listagem best-effort dos itens quando não houver Excel disponível.

Mesma estratégia de extração de texto de parser_pdf_oc.py (pdfplumber
preferencial, pdftotext como fallback local).
"""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

_RE_MONETARIO_OU_TRACO = re.compile(r"R\$\s*(-|[\d.]*,\d{2})")
_RE_ITEM_MARCADOR = re.compile(r"^\s*(\d{1,3})\b")
_RE_CLIENTE = re.compile(r"A/C:\s*(.+)")
_RE_TOTAL_PROPOSTA = re.compile(r"TOTAL DA PROPOSTA:\s*R\$\s*([\d.]*,\d{2})", re.IGNORECASE)
_RE_TOTAL_GERAL = re.compile(r"^TOTAL:\s*R\$\s*([\d.]*,\d{2})", re.IGNORECASE | re.MULTILINE)
_RE_DATA = re.compile(r"\b(\d{1,2}\s+de\s+\w+\s+de\s+\d{4})\b")


@dataclass
class ItemProposta:
    numero_item: int
    descricao: str
    valor_unitario: float | None
    valor_total: float | None
    confianca_extracao: str  # sempre "BAIXA" neste parser (ver docstring do módulo)


@dataclass
class PropostaComercial:
    cliente: str | None
    data_proposta: str | None
    total_geral: float | None
    total_proposta: float | None
    itens: list[ItemProposta]
    metodo_extracao: str
    avisos: list[str] = field(default_factory=list)


def _extrair_texto_pdfplumber(caminho: Path) -> str | None:
    try:
        import pdfplumber
    except ImportError:
        return None
    partes = []
    with pdfplumber.open(str(caminho)) as pdf:
        for pagina in pdf.pages:
            partes.append(pagina.extract_text() or "")
    return "\n".join(partes)


def _extrair_texto_pdftotext(caminho: Path) -> str | None:
    exe = shutil.which("pdftotext")
    if not exe:
        return None
    resultado = subprocess.run(
        [exe, "-layout", "-enc", "UTF-8", str(caminho), "-"],
        capture_output=True, timeout=60,
    )
    if resultado.returncode != 0:
        return None
    return resultado.stdout.decode("utf-8", errors="replace")


def _extrair_texto(caminho: Path) -> tuple[str, str]:
    texto = _extrair_texto_pdfplumber(caminho)
    if texto is not None:
        return texto, "pdfplumber"
    texto = _extrair_texto_pdftotext(caminho)
    if texto is not None:
        return texto, "pdftotext (fallback local — instale pdfplumber para o caminho oficial)"
    raise RuntimeError(
        "Nenhum extrator de PDF disponível. Instale pdfplumber (pip install pdfplumber) "
        "ou garanta que o binário 'pdftotext' (poppler/xpdf) esteja no PATH."
    )


def _para_float(valor: str) -> float:
    valor = valor.strip()
    if valor == "-":
        return 0.0
    return float(valor.replace(".", "").replace(",", "."))


def parse_pdf_proposta(caminho: str | Path) -> PropostaComercial:
    caminho = Path(caminho)
    if not caminho.exists():
        raise FileNotFoundError(f"PDF de proposta não encontrado: {caminho}")

    texto, metodo = _extrair_texto(caminho)
    avisos = [
        "parser_pdf_proposta: extração de itens é best-effort (confiança BAIXA). "
        "Use o Excel de cotação como fonte de itens cotados."
    ]

    m_cliente = _RE_CLIENTE.search(texto)
    cliente = m_cliente.group(1).strip() if m_cliente else None

    m_data = _RE_DATA.search(texto)
    data_proposta = m_data.group(1) if m_data else None

    m_total_proposta = _RE_TOTAL_PROPOSTA.search(texto)
    total_proposta = _para_float(m_total_proposta.group(1)) if m_total_proposta else None

    m_total_geral = _RE_TOTAL_GERAL.search(texto)
    total_geral = _para_float(m_total_geral.group(1)) if m_total_geral else None

    idx_inicio = texto.upper().find("ITEM")
    idx_fim = m_total_geral.start() if m_total_geral else len(texto)
    if idx_inicio == -1:
        raise ValueError(f"Cabeçalho da tabela de itens não encontrado em {caminho.name}")
    regiao_tabela = texto[idx_inicio:idx_fim]
    linhas = regiao_tabela.splitlines()

    blocos: list[dict] = []
    proximo_esperado = 1
    bloco_atual: dict | None = None
    for linha in linhas:
        m_marc = _RE_ITEM_MARCADOR.match(linha)
        if m_marc and int(m_marc.group(1)) == proximo_esperado:
            if bloco_atual is not None:
                blocos.append(bloco_atual)
            bloco_atual = {"numero": proximo_esperado, "linhas": [linha]}
            proximo_esperado += 1
        elif bloco_atual is not None:
            bloco_atual["linhas"].append(linha)
    if bloco_atual is not None:
        blocos.append(bloco_atual)

    if not blocos:
        raise ValueError(f"Nenhum item reconhecido na tabela da proposta {caminho.name}")

    itens: list[ItemProposta] = []
    for bloco in blocos:
        texto_bloco = " ".join(l.strip() for l in bloco["linhas"] if l.strip())
        tokens = _RE_MONETARIO_OU_TRACO.findall(texto_bloco)
        descricao = _RE_MONETARIO_OU_TRACO.sub("", texto_bloco)
        descricao = re.sub(r"^\s*\d{1,3}\s+", "", descricao)
        descricao = re.sub(r"\s{2,}", " ", descricao).strip()

        preco = total = None
        if len(tokens) >= 2:
            preco = _para_float(tokens[-2])
            total = _para_float(tokens[-1])
        elif len(tokens) == 1:
            total = _para_float(tokens[-1])

        itens.append(ItemProposta(
            numero_item=bloco["numero"],
            descricao=descricao,
            valor_unitario=preco,
            valor_total=total,
            confianca_extracao="BAIXA",
        ))

    soma_itens = sum(it.valor_total for it in itens if it.valor_total)
    referencia = total_proposta if total_proposta is not None else total_geral
    if referencia is not None and abs(soma_itens - referencia) > max(50.0, 0.02 * referencia):
        avisos.append(
            f"Soma dos {len(itens)} itens extraídos (R$ {soma_itens:.2f}) diverge do total "
            f"impresso (R$ {referencia:.2f}) além da tolerância — esperado dado o método "
            f"best-effort. Não use estes valores por item sem revisão manual."
        )

    return PropostaComercial(
        cliente=cliente,
        data_proposta=data_proposta,
        total_geral=total_geral,
        total_proposta=total_proposta,
        itens=itens,
        metodo_extracao=metodo,
        avisos=avisos,
    )
