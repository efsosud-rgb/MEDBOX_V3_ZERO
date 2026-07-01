# SKU-LOTE-01 — Regras de bloqueio de cascata perigosa

## Objetivo
Definir regras textuais para impedir que a cascata (propagação de SKU Master/fabricante/categoria para produtos "semelhantes") funda produtos que são, na prática, itens diferentes — problema confirmado com exemplos reais no relatório `relatorios/sku_master_pendencias_finais.md` (ex.: seringa 5ML sugerida como 10ML; sonda Foley Nº14 sugerida como Nº12; papel grau cirúrgico de 150mm sugerido como 300mm).

Estas regras **não foram implementadas em código nesta fase** (nenhum arquivo de `core/`/`app.py`/`templates/` foi alterado). Servem como especificação para uma futura melhoria do algoritmo de sugestão/cascata e como checklist de revisão manual enquanto isso não existir.

## Princípio geral
A cascata só deve ser aplicada entre dois produtos quando **todos os tokens numéricos com unidade** (volume, número, calibre, medida, concentração) presentes na descrição forem **idênticos** entre origem e destino. Se qualquer um desses tokens divergir, a cascata para aquele par deve ser **bloqueada**, mesmo que o score de similaridade textual (`fuzz.token_set_ratio`) seja alto.

## Categorias de token que bloqueiam cascata quando divergentes

| Categoria | Exemplos de valor | Padrão típico no texto |
|---|---|---|
| Volume | 5ML, 10ML, 20ML, 100ML, 250ML, 500ML, 1000ML | `\d+\s*ML` |
| Número/tamanho de sonda ou tubo | Nº 06, Nº 08, Nº 10, Nº 12, Nº 14, Nº 16 | `N[º°.]?\s*\d+` |
| Calibre de agulha | 18G, 20G, 22G, 25G | `\d+\s*G(?!R)` (evitar confundir com grama) |
| Medida linear | CM, MM, FR, CH | `\d+\s*(CM|MM|FR|CH)` |
| Concentração | %, MG/ML, MG, G, MCG | `\d+([.,]\d+)?\s*(%|MG/ML|MG|MCG|G)` |
| Embalagem/apresentação | CX, UND, FR, AMP, BOLSA, SERINGA, SONDA | comparação de palavra-chave de apresentação |
| Público-alvo | ADULTO, INFANTIL, PEDIÁTRICO, NEONATAL | comparação de palavra-chave, quando presente em ambos |
| Lado/tipo/modelo | DIREITO/ESQUERDO, MASCULINO/FEMININO, TIPO I/II, MODELO X/Y | comparação de palavra-chave, quando presente em ambos |

## Regras de bloqueio (uma por categoria)

1. **Volume**: se origem e destino tiverem valores de volume (`ML`) diferentes, bloquear cascata. Ex.: `5ML` ≠ `10ML` ≠ `20ML`.
2. **Número/tamanho**: se origem e destino tiverem número de sonda/tubo/cateter diferente, bloquear cascata. Ex.: `Nº 12` ≠ `Nº 14` ≠ `Nº 16`.
3. **Calibre**: se origem e destino tiverem calibre de agulha diferente, bloquear cascata. Ex.: `18G` ≠ `20G` ≠ `22G`.
4. **Medida linear**: se origem e destino tiverem medida em CM/MM/FR/CH diferente, bloquear cascata. Ex.: `150MM` ≠ `300MM`; `Fr 12` ≠ `Fr 14`.
5. **Concentração**: se origem e destino tiverem concentração (`%`, `MG/ML`, `MG`, `G`, `MCG`) diferente, bloquear cascata. Ex.: `40MG` ≠ `60MG` ≠ `80MG`.
6. **Embalagem/apresentação**: se origem e destino indicarem apresentações estruturalmente diferentes (ex.: `CX` vs `AMP`, `SERINGA` vs `FRASCO AMPOLA`, `BOLSA` vs `SONDA`), bloquear cascata, mesmo com texto parecido.
7. **Público-alvo**: se um dos dois mencionar explicitamente `ADULTO`/`INFANTIL`/`PEDIÁTRICO`/`NEONATAL` e o outro mencionar um público diferente (ou nenhum), bloquear cascata.
8. **Lado/tipo/modelo**: se houver indicação de lado (`DIREITO`/`ESQUERDO`), gênero (`MASCULINO`/`FEMININO`) ou modelo/tipo explícito divergente, bloquear cascata.

## Casos reais já observados que confirmam a necessidade destas regras

- `SERINGA DESCARTAVEL ESTERIL 5ML` → sugestão automática apontou `SERINGA DESCARTAVEL ESTERIL 10ML` (regra 1 violada).
- `SONDA DE FOLLEY Nº 14 2 VIAS` → sugestão automática apontou `SONDA FOLLEY N12 DUAS VIAS` (regra 2 violada).
- `PAPEL GRAU CIRURGICO C/FILME 150MM X 100MTS` → sugestão automática apontou `PAPEL GRAU CIRURGICO 300MM X 100MTS` (regra 4 violada).

## Observação sobre falsos positivos na triagem automática

Durante a geração do CSV `sku_lote_01_duplicatas_100.csv` desta fase, a checagem heurística de divergência numérica (usada só para classificar risco, sem aplicar nada) também gerou ao menos um falso positivo: no grupo `G001` (`TUBO ENDOTRAQUEAL COM BALONETE Nº 7,5`), um dos registros de origem tem a descrição do fornecedor escrita como `"TUBO ENDOTRAQUEAL C/BALAO N7,5MM UN SOLIDOR"` — o número "7,5" está colado à letra "N" sem espaço, o que confundiu a extração de token e destacou apenas "5MM" como se fosse um valor diferente. Isso não representa um produto diferente; é uma limitação de uma extração baseada em regex simples. **Por segurança, o grupo foi mantido como ALTO/"não consolidar sem revisão"** mesmo sendo, na prática, seguro — confirmando que a política correta é sempre revisão manual antes de qualquer consolidação, nunca aplicação automática baseada apenas na regra textual.

## Recomendação de implementação futura (fora do escopo desta fase)
Quando uma fase futura for autorizada a alterar código, a lógica de `_sugerir_sku_limpo` e `buscar_produtos_afetados_cascata` em `core/auditoria_sku_master.py` deveria extrair os tokens acima de origem e destino e **recusar a sugestão/cascata automaticamente** se qualquer token numérico com unidade divergir, independentemente do score de similaridade textual.
