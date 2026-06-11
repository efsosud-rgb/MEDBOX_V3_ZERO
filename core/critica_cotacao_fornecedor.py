import json
from collections import defaultdict

from core.busca_inteligente import buscar_produto_inteligente


STATUS_COM_PRECO = "com_preco"
STATUS_SKU_SEM_PRECO = "sku_sem_preco"
STATUS_SEM_MATCH = "sem_match_confiavel"


def selecionar_melhor_candidato(candidatos, score_minimo=70):
    for candidato in candidatos or []:
        if (candidato.get("score_busca") or 0) >= score_minimo:
            return candidato
    return None


def extrair_ofertas_do_candidato(candidato):
    if not candidato:
        return []

    ofertas = []
    for preco in candidato.get("precos") or []:
        fornecedor = preco.get("fornecedor") or "FORNECEDOR NAO IDENTIFICADO"
        ofertas.append({
            "fornecedor_id": preco.get("fornecedor_id"),
            "fornecedor": fornecedor,
            "produto_id": candidato.get("id"),
            "produto_padrao": candidato.get("produto_padrao"),
            "descricao_original": preco.get("descricao_original"),
            "codigo_fornecedor": preco.get("codigo_fornecedor"),
            "marca": preco.get("marca"),
            "preco": preco.get("preco"),
            "data_importacao": preco.get("data_importacao"),
            "score_busca": candidato.get("score_busca"),
        })

    return ofertas


def buscar_sku_para_item(item, limite_busca=5, score_minimo=70):
    item_original = str(item or "").strip()
    candidatos = buscar_produto_inteligente(item_original, limite=limite_busca)
    melhor = selecionar_melhor_candidato(candidatos, score_minimo=score_minimo)

    if not melhor:
        return {
            "item_original": item_original,
            "status": STATUS_SEM_MATCH,
            "sku_master": None,
            "menor_preco": None,
            "fornecedor_menor": None,
            "fornecedores": [],
            "ofertas": [],
            "candidatos_alternativos": candidatos,
        }

    ofertas = extrair_ofertas_do_candidato(melhor)
    status = STATUS_COM_PRECO if ofertas else STATUS_SKU_SEM_PRECO

    return {
        "item_original": item_original,
        "status": status,
        "sku_master": {
            "produto_id": melhor.get("id"),
            "produto_padrao": melhor.get("produto_padrao"),
            "score_busca": melhor.get("score_busca"),
            "categoria": melhor.get("categoria"),
            "fabricante": melhor.get("fabricante"),
        },
        "menor_preco": melhor.get("menor_preco"),
        "fornecedor_menor": melhor.get("fornecedor_menor"),
        "fornecedores": [
            {
                "fornecedor_id": oferta.get("fornecedor_id"),
                "fornecedor": oferta.get("fornecedor"),
                "preco": oferta.get("preco"),
                "marca": oferta.get("marca"),
                "data_importacao": oferta.get("data_importacao"),
            }
            for oferta in ofertas
        ],
        "ofertas": ofertas,
        "candidatos_alternativos": candidatos[1:] if candidatos else [],
    }


def _chave_fornecedor(oferta):
    fornecedor_id = oferta.get("fornecedor_id")
    if fornecedor_id is not None:
        return ("id", fornecedor_id)
    return ("nome", oferta.get("fornecedor") or "FORNECEDOR NAO IDENTIFICADO")


def montar_visao_por_fornecedor(itens_analisados):
    total_itens = len(itens_analisados)
    todos_itens = [item["item_original"] for item in itens_analisados]
    agrupados = {}

    for item in itens_analisados:
        if item.get("status") != STATUS_COM_PRECO:
            continue

        for oferta in item.get("ofertas") or []:
            chave = _chave_fornecedor(oferta)
            if chave not in agrupados:
                agrupados[chave] = {
                    "fornecedor_id": oferta.get("fornecedor_id"),
                    "fornecedor": oferta.get("fornecedor"),
                    "ofertas": [],
                    "_itens_atendidos": set(),
                    "_precos_por_item": defaultdict(list),
                }

            grupo = agrupados[chave]
            oferta_item = dict(oferta)
            oferta_item["item_original"] = item.get("item_original")
            grupo["ofertas"].append(oferta_item)
            grupo["_itens_atendidos"].add(item.get("item_original"))

            preco = oferta.get("preco")
            if preco is not None:
                grupo["_precos_por_item"][item.get("item_original")].append(preco)

    fornecedores = []
    for grupo in agrupados.values():
        itens_atendidos_set = grupo.pop("_itens_atendidos")
        precos_por_item = grupo.pop("_precos_por_item")

        custo_estimado = 0.0
        for precos in precos_por_item.values():
            if precos:
                custo_estimado += min(precos)

        itens_atendidos = len(itens_atendidos_set)
        cobertura = (itens_atendidos / total_itens * 100) if total_itens else 0.0

        grupo["itens_atendidos"] = itens_atendidos
        grupo["cobertura_percentual"] = round(cobertura, 2)
        grupo["custo_estimado"] = round(custo_estimado, 4)
        grupo["itens_faltantes"] = [
            item for item in todos_itens if item not in itens_atendidos_set
        ]

        fornecedores.append(grupo)

    return classificar_fornecedores_prioritarios(fornecedores)


def classificar_fornecedores_prioritarios(fornecedores):
    return sorted(
        fornecedores or [],
        key=lambda fornecedor: (
            -(fornecedor.get("itens_atendidos") or 0),
            fornecedor.get("custo_estimado") if fornecedor.get("custo_estimado") is not None else 999999999,
            fornecedor.get("fornecedor") or "",
        ),
    )


def montar_resumo(itens_analisados, fornecedores):
    total_itens = len(itens_analisados)
    itens_com_match = sum(
        1 for item in itens_analisados
        if item.get("status") in (STATUS_COM_PRECO, STATUS_SKU_SEM_PRECO)
    )
    itens_com_preco = sum(
        1 for item in itens_analisados
        if item.get("status") == STATUS_COM_PRECO
    )
    itens_sem_match = sum(
        1 for item in itens_analisados
        if item.get("status") == STATUS_SEM_MATCH
    )
    itens_sem_fornecedor = sum(
        1 for item in itens_analisados
        if item.get("status") == STATUS_SKU_SEM_PRECO
    )

    return {
        "total_itens": total_itens,
        "itens_com_match": itens_com_match,
        "itens_com_preco": itens_com_preco,
        "itens_sem_fornecedor": itens_sem_fornecedor,
        "itens_sem_match_confiavel": itens_sem_match,
        "total_fornecedores_encontrados": len(fornecedores or []),
    }


def analisar_cotacao_por_fornecedor(itens, limite_busca=5, score_minimo=70):
    itens_analisados = [
        buscar_sku_para_item(
            item,
            limite_busca=limite_busca,
            score_minimo=score_minimo,
        )
        for item in (itens or [])
    ]

    fornecedores = montar_visao_por_fornecedor(itens_analisados)
    resumo = montar_resumo(itens_analisados, fornecedores)
    itens_sem_cobertura = [
        {
            "item_original": item.get("item_original"),
            "status": item.get("status"),
            "motivo": (
                "Nenhum SKU Master identificado com score minimo"
                if item.get("status") == STATUS_SEM_MATCH
                else "SKU encontrado, mas sem fornecedor/preco cadastrado"
            ),
        }
        for item in itens_analisados
        if item.get("status") != STATUS_COM_PRECO
    ]

    return {
        "resumo": resumo,
        "itens": itens_analisados,
        "fornecedores": fornecedores,
        "fornecedores_prioritarios": fornecedores,
        "itens_sem_cobertura": itens_sem_cobertura,
    }


if __name__ == "__main__":
    itens_teste = [
        "Enoxaparina",
        "Lidocaina",
        "Propilenoglicol, acido cloridrico",
        "Oxaliplatina",
    ]

    resultado = analisar_cotacao_por_fornecedor(itens_teste)
    print(json.dumps(resultado, ensure_ascii=False, indent=2))
