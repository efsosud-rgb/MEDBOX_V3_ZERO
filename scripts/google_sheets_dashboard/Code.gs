/**
 * Code.gs — funções centrais de preparação e manutenção da planilha MEDBOX.
 */

var MEDBOX_TODAS_ABAS = [
  MEDBOX_ABAS.CONFIG, MEDBOX_ABAS.BASE_COTACOES,
  MEDBOX_ABAS.EMAILS_COTACOES, MEDBOX_ABAS.EMAILS_PEDIDOS,
  MEDBOX_ABAS.ITENS_COTADOS, MEDBOX_ABAS.ITENS_PEDIDOS,
  MEDBOX_ABAS.CRUZAMENTO_ITENS, MEDBOX_ABAS.RELATORIO_COTACOES,
  MEDBOX_ABAS.ITENS_CRITICOS_PERDIDOS, MEDBOX_ABAS.ITENS_REVISAR,
  MEDBOX_ABAS.DASHBOARD_BASE, MEDBOX_ABAS.DASHBOARD, MEDBOX_ABAS.ACOMPANHAMENTO,
  MEDBOX_ABAS.RELATORIO_CLIENTES, MEDBOX_ABAS.RELATORIO_RESPONSAVEIS,
  MEDBOX_ABAS.RELATORIO_RESPOSTAS,
];

// Abas com dados importados/gerados pelo robô — "Limpar Bases Geradas" some só com estas.
var MEDBOX_ABAS_GERADAS = [
  MEDBOX_ABAS.EMAILS_COTACOES, MEDBOX_ABAS.EMAILS_PEDIDOS,
  MEDBOX_ABAS.ITENS_COTADOS, MEDBOX_ABAS.ITENS_PEDIDOS,
  MEDBOX_ABAS.CRUZAMENTO_ITENS, MEDBOX_ABAS.RELATORIO_COTACOES,
  MEDBOX_ABAS.ITENS_CRITICOS_PERDIDOS, MEDBOX_ABAS.ITENS_REVISAR,
  MEDBOX_ABAS.DASHBOARD_BASE,
];

function medboxGetOuCriarAba_(nomeAba) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var aba = ss.getSheetByName(nomeAba);
  if (!aba) {
    aba = ss.insertSheet(nomeAba);
  }
  return aba;
}

function medboxFormatarCabecalho_(aba, cabecalhos) {
  if (!cabecalhos || cabecalhos.length === 0) return;
  var range = aba.getRange(1, 1, 1, cabecalhos.length);
  range.setValues([cabecalhos]);
  range.setFontWeight('bold');
  range.setFontColor(MEDBOX_CORES.BRANCO);
  range.setBackground(MEDBOX_CORES.AZUL_MARINHO);
  aba.setFrozenRows(1);
}

/** Menu: MEDBOX > Preparar Planilha */
function medboxPrepararPlanilha() {
  MEDBOX_TODAS_ABAS.forEach(function (nomeAba) {
    var aba = medboxGetOuCriarAba_(nomeAba);
    var cabecalhos = MEDBOX_CABECALHOS[nomeAba];
    if (cabecalhos && aba.getLastRow() === 0) {
      medboxFormatarCabecalho_(aba, cabecalhos);
    }
  });

  var abaConfig = medboxGetOuCriarAba_(MEDBOX_ABAS.CONFIG);
  if (abaConfig.getLastRow() === 0) {
    abaConfig.getRange('A1:B1').setValues([['Parâmetro', 'Valor']]);
    abaConfig.getRange('A1:B1').setFontWeight('bold').setBackground(MEDBOX_CORES.AZUL_ESCURO).setFontColor(MEDBOX_CORES.BRANCO);
    abaConfig.getRange('A2:B5').setValues([
      ['Vendedoras', 'JESSICA, STHEFANY, PAMELA, LAYANE'],
      ['Marcador Pedido', 'PEDIDO'],
      ['Valor crítico perdido (R$)', 2000],
      ['Última atualização', new Date()],
    ]);
  }

  SpreadsheetApp.getUi().alert('Planilha MEDBOX preparada: ' + MEDBOX_TODAS_ABAS.length + ' abas verificadas/criadas.');
}

/** Menu: MEDBOX > Verificar Estrutura */
function medboxVerificarEstrutura() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var faltando = MEDBOX_TODAS_ABAS.filter(function (nome) {
    return !ss.getSheetByName(nome);
  });

  var divergentes = [];
  Object.keys(MEDBOX_CABECALHOS).forEach(function (nomeAba) {
    var aba = ss.getSheetByName(nomeAba);
    if (!aba || aba.getLastRow() === 0) return;
    var cabecalhoAtual = aba.getRange(1, 1, 1, MEDBOX_CABECALHOS[nomeAba].length).getValues()[0];
    var esperado = MEDBOX_CABECALHOS[nomeAba];
    var igual = cabecalhoAtual.every(function (v, i) { return v === esperado[i]; });
    if (!igual) divergentes.push(nomeAba);
  });

  var msg = '';
  msg += faltando.length ? 'Abas faltando: ' + faltando.join(', ') + '\n' : 'Nenhuma aba faltando.\n';
  msg += divergentes.length ? 'Cabeçalhos divergentes: ' + divergentes.join(', ') : 'Todos os cabeçalhos conferem.';
  SpreadsheetApp.getUi().alert('Verificação de Estrutura MEDBOX', msg, SpreadsheetApp.getUi().ButtonSet.OK);
}

/** Menu: MEDBOX > Limpar Bases Geradas */
function medboxLimparBasesGeradas() {
  var ui = SpreadsheetApp.getUi();
  var resposta = ui.alert(
    'Confirmar limpeza',
    'Isso apaga os DADOS (mantendo o cabeçalho) das abas geradas pelo robô: ' + MEDBOX_ABAS_GERADAS.join(', ') + '.\n\nContinuar?',
    ui.ButtonSet.YES_NO
  );
  if (resposta !== ui.Button.YES) return;

  var ss = SpreadsheetApp.getActiveSpreadsheet();
  MEDBOX_ABAS_GERADAS.forEach(function (nomeAba) {
    var aba = ss.getSheetByName(nomeAba);
    if (!aba) return;
    var ultimaLinha = aba.getLastRow();
    if (ultimaLinha > 1) {
      aba.getRange(2, 1, ultimaLinha - 1, aba.getLastColumn()).clearContent();
    }
  });
  ui.alert('Bases geradas limpas.');
}
