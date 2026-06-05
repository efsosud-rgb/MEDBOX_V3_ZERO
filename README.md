# MedBox V3 — Sistema de Inteligência de Compras

## Visão Geral
Sistema Flask de inteligência de compras para distribuidora médica.
Permite importar tabelas de preços de fornecedores, padronizar produtos e comparar preços.

## Stack
- Python 3.14 + Flask
- SQLite (banco/medbox_v3.db)
- Ollama (llama3.2) para padronização de SKU_MASTER
- pdfplumber, openpyxl, python-docx, pytesseract (Tesseract instalado em C:\Program Files\Tesseract-OCR)

## Estrutura do Projeto
MEDBOX_V3_ZERO/
├── app.py
├── padronizar_skus.py
├── corrigir_marcas.py
├── banco/
│   └── medbox_v3.db
├── core/
│   ├── banco.py
│   ├── importador_sku.py
│   ├── importador_cotacao.py
│   └── importador_universal.py
├── templates/
│   ├── base.html
│   ├── dashboard.html
│   ├── busca.html
│   ├── fornecedores.html
│   ├── cotacoes.html
│   ├── equivalencias.html
│   ├── importacoes.html
│   ├── produtos.html
│   └── placeholder.html
├── static/
│   └── style.css
└── uploads/

## Banco de Dados — Tabelas
produtos (id, sku, produto_padrao, fabricante, categoria, ativo)
fornecedores (id, nome, tipo, contato, email, telefone, ativo)
precos_fornecedores (id, fornecedor_id, produto_id, descricao_original, codigo_fornecedor, marca, preco, data_importacao)
equivalencias (id, produto_id, descricao_equivalente)
cotacoes (id, fornecedor_id, data_importacao, arquivo_origem, total_itens)
sinonimos (id, termo, significado)

## Módulos Implementados
- Dashboard com cards de resumo e ações rápidas
- Busca Inteligente — busca por SKU, marca, categoria, fornecedor, descrição, medidas
- Variações de busca: "40x12" acha "12x40", "40 X 12", etc.
- Fornecedores — cadastro e exclusão
- Importações — aceita PDF, Excel, Word, CSV, TXT, Imagem (JPG/PNG)
- Importador Universal — detecta colunas automaticamente
- Extração automática de marca da descrição do produto
- Padronização SKU_MASTER: regras rápidas + Ollama llama3.2
- Equivalências — vincula descrições alternativas ao SKU Master
- Cotações — histórico de importações com tendência de preço
- Layout 2 colunas na busca (lista esquerda, detalhes direita)
- Tendência de preço (subiu/baixou nas últimas 3 cotações)

## Módulos Em Construção
- Histórico de Preços (gráfico)
- Relatórios
- Configurações

## Regras de Negócio Importantes
1. Marca:
   - Fabricante: marca = nome do fabricante
   - Distribuidor: marca = extraída da descrição (última palavra significativa após unidade)
   - Se não encontrar: "DESCONHECIDA"
2. SKU_MASTER: nome padronizado sem marca, fabricante, origem, localização
3. Preço: sempre o mais recente por fornecedor
4. Busca: retorna os 10 produtos mais baratos que correspondem ao termo
5. MATRIZ GO / MATRIX GO: localização da distribuidora, sempre ignorar
6. BC SUTURE, BIOCLOSE, BIOPDO: sublinhas da BIOLINE, remover do SKU_MASTER

## Comandos Úteis
Iniciar sistema:
python app.py

Padronizar SKU_MASTER (só regras, instantâneo):
python padronizar_skus.py --rapido

Padronizar SKU_MASTER (regras + IA Ollama):
python padronizar_skus.py

Corrigir marcas de distribuidores:
python corrigir_marcas.py

## Estado Atual (03/06/2026)
- 187 produtos importados (tabela Especifarma — fios cirúrgicos BIOLINE)
- 1 fornecedor ativo: ESPECIFARMA (Distribuidor)
- SKU_MASTERs padronizados com regras + Ollama llama3.2
- Busca inteligente funcionando com variações de medidas

## Próximos Passos
1. Importar mais tabelas de fornecedores para ter comparação de preços real
2. Implementar gráfico de histórico de preços
3. Implementar Relatórios
4. Melhorar extração de marca para novos formatos de tabela
5. Adicionar painel de detalhes do produto na busca
6. Implementar Configurações

## Observações Técnicas
- Ollama deve estar rodando antes de usar padronizar_skus.py sem --rapido
- Tesseract instalado em C:\Program Files\Tesseract-OCR\tesseract.exe
- Sistema roda em http://127.0.0.1:5000
- Debug mode ativo (não usar em produção)