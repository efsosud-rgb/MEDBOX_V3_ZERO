# SKU-MEMORIA-08 — Diagnóstico controlado da família SONDA

## Objetivo
Fazer diagnóstico detalhado da família `SONDA` (a maior família sem SKU_MASTER identificada pelo Codex, 291 produtos) e preparar uma planilha de revisão/aprovação manual — **sem alterar o banco e sem aplicar nenhum SKU_MASTER nesta fase**.

## Total de produtos SONDA encontrados
**291 produtos ativos** com `SONDA` na descrição e `sku_master` vazio, confirmando exatamente a contagem do diagnóstico anterior do Codex. (Há mais 192 produtos `SONDA` que já têm algum `sku_master` preenchido, não incluídos neste diagnóstico.)

## Total por subfamília detectada

| Subfamília | Quantidade |
|---|---:|
| SONDA FOLEY | 77 |
| SONDA ASPIRACAO TRAQUEAL | 61 |
| SONDA URETRAL | 18 |
| SONDA NASOGASTRICA | 19 |
| SONDA ENTERAL | 11 |
| SONDA RETAL | 10 |
| SONDA LEVINE | 9 |
| SONDA NASOENTERAL | 5 |
| SONDA NELATON | 1 |
| **OUTRAS/INDEFINIDAS** | **80** |
| **Total** | **291** |

A categoria `OUTRAS/INDEFINIDAS` (80 produtos) não representa falha de classificação — é composta majoritariamente por famílias de sonda genuinamente distintas das 10 subfamílias pedidas: **sonda de gastrostomia** (inclusive a linha comercial "MICKEY" com dezenas de combinações Fr×cm), **sonda endotraqueal aramada**, **sonda nasofaríngea**, **sonda Carlens** (intubação seletiva de duplo lúmen), **dreno de Kehr**, e acessórios como **fixadores/protetores/extensores para sonda** (que não são sondas em si). Cada uma dessas merece, no futuro, seu próprio diagnóstico dedicado — misturá-las nas 10 subfamílias pedidas seria um erro de classificação.

## Total por status

| Status | Quantidade |
|---|---:|
| CANDIDATO_SEGURO | 109 |
| PENDENTE_REVISAO | 62 |
| BLOQUEADO_ATRIBUTO_CRITICO | 57 |
| SEM_SUBFAMILIA_CLARA | 61 |
| DUPLICADO_POTENCIAL | 2 |
| **Total** | **291** |

## Principais riscos

1. **Descrições corrompidas por OCR (57 produtos, risco ALTO)**: um lote de importação antigo trouxe descrições com texto ilegível misturado a fragmentos de preço (ex.: `SKU PENDENTE - _[SONDA ASP SF TR LOFR SACM 24 A JARRALCOLO LN [6 [AM | 37.000) A2ASED)...`). Qualquer número "extraído" desse texto é **não confiável** — por isso nenhuma sugestão de SKU_MASTER foi gerada para esses casos, mesmo quando um padrão de dígitos parecia reconhecível.

2. **Foley sem volume de balão declarado (grande parte dos 62 pendentes)**: muitos produtos Foley têm número e via claramente escritos (ex.: `SONDA FOLEY 2 VIAS Nº 12 - EM LATEX`), mas **nenhum volume de balão** na descrição de origem. Como o volume do balão (5ml, 10ml, 30ml) é um atributo crítico que diferencia produtos reais, a sugestão foi deliberadamente **bloqueada** em vez de assumir um valor padrão.

3. **Mistura de vias, calibre e balão no mesmo texto sem marcador claro**: formatos como `SONDA FOLLEY ///3/// VIAS C/ BALAO N. 18` (barras em vez de espaço) não foram reconhecidos pelo extrator conservador — ficaram como `PENDENTE_REVISAO` em vez de arriscar uma extração incorreta.

4. **Duplicidade potencial confirmada em 2 casos reais**: `id 6278` (`SONDA URETRAL Nº 12`) e `id 7431` (`SONDA URETRAL N. 12`) são a mesma descrição (ignorando pontuação/dígitos) e o mesmo calibre — provável duplicidade de importação, sinalizada para revisão antes de consolidar.

5. **Números "soltos" sem marcador (`Nº`/`FR`)**: casos como `SONDA RETAL 14` ou `SONDA URETRAL PEDIATRICA 06` têm um número no fim do texto, mas sem nenhum marcador que confirme que aquele número é de fato o calibre — tratados como `PENDENTE_REVISAO` por segurança, em vez de assumir.

## Exemplos de cada subfamília

| Subfamília | Exemplo | Sugestão preliminar |
|---|---|---|
| SONDA FOLEY | `SONDA FOLEY DESC ESTERIL BALAO 30ML 2 VIAS Nº12` | `SONDA FOLEY 2 VIAS Nº 12 BALAO 30ML` |
| SONDA URETRAL | `SONDA URETRAL Nº 14` | `SONDA URETRAL Nº 14` |
| SONDA NELATON | (único caso do lote) | — |
| SONDA NASOGASTRICA | `SONDA NASOGASTRICA TIPO LEVINE LONGA ESTERIL DESCARTAVEL NUMERO 14` | classificado como LEVINE (mais específico) |
| SONDA NASOENTERAL | `SONDA DUBBHOFF C/ FIO Nº10` | `SONDA NASOENTERAL Nº 10` |
| SONDA ENTERAL | `SONDA PARA NUTRICAO ENTERAL, SILICONADA, ... Nº 12` | `SONDA ENTERAL Nº 12` |
| SONDA ASPIRACAO TRAQUEAL | `SONDA DE ASPIRACAO TRAQUEAL C/VALVULA Nº 12` | `SONDA ASPIRACAO TRAQUEAL Nº 12` |
| SONDA RETAL | `SONDA RETAL 10` (id 5173, garbled) | bloqueado (corrompido) |
| SONDA LEVINE | `SONDA LEVINE, NASOGASTRICA, LONGA, DESCARTAVEL, ESTERIL, N16` | `SONDA LEVINE Nº 16` |
| OUTRAS/INDEFINIDAS | `SONDA DE GASTROSTOMIA MICKEY 24X2,5CM - BOTTON` | sem sugestão (família própria) |

Nota: quando a descrição menciona `LEVINE` e `NASOGASTRICA` juntos, o produto foi classificado como `SONDA LEVINE` (mais específico), não como `SONDA NASOGASTRICA` genérica — Levine é um tipo específico de sonda nasogástrica.

## Recomendação para o usuário revisar
A planilha `relatorios/sku_memoria_08_sonda_aprovacao_manual.xlsx` contém as **291 linhas** (não apenas os 109 candidatos seguros) porque mesmo os itens bloqueados/pendentes/sem-subfamília merecem revisão humana — muitos podem ser resolvidos rapidamente por quem conhece o produto físico ou tem acesso à nota fiscal original. Recomenda-se:
1. Revisar primeiro os **109 CANDIDATO_SEGURO** (risco BAIXO) — são o lote mais rápido de aprovar.
2. Usar a aba `GRUPOS_SONDA` para ver quantos produtos cada sugestão agruparia, priorizando os grupos maiores (ex.: `SONDA ASPIRACAO TRAQUEAL Nº 12` e `Nº 14`, 8 produtos cada).
3. Tratar os **57 BLOQUEADO_ATRIBUTO_CRITICO** (texto corrompido) como um lote separado — provavelmente precisam de consulta à nota fiscal original ou embalagem física, não apenas revisão de texto.
4. Avaliar se as **80 OUTRAS/INDEFINIDAS** merecem fases de diagnóstico dedicadas (gastrostomia, endotraqueal aramada, etc.) antes de tentar padronizá-las junto com `SONDA`.

## Confirmações de segurança
- Banco (`banco/medbox_v3.db`) acessado somente em modo leitura (`mode=ro`); nenhum `UPDATE`/`DELETE`/`INSERT` foi executado.
- Nenhum SKU_MASTER foi aplicado a nenhum produto.
- Nenhuma cascata automática foi executada.
- `app.py`, `templates/` e `core/` não foram alterados.
- Bionexo e Dicionário Mestre MEDREG não foram tocados.
- Nenhuma pesquisa externa foi necessária nesta fase (os padrões de sonda são bem conhecidos e documentados na própria metodologia global do projeto).
