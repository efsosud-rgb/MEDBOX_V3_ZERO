from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BLOCKED_SUFFIXES = {".db", ".sqlite", ".sqlite3", ".p12", ".pfx", ".pem", ".key", ".pickle"}
BLOCKED_NAMES = {".env", "credentials.json", "token.json", "token_gmail.json", "token_sheets.json"}
BLOCKED_PREFIXES = ("uploads/", "banco/backups/", "data/gmail_cotacoes/", "data/dashboard_comercial/", "logs/")
SECRET_PATTERNS = {
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "GitHub token": re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b"),
    "Google API key": re.compile(r"\bAIza[0-9A-Za-z_-]{30,}\b"),
}
TEXT_SUFFIXES = {".py", ".js", ".html", ".css", ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".md", ".txt", ".ps1", ".sh"}


def tracked_files() -> list[str]:
    result = subprocess.run(["git", "ls-files"], cwd=ROOT, check=True, capture_output=True, text=True, encoding="utf-8")
    return [line.strip().replace("\\", "/") for line in result.stdout.splitlines() if line.strip()]


def main() -> int:
    violations: list[str] = []
    for relative in tracked_files():
        path = ROOT / relative
        normalized = relative.lower()
        if path.name.lower() in BLOCKED_NAMES:
            violations.append(f"arquivo sensível rastreado: {relative}")
        if path.suffix.lower() in BLOCKED_SUFFIXES:
            violations.append(f"extensão proibida rastreada: {relative}")
        if normalized.startswith(BLOCKED_PREFIXES):
            violations.append(f"diretório de dados reais rastreado: {relative}")
        if path.suffix.lower() not in TEXT_SUFFIXES or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for label, pattern in SECRET_PATTERNS.items():
            if pattern.search(text):
                violations.append(f"possível {label} em {relative}")
    if violations:
        print("Falha de segurança do repositório:", file=sys.stderr)
        for violation in sorted(set(violations)):
            print(f"- {violation}", file=sys.stderr)
        return 1
    print("Repository safety check: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
