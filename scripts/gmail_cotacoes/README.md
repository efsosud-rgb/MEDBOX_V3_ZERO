# Robô Gmail Cotações — MedBox

Analisa cotações recebidas por e-mail, cruzando os marcadores das vendedoras
(JESSICA, STHEFANY, PAMELA, LAYANE) com o marcador PEDIDO, e gera relatórios
de vendas/cotações por vendedor, cliente e cotação.

**Estado atual: modo local apenas.** A integração real com a Gmail API
(`gmail_client.py`) não foi configurada — não há credenciais, OAuth, leitura
ou envio de e-mail. O robô roda hoje a partir de um manifesto JSON local que
descreve os e-mails/anexos (ver `manifesto_local.py`).

## Arquitetura

| Arquivo | Papel |
|---|---|
| `config.py` | Caminhos, pesos de score, limiares de classificação |
| `gmail_client.py` | Interface da Gmail API — **placeholder**, levanta erro se usado |
| `extrator_anexos.py` | Localiza/copia anexos entre pastas locais |
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
   projeto principal e em `requirements_gmail_cotacoes.txt`). Ainda não
   estava instalado no ambiente Python usado para escrever e testar este
   robô.
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

## Uso (modo local)

```
python -m py_compile scripts/gmail_cotacoes/*.py
python scripts/gmail_cotacoes/testar_matching_itens.py

python scripts/gmail_cotacoes/main.py --somente-local \
    --manifesto-local data/gmail_cotacoes/amostras/manifesto_hmar_1006_real.json \
    --saida data/gmail_cotacoes/relatorios/relatorio_hmar_1006_real.xlsx --dry-run
```

Saídas geradas:
- `<saida>.xlsx` com abas EMAILS_COTACOES, EMAILS_PEDIDOS, ITENS_COTADOS,
  ITENS_PEDIDOS, CRUZAMENTO_ITENS, RELATORIO_COTACOES,
  ITENS_CRITICOS_PERDIDOS, ITENS_REVISAR, DASHBOARD_BASE
- `<saida>_resumo.txt`
- CSVs equivalentes em `data/gmail_cotacoes/relatorios/csv/`

## O que falta para a Gmail API real

- Criar projeto no Google Cloud, habilitar Gmail API, gerar `credentials.json`
  (OAuth client — Desktop app).
- Implementar o fluxo OAuth2 em `gmail_client.py` (google-auth-oauthlib),
  persistindo o token em `token_gmail.json` (git-ignorado).
- Implementar `listar_emails_por_marcador` (Gmail API `users.messages.list`
  com filtro de label) e `baixar_anexo` (`users.messages.attachments.get`).
- Nenhuma dessas credenciais/arquivos deve ser commitada — já protegidos no
  `.gitignore` da raiz do projeto.
