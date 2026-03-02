from __future__ import annotations

import os
from pathlib import Path


ENV_KEYS = (
    "DATABASE_URL",
    "DB_HOST",
    "DB_NAME",
    "DB_USER",
    "DB_PASSWORD",
    "DB_PORT",
    "DB_SSLMODE",
)


def _marker(value: str | None) -> str:
    return "SET" if str(value or "").strip() else "MISSING"


def main() -> int:
    print("runtime_env_probe")
    print(f"cwd={Path.cwd()}")

    for key in ENV_KEYS:
        print(f"env.{key}={_marker(os.getenv(key))}")

    check_paths = (
        Path("/app/.env"),
        Path("/app/.env.prod"),
        Path.cwd() / ".env",
        Path.cwd() / ".env.prod",
    )
    for path in check_paths:
        print(f"file.{path}=yes" if path.exists() else f"file.{path}=no")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
