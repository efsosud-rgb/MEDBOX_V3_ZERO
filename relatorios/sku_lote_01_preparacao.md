# SKU-LOTE-01 — Preparação segura do primeiro lote

## Objetivo
Preparar o primeiro lote de correção SKU_MASTER (consolidação de duplicatas 100% iguais) sem alterar o banco, sem aplicar cascata automática e sem aplicar qualquer correção — apenas organizar dados reais para revisão manual.

## Base analisada
- Banco: `banco/medbox_v3.db` (caminho oficial em `core/banco.py`), acessado somente leitura.
- Fonte de classificação: reuso da função de leitura já existente `gerar_auditoria_sku_master` (`core/auditoria_sku_master.py`), que não realiza nenhuma escrita.
- Relatório de origem: `relatorios/sku_master_pendencias_finais.md` (fase SKU-PENDENCIAS-01).

## Resumo das pendências (herdado da SKU-PENDENCIAS-01)

| Métrica | Valor |
|---|---:|
| Total de produtos cadastrados | 11.105 |
| Total ativos/auditáveis | 10.839 |
| Total corrigido (`sku_corrigido=1`) | 29 |
| Total pendente | 10.810 |
| Sem SKU Master | 6.256 |
| Sem fabricante | 7.687 |
| Itens em grupos 100% duplicados | 457 |
| Grupos 100% duplicados | 147 |
| Itens com sugestão automática de cascata | 1.935 |
| Fabricantes problemáticos (`UN`/`SR`/`S R`/`MD`) | 0 |
| LIMPO / SUSPEITO / CONTAMINADO_FORTE / SKU_PENDENTE / DUPLICADO | 4.178 / 1.473 / 3.939 / 792 / 457 |

## Duplicatas 100% iguais

- **Total de grupos**: 147
- **Total de itens**: 457
- **Grupos risco BAIXO**: 78 grupos (208 itens) — descrição 100% igual, sem conflito de fabricante/marca/SKU Master entre os membros do grupo.
- **Grupos risco MEDIO**: 37 grupos (115 itens) — descrição 100% igual, mas fabricante, marca ou SKU Master já preenchido diverge entre membros do mesmo grupo.
- **Grupos risco ALTO**: 32 grupos (134 itens) — descrições originais dos fornecedores (campo `precos_fornecedores.descricao_original`) contêm tokens numéricos com unidade (volume/número/calibre/medida/concentração) que divergem entre membros do grupo, mesmo com `produto_padrao` idêntico — sinal de possível produto diferente reunido no mesmo grupo textual.

Todos os 457 itens foram exportados com seus grupos, dados atuais e classificação de risco em:
`relatorios/sku_lote_01_duplicatas_100.csv`

Observação de transparência: a checagem de risco ALTO é uma heurística por regex e pode gerar falsos positivos (ex.: número colado a uma letra, como `"N7,5MM"`, confundido com um valor diferente). Isso está documentado com um caso real no arquivo de regras de bloqueio. Isso não compromete a segurança do processo — pelo contrário, reforça que todo grupo ALTO deve passar por revisão manual antes de qualquer ação, o que já é a recomendação desta fase.

## Regras de bloqueio de cascata
Criadas em `relatorios/sku_lote_01_regras_bloqueio_cascata.md`, cobrindo 8 categorias de divergência que devem impedir cascata automática: volume (ML), número/tamanho (Nº), calibre (G), medida linear (CM/MM/FR/CH), concentração (%/MG/MG por ML/MCG/G), embalagem/apresentação (CX/UND/FR/AMP/BOLSA/SERINGA/SONDA), público-alvo (adulto/infantil/pediátrico/neonatal) e lado/tipo/modelo. Cada regra traz pelo menos um caso real já observado (seringa 5ML↔10ML, sonda Foley Nº14↔Nº12, papel grau cirúrgico 150mm↔300mm) confirmando a necessidade.

**Nenhuma cascata automática foi aplicada ou será aplicada nesta fase.**

## Amostra para revisão manual
- Arquivo: `relatorios/sku_lote_01_amostra_correcao_manual.csv`
- Quantidade: 100 linhas, cobrindo 25 grupos completos (todos de risco BAIXO).
- Critérios aplicados:
  - Apenas grupos classificados como risco **BAIXO** (sem conflito de fabricante/marca/SKU Master).
  - Apenas descrições 100% duplicadas (mesmo `produto_padrao` normalizado exato).
  - Grupos com divergência de volume/número/calibre/medida/concentração ficam automaticamente fora (esses caem em MEDIO ou ALTO, nunca em BAIXO).
  - Priorização pelos maiores grupos primeiro (mais produtos duplicados = maior ganho de consolidação por decisão).
  - Sugestão de SKU Master/fabricante/marca calculada como o primeiro valor não vazio já existente dentro do próprio grupo (nunca um valor novo inventado) — se nenhum membro do grupo tiver SKU Master definido, a sugestão cai para o próprio `produto_padrao` do grupo.

## Riscos

- **Cascata errada por volume/número/calibre/medida/concentração**: risco principal desta fase, confirmado com casos reais (ver seção acima e arquivo de regras de bloqueio). Por isso, nenhuma cascata automática foi ou será aplicada — toda consolidação exige preview manual na tela de Auditoria antes de salvar.
- **Grupos MEDIO com conflito de fabricante/marca/SKU Master**: podem indicar que, apesar da descrição idêntica, alguém já corrigiu parcialmente um item do grupo com um valor diferente do resto — exige decisão humana sobre qual valor é o correto, não uma escolha automática.
- **Falsos positivos na classificação ALTO**: a extração de tokens numéricos por regex simples pode marcar como ALTO grupos que na prática são seguros (ex.: número de tubo colado a uma letra na descrição do fornecedor). Isso é uma margem de segurança intencional, não um erro a "corrigir automaticamente" — o custo de revisar manualmente um grupo seguro é muito menor que o custo de fundir dois produtos diferentes.
- **Volume de decisões**: mesmo restringindo a amostra a 100 linhas/25 grupos de risco BAIXO, ainda restam 53 grupos BAIXO adicionais e todos os grupos MEDIO/ALTO para lotes futuros — este primeiro lote é deliberadamente pequeno para validar o processo antes de escalar.

## Recomendação final

**APTO_PARA_REVISAO_MANUAL_LOTE_01**

Os artefatos desta fase (CSV completo de duplicatas classificadas por risco, regras de bloqueio de cascata e amostra de 100 linhas priorizando risco BAIXO) estão prontos para revisão humana. Nenhuma alteração foi feita no banco, no código ou no SKU_MASTER. A aplicação efetiva das correções depende de autorização explícita para uma próxima fase de execução (fora do escopo da SKU-LOTE-01).
