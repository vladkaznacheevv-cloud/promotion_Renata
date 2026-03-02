from __future__ import annotations

import asyncio
import os
import ssl
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

PROJECT_ROOT =Path (__file__ ).resolve ().parents [1 ]
if str (PROJECT_ROOT )not in sys .path :
    sys .path .insert (0 ,str (PROJECT_ROOT ))


def _int_env(name: str, default: int, *, minimum: int = 1, maximum: int | None = None) -> int:
    raw = str(os.getenv(name) or "").strip()
    try:
        value = int(raw) if raw else int(default)
    except Exception:
        value = int(default)
    if value < minimum:
        value = minimum
    if maximum is not None and value > maximum:
        value = maximum
    return value


def _timeout_seconds() -> float:
    return float(_int_env("DB_ACTIVITY_PROBE_TIMEOUT_SEC", 5, minimum=1, maximum=15))


def _connect_args() -> dict:
    connect_timeout_sec = _int_env("DB_CONNECT_TIMEOUT_SEC", 5, minimum=1, maximum=30)
    statement_timeout_ms = _int_env("DB_STATEMENT_TIMEOUT_MS", 7000, minimum=1000, maximum=60000)
    args: dict = {
        "timeout": connect_timeout_sec,
        "server_settings": {"statement_timeout": str(statement_timeout_ms)},
    }
    if (os.getenv("DB_SSLMODE") or "").strip().lower() == "require":
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        args["ssl"] = ssl_context
    return args


def _short_error_code(exc: Exception) -> str:
    text_value = str(exc or "").lower()
    if "permission denied" in text_value:
        return "insufficient_privileges"
    if "timeout" in text_value:
        return "timeout"
    if "connection" in text_value or "connect" in text_value:
        return "connection_error"
    return exc.__class__.__name__


def _format_counts(rows: list[tuple[str, int]]) -> str:
    if not rows:
        return "none"
    cleaned: list[tuple[str, int]] = []
    for key, value in rows:
        normalized_key = (str(key or "unknown").strip() or "unknown").lower()
        cleaned.append((normalized_key, int(value)))
    agg = defaultdict(int)
    for key, value in cleaned:
        agg[key] += value
    ordered = sorted(agg.items(), key=lambda item: (-item[1], item[0]))
    return ",".join(f"{k}:{v}" for k, v in ordered)


async def _scalar(session: Any, text_fn: Any, sql: str) -> int:
    result = await asyncio.wait_for(session.execute(text_fn(sql)), timeout=_timeout_seconds())
    return int(result.scalar_one())


async def _rows(session: Any, text_fn: Any, sql: str) -> list[tuple[str, int]]:
    result = await asyncio.wait_for(session.execute(text_fn(sql)), timeout=_timeout_seconds())
    output: list[tuple[str, int]] = []
    for row in result.all():
        output.append((str(row[0]), int(row[1])))
    return output


async def main() -> int:
    print("db_activity_probe")
    try:
        from sqlalchemy import text as sa_text
        from sqlalchemy.ext.asyncio import create_async_engine
    except Exception:
        print("probe.error=dependency_missing")
        return 2

    try:
        from core.db import database as db_module

        dsn = db_module._build_database_url()  # intentionally reuse app DSN builder
    except Exception as exc:
        print("db_url=UNAVAILABLE")
        print(f"probe.error={_short_error_code(exc)}")
        return 2

    engine = create_async_engine(
        dsn,
        echo=False,
        future=True,
        connect_args=_connect_args(),
        pool_pre_ping=True,
        pool_size=1,
        max_overflow=0,
        pool_timeout=_int_env("DB_POOL_TIMEOUT_SEC", 5, minimum=1, maximum=60),
    )
    try:
        async with engine.connect() as conn:
            try:
                await _scalar(conn, sa_text, "SELECT 1")
                print("db.ping=ok")
            except Exception as exc:
                print("db.ping=fail")
                print(f"probe.error={_short_error_code(exc)}")
                return 3

            try:
                total = await _scalar(conn, sa_text, "SELECT COUNT(*) FROM pg_stat_activity")
                print(f"pg_stat_activity.total={total}")
            except Exception as exc:
                print("pg_stat_activity.total=UNAVAILABLE")
                print(f"pg_stat_activity.access={_short_error_code(exc)}")
                return 0

            try:
                by_state = await _rows(
                    conn,
                    sa_text,
                    """
                    SELECT COALESCE(state, 'unknown') AS state, COUNT(*)
                    FROM pg_stat_activity
                    GROUP BY COALESCE(state, 'unknown')
                    """,
                )
                print(f"pg_stat_activity.by_state={_format_counts(by_state)}")
            except Exception as exc:
                print("pg_stat_activity.by_state=UNAVAILABLE")
                print(f"pg_stat_activity.by_state_error={_short_error_code(exc)}")

            try:
                by_wait = await _rows(
                    conn,
                    sa_text,
                    """
                    SELECT COALESCE(wait_event_type, 'none') AS wait_event_type, COUNT(*)
                    FROM pg_stat_activity
                    GROUP BY COALESCE(wait_event_type, 'none')
                    """,
                )
                print(f"pg_stat_activity.by_wait_event_type={_format_counts(by_wait)}")
            except Exception as exc:
                print("pg_stat_activity.by_wait_event_type=UNAVAILABLE")
                print(f"pg_stat_activity.by_wait_event_type_error={_short_error_code(exc)}")
        return 0
    finally:
        await engine.dispose()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
