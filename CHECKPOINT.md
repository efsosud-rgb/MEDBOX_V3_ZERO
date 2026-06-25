# CHECKPOINT MEDBOX_V3_ZERO

## Estado atual
- Data/hora: 2026-06-25 10:24:00 -03:00
- Agente em uso: Codex
- Branch: melhoria/auditoria-sku-master-todos-produtos
- Tarefa atual: gerar amostras de revisao da previa de normalizacao geral de `SKU_MASTER`
- Status: previa principal e amostras geradas; banco nao alterado; commit nao realizado

## Regras inviolaveis
- Nunca alterar banco sem backup previo.
- Nunca alterar `descricao_original`.
- SKU_MASTER nao substitui `descricao_original`.
- Nunca deletar historico de precos.
- Precos antigos vao para `precos_fornecedores_historico`.
- Nao misturar fornecedor com fabricante/marca.
- Nao fazer patch as cegas: diagnosticar antes.
- Nao mexer nos precos.
- Nao alterar `produtos.fabricante`.
- Nao alterar historico de precos.
- Nao executar SQL de escrita nesta etapa.
- Nao fazer commit nesta etapa.

## Arquivos permitidos nesta tarefa
- `scripts/diagnosticos/previa_normalizacao_sku_master.csv`
- `scripts/diagnosticos/amostra_normalizacao_sku_master_top100.csv`
- `scripts/diagnosticos/amostra_normalizacao_sku_master_fabricante_categoria.csv`
- `scripts/diagnosticos/amostra_normalizacao_sku_master_medidas.csv`
- `scripts/diagnosticos/resumo_normalizacao_sku_master.txt`
- `CHECKPOINT.md`

## Arquivos proibidos nesta tarefa
- `banco/`
- `uploads/`
- `descricao_original`
- historico de precos
- produtos.fabricante
- precos
- scripts de aplicacao/correcao

## Contexto anterior
- Diagnostico somente leitura identificou:
  - produtos total: 11.105
  - produtos ativos: 10.839
  - produtos com `sku_master` vazio/nulo: 6.308
  - produtos com `sku_master` preenchido: 4.797
  - produtos com fabricante vazio: 7.810
  - produtos com categoria vazia: 311
  - 102 grupos de `sku_master` com campos propagaveis em potencial.
- Bases candidatas:
  - `produtos.sku_master`
  - `produtos.produto_padrao`
  - `uploads/SKU_MASTER_2_0.xlsx`
  - `uploads/PRODUTOS.xlsx`
  - `equivalencias.descricao_equivalente`
  - `dicionario_termos`
  - `dicionario_sinonimos`
  - `sku_master_regras`
  - funcoes existentes em `core/banco.py`, `core/busca_inteligente.py`, `core/auditoria_sku_master.py`, `core/motor_sku_master.py`.

## Tarefa executada
- Criado arquivo: `scripts/diagnosticos/previa_normalizacao_sku_master.csv`
- Geracao feita por processo diagnostico inline, sem criar script de aplicacao.
- Banco aberto em modo somente leitura (`mode=ro`).
- XLSX lidos em modo somente leitura.
- Indice de referencia montado em memoria usando:
  - `produtos.sku_master` preenchido
  - `uploads/SKU_MASTER_2_0.xlsx`
  - `uploads/PRODUTOS.xlsx`
  - `equivalencias.descricao_equivalente`
  - `dicionario_termos`
  - `sku_master_regras`
- Foram bloqueadas referencias ruins:
  - `SKU PENDENTE*`
  - categoria `SKU PENDENTE DE PADRONIZACAO`
  - referencias com cara de empresa/marca/fabricante
  - referencias curtas demais sem termo tecnico critico.
- Criados arquivos de amostra para revisao humana:
  - `scripts/diagnosticos/amostra_normalizacao_sku_master_top100.csv`
  - `scripts/diagnosticos/amostra_normalizacao_sku_master_fabricante_categoria.csv`
  - `scripts/diagnosticos/amostra_normalizacao_sku_master_medidas.csv`
  - `scripts/diagnosticos/resumo_normalizacao_sku_master.txt`

## Totais da geracao
- Total de produtos ativos analisados: 10.839
- Total de referencias no indice final: 20.321
- Referencias bloqueadas por parecerem empresa/marca/fabricante: 1.486
- Referencias curtas bloqueadas: 155
- Total de candidatos encontrados antes do limite: 5.495
- Total de linhas gravadas no CSV: 2.000
- Total ALTA: 2.000
- Total MEDIA: 0
- Total BAIXA: 0
- Total com `sku_master` atual vazio: 2.000
- Total com sugestao de `sku_master`: 2.000
- Total com sugestao de fabricante: 43
- Total com sugestao de categoria: 9
- Total bloqueado por conflito de fabricante: 28
- Total bloqueado por conflito de categoria: 1

## Validacao do CSV
- `decisao_usuario` vazia nas 2.000 linhas.
- Nenhuma linha com `sku_master_sugerido` iniciando por `SKU PENDENTE`.
- Nenhuma linha com `sku_master_sugerido = PREMIUM`.
- Todas as 2.000 sugestoes de `sku_master_sugerido` estao em maiusculas.
- Colunas obrigatorias presentes:
  - `produto_id`
  - `descricao_atual`
  - `origem_descricao`
  - `sku_master_atual`
  - `sku_master_sugerido`
  - `score`
  - `nivel_confianca`
  - `origem_do_match`
  - `fabricante_atual`
  - `fabricante_sugerido`
  - `marca_atual`
  - `marca_sugerida`
  - `categoria_atual`
  - `categoria_sugerida`
  - `pode_propagar_fabricante`
  - `pode_propagar_categoria`
  - `motivo`
  - `decisao_usuario`

## Amostras geradas
- `amostra_normalizacao_sku_master_top100.csv`: 100 linhas.
- `amostra_normalizacao_sku_master_fabricante_categoria.csv`: 48 linhas unicas com `fabricante_sugerido` e/ou `categoria_sugerida`.
  - A previa principal possui 43 linhas com fabricante sugerido e 9 com categoria sugerida; ha intersecoes entre os grupos.
- `amostra_normalizacao_sku_master_medidas.csv`: 100 linhas com termos tecnicos criticos.
- `resumo_normalizacao_sku_master.txt`: 87 linhas.

## Riscos apontados no resumo
- Descricoes muito curtas ou sugestoes muito curtas: 168.
- Sugestoes com diferenca grande de tamanho: 8.
- Descricao contem termo tecnico ausente no SKU sugerido: 40.
- SKU sugerido contem termo tecnico ausente na descricao: 7.
- Linhas com fabricante/categoria sugeridos: 48.
- Linhas com conflitos bloqueados na amostra gravada: 0.

## Comandos executados nesta etapa
- `git status --short`
- `Test-Path uploads\SKU_MASTER_2_0.xlsx`
- `Test-Path uploads\PRODUTOS.xlsx`
- `Test-Path banco\medbox_v3.db`
- Geracao diagnostica via `py -B -` com SQLite somente leitura e `openpyxl` read-only.
- `Import-Csv -Delimiter ';' -Path scripts\diagnosticos\previa_normalizacao_sku_master.csv`
- `Get-Content scripts\diagnosticos\previa_normalizacao_sku_master.csv -TotalCount 8`
- `Export-Csv` para as tres amostras de revisao.
- `Set-Content` para `resumo_normalizacao_sku_master.txt`.
- `Get-Content scripts\diagnosticos\resumo_normalizacao_sku_master.txt -TotalCount 80`
- `git diff --stat`
- `git diff --check`
- `git diff --name-only -- banco`
- `Get-Date -Format "yyyy-MM-dd HH:mm:ss zzz"`

## Confirmacoes
- Banco nao foi alterado nesta etapa.
- Nenhum `UPDATE`, `INSERT`, `DELETE`, `DROP`, `ALTER` ou `CREATE` foi executado nesta etapa.
- Nenhum commit foi feito nesta etapa.
- Nao foi criado script de aplicacao.
- `descricao_original` nao foi alterada.
- `produtos.fabricante` nao foi alterado.
- Precos nao foram alterados.
- Historico de precos nao foi alterado.
- Nao foi feito commit.

## Riscos / observacoes
- A previa e diagnostica; nao autoriza aplicacao automatica.
- As 2.000 linhas sao os melhores candidatos apos ordenacao por confianca/score e limite inicial.
- Mesmo com filtros anti-marca/fabricante, a coluna `fabricante_sugerido` deve ser revisada manualmente antes de qualquer propagacao.
- Sugestoes ALTA incluem matches exatos/fortes contra bases internas; ainda precisam de amostragem humana por familia antes de aplicar.

## Proximo passo recomendado
- Revisao humana das amostras antes de qualquer aplicacao:
  - revisar `amostra_normalizacao_sku_master_top100.csv`
  - revisar `amostra_normalizacao_sku_master_fabricante_categoria.csv`
  - revisar `amostra_normalizacao_sku_master_medidas.csv`
  - usar `resumo_normalizacao_sku_master.txt` para priorizar riscos.

# Checkpoint - Revisao textual das amostras de normalizacao SKU_MASTER

Data: 2026-06-25

## Tarefa executada
- Criada revisao textual diagnostica das amostras em:
  - `scripts/diagnosticos/revisao_amostras_normalizacao_sku_master.txt`
- Arquivos analisados:
  - `scripts/diagnosticos/amostra_normalizacao_sku_master_top100.csv`
  - `scripts/diagnosticos/amostra_normalizacao_sku_master_fabricante_categoria.csv`
  - `scripts/diagnosticos/amostra_normalizacao_sku_master_medidas.csv`
  - `scripts/diagnosticos/resumo_normalizacao_sku_master.txt`

## Totais da revisao
- Linhas unicas analisadas nas amostras: 143.
- Casos classificados como mais seguros pelos criterios da revisao: 84.
- Casos que exigem revisao humana: 59.
- Linhas com `fabricante_sugerido`: 43.
- Linhas com `categoria_sugerida`: 9.
- Divergencias tecnicas detectadas na amostra de medidas: 11.

## Principais riscos encontrados
- A previa principal tem 2.000 linhas classificadas como ALTA, mas o resumo ainda aponta riscos que impedem aplicacao em massa:
  - 168 descricoes/sugestoes muito curtas.
  - 8 sugestoes com diferenca grande de tamanho.
  - 40 casos em que a descricao contem termo tecnico ausente no SKU sugerido.
  - 7 casos em que o SKU sugerido contem termo tecnico ausente na descricao.
  - 48 linhas com fabricante/categoria sugeridos.
- `fabricante_sugerido` deve ser revisado separadamente para evitar mistura entre fabricante, marca e fornecedor.
- Medidas/concentracoes e termos como `MG`, `ML`, `%`, `MM`, `CM`, `FR`, `G`, `LUER`, `LOCK`, `AGULHA` e `CUFF` devem bloquear aplicacao quando divergirem.

## Recomendacao
- Nao aplicar as 2.000 linhas de uma vez.
- Primeiro lote recomendado: 25 a 50 linhas.
- O primeiro lote deve conter apenas linhas:
  - sem `fabricante_sugerido`;
  - sem `categoria_sugerida`;
  - sem divergencia de medida/concentracao;
  - sem descricao ou SKU muito curto;
  - sem diferenca grande de tamanho;
  - com `score >= 98`.
- Propagacao de fabricante/categoria deve ser tratada em lote separado, com aprovacao manual.

## Confirmacoes
- Banco nao foi consultado nem alterado nesta revisao.
- Nenhum `UPDATE`, `INSERT`, `DELETE`, `DROP`, `ALTER` ou `CREATE` foi executado.
- Nenhum script de aplicacao foi criado.
- Nenhuma correcao foi aplicada.
- Nenhum commit foi feito.

## Proximo passo recomendado
- Gerar CSV de lote piloto pequeno para aprovacao manual, com `decisao_usuario` vazia, e depois criar somente um dry-run sem UPDATE.

# Checkpoint - Lote piloto seguro para normalizacao SKU_MASTER

Data: 2026-06-25

## Tarefa executada
- Criado CSV de lote piloto em:
  - `scripts/diagnosticos/lote_piloto_normalizacao_sku_master.csv`
- Criado resumo legivel em:
  - `scripts/diagnosticos/resumo_lote_piloto_normalizacao_sku_master.txt`
- O lote foi gerado somente a partir de `scripts/diagnosticos/previa_normalizacao_sku_master.csv`.
- Banco nao foi consultado.

## Total do lote
- Candidatos elegiveis antes do limite: 1.798.
- Linhas selecionadas para o lote piloto: 50.

## Criterios aplicados
- Maximo de 50 linhas.
- `nivel_confianca = ALTA`.
- `sku_master_atual` vazio/nulo.
- `sku_master_sugerido` preenchido.
- `decisao_usuario` vazia.
- Sem `fabricante_sugerido`.
- Sem `categoria_sugerida`.
- Sem `pode_propagar_fabricante = SIM/TRUE/1`.
- Sem `pode_propagar_categoria = SIM/TRUE/1`.
- Sem divergencia de termos tecnicos:
  - `MG`
  - `ML`
  - `%`
  - `MM`
  - `CM`
  - `FR`
  - `G`
  - `LUER`
  - `LOCK`
  - `AGULHA`
  - `CUFF`
  - `ADULTO`
  - `INFANTIL`
  - `PEDIATRICO`
  - `ESTERIL`
  - `FILTRO`
- Sem descricao ou SKU sugerido muito curto.
- Sem diferenca grande de tamanho entre `descricao_atual` e `sku_master_sugerido`.
- Sem sugestao `SKU PENDENTE`.
- Sem sugestao `PREMIUM`.
- Sem proposta de alteracao/propagacao de fabricante ou categoria neste lote.

## Validacoes do lote
- Arquivo `lote_piloto_normalizacao_sku_master.csv` criado: sim.
- Arquivo `resumo_lote_piloto_normalizacao_sku_master.txt` criado: sim.
- Total de linhas: 50.
- Total esta entre 25 e 50: sim.
- `decisao_usuario` preenchida: 0.
- Sugestoes `sku_master_sugerido` em maiusculas: 50/50.
- Linhas com `fabricante_sugerido`: 0.
- Linhas com `categoria_sugerida`: 0.
- Sugestoes `SKU PENDENTE`: 0.
- Sugestoes `PREMIUM`: 0.
- Divergencias tecnicas detectadas: 0.

## Confirmacoes
- Banco nao foi alterado.
- Nenhum `UPDATE`, `INSERT`, `DELETE`, `DROP`, `ALTER` ou `CREATE` foi executado.
- Nenhum script de aplicacao foi criado.
- Nenhuma correcao foi aplicada.
- `descricao_original` nao foi alterada.
- `produtos.fabricante` nao foi alterado.
- Precos nao foram alterados.
- Historico de precos nao foi alterado.
- Nenhum commit foi feito.

## Proximo passo recomendado
- Revisar manualmente `scripts/diagnosticos/lote_piloto_normalizacao_sku_master.csv`.
- Somente depois de aprovacao manual, criar script de dry-run para esse lote, ainda sem aplicar UPDATE automaticamente.
