# SKU-MEMORIA-13 — Diagnóstico oficial DIPIRONA

## Objetivo
Fazer diagnóstico detalhado da família `DIPIRONA` (32 produtos ativos sem SKU_MASTER, identificados pelo Codex em modo somente leitura) e preparar planilha de revisão/aprovação manual — **sem alterar o banco e sem aplicar nenhum SKU_MASTER nesta fase**.

## Total analisado
**32 produtos ativos** com `DIPIRONA` na descrição e `sku_master` vazio, confirmando exatamente a contagem do Codex. Nenhum produto foi encontrado sob os sinônimos comerciais pesquisados (`METAMIZOL`, `NOVALGINA`, `ANADOR`, `MAGNOPYROL`, `MAXALGINA`, `DORFLEX`) — achado honesto, essas marcas não aparecem no catálogo local sob esse nome exato.

## Total por status

| Status | Quantidade |
|---|---:|
| CANDIDATO_SEGURO | 23 |
| ASSOCIADA_COMPOSTA | 7 |
| PENDENTE_REVISAO | 1 |
| SEM_APRESENTACAO_CLARA | 1 |
| BLOQUEADO_ATRIBUTO_CRITICO | 0 |
| **Total** | **32** |

Nenhum texto corrompido (OCR) foi encontrado neste lote — dado mais limpo que os das famílias `SONDA`/`AGULHA`.

## Grupos encontrados

| SKU_MASTER sugerido | Qtd. produtos |
|---|---:|
| DIPIRONA SODICA 500MG/ML AMPOLA 2ML | 5 |
| DIPIRONA SODICA 500MG COMPRIMIDO | 5 |
| DIPIRONA SODICA 500MG/ML GOTAS 10ML | 3 |
| DIPIRONA SODICA 500MG/ML SOL ORAL 10ML | 3 |
| DIPIRONA SODICA 1G COMPRIMIDO | 2 |
| DIPIRONA SODICA 50MG/ML SOL ORAL 100ML | 2 |
| DIPIRONA SODICA 500MG/ML SOL ORAL 20ML | 1 |
| DIPIRONA SODICA 1G COMPRIMIDO EFERVESCENTE | 1 |
| DIPIRONA SODICA 300MG SUPOSITORIO | 1 |
| **Total** | **23** |

Os 3 grupos do Codex foram confirmados com boa aderência: `500MG/ML AMP 2ML` (Codex: 5 → confirmado: 5, match exato), `500MG/ML GOTAS 10ML` (Codex: 3 → confirmado: 3, match exato) e `500MG COMP` (Codex: 2 → este diagnóstico encontrou 5, mais completo — inclui variações de texto como "DIPIRONA 500MG (COMP)", "DIPIRONA 500MG CP" e versões "GENERICO OU SIMILAR"/"MARCA" que são o mesmo produto real).

Além disso, **6 novos grupos foram identificados**: `SOL ORAL 10ML` (3), `1G COMPRIMIDO` (2), `50MG/ML SOL ORAL 100ML` (2 — uma concentração mais diluída, formulação distinta de 500mg/ml), `SOL ORAL 20ML` (1), `1G COMPRIMIDO EFERVESCENTE` (1 — forma farmacêutica diferente do comprimido comum) e `300MG SUPOSITORIO` (1 — via retal, forma totalmente diferente das demais).

## Casos associados/compostos (bloqueados)
**7 produtos**, confirmando exatamente a contagem do Codex — todos combinam dipirona com outro princípio ativo:
- `BUTILBROMETO DE ESCOPOLAMINA + DIPIRONA SODICA` (analgésico + antiespasmódico, injetável e gotas) — 5 produtos
- `DIPIRONA/ORFENADRINA/CAFEINA` (associação tripla tipo "Dorflex-símile") — 1 produto

Nenhum desses foi misturado com dipirona simples — status `ASSOCIADA_COMPOSTA`, sem sugestão de SKU_MASTER, exatamente como pedido.

## Casos pendentes/indefinidos
- **1 PENDENTE_REVISAO**: `DIPIRONA 500MG/ML SOL ORAL FR` (id 7047) — concentração e forma (solução oral) claras, mas **sem volume declarado** na descrição de origem. Risco alto: não é seguro presumir se é 10ml, 20ml ou outro volume.
- **1 SEM_APRESENTACAO_CLARA**: `DIPIRONA 500 MG` (id 5926) — dose presente, mas nenhuma forma farmacêutica (comprimido/ampola/gotas) identificável no texto.

## Exemplos por apresentação

| Apresentação | Exemplo |
|---|---|
| Comprimido 500mg | `DIPIRONA SODICA 500 MG COMP` |
| Comprimido 1g | `DIPIRONA MONOIDRATADA 1G VIA ORAL COMPRIMIDO ADULTO/INFANTIL MARCA` |
| Gotas 500mg/ml 10ml | `DIPIRONA SODICA GOTAS 500MG/ML SOL ORAL 10ML (FR)` |
| Solução oral 500mg/ml 10ml | `DIPIRONA SODICA 500MG/ML 10ML FRASCO SOLUCAO ORAL` |
| Solução oral 50mg/ml 100ml | `DIPIRONA SODICA 50MG/ML VIA ORAL FRASCO 100ML ADULTO/INFANTIL MARCA` |
| Ampola 500mg/ml 2ml | `DIPIRONA SODICA 500MG/ML 2ML SOLUCAO INJETAVEL` |
| Comprimido efervescente 1g | `DIPIRONA MONOIDRATADA EFERVESCENTE 1G VIA ORAL COMPRIMIDO ADULTO/INFANTIL MARCA` |
| Supositório 300mg | `DIPIRONA SODICA 300MG VIA RETAL SUPOSITORIO ADULTO/INFANTIL MARCA` |
| Associada (escopolamina) | `ESCOPOLAMINA 4MG/ML + DIPIRONA 500MG/ML 5ML AMP` |
| Associada (orfenadrina/cafeína) | `DIPIRONA/ORFENADRINA/CAFEINA 300MG/35MG/50MG VIA ORAL COMPRIMIDO ADULTO MARCA` |

## Confirmações de segurança
- Banco (`banco/medbox_v3.db`) acessado somente em modo leitura (`mode=ro`); nenhum `UPDATE`/`DELETE`/`INSERT` foi executado.
- Nenhum SKU_MASTER foi aplicado a nenhum produto.
- Nenhuma cascata automática foi executada.
- `app.py`, `templates/` e `core/` não foram alterados.
- Dicionário Mestre MEDREG e Bionexo não foram tocados.

## Recomendação
**APTO_PARA_REVISAO_USUARIO** — a planilha `relatorios/sku_memoria_13_dipirona_aprovacao_manual.xlsx` está pronta para revisão. Conforme a regra global já estabelecida nas fases anteriores (`SONDA`, `AGULHA`), a aprovação do usuário na planilha será a validação final; nenhuma aplicação ocorrerá antes disso.
