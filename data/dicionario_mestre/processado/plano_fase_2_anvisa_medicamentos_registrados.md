# Plano FASE 2 - ANVISA Medicamentos Registrados

Data: 2026-06-26

## Objetivo da FASE 2
Planejar a incorporacao controlada da fonte oficial ANVISA Medicamentos Registrados como complemento externo ao Dicionario Mestre de Medicamentos.

## Diferenca entre DCB e Medicamentos Registrados
- DCB: base oficial de denominacoes comuns e principios ativos. Serve como fundamento terminologico e padronizacao de substancias.
- Medicamentos Registrados: fonte de produtos/medicamentos regularizados na Anvisa. Deve complementar a DCB com dados de produto, apresentacao, registro e empresa.

## Campos que podem complementar o dicionario_mestre_medicamentos.csv
Campos provaveis a preencher ou apoiar em fases futuras:
- nome comercial/produto
- principio ativo
- concentracao
- forma farmaceutica
- apresentacao
- via de uso, se disponivel
- numero de registro
- empresa detentora
- situacao do registro
- data de validade/publicacao, se disponivel

## Estrategia de vinculo com DCB
- Vincular inicialmente por principio ativo/denominacao normalizada.
- Usar a DCB como base oficial de principio ativo.
- Nunca vincular por SKU_MASTER nesta fase.
- Nao usar fonte interna nesta fase.
- Tratar divergencias, sinonimos, sais e combinacoes de principios ativos em auditoria separada.

## Estrutura proposta das proximas fases
- FASE 2.1 captura bruta controlada: capturar metadados e arquivo bruto oficial, se autorizado.
- FASE 2.2 processamento intermediario: normalizar arquivo bruto para CSV intermediario auditavel.
- FASE 2.3 auditoria: avaliar campos, duplicidades, vazios, principio ativo e registros.
- FASE 2.4 pre-carga: gerar proposta de enriquecimento sem alterar dicionario final.
- FASE 2.5 revisao: produzir amostras e pendencias para revisao humana.
- FASE 2.6 aplicacao controlada: aplicar somente se houver aprovacao explicita e backup.

## Travas antes de qualquer aplicacao real
- Validar fonte oficial e dicionario de dados.
- Preservar arquivo bruto.
- Nao alterar dicionario final sem pre-carga, auditoria, revisao e aprovacao explicita.
- Criar backup antes de qualquer aplicacao.
- Nao acessar banco.
- Nao usar fonte interna.
- Nao aplicar SKU_MASTER.

## Recomendacao tecnica
Iniciar FASE 2.1 com captura controlada dos metadados do conjunto "Medicamentos Registrados no Brasil" e identificacao do recurso tabular oficial, sem mesclagem no Dicionario Mestre.

## Confirmacoes desta fase
- Nenhum dicionario final foi alterado.
- Nenhum banco foi alterado.
- Nenhuma fonte interna foi usada.
- Nenhum SKU_MASTER foi aplicado.
- Nenhum arquivo de dados foi baixado.
