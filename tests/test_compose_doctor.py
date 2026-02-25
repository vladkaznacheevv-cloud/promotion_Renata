from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "scripts/compose_doctor.py", *args],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=90,
    )


def test_compose_doctor_detects_shell_commands(tmp_path: Path):
    compose_file = tmp_path / "compose.prod.yml"
    compose_file.write_text(
        'version: "3.8"\nservices:\n  web:\n    image: x\n' "docker compose -f compose.prod.yml up -d\n",
        encoding="utf-8",
    )
    res = _run("--file", str(compose_file))
    assert res.returncode == 1
    assert "suspicious shell-like lines" in (res.stdout + res.stderr)


def test_compose_doctor_validates_compose_prod_when_docker_available():
    if shutil.which("docker") is None:
        pytest.skip("docker is not available in test environment")
    res = _run()
    assert res.returncode == 0, res.stdout + "\n" + res.stderr
