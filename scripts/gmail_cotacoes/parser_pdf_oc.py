"""Parser da Ordem de Compra (PDF) do cliente.

Duas estratégias de extração de texto, nessa ordem de preferência:

1. pdfplumber (dependência oficial do projeto, ver requirements.txt /
   requirements_gmail_cotacoes.txt). Ainda não instalado neste ambiente
   no momento em que este parser foi escrito — ver README.md desta pasta.
2. Fallback local: binário `pdftotext` (xpdf/poppler), quando presente no
   PATH do sistema (ex.: já vem junto com o Git for Windows em
   mingw64/bin). Usado só para permitir teste local sem instalar nada
   novo. Fica registrado em `metodo_extracao` no resultado para ficar
   rastreável qual caminho foi usado.

Particularidade real observada no PDF de Ordem de Compra deste ERP: quando
a descrição de um item quebra em mais de uma linha, o texto extraído em
modo -layout "empurra" o par (preço unitário, valor total) do(s) item(ns)
SEGUINTE(S) para dentro do bloco visual do item anterior. Isso foi
confirmado manualmente no caso real HMAR 1006: os 13 pares de valores
monetários, tomados na ordem em que aparecem no texto (ignorando a linha
em que caem) e emparelhados 2 a 2, reconstroem exatamente os 13 itens
na ordem correta — e a soma bate com o "TOTAL" impresso no rodapé do
documento (R$ 33.257,89). Por isso a extração de valores usa uma fila
sequencial global de tokens monetários, e NUNCA tenta "adivinhar" a
qual item um valor pertence pela posição vertical da linha.

Se a soma dos valores extraídos não bater com o total impresso, o parser
não corrige nada silenciosamente — devolve o resultado com avisos.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

_RE_MONETARIO = re.compile(r"(?<!\d)(\d{1,3}(?:\.\d{3})*,\d{2})(?!\d)")
_RE_ITEM_START = re.compile(r"^\s*(\d{1,3})\s+(\S.*)$")
_RE_UNIDADE_QTD = re.compile(r"\b(UN|CX|PCT|FR|ROLO|KIT|PC|CJ)\b\s+([\d.]+(?:,\d+)?)")
_RE_NUMERO_OC = re.compile(r"Ordem de Compra No\.?\s*(\d+)", re.IGNORECASE)
# Ancorado em ", DATA" (padrão "Cidade, 01/07/2026" do cabeçalho de emissão da
# OC) para NUNCA capturar "Data Entrega: 15/07/2026" (esse é precedido por
# ":", não por ","). DATA_VENDA = esta data — nunca a de entrega, cotação ou
# recebimento do e-mail. Ver classificar_email_venda em correlacionador.py.
_RE_DATA_OC = re.compile(r",\s*(\d{2}/\d{2}/\d{4})\b")
_RE_TOTAL_RODAPE = re.compile(r"TOTAL\s+R\$\s*([\d.]*,\d{2})")
_RE_CLIENTE_FINAL = re.compile(r"^Nome:\s*(.+)$", re.MULTILINE)


@dataclass
class ItemOC:
    numero_item: int
    descricao: str
    unidade: str | None
    quantidade: float | None
    valor_unitario: float | None
    valor_total: float | None
    confianca_extracao: str  # ALTA | BAIXA


@dataclass
class OrdemDeCompra:
    numero_oc: str | None
    data_oc: str | None  # data de EMISSÃO da OC — é esta que vira DATA_VENDA nos relatórios
    cliente: str | None
    valor_total_impresso: float | None
    valor_total_calculado: float
    itens: list[ItemOC]
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


def parse_pdf_oc(caminho: str | Path) -> OrdemDeCompra:
    caminho = Path(caminho)
    if not caminho.exists():
        raise FileNotFoundError(f"PDF de Ordem de Compra não encontrado: {caminho}")

    texto, metodo = _extrair_texto(caminho)
    avisos: list[str] = []

    m_numero = _RE_NUMERO_OC.search(texto)
    numero_oc = m_numero.group(1) if m_numero else None

    m_data = _RE_DATA_OC.search(texto)
    data_oc = m_data.group(1) if m_data else None
    if data_oc is None:
        avisos.append(
            "Data de emissão da OC não encontrada (padrão ', DD/MM/AAAA' ausente). "
            "DATA_VENDA ficará vazia — não usar data de entrega/cotação/e-mail como substituto."
        )

    m_cliente = _RE_CLIENTE_FINAL.search(texto)
    cliente = m_cliente.group(1).strip() if m_cliente else None

    m_total = _RE_TOTAL_RODAPE.search(texto)
    valor_total_impresso = _para_float(m_total.group(1)) if m_total else None

    # Isola a região da tabela: entre o cabeçalho "ITEM" e a linha "TOTAL" do rodapé.
    idx_inicio = texto.upper().find("ITEM")
    idx_fim = m_total.start() if m_total else len(texto)
    if idx_inicio == -1:
        raise ValueError(f"Cabeçalho da tabela de itens não encontrado em {caminho.name}")
    regiao_tabela = texto[idx_inicio:idx_fim]

    linhas = regiao_tabela.splitlines()

    # 1ª passada: localizar início de cada item (número sequencial 1..N) e reunir a descrição.
    blocos: list[dict] = []
    proximo_esperado = 1
    bloco_atual = None
    for linha in linhas:
        m_item = _RE_ITEM_START.match(linha)
        if m_item and int(m_item.group(1)) == proximo_esperado:
            if bloco_atual is not None:
                blocos.append(bloco_atual)
            bloco_atual = {"numero": proximo_esperado, "linhas": [m_item.group(2)]}
            proximo_esperado += 1
        elif bloco_atual is not None:
            bloco_atual["linhas"].append(linha)
    if bloco_atual is not None:
        blocos.append(bloco_atual)

    if not blocos:
        raise ValueError(f"Nenhum item reconhecido na tabela da Ordem de Compra {caminho.name}")

    # 2ª passada: fila global de tokens monetários (preço unit., total) em ordem de leitura.
    tokens_monetarios = _RE_MONETARIO.findall(regiao_tabela)
    valores = [_para_float(t) for t in tokens_monetarios]

    n_itens = len(blocos)
    esperados = 2 * n_itens
    usar_fila_global = len(valores) == esperados
    if not usar_fila_global:
        avisos.append(
            f"Esperava {esperados} valores monetários ({n_itens} itens x 2) na tabela, "
            f"encontrou {len(valores)}. Valores por item não serão atribuídos automaticamente "
            f"— todos os itens ficam com confiança BAIXA para revisão manual."
        )

    itens: list[ItemOC] = []
    for i, bloco in enumerate(blocos):
        texto_bloco = " ".join(l.strip() for l in bloco["linhas"] if l.strip())
        # remove os próprios tokens monetários da descrição para não sujar o texto
        descricao_limpa = _RE_MONETARIO.sub("", texto_bloco).strip()
        descricao_limpa = re.sub(r"\s{2,}", " ", descricao_limpa)

        m_un = _RE_UNIDADE_QTD.search(texto_bloco)
        unidade = m_un.group(1) if m_un else None
        qtd_explicita = _para_float(m_un.group(2)) if m_un else None

        if usar_fila_global:
            preco = valores[2 * i]
            total = valores[2 * i + 1]
            qtd = qtd_explicita
            if qtd is None and preco:
                qtd = round(total / preco, 4)
            confianca = "ALTA"
        else:
            preco = total = None
            qtd = qtd_explicita
            confianca = "BAIXA"

        # remove o par "unidade qtd" do fim da descrição, se capturado
        if m_un:
            descricao_limpa = descricao_limpa[: m_un.start()].strip() or descricao_limpa

        itens.append(ItemOC(
            numero_item=bloco["numero"],
            descricao=descricao_limpa,
            unidade=unidade,
            quantidade=qtd,
            valor_unitario=preco,
            valor_total=total,
            confianca_extracao=confianca,
        ))

    valor_total_calculado = sum(it.valor_total for it in itens if it.valor_total)
    if valor_total_impresso is not None and abs(valor_total_calculado - valor_total_impresso) > 0.01:
        avisos.append(
            f"Soma dos itens extraídos (R$ {valor_total_calculado:.2f}) diverge do TOTAL "
            f"impresso no documento (R$ {valor_total_impresso:.2f})."
        )

    return OrdemDeCompra(
        numero_oc=numero_oc,
        data_oc=data_oc,
        cliente=cliente,
        valor_total_impresso=valor_total_impresso,
        valor_total_calculado=valor_total_calculado,
        itens=itens,
        metodo_extracao=metodo,
        avisos=avisos,
    )


def _para_float(valor: str) -> float:
    return float(valor.replace(".", "").replace(",", "."))
