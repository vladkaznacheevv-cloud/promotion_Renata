from __future__ import annotations

import os
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

OPENROUTER_API_BASE = "https://openrouter.ai/api/v1"
CACHE_TTL_SECONDS = 120
OTHER_MODEL_NAME = "unknown"

_CACHE: dict[str, Any] = {"ts": 0.0, "value": None}
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


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
                "tokens_total",
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
            ts /= 1000.0
        try:
            return datetime.fromtimestamp(ts, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None

    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if _DATE_RE.match(text):
            try:
                return datetime.strptime(text, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except ValueError:
                return None
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _extract_date(row: dict[str, Any]) -> str:
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
        return parsed.astimezone(timezone.utc).date().isoformat()
    return datetime.now(timezone.utc).date().isoformat()


def _in_last_30_days(date_str: str) -> bool:
    try:
        day = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return False
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    return day >= cutoff


def _extract_model(row: dict[str, Any]) -> str:
    model_value = (
        row.get("model")
        or row.get("model_name")
        or row.get("model_id")
        or row.get("name")
    )
    if isinstance(model_value, dict):
        model_value = (
            model_value.get("name")
            or model_value.get("id")
            or model_value.get("slug")
        )
    model = str(model_value or "").strip()
    return model or OTHER_MODEL_NAME


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


def _extract_tokens(row: dict[str, Any]) -> tuple[int, int, int, int]:
    prompt_tokens = _safe_int(row.get("prompt_tokens"))
    completion_tokens = _safe_int(row.get("completion_tokens"))
    reasoning_tokens = _safe_int(row.get("reasoning_tokens"))

    if prompt_tokens == 0 and completion_tokens == 0 and reasoning_tokens == 0:
        prompt_tokens = _safe_int(row.get("input_tokens"))
        completion_tokens = _safe_int(row.get("output_tokens"))

    total_tokens = prompt_tokens + completion_tokens + reasoning_tokens
    if total_tokens <= 0:
        total_tokens = _safe_int(row.get("tokens_total"))
    if total_tokens <= 0:
        total_tokens = _safe_int(row.get("total_tokens"))
    if total_tokens <= 0:
        tokens_raw = row.get("tokens")
        if isinstance(tokens_raw, dict):
            total_tokens = sum(_safe_int(value) for value in tokens_raw.values())
        else:
            total_tokens = _safe_int(tokens_raw)

    return prompt_tokens, completion_tokens, reasoning_tokens, max(total_tokens, 0)


def _normalize_activity_row(row: dict[str, Any]) -> dict[str, Any] | None:
    date = _extract_date(row)
    if not _in_last_30_days(date):
        return None
    model = _extract_model(row)
    usage = _extract_usage_usd(row)
    requests = _extract_requests(row)
    prompt_tokens, completion_tokens, reasoning_tokens, tokens = _extract_tokens(row)
    return {
        "date": date,
        "model": model,
        "usage": round(usage, 6),
        "requests": int(requests),
        "prompt_tokens": int(prompt_tokens),
        "completion_tokens": int(completion_tokens),
        "reasoning_tokens": int(reasoning_tokens),
        "tokens": int(tokens),
    }


def _extract_activity_rows(payload: Any) -> tuple[list[dict[str, Any]], bool]:
    items = _extract_items(payload)
    if items is None:
        return [], False

    rows: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        normalized = _normalize_activity_row(item)
        if normalized is not None:
            rows.append(normalized)

    rows.sort(key=lambda row: (row["date"], row["model"]))
    return rows, True


def _aggregate_activity_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "spend_usd": round(sum(_safe_float(row.get("usage")) for row in rows), 6),
        "requests": sum(_safe_int(row.get("requests")) for row in rows),
        "tokens": sum(_safe_int(row.get("tokens")) for row in rows),
    }


def _extract_models(rows: list[dict[str, Any]]) -> list[str]:
    return sorted({str(row.get("model") or OTHER_MODEL_NAME) for row in rows})


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
            "activity_rows": [],
            "models": [],
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
            "activity_rows": [],
            "models": [],
            "error": "OpenRouter metrics unavailable",
        }
        _CACHE["ts"] = now_ts
        _CACHE["value"] = value
        return value

    activity_rows: list[dict[str, Any]] = []
    models: list[str] = []
    activity = None
    rows_ok = True
    if activity_payload is not None:
        activity_rows, rows_ok = _extract_activity_rows(activity_payload)
        if rows_ok:
            activity = _aggregate_activity_rows(activity_rows)
            models = _extract_models(activity_rows)

    error = None
    if (
        credits_error == "OpenRouter metrics require a management key"
        or activity_error == "OpenRouter metrics require a management key"
    ):
        error = "OpenRouter metrics require a management key"
    elif credits_error or activity_error:
        error = "OpenRouter metrics unavailable"
    elif activity_payload is not None and not rows_ok:
        error = "OpenRouter metrics unavailable"

    value = {
        "credits": credits_payload,
        "activity": activity,
        "activity_rows": activity_rows,
        "models": models,
        "error": error,
    }
    _CACHE["ts"] = now_ts
    _CACHE["value"] = value
    return value
