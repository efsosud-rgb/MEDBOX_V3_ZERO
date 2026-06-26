# Plano de Fontes — Forma Farmacêutica, Concentração, Apresentação e Via de Uso

**Data:** 2026-06-26
**Fase:** 2.12 — Planejamento da fonte oficial
**Branch:** melhoria/auditoria-sku-master-todos-produtos
**Commit base:** `fa01971` (chore: revisa pos-enriquecimento dcb anvisa medreg)
**Decisão técnica:** `APTO_PARA_DIAGNOSTICAR_FONTE_OFICIAL_FORMA_CONCENTRACAO_APRESENTACAO_VIA`

---

## 1. Objetivo

Planejar, sem capturar dados e sem alterar o dicionário, a próxima fonte oficial para
preencher os campos `forma_farmaceutica`, `concentracao`, `apresentacao` e `via_uso`
nos 10.345 registros `ANVISA_MEDICAMENTOS_REGISTRADOS` do dicionário mestre.

---

## 2. Situação atual do dicionário

| Indicador | Valor |
|---|---|
| Total registros DCB | 12.715 |
| Total registros ANVISA_MEDREG | 10.345 |
| MEDREG com `dcb` + `cas` preenchidos | 7.984 (77,2%) — aplicado na FASE 2.10 |
| MEDREG sem `dcb`/`cas` | 2.361 (22,8%) |
| MEDREG sem `forma_farmaceutica` | **10.345 (100%)** |
| MEDREG sem `concentracao` | **10.345 (100%)** |
| MEDREG sem `apresentacao` | **10.345 (100%)** |
| MEDREG sem `via_uso` | **10.345 (100%)** |

Os quatro campos estão **completamente ausentes** em todos os registros MEDREG.

---

## 3. Por que a base DADOS_ABERTOS_MEDICAMENTOS.csv não trouxe esses campos

A base `DADOS_ABERTOS_MEDICAMENTOS.csv` (ANVISA Medicamentos Registrados — dados abertos)
contém apenas 11 colunas:

| Coluna original | Campo mapeado |
|---|---|
| TIPO_PRODUTO | — (informativo) |
| NOME_PRODUTO | `nome_padrao` |
| DATA_FINALIZACAO_PROCESSO | — |
| CATEGORIA_REGULATORIA | `classificacao` |
| NUMERO_REGISTRO_PRODUTO | usado no `id_dicionario` |
| DATA_VENCIMENTO_REGISTRO | — |
| NUMERO_PROCESSO | usado no `id_dicionario` (baixo risco) |
| CLASSE_TERAPEUTICA | — |
| EMPRESA_DETENTORA_REGISTRO | `observacao` parcial |
| SITUACAO_REGISTRO | usado como filtro de elegibilidade |
| PRINCIPIO_ATIVO | `principio_ativo` |

**Conclusão:** os campos `forma_farmaceutica`, `concentracao`, `apresentacao` e `via_uso`
**não existem** na base de dados abertos da ANVISA. Esses campos fazem parte do detalhamento
do produto por apresentação, disponível em outros sistemas ANVISA — não no CSV de dados abertos.

---

## 4. Fontes candidatas

### 4.1 Bulário Eletrônico ANVISA (ANVISA_BULARIO)

| Atributo | Detalhe |
|---|---|
| Status no catálogo | `planejada` |
| URL base | https://www.gov.br/anvisa/pt-br/sistemas/bulario-eletronico |
| URL operacional | https://consultas.anvisa.gov.br/#/bulario/ |
| Formato | HTML / PDF |
| Dados disponíveis | nome comercial, forma farmacêutica, concentração, via de uso, composição, posologia, empresa |
| Prioridade no catálogo | 3 |

**Vantagens:**
- Contém forma farmacêutica, concentração e via de uso por produto registrado.
- Fonte oficial ANVISA, alta confiabilidade.
- Permite busca por número de registro, nome comercial ou princípio ativo.

**Limitações:**
- Acesso via portal web (HTML), sem download em massa de CSV/XLSX.
- Captura requer automação controlada por número de registro.
- Volume: 10.345 registros MEDREG → 10.345 consultas individuais potenciais.
- Pode haver múltiplas bulas por registro (bula do paciente e bula do profissional).

### 4.2 ANVISA Consultas — Registro de Medicamentos

| Atributo | Detalhe |
|---|---|
| URL operacional | https://consultas.anvisa.gov.br/#/medicamentos/ |
| Dados disponíveis | número de registro, produto, empresa, apresentação, forma farmacêutica, via de administração |
| Formato | HTML (página por produto) |

**Vantagens:**
- Dados estruturados por número de registro.
- Contém apresentação (embalagem, unidade, quantidade) de forma explícita.
- Permite busca direta pelo `NUMERO_REGISTRO_PRODUTO` já presente nos IDs MEDREG.

**Limitações:**
- Sem download em massa.
- Requer acesso página a página por número de registro.
- JavaScript necessário — captura automatizada requer planejamento cuidadoso.

### 4.3 Dados abertos ANVISA — possíveis complementos futuros

O Plano de Dados Abertos ANVISA 2023-2025 prevê publicação de bases adicionais.
No momento, o dataset `DADOS_ABERTOS_MEDICAMENTOS.csv` é o único disponível com
todos os medicamentos registrados. Verificar em fase futura se novos datasets com
campo de apresentação/forma farmacêutica foram disponibilizados.

---

## 5. Comparação entre as fontes candidatas

| Critério | ANVISA_BULARIO | ANVISA_CONSULTAS |
|---|---|---|
| Forma farmacêutica | Sim | Sim |
| Concentração | Sim | Sim (embutida no nome do produto) |
| Apresentação | Sim (na bula) | Sim (estruturada) |
| Via de uso | Sim (na bula) | Sim |
| Formato | HTML/PDF | HTML |
| Download em massa | Não | Não |
| Busca por nº de registro | Sim | Sim |
| Volume de consultas | 10.345 | 10.345 |
| Rastreabilidade URL | Alta | Alta |
| Confiabilidade | Alta (oficial ANVISA) | Alta (oficial ANVISA) |
| Complexidade de captura | Alta (PDF/HTML) | Média (HTML estruturado) |

**Fonte recomendada para a FASE 2.13:**
`ANVISA_CONSULTAS` — busca por número de registro, campos mais estruturados,
apresentação explícita, menor dependência de parsing de PDF.

**Fonte complementar:**
`ANVISA_BULARIO` — para campos ausentes na consulta de registro (via de uso detalhada,
posologia) e para validação cruzada.

---

## 6. Estratégia de captura futura

A captura deve seguir rigorosamente o pipeline de fases, com dry-run obrigatório
antes de qualquer escrita no dicionário:

### Fase 2.13 — Diagnóstico oficial da fonte
- Confirmar campos disponíveis em ANVISA_CONSULTAS por número de registro.
- Verificar estrutura HTML da página de resultado.
- Documentar campos mapeáveis (sem download de dados).
- Registrar URL oficial, data de verificação e estrutura esperada.

### Fase 2.14 — Captura bruta controlada
- Capturar dados brutos de ANVISA_CONSULTAS para amostra controlada.
- Escopo inicial: máximo 100 registros para validação.
- Salvar bruto sem edição em `data/dicionario_mestre/bruto/anvisa/`.
- Registrar URL, data/hora, tamanho, formato.
- Somente após aprovação humana explícita para ampliar escopo.

### Fase 2.15 — Processamento intermediário
- Normalizar campos capturados para o formato do dicionário.
- Gerar intermediário auditável.
- Não alterar dicionário final.

### Fase 2.16 — Auditoria do intermediário
- Verificar qualidade, duplicatas, inconsistências.
- Confirmar que campos mapeados batem com o esperado.

### Fase 2.17 — Dry-run de enriquecimento
- Simular aplicação dos campos forma/concentração/apresentação/via nos MEDREG.
- Gerar diff e checklist.
- Não alterar dicionário final.

### Fase 2.18 — Aplicação controlada
- Aplicar somente após aprovação humana explícita.
- Criar backup obrigatório antes da escrita.
- Nunca sobrescrever campo já preenchido.
- Registrar rastreabilidade: URL fonte + data captura no campo `observacao`.

---

## 7. Critérios de segurança obrigatórios

- Não usar fonte interna ou SKU_MASTER como base de enriquecimento.
- Não preencher campos por inferência ou aproximação.
- Manter rastreabilidade oficial: URL fonte + data captura + número de registro.
- Registrar URL e data da fonte em `url_fonte` e `data_coleta`.
- Separar registros sem match na fonte candidata.
- Nenhuma captura automática em massa sem aprovação explícita e fase de diagnóstico prévia.
- Escopo incremental: amostra → validação → escala.

---

## 8. Riscos

| Risco | Impacto | Mitigação |
|---|---|---|
| Página web exige JavaScript | Captura simples falha | Usar automação headless controlada com registro de sessão |
| Volume alto (10.345 registros) | Captura demorada / bloqueio por rate limit | Captura incremental com pausa entre requisições |
| Campos com grafia variante | Normalização necessária | Usar mesmo pipeline de normalização das fases anteriores |
| Apresentação com múltiplos tamanhos | Uma linha por apresentação | Definir estratégia de agregação antes de enriquecer |
| Produto sem bula no Bulário | Campos ausentes | Marcar como PENDENTE_BULA; não deixar campo em branco sem registro |

---

## 9. Confirmações desta fase

- `dicionario_mestre_medicamentos.csv` **NÃO foi alterado** (read-only, 8.917.376 bytes).
- Banco de dados **NÃO foi acessado**.
- Fonte interna **NÃO foi usada**.
- SKU_MASTER **NÃO foi aplicado**.
- Nenhum dado foi baixado da internet.
- Nenhum scraping foi executado.

---

*Gerado na FASE 2.12 — Planejamento fonte forma/concentração/apresentação/via*
*Branch: melhoria/auditoria-sku-master-todos-produtos*
