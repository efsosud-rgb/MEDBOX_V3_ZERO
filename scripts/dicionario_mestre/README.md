# Scripts do Dicionario Mestre MEDBOX

## Fluxo correto do Dicionario Mestre

- A fonte externa oficial e a base principal do Dicionario Mestre.
- A fonte interna e auxiliar e so entra depois, para comparacao, validacao, lacunas e auditoria.
- Nao usar base interna para criar o dicionario inicial.
- Nao aplicar `SKU_MASTER` automaticamente.
- Cada fonte externa deve ter rastreabilidade completa.
- Cada etapa deve ser revisada antes de commit.
- Cada fonte externa precisa ter URL oficial validada antes de captura.
- O dicionario inicial nao deve ser construído a partir de fontes internas.

## Plano de trabalho

1. Planejar e catalogar fontes externas oficiais.
2. Capturar manualmente as fontes externas aprovadas.
3. Normalizar arquivos brutos para area processada.
4. Mesclar fontes externas validadas.
5. Usar fontes internas apenas como apoio posterior.
6. Gerar previas com rastreabilidade.
7. Aplicar somente apos aprovacao humana.
