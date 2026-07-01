# Metodologia Global SKU_MASTER MEDBOX

## Objetivo
SKU_MASTER **não é** cópia da descrição original do fornecedor, apenas limpa de ruído textual. SKU_MASTER é uma **descrição reduzida, padronizada e comercialmente útil**, que representa o princípio ativo/produto real por trás de qualquer nome comercial, abreviação ou variação de digitação — mantendo apenas os atributos que efetivamente diferenciam um produto do outro.

Essa mudança de paradigma vale para **todos os produtos** do catálogo, não apenas para os exemplos validados abaixo: qualquer nome comercial, marca ou descrição de fornecedor deve ser reduzido ao produto/princípio ativo padronizado, preservando apenas o que diferencia (concentração, volume, via, forma, tamanho, calibre, número, apresentação essencial), e descartando o que é ruído (marca, fabricante, redundância, texto comercial).

## Ordem de decisão
Ao padronizar um produto para SKU_MASTER, a decisão deve seguir esta ordem de prioridade:

1. **Memória validada pelo usuário** — se a descrição (ou uma equivalente) já foi validada manualmente (ver `exemplos_validados_sku_master.csv`), reutilizar o SKU_MASTER validado, sem reprocessar.
2. **Equivalência já encontrada em busca anterior** — se o robô/processo de enriquecimento já identificou este produto (mesmo nome comercial, mesmo registro) em uma busca anterior, reutilizar o mesmo SKU_MASTER já atribuído.
3. **Regra comercial MedBox** — aplicar as regras de família cadastradas (`regras_familias_sku_master.csv`), que mapeiam termos de entrada (nomes comerciais, sinônimos, princípios ativos) para o SKU base da família.
4. **Busca externa para enriquecer nome comercial** — quando o produto tem nome comercial mas não há regra de família nem memória, buscar externamente (bulário, ANVISA, dicionário de medicamentos) para identificar o princípio ativo e converter para o padrão.
5. **Assinatura técnica** — quando não há nome comercial reconhecível, extrair a assinatura técnica do texto (produto + concentração/dose + volume/medida) para montar o SKU_MASTER.
6. **Similaridade textual** — como último recurso automatizável, usar comparação de similaridade (fuzzy matching) contra produtos já padronizados, sempre sujeita aos bloqueios críticos abaixo.
7. **Revisão humana** — quando nenhuma das etapas anteriores resolve com segurança, ou quando um bloqueio crítico é acionado, o produto fica pendente de revisão manual — nunca recebe um SKU_MASTER "chutado".

## Regra de redução
O SKU_MASTER deve manter **apenas os atributos que diferenciam o produto** de outro produto real e distinto:

- princípio ativo ou produto padrão (ex.: "SORO FISIOLOGICO", "ENOXAPARINA SODICA");
- concentração/dose (ex.: "0,9%", "40MG");
- volume/tamanho/calibre/número (ex.: "1000ML", "Nº 12", "18G");
- via/forma quando diferencia (ex.: "NASAL SPRAY" vs. injetável);
- apresentação quando diferencia (ex.: "30 SACHES + FRASCO 240ML");
- kit/acessório quando faz parte essencial do item (ex.: soro com sistema de administração próprio).

## O que remover quando for ruído
Os elementos abaixo **não** devem compor o SKU_MASTER quando forem apenas ruído textual, redundância ou informação comercial sem valor de diferenciação:

- marca/nome comercial (ex.: "HEPTRIS", "CLEXANE", "NASOJET" saem do SKU_MASTER, mas continuam registrados no campo `marca`);
- fabricante;
- "adulto"/"infantil" quando não diferencia produto real (ex.: quando o item é o mesmo princípio ativo/dose e só muda o público em rótulo comercial, sem mudança técnica real);
- a palavra "marca";
- a palavra "genérico";
- "ou similar";
- forma redundante (repetição do mesmo termo em sequência);
- embalagem/caixa quando não define o SKU (ex.: "CX C/50" quando a unidade de venda real é por item, não por caixa);
- "seringa preenchida" quando for característica padrão da apresentação (ver regra específica abaixo).

### Regra específica: "seringa preenchida"
"Seringa preenchida" **não** deve entrar automaticamente no SKU_MASTER apenas por estar na descrição do fornecedor. Só deve ser mantida no SKU_MASTER quando ela **diferencia** o produto de outra apresentação real do mesmo princípio ativo/dose (por exemplo, quando existem no catálogo tanto a apresentação em seringa preenchida quanto em frasco-ampola do mesmo princípio ativo e dose, e é necessário distinguir as duas). Quando a seringa preenchida é a única forma de apresentação existente para aquele item (ou seja, é característica padrão, não diferenciadora), ela deve ser tratada como ruído e removida.

### Regra específica: nome comercial como SKU_MASTER final
Nome comercial/marca **não deve** virar SKU_MASTER final, **salvo se**:
- o produto realmente for identificado comercialmente por esse nome no mercado (isto é, não existe um princípio ativo/produto padronizável equivalente e reconhecido), **e**
- não houver princípio ativo/produto padronizável aplicável.

Nesses casos excepcionais, o nome comercial pode permanecer como SKU_MASTER, mas isso deve ser tratado como exceção documentada, não como regra geral.

## Bloqueios críticos
Nunca reaproveitar/propagar um SKU_MASTER de um produto para outro se qualquer um dos atributos abaixo for diferente entre eles:

- concentração;
- dose;
- volume;
- via;
- forma;
- tamanho;
- calibre;
- número;
- quantidade de sachês, quando faz parte do produto;
- kit/acessório essencial;
- apresentação que diferencia.

Esses bloqueios têm prioridade sobre qualquer score de similaridade textual — um texto muito parecido não autoriza cascata se um desses atributos divergir (ver também `relatorios/sku_lote_01_regras_bloqueio_cascata.md`, que detalha o mesmo princípio para a fase de consolidação de duplicatas).

## Exemplos validados pelo usuário

| Descrição original | SKU_MASTER correto |
|---|---|
| CLORETO DE SODIO 0,9% 1000ML | SORO FISIOLOGICO 0,9% 1000ML |
| CLORETO DE SODIO 9MG/ML VIA NASAL SPRAY 50ML | SORO FISIOLOGICO NASAL SPRAY 0,9% 50ML |
| NASOJET ALTO FLUXO 30 SACHES + FRASCO 240ML | SORO FISIOLOGICO NASAL ALTO FLUXO 30 SACHES + FRASCO 240ML |
| HEPTRIS 40MG | ENOXAPARINA SODICA 40MG/0,4ML |
| VERSA 80MG | ENOXAPARINA SODICA 80MG/0,8ML |
| NOXX 60MG | ENOXAPARINA SODICA 60MG/0,6ML |

Lista completa e estruturada em `exemplos_validados_sku_master.csv`.

## Regra de memória
Se um produto novo bater com um produto já validado — seja por nome comercial idêntico, assinatura técnica equivalente (mesmo princípio ativo + dose + volume) ou equivalência já confirmada em busca externa anterior — o sistema deve **repetir o SKU_MASTER já validado**, em vez de recalcular do zero. Isso garante consistência e evita que o mesmo produto comercial receba SKU_MASTER diferentes em momentos diferentes.

## Regra de marca e categoria

### Marca
- Se o produto **não tiver marca preenchida**: usar a marca/nome comercial coletada na pesquisa externa ou enriquecimento, quando disponível e confiável.
- Se **não houver marca confiável**: manter o campo vazio para revisão humana — nunca inventar ou inferir marca sem confiança.

### Categoria
- Se o produto **não tiver categoria preenchida** e for medicamento: preencher como `MEDICAMENTOS`.
- Se **não for medicamento**: preencher como `CORRELATOS`.
- Regra padrão: tudo que não for identificado como medicamento deve cair em `CORRELATOS`.

### Atenção — separação de responsabilidades entre campos
- A marca coletada **não deve substituir** o SKU_MASTER — ela fica exclusivamente no campo `marca`.
- O SKU_MASTER **continua reduzido e padronizado** (princípio ativo/produto + atributos diferenciadores), independentemente da marca identificada.
- A categoria serve para **classificar** o produto (`MEDICAMENTOS` vs. `CORRELATOS`), não para alterar o nome do SKU_MASTER.

### Exemplos
| Descrição original | SKU_MASTER | Marca | Categoria |
|---|---|---|---|
| HEPTRIS 40MG | ENOXAPARINA SODICA 40MG/0,4ML | HEPTRIS | MEDICAMENTOS |
| VERSA 80MG | ENOXAPARINA SODICA 80MG/0,8ML | VERSA | MEDICAMENTOS |
| NASOJET ALTO FLUXO | SORO FISIOLOGICO NASAL ALTO FLUXO 30 SACHES + FRASCO 240ML | NASOJET | MEDICAMENTOS |
| SERINGA DESCARTAVEL 10ML | (mantém descrição técnica reduzida, sem princípio ativo comercial) | — | CORRELATOS |
| EQUIPO MACROGOTAS | (mantém descrição técnica reduzida) | — | CORRELATOS |

## Quando exigir revisão humana
A padronização deve parar e aguardar revisão humana (nunca aplicar automaticamente) quando:

- o nome comercial tem múltiplas apresentações possíveis e não é possível determinar qual sem mais dados;
- o volume está ausente na descrição de origem;
- a concentração está ausente na descrição de origem;
- a marca está associada a mais de um produto/princípio ativo diferente;
- há conflito entre fontes (ex.: busca externa diverge da memória validada);
- a descrição está incompleta a ponto de não permitir identificar o produto com segurança;
- a similaridade textual é alta, mas algum atributo crítico (ver "Bloqueios críticos") é diferente.

## Relação com fases anteriores
Esta metodologia complementa (não substitui) o trabalho já feito nas fases `SKU-PENDENCIAS-01` e `SKU-LOTE-01`: aquelas fases tratavam de **consolidar duplicatas textuais exatas** dentro do que já existe no banco; esta metodologia define **como qualquer descrição nova ou existente deve ser reduzida** ao SKU_MASTER correto, incluindo casos de nome comercial que não são capturados pela comparação de texto puro.
