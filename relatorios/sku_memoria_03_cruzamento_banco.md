# SKU-MEMORIA-03 — Cruzamento da memória validada com produtos reais do banco

## Objetivo
Cruzar os 6 registros de `data/dicionario_mestre/interno/memoria_equivalencias_sku_master.csv` com os produtos reais de `banco/medbox_v3.db`, gerando uma prévia de sugestões seguras — **sem aplicar nada, sem alterar o banco, sem cascata automática**.

## Método
Busca somente leitura (`sqlite3` em modo `mode=ro`) em `produtos.produto_padrao`, `produtos.sku_master` e `precos_fornecedores.descricao_original`, usando como palavras-chave os nomes comerciais/termos de cada entrada da memória (`HEPTRIS`, `VERSA`, `NOXX`, `NASOJET`, `RINOSORO`, `NASONEW`, `CLORETO DE SODIO`). Cada produto candidato foi então classificado manualmente contra os atributos da memória (concentração, volume, forma, via, apresentação), aplicando os mesmos bloqueios críticos já definidos em `metodologia_global_sku_master.md` e `regras_pesquisa_externa_sku_master.md`.

## Total de produtos analisados
- **106 linhas candidatas** localizadas por palavra-chave em produtos ativos (bruto, antes de filtrar falsos positivos): `HEPTRIS` 12, `VERSA` 24, `NOXX` 0, `NASOJET` 0, `NASONEW` 0, `RINOSORO` 2, `CLORETO DE SODIO` 68.
- `NOXX`, `NASOJET` e `NASONEW` não aparecem **em nenhum produto do banco**, ativo ou inativo — essas marcas ainda não têm produto correspondente importado sob esse nome exato no catálogo atual. Achado honesto, sem match forçado.
- De `VERSA` (24 hits), **23 eram falsos positivos** — a palavra "VERSA" aparecia apenas como substring de "UNIVERSAL" (ex.: `PONTEIRA UNIVERSAL`, `BOMBA DE INFUSAO UNIVERSAL`), sem relação com o medicamento. Apenas 1 produto real (`id 1946`) é o medicamento VERSA.
- De `CLORETO DE SODIO` (68 hits), **16 são relevantes ao escopo desta memória** (contexto nasal/JET/alto fluxo ou exemplos explícitos de bloqueio por concentração pedidos na regra 6); os outros 52 são soro fisiológico intravenoso/oral padrão, fora do escopo dos 6 registros específicos desta memória (não listados individualmente aqui — pertencem à família mais ampla `SORO FISIOLOGICO` de `regras_familias_sku_master.csv`, não a esta memória de equivalências pontuais).
- **31 produtos foram efetivamente classificados** e estão em `relatorios/sku_memoria_03_previa_matches_banco.csv`.

## Contagem por status

| Status | Quantidade |
|---|---:|
| MATCH_MEMORIA_VALIDADA | 5 |
| MATCH_ASSINATURA_TECNICA | 10 |
| BLOQUEADO_CONFLITO_ATRIBUTOS | 11 |
| PENDENTE_REVISAO | 3 |
| SEM_MATCH | 2 |
| **Total** | **31** |

**Total de matches seguros (MATCH_MEMORIA_VALIDADA + MATCH_ASSINATURA_TECNICA): 15**

## Exemplos encontrados

### Match direto com a memória (`MATCH_MEMORIA_VALIDADA`)
- `id 267, 2016, 3906, 4284`: produtos `HEPTRIS 40MG` reais no banco → `ENOXAPARINA SODICA 40MG/0,4ML`. Em vários deles o `sku_master` atual já está quase certo (`ENOXAPARINA SODICA 40MG`, faltando só o volume `/0,4ML`).
- `id 8592`: `CLORETO DE SODIO 0,9% JET VIA NASAL FRASCO 100ML` — descrição **idêntica** à entrada da memória, match perfeito.

### Match por assinatura técnica, marca diferente (`MATCH_ASSINATURA_TECNICA`)
Achado mais interessante desta fase: produtos com a marca **HEPTRIS** em doses 60mg e 80mg batem tecnicamente com as memórias validadas para **NOXX 60mg** e **VERSA 80mg** — porque o princípio ativo, a dose e o volume são idênticos, só a marca comercial muda.
- `id 268, 3907, 4283` (marca HEPTRIS, 60mg/0,6ml) → sugestão `ENOXAPARINA SODICA 60MG/0,6ML` (mesma memória de NOXX), mantendo **marca real do produto = HEPTRIS** (não NOXX).
- `id 269, 3908, 4285` (marca HEPTRIS, 80mg/0,8ml) → sugestão `ENOXAPARINA SODICA 80MG/0,8ML` (mesma memória de VERSA), marca real = HEPTRIS.
- `id 1946` (marca **VERSA**, 40mg/0,4ml) → sugestão `ENOXAPARINA SODICA 40MG/0,4ML` (mesma memória de HEPTRIS), marca real = VERSA.

Isso confirma na prática a regra 5 da metodologia global ("se o robô já encontrou uma equivalência em busca anterior, deve reutilizar o mesmo SKU_MASTER para produtos iguais/equivalentes") — o SKU_MASTER é o mesmo independente da marca; a marca real de cada produto é preservada no campo `marca`, nunca substituída.
- `id 8549, 9031, 9275`: variações de `CLORETO DE SODIO 0,9% ... NASAL ... 100ML` sem a palavra "JET", mas com concentração/via/volume idênticos → mesma sugestão `SORO FISIOLOGICO NASAL SPRAY 0,9% 100ML`, marca deixada vazia (o texto original só tem a palavra genérica "MARCA" como placeholder, não uma marca real).

### Bloqueados por conflito de atributos (`BLOQUEADO_CONFLITO_ATRIBUTOS`)
- `id 1727, 5287`: **RINOSORO em gotas, 30ML** — mesma marca da memória, mas forma (gotas) e volume (30ml) divergem do validado (spray, 100ml). Não deve herdar o SKU_MASTER do spray.
- `id 8674`: `CLORETO DE SODIO 0,9% SPRAY VIA NASAL FRASCO 50ML` — mesma concentração e via, mas volume 50ml diverge dos 100ml validados.
- `id 9274`: `CLORETO DE SODIO 3% HIPERTONICO SPRAY VIA NASAL FRASCO 50ML` — concentração 3% (hipertônico) diverge de 0,9%.
- `id 5393, 8958`: `CLORETO DE SODIO 6MG/G GEL NASAL` — forma gel diverge de spray.
- `id 9599`: `CLORETO DE SODIO 2.160G ... ENVELOPE 120 ENVELOPES` — peso por envelope bate com o sachê da memória `NASOJET ALTO FLUXO` (2,16g), mas a quantidade (120 envelopes) diverge da caixa validada (30 sachês) — bloqueio por quantidade de embalagem.
- `id 187, 6878, 8813`: exemplos explícitos de `CLORETO DE SODIO 10%`/`20%` — corretamente excluídos do match automático, confirmando a regra 6 desta fase com dados reais do banco (o `id 8813` já havia sido confirmado como bloqueio crítico na pesquisa externa da fase `SKU-INTERNET-02`).
- `id 4549`: **`SORO FISIOLOGICO 20% 10ML`** — caso de risco de dado contaminado: o nome do produto sugere concentração padrão (0,9%), mas a concentração real cadastrada é 20%. Não deve ser tratado como soro fisiológico comum.

### Pendente revisão (`PENDENTE_REVISAO`)
- `id 9601, 10676`: `CLORETO DE SODIO ... VIA NASAL SPRAY` (sem volume) e `CLORETO DE SODIO 0,9%, FR SPRAY NASAL JET` (sem volume) — concentração e via batem, mas falta o volume explícito para confirmar se é a apresentação de 100ml da memória. O `id 10676` é candidato forte (contém "JET"), mas segue a regra: não aplicar sem confirmar volume.
- `id 897`: `CLORETO DE SODIO 0,09% 500ML` — possível erro de digitação (0,09% em vez de 0,9%); não presumir automaticamente qual é o caso correto.

### Sem match nesta memória (`SEM_MATCH`)
- `id 266, 3905`: `HEPTRIS 20MG` — dose não coberta por nenhum dos 6 registros atuais da memória (que só cobre 40/60/80mg). Precisaria de nova pesquisa externa específica para 20mg antes de padronizar.

## Riscos
- **Marca não deve determinar o SKU_MASTER, mas confunde buscas ingênuas**: os casos `MATCH_ASSINATURA_TECNICA` (HEPTRIS 60/80mg, VERSA 40mg) mostram que uma busca só por nome comercial teria deixado esses produtos sem sugestão, ou pior, um cruzamento ingênuo por texto poderia ter sugerido o SKU errado se comparasse só a marca. A classificação por assinatura técnica (princípio + dose + volume) é essencial.
- **Campo "MARCA" genérico no texto de origem**: vários produtos de cloreto de sódio nasal têm literalmente a palavra "MARCA" no lugar de uma marca real (placeholder de importação) — tratado corretamente como marca vazia, não como o texto literal "MARCA".
- **Dado potencialmente contaminado**: `SORO FISIOLOGICO 20% 10ML` (id 4549) e `CLORETO DE SODIO 0,09% 500ML` (id 897) são exemplos reais de descrição que pode enganar um processo automático — nome sugere uma coisa, concentração cadastrada sugere outra. Reforça a necessidade de nunca aplicar por nome isolado.
- **Divergência de quantidade de embalagem**: `id 9599` mostra que mesmo quando o "peso por unidade" bate (2,16g), a quantidade total da caixa pode divergir (120 envelopes vs. 30 sachês) — outro tipo de bloqueio crítico que a metodologia já previa.
- **Marcas da memória ainda não usadas no catálogo**: `NOXX`, `NASOJET` e `NASONEW` não aparecem em nenhum produto real hoje — a memória está pronta, mas ainda não tem aplicação no catálogo atual (pode mudar em importações futuras).

## Confirmações de segurança
- Banco (`banco/medbox_v3.db`) acessado somente em modo leitura (`mode=ro`); nenhum `UPDATE`/`DELETE`/`INSERT` foi executado.
- Nenhum SKU_MASTER foi aplicado a nenhum produto.
- Nenhuma cascata automática foi executada.
- `app.py` e `templates/` não foram alterados; nada integrado à tela.
- Nenhuma pesquisa à internet foi feita nesta fase — apenas leitura do banco e da memória já validada.

## Recomendação final
**APTO_PARA_REVISAO_MANUAL** dos 15 matches seguros (`MATCH_MEMORIA_VALIDADA` + `MATCH_ASSINATURA_TECNICA`) antes de qualquer aplicação real via tela de Auditoria SKU Master. Os 11 bloqueados e 3 pendentes devem permanecer como estão até nova informação (pesquisa adicional ou confirmação humana). Os 2 `SEM_MATCH` (HEPTRIS 20mg) são candidatos para uma futura pesquisa externa pontual.
