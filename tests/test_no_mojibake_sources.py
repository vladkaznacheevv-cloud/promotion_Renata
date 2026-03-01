from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def _run_doctor(*paths: str) -> subprocess.CompletedProcess[str]:
    cmd = [sys.executable, "scripts/mojibake_doctor.py", *paths]
    return subprocess.run(cmd, capture_output=True, text=True, check=False)


def test_no_mojibake_in_main_source() -> None:
    result = _run_doctor("telegram_bot/main.py")
    assert result.returncode == 0, result.stdout


def test_doctor_detects_mojibake_in_sample(tmp_path: Path) -> None:
    sample = tmp_path / "sample.py"
    sample.write_text('x = "РџСЂРёРІРµС‚"', encoding="utf-8")

    result = _run_doctor(str(sample))
    assert result.returncode == 1
    assert "sample.py:1" in result.stdout
