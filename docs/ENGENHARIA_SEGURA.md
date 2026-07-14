# Engenharia segura do MEDBOX_V3_ZERO

## Regras obrigatórias

1. O repositório de trabalho deve ficar fora do OneDrive, preferencialmente em `C:\dev\MEDBOX_V3_ZERO`.
2. Nenhum teste pode usar o banco operacional `banco\medbox_v3.db`.
3. Bancos, uploads, planilhas reais, relatórios, credenciais, tokens e logs não podem entrar no Git.
4. Toda alteração deve passar por Pull Request e pelo workflow `MEDBOX CI`.
5. Nenhum merge deve ocorrer com validações bloqueantes em falha.
6. Alterações de banco exigem backup, transação, rollback e teste em banco temporário.
7. Operações reais de Gmail e Bionexo permanecem fora da suíte automatizada.

## Ordem de estabilização

1. Manter clone definitivo fora do OneDrive.
2. Corrigir persistência e desempate do módulo de Lances.
3. Criar testes Playwright de tela até SQLite temporário e documento.
4. Consolidar implementações duplicadas em Python e JavaScript.
5. Remover `secret_key` fixa e `debug=True` de produção.
6. Fixar versões das dependências após validar compatibilidade.
7. Retomar a Issue #52 com aprovação manual de SKU_MASTER.
8. Avaliar Docker somente após CI verde e sistema estabilizado.

## Critério para liberar Gerar Cotação

- testes de criação e atualização em banco temporário;
- backend ignorando `vencedor` e `status` falsos do frontend;
- desempate MEDBOX > OSINFO > concorrente;
- fixture AFNE com R$ 119.461,60;
- rollback integral validado;
- revisão independente;
- CI verde.
