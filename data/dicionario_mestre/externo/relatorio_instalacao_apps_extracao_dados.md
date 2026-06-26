# FASE 2.14E-C — Instalação de ferramentas externas de apoio à extração de dados

## Objetivo

Instalar e diagnosticar ferramentas que facilitem a extração, limpeza, análise e cruzamento de dados públicos para o Dicionário Mestre MEDBOX.

## Ferramentas solicitadas/priorizadas

- OpenRefine
- Tabula Desktop
- DBeaver Community
- Excalibur
- Camelot
- Playwright Chromium
- Java
- ferramentas Python já instaladas

## Resultado por ferramenta

- Winget: OK, v1.28.240.
- Java: OK, OpenJDK Temurin 21.0.11 localizado fora do PATH em `C:\Program Files\Eclipse Adoptium\jdk-21.0.11.10-hotspot\bin\java.exe`.
- OpenRefine: OK, instalado via winget; localizado fora do PATH em `C:\Users\admph\AppData\Local\Programs\OpenRefine\openrefine.exe`.
- Tabula Desktop: OK, instalado via winget; localizado fora do PATH em `C:\Users\admph\AppData\Local\Microsoft\WinGet\Packages\tabulapdf.tabula_Microsoft.Winget.Source_8wekyb3d8bbwe\tabula\tabula.exe`.
- DBeaver Community: OK, instalado via winget; localizado fora do PATH em `C:\Users\admph\AppData\Local\DBeaver\dbeaver.exe`.
- Excalibur: OK, instalado via pip no `.venv`; importação local OK, versão 1.0.1.
- Camelot: OK, importação local OK, versão 2.0.0.
- Playwright: OK, importação local OK, versão 1.60.0.
- pdfplumber: OK, versão 0.11.10.
- PyMuPDF: OK, versão 1.27.2.3.
- tabula-py: OK, versão 2.10.0.
- DuckDB: OK, versão 1.5.4.

Não houve pendências no diagnóstico consolidado. Alguns aplicativos foram localizados fora do PATH; o PATH permanente não foi alterado.

## Uso previsto no projeto

- OpenRefine: limpeza e reconciliação de nomes de produto, empresa, princípio ativo, DCB e CAS.
- Tabula Desktop: extração visual de tabelas em PDF.
- DBeaver: análise visual de bases, DuckDB, CSV e validações SQL.
- Excalibur/Camelot: extração de tabelas PDF quando viável.
- Playwright Chromium: navegação controlada em páginas públicas para identificar links e elementos.
- pdfplumber/PyMuPDF/tabula-py: fallback para PDFs e bulas.

## Confirmações de segurança

- Nenhuma base foi baixada.
- Nenhuma captura foi executada.
- Scraping não foi executado.
- Banco não foi alterado.
- Dicionário final não foi alterado.
- Fonte interna não foi usada.
- SKU_MASTER não foi aplicado.
- Segurança do Windows não foi desativada.
- Instaladores/caches não foram commitados.
- Arquivos Bionexo/logs não foram commitados.

## Arquivos criados/alterados

- scripts/dicionario_mestre/diagnosticar_apps_extracao_dados.py
- data/dicionario_mestre/processado/diagnostico_apps_extracao_dados.csv
- data/dicionario_mestre/processado/checklist_instalacao_apps_extracao_dados.csv
- data/dicionario_mestre/externo/relatorio_instalacao_apps_extracao_dados.md
- scripts/dicionario_mestre/requirements_ingestao_multi_fonte.txt
- CHECKPOINT.md

## Decisão técnica

APTO_PARA_DOWNLOAD_CONTROLADO_COM_TOOLKIT_EXPANDIDO

## Próxima fase recomendada

FASE 2.14G-1B — download controlado direto ANVISA DADOS_ABERTOS_MEDICAMENTOS.csv.
