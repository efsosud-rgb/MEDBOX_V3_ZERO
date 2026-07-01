# SKU-MEMORIA-04B — Planilha Excel de aprovação manual SKU_MASTER

## Objetivo
Converter `relatorios/sku_memoria_04_aprovacao_manual.csv` em uma planilha Excel (`.xlsx`) profissional, mais prática para revisão humana, com tabela filtrável, lista suspensa de decisão e destaque visual — **sem alterar o banco e sem aplicar nada**.

## Arquivo gerado
`relatorios/sku_memoria_04_aprovacao_manual.xlsx`

## Quantidade de linhas
15 linhas de dados (mesmas 15 da fase `SKU-MEMORIA-04`: 5 `MATCH_MEMORIA_VALIDADA` + 10 `MATCH_ASSINATURA_TECNICA`), mais a linha de cabeçalho.

## Estrutura do arquivo

### Aba `APROVACAO_SKU`
- Colunas: `produto_id`, `tabela_origem`, `descricao_original`, `sku_master_sugerido`, `marca_sugerida`, `categoria_sugerida`, `tipo_match`, `confianca`, `motivo`, `decisao_usuario`, `observacao_usuario`.
- Dados formatados como **Tabela do Excel** (`TabelaAprovacaoSKU`), com autofiltro em todas as colunas.
- Primeira linha (cabeçalho) **congelada** (`freeze_panes = A2`), com fundo azul escuro e texto branco em negrito.
- Largura de coluna ajustada por conteúdo (colunas de texto longo como `descricao_original` e `motivo` mais largas; colunas curtas como `produto_id` e `confianca` mais estreitas), com quebra de linha automática e altura de linha ajustada para leitura confortável.
- Destaque visual estático na coluna `tipo_match`: verde suave para `MATCH_MEMORIA_VALIDADA`, azul suave para `MATCH_ASSINATURA_TECNICA`.
- Destaque visual **dinâmico** (formatação condicional) na coluna `decisao_usuario`: amarelo suave quando vazio (pendente), verde quando `APROVAR`, vermelho/rosa quando `REJEITAR`, azul quando `REVISAR` — atualiza automaticamente no Excel conforme o usuário preenche.

### Aba `INSTRUCOES`
Texto explicando como preencher a coluna `decisao_usuario` (`APROVAR`/`REJEITAR`/`REVISAR`), os cuidados com divergência de atributos críticos (concentração, volume, forma, via, calibre, número, tamanho, apresentação), a separação marca/SKU_MASTER, a regra de categoria (`MEDICAMENTOS`/`CORRELATOS`) e a confirmação de que nada é aplicado automaticamente.

## Confirmação de validação de dados
A coluna `decisao_usuario` (linhas 2 a 16) tem validação de dados do tipo lista, restrita exatamente a três valores: `APROVAR`, `REJEITAR`, `REVISAR`. Célula vazia é permitida (`allow_blank=True`) como estado inicial padrão — nenhuma decisão foi pré-selecionada. Verificado por leitura programática do arquivo gerado (`openpyxl.load_workbook`): 1 regra de validação de dados e 4 regras de formatação condicional presentes na aba `APROVACAO_SKU`.

## Confirmações de segurança
- Banco (`banco/medbox_v3.db`) não foi acessado nem alterado nesta fase.
- Nenhum SKU_MASTER foi aplicado a nenhum produto.
- `app.py`, `templates/` e `core/` não foram alterados.
- Nenhuma cascata automática foi executada.
- Nenhuma pesquisa à internet foi feita nesta fase — apenas conversão de formato (CSV → XLSX) do arquivo já existente.
