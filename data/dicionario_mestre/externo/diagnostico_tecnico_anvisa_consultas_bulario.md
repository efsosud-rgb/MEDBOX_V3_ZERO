# FASE 2.13 — Diagnóstico técnico ANVISA Consultas/Bulário

## Objetivo da fase

Diagnosticar tecnicamente, sem captura de dados em massa e sem alterar o Dicionário Mestre, como a fonte ANVISA Consultas e, de forma complementar, o Bulário ANVISA podem ser usadas em fases futuras para enriquecer os registros `ANVISA_MEDREG` com `forma_farmaceutica`, `concentracao`, `apresentacao` e `via_uso`.

Esta fase parte da decisão técnica da FASE 2.12: `APTO_PARA_DIAGNOSTICAR_FONTE_OFICIAL_FORMA_CONCENTRACAO_APRESENTACAO_VIA`.

## Escopo permitido

- Ler artefatos locais da FASE 2.12.
- Documentar viabilidade técnica da fonte ANVISA Consultas.
- Documentar uso complementar do Bulário ANVISA.
- Definir riscos, travas e critérios de amostragem para fase futura.
- Criar checklist técnico da FASE 2.13.
- Atualizar `CHECKPOINT.md` com o resultado da fase.

## Escopo proibido

- Capturar dados reais em massa.
- Executar crawler, scraping ou automação de consulta.
- Baixar bases completas.
- Preencher `forma_farmaceutica`, `concentracao`, `apresentacao` ou `via_uso`.
- Alterar `data/dicionario_mestre/dicionario_mestre_medicamentos.csv` ou qualquer dicionário final.
- Alterar banco, arquivos `.db`, `app.py`, `core/`, `templates/`, `uploads/`, `backups/`, `.claude/`, fontes internas ou arquivos Bionexo.
- Aplicar SKU_MASTER.

## Diagnóstico da fonte ANVISA Consultas

### Finalidade esperada

A fonte ANVISA Consultas deve ser tratada como a fonte principal futura para detalhar medicamentos registrados por número de registro. A expectativa técnica é que ela permita consultar a página operacional de medicamentos e obter dados por produto/apresentação com maior estrutura do que o CSV público `DADOS_ABERTOS_MEDICAMENTOS.csv`.

### Chave provável de consulta

A chave preferencial para consulta futura é o número de registro ANVISA já presente nos registros `ANVISA_MEDREG`. Essa chave oferece rastreabilidade direta e reduz ambiguidade frente a nome comercial, empresa ou princípio ativo.

### Campos-alvo

Campos que devem ser investigados na captura bruta futura:

- `forma_farmaceutica`
- `concentracao`
- `apresentacao`
- `via_uso`

### Possíveis dificuldades

- Portal dinâmico com navegação dependente de JavaScript.
- Necessidade de consulta individual por número de registro.
- Variação de layout entre medicamentos, categorias regulatórias e apresentações.
- Instabilidade do portal, timeouts ou mudanças de estrutura HTML.
- Bloqueios temporários por volume de consultas.
- Paginação ou expansão de detalhes por apresentação.
- Campos ausentes para parte dos registros.
- Duplicidade por apresentação: um registro pode ter múltiplas apresentações comerciais.
- Diferença conceitual entre medicamento, produto registrado e apresentação comercial.
- Possibilidade de concentração estar embutida no nome/apresentação, não em campo isolado.

### Risco de scraping

O risco técnico é relevante porque a fonte provavelmente exige consulta individual e interpretação de HTML dinâmico. Por isso, a fase futura deve começar com amostra pequena, limites explícitos, pausas, registro de falhas e armazenamento bruto separado. Não deve haver coleta massiva antes de validação humana da amostra.

### Recomendação para FASE 2.14

Executar apenas captura bruta controlada de amostra pequena, preferencialmente 100 registros `ANVISA_MEDREG`, sem alterar dicionário final. A captura deve salvar bruto separado e registrar status por registro, inclusive falhas, sem interromper todo o processo.

## Diagnóstico da fonte Bulário ANVISA

### Finalidade complementar

O Bulário ANVISA deve ser fonte complementar, útil para confirmar ou enriquecer informações textuais relacionadas a via de uso, forma, apresentações, composição e posologia quando essas informações estiverem disponíveis em bula.

### Possível uso

- Validar `via_uso` quando a consulta de registro estiver incompleta.
- Apoiar identificação de forma farmacêutica e apresentação quando houver texto estruturado.
- Registrar evidência complementar em casos de divergência ou ausência de campo na ANVISA Consultas.

### Limitações

- Pode envolver HTML e PDF.
- Pode haver bula do paciente e bula do profissional para o mesmo produto.
- Textos podem ser longos, não estruturados e com variação de linguagem.
- A apresentação comercial nem sempre aparece como campo normalizado.
- Pode haver ausência de bula para alguns registros.
- Parsing textual aumenta risco de inferência indevida.

### Recomendação de uso

Usar apenas como fonte complementar, nunca como fonte principal para aplicação automática. Qualquer extração do Bulário deve ser auditável, preservar trecho bruto, evitar inferência e passar por auditoria antes de dry-run.

## Estratégia técnica recomendada para fases futuras

- FASE 2.14: captura bruta controlada com amostra pequena, preferencialmente 100 registros `ANVISA_MEDREG`.
- FASE 2.15: processamento intermediário dos campos capturados, sem alterar dicionário final.
- FASE 2.16: auditoria do intermediário, duplicidades, ausências, divergências e qualidade de mapeamento.
- FASE 2.17: dry-run de enriquecimento, gerando diff e checklist sem escrita no dicionário final.
- FASE 2.18: aplicação controlada somente com aprovação explícita, backup prévio e regra de não sobrescrever campos já preenchidos.

## Critérios propostos para seleção da amostra 100 da FASE 2.14

A FASE 2.14 ainda não deve ser executada nesta fase. Para quando for autorizada, a amostra deve seguir estes critérios:

- Selecionar registros `ANVISA_MEDREG` com número de registro válido.
- Priorizar registros com `dcb` e `cas` preenchidos, pois têm maior rastreabilidade.
- Incluir alguns registros sem `dcb`/`cas` para medir comportamento da fonte em casos pendentes.
- Incluir diferentes medicamentos, empresas e categorias regulatórias.
- Evitar repetição excessiva do mesmo princípio ativo.
- Incluir registros com nomes comerciais simples e compostos.
- Registrar falhas por registro sem interromper todo o processo.
- Salvar evidência bruta separada, sem normalização manual.

## Campos técnicos sugeridos para captura bruta futura

- `registro_anvisa`
- `nome_produto`
- `empresa`
- `principio_ativo`
- `forma_farmaceutica`
- `concentracao`
- `apresentacao`
- `via_uso`
- `fonte`
- `url_consulta`
- `data_captura`
- `status_captura`
- `observacao`

## Riscos e travas de segurança

- Não aplicar direto no dicionário final.
- Manter dados brutos separados de intermediários e dicionários finais.
- Preservar rastreabilidade por URL, data de captura e número de registro.
- Exigir auditoria antes de qualquer dry-run.
- Exigir aprovação explícita antes de qualquer aplicação.
- Não usar fonte interna ou SKU_MASTER para preencher lacunas.
- Não inferir campos ausentes por aproximação textual.
- Não sobrescrever campo final já preenchido em fases futuras.
- Registrar falhas, ausências e múltiplas apresentações como pendências auditáveis.

## Decisão técnica final da FASE 2.13

`APTO_PARA_PREPARAR_CAPTURA_BRUTA_CONTROLADA_AMOSTRA_100`

## Confirmações

- Nenhuma captura bruta foi executada.
- Nenhum scraping foi executado.
- Nenhum dado foi baixado em massa.
- Dicionário final não foi alterado.
- Banco não foi alterado.
- Fonte interna não foi usada.
- SKU_MASTER não foi aplicado.
