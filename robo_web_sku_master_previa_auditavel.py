import csv
import hashlib
import json
import re
import sqlite3
import time
import urllib.parse
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

DB = Path("banco/medbox_v3.db")

PASTA_EVIDENCIAS = Path("evidencias_robo_web_sku_master")
PASTA_EVIDENCIAS.mkdir(exist_ok=True)

CSV = Path("previa_robo_web_sku_master_AUDITAVEL.csv")
TXT = Path("relatorio_robo_web_sku_master_AUDITAVEL.txt")

# Começa pequeno para validar. Depois aumentamos.
LIMITE_PRODUTOS = 10

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"
}

def agora():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def sha256_arquivo(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for bloco in iter(lambda: f.read(1024 * 1024), b""):
            h.update(bloco)
    return h.hexdigest()

def salvar_texto(path, texto):
    path.write_text(str(texto or ""), encoding="utf-8", errors="ignore")
    return {
        "arquivo": str(path),
        "existe": path.exists(),
        "bytes": path.stat().st_size if path.exists() else 0,
        "sha256": sha256_arquivo(path) if path.exists() and path.stat().st_size > 0 else "",
    }

def norm(txt):
    txt = str(txt or "").upper().strip()

    mapa = {
        "Á": "A", "À": "A", "Ã": "A", "Â": "A",
        "É": "E", "Ê": "E",
        "Í": "I",
        "Ó": "O", "Ô": "O", "Õ": "O",
        "Ú": "U",
        "Ç": "C",
    }

    for a, b in mapa.items():
        txt = txt.replace(a, b)

    substit = {
        "ENDOTRAQUEAL": "OROTRAQUEAL",
        "ORO TRAQUEAL": "OROTRAQUEAL",
        "ORO-TRAQUEAL": "OROTRAQUEAL",
        "C/": "COM ",
        "S/": "SEM ",
        "POLIVINIL": "PVC",
        "POLI VINIL": "PVC",
        "CLORETO DE POLIVINILA": "PVC",
        "BALONETE": "BALAO",
        "CUFF": "BALAO",
        "N°": "N ",
        "Nº": "N ",
        "NUMERO": "N ",
    }

    for a, b in substit.items():
        txt = txt.replace(a, b)

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

def extrair_specs_criticas(txt):
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
        "AZUL", "PRETO", "VERDE", "ROSA", "BRANCO",
        "OPACO", "TRANSPARENTE", "DRENAVEL",
        "ESTERIL", "NAO ESTERIL"
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

def spec_confirmada(spec, texto_evidencia):
    ev = norm(texto_evidencia)
    s = norm(spec).replace(" ", "")

    # Equivalências técnicas aceitas apenas para confirmação textual.
    if s == "C/BALAO":
        return any(x in ev for x in ["COM BALAO", "C BALAO", "BALAO", "BALONETE", "CUFF"])

    if s == "S/BALAO":
        return any(x in ev for x in ["SEM BALAO", "S BALAO", "SEM BALONETE", "SEM CUFF"])

    if s == "PVC":
        return any(x in ev for x in ["PVC", "POLIVINIL", "POLI VINIL", "CLORETO DE POLIVINILA"])

    return s in ev.replace(" ", "").replace(".", ",")

def base_produto(txt):
    t = norm(txt)

    if ("TUBO" in t or "CANULA" in t) and "OROTRAQUEAL" in t:
        return "TUBO ENDOTRAQUEAL"

    if "CANULA" in t and "TRAQUEOSTOMIA" in t:
        return "CANULA TRAQUEOSTOMIA"

    if "SONDA" in t and ("FOLEY" in t or "FOLLEY" in t):
        return "SONDA FOLEY"

    if "SONDA" in t and "ASPIRACAO" in t and "TRAQUEAL" in t:
        return "SONDA ASPIRACAO TRAQUEAL"

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

    return ""

def categoria_sugerida(descricao, base):
    t = norm(descricao + " " + base)

    correlatos = [
        "TUBO", "SONDA", "CANULA", "AGULHA", "CATETER", "BOLSA", "PLACA",
        "CURATIVO", "COLETOR", "MASCARA", "FIO DE SUTURA", "CAMPO",
        "LUVA", "SERINGA", "EQUIPO", "COMPRESSA", "GAZE"
    ]

    medicamentos = [
        "DIPIRONA", "ENOXAPARINA", "CLORETO DE SODIO", "AMOXICILINA",
        "MIDAZOLAM", "OLANZAPINA", "CANABIDIOL", "MG", "MCG", "UI",
        "COMP", "CAPS", "SOL INJ", "AMP", "FR AMP"
    ]

    if any(x in t for x in correlatos):
        return "CORRELATOS"

    if any(x in t for x in medicamentos):
        return "MEDICAMENTOS"

    return ""

def gerar_sku_padrao(descricao):
    base = base_produto(descricao)
    specs = extrair_specs_criticas(descricao)

    if not base:
        return "", "", specs

    partes = [base]

    for s in specs:
        if s not in partes:
            partes.append(s)

    sku = " ".join(partes)
    sku = norm(sku)
    sku = sku.replace("COM BALAO", "C/BALAO").replace("SEM BALAO", "S/BALAO")
    sku = re.sub(r"\s+", " ", sku).strip()

    return sku, categoria_sugerida(descricao, base), specs

def gerar_consulta(descricao):
    t = norm(descricao)
    t = t.replace("OROTRAQUEAL", "ENDOTRAQUEAL")
    t = t.replace("COM BALAO", "COM BALÃO")
    t = t.replace("SEM BALAO", "SEM BALÃO")
    termos = t.split()
    return " ".join(termos[:14]) + " produto hospitalar"

def decodificar_url_duckduckgo(url):
    if not url:
        return ""

    try:
        parsed = urllib.parse.urlparse(url)
        qs = urllib.parse.parse_qs(parsed.query)
        if "uddg" in qs and qs["uddg"]:
            return qs["uddg"][0]
    except Exception:
        pass

    return url

def buscar_duckduckgo(consulta, prefixo):
    url = "https://duckduckgo.com/html/?" + urllib.parse.urlencode({"q": consulta})

    info = {
        "url_busca": url,
        "status_http_busca": "",
        "erro_busca": "",
        "arquivo_html_busca": "",
        "sha256_html_busca": "",
        "resultados": [],
    }

    try:
        resp = requests.get(url, headers=HEADERS, timeout=25)
        info["status_http_busca"] = str(resp.status_code)

        html_path = PASTA_EVIDENCIAS / f"{prefixo}_busca.html"
        meta_html = salvar_texto(html_path, resp.text)

        info["arquivo_html_busca"] = meta_html["arquivo"]
        info["sha256_html_busca"] = meta_html["sha256"]

        if resp.status_code != 200:
            info["erro_busca"] = f"HTTP_{resp.status_code}"
            return info

        soup = BeautifulSoup(resp.text, "html.parser")

        for idx, r in enumerate(soup.select(".result"), start=1):
            titulo_el = r.select_one(".result__title")
            snippet_el = r.select_one(".result__snippet")
            link_el = r.select_one(".result__a")

            titulo = titulo_el.get_text(" ", strip=True) if titulo_el else ""
            snippet = snippet_el.get_text(" ", strip=True) if snippet_el else ""
            link = link_el.get("href", "") if link_el else ""
            link_real = decodificar_url_duckduckgo(link)

            if not titulo and not snippet:
                continue

            info["resultados"].append({
                "posicao": idx,
                "titulo": titulo,
                "snippet": snippet,
                "url": link_real,
            })

            if len(info["resultados"]) >= 8:
                break

        json_path = PASTA_EVIDENCIAS / f"{prefixo}_resultados.json"
        meta_json = salvar_texto(json_path, json.dumps(info, ensure_ascii=False, indent=2))

        info["arquivo_json_resultados"] = meta_json["arquivo"]
        info["sha256_json_resultados"] = meta_json["sha256"]

        return info

    except Exception as e:
        info["erro_busca"] = str(e)
        return info

def montar_evidencia_textual(info):
    partes = []

    for r in info.get("resultados", []):
        partes.append(str(r.get("titulo") or ""))
        partes.append(str(r.get("snippet") or ""))
        partes.append(str(r.get("url") or ""))

    return "\n".join(partes)

def avaliar_confianca(descricao, evidencia_texto, info_busca):
    sku, categoria, specs = gerar_sku_padrao(descricao)
    base = base_produto(descricao)

    motivos = []
    termos_confirmados = []
    termos_nao_confirmados = []

    if not info_busca.get("arquivo_html_busca"):
        return "BAIXA", "SEM_ARQUIVO_EVIDENCIA", sku, categoria, specs, "", ""

    if info_busca.get("status_http_busca") != "200":
        return "BAIXA", "HTTP_NAO_200", sku, categoria, specs, "", ""

    if not info_busca.get("resultados"):
        return "BAIXA", "SEM_RESULTADOS", sku, categoria, specs, "", ""

    if not sku:
        return "BAIXA", "SEM_SKU_GERADO", sku, categoria, specs, "", ""

    ev_norm = norm(evidencia_texto)
    base_norm = norm(base)

    base_ok = False

    if base_norm == "TUBO ENDOTRAQUEAL":
        base_ok = any(x in ev_norm for x in ["TUBO ENDOTRAQUEAL", "TUBO OROTRAQUEAL", "CANULA ENDOTRAQUEAL", "CANULA OROTRAQUEAL"])
    else:
        base_ok = base_norm and base_norm in ev_norm

    if base_ok:
        motivos.append("BASE_CONFIRMADA")
    else:
        motivos.append("BASE_NAO_CONFIRMADA")

    for s in specs:
        if spec_confirmada(s, evidencia_texto):
            termos_confirmados.append(s)
        else:
            termos_nao_confirmados.append(s)

    # Regra rígida:
    # ALTA só se base confirmada + todas specs críticas confirmadas + evidência real.
    if base_ok and specs and not termos_nao_confirmados:
        return (
            "ALTA",
            "BASE_E_TODAS_ESPECIFICACOES_CONFIRMADAS_COM_EVIDENCIA",
            sku,
            categoria,
            specs,
            ", ".join(termos_confirmados),
            ", ".join(termos_nao_confirmados),
        )

    if base_ok:
        return (
            "MEDIA",
            "BASE_CONFIRMADA_MAS_ESPECIFICACOES_INCOMPLETAS",
            sku,
            categoria,
            specs,
            ", ".join(termos_confirmados),
            ", ".join(termos_nao_confirmados),
        )

    return (
        "BAIXA",
        "SEM_CONFIRMACAO_SUFICIENTE_NA_EVIDENCIA",
        sku,
        categoria,
        specs,
        ", ".join(termos_confirmados),
        ", ".join(termos_nao_confirmados),
    )

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

cont = {
    "pesquisados": 0,
    "http_200": 0,
    "com_resultados": 0,
    "evidencias_html": 0,
    "alta": 0,
    "media": 0,
    "baixa": 0,
    "falhas": 0,
}

for idx, r in enumerate(rows, start=1):
    produto_id = r["id"]
    descricao = str(r["produto_padrao"] or r["sku"] or "").strip()
    consulta = gerar_consulta(descricao)
    prefixo = f"produto_{idx:04d}_id_{produto_id}"

    print(f"[{idx}/{len(rows)}] ID {produto_id} | {descricao}")
    print(f"Consulta: {consulta}")

    cont["pesquisados"] += 1

    info = buscar_duckduckgo(consulta, prefixo)

    if info.get("status_http_busca") == "200":
        cont["http_200"] += 1

    if info.get("resultados"):
        cont["com_resultados"] += 1

    if info.get("arquivo_html_busca") and Path(info["arquivo_html_busca"]).exists():
        cont["evidencias_html"] += 1

    evidencia_texto = montar_evidencia_textual(info)

    txt_path = PASTA_EVIDENCIAS / f"{prefixo}_evidencia.txt"
    meta_txt = salvar_texto(txt_path, evidencia_texto)

    confianca, motivo, sku, categoria, specs, termos_ok, termos_faltando = avaliar_confianca(
        descricao,
        evidencia_texto,
        info,
    )

    if confianca == "ALTA":
        cont["alta"] += 1
    elif confianca == "MEDIA":
        cont["media"] += 1
    else:
        cont["baixa"] += 1

    if info.get("erro_busca"):
        cont["falhas"] += 1

    primeira_url = ""
    primeiro_titulo = ""
    primeiro_trecho = ""

    if info.get("resultados"):
        primeira_url = info["resultados"][0].get("url", "")
        primeiro_titulo = info["resultados"][0].get("titulo", "")
        primeiro_trecho = info["resultados"][0].get("snippet", "")

    saida.append({
        "id": produto_id,
        "descricao_atual": descricao,
        "consulta_web": consulta,
        "sku_master_atual": r["sku_master"] or "",
        "sku_master_sugerido": sku,
        "categoria_atual": r["categoria"] or "",
        "categoria_sugerida": categoria,
        "fabricante_atual": r["fabricante"] or "",
        "confianca": confianca,
        "motivo": motivo,
        "specs_origem": ", ".join(specs),
        "termos_confirmados_na_evidencia": termos_ok,
        "termos_nao_confirmados_na_evidencia": termos_faltando,
        "url_busca": info.get("url_busca", ""),
        "status_http_busca": info.get("status_http_busca", ""),
        "erro_busca": info.get("erro_busca", ""),
        "primeira_url_fonte": primeira_url,
        "primeiro_titulo": primeiro_titulo,
        "primeiro_trecho": primeiro_trecho,
        "arquivo_html_busca": info.get("arquivo_html_busca", ""),
        "sha256_html_busca": info.get("sha256_html_busca", ""),
        "arquivo_json_resultados": info.get("arquivo_json_resultados", ""),
        "sha256_json_resultados": info.get("sha256_json_resultados", ""),
        "arquivo_txt_evidencia": meta_txt["arquivo"],
        "sha256_txt_evidencia": meta_txt["sha256"],
        "aplicar_automaticamente": "NAO",
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
        "confianca",
        "motivo",
        "specs_origem",
        "termos_confirmados_na_evidencia",
        "termos_nao_confirmados_na_evidencia",
        "url_busca",
        "status_http_busca",
        "erro_busca",
        "primeira_url_fonte",
        "primeiro_titulo",
        "primeiro_trecho",
        "arquivo_html_busca",
        "sha256_html_busca",
        "arquivo_json_resultados",
        "sha256_json_resultados",
        "arquivo_txt_evidencia",
        "sha256_txt_evidencia",
        "aplicar_automaticamente",
    ]

    w = csv.DictWriter(f, fieldnames=campos, delimiter=";")
    w.writeheader()
    w.writerows(saida)

csv_existe = CSV.exists()
csv_bytes = CSV.stat().st_size if csv_existe else 0
linhas_csv = len(saida)

veredito = "OK_PREVIA_AUDITAVEL"

if linhas_csv == 0:
    veredito = "FALHOU_CSV_SEM_LINHAS"

if cont["evidencias_html"] == 0:
    veredito = "FALHOU_SEM_EVIDENCIAS_HTML"

if cont["alta"] > 0:
    # Alta só é aceitável se cada alta tiver arquivo de evidência e termos confirmados.
    for row in saida:
        if row["confianca"] == "ALTA":
            if not row["arquivo_html_busca"] or not row["sha256_html_busca"]:
                veredito = "REPROVADO_ALTA_SEM_EVIDENCIA"
            if row["termos_nao_confirmados_na_evidencia"]:
                veredito = "REPROVADO_ALTA_COM_TERMO_NAO_CONFIRMADO"

linhas = []
linhas.append("===== ROBÔ WEB SKU_MASTER MEDBOX - PRÉVIA AUDITÁVEL =====")
linhas.append("")
linhas.append(f"Data/hora: {agora()}")
linhas.append(f"Produtos pesquisados: {cont['pesquisados']}")
linhas.append(f"HTTP 200: {cont['http_200']}")
linhas.append(f"Com resultados: {cont['com_resultados']}")
linhas.append(f"Evidências HTML salvas: {cont['evidencias_html']}")
linhas.append(f"Falhas/erros de busca: {cont['falhas']}")
linhas.append("")
linhas.append(f"ALTA confiança: {cont['alta']}")
linhas.append(f"MÉDIA confiança: {cont['media']}")
linhas.append(f"BAIXA confiança: {cont['baixa']}")
linhas.append("")
linhas.append(f"CSV existe: {'SIM' if csv_existe else 'NAO'}")
linhas.append(f"Tamanho CSV bytes: {csv_bytes}")
linhas.append(f"Linhas CSV: {linhas_csv}")
linhas.append(f"Pasta evidências: {PASTA_EVIDENCIAS.resolve()}")
linhas.append("")
linhas.append("Banco alterado: NÃO")
linhas.append("Aplicação automática: NÃO")
linhas.append("")
linhas.append(f"VEREDITO: {veredito}")

TXT.write_text("\n".join(linhas), encoding="utf-8")

conn.close()

print("")
print("Relatório gerado:", TXT.resolve())
print("CSV gerado:", CSV.resolve())
print("Pasta evidências:", PASTA_EVIDENCIAS.resolve())
print("Abra com:")
print("notepad relatorio_robo_web_sku_master_AUDITAVEL.txt")
print("start excel previa_robo_web_sku_master_AUDITAVEL.csv")
