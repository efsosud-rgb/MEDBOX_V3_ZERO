"""
Script de diagnostico da Metodologia Global SKU_MASTER (fase SKU-METODOLOGIA-GLOBAL-01).

Le os arquivos de memoria/regras em data/dicionario_mestre/interno/ e testa um
conjunto fixo de descricoes, gerando uma sugestao de SKU_MASTER quando houver
regra ou exemplo validado com seguranca, ou marcando PENDENTE_REVISAO quando
nao houver.

Nao acessa o banco de dados. Nao altera nenhum arquivo alem do CSV de saida em
relatorios/. Nao aplica nenhuma correcao.
"""
import csv
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
PASTA_INTERNO = BASE_DIR / "data" / "dicionario_mestre" / "interno"
ARQUIVO_EXEMPLOS = PASTA_INTERNO / "exemplos_validados_sku_master.csv"
ARQUIVO_REGRAS = PASTA_INTERNO / "regras_familias_sku_master.csv"
ARQUIVO_SAIDA = BASE_DIR / "relatorios" / "sku_metodologia_global_01_teste.csv"

TESTES = [
    "CLORETO DE SODIO 0,9% 1000ML",
    "CLORETO DE SODIO 9MG/ML VIA NASAL SPRAY 50ML",
    "NASOJET",
    "NASOJET ALTO FLUXO 30 SACHES FRASCO 240ML",
    "HEPTRIS 40MG",
    "VERSA 80MG",
    "NOXX 60MG",
    "CLEXANE 40MG",
    "CLORETO DE SODIO 10% 10ML",
    "CLORETO DE SODIO 20% 10ML",
    "PRODUTO DESCONHECIDO XYZ",
]


def normalizar(texto):
    return re.sub(r"\s+", " ", (texto or "").strip().upper())


def carregar_exemplos():
    exemplos = {}
    with open(ARQUIVO_EXEMPLOS, encoding="utf-8-sig") as f:
        for linha in csv.DictReader(f):
            chave = normalizar(linha["descricao_original"])
            exemplos[chave] = linha
    return exemplos


def carregar_regras():
    regras = []
    with open(ARQUIVO_REGRAS, encoding="utf-8-sig") as f:
        for linha in csv.DictReader(f):
            termos = [normalizar(t) for t in linha["termos_entrada"].split("|") if t.strip()]
            regras.append({**linha, "termos": termos})
    return regras


def extrair_dose_ml(texto):
    """Extrai padrao MG e sugere volume de seringa proporcional para enoxaparina (regra validada)."""
    m = re.search(r"(\d+)\s*MG", texto.upper())
    if not m:
        return None, None
    dose = int(m.group(1))
    # Proporcao validada nos exemplos: 40MG/0,4ML, 60MG/0,6ML, 80MG/0,8ML -> 1mg == 0,01ml
    volume = dose / 100
    volume_str = f"{volume:.1f}".replace(".", ",")
    return dose, volume_str


def extrair_concentracao_percentual(texto):
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*%", texto.upper())
    if m:
        return m.group(1).replace(".", ",")
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*MG/ML", texto.upper())
    if m:
        valor = float(m.group(1).replace(",", "."))
        return f"{valor / 10:.1f}".replace(".", ",")
    return None


def extrair_volume(texto):
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*ML\b", texto.upper())
    return m.group(0).replace(" ", "") if m else None


def testar_descricao(descricao, exemplos, regras):
    chave = normalizar(descricao)

    # 1. Memoria validada pelo usuario (match exato)
    if chave in exemplos:
        exemplo = exemplos[chave]
        return {
            "descricao_entrada": descricao,
            "sku_master_sugerido": exemplo["sku_master_correto"],
            "familia_detectada": exemplo["familia"],
            "status": "OK_MEMORIA_VALIDADA",
            "motivo": exemplo["motivo"],
        }

    # 2. Regra comercial MedBox (match por termo de entrada contido na descricao)
    regra_encontrada = None
    for regra in regras:
        for termo in regra["termos"]:
            if termo and termo in chave:
                regra_encontrada = regra
                break
        if regra_encontrada:
            break

    if regra_encontrada:
        familia = regra_encontrada["familia"]

        if familia == "ENOXAPARINA":
            dose, volume = extrair_dose_ml(chave)
            if dose:
                sku = f"ENOXAPARINA SODICA {dose}MG/{volume}ML"
                return {
                    "descricao_entrada": descricao,
                    "sku_master_sugerido": sku,
                    "familia_detectada": familia,
                    "status": "OK_REGRA_FAMILIA",
                    "motivo": "Nome comercial de enoxaparina reduzido para principio ativo + dose/volume proporcional",
                }
            return {
                "descricao_entrada": descricao,
                "sku_master_sugerido": "",
                "familia_detectada": familia,
                "status": "PENDENTE_REVISAO",
                "motivo": "Familia ENOXAPARINA identificada, mas dose (MG) ausente ou nao reconhecida",
            }

        if familia == "SORO FISIOLOGICO NASAL ALTO FLUXO":
            if "SACHE" in chave and "ML" in chave:
                volume = extrair_volume(chave) or "240ML"
                m_saches = re.search(r"(\d+)\s*SACHES?", chave)
                qtd_saches = m_saches.group(1) if m_saches else "30"
                sku = f"SORO FISIOLOGICO NASAL ALTO FLUXO {qtd_saches} SACHES + FRASCO {volume}"
                return {
                    "descricao_entrada": descricao,
                    "sku_master_sugerido": sku,
                    "familia_detectada": familia,
                    "status": "OK_REGRA_FAMILIA",
                    "motivo": "Marca NASOJET reduzida para soro fisiologico nasal alto fluxo com apresentacao completa",
                }
            return {
                "descricao_entrada": descricao,
                "sku_master_sugerido": "",
                "familia_detectada": familia,
                "status": "PENDENTE_REVISAO",
                "motivo": "Familia SORO FISIOLOGICO NASAL ALTO FLUXO identificada, mas apresentacao (saches/volume) incompleta na entrada",
            }

        if familia == "SORO FISIOLOGICO NASAL":
            volume = extrair_volume(chave)
            concentracao = extrair_concentracao_percentual(chave) or "0,9"
            if volume:
                sku = f"SORO FISIOLOGICO NASAL SPRAY {concentracao}% {volume}"
                return {
                    "descricao_entrada": descricao,
                    "sku_master_sugerido": sku,
                    "familia_detectada": familia,
                    "status": "OK_REGRA_FAMILIA",
                    "motivo": "Cloreto de sodio via nasal reduzido para soro fisiologico nasal spray",
                }
            return {
                "descricao_entrada": descricao,
                "sku_master_sugerido": "",
                "familia_detectada": familia,
                "status": "PENDENTE_REVISAO",
                "motivo": "Familia SORO FISIOLOGICO NASAL identificada, mas volume ausente na entrada",
            }

        if familia == "SORO FISIOLOGICO":
            volume = extrair_volume(chave)
            concentracao = extrair_concentracao_percentual(chave)
            if not concentracao:
                return {
                    "descricao_entrada": descricao,
                    "sku_master_sugerido": "",
                    "familia_detectada": familia,
                    "status": "PENDENTE_REVISAO",
                    "motivo": "Familia SORO FISIOLOGICO identificada, mas concentracao ausente na entrada",
                }
            if concentracao != "0,9":
                # Bloqueio critico: concentracao diferente da validada (0,9%) nao pode reusar o mesmo SKU.
                return {
                    "descricao_entrada": descricao,
                    "sku_master_sugerido": "",
                    "familia_detectada": familia,
                    "status": "PENDENTE_REVISAO",
                    "motivo": (
                        f"Bloqueio critico: concentracao {concentracao}% diverge da concentracao "
                        "validada (0,9%) para a familia SORO FISIOLOGICO; nao reutilizar SKU sem revisao humana"
                    ),
                }
            if not volume:
                return {
                    "descricao_entrada": descricao,
                    "sku_master_sugerido": "",
                    "familia_detectada": familia,
                    "status": "PENDENTE_REVISAO",
                    "motivo": "Familia SORO FISIOLOGICO identificada, mas volume ausente na entrada",
                }
            sku = f"SORO FISIOLOGICO {concentracao}% {volume}"
            return {
                "descricao_entrada": descricao,
                "sku_master_sugerido": sku,
                "familia_detectada": familia,
                "status": "OK_REGRA_FAMILIA",
                "motivo": "Cloreto de sodio 0,9% reduzido para soro fisiologico padrao",
            }

    # 3. Nenhuma memoria nem regra aplicavel com seguranca
    return {
        "descricao_entrada": descricao,
        "sku_master_sugerido": "",
        "familia_detectada": "",
        "status": "PENDENTE_REVISAO",
        "motivo": "Nenhuma memoria validada nem regra de familia reconhecida para esta descricao; requer revisao humana",
    }


def main():
    exemplos = carregar_exemplos()
    regras = carregar_regras()

    resultados = [testar_descricao(descricao, exemplos, regras) for descricao in TESTES]

    ARQUIVO_SAIDA.parent.mkdir(parents=True, exist_ok=True)
    with open(ARQUIVO_SAIDA, "w", newline="", encoding="utf-8-sig") as f:
        campos = ["descricao_entrada", "sku_master_sugerido", "familia_detectada", "status", "motivo"]
        writer = csv.DictWriter(f, fieldnames=campos)
        writer.writeheader()
        writer.writerows(resultados)

    print(f"{len(resultados)} descricoes testadas. Saida: {ARQUIVO_SAIDA}")
    for r in resultados:
        print(f"[{r['status']}] {r['descricao_entrada']} -> {r['sku_master_sugerido'] or '(sem sugestao)'}")


if __name__ == "__main__":
    main()
