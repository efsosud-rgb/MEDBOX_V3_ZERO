import tkinter as tk
from tkinter import filedialog, messagebox
import pandas as pd
import sqlite3
from pathlib import Path
import os
import time

# Manipulação direta da planilha mantendo layout idêntico
import openpyxl
from openpyxl.drawing.image import Image

# Automação nativa do Office para exportação estável em PDF
import comtypes.client

# ============================================================
# CONFIGURAÇÃO DO AMBIENTE (MEDBOX V3)
# ============================================================
PASTA_RAIZ   = Path(__file__).parent.resolve()
DB_PATH      = PASTA_RAIZ / "banco" / "medbox_v3.db"
PASTA_SAIDA  = PASTA_RAIZ / "cotacoes_emitidas"
LOGO_PATH    = PASTA_RAIZ / "unnamed.jpg.jpeg"

PASTA_SAIDA.mkdir(exist_ok=True)

# ============================================================
# CONSULTA INTELIGENTE E RESILIENTE DE PREÇOS
# ============================================================
def buscar_preco_produto_no_banco(codigo_produto):
    """Busca o preço de forma segura aceitando códigos decimais, textos ou inteiros."""
    if codigo_produto is None or pd.isna(codigo_produto):
        return 0.0
        
    try:
        # Limpa o código tirando espaços e formatações flutuantes indesejadas (ex: '2.77')
        cod_str = str(codigo_produto).strip()
        if '.' in cod_str and cod_str.replace('.', '', 1).isdigit():
            # Se for algo como 123.0, limpa para 123
            if cod_str.endswith('.0'):
                cod_str = cod_str.split('.')[0]

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # 1. Tenta buscar o preço ativo na tabela principal
        c.execute("SELECT MIN(preco) FROM precos_fornecedores WHERE produto_id = ?", (cod_str,))
        res = c.fetchone()[0]
        
        # 2. Se não localizar, busca no histórico retrospectivo
        if res is None:
            c.execute("SELECT MIN(preco) FROM precos_fornecedores_historico WHERE produto_id = ?", (cod_str,))
            res = c.fetchone()[0]
            
        conn.close()
        return float(res) if res is not None else 0.0
    except Exception:
        return 0.0

# ============================================================
# EXPORTADOR NATIVO DE PDF (PRESERVAÇÃO DO DESIGN ORIGINAL)
# ============================================================
def converter_excel_para_pdf(caminho_excel, caminho_pdf):
    excel_app = None
    try:
        comtypes.CoInitialize()
        excel_app = comtypes.client.CreateObject("Excel.Application")
        excel_app.Visible = False
        excel_app.DisplayAlerts = False
        
        wb = excel_app.Workbooks.Open(str(caminho_excel.resolve()))
        
        # Configura as abas para caber todas as colunas nativas na largura de uma página A4
        for ws in wb.Worksheets:
            ws.PageSetup.Orientation = 2 # 2 = Modo Paisagem (Horizontal)
            ws.PageSetup.Zoom = False
            ws.PageSetup.FitToPagesWide = 1
            ws.PageSetup.FitToPagesTall = False
            
        wb.ExportAsFixedFormat(0, str(caminho_pdf.resolve()))
        wb.Close(False)
    except Exception as e:
        raise RuntimeError(f"Erro na conversão para PDF: {e}")
    finally:
        if excel_app:
            excel_app.Quit()
        comtypes.CoUninitialize()

# ============================================================
# FLUXO CENTRAL DE TRATAMENTO E ATUALIZAÇÃO DA PLANILHA
# ============================================================
def processar_e_gerar_pdf_final(caminho_entrada, label_status):
    try:
        label_status.config(text="Carregando planilha nativa...", fg="#ffc107")
        label_status.update()
        
        # Abre usando openpyxl para garantir que as colunas originais permaneçam estáticas
        wb = openpyxl.load_workbook(caminho_entrada)
        
        nome_aba = "ITENS_ORCAMENTO" if "ITENS_ORCAMENTO" in wb.sheetnames else wb.sheetnames[0]
        ws = wb[nome_aba]
        
        # Mapeia os índices das colunas reais do cabeçalho
        headers = [str(cell.value).strip().upper() for cell in ws[1]]
        
        if "PRODUTO" not in headers:
            raise ValueError("Coluna 'PRODUTO' com o código chave não foi localizada no cabeçalho.")
            
        col_produto = headers.index("PRODUTO") + 1
        
        # Identifica ou cria dinamicamente as colunas comerciais de fechamento se não existirem
        col_preco = headers.index("PREÇO UNITÁRIO") + 1 if "PREÇO UNITÁRIO" in headers else None
        col_total = headers.index("VALOR TOTAL") + 1 if "VALOR TOTAL" in headers else None
        col_qtd   = headers.index("QUANTIDADE SOLICITADA") + 1 if "QUANTIDADE SOLICITADA" in headers else None

        # Fallbacks de segurança se o ERP não exportou as colunas em branco
        if not col_preco:
            ws.cell(row=1, column=ws.max_column + 1, value="PREÇO UNITÁRIO")
            col_preco = ws.max_column
        if not col_total:
            ws.cell(row=1, column=ws.max_column + 1, value="VALOR TOTAL")
            col_total = ws.max_column
        if not col_qtd:
            ws.cell(row=1, column=ws.max_column + 1, value="QUANTIDADE SOLICITADA")
            col_qtd = ws.max_column

        label_status.config(text="Preenchendo preços automáticos...", fg="#ffc107")
        label_status.update()

        total_itens_precificados = 0
        
        # Varre linha por linha fazendo o cruzamento resiliente
        for linha in range(2, ws.max_row + 1):
            cod_prod = ws.cell(row=linha, column=col_produto).value
            if cod_prod is None:
                continue
                
            preco_real = buscar_preco_produto_no_banco(cod_prod)
            
            if preco_real > 0:
                cell_p = ws.cell(row=linha, column=col_preco, value=preco_real)
                cell_p.number_format = 'R$ #,##0.00'
                
                qtd_val = ws.cell(row=linha, column=col_qtd).value
                try:
                    qtd = float(qtd_val) if qtd_val else 1.0
                except (ValueError, TypeError):
                    qtd = 1.0
                    
                cell_t = ws.cell(row=linha, column=col_total, value=preco_real * qtd)
                cell_t.number_format = 'R$ #,##0.00'
                
                total_itens_precificados += 1

        # Injeta a logo corporativa na aba principal do arquivo
        if LOGO_PATH.exists():
            try:
                aba_dados = wb["DADOS"] if "DADOS" in wb.sheetnames else wb.worksheets[0]
                img = Image(str(LOGO_PATH))
                img.width = 150
                img.height = 50
                aba_dados.add_image(img, "A1")
            except:
                pass

        timestamp = time.strftime("%Y%m%d_%H%M%S")
        excel_tmp = PASTA_SAIDA / f"Planilha_Preenchida_{timestamp}.xlsx"
        pdf_final = PASTA_SAIDA / f"Orcamento_MedBox_{timestamp}.pdf"
        
        wb.save(excel_tmp)

        label_status.config(text="Exportando para PDF uniforme...", fg="#ffc107")
        label_status.update()

        # Converte em PDF garantindo a uniformidade visual exata das colunas
        converter_excel_para_pdf(excel_tmp, pdf_final)
        
        if excel_tmp.exists():
            os.remove(excel_tmp)

        label_status.config(text=f"Concluído com Sucesso!", fg="#28a745")
        
        msg = f"Orçamento Processado!\n\nItens preenchidos com sucesso: {total_itens_precificados}\n\nDeseja visualizar o PDF oficial gerado?"
        if messagebox.askyesno("MedBox V3", msg):
            os.startfile(pdf_final)

    except Exception as e:
        messagebox.showerror("Erro de Processamento", f"Ocorreu um erro ao tratar os dados.\nDetalhes: {e}")
        label_status.config(text="Falha ao gerar orçamento.", fg="#dc3545")

# ============================================================
# INTERFACE GRÁFICA MÓDULO DE COTAÇÕES
# ============================================================
def abrir_aba_cotacoes(container_principal):
    for widget in container_principal.winfo_children():
        widget.destroy()
        
    frame_cotacoes = tk.Frame(container_principal, bg="#1e1e1e")
    frame_cotacoes.pack(fill="both", expand=True, padx=20, pady=20)
    
    tk.Label(
        frame_cotacoes, text="Módulo de Cotações de Clientes", 
        font=("Arial", 18, "bold"), bg="#1e1e1e", fg="#ffffff"
    ).pack(anchor="w", pady=(0, 5))
    
    tk.Label(
        frame_cotacoes, text="Insira a planilha original. O sistema preenche as colunas de Preço Unitário e Valor Total e exporta o PDF oficial.", 
        font=("Arial", 10), bg="#1e1e1e", fg="#aaaaaa"
    ).pack(anchor="w", pady=(0, 25))
    
    caixa_upload = tk.Frame(frame_cotacoes, bg="#2d2d2d", bd=2, relief="groove")
    caixa_upload.pack(fill="x", ipady=45, padx=5)
    
    tk.Label(
        caixa_upload, text="Selecione a planilha de orçamento (.xlsx)",
        font=("Arial", 12, "bold"), bg="#2d2d2d", fg="#ffffff"
    ).pack(pady=10)
    
    lbl_status = tk.Label(
        caixa_upload, text="Aguardando importação...",
        font=("Arial", 10), bg="#2d2d2d", fg="#aaaaaa"
    )
    
    def selecionar_arquivo_gatilho():
        tipos = [("Planilhas Excel", "*.xlsx")]
        arq = filedialog.askopenfilename(title="Selecionar Planilha do Cliente", filetypes=tipos)
        if arq:
            processar_e_gerar_pdf_final(Path(arq), lbl_status)

    btn_importar = tk.Button(
        caixa_upload, text="📁 Importar, Preencher e Emitir PDF",
        font=("Arial", 10, "bold"), bg="#28a745", fg="#ffffff",
        activebackground="#218838", activeforeground="#ffffff",
        cursor="hand2", bd=0, padx=25, pady=10,
        command=selecionar_arquivo_gatilho
    )
    btn_importar.pack()
    lbl_status.pack(pady=(15, 0))

if __name__ == "__main__":
    app = tk.Tk()
    app.title("MedBox V3 — Painel Operacional")
    app.geometry("900x550")
    app.configure(bg="#121212")
    
    menu_lateral = tk.Frame(app, bg="#1a1a1a", width=200)
    menu_lateral.pack(side="left", fill="y")
    menu_lateral.pack_propagate(False)
    
    painel_conteudo = tk.Frame(app, bg="#121212")
    painel_conteudo.pack(side="right", fill="both", expand=True)
    
    btn_menu = tk.Button(
        menu_lateral, text="📋 Cotações", font=("Arial", 11, "bold"),
        bg="#1a1a1a", fg="#ffffff", bd=0, anchor="w", padx=15, pady=12,
        cursor="hand2", command=lambda: abrir_aba_cotacoes(painel_conteudo)
    )
    btn_menu.pack(fill="x", pady=10)
    
    abrir_aba_cotacoes(painel_conteudo)
    app.mainloop()