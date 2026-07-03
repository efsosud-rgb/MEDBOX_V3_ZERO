# SKU-MEMORIA-11 — Diagnóstico oficial AGULHA HIPODERMICA

## Objetivo
Fazer diagnóstico detalhado da família `AGULHA` (263 produtos ativos sem SKU_MASTER, identificada pelo Codex em modo somente leitura) e preparar planilha de revisão/aprovação manual focada em `AGULHA HIPODERMICA` e `AGULHA HIPODERMICA ASPIRATIVA` — **sem alterar o banco e sem aplicar nenhum SKU_MASTER nesta fase**.

## Total AGULHA analisado
**263 produtos ativos** com `AGULHA` na descrição e `sku_master` vazio, confirmando exatamente a contagem do diagnóstico do Codex.

## Total por subfamília detectada

| Subfamília | Quantidade |
|---|---:|
| AGULHA HIPODERMICA | 39 |
| AGULHA HIPODERMICA ASPIRATIVA | 3 |
| AGULHA DESCARTAVEL COMUM | 15 |
| AGULHA RAQUI | 19 |
| AGULHA CANETA INSULINA | 4 |
| AGULHA COLETA / VACUO | 0 |
| AGULHA BIOPSIA | 7 |
| **OUTRAS / INDEFINIDAS** | **176** |
| **Total** | **263** |

O grande volume em `OUTRAS / INDEFINIDAS` (176 produtos) não é falha de classificação — a palavra `AGULHA` aparece com muita frequência em descrições de produtos que **não são agulhas propriamente ditas**, mas sim itens que a mencionam como componente:

| Categoria real | Quantidade |
|---|---:|
| FIO CIRÚRGICO (sutura com agulha embutida) | 101 |
| SERINGA (com ou sem agulha) | 37 |
| CATETER (com agulha de introdução) | 10 |
| CONJUNTO/KIT (kits cirúrgicos com agulha) | 9 |
| AGULHA GENGIVAL (odontológica) | 3 |
| AGULHA DE PUNÇÃO PORTCATH | 2 |
| AGULHA DE INFUSÃO INTRAÓSSEA | 2 |
| DRENO (com agulha) | 2 |
| ACESSÓRIO (tampa/dispositivo) | 2 |
| AGULHA DE ESCLEROSE | 1 |
| Texto corrompido (OCR) | 1 |

Nenhum desses itens é elegível para SKU_MASTER de agulha hipodérmica — são produtos de famílias completamente diferentes que compartilham a palavra-chave por acaso (ex.: `FIO POLIGLACTINA (VICRYL) 3-0 70CM AGULHA 1/2 CIR CIL 2,0CM` é um fio de sutura, não uma agulha isolada).

## Total por status

| Status | Quantidade |
|---|---:|
| CANDIDATO_SEGURO | 39 |
| PENDENTE_REVISAO | 3 |
| BLOQUEADO_ATRIBUTO_CRITICO | 1 |
| OUTRA_SUBFAMILIA | 220 |
| SEM_SUBFAMILIA_CLARA | 0 |
| **Total** | **263** |

## Grupos encontrados (AGULHA HIPODERMICA / ASPIRATIVA)

| SKU_MASTER sugerido | Qtd. produtos |
|---|---:|
| AGULHA HIPODERMICA 30X0,8MM | 7 |
| AGULHA HIPODERMICA 13X4,5MM | 7 |
| AGULHA HIPODERMICA 25X0,7MM | 6 |
| AGULHA HIPODERMICA 40X1,2MM | 6 |
| AGULHA HIPODERMICA 30X0,7MM | 4 |
| AGULHA HIPODERMICA 20X5,5MM | 4 |
| AGULHA HIPODERMICA 25X0,8MM | 3 |
| AGULHA HIPODERMICA 13X0,3MM | 1 |
| AGULHA HIPODERMICA ASPIRATIVA 25X1,2MM | 1 |
| **Total** | **39** |

Os 5 grupos originalmente identificados pelo Codex (`25X0,7`, `13X4,5`, `30X0,8`, `40X1,2`, `20X5,5`) foram confirmados por este diagnóstico independente, com contagens ligeiramente diferentes (naturais, já que este diagnóstico foi extraído diretamente do banco atual, não reaproveitado do levantamento anterior). Além disso, **3 novos grupos foram identificados**: `30X0,7MM` (4 produtos), `25X0,8MM` (3 produtos) e `13X0,3MM` (1 produto) — medidas reais presentes no catálogo que não haviam sido destacadas antes. A aspirativa `25X1,2MM` mencionada no contexto também foi confirmada (1 produto).

### Nota técnica sobre normalização de medida
Vários produtos tinham a medida digitada sem separador decimal ou com dígitos invertidos (ex.: `30X07`, `25X8,0`, `40X12`). Como nenhuma agulha hipodérmica real tem diâmetro igual ou maior que 2mm, essas variações foram normalizadas com segurança para o padrão `0,X` (ex.: `07` → `0,7`; `8,0` → `0,8`; `12` → `1,2`), consolidando produtos que na prática são idênticos mas foram digitados de formas diferentes.

## Exemplos por subfamília

| Subfamília | Exemplo |
|---|---|
| AGULHA HIPODERMICA | `AGULHA HIPODERMICA 25 X 0,7 (22G 1") COM DISP. DE SEGURANCA - CINZA -` |
| AGULHA HIPODERMICA ASPIRATIVA | `AGULHA DE ASPIRACAO MEDICAMENTOS PONTA ROMBA 25X1,2 1" 18G` |
| AGULHA DESCARTAVEL COMUM | `AGULHA DESCARTAVEL 40X12` (sem a palavra "hipodérmica") |
| AGULHA RAQUI | `AGULHA PARA RAQUIANESTESIA BISEL QUINCKE COM GUIA 25G X 3 1/2"` |
| AGULHA CANETA INSULINA | `AGULHA BD ULTRA FINE PENTA POINT 4MMX0,23MM` |
| AGULHA BIOPSIA | `AGULHA DE BIOPSIA SUPERCORE 18GX 20CM (COOK)` |
| OUTRAS (FIO CIRÚRGICO) | `FIO POLIGLACTINA (VICRYL) 3-0 70CM AGULHA 3/8 CIR CIL 3,0CM AP DIGESTIVO` |
| OUTRAS (SERINGA) | `SERINGA DESCARTAVEL 1 ML COM AGULHA 13X4,5` |
| Bloqueado (corrompido) | `SKU PENDENTE - _[AGULHA HIP 40X16 1661 12 DESC ISR UV [4 [AZ | OZ07I M` |

## Recomendação para revisão do usuário
A planilha `relatorios/sku_memoria_11_agulha_hipodermica_aprovacao_manual.xlsx` contém as **263 linhas** (não apenas os 39 candidatos seguros), porque mesmo os itens de outras subfamílias podem se beneficiar de uma revisão rápida do usuário (ex.: confirmar que um "AGULHA DESCARTAVEL COMUM" realmente não é hipodérmica). Recomenda-se:
1. Revisar primeiro os **39 CANDIDATO_SEGURO** — já agrupados por medida na aba `GRUPOS_AGULHA`, com destaque para os maiores grupos (`30X0,8MM` e `13X4,5MM`, 7 produtos cada).
2. Confirmar os **3 PENDENTE_REVISAO** manualmente (medida ambígua ou colada sem espaço no texto original).
3. Avaliar se as **15 AGULHA DESCARTAVEL COMUM** devem ser tratadas como hipodérmicas em uma fase futura (mesmo padrão de medida, só falta a palavra "hipodérmica" no texto).
4. As **19 AGULHA RAQUI**, **7 AGULHA BIOPSIA** e **4 AGULHA CANETA INSULINA** são famílias reais e reconhecidas, mas ficam para diagnósticos dedicados (fora do escopo desta fase, que é apenas hipodérmica/aspirativa).

## Confirmações de segurança
- Banco (`banco/medbox_v3.db`) acessado somente em modo leitura (`mode=ro`); nenhum `UPDATE`/`DELETE`/`INSERT` foi executado.
- Nenhum SKU_MASTER foi aplicado a nenhum produto.
- Nenhuma cascata automática foi executada.
- `app.py`, `templates/` e `core/` não foram alterados.
- Dicionário Mestre MEDREG e Bionexo não foram tocados.
