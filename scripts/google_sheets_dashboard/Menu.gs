/**
 * Menu.gs — menu MEDBOX na barra do Google Sheets.
 */

function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('MEDBOX')
    .addItem('Preparar Planilha', 'medboxPrepararPlanilha')
    .addItem('Importar Relatório CSV', 'medboxImportarRelatorioCsv')
    .addItem('Atualizar Dashboard', 'medboxAtualizarDashboard')
    .addItem('Atualizar Relatórios', 'medboxAtualizarRelatorios')
    .addItem('Verificar Estrutura', 'medboxVerificarEstrutura')
    .addSeparator()
    .addItem('Limpar Bases Geradas', 'medboxLimparBasesGeradas')
    .addToUi();
}
