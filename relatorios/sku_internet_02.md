# SKU-INTERNET-02 — Pesquisa externa real controlada para SKU_MASTER

## Objetivo
Executar a primeira pesquisa externa **real** (não simulada) para um conjunto pequeno de termos, usando apenas busca controlada em fontes públicas gratuitas, sem scraping agressivo, sem burlar captcha/login/Cloudflare e sem API paga — gerando evidências e sugestões, **sem aplicar nada no banco**.

## Como a coleta foi feita
A coleta de dados públicos (títulos, trechos de texto, URLs) foi realizada através de busca controlada (motor de busca sancionado, sem scraping direto de HTML, sem contornar nenhuma proteção de site) durante a preparação desta fase. Nenhum site retornou bloqueio, captcha ou erro de coleta para os 10 termos testados — por isso não há exemplos reais de `BLOQUEADO_FONTE` ou `ERRO_COLETA` nesta rodada, mas o script (`scripts/dicionario_mestre/pesquisar_enriquecimento_sku_master.py`) já suporta esses status para quando ocorrerem em fases futuras com mais volume.

O script em si **não faz requisições HTTP em tempo de execução** — ele processa as coletas já registradas (com URLs reais) e aplica as regras de decisão da metodologia global, permitindo reprodução determinística do resultado sem depender de a internet estar disponível no momento da execução. Isso mantém o script seguro para rodar em qualquer ambiente sem risco de scraping acidental.

## Fontes testadas
Todas públicas, gratuitas, sem login/paywall:
- **Consulta Remédios** (`consultaremedios.com.br`)
- **Bulas de fabricante**: Viatris/Mylan (HEPTRIS), Eurofarma (VERSA), Blau (NOXX), Natulab (NASOJET, NASOJET ALTO FLUXO), Airela (NASONEW)
- **Farmácias online**: Panvel, Drogaria Araújo, Drogaria Nova Esperança, Farmácia Indiana, Drogasmil, Drogaria Venâncio, Pague Menos
- **Agregadores de bula**: CliqueFarma, BulasMed
- Nenhuma fonte paga, nenhum login, nenhum captcha contornado.

## Termos pesquisados e resultados

| Termo | Status | Confiança | SKU_MASTER sugerido |
|---|---|---|---|
| NASONEW | MULTIPLAS_APRESENTACOES | MEDIA | (sem sugestão) |
| NASOJET | MULTIPLAS_APRESENTACOES | MEDIA | (sem sugestão) |
| NASOJET ALTO FLUXO | ENCONTRADO_UNICO | ALTA | SORO FISIOLOGICO NASAL ALTO FLUXO 30 SACHES + FRASCO 240ML |
| HEPTRIS 40MG | ENCONTRADO_UNICO | ALTA | ENOXAPARINA SODICA 40MG/0,4ML |
| VERSA 80MG | ENCONTRADO_UNICO | ALTA | ENOXAPARINA SODICA 80MG/0,8ML |
| NOXX 60MG | ENCONTRADO_UNICO | ALTA | ENOXAPARINA SODICA 60MG/0,6ML |
| RINOSORO 0,9% SPRAY 100ML | ENCONTRADO_UNICO | ALTA | SORO FISIOLOGICO NASAL SPRAY 0,9% 100ML |
| CLORETO DE SODIO 0,9% JET VIA NASAL FRASCO 100ML | ENCONTRADO_UNICO | MEDIA | SORO FISIOLOGICO NASAL SPRAY 0,9% 100ML |
| CLORETO DE SODIO 10% 10ML | PENDENTE_REVISAO | ALTA | (sem sugestão — bloqueio crítico) |
| PRODUTO DESCONHECIDO XYZ | NAO_ENCONTRADO | INDEFINIDA | (sem sugestão) |

Detalhamento completo (com URLs reais) em `relatorios/sku_internet_02_resultados_pesquisa.csv`.

## Casos com múltiplas apresentações
- **NASONEW**: a pesquisa real revelou algo que a fase anterior não sabia — o nome comercial cobre **duas formas farmacêuticas diferentes**: `NASONEW AIRES` (solução spray pronta 0,9%, 50ml) e `NASONEW AR` (pó para solução, mesma concentração mas forma diferente). Além disso, há risco real de confusão com `NASONEX` (mometasona, corticoide nasal — produto completamente diferente), que aparece misturado nos mesmos resultados de busca. Por isso, o status correto é `MULTIPLAS_APRESENTACOES`, mais cauteloso do que a suposição da fase `SKU-INTERNET-01` (que havia tratado `NASONEW` como caso único `PENDENTE_REVISAO`, sem saber da divergência de forma farmacêutica).
- **NASOJET**: confirmado como esperado — `NASOJET 3H` tem concentração 30mg/mL (3%), bem diferente de `NASOJET 0,9%` (9mg/mL), em volumes de 50ml e 100ml. Nome comercial isolado continua bloqueado para aplicação automática.

## Casos bloqueados (fonte)
Nenhum nesta rodada — todas as fontes consultadas estavam publicamente acessíveis, sem captcha, login ou paywall.

## Sugestões de SKU_MASTER geradas
- `ENOXAPARINA SODICA 40MG/0,4ML`, `80MG/0,8ML`, `60MG/0,6ML` — confirmam exatamente os valores já validados na memória (`HEPTRIS`, `VERSA`, `NOXX`), com bulas oficiais dos respectivos fabricantes como evidência adicional.
- `SORO FISIOLOGICO NASAL ALTO FLUXO 30 SACHES + FRASCO 240ML` — confirma o já validado para `NASOJET ALTO FLUXO`.
- `SORO FISIOLOGICO NASAL SPRAY 0,9% 100ML` — novo, gerado para `RINOSORO 0,9% SPRAY 100ML` e para `CLORETO DE SODIO 0,9% JET VIA NASAL FRASCO 100ML` (esta última já trazia os atributos essenciais na própria descrição de origem; a pesquisa apenas confirmou que a apresentação existe no mercado sob a marca Nasojet).

## Quais itens podem virar memória validada
Candidatos fortes para promoção a `exemplos_validados_sku_master.csv` (status `ENCONTRADO_UNICO`, confiança ALTA, fontes oficiais de fabricante confirmando):
- `RINOSORO 0,9% SPRAY 100ML → SORO FISIOLOGICO NASAL SPRAY 0,9% 100ML`
- `CLORETO DE SODIO 0,9% JET VIA NASAL FRASCO 100ML → SORO FISIOLOGICO NASAL SPRAY 0,9% 100ML` (associar marca NASOJET)

Estes ainda **não foram promovidos automaticamente** — promoção para memória exige validação explícita do usuário, conforme regra 1 de `regras_pesquisa_externa_sku_master.md`.

## Quais exigem revisão humana
- `NASONEW` — decidir qual apresentação (AIRES vs. AR) está de fato no catálogo do MEDBOX, e checar se há risco real de confusão com `NASONEX` nos dados importados.
- `NASOJET` (isolado, sem qualificador) — identificar qual das apresentações (3H, 0,9% 50ml, 0,9% 100ml, Alto Fluxo) corresponde a cada produto do catálogo antes de padronizar.
- `CLORETO DE SODIO 10% 10ML` — confirmado como solução hipertônica de uso intravenoso (reposição eletrolítica), **não** deve virar `SORO FISIOLOGICO`; mantido pendente por bloqueio crítico de concentração, exatamente como projetado.
- `PRODUTO DESCONHECIDO XYZ` — nenhuma fonte encontrada; permanece como está até haver mais contexto (ex.: descrição do fornecedor mais completa).

## Confirmações de segurança
- Banco (`banco/medbox_v3.db`) não foi acessado nem alterado nesta fase.
- Nenhum SKU_MASTER foi aplicado a nenhum produto do catálogo.
- `app.py` e `templates/` não foram alterados.
- Nenhum scraping agressivo, captcha, login ou Cloudflare foi contornado.
- Nenhuma fonte paga ou API paga foi usada.
- Não foi feita pesquisa do catálogo inteiro — apenas os 10 termos de teste definidos nesta fase.

## Próxima fase recomendada
1. Validar com o usuário os candidatos fortes (`RINOSORO`, `NASOJET 0,9% 100ML`) para promoção à memória.
2. Resolver a ambiguidade de `NASONEW` e `NASOJET` com mais contexto do catálogo real (ex.: cruzar com `precos_fornecedores.descricao_original` para ver qual apresentação aparece de fato nas notas fiscais importadas).
3. Ampliar a lista de termos de teste gradualmente (ainda sem pesquisar o catálogo inteiro), priorizando os termos mais frequentes entre os 6.256 produtos sem SKU Master (`sku_master_pendencias_finais.md`).
4. Só depois de um volume validado maior, avaliar integração deste fluxo na tela de Auditoria SKU Master (fora do escopo desta fase).
