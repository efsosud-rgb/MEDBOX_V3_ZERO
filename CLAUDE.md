# CLAUDE.md — Regras de Proteção do Projeto MEDBOX_V3_ZERO

## Arquivos e recursos protegidos

Os itens abaixo são **intocáveis** sem autorização explícita do responsável pelo projeto:

| Recurso | Restrição |
|---|---|
| `app.py` | Não alterar, refatorar, reescrever ou remover |
| `core/banco.py` | Não alterar esquemas, queries ou conexão com o banco |
| `templates/` (todos os arquivos) | Não modificar, renomear ou excluir nenhum template |
| `uploads/SKU_MASTER_*.xlsx` | Não sobrescrever, excluir ou regenerar |
| `banco/medbox.db` e `banco/medbox_v3.db` | Nunca recriar, dropar tabelas ou apagar dados |

## Proibições absolutas

- **Nunca apagar arquivos** do repositório sem autorização explícita.
- **Nunca recriar o banco de dados** — não executar `DROP TABLE`, `DROP DATABASE`, scripts de migração destrutiva ou qualquer operação que apague dados existentes.
- **Nunca remover funcionalidades existentes** — toda funcionalidade já implementada deve ser preservada.
- **Nunca modificar `app.py`** — o roteamento, as rotas Flask e a lógica principal da aplicação não devem ser tocados.
- **Nunca modificar `core/banco.py`** — a camada de acesso ao banco de dados é crítica e estável.
- **Nunca modificar os templates** em `templates/` — a interface do usuário não deve ser alterada sem aprovação.
- **Nunca sobrescrever o SKU_MASTER** — os arquivos em `uploads/SKU_MASTER_*.xlsx` são a fonte de verdade do catálogo de produtos.

## Fluxo obrigatório para qualquer alteração

1. Toda mudança, mesmo pequena, deve ser feita em uma **branch separada** (nunca direto em `main`).
2. A branch deve ter nome descritivo, por exemplo: `feature/nome-da-funcionalidade` ou `fix/descricao-do-bug`.
3. A alteração só pode ser integrada à `main` via **Pull Request aprovado**.
4. O PR deve descrever claramente **o que muda**, **por que muda** e **o que foi testado**.
5. Nenhum PR que toque nos arquivos protegidos acima pode ser mergeado sem autorização explícita do responsável.

## Princípio geral

> Em caso de dúvida sobre se uma ação é permitida, **não execute** — pergunte antes.
