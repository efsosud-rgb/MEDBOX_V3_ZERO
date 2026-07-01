# Plano de Pesquisa Externa para SKU_MASTER

## Objetivo
Definir como e quando o processo de padronização SKU_MASTER deve recorrer a pesquisa externa (internet) para identificar o princípio ativo/produto real por trás de um nome comercial, quando a memória local (`exemplos_validados_sku_master.csv`) e as regras de família (`regras_familias_sku_master.csv`) não forem suficientes para decidir com segurança.

A pesquisa externa é o **quarto passo** na ordem de decisão definida em `metodologia_global_sku_master.md`: só entra em ação depois de memória validada, equivalência já encontrada e regra comercial MedBox — e sempre produz uma **sugestão**, nunca uma aplicação automática no banco.

## Quando pesquisar
Pesquisar externamente somente quando:
- a descrição contém um nome comercial (ou termo) que não está em `exemplos_validados_sku_master.csv`;
- o nome/termo não corresponde a nenhum `termos_entrada` já cadastrado em `regras_familias_sku_master.csv`;
- não há assinatura técnica suficiente na própria descrição de origem para montar o SKU_MASTER sem ambiguidade (ex.: falta princípio ativo, concentração ou apresentação reconhecível).

Não pesquisar quando a memória ou uma regra de família já resolvem o caso com segurança — pesquisa externa é custosa e deve ser o último recurso automatizável antes da revisão humana.

## Quais fontes usar
Fontes públicas, gratuitas, sem necessidade de login/captcha/paywall:
- Google (busca manual ou controlada, sem scraping agressivo do resultado);
- sites de farmácias (páginas de produto público);
- Consulta Remédios;
- bulas oficiais (bulário eletrônico, PDFs públicos de fabricante);
- sites oficiais de fabricantes;
- ANVISA / Bulário Eletrônico, quando aplicável;
- CMED (tabela de preços de medicamentos), quando aplicável;
- catálogos públicos de fabricantes;
- páginas públicas de fornecedores/distribuidores.

Fontes pagas, com login obrigatório, ou que exijam contornar captcha/Cloudflare/limite de acesso **não devem ser usadas** — nem manual, nem automaticamente.

## Como coletar dados
Para cada termo pesquisado, extrair (quando disponível na fonte):
- nome comercial;
- princípio ativo;
- concentração;
- forma farmacêutica;
- via de administração;
- volume;
- apresentação (embalagem, quantidade, kit);
- marca/fabricante;
- URL da fonte consultada;
- data da coleta.

Cada achado é registrado como uma linha em `modelo_enriquecimento_externo_sku_master.csv`, nunca aplicado diretamente ao banco.

## Como avaliar confiança
Níveis de confiança sugeridos para o campo `confianca` do modelo de enriquecimento:
- **ALTA**: fonte oficial (bula, ANVISA, CMED, site do fabricante) com todos os atributos essenciais (princípio ativo, concentração, apresentação) presentes e uma única apresentação identificada.
- **MEDIA**: fonte secundária (farmácia, Consulta Remédios) confirmando os mesmos dados que uma fonte primária, ou fonte primária com algum atributo essencial ausente.
- **BAIXA**: apenas uma fonte secundária, sem confirmação cruzada, ou dados parcialmente incompletos.
- **INDEFINIDA**: nenhuma fonte confiável encontrada, ou fontes conflitantes entre si.

## Quando sugerir automaticamente
A sugestão de SKU_MASTER só pode ser proposta como `ENCONTRADO_UNICO` (pronta para revisão rápida e aplicação manual) quando, simultaneamente:
- confiança ALTA ou MEDIA;
- uma única apresentação/concentração/volume identificada para o termo pesquisado;
- nenhum atributo crítico (concentração, volume, forma, via) ausente;
- nenhuma divergência entre fontes consultadas.

## Quando exigir revisão humana
Marcar como `PENDENTE_REVISAO` (ou `MULTIPLAS_APRESENTACOES` / `CONFLITO_FONTES` / `NAO_ENCONTRADO`, conforme o caso) quando:
- o termo pesquisado tiver **múltiplas apresentações possíveis** (ex.: `NASOJET` pode ser `NASOJET 9MG/ML SPRAY 50ML`, `NASOJET ALTO FLUXO 30 SACHES + FRASCO 240ML` ou `NASOJET 3H 30MG/ML` — três produtos diferentes sob o mesmo nome comercial);
- faltar concentração ou volume na fonte encontrada;
- houver conflito entre fontes (uma fonte diz uma concentração, outra diz outra);
- nenhuma fonte confiável for encontrada (`NAO_ENCONTRADO`);
- a confiança for BAIXA ou INDEFINIDA.

Nesses casos, o robô **nunca decide sozinho** — o registro fica disponível para decisão humana na tela de Auditoria (quando integrado, fora do escopo desta fase).

## Como alimentar a memória de equivalências
Quando um enriquecimento é **validado pelo usuário** (campo `validado_por_usuario` = sim, status muda para `VALIDADO_USUARIO`), o par `termo_pesquisa → sku_master_sugerido` deve ser promovido para `exemplos_validados_sku_master.csv` (ou para uma nova entrada em `regras_familias_sku_master.csv`, se representar uma família inteira, não um único produto). Isso garante que a mesma pesquisa não precise ser refeita: da próxima vez, o passo 1 da ordem de decisão (memória validada) resolve o caso sem nova pesquisa externa.

## Como evitar risco de produto errado
- Nunca aplicar um enriquecimento com status diferente de `ENCONTRADO_UNICO` ou `VALIDADO_USUARIO`.
- Nunca aplicar cascata/propagação baseada em um enriquecimento externo sem revisão humana prévia (mesmo bloqueio crítico já usado nas fases `SKU-LOTE-01` e `SKU-METODOLOGIA-GLOBAL-01`: concentração, dose, volume, via, forma, tamanho, calibre, número, sachês, kit/apresentação).
- Nunca tratar um nome comercial com apresentações múltiplas conhecidas (como `NASOJET`) como se tivesse uma única resposta — cada apresentação real deve virar uma família/regra própria, nunca uma média ou "melhor achute".
- Registrar sempre a URL/fonte da coleta, para que qualquer sugestão possa ser auditada e revertida se a fonte se mostrar errada depois.
- Marca pesquisada nunca substitui o SKU_MASTER — vai para o campo `marca`; categoria pesquisada classifica o produto (`MEDICAMENTOS`/`CORRELATOS`), nunca altera o nome do SKU_MASTER (mesma regra de `metodologia_global_sku_master.md`).

## Limites de execução automatizada nesta fase
Nesta fase (`SKU-INTERNET-01`) não é feita nenhuma pesquisa real na internet. O que existe é: (1) o modelo de dados para registrar resultados de pesquisa (`modelo_enriquecimento_externo_sku_master.csv`), (2) as regras que governam o fluxo (`regras_pesquisa_externa_sku_master.md`) e (3) um script de diagnóstico que **simula** o fluxo de decisão usando exemplos já preenchidos no CSV modelo, sem acessar rede. A execução de pesquisa real (scraping controlado, respeitando robots.txt e limites de cada site) fica para uma fase futura, com escopo e autorização própria.
