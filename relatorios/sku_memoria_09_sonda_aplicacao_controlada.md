# SKU-MEMORIA-09 — Aplicação controlada da família SONDA

## Objetivo
Validar a planilha revisada `sku_memoria_08_sonda_aprovacao_manual.xlsx` (aba `APROVACAO_SONDA`) e aplicar no banco, com backup prévio e transação controlada, apenas as linhas seguras — **bloqueando qualquer inconsistência crítica mesmo quando marcada `APROVAR`**, dado o alto risco desta família.

## Decisões encontradas na planilha

| Decisão | Quantidade |
|---|---:|
| APROVAR | 291 |
| REJEITAR | 0 |
| REVISAR | 0 |
| (vazio) | 0 |
| Inválida | 0 |
| **Total de linhas** | **291** |

Nenhuma decisão inválida foi encontrada — a fase **não foi interrompida** e o backup foi criado normalmente.

## ⚠️ Observação importante sobre a planilha revisada
O usuário editou diretamente a coluna `sku_master_sugerido_preliminar` (258 das 291 linhas foram alteradas em relação ao diagnóstico original), em vez de usar a coluna dedicada `sku_master_corrigido_usuario` (que ficou vazia em todas as linhas). Isso incluiu um trabalho real e cuidadoso de decodificação de várias descrições — por exemplo, textos com OCR corrompido como `SKU PENDENTE - _[C)TO SONDA CARLENS 35 ESQ S/CARIN...` foram manualmente reescritos como `CONJ. SONDA CARLENS 35 ESQ. S/ CARINA PVC UN`.

Como a coluna `sku_master_corrigido_usuario` estava vazia, o sistema usou automaticamente `sku_master_sugerido_preliminar` como valor final para cada linha (regra 4), o que já incorpora as edições do usuário — nenhum ajuste adicional foi necessário para captar o trabalho de revisão feito.

## Validação e bloqueios (mesmo com `APROVAR`)
Apesar de **todas as 291 linhas** estarem marcadas `APROVAR`, a validação obrigatória (regra 7) bloqueou 179 delas por inconsistência crítica, independentemente da marcação:

| Status de validação | Quantidade | Motivo |
|---|---:|---|
| **APTO_PARA_APLICAR** | **112** | SKU final consistente com os atributos críticos da descrição original |
| BLOQUEADO_TEXTO_CORROMPIDO | 57 | Descrição de origem com OCR corrompido — bloqueado por regra explícita desta fase, mesmo com reconstrução manual cuidadosa do usuário (o risco de erro na decodificação de texto corrompido é alto demais para esta família) |
| BLOQUEADO_SUBFAMILIA_INDEFINIDA | 61 | Produto de família própria (gastrostomia, endotraqueal aramada, Carlens, nasofaríngea, acessórios) fora das 10 subfamílias esperadas — bloqueado por regra explícita |
| BLOQUEADO_PENDENTE_SEM_CORRECAO | 61 | Atributo crítico (geralmente volume do balão em sondas Foley, ou número/calibre) continua ausente no SKU final revisado — a edição do usuário não resolveu a lacuna original |

Nenhum `BLOQUEADO_CONFLITO_TIPO`/`NUMERO`/`VIAS`/`BALAO`/`MATERIAL` restou após a validação — dois falsos positivos identificados e corrigidos durante o desenvolvimento desta fase (ver seção abaixo) eliminaram esses casos.

### Correções feitas na lógica de validação antes de aplicar
Durante a primeira passada de validação, dois problemas de comparação foram identificados e corrigidos **antes** de qualquer escrita no banco:
1. **Falso conflito de número por zero à esquerda**: `"8"` (descrição original) vs. `"08"` (SKU final) eram tratados como divergentes por comparação de texto, quando são o mesmo número. Corrigido comparando como inteiro.
2. **Falso conflito de material**: a palavra `SILICONIZADA` (revestimento de superfície) estava sendo confundida com material base `SILICONE`, quando a descrição dizia explicitamente `CONFECCIONADA EM PVC`. Corrigido priorizando menções explícitas de `PVC`/`LÁTEX` sobre o termo genérico "silicon".

## Backup criado
`backups/medbox_v3_antes_sku_memoria_09_sonda_20260701_184425.db`
- Tamanho: 9.351.168 bytes.
- Verificado com `PRAGMA integrity_check` → `ok`, e contagem de produtos (11.105) confere com o banco antes da escrita.

## Totais

- **Total da planilha**: 291
- **Total apto para aplicar**: 112
- **Total bloqueado**: 179 (57 texto corrompido + 61 subfamília indefinida + 61 pendente sem correção)
- **Total aplicado**: 112
- **Total ignorado** (REJEITAR/REVISAR/vazio): 0
- **Total com erro**: 0

## Produtos aplicados (amostra representativa)

| produto_id | SKU_MASTER aplicado |
|---:|---|
| 5629–5632 | SONDA FOLEY DESC ESTERIL BALAO 30ML 2 VIAS Nº12/14/16/18 |
| 5643, 6277, 6278 | SONDA URETRAL Nº 10/12/14 |
| 5680–5682, 6199 | SONDA DE ASPIRACAO TRAQUEAL C/ VALV / S/ VALV Nº 12/14/16 |
| 6200 | SONDA DE BORRACHA (LATEX NATURAL) TIPO FOLEY C/ 2 VIAS BALAO 5CC Nº 20 |
| 6201, 6237, 6238, 6258 | SONDA GASTRICA/LEVINE NASOGASTRICA LONGA Nº 16/18/20 |
| 6202 | SONDA P/ ASPIRACAO TRAQUEAL ... PVC Nº 14 (material corrigido de SILICONE para PVC, ver seção de correções) |
| 6203 | SONDA P/ NUTRICAO ENTERAL SILICONADA MALEAVEL RADIOPACA MANDRIL Nº 12 |
| 6292–6294 | SONDA FOLEY VESICAL BALAO 30ML/5ML 2/3 VIAS Nº 20/22 |

Lista completa (112 produtos) em `relatorios/sku_memoria_09_sonda_pos_aplicacao.csv`.

## Produtos bloqueados (amostra por categoria)

| produto_id | Descrição | Motivo do bloqueio |
|---:|---|---|
| 4740–4746 | SONDA CARLENS (texto OCR corrompido) | BLOQUEADO_TEXTO_CORROMPIDO |
| 5105–5107 | SONDA ALIMENT ENTERAL (texto OCR corrompido) | BLOQUEADO_TEXTO_CORROMPIDO |
| 6247, 6248, 8078–8454 | SONDA DE GASTROSTOMIA (inclusive linha "MICKEY") | BLOQUEADO_SUBFAMILIA_INDEFINIDA |
| 7409–7532 | SONDA END. ARAMADA (endotraqueal) | BLOQUEADO_SUBFAMILIA_INDEFINIDA |
| 6204, 6317, 6913, 6950–6956 | SONDA FOLEY sem volume de balão explícito | BLOQUEADO_PENDENTE_SEM_CORRECAO |
| 6580, 6637, 6645 | SONDA NASOGASTRICA/URETRAL/RETAL sem número confiável | BLOQUEADO_PENDENTE_SEM_CORRECAO |

Lista completa dos 179 produtos bloqueados, com motivo individual, em `relatorios/sku_memoria_09_sonda_validacao_pre_aplicacao.csv` e `relatorios/sku_memoria_09_sonda_pos_aplicacao.csv`.

## Confirmações
- **`produto_padrao` não foi alterado** em nenhum dos 291 produtos — verificado durante a própria transação (comparação antes/depois de cada escrita); a transação seria revertida automaticamente se qualquer divergência fosse detectada.
- **Cascata não foi usada** — cada produto foi atualizado individualmente.
- **Marca não foi alterada** em nenhum produto nesta fase (regra explícita: não mexer em marca).
- **Categoria**: nenhuma alteração foi necessária — todos os 112 produtos aplicados já tinham categoria preenchida (`INSUMOS HOSPITALARES`); a regra de preencher `CORRELATOS` quando vazia não teve produtos aplicáveis nesta rodada.
- **Dicionário Mestre MEDREG não foi alterado.**
- **Bionexo não foi tocado.**
- `app.py`, `templates/` e `core/` não foram alterados.
- **Banco e backup não foram (nem serão) commitados** — ambos permanecem fora do controle de versão (`.gitignore`/`.git/info/exclude`).
- 112 registros criados em `auditoria_sku` com `origem_correcao = 'SKU-MEMORIA-09-SONDA'`.
- `python -m py_compile app.py` executado com sucesso.

## Recomendação final
Os 112 produtos seguros foram padronizados com sucesso. Os 179 produtos bloqueados permanecem exatamente como estavam — recomenda-se tratá-los em fases dedicadas e menores:
1. Os **57 com texto corrompido** provavelmente exigem consulta à nota fiscal original ou embalagem física (a reconstrução manual, embora cuidadosa, não é suficiente para esta família de alto risco).
2. Os **61 sem subfamília clara** (principalmente gastrostomia e endotraqueal aramada) merecem um diagnóstico próprio, fora do escopo de `SONDA` genérica.
3. Os **61 pendentes sem correção** precisam da informação crítica faltante (geralmente o volume do balão em Foleys) confirmada por outra fonte antes de qualquer nova tentativa.
