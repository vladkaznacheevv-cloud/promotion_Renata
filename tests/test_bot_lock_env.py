import os
import tempfile
from pathlib import Path

import pytest

from telegram_bot.lock_utils import BotSingleInstanceLock, get_lock_path


def test_bot_lock_path_from_env(monkeypatch):
    monkeypatch.setenv("BOT_LOCK_PATH", "/tmp/custom-bot.lock")
    monkeypatch.delenv("BOT_LOCK_FILE", raising=False)
    assert get_lock_path() == "/tmp/custom-bot.lock"


def test_bot_lock_path_default_in_system_tmp(monkeypatch):
    monkeypatch.delenv("BOT_LOCK_PATH", raising=False)
    monkeypatch.delenv("BOT_LOCK_FILE", raising=False)
    expected = str(Path(tempfile.gettempdir()) / "promotion_renata" / "renata_bot.lock")
    assert get_lock_path() == expected


def test_single_instance_lock_applies():
    if os.name == "nt":
        pytest.skip("fcntl locking is Linux-only")

    base = Path(".tmp")
    base.mkdir(exist_ok=True)
    lock_path = base / "test_renata_bot.lock"

    lock1 = BotSingleInstanceLock(str(lock_path))
    lock2 = BotSingleInstanceLock(str(lock_path))

    assert lock1.acquire() is True
    try:
        assert lock2.acquire() is False
    finally:
        lock1.release()

    assert lock2.acquire() is True
    lock2.release()
