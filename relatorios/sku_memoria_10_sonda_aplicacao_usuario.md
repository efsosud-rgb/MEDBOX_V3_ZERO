# SKU-MEMORIA-10 — Aplicação SONDA por aprovação manual do usuário (sem bloqueio semântico)

## Nova regra explícita do usuário
> "Tudo que eu der como aprovado, aprove. Eu preenchi os SKU_MASTER e a MARCA."

Diferente da fase `SKU-MEMORIA-09`, nesta fase os bloqueios **semânticos** (conflito de tipo, número, vias, balão, material, texto corrompido, subfamília indefinida, pendente sem correção) foram **desativados por decisão explícita do usuário**, que assumiu a responsabilidade pela revisão de cada linha. Foram mantidos apenas os bloqueios **técnicos** obrigatórios: decisão inválida, produto inexistente no banco, e SKU final vazio.

## Total de linhas e decisões

| Item | Quantidade |
|---|---:|
| Total de linhas na planilha | 291 |
| Total APROVAR | 291 |
| Total apto para aplicar (validação técnica) | 291 |
| Total bloqueado tecnicamente | 0 |

Nenhuma decisão inválida, produto ausente ou SKU final vazio foi encontrado — todas as 291 linhas passaram na validação técnica e foram aplicadas.

## O que o usuário efetivamente corrigiu
Confirmado por comparação com o diagnóstico original (`sku_memoria_08_sonda_diagnostico.csv`):
- **258 de 291** descrições de `sku_master_sugerido_preliminar` foram reescritas manualmente pelo usuário (incluindo a decodificação cuidadosa de textos com OCR corrompido, ex.: `SKU PENDENTE - _[C)TO SONDA CARLENS 35 ESQ S/CARIN...` → `CONJ. SONDA CARLENS 35 ESQ. S/ CARINA PVC UN`).
- **291 de 291** tiveram a coluna `marca_atual` preenchida com uma marca real (ex.: `VITALGOLD`, `LAVELEX`), coluna que originalmente estava vazia para a maioria dos produtos.

## Backup criado
`backups/medbox_v3_antes_sku_memoria_10_sonda_usuario_20260703_082709.db`
- Tamanho: 9.392.128 bytes.
- Verificado com `PRAGMA integrity_check` → `ok`, e contagem de produtos (11.105) confere com o banco antes da escrita.

## Total aplicado: 291
## Total bloqueado técnico: 0
## Total com erro: 0

A transação (`BEGIN`...`COMMIT`) processou todas as 291 linhas em um único bloco; nenhum erro ocorreu, nenhum `ROLLBACK` foi necessário.

Destas 291, **112 já haviam sido aplicadas na fase anterior** (`SKU-MEMORIA-09`) com o mesmo SKU_MASTER (a reaplicação apenas confirmou o valor e adicionou a marca); **179 são novas** — produtos que na fase anterior haviam sido bloqueados por regra semântica e agora foram liberados pela decisão explícita do usuário.

## ⚠️ Limitação estrutural encontrada na gravação da marca
O banco **não tem uma coluna `marca` na tabela `produtos`** — o campo marca só existe em `precos_fornecedores.marca`, associado a registros de preço de fornecedor. Ao tentar gravar a marca informada pelo usuário, foi constatado que **234 dos 291 produtos SONDA não têm nenhum registro em `precos_fornecedores`** (foram cadastrados diretamente no catálogo, sem importação de preço/nota fiscal associada). Por isso:
- **Marca gravada com sucesso**: 57 produtos (onde existe ao menos um registro de preço associado).
- **Marca não pôde ser gravada**: 234 produtos — não por bloqueio de regra, mas porque **não existe nenhuma linha em `precos_fornecedores` para receber o valor**. O SKU_MASTER desses 234 foi aplicado normalmente; apenas a marca ficou pendente por essa limitação estrutural, documentada linha a linha em `relatorios/sku_memoria_10_sonda_pos_aplicacao.csv`.

Nesta fase, a atualização de marca foi feita com **sobrescrita autorizada** (diferente das fases anteriores, que preservavam marca já preenchida) — nos 57 casos com registro de preço, o valor anterior (se houver) foi substituído pelo valor informado pelo usuário, por autorização explícita.

## Produtos aplicados
Todos os 291 produtos da planilha (lista completa com antes/depois de `sku_master`, `marca` e `categoria` em `relatorios/sku_memoria_10_sonda_pos_aplicacao.csv`). Nenhum produto ficou bloqueado tecnicamente.

## Confirmações
- **`produto_padrao` não foi alterado** em nenhum dos 291 produtos — verificado durante a própria transação (comparação antes/depois de cada escrita); a transação seria revertida automaticamente se qualquer divergência fosse detectada.
- **Cascata não foi usada** — cada produto foi atualizado individualmente.
- **Dicionário Mestre MEDREG não foi alterado.**
- **Bionexo não foi tocado.**
- `app.py`, `templates/` e `core/` não foram alterados.
- **Banco e backup não foram (nem serão) commitados** — ambos permanecem fora do controle de versão (`.gitignore`/`.git/info/exclude`), confirmado via `git check-ignore`.
- 236 registros criados em `auditoria_sku` (179 de `sku_master` + 57 de `marca`; nenhum de `categoria`, já que todas as categorias já estavam preenchidas) com `origem_correcao = 'SKU-MEMORIA-10-SONDA-USUARIO'`.
- `python -m py_compile app.py` executado com sucesso.
