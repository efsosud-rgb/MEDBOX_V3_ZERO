# Regras de Pesquisa Externa para SKU_MASTER

Estas regras governam como qualquer resultado de pesquisa externa (internet) pode ser usado no processo de padronização SKU_MASTER. Elas complementam `metodologia_global_sku_master.md` e `plano_pesquisa_externa_sku_master.md`, e têm precedência sobre qualquer sugestão automática.

## Regras obrigatórias

1. **Memória validada pelo usuário tem prioridade absoluta.** Se o termo pesquisado já existe em `exemplos_validados_sku_master.csv` ou corresponde a uma família em `regras_familias_sku_master.csv`, não é necessário (nem permitido, para evitar inconsistência) pesquisar de novo — reutilizar o SKU_MASTER já validado.

2. **Busca externa não altera o banco.** Nenhum resultado de pesquisa externa grava diretamente em `banco/medbox_v3.db`. Toda pesquisa produz, no máximo, uma linha em `modelo_enriquecimento_externo_sku_master.csv` (ou equivalente), à espera de aplicação manual futura pela tela de Auditoria.

3. **Busca externa gera sugestão, não aplicação.** O resultado de uma pesquisa é sempre um candidato a `sku_master_sugerido`, nunca um valor gravado automaticamente no campo `produtos.sku_master`.

4. **Múltiplas apresentações bloqueiam aplicação automática.** Se o termo pesquisado corresponder a mais de uma apresentação real (ex.: `NASOJET` → spray comum, alto fluxo, ou "3H"), o status deve ser `MULTIPLAS_APRESENTACOES` e nenhuma sugestão única de SKU_MASTER pode ser proposta para aplicação — cada apresentação deve ser resolvida individualmente, com informação adicional que identifique qual delas está sendo padronizada.

5. **Concentração ou volume ausente exige revisão.** Se a fonte encontrada não informar concentração ou volume (quando esses atributos são relevantes ao produto), o status deve ser `PENDENTE_REVISAO` — nunca preencher esses campos com suposição.

6. **Divergência de concentração, volume, forma ou via bloqueia reaproveitamento.** Se o produto sendo padronizado tiver algum desses atributos diferente do que foi encontrado na pesquisa (ou entre duas fontes), o SKU_MASTER da pesquisa não pode ser reaproveitado — mesmo bloqueio crítico usado em `SKU-LOTE-01` e na metodologia global.

7. **Marca pesquisada vai para o campo `marca`, nunca para o SKU_MASTER.** Um nome comercial encontrado na pesquisa (ex.: "NASONEW", "HEPTRIS") preenche `produtos_marca`/`marca` no modelo de enriquecimento; o `sku_master_sugerido` deve conter o produto/princípio ativo reduzido, não o nome comercial (salvo exceção documentada em `metodologia_global_sku_master.md`, quando não existe princípio ativo padronizável aplicável).

8. **Categoria pesquisada entra como `MEDICAMENTOS` ou `CORRELATOS`.** Nenhum outro valor de categoria deve ser sugerido a partir de pesquisa externa.

9. **Tudo que não for medicamento é `CORRELATOS`.** Regra padrão: na ausência de evidência de que o produto é um medicamento (princípio ativo, registro ANVISA, apresentação farmacêutica), a categoria sugerida é `CORRELATOS`.

10. **SKU_MASTER deve continuar reduzido e padronizado**, mesmo quando a pesquisa externa traz uma descrição rica em detalhes comerciais — a sugestão final segue a mesma regra de redução da metodologia global (manter apenas atributos que diferenciam: princípio ativo/produto, concentração/dose, volume/tamanho/calibre/número, via/forma quando diferencia, apresentação quando diferencia, kit/acessório essencial).

## Fluxo resumido de decisão para um termo pesquisado

1. Existe em memória validada? → usar SKU_MASTER da memória, `status = VALIDADO_USUARIO` (ou equivalente), sem pesquisa nova.
2. Existe em regra de família? → aplicar a regra, `status = OK_REGRA_FAMILIA`, sem pesquisa externa.
3. Não existe em nenhuma das duas → pesquisar externamente (fase futura; nesta fase apenas se simula o fluxo).
4. Resultado da pesquisa tem uma única apresentação, todos os atributos essenciais presentes, confiança ALTA/MEDIA → `status = ENCONTRADO_UNICO`, sugestão pronta para revisão manual rápida.
5. Resultado ambíguo (múltiplas apresentações, atributo ausente, fontes conflitantes, nada encontrado, confiança BAIXA/INDEFINIDA) → `status = MULTIPLAS_APRESENTACOES` / `PENDENTE_REVISAO` / `CONFLITO_FONTES` / `NAO_ENCONTRADO`, conforme o caso — sempre bloqueado para aplicação automática.
6. Usuário revisa e valida → `status = VALIDADO_USUARIO`, promovido para a memória (`exemplos_validados_sku_master.csv` ou nova família em `regras_familias_sku_master.csv`).
