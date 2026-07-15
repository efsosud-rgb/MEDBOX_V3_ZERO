$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path

if ($RepoRoot -like "*OneDrive*") {
    throw "Este repositório está dentro do OneDrive. Use um clone limpo em C:\dev\MEDBOX_V3_ZERO."
}

function Require-Command {
    param([Parameter(Mandatory = $true)][string]$Name)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Ferramenta obrigatória ausente: $Name"
    }
}

Set-Location $RepoRoot

Require-Command "git"
Require-Command "py"
Require-Command "node"
Require-Command "npm"

if (Get-Command code -ErrorAction SilentlyContinue) {
    $extensions = @(
        "ms-python.python",
        "ms-python.vscode-pylance",
        "charliermarsh.ruff",
        "github.vscode-pull-request-github",
        "usernamehw.errorlens",
        "editorconfig.editorconfig"
    )

    foreach ($extension in $extensions) {
        & code --install-extension $extension --force | Out-Host
        if ($LASTEXITCODE -ne 0) {
            throw "Falha ao instalar extensão VS Code: $extension"
        }
    }
} else {
    Write-Warning "VS Code não foi localizado no PATH; as extensões não foram instaladas."
}

if (-not (Test-Path ".venv")) {
    py -3.13 -m venv .venv
    if ($LASTEXITCODE -ne 0) {
        py -m venv .venv
    }
}

$Python = ".\.venv\Scripts\python.exe"
$PreCommit = ".\.venv\Scripts\pre-commit.exe"
$Ruff = ".\.venv\Scripts\ruff.exe"

& $Python -m pip install --upgrade pip
& $Python -m pip install --prefer-binary -r requirements.txt -r requirements-dev.txt
& $PreCommit install
& $Python scripts\ci\check_repo_safety.py
& $Python scripts\ci\check_test_db_isolation.py
& $Python -m compileall -q app.py core tests scripts
& $Ruff check app.py core tests scripts --select E9,F63,F7,F82
& $Python -m pytest -q
& node tests\lances_recalculo_dinamico_test.js

Write-Host "" 
Write-Host "Ambiente MEDBOX configurado e validado em: $RepoRoot" -ForegroundColor Green
Write-Host "Python:" -ForegroundColor Cyan
& $Python --version
Write-Host "Node:" -ForegroundColor Cyan
& node --version
Write-Host "Git:" -ForegroundColor Cyan
& git --version
