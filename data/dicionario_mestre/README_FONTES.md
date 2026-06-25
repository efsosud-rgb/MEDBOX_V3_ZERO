# Dicionario Mestre MEDBOX - Fontes e Regras

1. O Dicionario Mestre MEDBOX sera a fonte oficial de padronizacao.
2. O dicionario sera hibrido: fontes internas validadas + fontes externas oficiais e tecnicas.
3. Nenhuma descricao sera inventada.
4. Toda linha precisa ter `fonte_tipo`, `fonte_nome`, `fonte_origem` e `confianca`.
5. Quando fonte interna e externa concordarem, a confianca tende a ser `ALTA`.
6. Quando houver divergencia, `status_revisao` deve ficar `PENDENTE_REVISAO`.
7. Fornecedor nunca deve ser tratado como fabricante.
8. `descricao_original` nunca sera substituida.
9. O dicionario so sugere `SKU_MASTER`; aplicacao no banco exige dry-run, backup, auditoria e aprovacao.
10. O campo de custo/valor unitario devera vir de tabela de preco rastreavel, nunca de inferencia.
11. O futuro robô devera consultar o Dicionario Mestre antes de propor `SKU_MASTER`, fabricante, categoria ou custo.

Este repositorio inicia apenas a estrutura local e os arquivos planejados.
Nenhum dado externo foi coletado nesta etapa.
