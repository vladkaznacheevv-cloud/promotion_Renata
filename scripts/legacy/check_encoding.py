from __future__ import annotations

import sys
import tokenize
from pathlib import Path


def main() -> int:
    root = Path("telegram_bot")
    py_files = sorted(root.rglob("*.py"))
    unreadable: list[tuple[str, str]] = []
    non_utf8: list[tuple[str, str]] = []

    for path in py_files:
        raw = path.read_bytes()
        try:
            raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            non_utf8.append((str(path), str(exc)))

        try:
            tokenize.open(str(path)).read()
        except Exception as exc:  # noqa: BLE001
            unreadable.append((str(path), repr(exc)))

    if non_utf8:
        print("NON_UTF8_FILES:")
        for file, err in non_utf8:
            print(f"- {file}: {err}")

    if unreadable:
        print("UNREADABLE_FILES:")
        for file, err in unreadable:
            print(f"- {file}: {err}")

    if not non_utf8 and not unreadable:
        print("OK: all telegram_bot/*.py files are UTF-8 and readable via tokenize.open")
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
