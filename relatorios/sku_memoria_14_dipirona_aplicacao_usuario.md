# SKU-MEMORIA-14 — Aplicação DIPIRONA por aprovação manual do usuário

## Regra de aprovação manual do usuário
> "Salvei a planilha com a revisão."

Conforme a regra global já estabelecida (mesma usada em `SKU-MEMORIA-10`/`12`): toda aplicação depende da aprovação manual do usuário na planilha; se `decisao_usuario = APROVAR`, aplica-se sem bloqueio semântico, mantendo apenas os bloqueios **técnicos** obrigatórios (decisão inválida, produto inexistente, SKU final vazio). `REJEITAR` não aplica; `REVISAR` fica pendente; vazio também não é aplicado.

## Total de linhas e decisões

| Item | Quantidade |
|---|---:|
| Total de linhas na planilha | 32 |
| Total APROVAR | 30 |
| Total REJEITAR | 1 |
| Total REVISAR | 0 |
| Total vazio | 1 |
| Total inválido | 0 |
| Total apto para aplicar (validação técnica) | 30 |
| Total bloqueado técnico | 0 |

## O que o usuário efetivamente revisou
A revisão desta vez foi criteriosa e diferenciada linha a linha, diferente do padrão de "aprovar tudo" visto nas fases `SONDA`/`AGULHA`:

- **Id 5926** (`DIPIRONA 500 MG`, originalmente `SEM_APRESENTACAO_CLARA`) foi **REJEITADO** pelo usuário — decisão correta, pois o texto realmente não permite identificar a forma farmacêutica com segurança.
- **Id 5404** (`DIPIRONA SODICA GOTAS 500MG/ML SOL ORAL 10ML`, originalmente `CANDIDATO_SEGURO`) ficou com `decisao_usuario` **vazio** — respeitado como não aplicado (`IGNORADO_VAZIO`), sem presumir aprovação.
- **Id 7047** (`DIPIRONA 500MG/ML SOL ORAL FR`, originalmente `PENDENTE_REVISAO` por volume ausente) foi **APROVADO**, com o usuário preenchendo o volume que faltava (`DIPIRONA SODICA 500MG/ML GOTAS 10ML`) — resolveu a pendência manualmente.
- **7 produtos ASSOCIADA_COMPOSTA** (escopolamina, orfenadrina/cafeína) foram **APROVADOS**, com o usuário fornecendo o SKU_MASTER completo combinando os princípios ativos (ex.: `BUTILBROMETO ESCOPOLAMINA 4MG/ML + DIPIRONA SODICA 500MG/ML AMP 5ML`) — corretamente sem misturar com dipirona simples.
- **2 produtos** (`50MG/ML`) tiveram a forma corrigida de "SOL ORAL" para "GOTAS" pelo usuário — ajuste editorial aceito sem julgamento semântico adicional.

Nenhuma linha usou a coluna dedicada `sku_master_corrigido_usuario` (ficou vazia em todas) — a edição foi feita diretamente em `sku_master_sugerido_preliminar`, mesmo padrão observado nas fases anteriores. `marca_corrigida_usuario` também ficou vazia em todas as 32 linhas.

## Backup criado
`backups/medbox_v3_antes_sku_memoria_14_dipirona_usuario_20260703_124009.db`
- Tamanho: 9.555.968 bytes.
- Verificado com `PRAGMA integrity_check` → `ok`, e contagem de produtos (11.105) confere com o banco antes da escrita.

## Total aplicado: 30
## Total ignorado: 2 (1 REJEITAR + 1 vazio)
## Total bloqueado técnico: 0
## Total com erro: 0

A transação (`BEGIN`...`COMMIT`) processou as 30 linhas aprovadas em um único bloco; nenhum erro ocorreu, nenhum `ROLLBACK` foi necessário.

## Produtos aplicados
Todos os 30 produtos aprovados tiveram `sku_master` preenchido/atualizado (lista completa com antes/depois em `relatorios/sku_memoria_14_dipirona_pos_aplicacao.csv`). Todos também tiveram `sku_corrigido` marcado como `1` e `corrigido_em` atualizado.

Exemplos de aplicação:
| produto_id | Descrição original | SKU_MASTER aplicado |
|---:|---|---|
| 5407, 6726, 8530, 9704, 10317 | variações "DIPIRONA (SODICA) 500MG (COMP/CP)" | DIPIRONA SODICA 500MG COMP |
| 5405, 5787, 5928, 6727, 8695 | variações "DIPIRONA (SODICA) 500MG/ML ... 2ML" | DIPIRONA SODICA 500MG/ML AMP 2ML |
| 6862 | BUTILBROMETO DE ESCOPOLAMINA + DIPIRONA SODICA 4 MG + 500 MG/ML SOL INJ 5 ML | BUTILBROMETO ESCOPOLAMINA 4MG/ML + DIPIRONA SODICA 500MG/ML AMP 5ML |
| 9706 | DIPIRONA/ORFENADRINA/CAFEINA 300MG/35MG/50MG VIA ORAL COMPRIMIDO | DIPIRONA SODICA 300MG + ORFENADRINA 35MG + CAFEINA 50MG COMP |
| 9703 | DIPIRONA SODICA 300MG VIA RETAL SUPOSITORIO | DIPIRONA SODICA 300MG SUPOSITORIO |
| 7047 | DIPIRONA 500MG/ML SOL ORAL FR (sem volume) | DIPIRONA SODICA 500MG/ML GOTAS 10ML |

## Produtos ignorados
- **Id 5926** — `IGNORADO_REJEITAR`: usuário rejeitou por apresentação indefinida.
- **Id 5404** — `IGNORADO_VAZIO`: `decisao_usuario` não foi preenchida.

## Produtos bloqueados tecnicamente
Nenhum.

## Marcas aplicadas
Nenhuma — `marca_corrigida_usuario` estava vazia em todas as 32 linhas, então a marca atual de cada produto foi **preservada sem alteração**.

## Marcas que não puderam ser gravadas por limitação técnica
Não se aplica nesta fase — como nenhuma marca nova foi solicitada, não houve tentativa de gravação.

## Confirmações
- **`produto_padrao` não foi alterado** em nenhum dos 30 produtos aplicados — verificado durante a própria transação (comparação antes/depois de cada escrita); a transação seria revertida automaticamente se qualquer divergência fosse detectada.
- **Cascata não foi usada** — cada produto foi atualizado individualmente.
- **Dicionário Mestre MEDREG não foi alterado.**
- **Bionexo não foi tocado.**
- `app.py`, `templates/` e `core/` não foram alterados.
- **Banco e backup não foram (nem serão) commitados** — ambos permanecem fora do controle de versão (`.gitignore`/`.git/info/exclude`), confirmado via `git check-ignore`.
- 30 registros criados em `auditoria_sku` (todos de `sku_master`; nenhum de `categoria`, já que todas já estavam preenchidas com `MEDICAMENTOS`; nenhum de `marca`, já que nenhuma correção de marca foi fornecida) com `origem_correcao = 'SKU-MEMORIA-14-DIPIRONA-USUARIO'`.
- `python -m py_compile app.py` executado com sucesso.
