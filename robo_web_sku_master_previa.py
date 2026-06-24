import sqlite3
import re
import csv
import time
import urllib.parse
from pathlib import Path
from collections import Counter
import requests
from bs4 import BeautifulSoup

DB = Path("banco/medbox_v3.db")
CSV = Path("previa_robo_web_sku_master.csv")
TXT = Path("relatorio_robo_web_sku_master.txt")

# Para teste inicial, começa pequeno.
# Depois aumentamos para 200, 500, 1000 etc.
LIMITE_PRODUTOS = 30

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"
}

def norm(txt):
    txt = str(txt or "").upper().strip()
    mapa = {
        "Á":"A","À":"A","Ã":"A","Â":"A",
        "É":"E","Ê":"E",
        "Í":"I",
        "Ó":"O","Ô":"O","Õ":"O",
        "Ú":"U",
        "Ç":"C",
    }
    for a,b in mapa.items():
        txt = txt.replace(a,b)

    substit = {
        "ENDOTRAQUEAL": "OROTRAQUEAL",
        "ORO TRAQUEAL": "OROTRAQUEAL",
        "ORO-TRAQUEAL": "OROTRAQUEAL",
        "C/": "COM ",
        "S/": "SEM ",
        "POLIVINIL": "PVC",
        "POLI VINIL": "PVC",
        "CLORETO DE POLIVINILA": "PVC",
        "N°": "N ",
        "Nº": "N ",
        "NUMERO": "N ",
        "COMPRIMIDO": "COMP",
        "COMPRIMIDOS": "COMP",
        "CAPSULA": "CAPS",
        "CAPSULAS": "CAPS",
        "SOLUCAO": "SOL",
        "INJETAVEL": "INJ",
        "FRASCO AMPOLA": "FR AMP",
        "AMPOLA": "AMP",
        "FRASCO": "FR",
    }

    for a,b in substit.items():
        txt = txt.replace(a,b)

    txt = txt.replace("\\", "/")
    txt = re.sub(r"[^A-Z0-9%/,.\-+ X]+", " ", txt)
    txt = re.sub(r"\s+", " ", txt).strip()
    return txt

def add_unico(lista, valor):
    valor = str(valor or "").upper().strip()
    valor = valor.replace(".", ",")
    valor = re.sub(r"\s+", "", valor)
    if valor and valor not in lista:
        lista.append(valor)

def extrair_specs(txt):
    t = norm(txt)
    specs = []

    if "COM BALAO" in t:
        add_unico(specs, "C/BALAO")
    if "SEM BALAO" in t:
        add_unico(specs, "S/BALAO")

    for termo in ["PVC", "LATEX", "SILICONE", "POLIURETANO"]:
        if termo in t:
            add_unico(specs, termo)

    if "2 VIAS" in t or "DUAS VIAS" in t:
        add_unico(specs, "2 VIAS")
    if "3 VIAS" in t or "TRES VIAS" in t:
        add_unico(specs, "3 VIAS")

    for termo in [
        "AZUL","PRETO","VERDE","ROSA","BRANCO",
        "OPACO","TRANSPARENTE","DRENAVEL",
        "ESTERIL","NAO ESTERIL"
    ]:
        if termo in t:
            add_unico(specs, termo)

    for m in re.findall(r"\b\d+(?:[,.]\d+)?\s*(?:MG/ML|MG|MCG|G|ML|L|UI|U|CM|MM|M|FR)\b", t):
        add_unico(specs, m)

    for m in re.findall(r"\b\d+(?:[,.]\d+)?\s*X\s*\d+(?:[,.]\d+)?(?:\s*(?:MM|CM|M))?\b", t):
        add_unico(specs, m)

    for m in re.findall(r"\bN\s*\d+(?:[,.]\d+)?\b", t):
        numero = m.replace("N", "").strip()
        add_unico(specs, numero + "MM")

    return specs

def base_produto(txt):
    t = norm(txt)

    if ("TUBO" in t or "CANULA" in t) and "OROTRAQUEAL" in t:
        return "TUBO ENDOTRAQUEAL"

    if "CANULA" in t and "TRAQUEOSTOMIA" in t:
        return "CANULA TRAQUEOSTOMIA"

    if "SONDA" in t and ("FOLEY" in t or "FOLLEY" in t):
        return "SONDA FOLEY"

    if "CATETER" in t and "VENOSO" in t and "PERIFERICO" in t:
        return "CATETER VENOSO PERIFERICO"

    if "CATETER" in t and "VENOSO" in t and "CENTRAL" in t:
        return "CATETER VENOSO CENTRAL"

    if "AGULHA" in t and "HIPODERMICA" in t:
        return "AGULHA HIPODERMICA"

    if "CLORETO" in t and "SODIO" in t:
        return "CLORETO DE SODIO"

    if "ENOXAPARINA" in t:
        return "ENOXAPARINA SODICA"

    if "DIPIRONA" in t:
        return "DIPIRONA SODICA"

    remover = [
        "ADULTO","INFANTIL","PEDIATRICO","GENERICO","MARCA",
        "IMPORTADO","MANIPULADO","VIA ORAL","VIA INTRAVENOSA",
        "VIA INTRAMUSCULAR","USO HOSPITALAR","DESCARTAVEL",
        "REF","REFERENCIA","COM BALAO","SEM BALAO",
        "PVC","LATEX","SILICONE","POLIURETANO",
        "2 VIAS","3 VIAS","DUAS VIAS","TRES VIAS",
        "AZUL","PRETO","VERDE","ROSA","BRANCO",
        "OPACO","TRANSPARENTE","DRENAVEL","ESTERIL","NAO ESTERIL"
    ]

    for r in remover:
        t = t.replace(r, " ")

    t = re.sub(r"\b\d+(?:[,.]\d+)?\s*(?:MG/ML|MG|MCG|G|ML|L|UI|U|CM|MM|M|FR)\b", " ", t)
    t = re.sub(r"\b\d+(?:[,.]\d+)?\s*X\s*\d+(?:[,.]\d+)?(?:\s*(?:MM|CM|M))?\b", " ", t)
    t = re.sub(r"\bN\s*\d+(?:[,.]\d+)?\b", " ", t)
    t = re.sub(r"\bREF\.?\s*[:\-]?\s*[A-Z0-9/\-.]+", " ", t)

    ignorar = {
        "DE","DA","DO","DAS","DOS","PARA","POR","COM","SEM",
        "EM","E","A","O","AS","OS","UN","UND","UNIDADE"
    }

    palavras = [p for p in t.split() if p not in ignorar and len(p) > 1]
    return " ".join(palavras[:6]).strip()

def categoria_sugerida(txt, base):
    t = norm(txt + " " + base)

    correlatos = [
        "TUBO","SONDA","CANULA","AGULHA","CATETER","BOLSA","PLACA",
        "CURATIVO","COLETOR","MASCARA","FIO DE SUTURA","CAMPO",
        "LUVA","SERINGA","EQUIPO","COMPRESSA","GAZE"
    ]

    medicamentos = [
        "DIPIRONA","ENOXAPARINA","CLORETO DE SODIO","AMOXICILINA",
        "MIDAZOLAM","OLANZAPINA","CANABIDIOL","MG","MCG","UI",
        "COMP","CAPS","SOL INJ","AMP","FR AMP"
    ]

    if any(x in t for x in correlatos):
        return "CORRELATOS"

    if any(x in t for x in medicamentos):
        return "MEDICAMENTOS"

    return ""

def gerar_consulta(descricao):
    t = norm(descricao)

    consulta = t

    consulta = consulta.replace("POLIVINIL", "PVC")
    consulta = consulta.replace("OROTRAQUEAL", "ENDOTRAQUEAL")
    consulta = consulta.replace("COM BALAO", "COM BALÃO")
    consulta = consulta.replace("SEM BALAO", "SEM BALÃO")

    termos = consulta.split()

    # Evita consultas gigantes
    consulta = " ".join(termos[:12])

    return consulta + " produto hospitalar"

def buscar_web(consulta):
    url = "https://duckduckgo.com/html/?" + urllib.parse.urlencode({"q": consulta})
    resultados = []

    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
    except Exception as e:
        return [], f"ERRO_WEB: {e}"

    soup = BeautifulSoup(resp.text, "html.parser")

    for r in soup.select(".result"):
        titulo_el = r.select_one(".result__title")
        snippet_el = r.select_one(".result__snippet")
        link_el = r.select_one(".result__a")

        titulo = titulo_el.get_text(" ", strip=True) if titulo_el else ""
        snippet = snippet_el.get_text(" ", strip=True) if snippet_el else ""
        link = link_el.get("href", "") if link_el else ""

        texto = f"{titulo} {snippet}".strip()

        if texto:
            resultados.append({
                "titulo": titulo,
                "snippet": snippet,
                "link": link,
                "texto": texto,
            })

        if len(resultados) >= 8:
            break

    return resultados, ""

def gerar_sku_padrao(descricao_original, textos_web):
    evidencia = " ".join(textos_web[:5])
    combinado = descricao_original + " " + evidencia

    base = base_produto(combinado)
    specs_original = extrair_specs(descricao_original)
    specs_web = extrair_specs(evidencia)

    specs_finais = []

    # Especificações da descrição original mandam.
    for s in specs_original:
        add_unico(specs_finais, s)

    # A web só complementa material/tipo quando não conflita.
    for s in specs_web:
        if s in ["PVC", "LATEX", "SILICONE", "POLIURETANO", "C/BALAO", "S/BALAO", "2 VIAS", "3 VIAS"]:
            add_unico(specs_finais, s)

    if not base:
        return "", "", [], "BAIXA", "SEM_BASE_PRODUTO"

    partes = [base]
    for s in specs_finais:
        if s not in partes:
            partes.append(s)

    sku = " ".join(partes)
    sku = norm(sku)
    sku = sku.replace("COM BALAO", "C/BALAO").replace("SEM BALAO", "S/BALAO")
    sku = re.sub(r"\s+", " ", sku).strip()

    categoria = categoria_sugerida(combinado, base)

    confianca = "MEDIA"
    motivo = "BASE_GERADA_COM_APOIO_WEB"

    if base and specs_original:
        confianca = "ALTA"
        motivo = "BASE_E_ESPECIFICACOES_ORIGINAIS_CONFIRMADAS"

    if "SKU PENDENTE" in norm(descricao_original):
        confianca = "BAIXA"
        motivo = "ORIGEM_OCR_OU_SKU_PENDENTE"

    return sku, categoria, specs_finais, confianca, motivo

def marca_possivel(textos_web):
    marcas = [
        "MEDIX", "SOLIDOR", "COMPER", "HAIBREATH", "COVIDIEN", "MEDTRONIC",
        "PORTEX", "SHILEY", "ADVANTIVE", "VITALGOLD", "HOLLISTER",
        "CONVATEC", "BD", "DESCARPACK", "SR", "LABOR IMPORT"
    ]

    texto = norm(" ".join(textos_web))

    achadas = []
    for m in marcas:
        if m in texto:
            achadas.append(m)

    return ", ".join(achadas[:3])

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

rows = cur.execute("""
    SELECT id, sku, produto_padrao, sku_master, fabricante, categoria, ativo
    FROM produtos
    WHERE ativo = 1
      AND (
            sku_master IS NULL
            OR TRIM(sku_master) = ''
            OR UPPER(TRIM(sku_master)) LIKE 'SKU PENDENTE%'
            OR UPPER(TRIM(sku_master)) = UPPER(TRIM(produto_padrao))
      )
    ORDER BY id DESC
    LIMIT ?
""", (LIMITE_PRODUTOS,)).fetchall()

saida = []
cont = Counter()

for idx, r in enumerate(rows, start=1):
    descricao = str(r["produto_padrao"] or r["sku"] or "").strip()
    consulta = gerar_consulta(descricao)

    print(f"[{idx}/{len(rows)}] Pesquisando: {descricao}")
    print(f"Consulta: {consulta}")

    resultados, erro = buscar_web(consulta)

    textos = [x["texto"] for x in resultados]
    sku, categoria, specs, confianca, motivo = gerar_sku_padrao(descricao, textos)

    marca = marca_possivel(textos)

    cont[confianca] += 1

    evidencia_curta = " || ".join([
        f"{x['titulo']} - {x['snippet']}"[:350]
        for x in resultados[:3]
    ])

    saida.append({
        "id": r["id"],
        "descricao_atual": descricao,
        "consulta_web": consulta,
        "sku_master_atual": r["sku_master"] or "",
        "sku_master_sugerido": sku,
        "categoria_atual": r["categoria"] or "",
        "categoria_sugerida": categoria,
        "fabricante_atual": r["fabricante"] or "",
        "fabricante_marca_web": marca,
        "confianca": confianca,
        "motivo": motivo,
        "specs": ", ".join(specs),
        "erro_web": erro,
        "evidencia": evidencia_curta,
        "aplicar_automaticamente": "SIM" if confianca == "ALTA" else "NAO",
    })

    time.sleep(2)

with CSV.open("w", newline="", encoding="utf-8-sig") as f:
    campos = [
        "id",
        "descricao_atual",
        "consulta_web",
        "sku_master_atual",
        "sku_master_sugerido",
        "categoria_atual",
        "categoria_sugerida",
        "fabricante_atual",
        "fabricante_marca_web",
        "confianca",
        "motivo",
        "specs",
        "erro_web",
        "evidencia",
        "aplicar_automaticamente",
    ]
    w = csv.DictWriter(f, fieldnames=campos, delimiter=";")
    w.writeheader()
    w.writerows(saida)

linhas = []
linhas.append("===== ROBÔ WEB SKU_MASTER MEDBOX - PRÉVIA =====")
linhas.append("")
linhas.append(f"Produtos pesquisados: {len(rows)}")
linhas.append(f"ALTA confiança: {cont['ALTA']}")
linhas.append(f"MÉDIA confiança: {cont['MEDIA']}")
linhas.append(f"BAIXA confiança: {cont['BAIXA']}")
linhas.append("")
linhas.append(f"CSV gerado: {CSV.resolve()}")
linhas.append("")
linhas.append("Banco NÃO foi alterado.")
linhas.append("Esta etapa apenas pesquisa na internet e gera sugestões.")

TXT.write_text("\n".join(linhas), encoding="utf-8")

conn.close()

print("")
print("Relatório gerado:", TXT.resolve())
print("CSV gerado:", CSV.resolve())
print("Abra com:")
print("notepad relatorio_robo_web_sku_master.txt")
print("start excel previa_robo_web_sku_master.csv")
