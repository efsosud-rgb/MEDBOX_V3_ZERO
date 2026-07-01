# SKU-MEMORIA-02 — Promoção de candidatos fortes da pesquisa externa para memória validada

## Objetivo
Promover para memória validada (`data/dicionario_mestre/interno/memoria_equivalencias_sku_master.csv`) os candidatos fortes encontrados na pesquisa externa real controlada da fase `SKU-INTERNET-02`, e manter explicitamente bloqueados os casos ambíguos ou de bloqueio crítico — **sem alterar o banco, sem aplicar SKU_MASTER e sem integrar nada na tela**.

## Base analisada
`relatorios/sku_internet_02_resultados_pesquisa.csv` (10 termos pesquisados na fase anterior, commit `b9d7d81`).

## Registros promovidos (status `VALIDADO_USUARIO`)
Seis registros foram promovidos para `data/dicionario_mestre/interno/memoria_equivalencias_sku_master.csv`, todos com `fonte_origem = PESQUISA_EXTERNA_CONTROLADA`, `confianca = ALTA`, `validado_por = USUARIO` e `data_validacao = 2026-07-01`:

| Descrição normalizada | SKU_MASTER definido | Marca | Categoria |
|---|---|---|---|
| HEPTRIS 40MG | ENOXAPARINA SODICA 40MG/0,4ML | HEPTRIS | MEDICAMENTOS |
| VERSA 80MG | ENOXAPARINA SODICA 80MG/0,8ML | VERSA | MEDICAMENTOS |
| NOXX 60MG | ENOXAPARINA SODICA 60MG/0,6ML | NOXX | MEDICAMENTOS |
| NASOJET ALTO FLUXO | SORO FISIOLOGICO NASAL ALTO FLUXO 30 SACHES + FRASCO 240ML | NASOJET | MEDICAMENTOS |
| RINOSORO 0,9% SPRAY 100ML | SORO FISIOLOGICO NASAL SPRAY 0,9% 100ML | RINOSORO | MEDICAMENTOS |
| CLORETO DE SODIO 0,9% JET VIA NASAL FRASCO 100ML | SORO FISIOLOGICO NASAL SPRAY 0,9% 100ML | NASOJET (JET) | MEDICAMENTOS |

Cada registro mantém a URL da fonte que embasou a decisão (bula oficial de fabricante ou página pública de farmácia consistente com múltiplas fontes), preservando rastreabilidade: qualquer sugestão pode ser auditada e revertida se a fonte se mostrar incorreta depois. `HEPTRIS`, `VERSA` e `NOXX` já estavam em `exemplos_validados_sku_master.csv` desde a fase `SKU-METODOLOGIA-GLOBAL-01` — a promoção aqui reforça esses três com evidência de fonte externa oficial, sem duplicar ou contradizer a memória anterior. `NASOJET ALTO FLUXO` também já estava validado; os outros dois (`RINOSORO`, `CLORETO DE SODIO 0,9% JET...`) são registros novos nesta memória de equivalências.

## Registros que permanecem bloqueados (não promovidos)

| Termo | Motivo do bloqueio |
|---|---|
| NASONEW (isolado) | `MULTIPLAS_APRESENTACOES` — o nome comercial cobre pelo menos duas formas farmacêuticas diferentes (`NASONEW AIRES`, solução spray pronta, e `NASONEW AR`, pó para solução), confirmadas por bulas oficiais do mesmo fabricante (Airela). Promover um SKU único agora arriscaria aplicar a forma errada a um produto real. Há ainda risco adicional de confusão com o produto de nome semelhante `NASONEX` (mometasona, corticoide nasal — produto totalmente diferente), que aparece misturado nos resultados de busca. |
| NASOJET (isolado) | `MULTIPLAS_APRESENTACOES` — confirmado por pesquisa real que `NASOJET 3H` tem concentração 30mg/mL (3%, descongestionante) enquanto `NASOJET 0,9%` tem 9mg/mL (0,9%, isotônico), em volumes de 50ml e 100ml — produtos clinicamente diferentes sob a mesma marca. Sem um qualificador adicional na descrição de origem (como "ALTO FLUXO" ou "0,9%" + volume), não é seguro decidir automaticamente qual apresentação está sendo referida. |
| CLORETO DE SODIO 10% 10ML | Bloqueio crítico de concentração — confirmado por fonte oficial (BulasMed / Consulta Remédios) que a solução a 10% é hipertônica, de uso intravenoso, indicada como fonte de eletrólitos e base para soluções parenterais — **clinicamente diferente** do Soro Fisiológico 0,9%. Reaproveitar o SKU_MASTER da família `SORO FISIOLOGICO` para este produto seria um erro grave de padronização (mistura duas classes terapêuticas diferentes). A metodologia global e as regras de bloqueio crítico (`SKU-LOTE-01`, `SKU-METODOLOGIA-GLOBAL-01`) já prevêem exatamente este tipo de caso. |
| PRODUTO DESCONHECIDO XYZ | `NAO_ENCONTRADO` — nenhuma fonte pública relevante encontrada na pesquisa real; não há base para propor qualquer SKU_MASTER. |

Nenhum desses quatro casos foi inserido em `memoria_equivalencias_sku_master.csv`. Eles continuam registrados apenas em `relatorios/sku_internet_02_resultados_pesquisa.csv`, com seus status originais (`MULTIPLAS_APRESENTACOES`, `PENDENTE_REVISAO`, `NAO_ENCONTRADO`), aguardando informação adicional (ex.: qualificador de apresentação na descrição do fornecedor) antes de qualquer nova tentativa de resolução.

## Confirmações de segurança
- Banco (`banco/medbox_v3.db`) não foi acessado nem alterado nesta fase.
- Nenhum SKU_MASTER foi aplicado a nenhum produto do catálogo — a promoção afeta apenas o arquivo de memória local, usado como referência para decisões futuras (manuais ou assistidas), nunca como gravação automática.
- Nenhuma cascata automática foi executada.
- `app.py` e `templates/` não foram alterados; nada foi integrado à tela.
- Não foi feita nova pesquisa ao catálogo inteiro — esta fase apenas processou o resultado já coletado na fase `SKU-INTERNET-02`.

## Próxima fase recomendada
1. Ampliar a coleta com qualificadores adicionais para `NASONEW` e `NASOJET` (ex.: cruzar com `precos_fornecedores.descricao_original` no banco para descobrir se essas descrições completas — com volume/forma/apresentação — já aparecem nas notas fiscais importadas, o que resolveria a ambiguidade sem nova pesquisa externa).
2. Considerar promover `NASONEW AIRES` e `NASOJET 0,9%`/`NASOJET 3H` como entradas de memória separadas (uma por apresentação real), assim que a descrição de origem trouxer o qualificador necessário.
3. Seguir o plano acelerado já traçado (`SKU-LOTE-02` em diante) usando a memória agora ampliada como apoio à revisão manual.
