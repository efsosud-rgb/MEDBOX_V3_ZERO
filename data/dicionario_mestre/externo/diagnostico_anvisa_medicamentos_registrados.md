# Diagnostico ANVISA Medicamentos Registrados

Data: 2026-06-26

## Nome da fonte
ANVISA Medicamentos Registrados no Brasil.

## Orgao responsavel
Agencia Nacional de Vigilancia Sanitaria - Anvisa.

## URLs oficiais
- Pagina gov.br do sistema de consulta: https://www.gov.br/anvisa/pt-br/sistemas/consulta-a-registro-de-medicamentos
- Consulta operacional de medicamentos registrados: https://consultas.anvisa.gov.br/#/medicamentos/
- Base no Portal Brasileiro de Dados Abertos: https://dados.gov.br/dados/conjuntos-dados/medicamentos-registrados-no-brasil
- Noticia gov.br sobre novas bases de dados abertos, incluindo Medicamentos Registrados: https://www.gov.br/anvisa/pt-br/assuntos/noticias-anvisa/2021/anvisa-disponibiliza-dez-novas-bases-de-dados-abertos
- Plano de Dados Abertos ANVISA 2023-2025: https://www.gov.br/anvisa/pt-br/acessoainformacao/dadosabertos/arquivos/PlanodeDadosAbertosAnvisa20232025.pdf

## URLs operacionais candidatas
- Portal de consulta: https://consultas.anvisa.gov.br/#/medicamentos/
- Conjunto de dados: https://dados.gov.br/dados/conjuntos-dados/medicamentos-registrados-no-brasil
- Documentacao/dicionario de dados candidata: https://dados.anvisa.gov.br/dados/Documentacao_e_Dicionario_de_Dados_Registros_Validos_Medicamento_V1.pdf

## Evidencias oficiais encontradas
- A pagina gov.br "Consulta a registro de medicamentos" informa que o objetivo do sistema e permitir a consulta aos dados de registro de medicamentos e aponta para "Medicamentos registrados".
- A noticia gov.br de dados abertos da ANVISA informa a publicacao de bases no portal de dados abertos e lista "Medicamentos Registrados" entre elas.
- O Plano de Dados Abertos ANVISA 2023-2025 lista "Medicamentos Regularizados e Situacao do Registro", descrevendo dados de medicamentos regularizados, incluindo situacao de registro ativo ou nao, conforme o portal de consultas da Anvisa.
- A pagina de medicamentos pendentes de registro reforca que a consulta de medicamentos ja registrados permanece disponivel em https://consultas.anvisa.gov.br/#/medicamentos/.

## Formato provavel
- Portal de consulta web em consultas.anvisa.gov.br.
- Conjunto de dados em dados.gov.br, provavelmente com recurso tabular para download em fase futura.
- Documentacao candidata em PDF no dominio dados.anvisa.gov.br.
- O formato operacional exato da base deve ser confirmado na FASE 2.1, sem presumir antes de capturar os metadados do conjunto.

## Campos esperados
Campos esperados para complementar a DCB, sujeitos a confirmacao pelo dicionario oficial da base:
- nome comercial/produto
- principio ativo
- concentracao
- forma farmaceutica
- apresentacao
- via de uso, se disponivel
- numero de registro
- empresa detentora do registro
- situacao do registro
- data de validade ou publicacao, se disponivel
- categoria regulatoria, se disponivel

## Periodicidade
- O Plano de Dados Abertos indica que a base de medicamentos regularizados e situacao do registro deve refletir informacoes do portal de consultas da Anvisa.
- Periodicidade operacional exata da base "Medicamentos Registrados no Brasil" nao foi confirmada nesta fase e deve ser verificada na FASE 2.1 nos metadados do conjunto.

## Confiabilidade
- Alta, por se tratar de fonte oficial da Anvisa e de conjunto publicado no portal de dados abertos do governo federal.
- A fonte e adequada para complementar a DCB porque traz informacoes de produtos/medicamentos registrados, enquanto a DCB traz denominacoes oficiais de principios ativos.

## Riscos
- O portal dados.gov.br exige JavaScript para visualizacao completa, entao a captura automatica deve ser planejada com cuidado.
- A documentacao candidata em PDF deve ser baixada apenas em fase futura autorizada.
- Campos e formatos podem variar entre portal de consulta, dados abertos e documentacao.
- A vinculacao com a DCB deve ser feita por principio ativo/denominacao, nunca por SKU_MASTER nesta fase.
- Nomes comerciais e apresentacoes podem gerar multiplicidade de linhas por principio ativo.

## Recomendacao de captura futura
- FASE 2.1 deve capturar metadados do conjunto de dados e, se autorizado, o arquivo bruto oficial ou recurso tabular principal.
- Preservar arquivo bruto sem edicao manual.
- Registrar URL oficial, URL operacional, data/hora de captura, tamanho, formato, hash se viavel e dicionario de dados usado.
- Nao mesclar diretamente no dicionario final sem processamento intermediario, auditoria e revisao humana.

## Confirmacoes desta fase
- Nenhum arquivo da fonte foi baixado nesta fase.
- Nenhum banco foi acessado ou alterado.
- Nenhuma fonte interna foi usada.
- Nenhum SKU_MASTER foi aplicado.
- Nenhum dicionario final foi alterado.
