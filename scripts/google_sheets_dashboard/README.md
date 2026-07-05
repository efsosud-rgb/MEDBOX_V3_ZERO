# Painel MEDBOX (Google Sheets / Apps Script)

Dashboard para visualizar os relatórios gerados pelo robô Python
(`scripts/gmail_cotacoes/`). Não lê Gmail nem executa nada sozinho — só
importa os CSVs que o robô já gerou localmente.

## Arquivos

| Arquivo | Papel |
|---|---|
| `appsscript.json` | Manifesto do projeto Apps Script |
| `Config.gs` | Cores MedBox, nomes de abas, cabeçalhos esperados |
| `Code.gs` | Preparar planilha, verificar estrutura, limpar bases geradas |
| `Menu.gs` | Menu MEDBOX (`onOpen`) |
| `ImportadorRelatorio.gs` | Importa os CSVs (via pasta do Google Drive) |
| `Dashboard.gs` | Cards de resumo + relatórios agregados (clientes, responsáveis, respostas) |

## Abas

`CONFIG`, `BASE_COTACOES`, `EMAILS_COTACOES`, `EMAILS_PEDIDOS`,
`ITENS_COTADOS`, `ITENS_PEDIDOS`, `CRUZAMENTO_ITENS`, `RELATORIO_COTACOES`,
`ITENS_CRITICOS_PERDIDOS`, `ITENS_REVISAR`, `DASHBOARD_BASE`, `DASHBOARD`,
`ACOMPANHAMENTO`, `RELATORIO_CLIENTES`, `RELATORIO_RESPONSAVEIS`,
`RELATORIO_RESPOSTAS`.

## Menu MEDBOX

1. **Preparar Planilha** — cria as abas que faltarem e formata cabeçalhos.
2. **Importar Relatório CSV** — pede o nome de uma pasta do Google Drive
   contendo os arquivos `<NOME_DA_ABA>.csv` (os mesmos gerados em
   `data/gmail_cotacoes/relatorios/csv/`) e importa cada um para a aba
   correspondente.
3. **Atualizar Dashboard** — recalcula os cards em `DASHBOARD` a partir de
   `DASHBOARD_BASE` e `ITENS_CRITICOS_PERDIDOS`.
4. **Atualizar Relatórios** — recalcula `RELATORIO_CLIENTES`,
   `RELATORIO_RESPONSAVEIS`, `RELATORIO_RESPOSTAS` e `ACOMPANHAMENTO` a
   partir de `RELATORIO_COTACOES`, e chama Atualizar Dashboard.
5. **Verificar Estrutura** — confere se todas as abas existem e se os
   cabeçalhos batem com o esperado (`Config.gs`).
6. **Limpar Bases Geradas** — apaga os dados (mantendo cabeçalho) das abas
   alimentadas pelo robô, sem tocar em `CONFIG`/`DASHBOARD`/relatórios
   agregados.

## Cards do Dashboard

Total de cotações, total de itens cotados, ganhos, perdidos, não cotados,
itens para revisar, itens críticos perdidos, correlações de baixa
confiança, valor total cotado, valor total ganho, diferença de valor,
% itens ganhos, % não cotado.

## Cores MedBox

Vermelho `#D80024` · Azul-marinho `#00486C` · Azul escuro `#003B5C` ·
Cinza claro `#F4F7FA`.

## Como publicar

1. Crie uma planilha Google Sheets nova (ou use uma existente).
2. Extensões → Apps Script.
3. Copie o conteúdo de cada `.gs` (e `appsscript.json`, via ícone de
   engrenagem → "Mostrar arquivo de manifesto") para arquivos de mesmo
   nome no editor do Apps Script.
4. Salve e recarregue a planilha — o menu **MEDBOX** aparece na barra.
5. Rode **MEDBOX > Preparar Planilha** antes de importar qualquer CSV.

## Limitações desta primeira versão

- A importação depende de o usuário enviar os CSVs para uma pasta do
  Google Drive manualmente (não há upload direto do disco local do robô
  Python — isso exigiria uma integração adicional, ex. Google Drive API
  a partir do Python, fora do escopo desta etapa).
- Não há gatilho automático (`onEdit`/tempo) configurado — todas as ações
  são disparadas pelo menu MEDBOX.
