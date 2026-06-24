$arquivo = "HANDOFF_CODEX_PARA_CLAUDE.txt"

"===== HANDOFF CODEX PARA CLAUDE =====" | Set-Content $arquivo -Encoding UTF8
"Data/Hora: $(Get-Date)" | Add-Content $arquivo
"Diretorio: $(Get-Location)" | Add-Content $arquivo
"Branch: $(git branch --show-current)" | Add-Content $arquivo
"" | Add-Content $arquivo

"===== CHECKPOINT.md =====" | Add-Content $arquivo
if (Test-Path ".\CHECKPOINT.md") {
    Get-Content ".\CHECKPOINT.md" | Add-Content $arquivo
} else {
    "CHECKPOINT.md nao encontrado" | Add-Content $arquivo
}
"" | Add-Content $arquivo

"===== GIT STATUS SHORT =====" | Add-Content $arquivo
git status --short 2>&1 | Add-Content $arquivo
"" | Add-Content $arquivo

"===== GIT DIFF STAT =====" | Add-Content $arquivo
git diff --stat 2>&1 | Add-Content $arquivo
"" | Add-Content $arquivo

"===== GIT DIFF COMPLETO =====" | Add-Content $arquivo
git diff 2>&1 | Add-Content $arquivo
"" | Add-Content $arquivo

"===== ULTIMOS COMMITS =====" | Add-Content $arquivo
git log --oneline --decorate -10 2>&1 | Add-Content $arquivo
"" | Add-Content $arquivo

"===== INSTRUCAO PARA CLAUDE CODE =====" | Add-Content $arquivo
@"
Projeto: MEDBOX_V3_ZERO.

Continue uma tarefa interrompida pelo Codex CLI.

Antes de alterar qualquer coisa:
1. Leia AGENTS.md, CLAUDE.md, RETOMAR.md, CHECKPOINT.md e este arquivo HANDOFF_CODEX_PARA_CLAUDE.txt.
2. Rode git status.
3. Analise o git diff atual.
4. Nao sobrescreva alteracoes existentes sem entender.
5. Nao altere banco.
6. Nao altere descricao_original.
7. Nao altere historico de precos.
8. Nao faca commit.

Continue exatamente do ponto registrado no CHECKPOINT.md e no diff atual.

Ao final:
- Atualize CHECKPOINT.md.
- Informe arquivos alterados.
- Informe testes executados.
- Informe riscos.
- Nao faca commit.
"@ | Add-Content $arquivo

Write-Host "Handoff gerado em: $arquivo"
notepad ".\$arquivo"
