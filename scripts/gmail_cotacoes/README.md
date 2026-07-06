# Robô Gmail Cotações — MedBox

Analisa cotações recebidas por e-mail, cruzando os marcadores das vendedoras
(JESSICA, STHEFANY, PAMELA, LAYANE) com os marcadores PEDIDO e CANCELADO, e
gera relatórios de vendas/cotações por vendedor, cliente e cotação.

**Estado atual: Fase 1 (modo local) + Fase 2 (Gmail real, SOMENTE LEITURA
de diagnóstico).** O modo local (manifesto JSON + anexos em disco) continua
sendo o caminho padrão e totalmente funcional. O modo `--gmail-real` fala
com a Gmail API de verdade, mas só para diagnóstico controlado (listar
labels, verificar marcadores, buscar amostra de e-mails, baixar amostra de
anexos) — nunca envia, responde, arquiva, apaga ou altera labels. Escopo
OAuth único: `https://www.googleapis.com/auth/gmail.readonly`.

## Ambiente oficial: `.venv` do projeto

O ambiente validado e oficial para rodar o robô é o `.venv` na raiz do
projeto — **não o Python global do sistema**. Só o `.venv` tem, ao mesmo
tempo, `pdfplumber`/`pymupdf` (parser oficial de PDF) e as bibliotecas da
Gmail API (`google-api-python-client`, `google-auth`,
`google-auth-oauthlib`, `python-dotenv`).

Sempre use o Python do `.venv` explicitamente:
```
.venv\Scripts\python.exe scripts/gmail_cotacoes/main.py ...
```

Nunca use `python`/`pip` global para este robô. Para instalar/atualizar
dependências, sempre pelo `.venv`:
```
.venv\Scripts\python.exe -m pip install -r requirements_gmail_cotacoes.txt
```

Exemplos de uso real (diagnóstico, somente leitura):
```
.venv\Scripts\python.exe scripts/gmail_cotacoes/main.py --gmail-real --dry-run \
    --limite-cotacoes 1 --limite-pedidos 1 --acao-gmail buscar-amostra --marcador PEDIDO

.venv\Scripts\python.exe scripts/gmail_cotacoes/main.py --gmail-real --dry-run \
    --limite-pedidos 10 --acao-gmail contar-por-periodo --marcador PEDIDO \
    --data-inicio 2026-06-01 --data-fim 2026-06-30

.venv\Scripts\python.exe scripts/gmail_cotacoes/main.py --gmail-real --dry-run \
    --limite-cotacoes 1 --limite-pedidos 1 --acao-gmail baixar-anexos-amostra --marcador PEDIDO
```

Validado com testes reais controlados (1 mensagem por vez, `--dry-run`):
Ordem de Compra da LAYANE/PEDIDO (numero_oc 008875) e da STHEFANY
(numero_oc 008859) — em ambos os casos `pdfplumber` extraiu os itens sem
precisar do fallback `pdftotext`, e a soma dos itens bateu exatamente com
o total impresso no documento (zero avisos).

Regras que continuam valendo independente do ambiente:
- `credentials.json` e `token_gmail.json` ficam sempre ignorados pelo Git
  (raiz do projeto, nunca commitados).
- `data/gmail_cotacoes/` (amostras, anexos, relatórios) fica sempre
  ignorado pelo Git.
- Gmail permanece **somente leitura** — escopo único `gmail.readonly`,
  nunca envia/altera/apaga/arquiva nada.
- `--dry-run` é obrigatório em todo teste controlado contra a Gmail real.
- `DATA_VENDA` vem sempre da data de emissão da Ordem de Compra — nunca
  da data do e-mail, da cotação ou da entrega.

## Arquitetura

| Arquivo | Papel |
|---|---|
| `config.py` | Caminhos, pesos de score, limiares de classificação, escopo/paths OAuth |
| `gmail_client.py` | Cliente Gmail real, somente leitura (OAuth, labels, busca, download de anexo) |
| `extrator_anexos.py` | Localiza/copia anexos locais e salva anexos baixados da Gmail API |
| `parser_excel_cotacao.py` | Fonte **primária** dos itens cotados (Excel ERP, estruturado) |
| `parser_pdf_proposta.py` | Fonte **secundária**/informativa dos itens (PDF, best-effort) |
| `parser_pdf_oc.py` | Itens da Ordem de Compra (PDF) |
| `perfil_tecnico.py` | Extrai volume/dimensão/calibre/tamanho/etc. para evitar falso positivo |
| `correlacionador.py` | Score composto de e-mail + cruzamento de itens |
| `gerador_relatorios.py` | Gera XLSX (várias abas), TXT resumo e CSVs |
| `manifesto_local.py` | Carrega o manifesto JSON do modo local |
| `main.py` | Orquestrador / CLI |
| `testar_matching_itens.py` | Testes dos casos "podem casar" / "não podem casar" |

## Por que o Excel é a fonte primária dos itens cotados, e não o PDF da proposta?

O Excel `ITENS_ORCAMENTO` é um export estruturado do ERP do cliente — uma
linha por item, colunas fixas. É 100% confiável.

O PDF da proposta comercial quebra descrições longas em múltiplas linhas de
forma irregular, e a extração de texto (tanto por `pdftotext` quanto,
presumivelmente, em modo texto simples do `pdfplumber`) embaralha a ordem
vertical dos valores entre itens vizinhos. Isso foi validado no caso real
HMAR 1006: tentar emparelhar sequencialmente os tokens monetários da tabela
(a mesma técnica que funciona de forma **exata** para a Ordem de Compra, que
tem uma tabela mais simples) diverge da planilha de cotação a partir do
~10º item, porque um único item com valor "R$ -" já desalinha tudo o que
vem depois.

Por isso `parser_pdf_proposta.py` sempre marca `confianca_extracao="BAIXA"`
e não é usado como fonte de itens no pipeline principal — só para conferir
metadados (cliente, datas, valor total) e como fallback informativo.

## Extração de PDF: pdfplumber (oficial) vs pdftotext (fallback local)

`parser_pdf_oc.py` e `parser_pdf_proposta.py` tentam, nesta ordem:

1. **pdfplumber** — dependência oficial (está em `requirements.txt` do
   projeto principal e em `requirements_gmail_cotacoes.txt`). Instalado e
   validado no `.venv` do projeto (ver "Ambiente oficial" acima) — quando
   rodado com `.venv\Scripts\python.exe`, este é o caminho sempre usado,
   sem cair no fallback.
2. **pdftotext** (poppler/xpdf) via `subprocess`, se o binário estiver no
   PATH do sistema — no Windows, geralmente já vem junto com o Git for
   Windows (`mingw64/bin/pdftotext.exe`). Usado só para permitir teste
   local sem precisar instalar nada novo. Fica registrado no campo
   `metodo_extracao` do resultado.
3. Se nenhum dos dois estiver disponível, o parser levanta `RuntimeError`
   com o comando de instalação — nunca falha silenciosamente nem inventa
   dados.

Para uso oficial/produtivo, instale `pdfplumber`:
```
pip install pdfplumber
```

## Regras de classificação de itens (CRUZAMENTO_ITENS)

- **GANHO**: item cotado com valor, encontrado na OC, sem conflito técnico.
- **PERDIDO**: item cotado com valor, sem correspondente compatível na OC
  (ou claramente um produto tecnicamente diferente).
- **NAO_COTADO**: item cotado com valor zero, vazio ou "-".
- **POSSIVEL_GANHO_REVISAR**: texto muito parecido mas perfil técnico
  diverge (possível erro de cadastro), ou similaridade abaixo do limiar de
  confirmação. **Nunca vira GANHO automático.**

O perfil técnico (`perfil_tecnico.py`) compara volume, dimensões,
calibre/número, tamanho (P/M/G/GG), público (adulto/infantil),
esterilidade, presença de pó e tipo de conector Luer. Só bloqueia o match
quando os DOIS lados têm o atributo E os valores divergem — ausência de
informação em um dos lados não bloqueia.

## Regra de negócio final: quando um e-mail conta como venda (`classificar_email_venda`)

Marcadores monitorados: `JESSICA`, `STHEFANY`, `PAMELA`, `LAYANE`, `PEDIDO`,
`CANCELADO` (`config.MARCADORES_OBRIGATORIOS`).

| Marcadores/anexo do e-mail | STATUS_EMAIL | CONSIDERAR_VENDA | Observação |
|---|---|---|---|
| PEDIDO + OC reconhecida, sem CANCELADO | `VENDA_CONFIRMADA` | SIM | — |
| PEDIDO + OC reconhecida + CANCELADO | `CANCELADO` | NAO | CANCELADO sempre vence, mesmo com PEDIDO+OC |
| OC reconhecida, sem PEDIDO | `POSSIVEL_PEDIDO_REVISAR` | NAO | pode ser erro de marcação manual |
| PEDIDO, sem OC reconhecida | `PEDIDO_SEM_OC_RECONHECIDA` | NAO | — |
| PEDIDO + OC, sem marcador de vendedora | `VENDA_CONFIRMADA` | SIM | `VENDEDORA=SEM_VENDEDORA`, `STATUS_REVISAO=REVISAR_VENDEDORA` |

Duas regras não-negociáveis:
- **VENDEDORA vem sempre do marcador do Gmail** (JESSICA/STHEFANY/PAMELA/
  LAYANE) — nunca adivinhada por PDF, cliente, assunto ou texto do e-mail.
  Sem marcador de vendedora → `VENDEDORA=SEM_VENDEDORA`.
- **DATA_VENDA vem sempre da data de EMISSÃO da Ordem de Compra** (o
  cabeçalho "Cidade, DD/MM/AAAA" do PDF, ver `parser_pdf_oc._RE_DATA_OC`) —
  nunca da data de entrega, da cotação, ou de recebimento do e-mail.

"OC reconhecida" nas ações de diagnóstico (`buscar-amostra`) é uma
heurística por NOME do anexo (`extrator_anexos.parece_ordem_compra` —
procura "ORDEM DE COMPRA" ou o token isolado "OC"), já que essa ação não
baixa anexo algum. Em `baixar-anexos-amostra`, depois de baixar, o anexo
reconhecido é de fato parseado (`parser_pdf_oc.parse_pdf_oc`) para obter
`DATA_VENDA` real. No modo local (manifesto), o par cotação/pedido já é
por construção uma venda confirmada — `RELATORIO_COTACOES` usa
`classificar_email_venda({vendedora_do_caso, "PEDIDO"}, tem_anexo_ordem_compra=True)`
para preencher os mesmos campos de forma consistente com o modo real.

`POSSIVEIS_PEDIDOS_REVISAR` (aba nova) reúne as linhas de
`RELATORIO_COTACOES` com `STATUS_EMAIL` em
`POSSIVEL_PEDIDO_REVISAR`/`PEDIDO_SEM_OC_RECONHECIDA`, ou
`STATUS_REVISAO=REVISAR_VENDEDORA`.

## Uso (modo local)

```
.venv\Scripts\python.exe -m py_compile scripts/gmail_cotacoes/*.py
.venv\Scripts\python.exe scripts/gmail_cotacoes/testar_matching_itens.py

.venv\Scripts\python.exe scripts/gmail_cotacoes/main.py --somente-local \
    --manifesto-local data/gmail_cotacoes/amostras/manifesto_hmar_1006_real.json \
    --saida data/gmail_cotacoes/relatorios/relatorio_hmar_1006_real.xlsx --dry-run
```

Saídas geradas:
- `<saida>.xlsx` com abas EMAILS_COTACOES, EMAILS_PEDIDOS, ITENS_COTADOS,
  ITENS_PEDIDOS, CRUZAMENTO_ITENS, RELATORIO_COTACOES,
  ITENS_CRITICOS_PERDIDOS, ITENS_REVISAR, DASHBOARD_BASE,
  POSSIVEIS_PEDIDOS_REVISAR
- `<saida>_resumo.txt`
- CSVs equivalentes em `data/gmail_cotacoes/relatorios/csv/`

## Uso (Gmail real — diagnóstico somente leitura)

Pré-requisito: `credentials.json` (OAuth client tipo **Desktop app**, criado
no Google Cloud Console com a Gmail API habilitada e o escopo
`gmail.readonly`) salvo na raiz do projeto. Nunca commitar esse arquivo —
já está no `.gitignore`.

`--gmail-real` sempre exige `--dry-run` **e** pelo menos um limite
(`--limite-cotacoes` e/ou `--limite-pedidos`) — o robô se recusa a rodar
contra a Gmail API real sem os dois, para nunca varrer a caixa inteira por
acidente.

```
# 1. Listar todos os labels da conta (para confirmar nomes/hierarquia reais)
.venv\Scripts\python.exe scripts/gmail_cotacoes/main.py --gmail-real --dry-run --limite-cotacoes 1 \
    --acao-gmail listar-labels

# 2. Verificar se JESSICA/STHEFANY/PAMELA/LAYANE/PEDIDO/CANCELADO existem como label
.venv\Scripts\python.exe scripts/gmail_cotacoes/main.py --gmail-real --dry-run --limite-cotacoes 1 \
    --acao-gmail verificar-marcadores

# 3. Buscar amostra de e-mails de um marcador (sem baixar anexo nenhum)
.venv\Scripts\python.exe scripts/gmail_cotacoes/main.py --gmail-real --dry-run --limite-cotacoes 1 --limite-pedidos 1 \
    --acao-gmail buscar-amostra --marcador PEDIDO

# 4. Contar/listar e-mails por periodo do Gmail (sem baixar anexo e sem gravar banco)
.venv\Scripts\python.exe scripts/gmail_cotacoes/main.py --gmail-real --dry-run --limite-pedidos 10 \
    --acao-gmail contar-por-periodo --marcador PEDIDO --data-inicio 2026-06-01 --data-fim 2026-06-30

# 5. Baixar amostra de anexos de um marcador (grava em data/gmail_cotacoes/anexos/<marcador>/<message_id>/)
.venv\Scripts\python.exe scripts/gmail_cotacoes/main.py --gmail-real --dry-run --limite-cotacoes 1 --limite-pedidos 1 \
    --acao-gmail baixar-anexos-amostra --marcador PEDIDO
```

### Filtro de periodo no Gmail

As acoes de busca diagnostica aceitam `--data-inicio` e `--data-fim` no
formato `YYYY-MM-DD`. Esse filtro e aplicado na busca do Gmail pela data do
e-mail, usando os operadores `after:YYYY/MM/DD` e `before:YYYY/MM/DD`.

Importante: `before:` no Gmail e exclusivo. Portanto, quando o usuario passa
`--data-fim 2026-06-30`, a query enviada usa `before:2026/07/01` para incluir
todo o dia 30/06/2026.

Exemplo de query gerada:
```
label:PEDIDO after:2026/06/01 before:2026/07/01
```

Esse filtro nunca substitui `DATA_VENDA`: `DATA_VENDA` continua vindo somente
da data de emissao da Ordem de Compra extraida por `parser_pdf_oc.py`.
`contar-por-periodo` e diagnostico read-only: lista ate N mensagens, nao baixa
anexos, nao processa cotacoes, nao gera relatorio e nao persiste dados.

No primeiro uso, `flow.run_local_server()` abre o navegador para a tela de
consentimento OAuth do Google e, ao autorizar, grava `token_gmail.json` na
raiz do projeto (também git-ignorado). Nas próximas execuções o token é
reaproveitado/renovado automaticamente. `gmail_client.py` valida em tempo
de execução que o token só tem o escopo `gmail.readonly` — se detectar
qualquer escopo além desse, recusa a operação e orienta a apagar o token e
gerar um novo.

### O que este modo NUNCA faz

Enviar/responder e-mail, criar rascunho, alterar labels, arquivar, apagar
ou marcar mensagens como lidas/não lidas. `gmail_client.py` não implementa
nenhum desses métodos — só leitura (`labels.list`, `messages.list`,
`messages.get`, `messages.attachments.get`).

### Sobre o corpo do e-mail

Para listar nomes de anexo, a Gmail API exige `format="full"` (o formato
`metadata` não expõe a árvore MIME). Mesmo assim, o código nunca lê o
campo `body.data` de nenhuma parte do e-mail (é onde ficaria o texto do
corpo) — só cabeçalhos (Subject/From/Date), o `snippet` curto que a própria
API já devolve, e metadados de anexo (nome, mimeType, attachmentId,
tamanho). Ver `_extrair_metadados_anexos` em `gmail_client.py`.

## O que ainda falta para produção real (fora do escopo desta fase)

- Processamento em massa (hoje é só diagnóstico com amostra pequena).
- Persistir o resultado da correlação/cruzamento a partir de e-mails reais
  no pipeline de relatórios (hoje isso só existe para o manifesto local).
- Rotação/expiração de token em ambiente não-interativo (ex.: agendador).
