# MEDBOX_V3_ZERO - Regras para agentes de IA

Este repositório é o sistema MEDBOX_V3_ZERO, desenvolvido em Python/Flask com banco SQLite.

O sistema controla:
- SKU Master
- produtos de fornecedores
- importação de tabelas de fornecedores
- importação de XML/NF-e
- auditoria SKU
- busca inteligente
- crítica de cotação
- cotações de clientes
- histórico de preços

## Diretrizes obrigatórias

Ao trabalhar neste repositório, seja conservador.

Nunca:
- reescreva o sistema do zero;
- altere a branch principal diretamente;
- faça merge automático;
- apague funções existentes;
- apague dados;
- altere banco de dados sem migração explícita;
- mude nomes de tabelas ou colunas sem justificativa técnica;
- altere muitos arquivos para uma correção simples;
- altere módulos fora do escopo da tarefa.

## Arquivos críticos

Tenha cuidado extremo ao alterar:
- app.py
- core/banco.py
- core/importador_universal.py
- core/busca_inteligente.py
- core/reconstruir_sku_master.py
- banco/medbox_v3.db
- templates relacionados a Auditoria SKU, importações, busca e cotações

## Regras para Pull Requests

Todo PR deve:
- ser pequeno;
- ter objetivo claro;
- alterar somente os arquivos necessários;
- explicar todos os arquivos alterados;
- informar como testar;
- preservar funcionalidades existentes;
- preservar dados e histórico;
- não fazer merge automaticamente.

## Critérios de bloqueio

Alerte como risco alto se o PR:
- alterar banco.py sem necessidade clara;
- alterar estrutura de banco, tabelas ou colunas sem migração segura;
- apagar funções existentes;
- alterar rotas Flask fora do escopo;
- alterar importador_universal.py fora de tarefa específica;
- alterar busca_inteligente.py fora de tarefa específica;
- afetar Auditoria SKU sem pedido explícito;
- alterar muitos arquivos para uma correção simples;
- apagar histórico, preços, fornecedores, produtos ou SKU Master;
- criar risco de duplicidade de produtos;
- quebrar compatibilidade com o banco existente.

## Prioridades

1. Preservar dados.
2. Preservar funcionalidades existentes.
3. Manter PRs pequenos.
4. Apontar arquivos fora do escopo.
5. Recomendar merge somente se o PR estiver seguro.
6. Nunca aceitar alteração grande sem explicação técnica.
