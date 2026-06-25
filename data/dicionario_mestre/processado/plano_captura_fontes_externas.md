# Plano de Captura - Fontes Externas do Dicionario Mestre MEDBOX

## 1. Objetivo

Construir o Dicionario Mestre MEDBOX a partir de fontes externas oficiais e confiaveis.
As URLs oficiais devem ser validadas antes de cada captura.

## 2. Ordem de captura

1. ANVISA DCB
2. ANVISA Medicamentos Registrados
3. Bulário Eletrônico ANVISA
4. ANVISA Produtos para Saúde
5. WHO ATC/DDD
6. FDA AccessGUDID
7. Catálogos oficiais de fabricantes
8. Compêndios técnicos

## 3. Regra de prioridade

- Medicamentos começam pela ANVISA DCB.
- Medicamentos registrados e bulas complementam a base.
- Correlatos e produtos para saúde começam por ANVISA Produtos para Saúde.
- FDA AccessGUDID é complemento internacional.
- Fabricantes e compêndios validam detalhes específicos.

## 4. Regra de rastreabilidade

Cada produto ou termo futuro deve guardar:

- fonte
- URL ou caminho do arquivo bruto
- data de captura
- data da fonte, quando existir
- tipo de fonte
- confiança da fonte
- status de validação
- observação

## 5. Regra de segurança

- Não alterar banco.
- Não aplicar SKU_MASTER.
- Não mesclar automaticamente.
- Não sobrescrever dicionário final sem revisão.
- Toda transformação deve gerar relatório.

## 6. Diretrizes operacionais

- A DCB deve ser capturada pela página oficial da Farmacopeia/ANVISA.
- Produtos para Saúde deve começar pela lista oficial de dispositivos médicos regularizados.
- consultas.anvisa.gov.br pode ser usado como acesso operacional quando a página gov.br apontar para o sistema.
- As URLs oficiais devem ser checadas antes de cada captura para evitar referência desatualizada.

## 7. Próxima fase

Apos aprovacao deste plano, iniciar Fase 1: captura manual e validada da ANVISA DCB.
