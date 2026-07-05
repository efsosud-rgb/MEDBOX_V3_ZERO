"""Extração de perfil técnico de descrições de itens médico-hospitalares.

Objetivo: impedir que o cruzamento de itens (correlacionador.py) confunda
produtos tecnicamente diferentes só porque o texto é parecido — ex.:
SERINGA 60ML não pode "ganhar" contra SERINGA 20ML.

Cada atributo extraído aqui vira um campo do "perfil técnico" do item.
Dois itens só podem ser considerados o MESMO produto se, para cada
atributo presente em AMBOS os itens, os valores forem compatíveis.
Atributo ausente em um dos dois lados não bloqueia o match (ausência de
informação não é conflito) — só um valor presente e DIFERENTE bloqueia.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

_UNIDADES_VOLUME = {"ML": 1, "L": 1000, "LITROS": 1000, "LITRO": 1000}


def normalizar_texto(texto: str) -> str:
    """Maiúsculas, sem acento, sem caractere de substituição, espaços colapsados.

    Importante: º/°/ª são removidos ANTES da decomposição NFKD, porque a
    decomposição de compatibilidade Unicode transforma "º" em "o" (não
    remove o caractere) — se isso acontecer antes, "Nº 16" vira "NO 16"
    e o regex de calibre (_RE_CALIBRE) deixa de casar.
    """
    if not texto:
        return ""
    texto = texto.replace("�", " ")
    texto = re.sub(r"[°ºª]", "", texto)
    nfkd = unicodedata.normalize("NFKD", texto)
    sem_acento = "".join(c for c in nfkd if not unicodedata.combining(c))
    sem_acento = sem_acento.upper()
    sem_acento = re.sub(r"\s+", " ", sem_acento).strip()
    return sem_acento


@dataclass
class PerfilTecnico:
    texto_normalizado: str = ""
    volume_ml: float | None = None
    dimensao: tuple[float, float] | None = None
    calibre: str | None = None
    tamanho: str | None = None
    publico: str | None = None  # ADULTO / INFANTIL
    esterilidade: str | None = None  # ESTERIL / NAO_ESTERIL
    tipo_po: str | None = None  # COM_PO / SEM_PO
    luer: str | None = None  # LOCK / SLIP
    atributos_conflitantes: list = field(default_factory=list)


_RE_VOLUME = re.compile(r"(\d+(?:[.,]\d+)?)\s*(ML|LITROS?|L)\b")
_RE_DIMENSAO = re.compile(r"(\d+(?:[.,]\d+)?)\s*X\s*(\d+(?:[.,]\d+)?)\s*(CM)?\b")
_RE_CALIBRE = re.compile(r"\bN[º°]?\s*[.:]?\s*(\d+(?:[.,]\d+)?)\b")
_RE_TAMANHO = re.compile(r"\b(PP|P|M|G|GG|XG|PEQUENO|MEDIO|GRANDE)\b")
_TAMANHO_CANONICO = {
    "PP": "PP", "P": "P", "PEQUENO": "P",
    "M": "M", "MEDIO": "M",
    "G": "G", "GRANDE": "G",
    "GG": "GG", "XG": "GG",
}


def _extrair_volume(texto: str) -> float | None:
    m = _RE_VOLUME.search(texto)
    if not m:
        return None
    valor = float(m.group(1).replace(",", "."))
    unidade = m.group(2)
    return valor * _UNIDADES_VOLUME.get(unidade, 1)


def _extrair_dimensao(texto: str) -> tuple[float, float] | None:
    m = _RE_DIMENSAO.search(texto)
    if not m:
        return None
    a = float(m.group(1).replace(",", "."))
    b = float(m.group(2).replace(",", "."))
    return (a, b) if a <= b else (b, a)


def _extrair_calibre(texto: str) -> str | None:
    m = _RE_CALIBRE.search(texto)
    if not m:
        return None
    valor = m.group(1).replace(",", ".")
    if valor.endswith(".0"):
        valor = valor[:-2]
    return valor


def _extrair_tamanho(texto: str) -> str | None:
    m = _RE_TAMANHO.search(texto)
    if not m:
        return None
    return _TAMANHO_CANONICO.get(m.group(1))


def _extrair_publico(texto: str) -> str | None:
    if "INFANTIL" in texto or "PEDIATRIC" in texto:
        return "INFANTIL"
    if "ADULTO" in texto:
        return "ADULTO"
    return None


def _extrair_esterilidade(texto: str) -> str | None:
    if "NAO ESTERIL" in texto or "NAO-ESTERIL" in texto:
        return "NAO_ESTERIL"
    if "ESTERIL" in texto:
        return "ESTERIL"
    return None


def _extrair_tipo_po(texto: str) -> str | None:
    if "SEM PO" in texto or "S/ PO" in texto or "SEM PÓ".upper() in texto:
        return "SEM_PO"
    if "COM PO" in texto or "C/ PO" in texto or re.search(r"\bCOM P\b", texto):
        return "COM_PO"
    return None


def _extrair_luer(texto: str) -> str | None:
    if "LUER LOCK" in texto or "LUER LOK" in texto:
        return "LOCK"
    if "LUER SLIP" in texto:
        return "SLIP"
    return None


def extrair_perfil(descricao: str) -> PerfilTecnico:
    texto = normalizar_texto(descricao)
    return PerfilTecnico(
        texto_normalizado=texto,
        volume_ml=_extrair_volume(texto),
        dimensao=_extrair_dimensao(texto),
        calibre=_extrair_calibre(texto),
        tamanho=_extrair_tamanho(texto),
        publico=_extrair_publico(texto),
        esterilidade=_extrair_esterilidade(texto),
        tipo_po=_extrair_tipo_po(texto),
        luer=_extrair_luer(texto),
    )


def _proximo(a: float, b: float, tolerancia: float = 0.01) -> bool:
    if a == 0:
        return b == 0
    return abs(a - b) / max(abs(a), abs(b)) <= tolerancia


def comparar_perfis(p1: PerfilTecnico, p2: PerfilTecnico) -> tuple[bool, list[str]]:
    """Retorna (conflito_tecnico, motivos). conflito_tecnico=True bloqueia GANHO automático."""
    motivos: list[str] = []

    if p1.volume_ml is not None and p2.volume_ml is not None:
        if not _proximo(p1.volume_ml, p2.volume_ml):
            motivos.append(f"volume divergente ({p1.volume_ml}ML x {p2.volume_ml}ML)")

    if p1.dimensao is not None and p2.dimensao is not None:
        if not (_proximo(p1.dimensao[0], p2.dimensao[0]) and _proximo(p1.dimensao[1], p2.dimensao[1])):
            motivos.append(f"dimensão divergente ({p1.dimensao} x {p2.dimensao})")

    if p1.calibre is not None and p2.calibre is not None:
        if p1.calibre != p2.calibre:
            motivos.append(f"calibre/número divergente (Nº{p1.calibre} x Nº{p2.calibre})")

    if p1.tamanho is not None and p2.tamanho is not None:
        if p1.tamanho != p2.tamanho:
            motivos.append(f"tamanho divergente ({p1.tamanho} x {p2.tamanho})")

    if p1.publico is not None and p2.publico is not None:
        if p1.publico != p2.publico:
            motivos.append(f"público divergente ({p1.publico} x {p2.publico})")

    if p1.esterilidade is not None and p2.esterilidade is not None:
        if p1.esterilidade != p2.esterilidade:
            motivos.append(f"esterilidade divergente ({p1.esterilidade} x {p2.esterilidade})")

    if p1.tipo_po is not None and p2.tipo_po is not None:
        if p1.tipo_po != p2.tipo_po:
            motivos.append(f"pó divergente ({p1.tipo_po} x {p2.tipo_po})")

    if p1.luer is not None and p2.luer is not None:
        if p1.luer != p2.luer:
            motivos.append(f"conector Luer divergente ({p1.luer} x {p2.luer})")

    return (len(motivos) > 0, motivos)


_ATRIBUTOS_TECNICOS = ["volume_ml", "dimensao", "calibre", "tamanho", "publico", "esterilidade", "tipo_po", "luer"]


def contar_atributos_comparaveis(p1: PerfilTecnico, p2: PerfilTecnico) -> int:
    """Quantos atributos técnicos existem em AMBOS os perfis (por isso são comparáveis)."""
    return sum(
        1 for atr in _ATRIBUTOS_TECNICOS
        if getattr(p1, atr) is not None and getattr(p2, atr) is not None
    )


def score_tecnico(p1: PerfilTecnico, p2: PerfilTecnico) -> float:
    """Score 0-100: quanto mais atributos compatíveis em comum, maior o score.

    Não recompensa ausência de atributos — só coincidências reais. Quando
    nenhum atributo é comparável, devolve um valor neutro (50); quem chama
    esta função deve checar contar_atributos_comparaveis() antes de dar
    peso a este score, para não penalizar itens sem atributo técnico
    identificável nos dois lados (ver correlacionador.cruzar_itens).
    """
    comparaveis = 0
    compativeis = 0
    for atr in _ATRIBUTOS_TECNICOS:
        v1, v2 = getattr(p1, atr), getattr(p2, atr)
        if v1 is not None and v2 is not None:
            comparaveis += 1
            if v1 == v2:
                compativeis += 1
    if comparaveis == 0:
        return 50.0  # neutro: nenhum atributo técnico identificável em nenhum dos dois lados
    return 100.0 * compativeis / comparaveis
