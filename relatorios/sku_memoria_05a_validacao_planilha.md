# SKU-MEMORIA-05A — Validação da planilha revisada e preparação da aplicação

## Objetivo
Ler a planilha `relatorios/sku_memoria_04_aprovacao_manual.xlsx` já revisada pelo usuário, validar a coluna `decisao_usuario`, contar as decisões e preparar uma prévia segura de aplicação — **sem aplicar nada no banco nesta fase**.

## Planilha lida
`relatorios/sku_memoria_04_aprovacao_manual.xlsx`, aba `APROVACAO_SKU`.

## Total de linhas e decisões

| Decisão | Quantidade |
|---|---:|
| APROVAR | 15 |
| REJEITAR | 0 |
| REVISAR | 0 |
| (vazio) | 0 |
| Decisão inválida | 0 |
| **Total de linhas** | **15** |

O usuário aprovou **todas as 15 linhas** da planilha (5 `MATCH_MEMORIA_VALIDADA` + 10 `MATCH_ASSINATURA_TECNICA`). Nenhum valor fora da lista permitida (`APROVAR`/`REJEITAR`/`REVISAR`/vazio) foi encontrado.

## Validação contra o banco (somente leitura)
Todos os 15 `produto_id` foram localizados em `banco/medbox_v3.db` (`mode=ro`), todos ativos (`ativo=1`), todos com `sku_master_sugerido` preenchido na planilha. Nenhum bloqueio por produto inexistente, SKU_MASTER vazio ou decisão inválida.

**Total apto para aplicar: 15**
**Total bloqueado: 0**

## Produtos aprovados (o que mudaria)

| produto_id | SKU_MASTER atual | SKU_MASTER sugerido | Marca | Categoria |
|---:|---|---|---|---|
| 267 | ENOXAPARINA SODICA 40MG | ENOXAPARINA SODICA 40MG/0,4ML | mantém VIATRIS (já preenchida) | já MEDICAMENTOS |
| 2016 | ENOXAPARINA SODICA 40MG | ENOXAPARINA SODICA 40MG/0,4ML | mantém VIATRIS (já preenchida) | já MEDICAMENTOS |
| 3906 | (bruto, não padronizado) | ENOXAPARINA SODICA 40MG/0,4ML | preencheria HEPTRIS (vazia) | **não altera** (atual = "MARCAS UQ", não padrão, preenchida) |
| 4284 | ENOXAPARINA SODICA 40MG | ENOXAPARINA SODICA 40MG/0,4ML | preencheria HEPTRIS (vazia) | já MEDICAMENTOS |
| 268 | ENOXAPARINA SODICA 60MG | ENOXAPARINA SODICA 60MG/0,6ML | mantém VIATRIS (já preenchida) | **não altera** (atual = "MEDICAMENTO", singular, preenchida) |
| 3907 | (bruto, não padronizado) | ENOXAPARINA SODICA 60MG/0,6ML | preencheria HEPTRIS (vazia) | **não altera** (atual = "MARCAS UQ", preenchida) |
| 4283 | ENOXAPARINA SODICA 60MG | ENOXAPARINA SODICA 60MG/0,6ML | preencheria HEPTRIS (vazia) | preencheria MEDICAMENTOS (vazia) |
| 269 | ENOXAPARINA SODICA 80MG | ENOXAPARINA SODICA 80MG/0,8ML | mantém VIATRIS (já preenchida) | **não altera** (atual = "MEDICAMENTO", singular, preenchida) |
| 3908 | (bruto, não padronizado) | ENOXAPARINA SODICA 80MG/0,8ML | preencheria HEPTRIS (vazia) | **não altera** (atual = "MARCAS UQ", preenchida) |
| 4285 | ENOXAPARINA SODICA 80MG | ENOXAPARINA SODICA 80MG/0,8ML | preencheria HEPTRIS (vazia) | já MEDICAMENTOS (nota: produto já tem `sku_corrigido=1`) |
| 1946 | (bruto, não padronizado) | ENOXAPARINA SODICA 40MG/0,4ML | mantém EUROFARMA LABORATORIOS S. (já preenchida) | **não altera** (atual = "MEDICAMENTO", singular, preenchida) |
| 8592 | (vazio) | SORO FISIOLOGICO NASAL SPRAY 0,9% 100ML | preencheria NASOJET (vazia) | já MEDICAMENTOS |
| 8549 | (vazio) | SORO FISIOLOGICO NASAL SPRAY 0,9% 100ML | sem sugestão (mantém vazia) | já MEDICAMENTOS |
| 9031 | (vazio) | SORO FISIOLOGICO NASAL SPRAY 0,9% 100ML | sem sugestão (mantém vazia) | já MEDICAMENTOS |
| 9275 | (vazio) | SORO FISIOLOGICO NASAL SPRAY 0,9% 100ML | sem sugestão (mantém vazia) | já MEDICAMENTOS |

## Campos que seriam alterados (resumo)
- **`sku_master`**: seria alterado nas 15 linhas (é o campo principal desta aplicação).
- **`marca`** (via `precos_fornecedores.marca`, já que a tabela `produtos` não tem coluna própria de marca): seria preenchida apenas onde está vazia hoje — `3906, 4284, 3907, 4283, 3908, 4285, 8592` (7 produtos). Nos demais (`267, 2016, 268, 269, 1946`), o campo já está preenchido (`VIATRIS` ou `EUROFARMA LABORATORIOS S.`) e **não será sobrescrito** sem autorização explícita, mesmo que a sugestão da memória (`HEPTRIS`/`VERSA`) seja tecnicamente o nome comercial mais correto — vale registrar essa divergência para decisão futura, mas por regra desta fase não se altera automaticamente.
- **`categoria`**: seria preenchida apenas onde está vazia hoje — `4283` (1 produto). Em `3906, 3907, 3908` a categoria atual é `"MARCAS UQ"` (valor não padronizado, porém preenchido) e em `268, 269, 1946` é `"MEDICAMENTO"` (singular, não padronizado, também preenchido) — em ambos os casos, por já estarem preenchidos, **não serão alterados** nesta fase, embora sejam candidatos claros a uma limpeza de dados futura (fora do escopo desta fase).

## Observações especiais
- **`id 4285`** já está com `sku_corrigido = 1` (produto previamente marcado como corrigido). A alteração prevista é apenas de padronização (adicionar o sufixo de volume `/0,8ML`), sem conflito com a correção anterior — segue apto, mas fica registrado para rastreabilidade.
- **Valores não padronizados de categoria** (`"MARCAS UQ"`, `"MEDICAMENTO"` singular) apontam para uma inconsistência de dados pré-existente no banco, não criada por esta fase. Recomenda-se tratar isso em uma limpeza dedicada, não misturada com a aplicação da memória SKU_MASTER.
- Nenhum conflito crítico de concentração, dose, volume, via ou forma foi encontrado entre a descrição atual do produto e o SKU_MASTER sugerido em nenhuma das 15 linhas.

## Confirmações de segurança
- Banco (`banco/medbox_v3.db`) acessado somente em modo leitura (`mode=ro`); **nenhum `UPDATE`/`DELETE`/`INSERT` foi executado.**
- Nenhum SKU_MASTER foi aplicado.
- Nenhuma cascata automática foi executada.
- `app.py`, `templates/` e `core/` não foram alterados.
- Nenhuma pesquisa à internet foi feita nesta fase.

## Recomendação final
**APTO_PARA_APLICACAO_CONTROLADA**

As 15 linhas aprovadas passaram na validação (produto existente, SKU_MASTER sugerido presente, decisão válida, sem conflito crítico) e estão prontas para uma fase de aplicação real controlada — que deve incluir backup do banco antes de qualquer escrita, aplicar uma linha por vez (ou em lote pequeno) via `core/auditoria_sku_master.py`, e respeitar a regra de não sobrescrever `marca`/`categoria` já preenchidas sem autorização explícita adicional do usuário.
