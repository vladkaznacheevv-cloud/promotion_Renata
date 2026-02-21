from __future__ import annotations

import re
from typing import Any
from urllib.parse import parse_qs, urljoin, urlparse, urlunparse


_WHITESPACE_RE = re.compile(r"\s")


def normalize_getcourse_url(
    value: Any,
    *,
    base_url: str | None = None,
    min_key_length: int = 8,
) -> tuple[str | None, str | None]:
    """Return normalized URL and error reason (if any)."""
    if value in (None, ""):
        return None, None

    raw = str(value).strip()
    if not raw:
        return None, "empty"

    # Remove control separators that are often introduced by copy/paste.
    raw = raw.replace("\r", "").replace("\n", "").replace("\t", "")
    if not raw:
        return None, "empty"

    # Keep strict behavior: spaces inside URL are rejected.
    if _WHITESPACE_RE.search(raw):
        return None, "whitespace_in_url"

    if raw.startswith("/") and base_url:
        raw = urljoin(f"{base_url.rstrip('/')}/", raw.lstrip("/"))

    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"}:
        return None, "invalid_scheme"
    if not parsed.netloc:
        return None, "missing_host"

    query = parse_qs(parsed.query, keep_blank_values=True)
    key_values = query.get("key") or []
    if key_values:
        key_value = (key_values[0] or "").strip()
        if 0 < len(key_value) < min_key_length:
            return None, "truncated_key"

    normalized = urlunparse(parsed)
    return normalized, None


def is_valid_getcourse_url(value: Any, *, base_url: str | None = None) -> bool:
    normalized, _ = normalize_getcourse_url(value, base_url=base_url)
    return bool(normalized)
