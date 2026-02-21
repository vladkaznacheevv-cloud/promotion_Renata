from __future__ import annotations

import asyncio
import csv
import io
import logging
import os
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import httpx

logger = logging.getLogger(__name__)


@dataclass
class ExportResult:
    items: list[dict[str, Any]]
    fetched: int
    error: str | None = None
    status_code: int | None = None
    error_kind: str | None = None
    error_code: int | None = None
    error_message: str | None = None


class GetCourseUnsupportedResourceError(RuntimeError):
    def __init__(self, message: str = "Unsupported resource", status_code: int = 404) -> None:
        super().__init__(message)
        self.status_code = status_code


class GetCourseAuthError(RuntimeError):
    def __init__(self, message: str = "Request rejected", status_code: int = 401) -> None:
        super().__init__(message)
        self.status_code = status_code


class GetCourseBusyError(RuntimeError):
    def __init__(self, message: str = "Export is already running", status_code: int = 200, error_code: int = 905) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code


class GetCourseRequestRejectedError(RuntimeError):
    pass


class GetCourseExportClient:
    def __init__(self) -> None:
        self.api_key = (os.getenv("GETCOURSE_API_KEY") or "").strip()
        self.enabled = (os.getenv("GETCOURSE_ENABLED", "false").lower() == "true") and bool(self.api_key)
        self.base_url = self._normalize_base_url(os.getenv("GETCOURSE_BASE_URL") or "https://getcourse.ru")
        self.timeout = httpx.Timeout(30.0, connect=8.0)
        self.max_poll_attempts = 12

    @staticmethod
    def _normalize_base_url(value: str) -> str:
        raw = (value or "").strip()
        if not raw:
            return "https://getcourse.ru"
        if not raw.startswith(("http://", "https://")):
            raw = f"https://{raw}"
        parsed = urlparse(raw)
        if not parsed.netloc:
            return "https://getcourse.ru"
        return f"{parsed.scheme}://{parsed.netloc}".rstrip("/")

    @staticmethod
    def _safe_url(url: str) -> str:
        parsed = urlparse(url)
        if not parsed.query:
            return url
        redacted: list[tuple[str, str]] = []
        for key, value in parse_qsl(parsed.query, keep_blank_values=True):
            redacted.append((key, "***" if key.lower() == "key" else value))
        return urlunparse(parsed._replace(query=urlencode(redacted)))

    @staticmethod
    def _sanitize_error_message(value: str) -> str:
        text = str(value or "")
        text = re.sub(r"([?&]key=)[^&\s]+", r"\1***", text, flags=re.IGNORECASE)
        text = re.sub(r"(Bearer\s+)[A-Za-z0-9._\-]+", r"\1***", text, flags=re.IGNORECASE)
        return text

    @staticmethod
    def _extract_error(payload: Any) -> str | None:
        if not isinstance(payload, dict):
            return None
        success = payload.get("success")
        status = str(payload.get("status") or "").strip().lower()
        if success is not False and status not in {"error", "failed", "fail"} and "error" not in payload:
            return None
        for key in ("error", "message", "description", "detail"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return "Request rejected"

    @staticmethod
    def _extract_error_code(payload: Any) -> int | None:
        if not isinstance(payload, dict):
            return None
        value = payload.get("error_code")
        if value in (None, ""):
            return None
        try:
            return int(value)
        except Exception:
            return None

    @staticmethod
    def _extract_items(payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, list):
            return [x for x in payload if isinstance(x, dict)]
        if not isinstance(payload, dict):
            return []
        for key in ("items", "rows", "data", "result", "list", "info", "records"):
            value = payload.get(key)
            if isinstance(value, list):
                return [x for x in value if isinstance(x, dict)]
            if isinstance(value, dict):
                nested = GetCourseExportClient._extract_items(value)
                if nested:
                    return nested
        if "id" in payload and isinstance(payload, dict):
            return [payload]
        return []

    @staticmethod
    def _parse_csv(text: str) -> list[dict[str, Any]]:
        content = (text or "").strip()
        if not content:
            return []
        if "," not in content and ";" not in content:
            return []
        delimiter = ";" if content.count(";") > content.count(",") else ","
        reader = csv.DictReader(io.StringIO(content), delimiter=delimiter)
        rows: list[dict[str, Any]] = []
        for row in reader:
            parsed = {str(k).strip(): v for k, v in row.items() if k is not None}
            if any(v not in (None, "") for v in parsed.values()):
                rows.append(parsed)
        return rows

    @staticmethod
    def _resolve_from_date(last_sync_at: datetime | None = None) -> date:
        if last_sync_at is not None:
            if last_sync_at.tzinfo is None:
                last_sync_at = last_sync_at.replace(tzinfo=timezone.utc)
            return (last_sync_at - timedelta(days=1)).date()

        raw_days = (os.getenv("GETCOURSE_EXPORT_FROM_DAYS") or "").strip()
        try:
            days = int(raw_days) if raw_days else 30
        except Exception:
            days = 30
        days = max(days, 1)
        return (datetime.now(tz=timezone.utc) - timedelta(days=days)).date()

    @classmethod
    def build_filters(
        cls,
        *,
        filters: dict[str, Any] | None = None,
        last_sync_at: datetime | None = None,
    ) -> dict[str, Any]:
        merged = dict(filters or {})
        if not any(k.startswith("created_at[") or k.startswith("updated_at[") for k in merged.keys()):
            merged["created_at[from]"] = cls._resolve_from_date(last_sync_at).isoformat()
        return merged

    async def start_export(
        self,
        resource: str,
        filters: dict[str, Any] | None = None,
        *,
        last_sync_at: datetime | None = None,
    ) -> str:
        resource_name = (resource or "").strip().strip("/")
        if not resource_name:
            raise RuntimeError("Empty export resource")

        params = {"key": self.api_key}
        params.update(self.build_filters(filters=filters, last_sync_at=last_sync_at))

        url = f"{self.base_url}/pl/api/account/{resource_name}"
        safe_url = self._safe_url(url)

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, params=params, headers={"Accept": "application/json"})

            body_preview = self._sanitize_error_message((response.text or "")[:300].replace("\n", " ").replace("\r", " "))
            logger.info(
                "GetCourse export start: resource=%s status=%s url=%s body=%s",
                resource_name,
                response.status_code,
                safe_url,
                body_preview,
            )

            if response.status_code == 404:
                raise GetCourseUnsupportedResourceError(status_code=404)
            if response.status_code in {401, 403}:
                raise GetCourseAuthError(status_code=response.status_code)
            response.raise_for_status()

            payload = response.json()
            payload_error = self._extract_error(payload)
            if payload_error:
                error_code = self._extract_error_code(payload)
                if error_code == 905:
                    raise GetCourseBusyError(payload_error, status_code=response.status_code, error_code=905)
                lowered = payload_error.lower()
                if "unauthorized" in lowered or "forbidden" in lowered:
                    raise GetCourseAuthError(payload_error, status_code=403)
                raise GetCourseRequestRejectedError(payload_error)

            export_id = None
            if isinstance(payload, dict):
                export_id = payload.get("export_id")
                if not export_id and isinstance(payload.get("info"), dict):
                    export_id = payload["info"].get("export_id") or payload["info"].get("id")
            if export_id in (None, ""):
                raise RuntimeError("GetCourse export_id is missing")
            return str(export_id).strip()
        except (GetCourseUnsupportedResourceError, GetCourseAuthError, GetCourseBusyError, GetCourseRequestRejectedError):
            raise
        except Exception as exc:  # pragma: no cover - network dependent
            raise RuntimeError(self._sanitize_error_message(str(exc))) from exc

    async def poll_export(self, export_id: str) -> list[dict[str, Any]]:
        export_id = (export_id or "").strip()
        if not export_id:
            return []

        url = f"{self.base_url}/pl/api/account/exports/{export_id}"
        safe_url = self._safe_url(url)

        for attempt in range(1, self.max_poll_attempts + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.get(
                        url,
                        params={"key": self.api_key},
                        headers={"Accept": "application/json"},
                    )
                if response.status_code in {401, 403}:
                    raise GetCourseAuthError(status_code=response.status_code)
                if response.status_code == 404:
                    await asyncio.sleep(min(1.0 + attempt * 0.3, 3.0))
                    continue
                response.raise_for_status()

                body_preview = self._sanitize_error_message((response.text or "")[:300].replace("\n", " ").replace("\r", " "))
                logger.info(
                    "GetCourse export poll: export_id=%s attempt=%s status=%s url=%s body=%s",
                    export_id,
                    attempt,
                    response.status_code,
                    safe_url,
                    body_preview,
                )

                try:
                    payload = response.json()
                    payload_error = self._extract_error(payload)
                    if payload_error:
                        raise RuntimeError(payload_error)
                    items = self._extract_items(payload)
                except ValueError:
                    items = self._parse_csv(response.text or "")

                if items:
                    logger.info("GetCourse export fetched: export_id=%s fetched=%s", export_id, len(items))
                    return items
            except GetCourseAuthError:
                raise
            except Exception as exc:  # pragma: no cover - network dependent
                logger.warning(
                    "GetCourse export poll failed: export_id=%s attempt=%s url=%s error=%s",
                    export_id,
                    attempt,
                    safe_url,
                    self._sanitize_error_message(str(exc)),
                )
            await asyncio.sleep(min(1.0 + attempt * 0.3, 3.0))
        return []

    async def export_resource(
        self,
        resource: str,
        filters: dict[str, Any] | None = None,
        *,
        last_sync_at: datetime | None = None,
    ) -> ExportResult:
        if not self.enabled:
            return ExportResult(
                items=[],
                fetched=0,
                error="\u0418\u043d\u0442\u0435\u0433\u0440\u0430\u0446\u0438\u044f GetCourse \u043e\u0442\u043a\u043b\u044e\u0447\u0435\u043d\u0430",
                error_kind="disabled",
            )
        try:
            export_id = await self.start_export(resource, filters=filters, last_sync_at=last_sync_at)
            if not export_id:
                return ExportResult(items=[], fetched=0, error=None)
            items = await self.poll_export(export_id)
            return ExportResult(items=items, fetched=len(items), error=None)
        except GetCourseUnsupportedResourceError as exc:
            message = self._sanitize_error_message(str(exc))
            return ExportResult(
                items=[],
                fetched=0,
                error=message,
                status_code=exc.status_code,
                error_kind="unsupported",
                error_message=message,
            )
        except GetCourseAuthError as exc:
            message = self._sanitize_error_message(str(exc))
            return ExportResult(
                items=[],
                fetched=0,
                error=message,
                status_code=exc.status_code,
                error_kind="auth_error",
                error_message=message,
            )
        except GetCourseBusyError as exc:
            message = self._sanitize_error_message(str(exc))
            return ExportResult(
                items=[],
                fetched=0,
                error=message,
                status_code=exc.status_code,
                error_kind="busy",
                error_code=exc.error_code,
                error_message=message,
            )
        except GetCourseRequestRejectedError as exc:
            message = self._sanitize_error_message(str(exc))
            return ExportResult(
                items=[],
                fetched=0,
                error=message,
                status_code=200,
                error_kind="request_rejected",
                error_message=message,
            )
        except Exception as exc:
            message = self._sanitize_error_message(str(exc))
            error_kind = "auth_error" if ("401" in message or "403" in message) else "request_error"
            return ExportResult(
                items=[],
                fetched=0,
                error=message,
                status_code=None,
                error_kind=error_kind,
                error_message=message,
            )

    async def ping_export(self, resource: str = "users") -> dict[str, Any]:
        if not self.enabled:
            return {
                "ok": False,
                "resource": resource,
                "status_code": None,
                "error_kind": "disabled",
                "error_code": None,
                "error_message": "\u0418\u043d\u0442\u0435\u0433\u0440\u0430\u0446\u0438\u044f GetCourse \u043e\u0442\u043a\u043b\u044e\u0447\u0435\u043d\u0430",
            }

        resource_name = (resource or "").strip().strip("/")
        if not resource_name:
            return {
                "ok": False,
                "resource": resource,
                "status_code": None,
                "error_kind": "request_rejected",
                "error_code": None,
                "error_message": "Empty resource",
            }

        params = {"key": self.api_key}
        params.update(self.build_filters(last_sync_at=datetime.now(tz=timezone.utc) - timedelta(days=1)))
        url = f"{self.base_url}/pl/api/account/{resource_name}"
        safe_url = self._safe_url(url)

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, params=params, headers={"Accept": "application/json"})
        except Exception as exc:  # pragma: no cover - network dependent
            return {
                "ok": False,
                "resource": resource_name,
                "status_code": None,
                "error_kind": "request_error",
                "error_code": None,
                "error_message": self._sanitize_error_message(str(exc)),
            }

        logger.info(
            "GetCourse probe: resource=%s status=%s url=%s",
            resource_name,
            response.status_code,
            safe_url,
        )

        if response.status_code == 404:
            return {
                "ok": False,
                "resource": resource_name,
                "status_code": 404,
                "error_kind": "unsupported",
                "error_code": None,
                "error_message": "Unsupported resource",
            }
        if response.status_code in {401, 403}:
            return {
                "ok": False,
                "resource": resource_name,
                "status_code": response.status_code,
                "error_kind": "auth_error",
                "error_code": None,
                "error_message": "Request rejected",
            }

        try:
            payload = response.json()
        except Exception:
            payload = None

        payload_error = self._extract_error(payload)
        if payload_error:
            error_code = self._extract_error_code(payload)
            return {
                "ok": False,
                "resource": resource_name,
                "status_code": response.status_code,
                "error_kind": "busy" if error_code == 905 else "request_rejected",
                "error_code": error_code,
                "error_message": self._sanitize_error_message(payload_error),
            }

        return {
            "ok": True,
            "resource": resource_name,
            "status_code": response.status_code,
            "error_kind": None,
            "error_code": None,
            "error_message": None,
        }
