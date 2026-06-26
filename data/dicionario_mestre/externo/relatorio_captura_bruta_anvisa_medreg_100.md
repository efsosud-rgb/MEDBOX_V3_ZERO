# FASE 2.14B — Captura bruta controlada ANVISA MEDREG 100

## Objetivo

Executar captura bruta controlada, limitada e auditável para os 100 registros preparados na FASE 2.14A, usando apenas fonte pública oficial ANVISA autorizada, sem alterar dicionário final e sem alterar banco.

## Arquivo de entrada

- data/dicionario_mestre/processado/amostra_medreg_100_para_captura.csv

## Fontes consultadas

- ANVISA Consultas: https://consultas.anvisa.gov.br/#/medicamentos/

O Bulário ANVISA foi mantido como fonte complementar autorizada, mas não foi acionado porque a fonte principal não retornou dados estruturados aproveitáveis e a execução encontrou limitação HTTP 429.

## Estratégia usada

- Leitura da amostra local de 100 registros.
- Validação de origem e número de registro ANVISA.
- Teste controlado inicial com 3 registros.
- Execução limitada à amostra, com `MAX_REGISTROS=100`, pausa entre consultas e timeout.
- Consulta apenas a endpoints sob `https://consultas.anvisa.gov.br`.
- Registro de falhas sem salvar HTML bruto, cookies, tokens, headers sensíveis ou screenshots.
- Parada segura após bloqueios consecutivos (`HTTP 429`) sem tentar burlar ou insistir agressivamente.

## Totais

- Total de registros na amostra: 100
- Total com registro_anvisa: 100
- Total consultado na execução final: 14
- Total com captura OK: 0
- Total sem resultado: 11
- Total com falha: 0
- Total bloqueado/não automatizável: 3

## Campos brutos encontrados

Nenhum campo bruto estruturado foi capturado para:

- forma_farmaceutica
- concentracao
- apresentacao
- via_uso
- nome_produto
- empresa
- principio_ativo

## Campos não encontrados

Todos os campos-alvo permaneceram ausentes na captura desta fase, pois os endpoints simples testados não retornaram dados úteis e a fonte passou a responder HTTP 429.

## Limitações técnicas

- A consulta pública operacional parece depender de fluxo dinâmico/estrutura não exposta por endpoint simples por número de registro.
- As primeiras consultas retornaram `SEM_RESULTADO` nos endpoints testados.
- Após 14 registros consultados, ocorreram 3 respostas consecutivas `HTTP 429`, indicando bloqueio/rate limit.
- A captura foi interrompida automaticamente para evitar insistência agressiva.
- Não foram usadas técnicas para burlar bloqueio, captcha, limitação, sessão ou fluxo dinâmico.

## Arquivos gerados

- scripts/dicionario_mestre/capturar_bruto_anvisa_medreg_100.py
- data/dicionario_mestre/bruto/anvisa_medreg_100_captura_bruta.csv
- data/dicionario_mestre/bruto/anvisa_medreg_100_log_captura.csv
- data/dicionario_mestre/processado/checklist_captura_bruta_anvisa_medreg_100.csv
- data/dicionario_mestre/externo/relatorio_captura_bruta_anvisa_medreg_100.md

## Confirmações

- Banco não foi alterado.
- Dicionário final não foi alterado.
- Fonte interna não foi usada.
- SKU_MASTER não foi aplicado.
- Não houve consulta fora da amostra.
- Não houve captura acima de 100 registros.
- Não houve download de base completa.
- HTML bruto não foi salvo nem commitado.
- Screenshots não foram salvas nem commitadas.

## Decisão técnica

NAO_APTO_CAPTURA_AUTOMATICA_SEM_REVISAR_ABORDAGEM

## Próxima fase recomendada

Revisar abordagem técnica antes da FASE 2.15. A FASE 2.15 — processamento dos dados brutos capturados — não deve ser executada ainda, porque não há dados brutos suficientes para processar os campos-alvo.
