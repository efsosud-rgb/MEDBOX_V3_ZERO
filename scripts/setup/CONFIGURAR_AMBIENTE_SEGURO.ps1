$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path

if ($RepoRoot -like "*OneDrive*") {
    throw "Este repositório está dentro do OneDrive. Use um clone limpo em C:\dev\MEDBOX_V3_ZERO."
}

Set-Location $RepoRoot
if (-not (Test-Path ".venv")) { py -m venv .venv }
& ".\.venv\Scripts\python.exe" -m pip install --upgrade pip
& ".\.venv\Scripts\python.exe" -m pip install --prefer-binary -r requirements.txt -r requirements-dev.txt
& ".\.venv\Scripts\pre-commit.exe" install
& ".\.venv\Scripts\python.exe" scripts\ci\check_repo_safety.py
& ".\.venv\Scripts\python.exe" -m compileall -q app.py core tests scripts
& ".\.venv\Scripts\ruff.exe" check app.py core tests scripts --select E9,F63,F7,F82
& ".\.venv\Scripts\python.exe" -m pytest -q
Write-Host "Ambiente MEDBOX configurado em: $RepoRoot" -ForegroundColor Green
