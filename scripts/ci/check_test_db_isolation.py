from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TESTS_DIR = ROOT / "tests"

FORBIDDEN_PATTERNS = {
    "banco operacional": re.compile(r"medbox_v3\.db", re.IGNORECASE),
    "caminho direto para banco": re.compile(r"(?:banco[/\\]).*\.(?:db|sqlite|sqlite3)", re.IGNORECASE),
}

ALLOWED_TEMP_MARKERS = (
    "tempfile",
    "tmp_path",
    ":memory:",
    "temporarydirectory",
)


def main() -> int:
    violations: list[str] = []

    if not TESTS_DIR.exists():
        print("Diretório tests não encontrado.", file=sys.stderr)
        return 1

    for path in sorted(TESTS_DIR.rglob("*.py")):
        text = path.read_text(encoding="utf-8-sig", errors="ignore")
        lowered = text.lower()

        for label, pattern in FORBIDDEN_PATTERNS.items():
            if pattern.search(text):
                violations.append(f"{path.relative_to(ROOT)} referencia {label}")

        if "sqlite3.connect" in lowered and not any(marker in lowered for marker in ALLOWED_TEMP_MARKERS):
            violations.append(
                f"{path.relative_to(ROOT)} abre SQLite sem marcador explícito de banco temporário"
            )

    if violations:
        print("Falha de isolamento dos testes:", file=sys.stderr)
        for violation in sorted(set(violations)):
            print(f"- {violation}", file=sys.stderr)
        return 1

    print("Test database isolation check: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
