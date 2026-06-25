# Relatório de Captura — ANVISA DCB
**Data:** 2026-06-25
**Fase:** FASE 1 — ANVISA DCB

---

## Objetivo

Capturar de forma rastreável o arquivo bruto oficial vigente da Lista Consolidada das Denominações Comuns Brasileiras (DCB) publicada pela ANVISA, sem processar e sem mesclar no Dicionário Mestre MEDBOX.

---

## URLs Consultadas

| URL | Resultado |
|-----|-----------|
| https://www.gov.br/anvisa/pt-br/assuntos/farmacopeia/dcb | Acessada — confirma Lista Consolidada DCB na Biblioteca Digital |
| https://bibliotecadigital.anvisa.gov.br/jspui/handle/anvisa/20673 | Acessada via curl (bloqueada para WebFetch sem User-Agent de browser) — confirma IN 439/2026 VIGENTE |
| https://anfarmag.org.br/conteudos/atualizacao-da-lista-de-dcb-8/ | Consultada — confirma IN 439, DOU nº 74, 22/04/2026, 15 inclusões + 1 alteração |
| https://bibliotecadigital.anvisa.gov.br/jspui/bitstream/anvisa/20673/3/1-%20Lista%20DCB%20consolidada%20abr%202026.xlsx | Download realizado — HTTP 200, 588.227 bytes |

---

## Arquivo Bruto Salvo

- **Nome:** `anvisa_dcb_lista_consolidada_in_439_2026_original.xlsx`
- **Caminho:** `data/dicionario_mestre/bruto/anvisa/`
- **Formato:** Microsoft Excel XML (.xlsx)
- **Tamanho:** 588.227 bytes (574,4 kB)
- **Nome original no servidor:** `1- Lista DCB consolidada abr 2026.xlsx`
- **Fonte bitstream:** `https://bibliotecadigital.anvisa.gov.br/jspui/bitstream/anvisa/20673/3/1-%20Lista%20DCB%20consolidada%20abr%202026.xlsx`

---

## Metadados Registrados

- **Arquivo de metadados:** `data/dicionario_mestre/bruto/anvisa/anvisa_dcb_lista_consolidada_in_439_2026_metadados.txt`
- Contém: fonte, órgão, URLs oficiais, título, versão, data da IN, publicação DOU, status, alterações da versão, data/hora da captura, nome e tamanho do arquivo, URL bitstream de origem, e observação de preservação.

---

## Identificação da Versão Vigente

- **Título:** Lista consolidada das DCB: versão IN nº 439, de 16 de abril de 2026 - VIGENTE
- **IN nº:** 439/2026
- **Data da IN:** 16 de abril de 2026
- **Publicação no DOU:** nº 74, de 22 de abril de 2026 — Seção 1 — p.241
- **Alterações:** 15 novas DCBs incluídas; 1 alteração (CAS da glicose monoidratada: 14431-43-7 → 77938-63-7)
- **Status:** VIGENTE

---

## Confirmações de Integridade

- Nenhuma base de dados interna foi consultada ou usada.
- Nenhum banco de dados foi alterado.
- Nenhum arquivo .db foi tocado.
- Nenhum SKU_MASTER foi aplicado ou consultado.
- Nenhum processamento do arquivo bruto foi realizado.
- Nenhuma mesclagem no Dicionário Mestre foi executada.
- O arquivo bruto foi preservado sem edição manual do conteúdo.
- `app.py`, `core/`, `templates/`, `uploads/`, `backups/`, `.claude/` não foram alterados.

---

## Próxima Etapa Recomendada

Validar a estrutura interna do arquivo bruto (`anvisa_dcb_lista_consolidada_in_439_2026_original.xlsx`):
- verificar abas/sheets presentes
- identificar colunas disponíveis (DCB, CAS, categoria, etc.)
- criar script de processamento separado que gere um CSV normalizado da DCB

**Restrição:** o CSV normalizado deve ser gerado sem mesclar no Dicionário Mestre final — apenas como etapa intermediária de processamento.

---

## Controle de Catálogo e Histórico

- O catálogo externo (`catalogo_fontes_externas.csv`) mantém exatamente **uma linha por fonte**; a linha ANVISA_DCB registra o estado atual da fonte com `status = capturada_bruto`.
- A captura da DCB foi registrada no histórico de capturas (`historico_capturas_fontes.csv`) com `id_captura = ANVISA_DCB_20260625_IN_439_2026`, separando o rastreamento de cada evento de captura do estado estático do catálogo.
- O arquivo bruto (`anvisa_dcb_lista_consolidada_in_439_2026_original.xlsx`) ainda não foi processado — `processado = nao`.
- Nada foi mesclado ao Dicionário Mestre — `mesclado_dicionario = nao`.
