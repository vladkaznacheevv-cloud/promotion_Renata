from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

try:
    import fcntl  # type: ignore
except Exception:  # pragma: no cover
    fcntl = None

DEFAULT_LOCK_DIR = "promotion_renata"
DEFAULT_LOCK_FILE = "renata_bot.lock"


def _default_lock_path() -> str:
    base = Path(tempfile.gettempdir()) / DEFAULT_LOCK_DIR
    return str(base / DEFAULT_LOCK_FILE)


def _ensure_lock_parent(path: str) -> None:
    try:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass


def get_lock_path() -> str:
    return os.getenv("BOT_LOCK_PATH") or os.getenv("BOT_LOCK_FILE") or _default_lock_path()


def touch_lock_heartbeat(path: str) -> bool:
    try:
        _ensure_lock_parent(path)
        Path(path).touch()
        return True
    except Exception:
        return False


@dataclass
class BotSingleInstanceLock:
    path: str
    fd: object | None = None

    def acquire(self) -> bool:
        if fcntl is None:
            return True
        _ensure_lock_parent(self.path)
        fd = open(self.path, "a+", encoding="utf-8")
        try:
            fcntl.flock(fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            fd.close()
            return False
        self.fd = fd
        return True

    def release(self) -> None:
        if self.fd is None or fcntl is None:
            self.fd = None
            return
        try:
            fcntl.flock(self.fd.fileno(), fcntl.LOCK_UN)
        except Exception:
            pass
        try:
            self.fd.close()
        except Exception:
            pass
        self.fd = None
