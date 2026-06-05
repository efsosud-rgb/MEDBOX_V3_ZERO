import re, unicodedata

def norm(t):
    if not t: return ""
    t = str(t).strip()
    t = unicodedata.normalize("NFD", t)
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return t.upper().strip()

STOP = {
    "AP","AMP","AMPOLA","FR","FRASCO","FA","FLACONETE","CP","COMP","TB","TUBO",
    "ENV","CX","UN","UNI","UND","PC","PCT","ML","MG","MCG","UI","EV","IM","IV",
    "GEL","PO","SOL","INJ","BS","SER","LT","BG","SC","GTS","GT","KG","G","GR",
    "ITEM:","LOTE:","LT:","VAL.:","(ITEM:","(ITEM","RISCO","II","III",
    "S/V","S/AG","P/INJ","C/25","C/10","C/5","C/1","C/100","C/50"
}

def lc(p): return re.sub(r'[^A-Z0-9]','',p.upper())

def encontrar_repeticao(palavras):
    """Menor prefixo que se repete exatamente (tokens normalizados)."""
    n = len(palavras)
    pn = [lc(p) for p in palavras]
    for tam in range(2, n//2+2):
        pref = pn[:tam]
        for ini in range(tam, n-tam+1):
            if pn[ini:ini+tam] == pref:
                return tam, ini
    return 0, 0

def chave_conc(p):
    """Chave normalizada de um token de concentração: dígitos + unidade principal."""
    m = re.match(r'^(\d+[\.,]?\d*)(%|MG|ML|MCG|UI|G|VOL).*$', p, re.I)
    if m: return m.group(1).replace(',','.') + m.group(2).upper()
    return None

def corte_conc_dupla(palavras):
    """Corta quando a mesma concentração (dígitos+unidade) aparece pela 2ª vez."""
    vistas = {}
    for i, p in enumerate(palavras):
        c = chave_conc(p)
        if c:
            if c in vistas:
                return vistas[c] + 1
            vistas[c] = i
    return len(palavras)

def limpar(sku_palavras):
    while sku_palavras and (sku_palavras[-1] in STOP or lc(sku_palavras[-1]) in STOP
                            or sku_palavras[-1] in {".","-",",","+","S/V"}):
        sku_palavras.pop()
    while sku_palavras and re.fullmatch(r'[\d,\.]+', sku_palavras[-1]):
        sku_palavras.pop()
    return sku_palavras

def extrair_sku(descricao: str) -> str:
    d = norm(descricao)
    if not d: return ""
    palavras = d.split()
    n = len(palavras)

    tam_rep, ini_rep = encontrar_repeticao(palavras)
    corte_cc = corte_conc_dupla(palavras)

    if tam_rep >= 2:
        # Repetição textual encontrada — método mais confiável
        candidatos = [p for p in palavras[:ini_rep] if p not in STOP and lc(p) not in STOP and p != "-"]
        if len(candidatos) >= 2:
            sku_palavras = candidatos
        else:
            sku_palavras = list(palavras[:tam_rep])

    elif corte_cc < n:
        # Concentração dupla: corte secundário
        sku_palavras = list(palavras[:corte_cc])

    else:
        # Sem padrão detectável: avança token a token
        sku_palavras = []
        for i, p in enumerate(palavras):
            if i < 2: sku_palavras.append(p); continue
            if p in STOP or lc(p) in STOP: break
            if p in {"-"} and i > 2: break
            if re.match(r'^[CSP]/$', p): break
            if p.startswith("(") and ("ITEM" in p or "LOTE" in p): break
            tem_num = any(re.search(r'\d', x) for x in sku_palavras)
            if tem_num and p.isalpha() and len(p) > 4 and i >= 3: break
            sku_palavras.append(p)
            if len(sku_palavras) >= 7: break

    sku_palavras = limpar(sku_palavras)
    sku = " ".join(sku_palavras).strip().rstrip(".,")
    sku = re.sub(r'\s*\([^)]*$','', sku).strip()
    return sku if len(sku) >= 3 else (palavras[0] if palavras else "")