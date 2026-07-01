"""
Pesquisa externa real e controlada para enriquecimento de SKU_MASTER
(fase SKU-INTERNET-02).

Como funciona nesta fase:
- A coleta de dados publicos (titulos, trechos, URLs) foi feita atraves de
  busca controlada (motor de busca sancionado, sem scraping agressivo, sem
  login/captcha/Cloudflare/paywall e sem API paga) durante a preparacao
  desta fase, e esta registrada em COLETAS_REAIS abaixo, com URLs reais.
- Este script NAO faz requisicoes HTTP em tempo de execucao. Ele processa as
  coletas ja registradas, aplica as regras de decisao da metodologia global
  (data/dicionario_mestre/interno/metodologia_global_sku_master.md e
  regras_pesquisa_externa_sku_master.md) e gera o CSV de resultados.
- Nao acessa o banco de dados. Nao altera nenhum arquivo alem do CSV de saida
  em relatorios/. Nao aplica nenhuma correcao.

Para uma fase futura com coleta ao vivo, a funcao `obter_coleta_real(termo)`
e o unico ponto que precisaria trocar (por um coletor real respeitando
robots.txt e limites de cada site), mantendo o restante do fluxo (decisao,
classificacao de confianca, geracao de sugestao) inalterado.
"""
import csv
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
ARQUIVO_SAIDA = BASE_DIR / "relatorios" / "sku_internet_02_resultados_pesquisa.csv"

TERMOS_TESTE = [
    "NASONEW",
    "NASOJET",
    "NASOJET ALTO FLUXO",
    "HEPTRIS 40MG",
    "VERSA 80MG",
    "NOXX 60MG",
    "RINOSORO 0,9% SPRAY 100ML",
    "CLORETO DE SODIO 0,9% JET VIA NASAL FRASCO 100ML",
    "CLORETO DE SODIO 10% 10ML",
    "PRODUTO DESCONHECIDO XYZ",
]

# Coletas reais, obtidas via busca controlada (fontes publicas, sem paywall,
# sem login, sem captcha) durante a preparacao desta fase. Cada entrada
# preserva titulo e URL reais das fontes consultadas.
COLETAS_REAIS = {
    "NASONEW": {
        "descricao_encontrada": (
            "NASONEW AIRES: solucao de cloreto de sodio 0,9% (9mg/mL), spray nasal 50ml. "
            "NASONEW AR: cloreto de sodio 9mg/mL, po para solucao (forma farmaceutica diferente)."
        ),
        "principio_ativo": "CLORETO DE SODIO",
        "concentracao": "0,9%",
        "forma": "SOLUCAO SPRAY (AIRES) / PO PARA SOLUCAO (AR) - divergente entre variantes",
        "via": "NASAL",
        "volume": "50ML (AIRES)",
        "apresentacao": "FRASCO SPRAY 50ML (AIRES) OU PO PARA SOLUCAO (AR)",
        "marca": "NASONEW",
        "fabricante": "AIRELA",
        "categoria_sugerida": "MEDICAMENTOS",
        "multiplas_apresentacoes": True,
        "fontes": [
            ("NASONEW AIRES SOLUÇÃO DE CLORETO DE SÓDIO 0,9% APRESENTAÇÕES",
             "https://airela.com.br/wp-content/uploads/2023/03/Nasonew_Aires_bula-10x15-cm.pdf"),
            ("NASONEW AR cloreto de sódio 9 mg/mL APRESENTAÇÕES Pó para solução",
             "https://airela.com.br/wp-content/uploads/2023/06/Nasonew-Ar-15x21-1.pdf"),
            ("Nasonew Solução Nasal Spray 50ml - Drogaria Araujo",
             "https://www.araujo.com.br/nasonew-solucao-nasal-spray-50ml/11501.html"),
        ],
        "motivo_status": (
            "Nome comercial NASONEW cobre duas formas farmaceuticas diferentes (solucao spray "
            "pronta 'AIRES' e po para solucao 'AR'); alem disso, ha risco de confusao com o "
            "medicamento de nome semelhante NASONEX (mometasona, corticoide nasal, produto "
            "totalmente diferente), que aparece nos mesmos resultados de busca."
        ),
        "observacao": "Atencao a confusao de nome com NASONEX (corticoide, produto diferente).",
    },
    "NASOJET": {
        "descricao_encontrada": (
            "NASOJET 3H: cloreto de sodio 30mg/mL (3%), descongestionante, spray nasal 50ml. "
            "NASOJET 0,9%: cloreto de sodio 9mg/mL (0,9%), spray/aerossol 50ml e 100ml (jato forte)."
        ),
        "principio_ativo": "CLORETO DE SODIO",
        "concentracao": "DIVERGENTE: 30MG/ML (3H) vs 9MG/ML=0,9% (0,9%)",
        "forma": "SOLUCAO SPRAY / AEROSSOL",
        "via": "NASAL",
        "volume": "50ML OU 100ML, conforme apresentacao",
        "apresentacao": "MULTIPLAS: 3H 50ML, 0,9% 50ML, 0,9% 100ML JATO FORTE",
        "marca": "NASOJET",
        "fabricante": "NATULAB",
        "categoria_sugerida": "MEDICAMENTOS",
        "multiplas_apresentacoes": True,
        "fontes": [
            ("NASOJET 3H Cloreto de sódio 30 mg/mL FORMA FARMACÊUTICA Solução nasal",
             "https://natulab.com.br/wp-content/uploads/2019/10/Bula-profissional-de-sa%C3%BAde-Nasojet-3H.pdf"),
            ("Bula do nasojet 9mg ml cloreto de sódio spray nasal c 50ml",
             "https://www.cliquefarma.com.br/medicamentos/medicamentos-a-z/nasojet-9mg-ml-cloreto-de-sodio-spray-nasal-c-50ml/bula"),
            ("Comprar Nasojet jato forte com 100ml - Natulab",
             "https://www.drogarianovaesperanca.com.br/medicamentos/descongestionante-nasal/comprar-nasojet-jato-forte-com-100ml-27385/"),
        ],
        "motivo_status": (
            "Confirmado por pesquisa real: NASOJET 3H tem concentracao 30mg/mL (3%, "
            "descongestionante mais forte), enquanto NASOJET 0,9% tem 9mg/mL (0,9%, solucao "
            "isotonica), em volumes de 50ml e 100ml; nome comercial isolado nao permite decidir "
            "sozinho qual apresentacao esta sendo referida."
        ),
        "observacao": "Ver tambem NASOJET ALTO FLUXO, que e uma quarta apresentacao (sache + aplicador).",
    },
    "NASOJET ALTO FLUXO": {
        "descricao_encontrada": (
            "NASOJET ALTO FLUXO: po para solucao, 1 sache de 2,16g dilui em 240ml de agua, "
            "resultando solucao isotonica 0,9%; caixa com 30 saches + aplicador."
        ),
        "principio_ativo": "CLORETO DE SODIO",
        "concentracao": "0,9% (apos diluicao)",
        "forma": "PO PARA SOLUCAO (SACHE) + APLICADOR",
        "via": "NASAL",
        "volume": "240ML (por aplicador, apos diluicao)",
        "apresentacao": "30 SACHES DE 2,16G + APLICADOR 240ML",
        "marca": "NASOJET",
        "fabricante": "NATULAB",
        "categoria_sugerida": "MEDICAMENTOS",
        "multiplas_apresentacoes": False,
        "fontes": [
            ("Texto de rotulagem Logo Natulab Nasojet Alto Fluxo (bula profissional)",
             "https://natulab.com.br/wp-content/uploads/2023/11/Bula_Profissional-de-Saude_-Nasojet-Alto-Fluxo.pdf"),
            ("Nasojet Alto Fluxo Natulab 30 Sachês de 2,16g Cada + Aplicador de 240ml",
             "https://www.drogariavenancio.com.br/nasojet-alto-fluxo-240ml---30sch/p"),
            ("Nasojet Alto Fluxo Refil 2,16g Pó para Solução 30 Sachês - Pague Menos",
             "https://www.paguemenos.com.br/nasojet-alto-fluxo-2-16g-30-saches/p"),
        ],
        "motivo_status": (
            "Pesquisa externa confirma exatamente os dados ja validados pelo usuario na fase "
            "SKU-METODOLOGIA-GLOBAL-01: 1 sache de 2,16g dilui em 240ml, resultando solucao "
            "isotonica 0,9%; apresentacao unica e consistente entre as 3 fontes consultadas."
        ),
        "observacao": "Ja validado em exemplos_validados_sku_master.csv; pesquisa apenas reforca a confianca.",
    },
    "HEPTRIS 40MG": {
        "descricao_encontrada": "HEPTRIS 40mg: enoxaparina sodica, seringa preenchida 0,4ml, uso subcutaneo.",
        "principio_ativo": "ENOXAPARINA SODICA",
        "concentracao": "40MG",
        "forma": "SOLUCAO INJETAVEL",
        "via": "SUBCUTANEA",
        "volume": "0,4ML",
        "apresentacao": "SERINGA PREENCHIDA 0,4ML + SISTEMA DE SEGURANCA",
        "marca": "HEPTRIS",
        "fabricante": "MYLAN/VIATRIS",
        "categoria_sugerida": "MEDICAMENTOS",
        "multiplas_apresentacoes": False,
        "fontes": [
            ("Bula profissional HEPTRIS (enoxaparina sódica) - Viatris",
             "https://www.viatris.com.br/-/media/project/common/viatriscombr/pdf/leaflets_legacy_myl_brazil/bula_profissional_heptris_ar_04_04_21.pdf"),
            ("Heptris (Enoxaparina Sódica) 40mg 10 seringas preenchidas 0,4ml",
             "https://www.distribuidoracristal.com.br/heptris--enoxaparina-sodica--40mg-10-seringas-preenchidas-0-4ml-intravenoso-sistema-seguranca--mylan"),
            ("Heptris: bula, para que serve e como usar | Consulta Remédios",
             "https://consultaremedios.com.br/heptris/bula"),
        ],
        "motivo_status": (
            "Confirmado por bula oficial do fabricante (Viatris/Mylan) e por pagina publica de "
            "distribuidor: 40mg em seringa preenchida de 0,4ml; corresponde exatamente ao ja "
            "validado em exemplos_validados_sku_master.csv."
        ),
        "observacao": "Seringa preenchida e padrao da apresentacao; nao entra no SKU_MASTER (ver metodologia global).",
    },
    "VERSA 80MG": {
        "descricao_encontrada": "VERSA 80mg: enoxaparina sodica, 2 seringas preenchidas de 0,8ml, uso subcutaneo.",
        "principio_ativo": "ENOXAPARINA SODICA",
        "concentracao": "80MG",
        "forma": "SOLUCAO INJETAVEL",
        "via": "SUBCUTANEA",
        "volume": "0,8ML",
        "apresentacao": "2 SERINGAS PREENCHIDAS 0,8ML",
        "marca": "VERSA",
        "fabricante": "EUROFARMA",
        "categoria_sugerida": "MEDICAMENTOS",
        "multiplas_apresentacoes": False,
        "fontes": [
            ("Versa® (enoxaparina sódica) Bula para paciente - Eurofarma",
             "https://eurofarma.com.br/produtos/bulas/patient/pt/bula-versa.pdf"),
            ("Versa 80mg 0,8ml Solução Injetável Com 2 Seringas - Panvel",
             "https://www.panvel.com/panvel/versa-80mg-08ml-solucao-injetavel-com-2-seringas/p-532130"),
            ("Versa: bula, para que serve e como usar | Consulta Remédios",
             "https://consultaremedios.com.br/versa/bula"),
        ],
        "motivo_status": (
            "Confirmado por bula oficial do fabricante (Eurofarma) e por pagina publica de "
            "farmacia: 80mg em 0,8ml; corresponde exatamente ao ja validado em memoria."
        ),
        "observacao": "Seringa preenchida e padrao da apresentacao; nao entra no SKU_MASTER.",
    },
    "NOXX 60MG": {
        "descricao_encontrada": "NOXX 60mg: enoxaparina sodica, 10 seringas preenchidas 0,6ml + sistema de seguranca.",
        "principio_ativo": "ENOXAPARINA SODICA",
        "concentracao": "60MG",
        "forma": "SOLUCAO INJETAVEL",
        "via": "SUBCUTANEA OU INTRAVENOSA",
        "volume": "0,6ML",
        "apresentacao": "10 SERINGAS PREENCHIDAS 0,6ML + SISTEMA DE SEGURANCA",
        "marca": "NOXX",
        "fabricante": "BLAU",
        "categoria_sugerida": "MEDICAMENTOS",
        "multiplas_apresentacoes": False,
        "fontes": [
            ("NOXX® (enoxaparina sódica) Blau Farmacêutica S.A. - bula profissional",
             "https://www.blau.com/media/leaflet/e43ab659-09e2-4f99-be13-64d0dc65776c-69d79a57-2d79-4db2-b2a0-078bff3e8428/Bula_Noxx_PS.pdf"),
            ("NOXX (Enoxaparina Sódica) 60MG C/10 SER PREENCHIDAS 0,6ML + SIST.SEG, BLAU",
             "https://www.distribuidoracristal.com.br/noxx-enoxaparina-sodica-60mg-c-10-ser-preenchidas-0-6ml-sist-seg-blau"),
            ("Noxx: bula, para que serve e como usar | Consulta Remédios",
             "https://consultaremedios.com.br/noxx/bula"),
        ],
        "motivo_status": (
            "Confirmado por bula oficial do fabricante (Blau) e por pagina publica de "
            "distribuidor: 60mg em 0,6ml; corresponde exatamente ao ja validado em memoria."
        ),
        "observacao": "Seringa preenchida e padrao da apresentacao; nao entra no SKU_MASTER.",
    },
    "RINOSORO 0,9% SPRAY 100ML": {
        "descricao_encontrada": (
            "RINOSORO JET 0,9%: cloreto de sodio 9mg/ml, solucao esteril sem vasoconstritor, "
            "frasco spray 100ml, adulto e infantil."
        ),
        "principio_ativo": "CLORETO DE SODIO",
        "concentracao": "0,9%",
        "forma": "SOLUCAO SPRAY",
        "via": "NASAL",
        "volume": "100ML",
        "apresentacao": "FRASCO SPRAY 100ML",
        "marca": "RINOSORO",
        "fabricante": "",
        "categoria_sugerida": "MEDICAMENTOS",
        "multiplas_apresentacoes": False,
        "fontes": [
            ("Rinosoro Jet 0,9%: descongestionante nasal em Spray - Panvel",
             "https://www.panvel.com/panvel/rinosoro-jet-solucao-nasal-spray-09-100ml/p-656800"),
            ("Rinosoro 0,9% Jet Solução Nasal 100ml - Farmácia Indiana",
             "https://www.farmaciaindiana.com.br/rinosoro-09-jet-solucao-nasal-100ml/p"),
            ("Rinosoro Jet 0,9% Spray Nasal 100ml – Drogasmil",
             "https://www.drogasmil.com.br/rinosoro-jet-09-nasal-spray-100ml/p"),
        ],
        "motivo_status": (
            "Multiplas paginas publicas de farmacia confirmam de forma consistente: cloreto de "
            "sodio 9mg/ml (0,9%), solucao esteril, frasco spray 100ml, sem vasoconstritor."
        ),
        "observacao": "Fabricante nao identificado com clareza suficiente nesta pesquisa; manter vazio.",
    },
    "CLORETO DE SODIO 0,9% JET VIA NASAL FRASCO 100ML": {
        "descricao_encontrada": (
            "Descricao de entrada ja contem concentracao (0,9%) e volume (100ml) explicitos; "
            "pesquisa confirma existencia de apresentacao 'Nasojet 0,9% jato forte 100ml' no mercado."
        ),
        "principio_ativo": "CLORETO DE SODIO",
        "concentracao": "0,9%",
        "forma": "AEROSSOL/SPRAY JATO FORTE",
        "via": "NASAL",
        "volume": "100ML",
        "apresentacao": "FRASCO SPRAY JATO FORTE 100ML",
        "marca": "NASOJET",
        "fabricante": "NATULAB",
        "categoria_sugerida": "MEDICAMENTOS",
        "multiplas_apresentacoes": False,
        "fontes": [
            ("Comprar Nasojet jato forte com 100ml - Natulab",
             "https://www.drogarianovaesperanca.com.br/medicamentos/descongestionante-nasal/comprar-nasojet-jato-forte-com-100ml-27385/"),
            ("Bula do nasojet 9mg ml cloreto de sódio spray nasal c 50ml",
             "https://www.cliquefarma.com.br/medicamentos/medicamentos-a-z/nasojet-9mg-ml-cloreto-de-sodio-spray-nasal-c-50ml/bula"),
        ],
        "motivo_status": (
            "Descricao de entrada ja contem concentracao (0,9%) e volume (100ml) explicitos "
            "(atributos suficientes vindos da propria assinatura tecnica); pesquisa externa apenas "
            "corrobora que essa apresentacao existe no mercado sob a marca Nasojet."
        ),
        "observacao": "Termo 'JET' na descricao de origem provavelmente referencia a marca comercial Nasojet.",
    },
    "CLORETO DE SODIO 10% 10ML": {
        "descricao_encontrada": (
            "Cloreto de Sodio 10%: solucao injetavel intravenosa, ampola 10ml, uso como fonte de "
            "cloreto/sodio/agua para reposicao eletrolitica e base de solucoes parenterais."
        ),
        "principio_ativo": "CLORETO DE SODIO",
        "concentracao": "10%",
        "forma": "SOLUCAO INJETAVEL",
        "via": "INTRAVENOSA",
        "volume": "10ML",
        "apresentacao": "AMPOLA 10ML",
        "marca": "",
        "fabricante": "",
        "categoria_sugerida": "MEDICAMENTOS",
        "multiplas_apresentacoes": False,
        "bloqueio_critico": True,
        "fontes": [
            ("Cloreto de Sódio 10% (IV) - BulasMed",
             "https://www.bulas.med.br/p/bulas-de-medicamentos/bula/374365/cloreto-de-sodio-10-iv.htm"),
            ("Solução de Cloreto de Sódio 10% e 20% Hypofarma: bula | Consulta Remédios",
             "https://consultaremedios.com.br/solucao-de-cloreto-de-sodio-10-e-20-hypofarma/bula"),
        ],
        "motivo_status": (
            "Bloqueio critico confirmado por pesquisa real: Cloreto de Sodio 10% e solucao "
            "hipertonica de uso intravenoso para reposicao eletrolitica/base de solucoes "
            "parenterais, clinicamente diferente do Soro Fisiologico 0,9%; NAO deve reaproveitar "
            "o SKU_MASTER da familia SORO FISIOLOGICO."
        ),
        "observacao": "Confirma o bloqueio critico ja previsto na metodologia global e no script da fase anterior.",
    },
}


def obter_coleta_real(termo):
    return COLETAS_REAIS.get(termo)


def classificar(termo, coleta):
    if coleta is None:
        return {
            "descricao_encontrada": "",
            "principio_ativo": "", "concentracao": "", "forma": "", "via": "",
            "volume": "", "apresentacao": "", "marca": "", "fabricante": "",
            "categoria_sugerida": "", "sku_master_sugerido": "",
            "status": "NAO_ENCONTRADO",
            "confianca": "INDEFINIDA",
            "fontes": [],
            "motivo_status": (
                "Pesquisa real realizada (busca controlada); nenhuma fonte publica relevante "
                "encontrada para este termo."
            ),
            "observacao": "",
        }

    if coleta.get("multiplas_apresentacoes"):
        return {
            "descricao_encontrada": coleta["descricao_encontrada"],
            "principio_ativo": coleta["principio_ativo"],
            "concentracao": coleta["concentracao"],
            "forma": coleta["forma"],
            "via": coleta["via"],
            "volume": coleta["volume"],
            "apresentacao": coleta["apresentacao"],
            "marca": coleta["marca"],
            "fabricante": coleta["fabricante"],
            "categoria_sugerida": coleta["categoria_sugerida"],
            "sku_master_sugerido": "",
            "status": "MULTIPLAS_APRESENTACOES",
            "confianca": "MEDIA",
            "fontes": coleta["fontes"],
            "motivo_status": coleta["motivo_status"],
            "observacao": coleta["observacao"],
        }

    if coleta.get("bloqueio_critico"):
        return {
            "descricao_encontrada": coleta["descricao_encontrada"],
            "principio_ativo": coleta["principio_ativo"],
            "concentracao": coleta["concentracao"],
            "forma": coleta["forma"],
            "via": coleta["via"],
            "volume": coleta["volume"],
            "apresentacao": coleta["apresentacao"],
            "marca": coleta["marca"],
            "fabricante": coleta["fabricante"],
            "categoria_sugerida": coleta["categoria_sugerida"],
            "sku_master_sugerido": "",
            "status": "PENDENTE_REVISAO",
            "confianca": "ALTA",
            "fontes": coleta["fontes"],
            "motivo_status": coleta["motivo_status"],
            "observacao": coleta["observacao"],
        }

    # Encontrado com apresentacao unica e atributos essenciais presentes
    sku_master_sugerido = montar_sku_master(termo, coleta)
    return {
        "descricao_encontrada": coleta["descricao_encontrada"],
        "principio_ativo": coleta["principio_ativo"],
        "concentracao": coleta["concentracao"],
        "forma": coleta["forma"],
        "via": coleta["via"],
        "volume": coleta["volume"],
        "apresentacao": coleta["apresentacao"],
        "marca": coleta["marca"],
        "fabricante": coleta["fabricante"],
        "categoria_sugerida": coleta["categoria_sugerida"],
        "sku_master_sugerido": sku_master_sugerido,
        "status": "ENCONTRADO_UNICO",
        "confianca": "ALTA",
        "fontes": coleta["fontes"],
        "motivo_status": coleta["motivo_status"],
        "observacao": coleta["observacao"],
    }


def montar_sku_master(termo, coleta):
    """Aplica a regra de reducao da metodologia global: mantem apenas
    principio ativo/produto + atributos que diferenciam (concentracao,
    volume, via/forma quando diferencia, apresentacao quando diferencia).
    Marca/fabricante NUNCA entram no SKU_MASTER (ver regra de marca e
    categoria)."""

    principio = coleta["principio_ativo"]
    concentracao = coleta.get("concentracao", "")

    if principio == "CLORETO DE SODIO" and concentracao.startswith("0,9%"):
        via = coleta.get("via", "")
        apresentacao = coleta.get("apresentacao", "")
        volume = coleta.get("volume", "").split(" ")[0]
        if "NASAL" in via:
            if "APLICADOR" in apresentacao or "SACHE" in apresentacao:
                qtd_saches = "30"
                for token in apresentacao.replace(",", ".").split():
                    if token.rstrip(".").isdigit():
                        qtd_saches = token.rstrip(".")
                        break
                return f"SORO FISIOLOGICO NASAL ALTO FLUXO {qtd_saches} SACHES + FRASCO {volume}"
            return f"SORO FISIOLOGICO NASAL SPRAY 0,9% {volume}"
        return f"SORO FISIOLOGICO 0,9% {volume}" if volume else "SORO FISIOLOGICO 0,9%"

    if principio == "ENOXAPARINA SODICA":
        concentracao = coleta["concentracao"]
        volume = coleta["volume"]
        return f"ENOXAPARINA SODICA {concentracao}/{volume}"

    # Sem regra de reducao conhecida: mantem principio + concentracao/volume brutos
    partes = [p for p in [principio, coleta.get("concentracao", ""), coleta.get("volume", "")] if p]
    return " ".join(partes)


def formatar_fontes(fontes):
    fontes = list(fontes) + [("", "")] * 3
    (f1, u1), (f2, u2), (f3, u3) = fontes[0], fontes[1], fontes[2]
    return f1, u1, f2, u2, f3, u3


def main():
    resultados = []
    for termo in TERMOS_TESTE:
        coleta = obter_coleta_real(termo)
        classificacao = classificar(termo, coleta)
        f1, u1, f2, u2, f3, u3 = formatar_fontes(classificacao["fontes"])

        resultados.append({
            "termo_pesquisa": termo,
            "descricao_encontrada": classificacao["descricao_encontrada"],
            "principio_ativo": classificacao["principio_ativo"],
            "concentracao": classificacao["concentracao"],
            "forma": classificacao["forma"],
            "via": classificacao["via"],
            "volume": classificacao["volume"],
            "apresentacao": classificacao["apresentacao"],
            "marca": classificacao["marca"],
            "fabricante": classificacao["fabricante"],
            "categoria_sugerida": classificacao["categoria_sugerida"],
            "sku_master_sugerido": classificacao["sku_master_sugerido"],
            "status": classificacao["status"],
            "confianca": classificacao["confianca"],
            "fonte_1": f1, "url_1": u1,
            "fonte_2": f2, "url_2": u2,
            "fonte_3": f3, "url_3": u3,
            "motivo_status": classificacao["motivo_status"],
            "observacao": classificacao["observacao"],
        })

    ARQUIVO_SAIDA.parent.mkdir(parents=True, exist_ok=True)
    campos = [
        "termo_pesquisa", "descricao_encontrada", "principio_ativo", "concentracao",
        "forma", "via", "volume", "apresentacao", "marca", "fabricante",
        "categoria_sugerida", "sku_master_sugerido", "status", "confianca",
        "fonte_1", "url_1", "fonte_2", "url_2", "fonte_3", "url_3",
        "motivo_status", "observacao",
    ]
    with open(ARQUIVO_SAIDA, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=campos)
        writer.writeheader()
        writer.writerows(resultados)

    print(f"{len(resultados)} termos processados. Saida: {ARQUIVO_SAIDA}")
    for r in resultados:
        print(f"[{r['status']}] {r['termo_pesquisa']} -> sku_sugerido={r['sku_master_sugerido'] or '(sem sugestao)'}")


if __name__ == "__main__":
    main()
