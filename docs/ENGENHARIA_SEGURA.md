# Engenharia segura do MEDBOX_V3_ZERO

## Regras obrigatórias

1. O repositório de trabalho deve ficar fora do OneDrive, preferencialmente em `C:\dev\MEDBOX_V3_ZERO`.
2. O OneDrive pode armazenar backups compactados, mas nunca a pasta `.git` ativa.
3. Nenhum teste pode usar o banco operacional `banco\medbox_v3.db`.
4. Bancos, uploads, planilhas reais, relatórios, credenciais, tokens e logs não podem entrar no Git.
5. Toda alteração deve passar por Pull Request e pelo workflow `MEDBOX CI`.
6. Nenhum merge deve ocorrer com validações bloqueantes em falha.
7. Alterações de banco exigem backup, transação, rollback e teste em banco temporário.
8. Operações reais de Gmail e Bionexo permanecem fora da suíte automatizada.

## Ferramentas adotadas

- Git e GitHub Desktop para versionamento e inspeção visual.
- GitHub CLI para operações administrativas controladas.
- Visual Studio Code com Python, Pylance, Ruff, GitHub Pull Requests, Error Lens e EditorConfig.
- Python 3.13 como ambiente principal; Python 3.14 como compatibilidade adicional.
- Node.js LTS para testes JavaScript.
- pytest e pytest-cov para testes e cobertura.
- Ruff para erros críticos e qualidade Python.
- pre-commit para impedir commits inválidos.
- Bandit e pip-audit para auditoria de segurança.
- Dependabot para atualização controlada de dependências.
- Playwright para testes ponta a ponta depois da estabilização das rotas de Lances.

## Preparação do clone limpo

O clone operacional deve ficar em `C:\dev\MEDBOX_V3_ZERO`. Não copiar a pasta `.git` do OneDrive.

Depois do clone, executar:

```powershell
Set-Location C:\dev\MEDBOX_V3_ZERO
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
.\scripts\setup\CONFIGURAR_AMBIENTE_SEGURO.ps1
```

O script:

- recusa execução dentro do OneDrive;
- exige Git, Python, Node e npm;
- instala as extensões recomendadas do VS Code quando `code` estiver disponível;
- cria `.venv` com Python 3.13, usando o Python disponível como fallback;
- instala dependências de produção e desenvolvimento;
- habilita pre-commit;
- verifica arquivos sensíveis;
- bloqueia testes ligados ao banco operacional;
- compila o código;
- executa Ruff, pytest e o teste JavaScript de Lances.

## Política gradual de qualidade

### Bloqueante desde a implantação

- arquivos sensíveis;
- bancos e chaves privadas;
- testes que apontem para o banco operacional;
- conflitos de merge;
- Python que não compila;
- erros críticos do Ruff;
- testes Python;
- teste JavaScript de Lances.

### Auditoria inicialmente informativa

- Bandit;
- pip-audit;
- cobertura total;
- formatação integral do legado.

Essas verificações devem se tornar bloqueantes depois que os problemas legados forem tratados em PRs pequenos e independentes.

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
