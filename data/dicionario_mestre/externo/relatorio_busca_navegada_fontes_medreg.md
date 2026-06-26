# FASE 2.14C-R — Busca navegada profunda de fontes públicas MEDREG

## Objetivo
Mapear fontes públicas oficiais e estruturadas para enriquecer MEDREG com forma farmacêutica, concentração, apresentação, via de uso, princípio ativo, empresa, registro ANVISA, código GGREM, bula e vocabulários controlados.

## Contexto
A captura direta da FASE 2.14B não gerou dados úteis e encontrou HTTP 429. Por isso, a estratégia passa a priorizar fontes públicas estruturadas e baixáveis, deixando ANVISA Consultas como fallback.

## Método
Foram feitas buscas e navegação curta em páginas oficiais. As páginas foram abertas e lidas apenas o suficiente para registrar órgão responsável, formato provável, campos potenciais, chave de cruzamento, risco e recomendação. Não houve download de base grande, leitura de arquivo gigante, scraping massivo nem nova captura da amostra 100.

## Fontes pesquisadas
- Dados Abertos ANVISA: https://www.gov.br/anvisa/pt-br/acessoainformacao/dadosabertos
- Medicamentos registrados no Brasil / dados.gov.br: https://dados.gov.br/dados/conjuntos-dados/medicamentos-registrados-no-brasil
- CMED listas de preços: https://www.gov.br/anvisa/pt-br/assuntos/medicamentos/cmed/precos
- Como consultar listas CMED: https://www.gov.br/anvisa/pt-br/assuntos/medicamentos/cmed/precos/como-consultar/como-consultar-as-listas
- Bulário Eletrônico ANVISA: https://www.gov.br/anvisa/pt-br/sistemas/bulario-eletronico
- Consulta a registro de medicamentos: https://www.gov.br/anvisa/pt-br/sistemas/consulta-a-registro-de-medicamentos
- Sistema de Consultas ANVISA: https://consultas.anvisa.gov.br/#/medicamentos/
- DCB ANVISA: https://www.gov.br/anvisa/pt-br/assuntos/farmacopeia/dcb
- Farmacopeia Brasileira: https://www.gov.br/anvisa/pt-br/assuntos/farmacopeia/farmacopeia-brasileira
- Medicamentos genéricos e similares: https://www.gov.br/anvisa/pt-br/assuntos/medicamentos/genericos
- Medicamentos de referência: https://www.gov.br/anvisa/pt-br/assuntos/medicamentos/medicamentos-de-referencia

## Fontes úteis encontradas

### Fontes principais
- Dados Abertos ANVISA.
- Medicamentos registrados no Brasil / dados.gov.br.
- DCB ANVISA, para princípio ativo, DCB, CAS e nomenclatura.

### Fontes complementares
- CMED listas de preços, principalmente para apresentação comercial, concentração descrita e código GGREM.
- Bulário Eletrônico ANVISA, principalmente para texto técnico, via de uso e validações.
- Farmacopeia Brasileira / vocabulários controlados, para normalização de termos.

### Fontes de validação
- Como consultar listas CMED.
- Medicamentos genéricos e similares.
- Medicamentos de referência.

### Fallback
- Consulta a registro de medicamentos.
- Sistema de Consultas ANVISA.

### Descartadas ou não recomendadas como fonte principal
- Consulta direta de volume no Sistema de Consultas ANVISA, porque a FASE 2.14B registrou HTTP 429 consecutivo.
- Painéis sem exportação direta documentada, se dependerem de automação frágil ou tentativa de contorno.

## Links de arquivos ou bases encontrados
- Dados Abertos ANVISA: página oficial de acesso a bases abertas do órgão.
- Medicamentos registrados no Brasil / dados.gov.br: conjunto oficial com base estruturada em CSV.
- CMED listas de preços: página oficial com listas em PDF/XLS e painel.
- DCB ANVISA: página oficial que direciona para a Biblioteca Digital da Anvisa.
- Bulário Eletrônico ANVISA: página oficial de consulta de bulas.
- Farmacopeia Brasileira: página oficial com volumes e documentos técnicos.

Nenhuma base grande foi baixada nesta fase; os links foram apenas registrados para planejamento.

## Ranking recomendado
1. Fontes estruturadas baixáveis oficiais: Dados Abertos ANVISA e Medicamentos registrados no Brasil.
2. CMED/listas de preços, especialmente para apresentação, concentração comercial e código GGREM.
3. DCB/vocabulários controlados ANVISA/Farmacopeia.
4. Bulário Eletrônico, como complemento textual e fonte de validação.
5. ANVISA Consultas, apenas como fallback individual, lento e com baixa frequência.

## Estratégia de cruzamento
Usar, quando disponíveis:
- registro_anvisa
- nome_produto
- principio_ativo
- empresa
- codigo_ggrem
- dcb
- cas

O cruzamento deve preservar rastreabilidade por fonte e registrar divergências sem aplicar alterações diretamente ao dicionário final.

## Riscos
- Divergência de nomes entre bases.
- Ausência de campos alvo em bases estruturadas.
- Chaves incompletas ou inconsistentes.
- Formatos difíceis ou variáveis entre publicações.
- PowerBI sem exportação direta simples.
- HTTP 429 em consulta individual.
- Texto livre do Bulário exigindo auditoria antes de qualquer uso definitivo.

## Próxima fase recomendada
FASE 2.14D — Planejamento de ingestão multi-fonte estruturada, definindo quais arquivos baixar, onde salvar e como validar, sem aplicar no dicionário final.

## Decisão técnica
APTO_PARA_PLANEJAR_INGESTAO_MULTI_FONTE_ESTRUTURADA
