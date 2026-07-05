/**
 * Dashboard.gs — cards de resumo (aba DASHBOARD) e relatórios agregados
 * (RELATORIO_CLIENTES, RELATORIO_RESPONSAVEIS, RELATORIO_RESPOSTAS,
 * ACOMPANHAMENTO), a partir dos dados importados em DASHBOARD_BASE,
 * RELATORIO_COTACOES e ITENS_CRITICOS_PERDIDOS.
 */

function medboxLerAbaComoObjetos_(nomeAba) {
  var aba = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(nomeAba);
  if (!aba || aba.getLastRow() < 2) return [];
  var dados = aba.getRange(1, 1, aba.getLastRow(), aba.getLastColumn()).getValues();
  var cabecalho = dados[0];
  return dados.slice(1).map(function (linha) {
    var obj = {};
    cabecalho.forEach(function (chave, i) { obj[chave] = linha[i]; });
    return obj;
  });
}

/** Menu: MEDBOX > Atualizar Dashboard */
function medboxAtualizarDashboard() {
  var base = medboxLerAbaComoObjetos_(MEDBOX_ABAS.DASHBOARD_BASE);
  var criticos = medboxLerAbaComoObjetos_(MEDBOX_ABAS.ITENS_CRITICOS_PERDIDOS);
  var revisar = medboxLerAbaComoObjetos_(MEDBOX_ABAS.ITENS_REVISAR);

  var consolidado = base[0] || {};
  var totalItensRevisar = consolidado.TOTAL_ITENS_REVISAR != null ? consolidado.TOTAL_ITENS_REVISAR : revisar.length;

  var cards = [
    { label: 'Total de Cotações', valor: consolidado.TOTAL_COTACOES || 0, cor: MEDBOX_CORES.AZUL_MARINHO },
    { label: 'Itens Cotados', valor: consolidado.TOTAL_ITENS_COTADOS || 0, cor: MEDBOX_CORES.AZUL_MARINHO },
    { label: 'Itens Ganhos', valor: consolidado.TOTAL_ITENS_GANHOS || 0, cor: MEDBOX_CORES.AZUL_ESCURO },
    { label: 'Itens Perdidos', valor: consolidado.TOTAL_ITENS_PERDIDOS || 0, cor: MEDBOX_CORES.VERMELHO },
    { label: 'Itens Não Cotados', valor: consolidado.TOTAL_ITENS_NAO_COTADOS || 0, cor: MEDBOX_CORES.AZUL_ESCURO },
    { label: 'Itens para Revisar', valor: totalItensRevisar, cor: MEDBOX_CORES.VERMELHO },
    { label: 'Itens Críticos Perdidos', valor: criticos.length, cor: MEDBOX_CORES.VERMELHO },
    { label: 'Correlações Baixa Confiança', valor: consolidado.CORRELACOES_BAIXA_CONFIANCA || 0, cor: MEDBOX_CORES.VERMELHO },
    { label: 'Valor Total Cotado', valor: consolidado.VALOR_TOTAL_COTADO || 0, cor: MEDBOX_CORES.AZUL_MARINHO, moeda: true },
    { label: 'Valor Total Ganho', valor: consolidado.VALOR_TOTAL_GANHO || 0, cor: MEDBOX_CORES.AZUL_ESCURO, moeda: true },
    { label: 'Diferença de Valor', valor: consolidado.DIFERENCA_VALOR || 0, cor: MEDBOX_CORES.VERMELHO, moeda: true },
    { label: '% Itens Ganhos', valor: (consolidado.PERC_ITENS_GANHOS || 0) + '%', cor: MEDBOX_CORES.AZUL_ESCURO },
    { label: '% Itens Não Cotados', valor: (consolidado.PERC_ITENS_NAO_COTADOS || 0) + '%', cor: MEDBOX_CORES.AZUL_ESCURO },
  ];

  var aba = medboxGetOuCriarAba_(MEDBOX_ABAS.DASHBOARD);
  aba.clear();
  aba.setTabColor(MEDBOX_CORES.VERMELHO);

  var titulo = aba.getRange('A1:D1').merge();
  titulo.setValue('DASHBOARD — ROBÔ GMAIL COTAÇÕES MEDBOX');
  titulo.setFontSize(16).setFontWeight('bold').setFontColor(MEDBOX_CORES.BRANCO).setBackground(MEDBOX_CORES.VERMELHO);

  var colunas = 4;
  cards.forEach(function (card, i) {
    var linha = 3 + Math.floor(i / colunas) * 3;
    var coluna = 1 + (i % colunas) * 2;

    var celulaLabel = aba.getRange(linha, coluna, 1, 2).merge();
    celulaLabel.setValue(card.label);
    celulaLabel.setFontColor(MEDBOX_CORES.BRANCO).setBackground(card.cor).setFontWeight('bold').setHorizontalAlignment('center');

    var celulaValor = aba.getRange(linha + 1, coluna, 1, 2).merge();
    celulaValor.setValue(card.valor);
    celulaValor.setFontSize(18).setFontWeight('bold').setBackground(MEDBOX_CORES.CINZA_CLARO).setHorizontalAlignment('center');
    if (card.moeda) celulaValor.setNumberFormat('R$ #,##0.00');
  });

  for (var c = 1; c <= colunas * 2; c++) aba.setColumnWidth(c, 130);

  SpreadsheetApp.getUi().alert('Dashboard atualizado com ' + cards.length + ' cards.');
}

function medboxAgrupar_(linhas, chave, agregadores) {
  var grupos = {};
  linhas.forEach(function (linha) {
    var k = linha[chave] || '(sem valor)';
    if (!grupos[k]) {
      grupos[k] = {};
      Object.keys(agregadores).forEach(function (campo) { grupos[k][campo] = 0; });
      grupos[k][chave] = k;
    }
    Object.keys(agregadores).forEach(function (campo) {
      grupos[k][campo] += Number(linha[agregadores[campo]] || 0);
    });
  });
  return Object.keys(grupos).map(function (k) { return grupos[k]; });
}

function medboxEscreverTabela_(nomeAba, cabecalho, linhasObjeto) {
  var aba = medboxGetOuCriarAba_(nomeAba);
  aba.clearContents();
  var linhas = linhasObjeto.map(function (obj) {
    return cabecalho.map(function (campo) { return obj[campo] != null ? obj[campo] : ''; });
  });
  aba.getRange(1, 1, 1, cabecalho.length).setValues([cabecalho]);
  if (linhas.length) aba.getRange(2, 1, linhas.length, cabecalho.length).setValues(linhas);
  medboxFormatarCabecalho_(aba, cabecalho);
}

/** Menu: MEDBOX > Atualizar Relatórios (RELATORIO_CLIENTES, RELATORIO_RESPONSAVEIS, RELATORIO_RESPOSTAS, ACOMPANHAMENTO) */
function medboxAtualizarRelatorios() {
  var cotacoes = medboxLerAbaComoObjetos_(MEDBOX_ABAS.RELATORIO_COTACOES);

  var agregador = {
    TOTAL_ITENS_COTADOS: 'TOTAL_ITENS_COTADOS',
    TOTAL_ITENS_GANHOS: 'TOTAL_ITENS_GANHOS',
    TOTAL_ITENS_PERDIDOS: 'TOTAL_ITENS_PERDIDOS',
    TOTAL_ITENS_NAO_COTADOS: 'TOTAL_ITENS_NAO_COTADOS',
    VALOR_TOTAL_COTACAO: 'VALOR_TOTAL_COTACAO',
    VALOR_TOTAL_GANHO: 'VALOR_TOTAL_GANHO',
  };

  var porCliente = medboxAgrupar_(cotacoes, 'CLIENTE', agregador);
  medboxEscreverTabela_(MEDBOX_ABAS.RELATORIO_CLIENTES, ['CLIENTE'].concat(Object.keys(agregador)), porCliente);

  var porVendedora = medboxAgrupar_(cotacoes, 'VENDEDORA', agregador);
  medboxEscreverTabela_(MEDBOX_ABAS.RELATORIO_RESPONSAVEIS, ['VENDEDORA'].concat(Object.keys(agregador)), porVendedora);

  var contagemConfianca = {};
  cotacoes.forEach(function (c) {
    var k = c.CONFIANCA_CORRELACAO_EMAIL || '(sem valor)';
    contagemConfianca[k] = (contagemConfianca[k] || 0) + 1;
  });
  var linhasRespostas = Object.keys(contagemConfianca).map(function (k) {
    return { CONFIANCA_CORRELACAO_EMAIL: k, TOTAL_COTACOES: contagemConfianca[k] };
  });
  medboxEscreverTabela_(MEDBOX_ABAS.RELATORIO_RESPOSTAS, ['CONFIANCA_CORRELACAO_EMAIL', 'TOTAL_COTACOES'], linhasRespostas);

  medboxEscreverTabela_(MEDBOX_ABAS.ACOMPANHAMENTO, [
    'VENDEDORA', 'CLIENTE', 'COTACAO', 'CONFIANCA_CORRELACAO_EMAIL',
    'TOTAL_ITENS_REVISAR', 'PERC_ITENS_GANHOS', 'PERC_DIFERENCA',
  ], cotacoes);

  medboxAtualizarDashboard();
  SpreadsheetApp.getUi().alert('Relatórios (Clientes, Responsáveis, Respostas, Acompanhamento) atualizados.');
}
