# FASE 2.14E-B — Instalação de dependências PDF/Navegação

## Objetivo

Instalar e diagnosticar Java, Ghostscript, Playwright Chromium e Camelot funcional, sem desativar segurança do Windows e sem executar captura ou scraping.

## Ambiente

- Branch: melhoria/auditoria-sku-master-todos-produtos
- Python base: Python 3.14.5
- Python .venv: Python 3.14.5
- Pip .venv: pip 26.1.2
- Winget: v1.28.240

## Resultado Java

- Status: OK.
- Instalação: Eclipse Temurin JDK 21 via winget.
- Versão diagnosticada: OpenJDK 21.0.11 LTS.
- Observação: `java` não ficou disponível no PATH da sessão atual; foi verificado pelo caminho instalado `C:\Program Files\Eclipse Adoptium\jdk-21.0.11.10-hotspot\bin\java.exe`.
- PATH permanente não foi alterado.

## Resultado Ghostscript

- Status: PENDENTE.
- Tentativa: `winget install --id ArtifexSoftware.GhostScript -e --accept-package-agreements --accept-source-agreements`.
- Resultado: o catálogo winget local não encontrou pacote correspondente.
- Verificação: `gswin64c` não foi encontrado no PATH nem em `C:\Program Files\gs` ou `C:\Program Files (x86)\gs`.
- PATH permanente não foi alterado.

## Resultado Playwright Chromium

- Status: OK.
- Comando executado: `.venv\Scripts\python.exe -m playwright install chromium`.
- Teste de importação: OK.
- Chromium localizado em cache local: `C:\Users\admph\AppData\Local\ms-playwright\chromium-1223`.

## Resultado Camelot

- Status: OK.
- Bibliotecas Python relacionadas retestadas/atualizadas: camelot-py, opencv-python-headless, pypdf e pdfminer.six.
- Teste: `import camelot` OK.
- Versão: 2.0.0.
- Não houve desativação de SmartScreen, Defender, App Control ou qualquer política de segurança do Windows.

## Pendências

- Ghostscript permanece pendente porque o pacote Artifex não foi encontrado no catálogo winget local e `gswin64c` não foi localizado na máquina.
- Fallbacks disponíveis para a próxima fase: pdfplumber, PyMuPDF, pypdf, tabula-py e Camelot quando não depender de Ghostscript no caso específico.

## Confirmações

- Nenhuma base foi baixada.
- Nenhuma captura foi executada.
- Scraping não foi executado.
- Banco não foi alterado.
- Dicionário final não foi alterado.
- Fonte interna não foi usada.
- SKU_MASTER não foi aplicado.
- Segurança do Windows não foi desativada.
- Instaladores, downloads, caches, `.venv`, logs e Bionexo não foram preparados para commit.

## Arquivos criados

- scripts/dicionario_mestre/diagnosticar_dependencias_pdf_navegacao.py
- data/dicionario_mestre/processado/diagnostico_dependencias_pdf_navegacao.csv
- data/dicionario_mestre/processado/checklist_instalacao_dependencias_pdf_navegacao.csv
- data/dicionario_mestre/externo/relatorio_instalacao_dependencias_pdf_navegacao.md

## Decisão técnica

APTO_COM_PENDENCIAS_PDF_NAV

## Próxima fase recomendada

FASE 2.14F — criação dos scripts de download estruturado.
