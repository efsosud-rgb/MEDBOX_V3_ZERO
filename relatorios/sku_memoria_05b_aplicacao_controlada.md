# SKU-MEMORIA-05B — Aplicação controlada dos 15 SKU_MASTER aprovados

## Objetivo
Aplicar no banco, de forma controlada e com backup prévio, os 15 registros aprovados (`decisao_usuario = APROVAR`) da planilha `sku_memoria_04_aprovacao_manual.xlsx`, validados na fase `SKU-MEMORIA-05A` como `APTO_PARA_APLICACAO_CONTROLADA`.

## Backup criado
`backups/medbox_v3_antes_sku_memoria_05b_20260701_163015.db`
- Tamanho: 9.342.976 bytes (idêntico ao banco original antes da escrita).
- Verificado com `PRAGMA integrity_check` → `ok`, e contagem de produtos (11.105) confere com o banco de origem antes da aplicação.

## Total aplicado
**15 de 15** produtos aprovados foram aplicados com sucesso, em uma única transação SQLite (`BEGIN`...`COMMIT`), sem nenhum erro. **Total com erro: 0.**

A transação era tudo-ou-nada: se qualquer uma das 15 linhas falhasse (produto não encontrado, `produto_padrao` alterado inesperadamente, etc.), toda a operação seria revertida (`ROLLBACK`) e nenhuma alteração persistiria. Isso não foi necessário — todas as 15 linhas foram validadas e aplicadas com sucesso.

## Produtos aplicados

| produto_id | SKU_MASTER antes | SKU_MASTER depois |
|---:|---|---|
| 267 | ENOXAPARINA SODICA 40MG | ENOXAPARINA SODICA 40MG/0,4ML |
| 2016 | ENOXAPARINA SODICA 40MG | ENOXAPARINA SODICA 40MG/0,4ML |
| 3906 | (bruto, não padronizado) | ENOXAPARINA SODICA 40MG/0,4ML |
| 4284 | ENOXAPARINA SODICA 40MG | ENOXAPARINA SODICA 40MG/0,4ML |
| 268 | ENOXAPARINA SODICA 60MG | ENOXAPARINA SODICA 60MG/0,6ML |
| 3907 | (bruto, não padronizado) | ENOXAPARINA SODICA 60MG/0,6ML |
| 4283 | ENOXAPARINA SODICA 60MG | ENOXAPARINA SODICA 60MG/0,6ML |
| 269 | ENOXAPARINA SODICA 80MG | ENOXAPARINA SODICA 80MG/0,8ML |
| 3908 | (bruto, não padronizado) | ENOXAPARINA SODICA 80MG/0,8ML |
| 4285 | ENOXAPARINA SODICA 80MG | ENOXAPARINA SODICA 80MG/0,8ML |
| 1946 | (bruto, não padronizado) | ENOXAPARINA SODICA 40MG/0,4ML |
| 8592 | (vazio) | SORO FISIOLOGICO NASAL SPRAY 0,9% 100ML |
| 8549 | (vazio) | SORO FISIOLOGICO NASAL SPRAY 0,9% 100ML |
| 9031 | (vazio) | SORO FISIOLOGICO NASAL SPRAY 0,9% 100ML |
| 9275 | (vazio) | SORO FISIOLOGICO NASAL SPRAY 0,9% 100ML |

Todos os 15 produtos também tiveram `sku_corrigido` marcado como `1` e `corrigido_em` atualizado para o momento da aplicação. `id 4285` já estava com `sku_corrigido=1` de uma correção anterior — permaneceu `1`, sem conflito.

Detalhamento completo (antes/depois de todos os campos) em `relatorios/sku_memoria_05b_pos_aplicacao.csv`.

## Marcas preenchidas
Marca (campo `precos_fornecedores.marca`, já que `produtos` não tem coluna própria de marca) foi preenchida — porque estava vazia — em **6 produtos**:
- `3906, 4284` → `HEPTRIS`
- `3907, 4283` → `HEPTRIS`
- `3908, 4285` → `HEPTRIS`

**1 produto não pôde receber a marca**, mesmo estando aprovado e com `marca_sugerida` preenchida: `id 8592` (`marca_sugerida = NASOJET`) não tem nenhuma linha em `precos_fornecedores` — não há onde gravar a marca. O SKU_MASTER foi aplicado normalmente; a marca fica pendente para quando esse produto tiver algum registro de preço/fornecedor associado.

## Categorias preenchidas
Categoria foi preenchida — porque estava vazia — em **1 produto**: `id 4283` → `MEDICAMENTOS`.

## Marcas/categorias preservadas (não sobrescritas)
Por regra explícita desta fase, nenhum valor já preenchido foi sobrescrito:

- **Marca já preenchida, preservada**: `267, 2016, 268, 269` (marca = `VIATRIS`) e `1946` (marca = `EUROFARMA LABORATORIOS S.`). A sugestão da memória (`HEPTRIS`/`VERSA`, o nome comercial correto) **não foi aplicada** nesses casos porque o campo já tinha um valor (o fabricante, tecnicamente, estava gravado no campo marca) — fica registrado como divergência a resolver em uma fase futura com autorização explícita, não nesta.
- **Categoria já preenchida, preservada**: `267, 2016, 4284, 4285, 8592, 8549, 9031, 9275` (já `MEDICAMENTOS`, sem alteração necessária); `3906, 3907, 3908` (`"MARCAS UQ"`, valor não padronizado mas preenchido); `268, 269, 1946` (`"MEDICAMENTO"`, singular, não padronizado mas preenchido). Nenhum desses 9 produtos com categoria não padronizada foi corrigido nesta fase — fica como candidato a uma limpeza de dados futura e separada.

## Confirmações
- **`produto_padrao` não foi alterado** em nenhum dos 15 produtos — verificado por leitura pós-aplicação e comparação byte a byte com o valor capturado antes da escrita (confere em 100% dos casos).
- **Cascata não foi usada** — cada produto foi atualizado individualmente, sem qualquer propagação para produtos semelhantes ou duplicados.
- **Dicionário Mestre MEDREG não foi alterado** — nenhum arquivo em `data/dicionario_mestre/` foi tocado nesta fase.
- **Bionexo não foi tocado.**
- **`app.py`, `templates/` e `core/` não foram alterados** — apenas dados foram escritos no banco via SQL direto, executado fora da aplicação Flask.
- Todas as alterações foram registradas na tabela `auditoria_sku` (22 registros: 15 de `sku_master`, 1 de `categoria`, 6 de `marca`), com `origem_correcao = 'SKU-MEMORIA-05B'`, permitindo rastreabilidade completa e possível reversão manual se necessário.
- `python -m py_compile app.py` executado com sucesso (sanity check; `app.py` não foi alterado nesta fase).

## Recomendação final
**APLICACAO_CONTROLADA_CONCLUIDA**

Os 15 produtos aprovados foram padronizados com sucesso, com rastro de auditoria completo e backup do banco disponível para reversão, se necessário. Duas pendências ficaram registradas para decisão futura (fora do escopo desta fase): (1) marca não gravada para `id 8592` por ausência de registro em `precos_fornecedores`; (2) 4 produtos com marca já preenchida com o nome do fabricante em vez do nome comercial correto, e 9 produtos com categoria não padronizada — nenhum dos dois foi alterado sem autorização explícita adicional.
