# SKU-MEMORIA-07 — Aplicação controlada do lote 06

## Objetivo
Validar a planilha revisada `sku_memoria_06_aprovacao_manual.xlsx` e aplicar no banco, com backup prévio e transação controlada, apenas as linhas seguras marcadas `APROVAR` — **sem cascata, sem sobrescrever marca/categoria já preenchidas**.

## Decisões encontradas na planilha

| Decisão | Quantidade |
|---|---:|
| APROVAR | 6 |
| REJEITAR | 0 |
| REVISAR | 0 |
| (vazio) | 0 |
| Inválida (fora da lista) | 0 |
| **Total de linhas** | **6** |

Formalmente, todas as 6 linhas foram marcadas `APROVAR`. **Porém, 2 delas foram bloqueadas nesta fase por inconsistência de dados**, detalhada abaixo — decisão tomada com base na regra explícita já fornecida pelo usuário ("os itens de CLORETO DE SODIO ... sem volume confirmado não devem ser aplicados").

## ⚠️ Anomalia detectada e ação tomada
Os produtos `10676` e `9601` (`CLORETO DE SODIO 0,9% FR SPRAY NASAL JET` e `CLORETO DE SODIO 9MG/ML VIA NASAL SPRAY`) têm status original `PENDENTE_REVISAO` — a pesquisa da fase `SKU-MEMORIA-06` não encontrou volume confiável para eles e **deixou `sku_master_sugerido` vazio de propósito**, exatamente para impedir aplicação automática.

Na planilha revisada, porém, o campo `sku_master_sugerido` dessas duas linhas aparece preenchido com `"SORO FISIOLOGICO NASAL GOTAS 0,9% 30ML"` — valor que não existe no CSV de origem (`sku_memoria_06_previa_matches_banco.csv`, onde o campo está vazio para essas duas linhas) e que, tecnicamente, está **errado** para esses produtos (eles são descritos como `SPRAY`, não `GOTAS`; a família de 30ml em gotas não tem relação direta com o volume desconhecido do spray). Tudo indica um efeito de autopreenchimento do Excel (a tabela do Excel sugere/repete o valor da célula da linha imediatamente acima — `RINOSORO ... GOTAS 30ML` — quando o usuário interage com a coluna), não uma decisão deliberada.

**Ação tomada**: essas 2 linhas foram tratadas como decisão inválida e **não foram aplicadas**, mesmo constando `APROVAR`. Isso segue diretamente a instrução já dada nesta mesma fase pelo usuário: itens de cloreto de sódio nasal sem volume confirmado não devem ser aplicados. Os dois produtos permanecem exatamente como estavam antes desta fase.

## Backup criado
`backups/medbox_v3_antes_sku_memoria_07_20260701_170900.db`
- Tamanho: 9.347.072 bytes.
- Verificado com `PRAGMA integrity_check` → `ok`, e contagem de produtos (11.105) confere com o banco antes da escrita.

## Total APROVAR (na planilha): 6
## Total aplicado: 4
## Total ignorado por REJEITAR/REVISAR/vazio: 0
## Total ignorado por decisão inválida (anomalia de dados): 2
## Total com erro: 0

A transação (`BEGIN`...`COMMIT`) processou apenas os 4 produtos validados como seguros e consistentes; nenhum erro ocorreu.

## Produtos aplicados

| produto_id | SKU_MASTER antes | SKU_MASTER depois | Marca | Categoria |
|---:|---|---|---|---|
| 266 | ENOXAPARINA SODICA 20MG | ENOXAPARINA SODICA 20MG/0,2ML | preservada (VIATRIS) | preservada (MEDICAMENTOS) |
| 3905 | (bruto, não padronizado) | ENOXAPARINA SODICA 20MG/0,2ML | preenchida (HEPTRIS, estava vazia) | preservada ("MARCAS UQ", não padronizada) |
| 1727 | RINOSORO FR 30ML GOTA SOL NASAL | SORO FISIOLOGICO NASAL GOTAS 0,9% 30ML | preservada (COSMED) | preservada (MEDICAMENTOS) |
| 5287 | (vazio) | SORO FISIOLOGICO NASAL GOTAS 0,9% 30ML | preenchida (RINOSORO, estava vazia) | preservada ("MEDICAMENTOS \| SKU PENDENTE DE PADRONIZACAO", não padronizada) |

Todos os 4 tiveram `sku_corrigido` marcado como `1` e `corrigido_em` atualizado.

## Produtos ignorados

| produto_id | Motivo |
|---:|---|
| 10676 | Decisão `APROVAR` inconsistente com os dados de origem (ver anomalia acima); permanece sem SKU_MASTER, aguardando confirmação de volume |
| 9601 | Mesmo motivo; permanece sem SKU_MASTER |

## Marcas preenchidas
2 produtos, ambos com `HEPTRIS`/`RINOSORO` porque o campo estava vazio:
- `3905` → `HEPTRIS`
- `5287` → `RINOSORO`

## Categorias preenchidas
Nenhuma — todas as 4 categorias já estavam preenchidas (mesmo que com valores não padronizados em 2 casos).

## Marcas/categorias preservadas (não sobrescritas)
- **Marca**: `266` (`VIATRIS`) e `1727` (`COSMED`) já tinham marca preenchida — a sugestão da memória (`HEPTRIS`/`RINOSORO`, nome comercial correto) não foi aplicada; mesma pendência já registrada no lote anterior para casos análogos.
- **Categoria**: `3905` (`"MARCAS UQ"`) e `5287` (`"MEDICAMENTOS | SKU PENDENTE DE PADRONIZACAO"`) têm valores não padronizados, mas preenchidos — preservados sem alteração, candidatos a limpeza de dados futura.

## Confirmações
- **`produto_padrao` não foi alterado** em nenhum dos 6 produtos (aplicados ou ignorados) — verificado por comparação byte a byte pós-aplicação.
- **Cascata não foi usada** — cada produto foi atualizado individualmente.
- **Dicionário Mestre MEDREG não foi alterado.**
- **Bionexo não foi tocado.**
- `app.py`, `templates/` e `core/` não foram alterados.
- 6 registros criados em `auditoria_sku` (4 de `sku_master` + 2 de `marca`), com `origem_correcao = 'SKU-MEMORIA-07'`.
- `python -m py_compile app.py` executado com sucesso.

## Recomendação final
Os 4 produtos seguros foram padronizados com sucesso. Os 2 produtos de cloreto de sódio nasal seguem **pendentes** — recomenda-se que o usuário confirme o volume real (50ml ou 100ml) por outra via (ex.: nota fiscal do fornecedor, embalagem física) antes de uma nova tentativa de aprovação, e revise a planilha `sku_memoria_06_aprovacao_manual.xlsx` para corrigir o valor de `sku_master_sugerido` dessas duas linhas antes de reenviá-las para aprovação.
