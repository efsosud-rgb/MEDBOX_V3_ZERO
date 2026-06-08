# Fase 1 — Migração SKU Master: Guia de Uso

## Visão geral

Esta fase entrega dois scripts que preparam o banco de dados para receber a base de produtos
do arquivo `Produtos.xlsx`, sem alterar nenhum arquivo protegido do sistema.

**Por padrão, todos os scripts operam apenas na cópia de teste.**
O banco real (`banco/medbox_v3.db`) só é alterado com o argumento explícito `--confirmar`.

---

## Pré-requisitos

```bash
pip install openpyxl
```

Coloque o arquivo `Produtos.xlsx` em `uploads/Produtos.xlsx`.

---

## Passo 1 — Migrar o banco (adicionar colunas novas)

```bash
# Modo seguro: age APENAS na cópia de teste (banco/medbox_v3_teste.db)
python core/migrador_banco.py

# Modo confirmar: age também no banco real
python core/migrador_banco.py --confirmar
```

**O que este script faz:**

1. Cria um backup automático em `banco/backups/medbox_v3_<timestamp>.db`.
2. Cria/recria a cópia de teste `banco/medbox_v3_teste.db`.
3. Adiciona as colunas abaixo à tabela `produtos` (somente se ainda não existirem):
   - `chave_sku` — chave normalizada do produto
   - `forma_farmaceutica` — forma de apresentação (ex.: cápsula, comprimido)
   - `concentracao` — concentração do princípio ativo
   - `apresentacao` — apresentação comercial
   - `unidade_compra` — unidade de compra (ex.: CX, UN)
   - `origem` — origem do registro (default `'SISTEMA'`)
   - `data_criacao` — data de criação do registro
4. Imprime quais colunas foram adicionadas e quais já existiam.

---

## Passo 2 — Importar produtos do Produtos.xlsx

```bash
# Modo seguro: importa APENAS na cópia de teste
python core/importador_base_produtos.py

# Modo confirmar: importa no banco real
python core/importador_base_produtos.py --confirmar
```

**O que este script faz:**

1. Lê a aba `Produtos` do arquivo `uploads/Produtos.xlsx`.
2. Ignora a primeira linha (título "BASE DE PRODUTOS").
3. Para cada descrição, gera uma `chave_sku` normalizada e verifica duplicatas.
4. Insere os registros com `origem = 'BASE_PRODUTOS'` e `ativo = 1`.
5. Campos deixados como NULL nesta fase (extração futura com revisão manual):
   `forma_farmaceutica`, `concentracao`, `apresentacao`, `unidade_compra`, `categoria`.
6. Exibe relatório final no terminal.

**Saída esperada:**

```
====================================================
RELATÓRIO DE IMPORTAÇÃO — cópia de TESTE
====================================================
  Total de linhas lidas:              8034
  Total inseridos:                    7980
  Total ignorados (duplicidade):        50
  Total com dados incompletos:           4
====================================================
```

---

## Ordem de execução obrigatória

```
1. python core/migrador_banco.py
2. python core/importador_base_produtos.py
```

Sempre execute o migrador antes do importador.
Se as colunas ainda não existirem, o importador exibirá uma mensagem de erro clara.

---

## Arquivos gerados

| Arquivo | Descrição |
|---|---|
| `banco/backups/medbox_v3_<timestamp>.db` | Backup automático do banco real |
| `banco/medbox_v3_teste.db` | Cópia de teste com as migrações aplicadas |
