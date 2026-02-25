from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_COMPOSE_FILE = PROJECT_ROOT / "compose.prod.yml"
BAD_PREFIXES = ("docker ", "sudo ", "git ")


def _scan_for_suspicious_lines(path: Path) -> list[tuple[int, str]]:
    bad: list[tuple[int, str]] = []
    for lineno, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = raw_line.lstrip()
        if any(stripped.startswith(prefix) for prefix in BAD_PREFIXES):
            bad.append((lineno, raw_line))
    return bad


def _print_hints(path: Path) -> None:
    print("\nHints:")
    print(f"- Restore compose file from HEAD: git restore -- {path.as_posix()}")
    print(
        f"- Recreate web/frontend after fix: docker compose -f {path.as_posix()} "
        "up -d --build --force-recreate web frontend"
    )


def _extract_ports_lines(config_text: str) -> list[str]:
    lines = config_text.splitlines()
    out: list[str] = []
    for idx, line in enumerate(lines):
        if line.strip().startswith("web:") or line.strip().startswith("frontend:"):
            section_indent = len(line) - len(line.lstrip())
            out.append(line)
            j = idx + 1
            while j < len(lines):
                cur = lines[j]
                cur_indent = len(cur) - len(cur.lstrip())
                if cur.strip() and cur_indent <= section_indent:
                    break
                if "ports:" in cur or (out and out[-1].strip() == "ports:") or cur.strip().startswith("- target:"):
                    out.append(cur)
                j += 1
    # fallback if parser above misses compact styles
    if not any("ports:" in x for x in out):
        out.extend([ln for ln in lines if "ports:" in ln or "published:" in ln])
    return out


def run_doctor(compose_file: Path) -> int:
    if not compose_file.exists():
        print(f"ERROR: compose file not found: {compose_file}")
        _print_hints(compose_file)
        return 1

    suspicious = _scan_for_suspicious_lines(compose_file)
    if suspicious:
        print(f"ERROR: suspicious shell-like lines found in {compose_file}:")
        for lineno, line in suspicious:
            print(f"  {lineno}: {line}")
        _print_hints(compose_file)
        return 1

    if shutil.which("docker") is None:
        print("ERROR: docker command not found (cannot run `docker compose config`).")
        _print_hints(compose_file)
        return 1

    cmd = ["docker", "compose", "-f", str(compose_file), "config"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    except Exception as exc:
        print(f"ERROR: failed to run docker compose config: {exc.__class__.__name__}")
        _print_hints(compose_file)
        return 1

    if result.returncode != 0:
        print("ERROR: `docker compose config` failed")
        stderr = (result.stderr or "").strip()
        stdout = (result.stdout or "").strip()
        if stderr:
            print(stderr)
        elif stdout:
            print(stdout)
        _print_hints(compose_file)
        return 1

    print("OK: compose.prod.yml passed heuristics and `docker compose config`.")
    port_lines = _extract_ports_lines(result.stdout or "")
    if port_lines:
        print("\nPorts in rendered config (web/frontend):")
        for line in port_lines:
            print(line)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate compose.prod.yml and detect pasted shell commands.")
    parser.add_argument(
        "--file",
        default=str(DEFAULT_COMPOSE_FILE),
        help="Path to compose file (default: compose.prod.yml)",
    )
    args = parser.parse_args()
    compose_file = Path(args.file)
    if not compose_file.is_absolute():
        compose_file = (PROJECT_ROOT / compose_file).resolve()
    return run_doctor(compose_file)


if __name__ == "__main__":
    raise SystemExit(main())
