import re
from core.banco import conectar

def extrair_marca_da_descricao(descricao):
    """
    Extrai a marca da descrição do produto.
    Regra: a marca geralmente é a última palavra antes de (MATRIZ GO),
    ou a última palavra significativa após a unidade de medida.
    """
    descricao = descricao.upper().strip()

    # Remove sufixos de localização
    descricao_limpa = re.sub(r'\(MATRIZ\s*GO\)', '', descricao).strip()
    descricao_limpa = re.sub(r'\(.*?\)', '', descricao_limpa).strip()

    # Unidades comuns — a marca vem depois delas
    unidades = r'\b(ENV|UN|UNI|CX|FR|PC|KIT|AMP|BIS|SC|RL|MT|KG|GR|ML|L|TB|BX|AP|EV|CP|FA|UNI)\b'

    # Tenta pegar o que vem após a última unidade
    partes = re.split(unidades, descricao_limpa)

    if len(partes) >= 3:
        # Pega tudo após a última unidade
        resto = partes[-1].strip()
        if resto:
            # Pega as palavras do resto
            palavras = [p for p in resto.split() if len(p) > 1]
            if palavras:
                # Remove palavras que são claramente não-marca
                ignorar = {'BC', 'S/AG', 'FIOS', 'CM', 'MM', 'AG', 'CIL', 'CORT',
                          'ALTA', 'PERFORMACE', 'PRETO', 'INCOLOR', 'VIOLETA',
                          'ABSORVIVEL', 'CUTICULAR', 'LACADO', 'LACADO', 'LAÇADO',
                          'AMIDALECTOMIA', 'PLASTICA', 'FARPADO', 'BIDIRECIONAL',
                          'UNIDIRECIONAL', 'CROMADO', 'SIMPLES', 'AZUL', 'MARROM',
                          '910', '300', 'SERIE', 'RETA', 'ESPAT', 'ESP'}
                palavras_validas = [p for p in palavras if p not in ignorar and not p.replace('.','').replace(',','').isdigit()]
                if palavras_validas:
                    # Junta palavras que formam marcas compostas (ex: BC SUTURE, VIC PHARMA)
                    if len(palavras_validas) >= 2:
                        marca_composta = ' '.join(palavras_validas[:2])
                        marcas_compostas_conhecidas = [
                            'BC SUTURE', 'VIC PHARMA', 'UNIAO QUIMICA', 'GREEN MED',
                            'NOVA LINEA', 'LABOR IMPORT', 'SOL CARE', 'MK LIFE',
                            'SALDANHA RODRIGUES'
                        ]
                        for mc in marcas_compostas_conhecidas:
                            if mc in descricao_limpa:
                                return mc
                    return palavras_validas[0]

    # Fallback: tenta encontrar marca conhecida na descrição
    marcas_conhecidas = [
        "BIOLINE", "EMS", "FRESENIUS", "BLAU", "TEUTO", "GEOLAB", "HIPOLABOR",
        "HYPOFARMA", "EQUIPLEX", "VIC PHARMA", "MAYBEN", "NATULAB", "HALEXISTAR",
        "RIOQUIMICA", "DESCARPACK", "BC SUTURE", "BIOCLOSE", "BIOPDO",
        "FARMARIN", "UNIAO QUIMICA", "GTS", "TROL", "THEOTO", "SOLIDOR",
        "WILTEX", "MEDIX", "INJEX", "LABOR IMPORT", "PROCARE", "MK LIFE",
        "SALDANHA RODRIGUES", "NOVA LINEA"
    ]
    for marca in marcas_conhecidas:
        if marca in descricao:
            return marca

    return "DESCONHECIDA"


def corrigir_marcas_distribuidor():
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT pf.id, pf.descricao_original, pf.marca, f.nome AS fornecedor, f.tipo
        FROM precos_fornecedores pf
        JOIN fornecedores f ON f.id = pf.fornecedor_id
        WHERE UPPER(f.tipo) = 'DISTRIBUIDOR'
    """)
    rows = cursor.fetchall()

    print(f"Total de itens de distribuidores: {len(rows)}")
    corrigidos = 0

    for row in rows:
        nova_marca = extrair_marca_da_descricao(row["descricao_original"])

        if nova_marca != (row["marca"] or ""):
            cursor.execute("""
                UPDATE precos_fornecedores SET marca = ? WHERE id = ?
            """, (nova_marca, row["id"]))
            corrigidos += 1
            print(f"  {row['descricao_original'][:60]:<60} → {nova_marca}")

    conn.commit()
    conn.close()
    print(f"\nConcluído! {corrigidos} marcas corrigidas.")


if __name__ == "__main__":
    corrigir_marcas_distribuidor()