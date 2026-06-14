from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(os.getenv("TEXT_SMOKE_ROOT", "app"))
SOURCE_EXTENSIONS = {".py", ".html", ".txt", ".md"}
BAD_PATTERNS = (
    "�",
    "锟",
    "Ã",
    "Â",
    "Î",
    "Ð",
    "Ë",
    "£",
    "谷旋",
    "隆辺",
    "住豚",
    "人薩",
)

ALLOWLIST = (
    ("app/importers/legacy_customers.py", "锟斤拷锟斤拷员"),
    ("app/importers/legacy_customers.py", '"锟" in lowered'),
    ("app/importers/legacy_customers.py", '"�" in lowered'),
)


def is_allowed(path: Path, line: str) -> bool:
    normalized = path.as_posix()
    return any(normalized.endswith(allowed_path) and token in line for allowed_path, token in ALLOWLIST)


def should_scan(path: Path) -> bool:
    if "__pycache__" in path.parts:
        return False
    if path.name == "text_smoke.py":
        return False
    return path.suffix in SOURCE_EXTENSIONS


def main() -> int:
    root = ROOT.resolve()
    failures: list[str] = []
    if not root.exists():
        print(f"[FAIL] text smoke root does not exist: {root}")
        return 1

    for path in sorted(item for item in root.rglob("*") if item.is_file() and should_scan(item)):
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            failures.append(f"{path}: cannot decode as UTF-8")
            continue

        for line_no, line in enumerate(lines, start=1):
            if is_allowed(path, line):
                continue
            matches = [pattern for pattern in BAD_PATTERNS if pattern in line]
            if matches:
                failures.append(f"{path}:{line_no}: suspicious text {matches}: {line.strip()}")

    if failures:
        print("[FAIL] suspicious text found")
        for failure in failures:
            print(f"  - {failure}")
        return 1

    print(f"[PASS] backend text smoke scanned {root}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
