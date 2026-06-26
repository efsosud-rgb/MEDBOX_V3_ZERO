# FASE 2.14E — Instalação controlada do toolkit Python de ingestão multi-fonte

## Objetivo

Instalar bibliotecas Python para futura ingestão multi-fonte do Dicionário Mestre MEDBOX.

## Ambiente

- Branch: melhoria/auditoria-sku-master-todos-produtos
- Python base: Python 3.14.5
- Pip base: pip 26.1.1
- Ambiente virtual usado: .venv
- Ambiente virtual: criado nesta fase
- Python do .venv: Python 3.14.5
- Pip do .venv: pip 26.1.2

## Bibliotecas instaladas

- requests
- httpx
- tenacity
- tqdm
- python-dotenv
- pandas
- openpyxl
- pyxlsb
- fastexcel
- polars
- duckdb
- pyarrow
- beautifulsoup4
- lxml
- selectolax
- playwright
- pymupdf
- pdfplumber
- pypdf
- camelot-py
- tabula-py
- rapidfuzz
- Unidecode
- python-slugify
- regex
- jsonlines
- sqlite-utils

## Diagnóstico de importação

Resumo do diagnóstico offline:

- Bibliotecas com importação OK: 26
- Bibliotecas com erro/pendência: 1

Importações OK:

- requests
- httpx
- tenacity
- tqdm
- dotenv
- pandas
- openpyxl
- pyxlsb
- fastexcel
- polars
- duckdb
- pyarrow
- bs4
- lxml
- selectolax
- playwright
- fitz
- pdfplumber
- pypdf
- tabula
- rapidfuzz
- unidecode
- slugify
- regex
- jsonlines
- sqlite_utils

Erro/pendência registrada:

- camelot: OSError [WinError 4551] Uma política de Controle de Aplicativo bloqueou este arquivo.

O arquivo detalhado do diagnóstico foi salvo em `data/dicionario_mestre/processado/diagnostico_toolkit_ingestao_multi_fonte.csv`.

## Observações

- Playwright foi instalado como biblioteca Python, mas os navegadores Playwright não foram instalados.
- tabula-py pode exigir Java para uso real.
- camelot-py pode exigir dependências externas para determinados PDFs e, neste ambiente, teve importação bloqueada por política do Windows.
- Nenhuma base foi baixada.
- Nenhuma captura foi executada.
- Scraping não foi executado.
- Banco não foi alterado.
- Dicionário final não foi alterado.
- Fonte interna não foi usada.
- SKU_MASTER não foi aplicado.
- Java não foi instalado.
- Ghostscript não foi instalado.

## Próxima fase recomendada

FASE 2.14F — criação dos scripts de download estruturado, ainda sem aplicação no dicionário final.

## Decisão técnica

APTO_PARA_PREPARAR_SCRIPTS_DOWNLOAD_ESTRUTURADO
