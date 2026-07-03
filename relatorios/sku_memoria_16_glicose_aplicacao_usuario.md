# SKU-MEMORIA-16 — Aplicação GLICOSE por aprovação manual do usuário

## Regra de aprovação manual do usuário
> "Planilha revisada da Glicosado."

Conforme a regra global já estabelecida (mesma usada em `SKU-MEMORIA-10`/`12`/`14`): toda aplicação depende da aprovação manual do usuário na planilha; se `decisao_usuario = APROVAR`, aplica-se sem bloqueio semântico, mantendo apenas os bloqueios **técnicos** obrigatórios (decisão inválida, produto inexistente, SKU final vazio).

## Total de linhas e decisões

| Item | Quantidade |
|---|---:|
| Total de linhas na planilha | 34 |
| Total APROVAR | 34 |
| Total REJEITAR | 0 |
| Total REVISAR | 0 |
| Total vazio | 0 |
| Total inválido | 0 |
| Total apto para aplicar (validação técnica) | 34 |
| Total bloqueado técnico | 0 |

## O que o usuário efetivamente revisou
O usuário aprovou **todas as 34 linhas**, incluindo os itens antes classificados `ASSOCIADA_OUTRAS` e `PENDENTE_REVISAO`:

- **Padronização própria**: o usuário renomeou os grupos de `SOLUCAO GLICOSE X% YML` / `GLICOSE X% YML AMP` para o termo clínico consagrado `SORO GLICOSADO X% YML`, aplicado uniformemente a todos os 20 produtos originalmente `CANDIDATO_SEGURO`.
- **Bolsa unificada com frasco**: diferente da separação conservadora deste diagnóstico (que mantinha `BOLSA` como grupo distinto), o usuário optou por unificar os 2 produtos em bolsa (ids 6752 e 6753) nos mesmos grupos `SORO GLICOSADO 5% 250ML` e `SORO GLICOSADO 5% 500ML` — decisão editorial aceita sem julgamento semântico adicional, conforme a regra desta fase.
- **Pendências resolvidas**: os 2 produtos `PENDENTE_REVISAO` (ids 5975 e 5977, embalagem não explícita) foram aprovados como ampola, confirmando a suposição já levantada no relatório de diagnóstico (`SORO GLICOSADO 25% 10ML` e `SORO GLICOSADO 50% 10ML`).
- **Associados/outros aprovados com SKU_MASTER próprio**: os 10 produtos `ASSOCIADA_OUTRAS` (nutrição parenteral, anestésico com glicose, soro de reidratação oral, tiras/sensores de glicemia) foram aprovados com SKU_MASTER específico fornecido pelo usuário, sem misturar com glicose simples (ex.: `AMINOACIDOS + GLICOSE + ELETROLITOS NUTRICAO PARENTERAL 1000ML`, `SENSOR GLICOSE FREESTYLE LIBRE`, `TIRA TESTE GLICOSE HGT C/50`).

Nenhuma linha usou a coluna dedicada `sku_master_corrigido_usuario` (ficou vazia em todas) — a edição foi feita diretamente em `sku_master_sugerido_preliminar`, mesmo padrão observado nas fases anteriores. `marca_corrigida_usuario` também ficou vazia em todas as 34 linhas.

## Backup criado
`backups/medbox_v3_antes_sku_memoria_16_glicose_usuario_20260703_131506.db`
- Tamanho: 9.584.640 bytes.
- Verificado com `PRAGMA integrity_check` → `ok`, e contagem de produtos (11.105) confere com o banco antes da escrita.

## Total aplicado: 34
## Total ignorado: 0
## Total bloqueado técnico: 0
## Total com erro: 0

A transação (`BEGIN`...`COMMIT`) processou as 34 linhas em um único bloco; nenhum erro ocorreu, nenhum `ROLLBACK` foi necessário.

## Produtos aplicados
Todos os 34 produtos tiveram `sku_master` preenchido/atualizado (lista completa com antes/depois em `relatorios/sku_memoria_16_glicose_pos_aplicacao.csv`). Todos também tiveram `sku_corrigido` marcado como `1` e `corrigido_em` atualizado.

Exemplos de aplicação:
| produto_id | Descrição original | SKU_MASTER aplicado |
|---:|---|---|
| 5386, 6754, 7130, 8921, 5977 | variações "GLICOSE 50% ... 10ML (AMP)" | SORO GLICOSADO 50% 10ML |
| 5391, 6752, 7131, 10419, 10420 | variações "GLICOSE 5% ... 250ML" (frasco e bolsa) | SORO GLICOSADO 5% 250ML |
| 5746 | GLICOSE 750 MG/ML (75%) SOLUCAO INJETAVEL AMP. 10ML | SORO GLICOSADO 75% 10ML |
| 5824 | AMINOACIDOS + GLICOSE + ELETROLITOS CAPACIDADE PROXIMA DE 1000 ML | AMINOACIDOS + GLICOSE + ELETROLITOS NUTRICAO PARENTERAL 1000ML |
| 8115 | SENSOR DE GLICOSE FREESTYLE LIBRE | SENSOR GLICOSE FREESTYLE LIBRE |

## Produtos ignorados
Nenhum — todas as 34 linhas estavam marcadas `APROVAR` e passaram na validação técnica.

## Produtos bloqueados tecnicamente
Nenhum.

## Marcas aplicadas
Nenhuma — `marca_corrigida_usuario` estava vazia em todas as 34 linhas, então a marca atual de cada produto foi **preservada sem alteração**.

## Marcas que não puderam ser gravadas por limitação técnica
Não se aplica nesta fase — como nenhuma marca nova foi solicitada, não houve tentativa de gravação.

## Confirmações
- **`produto_padrao` não foi alterado** em nenhum dos 34 produtos aplicados — verificado durante a própria transação (comparação antes/depois de cada escrita); a transação seria revertida automaticamente se qualquer divergência fosse detectada.
- **Cascata não foi usada** — cada produto foi atualizado individualmente.
- **Dicionário Mestre MEDREG não foi alterado.**
- **Bionexo não foi tocado.**
- `app.py`, `templates/` e `core/` não foram alterados.
- **Banco e backup não foram (nem serão) commitados** — ambos permanecem fora do controle de versão (`.gitignore`/`.git/info/exclude`), confirmado via `git check-ignore`.
- 34 registros criados em `auditoria_sku` (todos de `sku_master`; nenhum de `categoria`, já que todas já estavam preenchidas com `MEDICAMENTOS` ou `INSUMOS HOSPITALARES`; nenhum de `marca`, já que nenhuma correção de marca foi fornecida) com `origem_correcao = 'SKU-MEMORIA-16-GLICOSE-USUARIO'`.
- `python -m py_compile app.py` executado com sucesso.
