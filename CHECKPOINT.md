# CHECKPOINT MEDBOX_V3_ZERO

## Estado atual
- Data/hora: 2026-06-25 08:20:02 -03:00
- Agente em uso: Codex
- Branch: melhoria/auditoria-sku-master-todos-produtos
- Tarefa atual: preparar script seguro para correcao futura das marcas invalidas em precos_fornecedores
- Status: script criado; APPLY nao executado; DRY-RUN bloqueado por ausencia do comando `python` no PATH
- Status Git antes desta rodada: `CHECKPOINT.md` modificado e `.claude/` nao rastreado

## Regras inviolaveis
- Nunca alterar banco sem backup previo.
- Nunca alterar descricao_original.
- SKU_MASTER nao substitui descricao_original.
- Nunca deletar historico de precos.
- Precos antigos vao para precos_fornecedores_historico.
- Nao misturar fornecedor com fabricante/marca.
- Nao fazer patch as cegas: diagnosticar antes.
- Nao executar `--apply` nesta tarefa.

## Arquivos permitidos nesta tarefa
- scripts/correcoes/corrigir_marcas_invalidas_precos.py
- CHECKPOINT.md

## Arquivos proibidos nesta tarefa
- banco/
- uploads/
- backups/
- descricao_original
- historico de precos
- arquivos fora do escopo da tarefa

## O que ja foi feito
- AGENTS.md, CLAUDE.md, RETOMAR.md e CHECKPOINT.md lidos antes da alteracao.
- `git status --short` executado antes da alteracao.
- Criado `scripts/correcoes/corrigir_marcas_invalidas_precos.py`.
- Configurado DRY-RUN como modo padrao, sem conexao de escrita.
- Configurado APPLY futuro para exigir `--apply --confirmar`, branch correta e Git limpo.
- Configurada contagem obrigatoria de exatamente 89 registros.
- Configurado bloqueio explicito de `SR` e `S R`.
- Configuradas validacoes de existencia de CSV/banco, IDs, produto_id e marca atual.
- Configurado `NOVO_VALOR_MARCA = None`, documentado como SQL NULL pendente de validacao humana.
- Configurados backup SQLite em `backups/` e CSV de auditoria com timestamp para APPLY futuro.
- Reconciliados por leitura independente os 89 registros do CSV com os 89 registros atuais do banco.

## O que falta fazer
- Executar o DRY-RUN em ambiente com comando `python` disponivel.
- Validar o resultado do DRY-RUN antes de qualquer autorizacao futura de APPLY.
- Decidir explicitamente se `NOVO_VALOR_MARCA = None` sera mantido.
- Nenhuma correcao de banco esta autorizada nesta etapa.

## Arquivos alterados
- scripts/correcoes/corrigir_marcas_invalidas_precos.py
- CHECKPOINT.md

## Comandos executados
- `git status --short` antes da tarefa.
- Leitura de AGENTS.md, CLAUDE.md, RETOMAR.md e CHECKPOINT.md.
- `python scripts/correcoes/corrigir_marcas_invalidas_precos.py` sem argumentos.
- Nova tentativa em 2026-06-25: mesmo comando solicitado, bloqueado porque `python` nao esta disponivel no PATH.
- Consultas independentes somente leitura via `node:sqlite` para reconciliacao.
- `git diff --check`, `git diff --name-only -- banco` e `git check-ignore -v`.

## Testes executados
- Tentativa do DRY-RUN pelo comando Python solicitado.
- Validacao independente de 89 registros selecionados no CSV.
- Validacao de 89 `preco_id` unicos.
- Confirmacao de que nenhum registro SR/S R entrou no conjunto.
- Reconciliacao de `preco_id`, `produto_id` e `marca_preco_atual` com o banco.
- Verificacao estatica das protecoes de branch, Git limpo, backup, auditoria e confirmacao dupla.
- Comparacao de tamanho e data de modificacao do banco antes/depois.

## Resultado dos testes
- O comando Python nao iniciou: `python` nao esta disponivel no PATH desta sessao.
- Nova tentativa em 2026-06-25 confirmou o mesmo bloqueio de ambiente.
- Nenhuma linha do script foi executada pelo interpretador Python nesta sessao.
- Validacao independente: 89 registros, IDs unicos, zero SR/S R e zero divergencias com o banco.
- Totais por marca: UN 64, U N 2, RL 12, PR 3, PT 1, CX 1, FL 1, GL 1, KT 1, MT 3.
- Banco permaneceu inalterado.
- Nenhum UPDATE, INSERT, DELETE, DROP, ALTER ou CREATE foi executado.
- APPLY nao foi executado.

## Riscos / observacoes
- O DRY-RUN real ainda precisa ser executado onde Python esteja disponivel.
- O script contem o UPDATE futuro, mas ele esta isolado no caminho protegido por `--apply --confirmar`.
- O arquivo corresponde ao padrao local ignorado `corrigir_*.py` em `.git/info/exclude`; por isso nao aparece no `git status`. Para rastrea-lo futuramente sera necessario revisar essa exclusao ou usar `git add -f`, sem fazer isso nesta tarefa.
- O Git esta propositalmente sujo durante o desenvolvimento; o APPLY futuro abortara ate que esteja limpo.
- `.claude/` continua nao rastreado e nao foi alterado.

## Proximo passo recomendado
- Em PowerShell com Python disponivel, executar `python scripts\correcoes\corrigir_marcas_invalidas_precos.py` e revisar o DRY-RUN. Nao usar `--apply` antes de nova autorizacao explicita.
