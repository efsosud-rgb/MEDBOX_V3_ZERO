# SKU-METODOLOGIA-GLOBAL-01 — Metodologia global de padronização SKU_MASTER

## Objetivo
Registrar a mudança de paradigma na padronização do SKU_MASTER, validada pelo usuário durante revisão manual, e preparar a base de memória/regras/script de diagnóstico necessária para aplicá-la — **sem alterar banco, sem aplicar SKU_MASTER em massa e sem integrar nada na tela ainda**.

## Mudança de paradigma
Até a fase `SKU-LOTE-01`, o trabalho de padronização tratava o SKU_MASTER como uma versão **limpa** da descrição original (remover ruído textual, mas manter a estrutura da frase do fornecedor). A validação do usuário nesta fase mostra que isso é insuficiente: o SKU_MASTER precisa ser uma **redução real ao produto/princípio ativo comercialmente reconhecido**, mesmo quando a descrição de origem usa um nome comercial completamente diferente do princípio ativo (ex.: `HEPTRIS 40MG` não é parecido textualmente com `ENOXAPARINA SODICA 40MG/0,4ML`, mas é o mesmo produto).

Isso significa que a padronização não pode depender só de comparação textual/fuzzy — precisa de uma camada de **conhecimento de domínio** (memória validada + regras de família + busca externa), com a comparação textual entrando apenas como último recurso, sempre sujeita aos mesmos bloqueios críticos já usados na fase `SKU-LOTE-01`.

## Por que a lógica vale para todos os produtos
Os exemplos validados (soro fisiológico, soro fisiológico nasal, soro fisiológico nasal alto fluxo, enoxaparina) não são casos especiais — são a prova de conceito de um padrão que se repete em todo o catálogo: qualquer princípio ativo genérico tem múltiplos nomes comerciais (marcas), e qualquer produto padrão (soro, seringa, sonda) tem variações de descrição por fornecedor. A metodologia documentada em `data/dicionario_mestre/interno/metodologia_global_sku_master.md` generaliza a regra para qualquer produto do catálogo, não apenas para os exemplos citados.

## Exemplos de redução

| Descrição original (fornecedor) | SKU_MASTER (produto real) | O que foi removido | O que foi mantido |
|---|---|---|---|
| CLORETO DE SODIO 0,9% 1000ML | SORO FISIOLOGICO 0,9% 1000ML | nome químico substituído pelo nome comercial padrão | concentração (0,9%) e volume (1000ML) |
| CLORETO DE SODIO 9MG/ML VIA NASAL SPRAY 50ML | SORO FISIOLOGICO NASAL SPRAY 0,9% 50ML | unidade de concentração convertida (9MG/ML = 0,9%) | via/forma (nasal spray) e volume |
| NASOJET ALTO FLUXO 30 SACHES + FRASCO 240ML | SORO FISIOLOGICO NASAL ALTO FLUXO 30 SACHES + FRASCO 240ML | marca comercial "NASOJET" (vai para o campo `marca`) | apresentação completa (alto fluxo, saches, frasco) |
| HEPTRIS 40MG | ENOXAPARINA SODICA 40MG/0,4ML | nome comercial "HEPTRIS" (vai para o campo `marca`) | princípio ativo + dose + volume proporcional |
| VERSA 80MG | ENOXAPARINA SODICA 80MG/0,8ML | nome comercial "VERSA" | princípio ativo + dose + volume proporcional |
| NOXX 60MG | ENOXAPARINA SODICA 60MG/0,6ML | nome comercial "NOXX" | princípio ativo + dose + volume proporcional |

## Importância da memória
Sem memória, cada novo lote reprocessaria os mesmos nomes comerciais do zero, com risco de gerar SKU_MASTER diferentes para o mesmo produto em momentos diferentes (ex.: `HEPTRIS 40MG` virar `ENOXAPARINA SODICA 40MG/0,4ML` em um lote e `ENOXAPARINA 40MG` em outro). A ordem de decisão da metodologia coloca a memória validada pelo usuário e as equivalências já encontradas em buscas anteriores **antes** de qualquer regra automática ou busca externa nova, garantindo consistência e economia de esforço.

## Limites de segurança
- Nenhuma correção foi aplicada ao banco nesta fase — apenas documentação, memória e um script de diagnóstico que roda contra arquivos CSV locais, sem conexão com `banco/medbox_v3.db`.
- A metodologia mantém os mesmos **bloqueios críticos** já definidos em `relatorios/sku_lote_01_regras_bloqueio_cascata.md` (concentração, dose, volume, via, forma, tamanho, calibre, número, sachês, kit/acessório, apresentação): nenhuma equivalência é aplicada automaticamente se um desses atributos divergir.
- O script de teste (`scripts/dicionario_mestre/testar_metodologia_global_sku_master.py`) confirma esse comportamento na prática: `CLORETO DE SODIO 10% 10ML` e `CLORETO DE SODIO 20% 10ML` **não** foram convertidos para `SORO FISIOLOGICO` (que só vale para 0,9%) — corretamente marcados como `PENDENTE_REVISAO`, evitando o erro de tratar uma solução hipertônica como se fosse soro fisiológico comum.
- `PRODUTO DESCONHECIDO XYZ` (sem memória, sem regra de família) também cai em `PENDENTE_REVISAO` — o sistema nunca inventa um SKU_MASTER quando não tem base segura.

## Regra de marca e categoria

### Marca
- Produto sem marca preenchida: usar a marca/nome comercial coletado em pesquisa externa ou enriquecimento, quando disponível e confiável.
- Sem marca confiável disponível: manter o campo vazio para revisão humana.

### Categoria
- Produto sem categoria preenchida e identificado como medicamento: `MEDICAMENTOS`.
- Produto não identificado como medicamento: `CORRELATOS` (regra padrão — tudo que não é medicamento é CORRELATOS).

### Separação de responsabilidades
- A marca coletada **não substitui** o SKU_MASTER — fica exclusivamente no campo `marca`.
- O SKU_MASTER continua reduzido e padronizado, independente da marca.
- A categoria classifica o produto; não altera o nome do SKU_MASTER.

### Exemplos
| Descrição original | SKU_MASTER | Marca | Categoria |
|---|---|---|---|
| HEPTRIS 40MG | ENOXAPARINA SODICA 40MG/0,4ML | HEPTRIS | MEDICAMENTOS |
| VERSA 80MG | ENOXAPARINA SODICA 80MG/0,8ML | VERSA | MEDICAMENTOS |
| NASOJET ALTO FLUXO | SORO FISIOLOGICO NASAL ALTO FLUXO 30 SACHES + FRASCO 240ML | NASOJET | MEDICAMENTOS |
| SERINGA DESCARTAVEL 10ML | (descrição técnica reduzida, sem princípio ativo comercial) | — | CORRELATOS |
| EQUIPO MACROGOTAS | (descrição técnica reduzida) | — | CORRELATOS |

## Resultado dos testes (script de diagnóstico)
11 descrições testadas contra a memória validada e as regras de família, sem acessar o banco:

| Status | Quantidade | Casos |
|---|---:|---|
| OK_MEMORIA_VALIDADA | 6 | CLORETO DE SODIO 0,9% 1000ML, CLORETO DE SODIO 9MG/ML NASAL SPRAY 50ML, HEPTRIS 40MG, VERSA 80MG, NOXX 60MG, CLEXANE 40MG |
| OK_REGRA_FAMILIA | 1 | NASOJET ALTO FLUXO 30 SACHES FRASCO 240ML |
| PENDENTE_REVISAO | 4 | NASOJET (isolado, sem apresentação), CLORETO DE SODIO 10% 10ML, CLORETO DE SODIO 20% 10ML, PRODUTO DESCONHECIDO XYZ |

Saída completa em `relatorios/sku_metodologia_global_01_teste.csv`.

## Próximos passos
1. Ampliar `regras_familias_sku_master.csv` com mais famílias conforme o usuário validar novos exemplos (não automatizar sem validação).
2. Avaliar integração da busca externa (bulário/ANVISA) como fonte de enriquecimento para produtos sem memória nem regra de família — ainda como etapa de sugestão, não de aplicação automática.
3. Só depois de um volume razoável de famílias validadas, avaliar integração deste motor de sugestão na tela de Auditoria SKU Master (fora do escopo desta fase — **não integrar ainda na tela**).
4. Aplicar a metodologia como critério de priorização nos próximos lotes de correção (`SKU-LOTE-02` em diante), sempre com revisão manual antes de salvar.

## Recomendação final
A metodologia e a base de memória/regras estão prontas para uso como **apoio à decisão humana** na tela de Auditoria SKU Master. Nenhuma integração automática foi feita — a aplicação continua manual, produto a produto ou em lotes pequenos com revisão, como nas fases anteriores.
