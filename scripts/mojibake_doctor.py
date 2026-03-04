from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Iterable

RUS_RE = re.compile(r"[А-Яа-яЁё]")
CYR_RE = re.compile(r"[\u0400-\u04FF]")
LATIN_MOJIBAKE_RE = re.compile(r"[ÐÑÃ]")


def _russian_count(text: str) -> int:
    return len(RUS_RE.findall(text))


def _non_russian_cyr_count(text: str) -> int:
    cyr_total = len(CYR_RE.findall(text))
    return cyr_total - _russian_count(text)


def _score(text: str) -> int:
    russian = _russian_count(text)
    non_russian_cyr = _non_russian_cyr_count(text)
    latin_mojibake = len(LATIN_MOJIBAKE_RE.findall(text))
    replacement = text.count("\ufffd")
    question_runs = text.count("????")
    return (russian * 8) - (non_russian_cyr * 20) - (latin_mojibake * 25) - (replacement * 40) - (question_runs * 40)


def _attempt_repairs(text: str) -> Iterable[str]:
    for source_encoding in ("cp1251", "latin1", "cp1252"):
        try:
            yield text.encode(source_encoding, errors="strict").decode("utf-8", errors="strict")
        except Exception:
            continue


def _is_suspicious_line(text: str) -> bool:
    if not text.strip():
        return False
    if "\ufffd" in text or "????" in text:
        return True
    if LATIN_MOJIBAKE_RE.search(text):
        return True
    if _non_russian_cyr_count(text) >= 2:
        return True
    return False


def find_mojibake_lines(paths: Iterable[Path]) -> list[tuple[Path, int]]:
    issues: list[tuple[Path, int]] = []
    for path in paths:
        if not path.exists() or not path.is_file():
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except Exception:
            continue
        for idx, line in enumerate(lines, start=1):
            if not _is_suspicious_line(line):
                continue
            baseline = _score(line)
            improved = False
            for candidate in _attempt_repairs(line):
                if candidate != line and _score(candidate) > baseline + 20:
                    improved = True
                    break
            if improved:
                issues.append((path, idx))
    return issues


def _default_paths(repo_root: Path) -> list[Path]:
    paths = [repo_root / "telegram_bot" / "main.py", repo_root / "telegram_bot" / "keyboards.py"]
    rag_data = repo_root / "rag_data"
    if rag_data.exists():
        paths.extend(sorted(rag_data.glob("*.md")))
    return paths


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Detect mojibake in source files.")
    parser.add_argument("paths", nargs="*", help="Optional file paths to scan")
    args = parser.parse_args(argv)

    repo_root = Path(__file__).resolve().parents[1]
    if args.paths:
        scan_paths = [Path(p) if Path(p).is_absolute() else (repo_root / p) for p in args.paths]
    else:
        scan_paths = _default_paths(repo_root)

    issues = find_mojibake_lines(scan_paths)
    for path, line_no in issues:
        if path.is_absolute():
            try:
                rel = path.relative_to(repo_root)
            except Exception:
                rel = Path(path.name)
        else:
            rel = path
        print(f"{rel}:{line_no}")
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
