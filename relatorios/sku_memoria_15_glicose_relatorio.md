# SKU-MEMORIA-15 — Diagnóstico oficial GLICOSE

## Objetivo
Fazer diagnóstico detalhado da família `GLICOSE` (34 produtos ativos sem SKU_MASTER, identificados pelo Codex em modo somente leitura) e preparar planilha de revisão/aprovação manual — **sem alterar o banco e sem aplicar nenhum SKU_MASTER nesta fase**.

## Total analisado
**34 produtos ativos** com `GLICOSE` na descrição e `sku_master` vazio, confirmando exatamente a contagem do Codex. Nenhum produto foi encontrado sob os sinônimos pesquisados (`DEXTROSE`, `SOLUCAO GLICOSADA`, `SOL GLICOSADA`, `SG 5%/10%/25%/50%`) fora dos já capturados por `GLICOSE`.

## Total por status

| Status | Quantidade |
|---|---:|
| CANDIDATO_SEGURO | 20 |
| ASSOCIADA_OUTRAS | 12 |
| PENDENTE_REVISAO | 2 |
| BLOQUEADO_ATRIBUTO_CRITICO | 0 |
| SEM_APRESENTACAO_CLARA | 0 |
| **Total** | **34** |

## Grupos encontrados

| SKU_MASTER sugerido | Qtd. produtos |
|---|---:|
| GLICOSE 50% 10ML AMP | 4 |
| SOLUCAO GLICOSE 5% 250ML | 4 |
| SOLUCAO GLICOSE 10% 500ML | 3 |
| SOLUCAO GLICOSE 5% 500ML | 3 |
| GLICOSE 25% 10ML AMP | 2 |
| GLICOSE 75% 10ML AMP | 1 |
| SOLUCAO GLICOSE 5% 250ML BOLSA | 1 |
| SOLUCAO GLICOSE 5% 500ML BOLSA | 1 |
| SOLUCAO GLICOSE 10% 250ML | 1 |
| **Total** | **20** |

Os 5 grupos do Codex foram confirmados com boa aderência: `SOLUCAO GLICOSE 10% 500ML` (Codex: 3 → confirmado: 3, match exato) e `SOLUCAO GLICOSE 5% 500ML` (Codex: 3 → confirmado: 3 no grupo FRASCO/sistema fechado, mais 1 em bolsa separada — match exato quando a bolsa é tratada como grupo distinto). Os grupos `GLICOSE 50% 10ML AMP` (Codex: 5 → confirmado: 4), `GLICOSE 25% 10ML AMP` (Codex: 3 → confirmado: 2) e `SOLUCAO GLICOSE 5% 250ML` (Codex: 3 → confirmado: 4 + 1 bolsa) tiveram pequenas diferenças, explicadas abaixo. Confirmado também: nenhum grupo seguro para `SOLUCAO GLICOSE 5% 100ML` e `5% 1000ML`, exatamente como o Codex apontou — nenhum produto com esses volumes foi encontrado no lote.

**Nota sobre embalagem (ampola/frasco/bolsa)**: este diagnóstico tratou bolsa como apresentação distinta de frasco/ampola, conforme a regra explícita de não misturar essas embalagens. Isso significa que `SOLUCAO GLICOSE 5% 250ML` (4 produtos em frasco/sistema fechado) e `SOLUCAO GLICOSE 5% 250ML BOLSA` (1 produto em bolsa) aparecem como dois grupos separados, mesmo compartilhando concentração e volume — mais conservador que uma contagem unificada.

**Nota sobre a divergência nos grupos AMP 10ML**: os 2 produtos que o Codex provavelmente contabilizou a mais em `50% 10ML AMP` e `25% 10ML AMP` são exatamente os 2 casos classificados aqui como `PENDENTE_REVISAO` — descrições como `GLICOSE 25% 10ML SOLUCAO INJETAVEL` e `GLICOSE 50% 10ML SOLUCAO INJETAVEL`, que têm concentração e volume claros mas **não mencionam explicitamente "ampola"** no texto de origem. Embora seja um padrão altamente provável (todos os demais produtos 25%/50% 10ML deste lote são ampola), este diagnóstico optou por não presumir a embalagem sem confirmação explícita, mantendo a mesma cautela usada em fases anteriores (ex.: volume ausente em DIPIRONA).

**Dois novos grupos identificados**, fora da lista de 7 apresentações pré-definidas: `GLICOSE 75% 10ML AMP` (concentração hipertônica incomum, 1 produto: `GLICOSE 750 MG/ML (75%) SOLUCAO INJETAVEL AMP. 10ML`) e `SOLUCAO GLICOSE 10% 250ML` (1 produto: `GLICOSE 10% 250ML SISTEMA FECHADO SOLUCAO INJETAVEL`).

## Casos associados/outros (bloqueados)
**12 produtos**, classificados `ASSOCIADA_OUTRAS` — abaixo dos 14 do Codex (divergência esperada de uma leitura preliminar; ver observação final). Categorias encontradas:
- **Nutrição parenteral total (multi-componente)**: `AMINOACIDOS + GLICOSE + ELETROLITOS`, `AMINOACIDOS + GLICOSE + LIPIDEOS + ELETROLITOS` — 3 produtos
- **Anestésico hiperbárico com glicose**: `BUPIVACAINA + GLICOSE` — 2 produtos
- **Antiemético combinado**: `DIMENIDRINATO + PIRIDOXINA + GLICOSE + FRUTOSE` — 1 produto
- **Soro de reidratação oral (sais + glicose)**: `CITRATO DE SODIO/CLORETO DE POTASSIO/GLICOSE/CLORETO DE SODIO` — 2 produtos
- **Dispositivos de monitoramento de glicemia (não são solução de glicose)**: tiras reagentes e sensores (`TIRA REATIVA`, `TIRA PARA TESTE`, `SENSOR DE GLICOSE FREESTYLE LIBRE`) — 4 produtos

Nenhum desses foi misturado com glicose simples — sem sugestão de SKU_MASTER, exatamente como pedido.

## Casos pendentes
**2 PENDENTE_REVISAO** — concentração e volume claros (25%/50%, 10ML), mas sem menção explícita de ampola/frasco/bolsa na descrição de origem: `GLICOSE 25% 10ML SOLUCAO INJETAVEL` (id 5975) e `GLICOSE 50% 10ML SOLUCAO INJETAVEL` (id 5977).

## Exemplos por apresentação

| Apresentação | Exemplo |
|---|---|
| Ampola 50% 10ml | `GLICOSE 50% HIPERTONICA 10ML (AMP)` |
| Ampola 25% 10ml | `GLICOSE 25% 10ML AMP` |
| Ampola 75% 10ml (novo) | `GLICOSE 750 MG/ML (75%) SOLUCAO INJETAVEL AMP. 10ML` |
| Frasco 5% 250ml | `GLICOSE 5% 250ML (FR)` |
| Frasco sistema fechado 10% 500ml | `GLICOSE 10% 500ML SISTEMA FECHADO SOLUCAO INJETAVEL` |
| Bolsa 5% 250ml | `GLICOSE 5 % SOL INJ BOL 250 ML` |
| Bolsa 5% 500ml | `GLICOSE 5 % SOL INJ BOL 500 ML` |
| Frasco 10% 250ml (novo) | `GLICOSE 10% 250ML SISTEMA FECHADO SOLUCAO INJETAVEL` |
| Nutrição parenteral | `AMINOACIDOS + GLICOSE + LIPIDEOS + ELETROLITOS CAPACIDADE DE 1875 ML A 2100 ML` |
| Anestésico com glicose | `BUPIVACAINA CLORIDRATO 5MG/ML (0,5%) + GLICOSE 80MG/ML (8%)` |
| Reidratação oral | `CITRATO SODIO DI-HIDRATADO/CLORETO POTASSIO/GLICOSE/CLORETO SODIO ... VIA ORAL ENVELOPE` |
| Dispositivo de glicemia | `SENSOR DE GLICOSE FREESTYLE LIBRE 2 PLUS ABBOTT` |

## Confirmações de segurança
- Banco (`banco/medbox_v3.db`) acessado somente em modo leitura (`mode=ro`); nenhum `UPDATE`/`DELETE`/`INSERT` foi executado.
- Nenhum SKU_MASTER foi aplicado a nenhum produto.
- Nenhuma cascata automática foi executada.
- `app.py`, `templates/` e `core/` não foram alterados.
- Dicionário Mestre MEDREG e Bionexo não foram tocados.

## Recomendação
**APTO_PARA_REVISAO_USUARIO** — a planilha `relatorios/sku_memoria_15_glicose_aprovacao_manual.xlsx` está pronta para revisão. Conforme a regra global já estabelecida nas fases anteriores, a aprovação do usuário na planilha será a validação final; nenhuma aplicação ocorrerá antes disso. Os 2 casos `PENDENTE_REVISAO` merecem atenção especial: se o usuário confirmar que são de fato ampolas (padrão consistente com o restante do catálogo), pode preencher `sku_master_corrigido_usuario` diretamente na planilha.
