from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)


DEFAULT_ENTITY_PATHS: tuple[tuple[str, str], ...] = (
    ("deals", "/pl/api/deals"),
    ("products", "/pl/api/products"),
    ("courses", "/pl/api/courses"),
    ("webinars", "/pl/api/webinars"),
    ("pages", "/pl/api/pages"),
)


class GetCourseClient:
    def __init__(self) -> None:
        self.api_key = (os.getenv("GETCOURSE_API_KEY") or "").strip()
        self.base_url = (os.getenv("GETCOURSE_BASE_URL") or "https://getcourse.ru").rstrip("/")
        self.enabled = (os.getenv("GETCOURSE_ENABLED", "false").lower() == "true") and bool(self.api_key)
        self.entity_paths = self._entity_paths()

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
                parsed.append((source.strip() or "unknown", path.strip()))
            else:
                parsed.append((item.strip().strip("/"), item.strip()))
        return tuple(parsed) if parsed else DEFAULT_ENTITY_PATHS

    def _headers(self) -> dict[str, str]:
        return {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

    def _auth_params(self) -> dict[str, str]:
        # Для разных конфигураций API поддерживаем query key как fallback.
        return {"key": self.api_key}

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

    async def _fetch_path(self, path: str) -> list[dict[str, Any]]:
        if not path:
            return []

        url = f"{self.base_url}/{path.lstrip('/')}"
        timeout = httpx.Timeout(15.0, connect=5.0)

        last_error: Exception | None = None
        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.get(
                        url,
                        headers=self._headers(),
                        params=self._auth_params(),
                    )
                if response.status_code == 404:
                    return []
                response.raise_for_status()
                payload = response.json()
                return self._extract_items(payload)
            except httpx.HTTPStatusError as exc:  # pragma: no cover - network dependent
                # Неверная авторизация/доступ: не продолжаем бессмысленные retries.
                if exc.response.status_code in {401, 403}:
                    raise
                last_error = exc
                logger.warning("GetCourse request %s failed (attempt %s/3): %s", path, attempt + 1, exc)
            except Exception as exc:  # pragma: no cover - network dependent
                last_error = exc
                logger.warning("GetCourse request %s failed (attempt %s/3): %s", path, attempt + 1, exc)
            if attempt < 2:
                await asyncio.sleep(0.8 * (attempt + 1))

        if last_error is not None:
            raise last_error
        return []

    async def fetch_entities_raw(self) -> tuple[list[dict[str, Any]], dict[str, int]]:
        if not self.enabled:
            return [], {}

        aggregated: list[dict[str, Any]] = []
        source_counts: dict[str, int] = {}

        for source, path in self.entity_paths:
            items = await self._fetch_path(path)
            source_counts[source] = len(items)
            for item in items:
                if "_gc_source" not in item:
                    item = {**item, "_gc_source": source}
                aggregated.append(item)

        return aggregated, source_counts
