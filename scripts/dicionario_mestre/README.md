# Scripts do Dicionario Mestre MEDBOX

Este diretorio guarda o fluxo inicial do Dicionario Mestre MEDBOX.

Como rodar o extrator de fontes internas:

```bash
python scripts/dicionario_mestre/extrair_fontes_internas.py
```

O extrator:

1. Lê fontes internas em modo somente leitura.
2. Exporta tabelas SQLite, arquivos XLSX e CSVs de auditoria para `data/dicionario_mestre/interno/`.
3. Gera relatório textual em `data/dicionario_mestre/processado/`.
4. Não aplica correções.
5. Não altera `SKU_MASTER` no banco.

Fontes lidas:

1. `banco/medbox_v3.db` em modo read-only.
2. `uploads/SKU_MASTER_2_0.xlsx`, se existir.
3. `uploads/PRODUTOS.xlsx`, se existir.
4. `backups/auditoria_lote_piloto_sku_master_20260625_112310.csv`, se existir.
5. Tabelas SQLite já aprovadas para leitura.

Arquivos gerados:

1. `data/dicionario_mestre/interno/*.csv`
2. `data/dicionario_mestre/processado/relatorio_extracao_fontes_internas.txt`

Garantia:

1. Apenas leitura.
2. Nenhuma escrita no SQLite.
3. Nenhuma correção no banco.
