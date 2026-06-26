# FASE 2.14F — Scripts de download estruturado multi-fonte MEDREG

## Objetivo

Criar scripts seguros para preparar downloads estruturados de fontes públicas oficiais, sem executar download real nesta fase.

## Scripts criados

- scripts/dicionario_mestre/baixar_fontes_estruturadas_medreg.py
- scripts/dicionario_mestre/validar_fontes_estruturadas_medreg.py

## Modo seguro

- `DRY_RUN=True` por padrão.
- Nenhuma base grande foi baixada.
- Nenhum scraping foi executado.
- Nenhum dicionário final foi alterado.
- Banco permaneceu intacto.
- Fonte interna não foi usada.
- SKU_MASTER não foi aplicado.
- ANVISA Consultas por registro não foi usada.
- O script de download apenas gerou plano e log de execução segura.
- O script de validação apenas verificou a existência futura dos caminhos planejados.

## Fontes planejadas

- Medicamentos registrados no Brasil / dados.gov.br.
- Dados Abertos ANVISA.
- CMED listas de preços.
- DCB ANVISA.
- Farmacopeia/vocabulários.
- Bulário Eletrônico.
- ANVISA Consultas como fallback futuro.

## Arquivos gerados pelos scripts

- data/dicionario_mestre/processado/plano_download_fontes_estruturadas_medreg.csv
- data/dicionario_mestre/processado/log_download_fontes_estruturadas_medreg.csv
- data/dicionario_mestre/processado/validacao_fontes_estruturadas_medreg.csv

## Resultado da execução segura

- Fontes planejadas: 7.
- Downloads reais executados: 0.
- Validações geradas: 7.
- Fontes pendentes por arquivo não baixado: 7.
- Erros de validação: 0.

## Próxima fase recomendada

FASE 2.14G — execução controlada do download de fontes estruturadas autorizadas, uma fonte por vez, começando pela fonte mais segura e estruturada.

## Decisão técnica

APTO_PARA_EXECUTAR_DOWNLOAD_CONTROLADO_FONTE_A_FONTE
