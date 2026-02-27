from __future__ import annotations

from pathlib import Path
import importlib.util
import json


def _load_script_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "admin_recheck_yookassa_payment.py"
    spec = importlib.util.spec_from_file_location("admin_recheck_yookassa_payment", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_admin_recheck_script_smoke(monkeypatch, capsys):
    module = _load_script_module()

    async def _fake_run(payment_id: str):
        return {
            "payment_id": payment_id,
            "tg_id": 123456,
            "status": "succeeded",
            "result": "invite_failed",
            "error_type": "Forbidden",
            "confirmation_url": "https://pay.example/secret",
            "invite_link": "https://t.me/+secret",
            "token": "top-secret",
        }

    monkeypatch.setattr(module, "_run", _fake_run)
    exit_code = module.main(["yk_test_script_1"])
    assert exit_code == 0

    captured = capsys.readouterr().out.strip()
    payload = json.loads(captured)
    assert payload["payment_id"] == "yk_test_script_1"
    assert payload["status"] == "succeeded"
    assert payload["outcome"] == "invite_failed"
    assert payload["error_type"] == "Forbidden"
    assert "confirmation_url" not in payload
    assert "invite_link" not in payload
    assert "token" not in payload
    assert "https://pay.example/secret" not in captured
    assert "https://t.me/+secret" not in captured
