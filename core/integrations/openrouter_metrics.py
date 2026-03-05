from __future__ import annotations

import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

OPENROUTER_API_BASE = "https://openrouter.ai/api/v1"
CACHE_TTL_SECONDS = 120

_CACHE: dict[str, Any] = {"ts": 0.0, "value": None}


def _safe_float(value: Any) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return 0.0
    if isinstance(value, dict):
        for key in ("value", "amount", "usd", "total", "sum"):
            if key in value:
                return _safe_float(value.get(key))
    return 0.0


def _safe_int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return 0
        try:
            return int(float(text))
        except ValueError:
            return 0
    return 0


def _extract_items(payload: Any) -> list[Any] | None:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        data = payload.get("data")
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            nested_items = data.get("items")
            if isinstance(nested_items, list):
                return nested_items
            nested_data = data.get("data")
            if isinstance(nested_data, list):
                return nested_data
        items = payload.get("items")
        if isinstance(items, list):
            return items
        if any(
            key in payload
            for key in (
                "usage",
                "spend",
                "cost",
                "requests",
                "request_count",
                "generation_count",
                "tokens",
                "total_tokens",
                "prompt_tokens",
                "completion_tokens",
                "reasoning_tokens",
            )
        ):
            return [payload]
    return None


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, (int, float)):
        ts = float(value)
        if ts > 1_000_000_000_000:
            ts = ts / 1000.0
        try:
            return datetime.fromtimestamp(ts, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _is_within_last_30_days(row: dict[str, Any]) -> bool:
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    for key in (
        "date",
        "day",
        "timestamp",
        "time",
        "bucket_start",
        "start_time",
        "created_at",
    ):
        parsed = _parse_datetime(row.get(key))
        if parsed is None:
            continue
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed >= cutoff
    return True


def _extract_usage_usd(row: dict[str, Any]) -> float:
    for key in ("usage", "spend", "cost", "amount", "usd"):
        if key in row:
            return _safe_float(row.get(key))
    return 0.0


def _extract_requests(row: dict[str, Any]) -> int:
    for key in ("requests", "request_count", "generation_count", "count"):
        if key in row:
            return _safe_int(row.get(key))
    return 0


def _extract_tokens(row: dict[str, Any]) -> int:
    primary = (
        _safe_int(row.get("prompt_tokens"))
        + _safe_int(row.get("completion_tokens"))
        + _safe_int(row.get("reasoning_tokens"))
    )
    if primary > 0:
        return primary

    io_tokens = _safe_int(row.get("input_tokens")) + _safe_int(row.get("output_tokens"))
    if io_tokens > 0:
        return io_tokens

    tokens_field = row.get("tokens")
    if isinstance(tokens_field, dict):
        subtotal = 0
        for key in (
            "prompt",
            "completion",
            "reasoning",
            "input",
            "output",
            "total",
            "prompt_tokens",
            "completion_tokens",
            "reasoning_tokens",
            "input_tokens",
            "output_tokens",
            "total_tokens",
        ):
            subtotal += _safe_int(tokens_field.get(key))
        if subtotal > 0:
            return subtotal
        return sum(_safe_int(value) for value in tokens_field.values())

    tokens_scalar = _safe_int(tokens_field)
    if tokens_scalar > 0:
        return tokens_scalar

    return _safe_int(row.get("total_tokens"))


def _aggregate_activity(payload: Any) -> dict[str, Any] | None:
    items = _extract_items(payload)
    if items is None:
        return None

    spend_usd = 0.0
    requests = 0
    tokens = 0
    for item in items:
        if not isinstance(item, dict):
            continue
        if not _is_within_last_30_days(item):
            continue
        spend_usd += _extract_usage_usd(item)
        requests += _extract_requests(item)
        tokens += _extract_tokens(item)

    return {
        "spend_usd": round(spend_usd, 6),
        "requests": requests,
        "tokens": tokens,
    }


def _get_key() -> str | None:
    management_key = (os.getenv("OPENROUTER_MANAGEMENT_KEY") or "").strip()
    if management_key:
        return management_key
    api_key = (os.getenv("OPENROUTER_API_KEY") or "").strip()
    return api_key or None


async def _fetch_json(
    client: httpx.AsyncClient,
    path: str,
    key: str,
) -> tuple[Any | None, str | None]:
    response = await client.get(
        f"{OPENROUTER_API_BASE}{path}",
        headers={"Authorization": f"Bearer {key}"},
    )
    if response.status_code in (401, 403):
        return None, "OpenRouter metrics require a management key"
    if response.status_code >= 400:
        return None, "OpenRouter metrics unavailable"
    try:
        return response.json(), None
    except ValueError:
        return None, "OpenRouter metrics unavailable"


async def fetch_openrouter_credits(
    client: httpx.AsyncClient,
    key: str,
) -> tuple[Any | None, str | None]:
    return await _fetch_json(client, "/credits", key)


async def fetch_openrouter_activity(
    client: httpx.AsyncClient,
    key: str,
) -> tuple[Any | None, str | None]:
    return await _fetch_json(client, "/activity", key)


async def fetch_openrouter_metrics() -> dict[str, Any]:
    now_ts = time.time()
    cached_value = _CACHE.get("value")
    cached_ts = float(_CACHE.get("ts") or 0.0)
    if cached_value is not None and (now_ts - cached_ts) < CACHE_TTL_SECONDS:
        return cached_value

    key = _get_key()
    if not key:
        value = {
            "credits": None,
            "activity": None,
            "error": "OpenRouter metrics require a management key",
        }
        _CACHE["ts"] = now_ts
        _CACHE["value"] = value
        return value

    credits_payload = None
    activity_payload = None
    credits_error = None
    activity_error = None
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            credits_payload, credits_error = await fetch_openrouter_credits(client, key)
            activity_payload, activity_error = await fetch_openrouter_activity(client, key)
    except Exception:
        value = {
            "credits": None,
            "activity": None,
            "error": "OpenRouter metrics unavailable",
        }
        _CACHE["ts"] = now_ts
        _CACHE["value"] = value
        return value

    activity = _aggregate_activity(activity_payload) if activity_payload is not None else None

    error = None
    if credits_error == "OpenRouter metrics require a management key" or activity_error == "OpenRouter metrics require a management key":
        error = "OpenRouter metrics require a management key"
    elif credits_error or activity_error:
        error = "OpenRouter metrics unavailable"
    elif activity_payload is not None and activity is None:
        error = "OpenRouter metrics unavailable"

    value = {
        "credits": credits_payload,
        "activity": activity,
        "error": error,
    }
    _CACHE["ts"] = now_ts
    _CACHE["value"] = value
    return value
