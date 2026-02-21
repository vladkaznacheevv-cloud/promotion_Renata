import uuid
from pathlib import Path

from telegram_bot.lock_utils import get_lock_path, touch_lock_heartbeat


def test_get_lock_path_from_env(monkeypatch):
    monkeypatch.setenv("BOT_LOCK_PATH", "/tmp/custom.lock")
    assert get_lock_path() == "/tmp/custom.lock"


def test_touch_lock_heartbeat_handles_missing_directory():
    missing_dir = Path(".tmp") / f"missing-{uuid.uuid4().hex}"
    lock_path = missing_dir / "bot.lock"
    assert touch_lock_heartbeat(str(lock_path)) is False


def test_touch_lock_heartbeat_creates_file():
    base = Path(".tmp")
    base.mkdir(exist_ok=True)
    lock_path = base / f"bot-{uuid.uuid4().hex}.lock"
    assert touch_lock_heartbeat(str(lock_path)) is True
    assert Path(lock_path).exists()
