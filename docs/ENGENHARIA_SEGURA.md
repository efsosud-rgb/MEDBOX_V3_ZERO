# Engenharia segura do MEDBOX_V3_ZERO

## Regras obrigatórias

1. O repositório de trabalho deve ficar fora do OneDrive, preferencialmente em `C:\dev\MEDBOX_V3_ZERO`.
2. O OneDrive pode armazenar backups compactados, mas nunca a pasta `.git` ativa.
3. Nenhum teste pode usar o banco operacional `banco\medbox_v3.db`.
4. Bancos, uploads, planilhas reais, relatórios, credenciais, tokens e logs não podem entrar no Git.
5. Toda alteração deve passar por Pull Request e pelo workflow `MEDBOX CI`.
6. Nenhum merge deve ocorrer com o job `Validar código e testes` em falha.
7. Alterações de banco exigem backup, transação, rollback e teste em banco temporário.
8. Operações reais de Gmail e Bionexo permanecem separadas da suíte automatizada.

## Ambiente local recomendado

- VS Code com Python, Pylance, Ruff, GitHub Pull Requests, Error Lens e EditorConfig.
- GitHub Desktop apenas para inspeção visual e operações Git simples.
- Codex como executor principal no clone limpo.
- Claude Code como auditor independente em modo somente leitura.
- Jules apenas para tarefas completamente reproduzíveis no repositório remoto.

## Preparação do clone

```powershell
Set-Location C:\dev\MEDBOX_V3_ZERO
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt -r requirements-dev.txt
pre-commit install
pre-commit run --all-files
pytest -q
```

## Política gradual de qualidade

### Bloqueante desde a implantação

- arquivos sensíveis;
- bancos e chaves privadas;
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

1. Manter o clone definitivo fora do OneDrive.
2. Corrigir persistência e desempate do módulo de Lances.
3. Criar testes completos de `tela → payload → Flask → SQLite → documento` com Playwright e banco temporário.
4. Consolidar as implementações duplicadas de Lances em Python e JavaScript.
5. Corrigir `secret_key` e `debug=True` por configuração de ambiente.
6. Fixar as dependências de produção após validação de compatibilidade.
7. Consolidar scripts `testar_*.py` dentro de `tests/`.
8. Retomar a Issue #52 com testes de preservação de referências e aprovação manual de SKU_MASTER.
9. Avaliar Docker somente após o sistema estar estável e com CI verde.

## Critério de liberação do botão Gerar Cotação

O botão só deve voltar ao uso real após:

- testes de criação e atualização em banco temporário;
- teste de payload sem `vencedor` e `status`;
- teste de desempate MEDBOX > OSINFO > concorrente;
- fixture AFNE com total esperado de R$ 119.461,60;
- revisão independente do diff;
- CI verde.
