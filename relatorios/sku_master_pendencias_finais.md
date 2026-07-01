# SKU-PENDENCIAS-01 — Mapeamento final das pendências SKU_MASTER

## Objetivo
Mapear, com números e exemplos reais, o que ainda falta para concluir a padronização SKU_MASTER no branch local `melhoria/auditoria-sku-master-todos-produtos`.

## Estado funcional do módulo
**APTO_PARA_USO.**

Verificação por leitura de código (`app.py` + `core/auditoria_sku_master.py` + `templates/sku_master_auditoria.html`), sem execução de escrita:

| Capacidade | Presente? | Onde |
|---|---|---|
| Buscar qualquer produto por descrição (`q`) | Sim | `gerar_auditoria_sku_master` busca em `produto_padrao`, `sku_master` e `precos_fornecedores.descricao_original` |
| Editar SKU Master | Sim | `salvar_edicao_manual_produto` / rota `/sku-master/auditoria/salvar-edicao` |
| Editar fabricante/categoria/ativo/observações | Sim | mesmo whitelist `campos_editaveis`; `produto_padrao` permanece somente leitura |
| Salvar correção | Sim | `salvar-edicao`, `salvar-sku`, `salvar-sku-ajax`, `corrigir-todos` |
| Propagar para similares (cascata) | Sim | `preview-cascata` (dry-run) + `ids_cascata_selecionados` aplicados em `salvar_edicao_manual_produto` |
| Marcar como corrigido | Sim, automático | `_sincronizar_destino_corrigido` seta `sku_corrigido=1` e `corrigido_em` ao aplicar SKU Master |
| Exportar CSV | Sim | rota `/sku-master/auditoria.csv`, mesmo filtro/`q` da listagem |

## Banco analisado
- Caminho oficial: `banco/medbox_v3.db` (definido em `core/banco.py:11`, `DB_PATH = PASTA_BANCO / "medbox_v3.db"`; é o banco usado por `conectar()` em toda a aplicação).
- Modo de acesso: **somente leitura** (`sqlite3.connect("file:banco/medbox_v3.db?mode=ro", uri=True)` e reuso das funções de leitura já existentes em `core/auditoria_sku_master.py`, como `gerar_auditoria_sku_master`, que não faz nenhuma escrita).
- Outros bancos encontrados na pasta `banco/` (`medbox.db`, `medbox_v3_teste.db`) **não são usados** pelo código atual — não foram tocados.

## Contagens gerais

| Métrica | Valor | % sobre auditável (10.839) |
|---|---:|---:|
| Total de produtos cadastrados (incluindo inativos) | 11.105 | — |
| Total inativos (`ativo=0`) | 266 | — |
| **Total auditável (`ativo=1`)** | **10.839** | 100% |
| Total corrigido/revisado (`sku_corrigido=1`, ativos) | 29 | 0,3% |
| Total pendente (ativo, `sku_corrigido` ≠ 1) | 10.810 | 99,7% |
| Total sem SKU Master preenchido | 6.256 | 57,7% |
| Total com SKU Master preenchido | 4.583 | 42,3% |
| Total sem fabricante preenchido | 7.687 | 70,9% |
| Total com fabricante problemático (`UN`, `SR`, `S R`, `MD` isolados) | 0 | 0% |
| Total de itens em descrições 100% duplicadas | 457 | 4,2% |
| Total de grupos 100% duplicados | 147 | — |
| Total de itens com sugestão automática de cascata (candidatos) | 1.935 | 17,9% |

### Classificação da Auditoria SKU Master (lógica já existente no módulo)

| Classificação | Quantidade | % |
|---|---:|---:|
| LIMPO | 4.178 | 38,5% |
| SUSPEITO | 1.473 | 13,6% |
| CONTAMINADO_FORTE | 3.939 | 36,3% |
| SKU_PENDENTE | 792 | 7,3% |
| DUPLICADO | 457 | 4,2% |
| **Total** | **10.839** | 100% |

Nota sobre fabricante problemático: os códigos citados no escopo (`UN`, `S R`, `SR`, `MD`) **não existem hoje** como valor isolado em `produtos.fabricante` nem em `precos_fornecedores.marca` — provavelmente já foram corrigidos em fases anteriores (há histórico de scripts `corrigir_sr_precos.py`, `ajuste_fr_fabricante_real_contextual.txt` no repositório). O problema real e dominante hoje é **ausência total de fabricante** (70,9% dos produtos ativos), não um código inválido específico.

## Principais categorias de pendência

| Categoria | Quantidade | Impacto |
|---|---:|---|
| Sem fabricante preenchido | 7.687 | Impede rastreabilidade de marca/fornecedor e regras de cascata por fabricante |
| Sem SKU Master preenchido | 6.256 | Produto ainda depende da `produto_padrao` bruta da importação; sem padronização |
| Contaminado forte (descrição com excesso de tokens/muito longa) | 3.939 | Descrição de baixa qualidade, maior risco de duplicidade textual |
| Suspeito (motivos leves: repetição de termo, marca no fim) | 1.473 | Necessita revisão manual pontual |
| SKU pendente (prefixo literal `SKU PENDENTE`) | 792 | Produto importado sem qualquer padronização aplicada |
| Duplicado (mesma descrição final em 2+ produtos ativos) | 457 itens / 147 grupos | Risco de dispersão de preços/histórico entre produtos que deveriam ser um só |
| Candidatos a cascata com sugestão automática | 1.935 | Uso do recurso de sugestão já existente pode acelerar em lote, mas exige checagem (ver Riscos) |

Motivos mais frequentes nos itens não-LIMPO (podem se sobrepor no mesmo produto):
- `excesso_tokens`: 4.265 ocorrências
- `muito_longo`: 3.904 ocorrências
- `igual_descricao_original`: 2.384 ocorrências
- `sku_pendente`: 792 ocorrências
- `repeticao_termo_base`: 45 ocorrências
- `marca_fabricante_no_fim`: 35 ocorrências

## Exemplos reais

### Sem SKU Master preenchido (amostra de 30, de 6.256)
```
11054 | SONDA ASPIRACAO TRAQUEAL Nº10 - EMBRAMED
11053 | SONDA ASPIRACAO TRAQUEAL Nº 20
11052 | SONDA ASPIRACAO TRAQUEAL Nº 16
11051 | SONDA ASPIRACAO TRAQUEAL Nº 14
11050 | SONDA ASPIRACAO TRAQUEAL Nº 10
11049 | SONDA ASPIRACAO TRAQUEAL Nº 08
11048 | SONDA ASPIRACAO TRAQUEAL Nº 04
11047 | SOLUCAO PARA IRRIGACAO DE FERIDAS COMPOSTA DE 0,1% DE POLIHEXANIDA...
11046 | SOLUCAO DE IRRIGACAO DE FERIDAS COMPOSTA DE 0,1% DE POLIHEXANIDA...
11045 | SOLUCAO AQUOSA, 0,2%, DERMOSAUVE, EM ALMOTOLIA 100
11044 | SISTEMA PARA ASPIRACAO DAS VIAS AEREAS 250 ML. SECRECAO
11043 | SISTEMA FECHADO DE ASPIRACAO TRAQUEAL Nº12
11041 | SERINGA HIP. 1ML- S/DISP.SEG.(INSULINA)- S/AGULHA- LUER LOK
11040 | SERINGA DOSADORA DESCARTAVEL ESTERIL 10ML C/ TAMPA - EMB. INDIVIDUAL
11039 | SERINGA DESCARTAVEL ESTERIL 5ML - C/ AGULHA - 25X0,7
11038 | SERINGA DESCARTAVEL ESTERIL 3ML - C/ AGULHA - 25X0,7
11037 | SERINGA DESCARTAVEL ESTERIL 20ML - S/AGULHA LUER SLIP
11036 | SERINGA DESCARTAVEL ESTERIL 20ML - C/ AGULHA - 25X0,7
11035 | SERINGA DESCARTAVEL ESTERIL 1ML INSULINA - C/ AGULHA- 13X0,45MM
11034 | SERINGA DESCARTAVEL ESTERIL 10ML - C/ AGULHA 25X0,7
11033 | SERINGA DESCARTAVEL 03ML S/AG, COM BICO. LUER SLIP
11032 | SCALP 25
11031 | SACO COLETOR DE URINA PEDIATRICO - MASCULINO
11030 | SACO COLETOR DE URINA PEDIATRICO - FEMININO
11029 | SABONETE CREMOSO SEM GERMICIDA - 1L
11028 | PULSEIRA VERMELHA - COM INSCRICAO (ALERGIA)
11027 | PULSEIRA IDENTIFICACAO MAE/FILHO ROSA, CONJUNTO POLIESTER RESISTENTE
11026 | PULSEIRA IDENTIFICACAO MAE/FILHO AZUL CONJUNTO POLIESTER RESISTENTE
11025 | PULSEIRA DE PAPEL (TYVEK) P/ IDENTIFICACAO INF. VERDE C/ DADOS
11024 | PULSEIRA DE IDENTIFICACAO VERMELHA CONFECCIONADA EM POLIESTER
```

### Sem fabricante preenchido (amostra de 30, de 7.687)
```
11089 | TUBO ENDOTRAQUEAL NO 6,0. COM CUFF
11088 | TUBO ENDOTRAQUEAL NO 10, 2,0MM
11087 | TUBO ENDOTRAQUEAL COM BALONETE Nº 7,5
11086 | TUBO ENDOTRAQUEAL COM BALONETE Nº 6,5
11085 | TUBO ENDOTRAQUEAL COM BALONETE Nº 5,5
11084 | TUBO ENDOTRAQUEAL C/ BALAO TAM 9,0
11054 | SONDA ASPIRACAO TRAQUEAL Nº10 - EMBRAMED
11053 | SONDA ASPIRACAO TRAQUEAL Nº 20
11052 | SONDA ASPIRACAO TRAQUEAL Nº 16
11051 | SONDA ASPIRACAO TRAQUEAL Nº 14
11050 | SONDA ASPIRACAO TRAQUEAL Nº 10
11049 | SONDA ASPIRACAO TRAQUEAL Nº 08
11048 | SONDA ASPIRACAO TRAQUEAL Nº 04
11047 | SOLUCAO PARA IRRIGACAO DE FERIDAS COMPOSTA DE 0,1% DE POLIHEXANIDA...
11046 | SOLUCAO DE IRRIGACAO DE FERIDAS COMPOSTA DE 0,1% DE POLIHEXANIDA...
11045 | SOLUCAO AQUOSA, 0,2%, DERMOSAUVE, EM ALMOTOLIA 100
11044 | SISTEMA PARA ASPIRACAO DAS VIAS AEREAS 250 ML. SECRECAO
11043 | SISTEMA FECHADO DE ASPIRACAO TRAQUEAL Nº12
11041 | SERINGA HIP. 1ML- S/DISP.SEG.(INSULINA)- S/AGULHA- LUER LOK
11040 | SERINGA DOSADORA DESCARTAVEL ESTERIL 10ML C/ TAMPA
11039 | SERINGA DESCARTAVEL ESTERIL 5ML - C/ AGULHA - 25X0,7
11038 | SERINGA DESCARTAVEL ESTERIL 3ML - C/ AGULHA - 25X0,7
11037 | SERINGA DESCARTAVEL ESTERIL 20ML - S/AGULHA LUER SLIP
11036 | SERINGA DESCARTAVEL ESTERIL 20ML - C/ AGULHA - 25X0,7
11035 | SERINGA DESCARTAVEL ESTERIL 1ML INSULINA - C/ AGULHA- 13X0,45MM
11034 | SERINGA DESCARTAVEL ESTERIL 10ML - C/ AGULHA 25X0,7
11033 | SERINGA DESCARTAVEL 03ML S/AG, COM BICO. LUER SLIP
11032 | SCALP 25
11031 | SACO COLETOR DE URINA PEDIATRICO - MASCULINO
11030 | SACO COLETOR DE URINA PEDIATRICO - FEMININO
```

### Fabricante problemático (códigos `UN`/`SR`/`S R`/`MD`)
Nenhum exemplo encontrado — não há ocorrência desses valores isolados em `produtos.fabricante` nem em `precos_fornecedores.marca` no estado atual do banco. Valores curtos existentes são fabricantes legítimos: `BD` (14), `3M` (6), `ABL` (15), `EMS` (33), `AMED` (36) — nenhum sinal de contaminação por código de unidade.

### Descrições 100% duplicadas — maiores grupos (até 30, de 147 grupos)
```
[11x] TUBO ENDOTRAQUEAL COM BALONETE Nº 7,5           | ids: 11087,10624,7444,6505,6207,5685,5540,4527...
[10x] TUBO OROTRAQUEAL COM BALAO POLIVINIL 8,0MM       | ids: 11096,7751,7445,6506,6224,6208,5541,4528...
[10x] ENOXAPARINA SODICA 40MG SC SERINGA 0,4ML ADULTO  | ids: 8976,8608,6732,6424,5937,4284,3590,2016...
[9x]  TUBO OROTRAQUEAL COM BALAO POLIVINIL 8,5MM       | ids: 11097,7789,7446,6507,6209,5686,5542,3186...
[9x]  ENOXAPARINA SODICA 60MG SC SERINGA 0,6ML GENÉRICO| ids: 9721,6733,6425,5938,5364,4283,3588,960...
[9x]  AGULHA HIPODERMICA 30X0,80MM                     | ids: 3028,3027,3023,3022,3021,2024,2020,2019...
[8x]  ROCURONIO, BROMETO 10MG/ML 5ML SOL. INJETAVEL    | ids: 10576,6860,6401,6103,5774,4387,1182,586
[8x]  PIPERACILINA 4G + TAZOBACTAM 0,5G PO INJ.         | ids: 10551,9192,6797,6444,6122,4372,3601,555
[8x]  OXACILINA SODICA 500MG PO IM/IV FRASCO AMPOLA     | ids: 10128,7121,6793,6076,5325,4365,1148,536
[7x]  TUBO OROTRAQUEAL COM BALAO POLIVINIL 7,0MM        | ids: 11095,7750,7443,6504,5684,5539,3183
[7x]  LUVA DE PROCEDIMENTO PEQUENA C/PO                 | ids: 10995,8072,7713,2142,478,477,473
[7x]  LUVA DE PROCEDIMENTO MEDIA - CX C/50               | ids: 10993,7801,7712,2141,1100,476,472
[7x]  ENOXAPARINA SODICA 20MG SC SERINGA 0,2ML ADULTO   | ids: 9720,8758,7037,5936,5363,3589,266
[7x]  IMUNOGLOBULINA ANTI RH INJ 250 A 300 MCG F/A       | ids: 5430,4322,3595,1811,1770,1058,391
[6x]  SKU PENDENTE - 20870 AGULHA 40X12 (18G X 1-1/2)UN  | ids: 4477,3047,3046,3029,2025,19
[6x]  CLORETO DE SODIO 0,9% 500ML SIST. FECHADO SOL.INJ. | ids: 3584,2200,1220,1219,897,186
[5x]  TUBO ENDOTRAQUEAL SEM BALONETE Nº 3,5              | ids: 11092,10625,5536,3193,722
[5x]  TUBO ENDOTRAQUEAL COM BALONETE Nº 5,5              | ids: 11085,7442,5683,5538,3180
[5x]  LUVA PROCEDIMENTO LATEX G COM PO COM 100UNID       | ids: 7937,7704,2140,474,471
[5x]  TOUCA                                              | ids: 4600,2198,1246,1245,714
[5x]  CLORETO DE SODIO 0,9% 100 ML, SOL. INJ. SIST.FECH. | ids: 3585,2199,1218,1217,673
[4x]  TUBO ENDOTRAQUEAL NO 6,0. COM CUFF                 | ids: 11089,7545,3181,723
[4x]  TUBO ENDOTRAQUEAL C/ BALAO TAM 9,0                 | ids: 11084,6508,3187,727
[4x]  SONDA FOLLEY Nº 12 2 VIAS                          | ids: 11063,11056,8020,7416
[4x]  ENOXAPARINA SODICA SC 80MG/0,8ML SERINGA           | ids: 10329,4285,961,269
[4x]  TUBO ENDOTRAQUEAL C/BALAO N. 3,5                   | ids: 7439,6616,5544,3176
[4x]  COMPRESSA DE GAZE                                  | ids: 4605,4604,4597,4592
[4x]  SORO FISIOLOGICO 20% 10ML                          | ids: 4549,4434,4258,187
[4x]  SKU PENDENTE - 19856 GAZE 7,5 X 7,5 13FIOS ESTERIL  | ids: 4496,919,351,350
[4x]  SKU PENDENTE - 14424 CETOPROFENO 100MG IV 2ML       | ids: 4427,4249,880,165
```

### Grupos candidatos a cascata — sugestão automática já calculada pelo módulo (amostra de 30, de 1.935 itens)
```
11099 | TUBO OROTRAQUEAL SEM BALAO POLIVINIL 5,5MM  -> sugestão: TUBO ENDOTRAQUEAL
11098 | TUBO OROTRAQUEAL SEM BALAO POLIVINIL 4,0MM  -> sugestão: TUBO ENDOTRAQUEAL
11097 | TUBO OROTRAQUEAL COM BALAO POLIVINIL 8,5MM  -> sugestão: TUBO ENDOTRAQUEAL
11096 | TUBO OROTRAQUEAL COM BALAO POLIVINIL 8,0MM  -> sugestão: TUBO ENDOTRAQUEAL
11095 | TUBO OROTRAQUEAL COM BALAO POLIVINIL 7,0MM  -> sugestão: TUBO ENDOTRAQUEAL
11093 | TUBO ENDOTRAQUEAL SEM BALONETE Nº 3.0        -> sugestão: TUBO ENDOTRAQUEAL
11092 | TUBO ENDOTRAQUEAL SEM BALONETE Nº 3,5        -> sugestão: TUBO ENDOTRAQUEAL
11091 | TUBO ENDOTRAQUEAL SEM BALONETE Nº 2,0        -> sugestão: TUBO ENDOTRAQUEAL
11090 | TUBO ENDOTRAQUEAL S/ BALONETE Nº 7,0         -> sugestão: TUBO ENDOTRAQUEAL
11089 | TUBO ENDOTRAQUEAL NO 6,0. COM CUFF           -> sugestão: TUBO ENDOTRAQUEAL
11088 | TUBO ENDOTRAQUEAL NO 10, 2,0MM               -> sugestão: TUBO ENDOTRAQUEAL
11087 | TUBO ENDOTRAQUEAL COM BALONETE Nº 7,5        -> sugestão: TUBO ENDOTRAQUEAL
11086 | TUBO ENDOTRAQUEAL COM BALONETE Nº 6,5        -> sugestão: TUBO ENDOTRAQUEAL
11085 | TUBO ENDOTRAQUEAL COM BALONETE Nº 5,5        -> sugestão: TUBO ENDOTRAQUEAL
11084 | TUBO ENDOTRAQUEAL C/ BALAO TAM 9,0           -> sugestão: TUBO ENDOTRAQUEAL
11078 | TENA SLIP NOTURNA - FRALDA GERIATRICA HIPOALERGÊNICA -> sugestão: FRALDA GERIATRICA
11077 | TENA SLIP NOTURNA - FRALDA GERIATRICA HIPOALERGÊNICA -> sugestão: FRALDA GERIATRICA
11063 | SONDA FOLLEY Nº 12 2 VIAS                    -> sugestão: SONDA FOLLEY N12 DUAS VIAS
11059 | SONDA DE FOLLEY Nº 24 2 VIAS                 -> sugestão: SONDA FOLLEY 2 VIAS C/ BALAO N. 22  ⚠ tamanho diferente
11058 | SONDA DE FOLLEY Nº 22 2 VIAS                 -> sugestão: SONDA FOLLEY 2 VIAS C/ BALAO N. 22
11057 | SONDA DE FOLLEY Nº 18 2 VIAS                 -> sugestão: SONDA FOLLEY 2 VIAS C/ BALAO N. 18
11056 | SONDA DE FOLLEY Nº 14 2 VIAS                 -> sugestão: SONDA FOLLEY N12 DUAS VIAS ⚠ tamanho diferente
11040 | SERINGA DOSADORA DESCARTAVEL ESTERIL 10ML    -> sugestão: SERINGA 10ML
11039 | SERINGA DESCARTAVEL ESTERIL 5ML C/ AGULHA    -> sugestão: SERINGA DESCARTAVEL ESTERIL 10ML C/ AGULHA ⚠ volume diferente
11038 | SERINGA DESCARTAVEL ESTERIL 3ML C/ AGULHA    -> sugestão: SERINGA DESCARTAVEL ESTERIL 10ML C/ AGULHA ⚠ volume diferente
11036 | SERINGA DESCARTAVEL ESTERIL 20ML C/ AGULHA   -> sugestão: SERINGA 20ML
11024 | PULSEIRA DE IDENTIFICACAO VERMELHA           -> sugestão: PULSEIRA VERMELHA - COM INSCRICAO (ALERGIA)
11008 | PAPEL GRAU CIRURGICO C/FILME 450MM X 100MTS  -> sugestão: PAPEL GRAU CIRURGICO 300MM X 100MTS ⚠ medida diferente
11007 | PAPEL GRAU CIRURGICO C/FILME 250MM X 100MTS  -> sugestão: PAPEL GRAU CIRURGICO 300MM X 100MTS ⚠ medida diferente
11006 | PAPEL GRAU CIRURGICO C/FILME 150MM X 100MTS  -> sugestão: PAPEL GRAU CIRURGICO 300MM X 100MTS ⚠ medida diferente
```
Os itens marcados com ⚠ são casos reais em que a sugestão automática (fuzzy match `token_set_ratio >= 92`) aproxima produtos com **volume/tamanho/medida diferentes** (ex.: seringa de 5ML sendo sugerida como 10ML; sonda Foley Nº14 sugerida como Nº12; papel grau cirúrgico de 150mm sugerido como 300mm). Isso confirma na prática o risco descrito abaixo — a sugestão automática não deve ser aplicada às cegas em lote.

## Riscos

- **Corrigir fabricante errado**: 70,9% dos produtos ativos não têm fabricante. Qualquer correção em lote por padrão de texto pode atribuir fabricante incorreto a itens genéricos (ex.: "SERINGA DESCARTAVEL 20ML" pode ter múltiplos fabricantes reais).
- **Cascata excessiva**: a opção "semelhante" recalcula todos os produtos ativos por similaridade textual; se aplicada sem revisão, pode propagar um SKU Master errado para dezenas de produtos de uma vez (o preview existe exatamente para mitigar isso — deve ser sempre usado antes de salvar).
- **Descrição parecida mas produto diferente**: confirmado nos exemplos acima (⚠) — a sugestão automática por `fuzz.token_set_ratio >= 92` ignora diferenças de volume/tamanho/medida quando o restante do texto é muito similar. Aplicar essas sugestões em lote sem checagem manual pode fundir produtos que são, na prática, itens distintos (ex.: seringa 5ML ≠ 10ML).
- **Atualizar `produto_padrao` indevidamente**: mitigado — o campo não está na whitelist `campos_editaveis`, portanto está protegido contra escrita acidental pela Auditoria SKU Master atual. Deve continuar assim.
- **Duplicidade residual**: mesmo após corrigir os 147 grupos 100% duplicados hoje identificados, novas duplicatas podem surgir por diferenças mínimas de digitação (acentuação, abreviação) que a comparação por igualdade exata não captura — só a comparação fuzzy (já usada para sugestão) pegaria esses casos, com o mesmo risco de falso positivo acima.

## Plano acelerado recomendado

1. **SKU-LOTE-01** — corrigir fabricantes problemáticos conhecidos. Como não há mais códigos inválidos isolados (`UN`/`SR`/`MD`), esta fase deve ser redefinida para focar em preencher fabricante ausente nos casos de maior confiança (ex.: produto já com SKU Master definido e fabricante identificável por descrição), sempre com revisão amostral antes de aplicar.
2. **SKU-LOTE-02** — consolidar as 147 duplicatas 100% iguais (457 produtos), começando pelos maiores grupos (11x, 10x, 9x) listados acima, com preview de cascata obrigatório antes de cada salvamento.
3. **SKU-LOTE-03** — aplicar cascata apenas nos grupos de **alta confiança** (mesma medida/volume/tamanho no texto, não apenas score fuzzy alto) — excluir explicitamente os casos como os marcados com ⚠ acima.
4. **SKU-LOTE-04** — revisar as pendências sem SKU Master (6.256), priorizando os 792 com prefixo `SKU PENDENTE` (indicam produto nunca padronizado desde a importação).
5. **SKU-LOTE-05** — teste final e relatório de cobertura (recontagem das mesmas métricas deste relatório para medir evolução).

## Recomendação final

**APTO_PARA_CORRECAO_EM_LOTES_CONTROLADOS**

O módulo está funcionalmente pronto (busca, edição, cascata com preview, exportação, proteção de `produto_padrao`) e os números estão claros. A ressalva é que os lotes de correção devem tratar a sugestão automática de cascata como um **ponto de partida para revisão humana**, não como aplicação automática, dado o risco concreto identificado (fusão de produtos com volume/tamanho diferentes).
