from __future__ import annotations

import asyncio
import csv
import io
import logging
import os
import re
from typing import Any
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

import httpx

logger = logging.getLogger(__name__)


DEFAULT_ENTITY_PATHS: tuple[tuple[str, str], ...] = (
    ("deals", "/pl/api/account/deals"),
)


class GetCourseClient:
    def __init__(self) -> None:
        self.api_key = (os.getenv("GETCOURSE_API_KEY") or "").strip()
        self.use_bearer = (os.getenv("GETCOURSE_USE_BEARER", "false").lower() == "true")
        self.base_url = self._normalize_base_url(
            os.getenv("GETCOURSE_BASE_URL") or "https://getcourse.ru"
        )
        self.enabled = (os.getenv("GETCOURSE_ENABLED", "false").lower() == "true") and bool(self.api_key)
        self.entity_paths = self._entity_paths()
        self.action_fallbacks = self._action_fallbacks()

    @staticmethod
    def _normalize_base_url(value: str) -> str:
        raw = (value or "").strip()
        if not raw:
            return "https://getcourse.ru"
        if not raw.startswith(("http://", "https://")):
            raw = f"https://{raw}"

        parsed = urlparse(raw)
        if not parsed.netloc:
            logger.warning("Invalid GETCOURSE_BASE_URL=%r. Fallback to https://getcourse.ru", value)
            return "https://getcourse.ru"

        normalized = f"{parsed.scheme}://{parsed.netloc}".rstrip("/")
        if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
            logger.warning(
                "GETCOURSE_BASE_URL should be origin only. Normalized %r -> %r",
                raw,
                normalized,
            )
        return normalized

    @staticmethod
    def _safe_url_for_logs(url: str) -> str:
        parsed = urlparse(url)
        if not parsed.query:
            return url
        redacted_query = []
        for key, value in parse_qsl(parsed.query, keep_blank_values=True):
            if key.lower() == "key":
                redacted_query.append((key, "***"))
            else:
                redacted_query.append((key, value))
        return urlunparse(parsed._replace(query=urlencode(redacted_query)))

    @staticmethod
    def _normalize_api_path(path_or_url: str) -> str | None:
        parsed = urlparse(path_or_url)
        path = parsed.path if parsed.scheme else path_or_url
        path = (path or "").strip()
        if not path:
            return None
        if not path.startswith("/"):
            path = f"/{path.lstrip('/')}"
        if not path.startswith("/pl/api/"):
            return None
        if path == "/pl/api/deals":
            path = "/pl/api/account/deals"
        if path == "/pl/api/users":
            path = "/pl/api/account/users"
        query = f"?{parsed.query}" if parsed.query else ""
        return f"{path}{query}"

    def _entity_paths(self) -> tuple[tuple[str, str], ...]:
        raw = (os.getenv("GETCOURSE_ENTITY_PATHS") or "").strip()
        if not raw:
            return DEFAULT_ENTITY_PATHS

        parsed: list[tuple[str, str]] = []
        for part in raw.split(","):
            item = part.strip()
            if not item:
                continue
            if ":" in item:
                source, path = item.split(":", 1)
                normalized_path = self._normalize_api_path(path.strip())
                if normalized_path:
                    parsed.append((source.strip() or "unknown", normalized_path))
                else:
                    logger.warning(
                        "Skip non-API GETCOURSE_ENTITY_PATHS value for source=%s: %s",
                        source.strip() or "unknown",
                        path.strip(),
                    )
            else:
                normalized_path = self._normalize_api_path(item.strip())
                if normalized_path:
                    parsed.append((item.strip().strip("/"), normalized_path))
                else:
                    logger.warning("Skip non-API GETCOURSE_ENTITY_PATHS value: %s", item.strip())
        if not parsed:
            return DEFAULT_ENTITY_PATHS

        # Keep custom paths, but append defaults that are not explicitly configured.
        existing_sources = {source for source, _ in parsed}
        for source, path in DEFAULT_ENTITY_PATHS:
            if source not in existing_sources:
                parsed.append((source, path))
        return tuple(parsed)

    def _headers(self, *, form: bool = False) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
        }
        if self.use_bearer and self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        if form:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        return headers

    def _auth_params(self, action: str | None = None) -> dict[str, str]:
        # Для разных конфигураций API поддерживаем query key.
        params = {"key": self.api_key}
        if action:
            params["action"] = action
        return params

    @staticmethod
    def _looks_like_action_error(message: str) -> bool:
        text = (message or "").strip().lower()
        if not text:
            return False
        markers = ("action", "действ", "пустой параметр")
        return any(marker in text for marker in markers)

    @staticmethod
    def _action_fallbacks() -> tuple[str | None, ...]:
        raw = (os.getenv("GETCOURSE_ACTION_FALLBACKS") or "").strip()
        if raw:
            values = [part.strip() for part in raw.split(",") if part.strip()]
            if None not in values:
                values.append(None)
            return tuple(values)
        return ("get", "list", None)

    def _actions_for_source(self, source: str, path: str) -> tuple[str | None, ...]:
        source_norm = (source or "").strip().lower()
        path_tail = (path.rsplit("/", 1)[-1] or "").split("?", 1)[0].strip().lower()
        candidates: list[str | None] = []
        # For account APIs many installations still require explicit action.
        if "/pl/api/account/" in path:
            for value in (source_norm, source_norm.rstrip("s"), "get", "list", None):
                if value in ("", None):
                    if None not in candidates:
                        candidates.append(None)
                    continue
                if value not in candidates:
                    candidates.append(value)
            return tuple(candidates)

        for value in (
            source_norm,
            path_tail,
            source_norm.rstrip("s"),
            path_tail.rstrip("s"),
            *self.action_fallbacks,
        ):
            if value in ("", None):
                if None not in candidates:
                    candidates.append(None)
                continue
            if value not in candidates:
                candidates.append(value)
        if None not in candidates:
            candidates.append(None)
        return tuple(candidates)

    def _extract_items(self, payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]

        if not isinstance(payload, dict):
            return []

        keys = (
            "result",
            "items",
            "data",
            "list",
            "info",
            "rows",
            "records",
            "deals",
            "products",
            "courses",
            "webinars",
            "events",
            "pages",
            "offers",
        )
        for key in keys:
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
            if isinstance(value, dict):
                nested = self._extract_items(value)
                if nested:
                    return nested

        # В некоторых ответах сущность может быть верхнеуровневым dict.
        if "id" in payload:
            return [payload]
        return []

    @staticmethod
    def _extract_payload_error(payload: Any) -> str | None:
        if not isinstance(payload, dict):
            return None

        success = payload.get("success")
        status = str(payload.get("status") or "").strip().lower()
        has_error = success is False or status in {"error", "failed", "fail"}
        if not has_error and "error" not in payload and "errors" not in payload:
            return None

        for key in ("error", "message", "description", "detail"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        errors = payload.get("errors")
        if isinstance(errors, list) and errors:
            return str(errors[0])
        if isinstance(errors, dict) and errors:
            first_key = next(iter(errors.keys()))
            return f"{first_key}: {errors[first_key]}"
        return "Request rejected"

    def _extract_export_urls(self, payload: Any) -> list[str]:
        if not isinstance(payload, dict):
            return []

        candidates: list[str] = []
        for key in ("export_url", "result_url", "download_url", "url", "link"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                candidates.append(value.strip())

        info = payload.get("info")
        if isinstance(info, dict):
            for key in ("export_url", "result_url", "download_url", "url", "link"):
                value = info.get(key)
                if isinstance(value, str) and value.strip():
                    candidates.append(value.strip())
            export_id = info.get("export_id") or info.get("id")
            if export_id not in (None, ""):
                export_id = str(export_id).strip()
                candidates.extend(
                    [
                        f"/pl/api/account/exports/{export_id}",
                        f"/pl/api/account/export/{export_id}",
                        f"/pl/api/account/export?export_id={export_id}",
                        f"/pl/api/account/exports?export_id={export_id}",
                        f"/pl/api/account/exports?id={export_id}",
                    ]
                )

        normalized: list[str] = []
        seen: set[str] = set()
        for value in candidates:
            candidate = value
            parsed = urlparse(value)
            if parsed.scheme:
                path = parsed.path or ""
                if not path.startswith("/pl/api/"):
                    continue
            else:
                path = value.split("?", 1)[0]
                if not path.startswith("/pl/api/"):
                    continue
                candidate = urljoin(f"{self.base_url.rstrip('/')}/", value.lstrip("/"))

            if candidate not in seen:
                seen.add(candidate)
                normalized.append(candidate)
        return normalized

    async def _fetch_export_items(self, url: str) -> list[dict[str, Any]]:
        timeout = httpx.Timeout(15.0, connect=5.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url, headers=self._headers(), params=self._auth_params())
        if response.status_code == 404:
            return []
        response.raise_for_status()
        try:
            payload = response.json()
            return self._extract_items(payload)
        except Exception:
            text = response.text or ""
            return self._parse_csv_items(text)

    @staticmethod
    def _parse_csv_items(text: str) -> list[dict[str, Any]]:
        content = (text or "").strip()
        if not content:
            return []
        if "," not in content and ";" not in content:
            return []
        delimiter = ";" if content.count(";") > content.count(",") else ","
        stream = io.StringIO(content)
        reader = csv.DictReader(stream, delimiter=delimiter)
        rows: list[dict[str, Any]] = []
        for row in reader:
            normalized = {str(k).strip(): v for k, v in row.items() if k is not None}
            if any(value not in (None, "") for value in normalized.values()):
                rows.append(normalized)
        return rows

    async def _fetch_with_action(self, url: str, action: str | None, timeout: httpx.Timeout) -> list[dict[str, Any]]:
        action_label = action or "<empty>"
        last_error: Exception | None = None
        action_error: str | None = None
        for attempt in range(3):
            for method in ("get", "post"):
                try:
                    async with httpx.AsyncClient(timeout=timeout) as client:
                        params = self._auth_params(action)
                        if method == "get":
                            response = await client.get(
                                url,
                                headers=self._headers(),
                                params=params,
                            )
                        else:
                            response = await client.post(
                                url,
                                headers=self._headers(form=True),
                                data=params,
                            )
                    if response.status_code == 404:
                        return []
                    response.raise_for_status()
                    payload = response.json()
                    payload_error = self._extract_payload_error(payload)
                    if payload_error:
                        if self._looks_like_action_error(payload_error):
                            action_error = payload_error
                            continue
                        raise RuntimeError(payload_error)

                    items = self._extract_items(payload)
                    if items:
                        return items

                    for export_url in self._extract_export_urls(payload):
                        try:
                            export_items = await self._fetch_export_items(export_url)
                        except Exception as export_exc:  # pragma: no cover - network dependent
                            logger.warning(
                                "GetCourse export fetch failed %s: %s",
                                self._safe_url_for_logs(export_url),
                                export_exc,
                            )
                            continue
                        if export_items:
                            return export_items
                    return []
                except httpx.HTTPStatusError as exc:  # pragma: no cover - network dependent
                    if exc.response.status_code in {401, 403}:
                        raise RuntimeError(f"Request rejected (HTTP {exc.response.status_code})") from exc
                    if exc.response.status_code == 400:
                        safe_url = self._safe_url_for_logs(url)
                        if "/pl/cms/page/view" in safe_url:
                            raise RuntimeError("Bad URL (truncated key)") from exc
                        raise RuntimeError("Request rejected (HTTP 400)") from exc
                    last_error = RuntimeError(self._sanitize_error_message(str(exc)))
                    logger.warning(
                        "GetCourse request failed path=%s action=%s method=%s (attempt %s/3): %s",
                        url,
                        action_label,
                        method,
                        attempt + 1,
                        self._sanitize_error_message(str(exc)),
                    )
                except ValueError as exc:
                    action_error = str(exc)
                    continue
                except Exception as exc:  # pragma: no cover - network dependent
                    last_error = RuntimeError(self._sanitize_error_message(str(exc)))
                    logger.warning(
                        "GetCourse request failed path=%s action=%s method=%s (attempt %s/3): %s",
                        url,
                        action_label,
                        method,
                        attempt + 1,
                        self._sanitize_error_message(str(exc)),
                    )
            if attempt < 2:
                await asyncio.sleep(0.8 * (attempt + 1))

        if action_error:
            raise ValueError(action_error)
        if last_error is not None:
            raise last_error
        return []

    async def _fetch_path(self, source: str, path: str) -> list[dict[str, Any]]:
        if not path:
            return []
        if not path.startswith("/pl/api/"):
            raise RuntimeError(f"Request rejected: non-API path '{path}'")

        url = f"{self.base_url}/{path.lstrip('/')}"
        timeout = httpx.Timeout(15.0, connect=5.0)
        last_action_error: str | None = None
        for action in self._actions_for_source(source, path):
            try:
                return await self._fetch_with_action(url, action, timeout)
            except ValueError as exc:
                last_action_error = str(exc)
                continue

        if last_action_error:
            raise RuntimeError(last_action_error)
        return []

    async def fetch_entities_raw(self) -> tuple[list[dict[str, Any]], dict[str, int]]:
        if not self.enabled:
            return [], {}

        aggregated: list[dict[str, Any]] = []
        source_counts: dict[str, int] = {}
        source_errors: list[str] = []

        for source, path in self.entity_paths:
            try:
                items = await self._fetch_path(source, path)
            except Exception as exc:
                logger.warning("GetCourse source failed: source=%s path=%s error=%s", source, path, exc)
                source_counts[source] = 0
                source_errors.append(f"{source}: {exc}")
                continue
            source_counts[source] = len(items)
            for item in items:
                if "_gc_source" not in item:
                    item = {**item, "_gc_source": source}
                aggregated.append(item)

        if not aggregated and source_errors and len(source_errors) >= len(self.entity_paths):
            raise RuntimeError("; ".join(source_errors[:3]))

        return aggregated, source_counts
    @staticmethod
    def _sanitize_error_message(value: str) -> str:
        text = str(value or "")
        text = re.sub(r"([?&]key=)[^&\\s]+", r"\\1***", text, flags=re.IGNORECASE)
        text = re.sub(r"(Bearer\\s+)[A-Za-z0-9._\\-]+", r"\\1***", text, flags=re.IGNORECASE)
        return text
