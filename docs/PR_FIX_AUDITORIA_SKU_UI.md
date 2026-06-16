# Correção Auditoria SKU Master

Branch: `fix-auditoria-sku-ui-segura`

## Objetivo

Corrigir a tela `/sku-master/auditoria` para reduzir falhas de edição e deixar o fluxo mais seguro.

## Alterações feitas

- Ajustado `templates/sku_master_auditoria.html`.
- Adicionado aviso visual de sucesso/erro na própria tela.
- Melhorado tratamento de resposta das chamadas `fetch` para exibir erro real da API em vez de apenas “Erro de rede”.
- Categoria passou a ser `select` restrito a:
  - `CORRELATOS`
  - `MEDICAMENTOS`
- Botão de exclusão foi renomeado para `Excluir item` e mantido visível na coluna de ação.
- Exclusão usa confirmação antes de chamar a rota existente `/sku-master/auditoria/excluir/<id>`.
- Ao alterar o campo SKU Master/Produto Padrão no modal, a opção de cascata para produtos semelhantes é marcada automaticamente.
- A mensagem de sucesso passa a informar quantos itens semelhantes foram atualizados automaticamente, quando a API retornar esse total.

## Limites desta alteração

- Não alterei `app.py`.
- Não alterei `core/banco.py`.
- Não alterei `core/importador_universal.py`.
- Não alterei `core/busca_inteligente.py`.
- Não alterei banco de dados.
- Não fiz merge.

## Como testar

1. Abrir o sistema local.
2. Acessar `/sku-master/auditoria`.
3. Em uma linha, alterar categoria para `CORRELATOS` ou `MEDICAMENTOS` e salvar pelo botão rápido.
4. Confirmar que aparece mensagem clara de sucesso ou erro.
5. Abrir o modal de edição.
6. Alterar o SKU Master/Produto Padrão.
7. Confirmar que a opção de cascata de semelhantes fica marcada automaticamente.
8. Salvar.
9. Confirmar que não aparece mais erro genérico de rede.
10. Confirmar que a tela informa quantos itens semelhantes foram atualizados, quando a API retornar esse dado.
11. Testar o botão `Excluir item` e confirmar que ele pede confirmação antes de inativar/remover.
