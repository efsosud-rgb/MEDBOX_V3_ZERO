# FASE 2.14G-1 — Download controlado Medicamentos registrados / dados.gov.br

## Objetivo

Executar download controlado de uma única fonte oficial estruturada para validar o pipeline de ingestão.

## Fonte autorizada

Medicamentos registrados no Brasil / dados.gov.br:
https://dados.gov.br/dados/conjuntos-dados/medicamentos-registrados-no-brasil

## Resultado do download

- Download executado: tentativa controlada executada somente para a fonte autorizada.
- Arquivos baixados: nenhum.
- Diretório bruto usado: `data/dicionario_mestre/bruto/medicamentos_registrados_dados_gov/`.
- Manifesto criado: `data/dicionario_mestre/bruto/medicamentos_registrados_dados_gov/manifesto_download.csv`.
- Status: `PENDENTE_LINK_DOWNLOAD_NAO_LOCALIZADO`.
- Motivo: a API pública testada retornou HTTP 401 e a página pública inicial não expôs link CSV/ZIP/XLS/XLSX simples no HTML lido.
- URL de origem: https://dados.gov.br/dados/conjuntos-dados/medicamentos-registrados-no-brasil
- Tamanho: 0 bytes baixados.
- Hash sha256: não aplicável, pois nenhum arquivo foi baixado.

## Resultado da validação

- Validação executada: sim.
- Formato detectado: nenhum arquivo bruto disponível.
- Quantidade de arquivos: 0.
- Linhas detectadas: não aplicável.
- Colunas detectadas: não aplicável.
- Campos úteis encontrados: nenhum, porque não houve arquivo bruto.
- Limitação: a fonte precisa de revisão do método de localização do recurso baixável antes de nova tentativa.

## Confirmações de segurança

- Apenas uma fonte foi tentada.
- CMED não foi baixada.
- DCB não foi baixada.
- Bulário não foi baixado.
- Farmacopeia não foi baixada.
- ANVISA Consultas por registro não foi usada.
- Scraping não foi executado.
- Banco não foi alterado.
- Dicionário final não foi alterado.
- Fonte interna não foi usada.
- SKU_MASTER não foi aplicado.
- Nenhuma fonte alternativa foi usada.
- Nenhuma técnica de contorno foi usada.

## Arquivos gerados

- data/dicionario_mestre/bruto/medicamentos_registrados_dados_gov/manifesto_download.csv
- data/dicionario_mestre/processado/log_download_medicamentos_registrados_dados_gov.csv
- data/dicionario_mestre/processado/validacao_medicamentos_registrados_dados_gov.csv

## Decisão técnica

PENDENTE_REVISAR_DOWNLOAD_MEDICAMENTOS_REGISTRADOS

## Próxima fase recomendada

Revisar link ou método de download da fonte Medicamentos registrados antes de avançar para CMED.
