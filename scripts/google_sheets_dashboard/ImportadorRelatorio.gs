/**
 * ImportadorRelatorio.gs — importa os CSVs gerados pelo robô Python
 * (data/gmail_cotacoes/relatorios/csv/*.csv) para as abas correspondentes.
 *
 * Fluxo: faça upload dos CSVs para uma pasta do Google Drive, informe o
 * nome da pasta quando solicitado. Cada arquivo "<NOME_DA_ABA>.csv" é
 * importado para a aba de mesmo nome (ex.: RELATORIO_COTACOES.csv ->
 * aba RELATORIO_COTACOES).
 */

var MEDBOX_CSVS_IMPORTAVEIS = [
  MEDBOX_ABAS.EMAILS_COTACOES, MEDBOX_ABAS.EMAILS_PEDIDOS,
  MEDBOX_ABAS.ITENS_COTADOS, MEDBOX_ABAS.ITENS_PEDIDOS,
  MEDBOX_ABAS.CRUZAMENTO_ITENS, MEDBOX_ABAS.RELATORIO_COTACOES,
  MEDBOX_ABAS.ITENS_CRITICOS_PERDIDOS, MEDBOX_ABAS.ITENS_REVISAR,
  MEDBOX_ABAS.DASHBOARD_BASE,
];

function medboxImportarRelatorioCsv() {
  var ui = SpreadsheetApp.getUi();
  var resposta = ui.prompt(
    'Importar Relatório CSV',
    'Nome da pasta do Google Drive onde os CSVs foram enviados (ex.: relatorio_hmar_1006_real):',
    ui.ButtonSet.OK_CANCEL
  );
  if (resposta.getSelectedButton() !== ui.Button.OK) return;

  var nomePasta = resposta.getResponseText().trim();
  var pastas = DriveApp.getFoldersByName(nomePasta);
  if (!pastas.hasNext()) {
    ui.alert('Pasta "' + nomePasta + '" não encontrada no Google Drive.');
    return;
  }
  var pasta = pastas.next();

  var importados = [];
  var naoEncontrados = [];

  MEDBOX_CSVS_IMPORTAVEIS.forEach(function (nomeAba) {
    var nomeArquivo = nomeAba + '.csv';
    var arquivos = pasta.getFilesByName(nomeArquivo);
    if (!arquivos.hasNext()) {
      naoEncontrados.push(nomeArquivo);
      return;
    }
    var arquivo = arquivos.next();
    var conteudo = arquivo.getBlob().getDataAsString('UTF-8');
    var linhas = Utilities.parseCsv(conteudo);
    if (linhas.length === 0) return;

    var aba = medboxGetOuCriarAba_(nomeAba);
    aba.clearContents();
    aba.getRange(1, 1, linhas.length, linhas[0].length).setValues(linhas);
    medboxFormatarCabecalho_(aba, linhas[0]);
    importados.push(nomeArquivo + ' (' + (linhas.length - 1) + ' linha(s))');
  });

  var msg = importados.length ? 'Importado:\n' + importados.join('\n') : 'Nenhum CSV importado.';
  if (naoEncontrados.length) {
    msg += '\n\nNão encontrados na pasta:\n' + naoEncontrados.join('\n');
  }
  ui.alert('Importar Relatório CSV', msg, ui.ButtonSet.OK);
}
