def moeda_br(valor):
    if valor is None:
        return "-"

    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return "-"

    texto = f"R$ {numero:,.2f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")
