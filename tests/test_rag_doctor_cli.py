from __future__ import annotations

import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "scripts/rag_doctor.py", *args],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_rag_doctor_list_exit_zero():
    res = _run("--list")
    assert res.returncode == 0


def test_rag_doctor_query_single_collection_exit_zero():
    res = _run("--query", "игра 10:0", "--collections", "game10")
    assert res.returncode == 0


def test_rag_doctor_query_all_collections_exit_zero():
    res = _run("--query", "игра 10:0", "--collections", "all")
    assert res.returncode == 0
