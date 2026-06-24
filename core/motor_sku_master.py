
import re

try:
    from core.dicionario_tecnico import aplicar_sinonimos_dicionario
except Exception:
    aplicar_sinonimos_dicionario = None


def remover_acentos(txt):
    txt = str(txt or "")
    mapa = {
        "Á": "A", "À": "A", "Ã": "A", "Â": "A", "Ä": "A",
        "É": "E", "Ê": "E", "È": "E", "Ë": "E",
        "Í": "I", "Ì": "I", "Î": "I", "Ï": "I",
        "Ó": "O", "Ô": "O", "Õ": "O", "Ò": "O", "Ö": "O",
        "Ú": "U", "Ù": "U", "Û": "U", "Ü": "U",
        "Ç": "C",
        "á": "a", "à": "a", "ã": "a", "â": "a", "ä": "a",
        "é": "e", "ê": "e", "è": "e", "ë": "e",
        "í": "i", "ì": "i", "î": "i", "ï": "i",
        "ó": "o", "ô": "o", "õ": "o", "ò": "o", "ö": "o",
        "ú": "u", "ù": "u", "û": "u", "ü": "u",
        "ç": "c",
    }
    for a, b in mapa.items():
        txt = txt.replace(a, b)
    return txt


def normalizar_descricao(txt):
    t = remover_acentos(txt).upper()

    t = t.replace("\\", "/")
    t = t.replace("N°", " N ")
    t = t.replace("Nº", " N ")
    t = t.replace("NO ", " N ")
    t = t.replace("NUMERO", " N ")

    # Primeiro aplica o dicionário técnico vindo do banco.
    if aplicar_sinonimos_dicionario:
        t = aplicar_sinonimos_dicionario(t)

    # Normalizações de segurança caso o banco ainda não tenha alguma variação.
    t = t.replace("COM/BALAO", " COM BALAO ")
    t = t.replace("COM /BALAO", " COM BALAO ")
    t = t.replace("COM/ BALAO", " COM BALAO ")
    t = t.replace("C/BALAO", " COM BALAO ")
    t = t.replace("C/ BALAO", " COM BALAO ")
    t = t.replace("C /BALAO", " COM BALAO ")
    t = t.replace("C / BALAO", " COM BALAO ")

    t = t.replace("SEM/BALAO", " SEM BALAO ")
    t = t.replace("SEM /BALAO", " SEM BALAO ")
    t = t.replace("SEM/ BALAO", " SEM BALAO ")
    t = t.replace("S/BALAO", " SEM BALAO ")
    t = t.replace("S/ BALAO", " SEM BALAO ")
    t = t.replace("S /BALAO", " SEM BALAO ")
    t = t.replace("S / BALAO", " SEM BALAO ")

    t = t.replace("COM/BALONETE", " COM BALONETE ")
    t = t.replace("C/BALONETE", " COM BALONETE ")
    t = t.replace("SEM/BALONETE", " SEM BALONETE ")
    t = t.replace("S/BALONETE", " SEM BALONETE ")

    t = t.replace("COM/CUFF", " COM CUFF ")
    t = t.replace("C/CUFF", " COM CUFF ")
    t = t.replace("SEM/CUFF", " SEM CUFF ")
    t = t.replace("S/CUFF", " SEM CUFF ")

    t = t.replace("C/", " COM ")
    t = t.replace("S/", " SEM ")

    t = t.replace("ORO TRAQUEAL", "ENDOTRAQUEAL")
    t = t.replace("ORO-TRAQUEAL", "ENDOTRAQUEAL")
    t = t.replace("OROTRAQUEAL", "ENDOTRAQUEAL")
    t = t.replace("CANULA ENDOTRAQUEAL", "TUBO ENDOTRAQUEAL")
    t = t.replace("SONDA ENDOTRAQUEAL", "TUBO ENDOTRAQUEAL")

    t = t.replace("BALONETE", "CUFF")
    t = t.replace("BALAO", "CUFF")

    t = t.replace("POLIVINIL", "PVC")
    t = t.replace("POLI VINIL", "PVC")
    t = t.replace("CLORETO DE POLIVINILA", "PVC")

    t = re.sub(r"[^A-Z0-9,.\-/+% ]+", " ", t)
    t = re.sub(r"\s+", " ", t).strip()

    return t


def formatar_medida(valor, unidade="MM"):
    valor = str(valor or "").strip().replace(".", ",")
    if "," not in valor:
        valor = valor + ",0"
    return f"{valor}{unidade}"


def numero_valido_tubo(valor):
    try:
        n = float(str(valor).replace(",", "."))
        return 2.0 <= n <= 10.0
    except Exception:
        return False


def extrair_medida_tubo(t):
    # N7,5MM / N4,5MM / N. 7,5MM / N 7,5MM
    m = re.search(r"\bN\.?\s*(\d+[,.]\d+)\s*MM\b", t)
    if m and numero_valido_tubo(m.group(1)):
        return formatar_medida(m.group(1), "MM"), "MEDIDA_POR_N_DECIMAL_COM_MM"

    # Casos complexos reais: NO 12, 2,5MM / N 10, 2,0MM
    m = re.search(r"\bN\s*(\d{2,})\s*,\s*(\d+[,.]\d+)\s*MM\b", t)
    if m and numero_valido_tubo(m.group(2)):
        return formatar_medida(m.group(2), "MM"), "MEDIDA_APOS_N_COMPLEXO"

    # N. 3,5 / N 3,5 / Nº8
    m = re.search(r"\bN\.?\s*(\d+(?:[,.]\d+)?)\b", t)
    if m and numero_valido_tubo(m.group(1)):
        return formatar_medida(m.group(1), "MM"), "MEDIDA_POR_N"

    # TAM 9,0
    m = re.search(r"\bTAM\s*(\d+(?:[,.]\d+)?)\b", t)
    if m and numero_valido_tubo(m.group(1)):
        return formatar_medida(m.group(1), "MM"), "MEDIDA_POR_TAM"

    # Remove medidas que não são do tubo, como conector 15MM.
    t_limpo = re.sub(r"CONECTOR\s+DE\s+\d+(?:[,.]\d+)?\s*MM", " ", t)
    t_limpo = re.sub(r"CONECTOR\s+\d+(?:[,.]\d+)?\s*MM", " ", t_limpo)
    t_limpo = re.sub(r"GRADUACAO\s+EM\s+CENTIMETROS", " ", t_limpo)

    m = re.search(r"ENDOTRAQUEAL\s+(\d+(?:[,.]\d+)?)\s*MM", t_limpo)
    if m and numero_valido_tubo(m.group(1)):
        return formatar_medida(m.group(1), "MM"), "MEDIDA_APOS_ENDOTRAQUEAL_MM"

    m = re.search(r"ENDOTRAQUEAL\s+(\d+(?:[,.]\d+)?)\s+(COM|SEM)\s+CUFF", t_limpo)
    if m and numero_valido_tubo(m.group(1)):
        return formatar_medida(m.group(1), "MM"), "MEDIDA_APOS_ENDOTRAQUEAL"

    m = re.search(r"ENDOTRAQUEAL\s+ARAMAD[OA]\s+(\d+(?:[,.]\d+)?)\s+(COM|SEM)\s+CUFF", t_limpo)
    if m and numero_valido_tubo(m.group(1)):
        return formatar_medida(m.group(1), "MM"), "MEDIDA_APOS_ARAMADO"

    m = re.search(r"ENDOTRAQUEAL\s+COM\s+ASPIRACAO\s+(\d+(?:[,.]\d+)?)\s+(COM|SEM)\s+CUFF", t_limpo)
    if m and numero_valido_tubo(m.group(1)):
        return formatar_medida(m.group(1), "MM"), "MEDIDA_APOS_ASPIRACAO"

    m = re.search(r"\b(\d+(?:[,.]\d+)?)\s+(COM|SEM)\s+CUFF\b", t_limpo)
    if m and numero_valido_tubo(m.group(1)):
        return formatar_medida(m.group(1), "MM"), "MEDIDA_ANTES_CUFF"

    medidas = re.findall(r"\b(\d+(?:[,.]\d+)?)\s*MM\b", t_limpo)
    for valor in medidas:
        if numero_valido_tubo(valor):
            return formatar_medida(valor, "MM"), "MEDIDA_MM_FILTRADA"

    return "", "SEM_MEDIDA_SEGURA"


def detectar_familia(desc):
    t = normalizar_descricao(desc)

    if "FIXADOR" in t and "ENDOTRAQUEAL" in t:
        return "FIXADOR TUBO ENDOTRAQUEAL"

    if "SISTEMA DE ASP" in t or "ASP FECHADO" in t or "TRACK CARE" in t:
        return "SISTEMA ASPIRACAO FECHADO"

    if "ENDOTRAQUEAL" in t:
        return "TUBO ENDOTRAQUEAL"

    if "SERINGA" in t:
        return "SERINGA"

    if "AGULHA" in t:
        return "AGULHA HIPODERMICA"

    if "LUVA" in t:
        return "LUVA"

    if "CATETER" in t:
        return "CATETER"

    if "SONDA" in t and "FOLEY" in t:
        return "SONDA FOLEY"

    if "EQUIPO" in t:
        return "EQUIPO"

    return "REVISAR"


def extrair_atributos(desc):
    t = normalizar_descricao(desc)
    familia = detectar_familia(desc)

    attrs = {
        "familia": familia,
        "bloqueios": [],
        "atributos": {},
        "descricao_normalizada": t,
    }

    if familia == "TUBO ENDOTRAQUEAL":
        attrs["atributos"]["aramado"] = "SIM" if ("ARAMADO" in t or "ARAMADA" in t) else "NAO"
        attrs["atributos"]["aspiracao"] = "SIM" if "ASPIRACAO" in t else "NAO"

        tem_com = "COM CUFF" in t
        tem_sem = "SEM CUFF" in t

        if tem_com and tem_sem:
            attrs["bloqueios"].append("CONFLITO_COM_E_SEM_CUFF")
        elif tem_com:
            attrs["atributos"]["cuff"] = "C/CUFF"
        elif tem_sem:
            attrs["atributos"]["cuff"] = "S/CUFF"
        else:
            attrs["bloqueios"].append("NAO_IDENTIFICOU_CUFF")

        medida, origem = extrair_medida_tubo(t)
        if medida:
            attrs["atributos"]["medida"] = medida
            attrs["atributos"]["origem_medida"] = origem
        else:
            attrs["bloqueios"].append("NAO_IDENTIFICOU_MEDIDA")

    return attrs


def gerar_assinatura_tecnica(desc):
    dados = extrair_atributos(desc)
    familia = dados["familia"]
    at = dados["atributos"]

    if familia == "TUBO ENDOTRAQUEAL":
        partes = [
            familia,
            f"cuff={at.get('cuff', '')}",
            f"medida={at.get('medida', '')}",
            f"aramado={at.get('aramado', '')}",
            f"aspiracao={at.get('aspiracao', '')}",
        ]
        return " | ".join(partes)

    return familia


def sugerir_sku_master(desc):
    dados = extrair_atributos(desc)
    familia = dados["familia"]
    at = dados["atributos"]
    bloqueios = dados["bloqueios"]

    if familia == "TUBO ENDOTRAQUEAL":
        if bloqueios:
            return {
                "aplica": "NAO",
                "sku_master": "",
                "familia": familia,
                "assinatura": gerar_assinatura_tecnica(desc),
                "confianca": "BAIXA",
                "motivo": "; ".join(bloqueios),
                "atributos": at,
            }

        prefixo = "TUBO ENDOTRAQUEAL"

        if at.get("aramado") == "SIM":
            prefixo += " ARAMADO"

        if at.get("aspiracao") == "SIM":
            prefixo += " C/ASPIRACAO"

        sku = f"{prefixo} {at['cuff']} {at['medida']}"

        return {
            "aplica": "SIM",
            "sku_master": sku,
            "familia": familia,
            "assinatura": gerar_assinatura_tecnica(desc),
            "confianca": "ALTA",
            "motivo": "REGRA_TECNICA_TUBO_ENDOTRAQUEAL_DICIONARIO_MEDBOX",
            "atributos": at,
        }

    return {
        "aplica": "NAO",
        "sku_master": "",
        "familia": familia,
        "assinatura": gerar_assinatura_tecnica(desc),
        "confianca": "BAIXA",
        "motivo": "FAMILIA_AINDA_NAO_IMPLEMENTADA_NO_MOTOR",
        "atributos": at,
    }
