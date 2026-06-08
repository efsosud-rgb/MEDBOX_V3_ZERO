# Plano da Busca Inteligente V2

Data: 2026-06-08

Escopo desta entrega:

- Criar uma camada nova de busca inteligente.
- Manter a busca atual intacta.
- Nao alterar banco, templates, importadores, cotacoes ou rotas Flask.

## Arquivos criados

### `core/busca_inteligente.py`

Nova camada paralela de busca.

Ela nao substitui `buscar_produto` em `core/banco.py`.
Ela expõe uma nova funcao principal:

```python
buscar_produto_inteligente(termo, limite=20)
```

### `relatorios/plano_busca_inteligente_v2.md`

Este relatorio tecnico com a descricao da implementacao, estrategia de score, testes manuais, riscos e proximo passo de integracao.

## Funcoes criadas

### Funcao publica

```python
buscar_produto_inteligente(termo, limite=20)
```

Responsabilidades:

1. Normalizar e expandir o termo.
2. Recuperar candidatos usando as tabelas atuais.
3. Calcular score real com RapidFuzz.
4. Carregar precos atuais e historico.
5. Ordenar por relevancia, menor preco e nome do produto.
6. Retornar ate `limite` resultados.

### Funcoes internas

- `_termos_expandidos(termo)`
- `_produto_base(row)`
- `_adicionar_candidato(candidatos, row, campo, texto)`
- `_buscar_por_campo_produto(cursor, candidatos, campo_sql, campo_evidencia, termo)`
- `_buscar_por_equivalencias(cursor, candidatos, termo)`
- `_buscar_por_precos(cursor, candidatos, campo_sql, campo_evidencia, termo)`
- `_buscar_por_fornecedor(cursor, candidatos, termo)`
- `_recuperar_candidatos(cursor, termos)`
- `_score_texto(consulta, texto, usar_partial=False)`
- `_calcular_score(termo, produto)`
- `_carregar_precos(cursor, produto_id)`
- `_carregar_historico(cursor, produto_id)`
- `_montar_resultado(cursor, termo, produto)`

## Etapa 1 - Recuperacao de candidatos

A V2 recupera candidatos sem alterar a estrutura do banco.

Tabelas usadas:

- `produtos`
- `equivalencias`
- `precos_fornecedores`
- `fornecedores`

Campos pesquisados:

- `produtos.produto_padrao`
- `produtos.fabricante`
- `equivalencias.descricao_equivalente`
- `precos_fornecedores.descricao_original`
- `precos_fornecedores.marca`
- `fornecedores.nome`

A recuperacao usa as mesmas bases de compatibilidade da busca atual:

- `normalizar_texto`
- `gerar_variacoes`
- `expandir_com_sinonimos`

Essas funcoes continuam em `core/banco.py` e foram apenas reaproveitadas.

## Etapa 2 - Calculo de score real

A V2 usa RapidFuzz.

Metricas usadas:

- `fuzz.token_set_ratio`: bom para termos fora de ordem.
- `fuzz.partial_ratio`: usado para descricoes longas, especialmente `descricao_original`.

Pesos aplicados por campo:

| Campo | Peso |
|---|---:|
| `produto_padrao` | 1.00 |
| `equivalencia` | 0.95 |
| `descricao_original` | 0.80 |
| `fabricante` | 0.55 |
| `marca` | 0.55 |
| `fornecedor` | 0.30 |

Para cada produto candidato:

1. O sistema calcula o melhor score textual por campo.
2. Aplica o peso correspondente ao campo.
3. Usa o maior score ponderado como `score_busca`.
4. Mantem detalhes em `scores_por_campo` e `evidencias_busca` para auditoria futura.

### Ajuste fino de score

A calibragem inicial gerava muitos `score_busca = 100.0` em buscas amplas, porque `token_set_ratio` pode atribuir 100 quando o termo pesquisado aparece como subconjunto de uma descricao maior.

Exemplo observado:

- Busca: `GLICOSE`
- Resultado indesejado: `TIRA P/ TESTE DE GLICOSE` empatava com produtos iniciados por `GLICOSE`.

Para reduzir esse empate artificial, a V2 agora aplica tres ajustes:

1. Bonus quando o texto comeca com o termo pesquisado, principalmente em `produto_padrao` e `equivalencia`.
2. Reducao do impacto de `partial_ratio` em `descricao_original`, porque descricoes de fornecedor costumam ser longas.
3. Penalidade quando o termo aparece apenas no meio ou no final do texto, com penalidade adicional para descricoes longas e excesso de tokens.

Comportamento esperado:

| Busca | Antes esperado | Depois esperado |
|---|---|---|
| `GLICOSE` | Itens como `TIRA P/ TESTE DE GLICOSE` podiam empatar com `GLICOSE 25%` | Produtos que comecam com `GLICOSE` devem aparecer antes de ocorrencias no meio/final |
| `DIPIRONA` | Descricoes longas contendo `DIPIRONA` podiam empatar com produto principal | Produto principal iniciado por `DIPIRONA` deve ter prioridade |
| `SORO` | Itens que apenas citam `SORO` podiam se aproximar de soros principais | Produtos iniciados por `SORO` devem ser favorecidos |
| `SERINGA` | Ocorrencias parciais em descricoes longas podiam ganhar relevancia excessiva | Produto padrao iniciado por `SERINGA` deve ficar acima |
| `CATETER` | Descricoes longas com `CATETER` no meio podiam empatar | `CATETER...` no inicio deve ser priorizado |
| `ATADURA` | Ocorrencias parciais podiam empatar por subconjunto | `ATADURA...` no inicio deve ser priorizada |

Exemplo conceitual:

```python
score_produto = token_set_ratio(termo, produto_padrao) * 1.00
score_equiv = token_set_ratio(termo, equivalencia) * 0.95
score_desc = max(token_set_ratio(...), partial_ratio(...)) * 0.80
score_final = max(score_produto, score_equiv, score_desc, ...)
```

## Ordenacao dos resultados

A ordenacao segue a regra solicitada:

1. Maior score de relevancia.
2. Menor preco.
3. Nome do produto.

Produtos sem preco nao sao removidos.

Quando nao ha preco:

- `menor_preco` fica `None`.
- `fornecedor_menor` recebe `"sem preco cadastrado"`.
- O produto continua no resultado.

## Compatibilidade com a busca atual

A V2 retorna campos proximos aos usados pela busca atual:

- `id`
- `sku`
- `produto_padrao`
- `fabricante`
- `categoria`
- `sku_master`
- `score_busca`
- `origem_busca`
- `precos`
- `menor_preco`
- `fornecedor_menor`
- `historico_precos`
- `tem_historico_real`

Campos novos para auditoria:

- `scores_por_campo`
- `evidencias_busca`

## Como testar manualmente

Importante: a rota `/busca` ainda nao usa a V2.

Para testar manualmente em ambiente controlado, usar um comando de leitura que importe a funcao nova e consulte os termos abaixo.

Nesta sessao, a validacao automatica de execucao nao foi feita porque o Python disponivel no runtime Codex nao possui `rapidfuzz` instalado (`ModuleNotFoundError`). O projeto ja declara `rapidfuzz==3.9.6` em `requirements.txt`; portanto, o teste manual deve ser feito em um ambiente com as dependencias do projeto instaladas.

Atualizacao do ajuste fino: foi feita uma tentativa de instalar `rapidfuzz==3.9.6` temporariamente fora do projeto para rodar os termos abaixo. A instalacao concluiu, mas o runtime continuou falhando ao importar `from rapidfuzz import fuzz`, enxergando `rapidfuzz` como namespace vazio. Por isso, nesta sessao foi validada apenas a sintaxe do modulo; a validacao funcional deve ser repetida no ambiente da aplicacao com as dependencias instaladas.

Termos obrigatorios:

- `DIPIRONA`
- `SORO`
- `GLICOSE`
- `SERINGA`
- `CATETER`
- `ATADURA`

Exemplo de teste manual:

```python
from core.busca_inteligente import buscar_produto_inteligente

termos = ["DIPIRONA", "SORO", "GLICOSE", "SERINGA", "CATETER", "ATADURA"]

for termo in termos:
    resultados = buscar_produto_inteligente(termo, limite=5)
    print(f"\nTERMO: {termo}")
    for item in resultados:
        print(
            item["score_busca"],
            item["produto_padrao"],
            item["menor_preco"] if item["menor_preco"] is not None else "sem preco cadastrado",
        )
```

O que verificar:

1. A funcao retorna lista, mesmo quando nao houver preco.
2. `score_busca` varia conforme o termo e o campo encontrado.
3. Produtos com match melhor aparecem antes de produtos baratos menos relevantes.
4. Produtos sem preco aparecem no resultado quando encontrados.
5. `origem_busca` vem como `busca_inteligente_v2`.

## Riscos

### Dependencia RapidFuzz

`requirements.txt` ja lista `rapidfuzz==3.9.6`.
Se o ambiente nao tiver dependencias instaladas, a importacao da V2 falhara.

### Performance

A V2 ainda recupera candidatos com `LIKE '%termo%'`, como a busca atual.
Em bases maiores, pode ser necessario medir tempo de resposta e avaliar indices ou FTS5.

### Volume de candidatos

Sinônimos, variacoes e tokens podem ampliar o conjunto inicial de candidatos.
Isso melhora recall, mas pode aumentar custo da busca.

### Score inicial precisa calibracao

Os pesos definidos sao conservadores e explicitos, mas devem ser avaliados com casos reais.

### Busca por fornecedor

Fornecedor tem peso baixo, mas ainda pode trazer produtos relacionados ao fornecedor quando o termo coincidir com o nome dele.

## Proximo passo para integrar na rota `/busca`

Depois de validar manualmente a V2:

1. Criar uma branch separada apenas para integracao da rota.
2. Alterar `app.py` para trocar:

```python
resultados = buscar_produto(termo)
```

por:

```python
from core.busca_inteligente import buscar_produto_inteligente
resultados = buscar_produto_inteligente(termo)
```

3. Manter `buscar_produto` antiga disponivel para rollback.
4. Testar a tela `/busca` com os termos:
   - `DIPIRONA`
   - `SORO`
   - `GLICOSE`
   - `SERINGA`
   - `CATETER`
   - `ATADURA`
5. Comparar resultado V1 x V2 antes de aprovar a troca definitiva.

## Resumo

A Busca Inteligente V2 foi criada como camada nova e paralela.
Ela recupera candidatos nas tabelas atuais, calcula score real com RapidFuzz e ordena por relevancia antes de preco.

A busca atual permanece intacta e nenhuma integracao com a rota `/busca` foi feita nesta etapa.
