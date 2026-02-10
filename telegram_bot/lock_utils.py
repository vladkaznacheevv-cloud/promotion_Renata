from __future__ import annotations

import os
from dataclasses import dataclass

try:
    import fcntl  # type: ignore
except Exception:  # pragma: no cover
    fcntl = None


def get_lock_path() -> str:
    return os.getenv("BOT_LOCK_PATH") or os.getenv("BOT_LOCK_FILE") or "/tmp/renata_bot.lock"


@dataclass
class BotSingleInstanceLock:
    path: str
    fd: object | None = None

    def acquire(self) -> bool:
        if fcntl is None:
            return True
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
