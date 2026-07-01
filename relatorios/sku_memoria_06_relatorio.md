# SKU-MEMORIA-06 — Novo lote de pesquisa e aprovação SKU_MASTER

## Objetivo
Pesquisar/enriquecer três pendências reais identificadas na revisão visual pós-aplicação do primeiro lote (`HEPTRIS 20MG`, `RINOSORO FR 30ML GOTA SOL NASAL`, `CLORETO DE SODIO 0,9% FR SPRAY NASAL JET`), cruzar com o banco real e preparar uma nova planilha de aprovação manual — **sem alterar o banco e sem aplicar nenhum SKU_MASTER nesta fase**.

## Termos pesquisados
1. `HEPTRIS 20MG`
2. `RINOSORO FR 30ML GOTA SOL NASAL`
3. `CLORETO DE SODIO 0,9% FR SPRAY NASAL JET`
4. `CLORETO DE SODIO 0,9% SPRAY NASAL JET`
5. `RINOSORO GOTAS 30ML`
6. `SORO FISIOLOGICO NASAL GOTAS 30ML`

## Fontes usadas
Todas públicas, gratuitas, sem login/paywall/captcha:
- Bula profissional/paciente do fabricante **Viatris/Mylan** (HEPTRIS)
- Farmácias online: Sampharma, Farmasilva, Drogal, Farma22, Preço Popular, Drogasil, Drogaria Catarinense, Farma Ponte, Ultrafarma, Drogaria Nova Esperança, Araújo

Nenhuma fonte bloqueou o acesso; nenhuma fonte paga ou API paga foi usada.

## Resultados encontrados

| Termo | Status | SKU_MASTER sugerido |
|---|---|---|
| HEPTRIS 20MG | ENCONTRADO_UNICO | ENOXAPARINA SODICA 20MG/0,2ML |
| RINOSORO FR 30ML GOTA SOL NASAL | ENCONTRADO_UNICO | SORO FISIOLOGICO NASAL GOTAS 0,9% 30ML |
| CLORETO DE SODIO 0,9% FR SPRAY NASAL JET | PENDENTE_REVISAO | (sem sugestão — volume ausente) |
| CLORETO DE SODIO 0,9% SPRAY NASAL JET | PENDENTE_REVISAO | (sem sugestão — volume ausente) |
| RINOSORO GOTAS 30ML | ENCONTRADO_UNICO | SORO FISIOLOGICO NASAL GOTAS 0,9% 30ML |
| SORO FISIOLOGICO NASAL GOTAS 30ML | ENCONTRADO_UNICO | SORO FISIOLOGICO NASAL GOTAS 0,9% 30ML |

Detalhamento completo (com URLs reais) em `relatorios/sku_memoria_06_pesquisa_pendencias.csv`.

### HEPTRIS 20MG
Confirmado por bula oficial do fabricante (Viatris/Mylan) e por duas farmácias públicas: enoxaparina sódica 20mg em seringa preenchida de 0,2ml, mesmo padrão proporcional já validado para 40/60/80mg (`1mg = 0,01ml`). `sku_master_sugerido = ENOXAPARINA SODICA 20MG/0,2ML`.

### RINOSORO FR 30ML GOTA SOL NASAL
Confirmado por 5 farmácias públicas diferentes (pesquisado com dois termos distintos para reforçar confiança): cloreto de sódio 9,0mg/ml (0,9%) + cloreto de benzalcônio 0,1mg/ml, gotas, frasco 30ml, sem vasoconstritor. Esta é uma **apresentação diferente** (gotas, 30ml) da já validada `RINOSORO 0,9% SPRAY 100ML` — por isso recebe seu próprio `sku_master_sugerido = SORO FISIOLOGICO NASAL GOTAS 0,9% 30ML`, não reaproveita o SKU do spray.

### CLORETO DE SODIO 0,9% FR/SPRAY NASAL JET
A pesquisa confirma que a marca comercial associada ao termo "JET" é quase certamente **Nasojet**, mas revela um problema real: **Nasojet 0,9% existe em pelo menos duas apresentações de volume — 50ml e 100ml** (fontes: Ultrafarma para 50ml; Drogaria Nova Esperança e Araújo para 100ml "jato forte"). Como a descrição de origem não especifica o volume, **não é seguro decidir automaticamente** qual apresentação está sendo referida. Seguindo a regra explícita desta fase, o status é `PENDENTE_REVISAO`, sem `sku_master_sugerido`, até que o volume seja confirmado por outra via (ex.: cruzamento com nota fiscal/preço do fornecedor, ou revisão manual do produto físico).

## Casos bloqueados
Nenhum bloqueio por concentração divergente (10%/20%/3%/0,09%) foi necessário nesta rodada — nenhum dos termos pesquisados retornou uma concentração diferente de 0,9%/9mg/ml. As únicas restrições aplicadas foram por **volume ausente** (`CLORETO DE SODIO ... JET`), não por conflito de concentração.

## Produtos do banco relacionados (somente leitura)
Cruzamento contra `banco/medbox_v3.db` (`mode=ro`) usando os termos `HEPTRIS 20`, `RINOSORO`, `GOTA`, `GOTAS`, `NASAL`, `JET`, `SPRAY`, `CLORETO DE SODIO 0,9` — os últimos 5 termos, usados isoladamente, retornaram entre 54 e 246 produtos (a maioria irrelevante, ex.: "JET" aparece em "INJETAVEL", "PROJETOR"). Após filtrar apenas os candidatos realmente relacionados às 3 pendências pesquisadas, restaram **6 produtos**:

| produto_id | Descrição | Status |
|---:|---|---|
| 266 | ENOXAPARINA SODICA 20MG/0,2ML HEPTRIS 20MG/0,2ML ... | MATCH_MEMORIA_VALIDADA |
| 3905 | HEPTRIS 20 MG SOL INJ CT 10 SER ... (bruto) | MATCH_MEMORIA_VALIDADA |
| 1727 | RINOSORO FR 30ML GOTA SOL NASAL (CLORETO D | MATCH_MEMORIA_VALIDADA |
| 5287 | SKU PENDENTE - RINOSORO FR 30M GOTASOL NASAL (CLORETOD COSMED | MATCH_MEMORIA_VALIDADA |
| 10676 | CLORETO DE SODIO 0,9%, FR SPRAY NASAL JET | PENDENTE_REVISAO |
| 9601 | CLORETO DE SODIO 9MG\ML VIA NASAL SPRAY ADULTO\INFANTIL MARCA | PENDENTE_REVISAO |

Nota: `8549, 8592, 9031, 9275` (também "CLORETO DE SODIO ... NASAL ... SPRAY") já foram corrigidos no lote anterior (`SKU-MEMORIA-05B`) e não aparecem aqui por já terem `sku_master` preenchido.

Detalhamento completo em `relatorios/sku_memoria_06_previa_matches_banco.csv`.

## Quantidade de linhas na planilha de aprovação
`relatorios/sku_memoria_06_aprovacao_manual.xlsx`, aba `APROVACAO_SKU`: **6 linhas** — 4 candidatos seguros (`MATCH_MEMORIA_VALIDADA`) e 2 pendências relevantes para revisão humana (`PENDENTE_REVISAO`, sem SKU_MASTER pronto, incluídas para que o usuário decida `REVISAR` ou `REJEITAR` — nunca `APROVAR` sem confirmar o volume antes). Coluna `decisao_usuario` com lista suspensa (`APROVAR`/`REJEITAR`/`REVISAR`) e formatação condicional dinâmica, mesmo padrão da planilha do primeiro lote. Aba `INSTRUCOES` inclui um aviso específico sobre as 2 linhas pendentes.

## Confirmações de segurança
- Banco (`banco/medbox_v3.db`) acessado somente em modo leitura (`mode=ro`); nenhum `UPDATE`/`DELETE`/`INSERT` foi executado.
- Nenhum SKU_MASTER foi aplicado.
- Nenhuma cascata automática foi executada.
- `app.py`, `templates/` e `core/` não foram alterados.
- Dicionário Mestre MEDREG e Bionexo não foram tocados.
- Nenhum scraping agressivo, captcha, login ou Cloudflare foi contornado; nenhuma fonte ou API paga foi usada.

## Recomendação final
**APTO_PARA_REVISAO_USUARIO**

Os 4 candidatos seguros (HEPTRIS 20mg × 2 produtos, RINOSORO gotas × 2 produtos) estão prontos para aprovação manual, seguindo exatamente o mesmo padrão validado no primeiro lote. As 2 linhas pendentes (`CLORETO DE SODIO ... JET`/`SPRAY` sem volume) precisam de confirmação adicional antes de qualquer aplicação — não devem ser aprovadas nesta rodada.
