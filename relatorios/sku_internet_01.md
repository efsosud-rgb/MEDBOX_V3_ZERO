# SKU-INTERNET-01 — Planejamento do motor controlado de pesquisa externa para SKU_MASTER

## Objetivo
Planejar a camada de pesquisa/enriquecimento externo que falta na metodologia global de padronização SKU_MASTER (`SKU-METODOLOGIA-GLOBAL-01`), definindo estrutura de dados, regras de segurança e um script de diagnóstico que simula o fluxo de decisão — **sem acessar a internet, sem alterar o banco, sem aplicar SKU_MASTER e sem integrar nada na tela nesta fase**.

## Por que a internet é necessária
A memória local (`exemplos_validados_sku_master.csv`) e as regras de família (`regras_familias_sku_master.csv`) só cobrem os produtos que já foram vistos e validados manualmente. O catálogo do MEDBOX tem 6.256 produtos ativos sem SKU Master (ver `sku_master_pendencias_finais.md`), muitos identificados apenas por nome comercial (marca) sem indicação do princípio ativo na descrição do fornecedor. Sem uma fonte externa, esses produtos ficariam permanentemente sem padronização — o robô não tem como "adivinhar" que `HEPTRIS` é `ENOXAPARINA SODICA` sem alguma fonte externa (ou validação humana prévia) que faça essa ligação uma vez.

## Como ela será usada
A pesquisa externa entra como o **quarto passo** da ordem de decisão da metodologia global — só é usada quando memória e regras de família não resolvem o caso. O fluxo planejado:

1. Termo não resolvido por memória/regra de família → candidato a pesquisa externa.
2. Pesquisa (fase futura) consulta fontes públicas e gratuitas (Google, farmácias, Consulta Remédios, bulas, sites de fabricante, ANVISA/Bulário, CMED, catálogos de fabricante) — nunca fontes pagas, nunca contornando login/captcha/Cloudflare/limite de acesso.
3. Resultado é registrado em `modelo_enriquecimento_externo_sku_master.csv`, com nível de confiança e status.
4. Se resultado é único e confiável (`ENCONTRADO_UNICO`) → vira sugestão pronta para revisão manual rápida na tela de Auditoria (quando integrado).
5. Se resultado é ambíguo (`MULTIPLAS_APRESENTACOES`, `PENDENTE_REVISAO`, `CONFLITO_FONTES`, `NAO_ENCONTRADO`) → fica bloqueado para aplicação automática, aguardando decisão humana.
6. Quando o usuário valida uma sugestão, ela é promovida para a memória (`VALIDADO_USUARIO`) e nunca mais precisa ser pesquisada de novo.

Detalhamento completo em `data/dicionario_mestre/externo/plano_pesquisa_externa_sku_master.md` e `data/dicionario_mestre/interno/regras_pesquisa_externa_sku_master.md`.

## Por que não aplicar direto
Um nome comercial pode representar mais de um produto real. O caso mais claro levantado nesta fase é `NASOJET`, que sozinho pode ser:
- `NASOJET 9MG/ML SPRAY 50ML`;
- `NASOJET ALTO FLUXO 30 SACHES + FRASCO 240ML`;
- `NASOJET 3H 30MG/ML`.

Três produtos diferentes (volume, apresentação e possivelmente concentração diferentes) sob o mesmo nome comercial. Se o robô aplicasse automaticamente "a primeira resposta do Google" como SKU_MASTER, o risco de fundir produtos diferentes seria alto — o mesmo problema já identificado e documentado nas fases `SKU-LOTE-01` (cascata perigosa) e `SKU-METODOLOGIA-GLOBAL-01` (bloqueios críticos). Por isso, toda vez que uma pesquisa (real ou simulada) encontra múltiplas apresentações possíveis, o status obrigatório é `MULTIPLAS_APRESENTACOES` e nenhuma sugestão única é proposta.

## Como a memória será alimentada
Toda sugestão de pesquisa externa que o usuário valida deixa de precisar de nova pesquisa: o par `termo_pesquisa → sku_master_sugerido` é promovido para `exemplos_validados_sku_master.csv` (produto específico) ou para uma nova família em `regras_familias_sku_master.csv` (quando representa um padrão reutilizável, como aconteceu com `ENOXAPARINA`). Isso garante que o mesmo nome comercial não seja pesquisado nem decidido duas vezes, e que a base de conhecimento cresça de forma auditável — cada entrada de memória carrega o motivo da decisão.

## Exemplos NASONEW / NASOJET / HEPTRIS / VERSA / NOXX
Registrados em `data/dicionario_mestre/interno/modelo_enriquecimento_externo_sku_master.csv` (7 linhas), com o cuidado explícito de **não afirmar fonte definitiva** quando nenhuma URL foi realmente coletada nesta fase:

| Termo | Status | Observação |
|---|---|---|
| NASONEW | PENDENTE_REVISAO | Dado citado pelo usuário na conversa (`CLORETO DE SODIO 0,9% SPRAY 50ML`), sem URL coletada localmente — sugestão fica registrada, mas marcada como pendente de verificação real antes de qualquer aplicação. |
| NASOJET | MULTIPLAS_APRESENTACOES | Nome comercial com 3 apresentações conhecidas relatadas; nenhuma sugestão única de SKU_MASTER é proposta. |
| NASOJET ALTO FLUXO | VALIDADO_USUARIO | Já validado na fase `SKU-METODOLOGIA-GLOBAL-01`; reaproveitado da memória, sem necessidade de nova pesquisa. |
| HEPTRIS 40MG | VALIDADO_USUARIO | Já validado; reaproveitado da memória. |
| VERSA 80MG | VALIDADO_USUARIO | Já validado; reaproveitado da memória. |
| NOXX 60MG | VALIDADO_USUARIO | Já validado; reaproveitado da memória. |
| RINOSORO 0,9% SPRAY 100ML | PENDENTE_REVISAO | Nome comercial novo; atributos aparecem na própria descrição (0,9%, spray, 100ml), mas nenhuma pesquisa externa real foi feita — fica como candidato a nova família após confirmação. |

## Resultado da simulação de fluxo (script de diagnóstico)
O script `scripts/dicionario_mestre/testar_fluxo_pesquisa_externa_sku.py` simula a decisão para 7 entradas de teste, sem acessar internet nem banco, usando apenas os CSVs de memória e modelo de enriquecimento como fonte:

| Entrada | Ação | Status | SKU_MASTER sugerido |
|---|---|---|---|
| NASONEW | MARCAR_PENDENTE_REVISAO | PENDENTE_REVISAO | SORO FISIOLOGICO NASAL SPRAY 0,9% 50ML (não aplicar sem confirmar fonte) |
| NASOJET | BLOQUEAR_MULTIPLAS_APRESENTACOES | MULTIPLAS_APRESENTACOES | (sem sugestão) |
| NASOJET ALTO FLUXO | USAR_SUGESTAO_PESQUISA_EXTERNA | VALIDADO_USUARIO | SORO FISIOLOGICO NASAL ALTO FLUXO 30 SACHES + FRASCO 240ML |
| HEPTRIS 40MG | REUTILIZAR_MEMORIA_VALIDADA | VALIDADO_USUARIO | ENOXAPARINA SODICA 40MG/0,4ML |
| VERSA 80MG | REUTILIZAR_MEMORIA_VALIDADA | VALIDADO_USUARIO | ENOXAPARINA SODICA 80MG/0,8ML |
| NOXX 60MG | REUTILIZAR_MEMORIA_VALIDADA | VALIDADO_USUARIO | ENOXAPARINA SODICA 60MG/0,6ML |
| PRODUTO DESCONHECIDO XYZ | PESQUISAR_EXTERNAMENTE_FASE_FUTURA | NAO_ENCONTRADO | (sem sugestão) |

Saída completa em `relatorios/sku_internet_01_fluxo_simulado.csv`. O resultado confirma o comportamento esperado: produtos já validados são reaproveitados sem nova pesquisa; nomes comerciais ambíguos (`NASOJET`) são bloqueados; nomes sem qualquer informação disponível ficam explicitamente marcados para pesquisa externa futura, sem inventar resposta.

## Próxima fase recomendada
1. Implementar a pesquisa externa real (fase futura, escopo próprio), respeitando `robots.txt`, limites de acesso de cada site e as restrições desta fase (sem scraping agressivo, sem captcha/login/Cloudflare, sem fontes pagas).
2. Popular `modelo_enriquecimento_externo_sku_master.csv` com resultados reais e URLs verificadas, substituindo os registros `PENDENTE_REVISAO` desta fase (`NASONEW`, `RINOSORO`) assim que houver confirmação.
3. Resolver a ambiguidade de `NASOJET`, cadastrando cada apresentação real (`NASOJET SPRAY`, `NASOJET ALTO FLUXO`, `NASOJET 3H`) como entradas de memória ou família próprias, após validação do usuário.
4. Só depois de acumular um volume razoável de enriquecimentos validados, avaliar integração deste fluxo na tela de Auditoria SKU Master (fora do escopo desta fase — **não integrar ainda na tela**).
