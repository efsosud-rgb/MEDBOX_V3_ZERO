"""
Script de diagnostico do fluxo de pesquisa externa para SKU_MASTER
(fase SKU-INTERNET-01).

Este script NAO acessa a internet. Ele simula a decisao do robo usando dois
arquivos locais como fonte de dados:

- data/dicionario_mestre/interno/exemplos_validados_sku_master.csv
    (memoria validada pelo usuario, prioridade maxima)
- data/dicionario_mestre/interno/modelo_enriquecimento_externo_sku_master.csv
    (resultados de pesquisa ja registrados, simulando o que uma pesquisa
    externa real traria, incluindo casos de multiplas apresentacoes e
    pendencia de revisao)

Nao acessa o banco de dados. Nao altera nenhum arquivo alem do CSV de saida
em relatorios/. Nao aplica nenhuma correcao.
"""
import csv
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
PASTA_INTERNO = BASE_DIR / "data" / "dicionario_mestre" / "interno"
ARQUIVO_MEMORIA = PASTA_INTERNO / "exemplos_validados_sku_master.csv"
ARQUIVO_MODELO = PASTA_INTERNO / "modelo_enriquecimento_externo_sku_master.csv"
ARQUIVO_SAIDA = BASE_DIR / "relatorios" / "sku_internet_01_fluxo_simulado.csv"

TESTES = [
    "NASONEW",
    "NASOJET",
    "NASOJET ALTO FLUXO",
    "HEPTRIS 40MG",
    "VERSA 80MG",
    "NOXX 60MG",
    "PRODUTO DESCONHECIDO XYZ",
]

STATUS_APLICAVEIS_SEM_REVISAO = {"VALIDADO_USUARIO", "ENCONTRADO_UNICO"}
STATUS_BLOQUEIO_MULTIPLAS = {"MULTIPLAS_APRESENTACOES"}
STATUS_BLOQUEIO_REVISAO = {"PENDENTE_REVISAO", "CONFLITO_FONTES"}
STATUS_NAO_ENCONTRADO = {"NAO_ENCONTRADO"}


def normalizar(texto):
    return re.sub(r"\s+", " ", (texto or "").strip().upper())


def carregar_memoria():
    linhas = []
    with open(ARQUIVO_MEMORIA, encoding="utf-8-sig") as f:
        for linha in csv.DictReader(f):
            linhas.append(linha)
    return linhas


def carregar_modelo():
    linhas = []
    with open(ARQUIVO_MODELO, encoding="utf-8-sig") as f:
        for linha in csv.DictReader(f):
            linhas.append(linha)
    return linhas


def buscar_na_memoria(descricao, memoria):
    chave = normalizar(descricao)
    for linha in memoria:
        if normalizar(linha["descricao_original"]) == chave:
            return linha
    return None


def buscar_no_modelo(descricao, modelo):
    chave = normalizar(descricao)

    # 1) match exato por termo_pesquisa
    for linha in modelo:
        if normalizar(linha["termo_pesquisa"]) == chave:
            return linha

    # 2) match exato por descricao_original
    for linha in modelo:
        if normalizar(linha["descricao_original"]) == chave:
            return linha

    # 3) match parcial: termo_pesquisa contido na descricao de entrada, ou vice-versa
    candidatos = []
    for linha in modelo:
        termo = normalizar(linha["termo_pesquisa"])
        if not termo:
            continue
        if termo in chave or chave in termo:
            candidatos.append(linha)
    if candidatos:
        # prioriza o termo mais longo (match mais especifico)
        candidatos.sort(key=lambda l: -len(l["termo_pesquisa"]))
        return candidatos[0]

    return None


def marca_categoria_do_modelo(descricao, modelo):
    """Busca marca/categoria em modelo mesmo quando a resposta veio da memoria."""
    linha = buscar_no_modelo(descricao, modelo)
    if linha:
        return linha.get("marca", ""), linha.get("categoria_sugerida", "")
    return "", ""


def testar_descricao(descricao, memoria, modelo):
    # 1. Memoria validada pelo usuario tem prioridade absoluta
    linha_memoria = buscar_na_memoria(descricao, memoria)
    if linha_memoria:
        marca, categoria = marca_categoria_do_modelo(descricao, modelo)
        return {
            "descricao_entrada": descricao,
            "acao": "REUTILIZAR_MEMORIA_VALIDADA",
            "status": "VALIDADO_USUARIO",
            "sku_master_sugerido": linha_memoria["sku_master_correto"],
            "marca_sugerida": marca,
            "categoria_sugerida": categoria or "MEDICAMENTOS",
            "motivo": (
                "Descricao ja validada pelo usuario em exemplos_validados_sku_master.csv "
                f"(motivo original: {linha_memoria['motivo']}); pesquisa externa nao necessaria"
            ),
        }

    # 2. Resultado de pesquisa (real ou simulada) ja registrado no modelo de enriquecimento
    linha_modelo = buscar_no_modelo(descricao, modelo)
    if linha_modelo:
        status = linha_modelo["status"]

        if status in STATUS_APLICAVEIS_SEM_REVISAO:
            acao = "USAR_SUGESTAO_PESQUISA_EXTERNA"
        elif status in STATUS_BLOQUEIO_MULTIPLAS:
            acao = "BLOQUEAR_MULTIPLAS_APRESENTACOES"
        elif status in STATUS_BLOQUEIO_REVISAO:
            acao = "MARCAR_PENDENTE_REVISAO"
        elif status in STATUS_NAO_ENCONTRADO:
            acao = "PESQUISAR_EXTERNAMENTE_FASE_FUTURA"
        else:
            acao = "MARCAR_PENDENTE_REVISAO"

        return {
            "descricao_entrada": descricao,
            "acao": acao,
            "status": status,
            "sku_master_sugerido": linha_modelo.get("sku_master_sugerido", ""),
            "marca_sugerida": linha_modelo.get("marca", ""),
            "categoria_sugerida": linha_modelo.get("categoria_sugerida", ""),
            "motivo": linha_modelo.get("motivo_status", ""),
        }

    # 3. Nao ha memoria nem registro de pesquisa local; pesquisa externa real
    #    ainda nao esta implementada nesta fase (apenas planejada).
    return {
        "descricao_entrada": descricao,
        "acao": "PESQUISAR_EXTERNAMENTE_FASE_FUTURA",
        "status": "NAO_ENCONTRADO",
        "sku_master_sugerido": "",
        "marca_sugerida": "",
        "categoria_sugerida": "",
        "motivo": (
            "Termo nao encontrado na memoria validada nem no modelo de enriquecimento local; "
            "pesquisa externa real ainda nao foi implementada nesta fase (SKU-INTERNET-01 e apenas planejamento)"
        ),
    }


def main():
    memoria = carregar_memoria()
    modelo = carregar_modelo()

    resultados = [testar_descricao(descricao, memoria, modelo) for descricao in TESTES]

    ARQUIVO_SAIDA.parent.mkdir(parents=True, exist_ok=True)
    campos = [
        "descricao_entrada", "acao", "status", "sku_master_sugerido",
        "marca_sugerida", "categoria_sugerida", "motivo",
    ]
    with open(ARQUIVO_SAIDA, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=campos)
        writer.writeheader()
        writer.writerows(resultados)

    print(f"{len(resultados)} descricoes testadas. Saida: {ARQUIVO_SAIDA}")
    for r in resultados:
        print(f"[{r['status']}] {r['descricao_entrada']} -> acao={r['acao']} | sku={r['sku_master_sugerido'] or '(sem sugestao)'}")


if __name__ == "__main__":
    main()
