from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable

from core.rag.rag_schema import RagChunk

_SPACES_RE = re.compile(r"\s+")
_HEADING_RE = re.compile(r"^\s*#{1,6}\s+(.+?)\s*$")
_TOKEN_RE = re.compile(r"[a-zA-Z\u0430-\u044f\u0410-\u042f\u0451\u04010-9]{2,}")
_FRONTMATTER_RE = re.compile(r"\A---\s*\n(?P<meta>.*?)\n---\s*(?:\n|$)", re.S)
_ALLOWED_DOC_TYPES = {"card", "form", "faq", "route", "program", "policy_reference"}
_ALLOWED_STATUSES = {"active", "draft", "archived"}
_TEXT_EXTS = ("*.md", "*.txt", "*.json")


def _normalize_text(value: str) -> str:
    return _SPACES_RE.sub(" ", (value or "").strip().lower().replace("ё", "е"))


def _tokenize(value: str) -> tuple[str, ...]:
    normalized = _normalize_text(value)
    return tuple(_TOKEN_RE.findall(normalized))


def _scalar_to_text(value: object) -> str:
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        parts = [_scalar_to_text(item) for item in value]
        return ", ".join(part for part in parts if part)
    return ""


def _strip_quotes(value: str) -> str:
    text = (value or "").strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {'"', "'"}:
        return text[1:-1].strip()
    return text


def _parse_scalar(value: str) -> object:
    text = _strip_quotes(value)
    lower = text.lower()
    if lower in {"true", "yes", "on"}:
        return True
    if lower in {"false", "no", "off"}:
        return False
    if text.startswith("[") and text.endswith("]"):
        items = [item.strip() for item in text[1:-1].split(",")]
        return [_strip_quotes(item) for item in items if item.strip()]
    try:
        return int(text)
    except Exception:
        pass
    try:
        return float(text)
    except Exception:
        pass
    return text


def _flatten_payload_items(value: object, *, prefix: str = "") -> list[tuple[str, str]]:
    if isinstance(value, dict):
        items: list[tuple[str, str]] = []
        for key, nested in value.items():
            key_text = str(key).strip()
            if not key_text:
                continue
            next_prefix = f"{prefix}.{key_text}" if prefix else key_text
            items.extend(_flatten_payload_items(nested, prefix=next_prefix))
        return items

    if isinstance(value, list):
        items: list[tuple[str, str]] = []
        for nested in value:
            if isinstance(nested, (dict, list)):
                items.extend(_flatten_payload_items(nested, prefix=prefix))
                continue
            text = _scalar_to_text(nested)
            if text:
                items.append((prefix, text))
        return items

    text = _scalar_to_text(value)
    if not text:
        return []
    return [(prefix, text)]


@dataclass(slots=True)
class RagStore:
    data_dir: str = "rag_data"
    min_chars: int = 300
    max_chars: int = 600
    overlap: int = 100

    def list_collections(self, base_dir: str | None = None) -> dict[str, str]:
        root = Path(base_dir or self.data_dir)
        collections: dict[str, str] = {}
        if not root.exists() or not root.is_dir():
            return {"default": str(root)}

        collections["default"] = str(root)
        for path in sorted(root.rglob("*")):
            if not path.is_dir() or path.name.startswith("."):
                continue
            has_docs = any(path.glob("*.md")) or any(path.glob("*.txt")) or any(path.glob("*.json"))
            if not has_docs:
                continue
            try:
                name = path.relative_to(root).as_posix().strip()
            except Exception:
                name = path.name.strip()
            if not name:
                continue
            collections[name.lower()] = str(path)
        return collections

    def load_chunks(self, collection_dir: str | None = None) -> list[RagChunk]:
        root = Path(collection_dir or self.data_dir)
        collection_name = self._collection_name(root)
        files = list(self._iter_files(collection_dir=collection_dir))
        chunks: list[RagChunk] = []
        for path in files:
            for title, text, metadata in self._iter_documents_from_file(path, collection_name=collection_name):
                if not text:
                    continue
                for chunk_text in self._chunk_text(text):
                    normalized = _normalize_text(chunk_text)
                    tokens = _tokenize(chunk_text)
                    if not tokens:
                        continue
                    chunks.append(
                        RagChunk(
                            source=path.name,
                            title=title,
                            text=chunk_text,
                            normalized=normalized,
                            tokens=tokens,
                            metadata=dict(metadata),
                        )
                    )
        return chunks

    def list_collection_documents(self, collection_dir: str | None = None) -> list[dict[str, object]]:
        root = Path(collection_dir or self.data_dir)
        collection_name = self._collection_name(root)
        documents: list[dict[str, object]] = []
        for path in self._iter_files(collection_dir=collection_dir):
            for title, text, metadata in self._iter_documents_from_file(path, collection_name=collection_name):
                if not text:
                    continue
                item = dict(metadata)
                item["title"] = title
                item["source"] = path.name
                documents.append(item)
        return documents

    def _collection_name(self, root: Path) -> str:
        try:
            rel = root.resolve().relative_to(Path(self.data_dir).resolve()).as_posix().strip()
        except Exception:
            rel = ""
        return rel.lower() if rel else "default"

    def _iter_documents_from_file(self, path: Path, *, collection_name: str) -> Iterable[tuple[str, str, dict[str, object]]]:
        suffix = path.suffix.lower()
        if suffix == ".json":
            raw = self._read_text(path)
            if not raw:
                return []
            try:
                parsed = json.loads(raw)
            except Exception:
                return []
            entries = self._extract_json_entries(parsed)
            if not entries:
                return []

            docs: list[tuple[str, str, dict[str, object]]] = []
            for idx, entry in enumerate(entries, start=1):
                if not isinstance(entry, dict):
                    continue
                title = _scalar_to_text(
                    entry.get("__title")
                    or entry.get("title")
                    or entry.get("button_title")
                    or entry.get("section_title")
                    or entry.get("product_title")
                    or entry.get("name")
                    or entry.get("route_key")
                    or entry.get("slug")
                    or entry.get("button_key")
                    or entry.get("section_key")
                    or entry.get("id")
                    or f"{path.stem}-{idx}"
                ) or f"{path.stem}-{idx}"
                text = self._build_json_text(title=title, payload=entry)
                metadata = self._build_metadata(
                    path=path,
                    collection_name=collection_name,
                    title=title,
                    raw_metadata={**entry, "__entry_index": idx},
                )
                docs.append((title, text, metadata))
            return docs

        raw = self._read_text(path)
        if not raw:
            return []
        frontmatter, text = self._split_frontmatter(raw)
        title = _scalar_to_text(frontmatter.get("title")) or self._extract_title(path, text)
        metadata = self._build_metadata(
            path=path,
            collection_name=collection_name,
            title=title,
            raw_metadata=frontmatter,
        )
        return [(title, text, metadata)]

    @staticmethod
    def _split_frontmatter(text: str) -> tuple[dict[str, object], str]:
        match = _FRONTMATTER_RE.match(text or "")
        if not match:
            return {}, (text or "").strip()
        metadata = RagStore._parse_frontmatter(match.group("meta") or "")
        body = (text[match.end() :] or "").strip()
        return metadata, body

    @staticmethod
    def _parse_frontmatter(raw: str) -> dict[str, object]:
        metadata: dict[str, object] = {}
        current_key = ""
        for source_line in (raw or "").splitlines():
            line = source_line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("- ") and current_key:
                value = _parse_scalar(line[2:].strip())
                existing = metadata.get(current_key)
                if isinstance(existing, list):
                    existing.append(value)
                elif existing in (None, ""):
                    metadata[current_key] = [value]
                else:
                    metadata[current_key] = [existing, value]
                continue
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            key = key.strip().lower()
            if not key:
                continue
            value = value.strip()
            if not value:
                metadata[key] = []
                current_key = key
                continue
            metadata[key] = _parse_scalar(value)
            current_key = key
        return metadata

    def _extract_json_entries(self, parsed: object) -> list[dict[str, object]]:
        if isinstance(parsed, list):
            return [item for item in parsed if isinstance(item, dict)]
        if not isinstance(parsed, dict):
            return []

        if isinstance(parsed.get("documents"), list):
            return [item for item in (parsed.get("documents") or []) if isinstance(item, dict)]
        if isinstance(parsed.get("sections"), list):
            return self._expand_menu_sections(parsed)
        if isinstance(parsed.get("routes"), list):
            return self._expand_payment_routes(parsed)
        return [parsed]

    def _expand_menu_sections(self, payload: dict[str, object]) -> list[dict[str, object]]:
        sections = payload.get("sections")
        if not isinstance(sections, list):
            return []

        base_status = _scalar_to_text(payload.get("status"))
        base_priority = payload.get("priority")
        base_updated_at = _scalar_to_text(payload.get("updated_at"))

        entries: list[dict[str, object]] = []
        for section_idx, section_raw in enumerate(sections, start=1):
            if not isinstance(section_raw, dict):
                continue

            section_key = _scalar_to_text(section_raw.get("section_key")) or f"section-{section_idx}"
            section_title = _scalar_to_text(section_raw.get("section_title")) or section_key
            section_status = _scalar_to_text(section_raw.get("status") or base_status) or "active"
            section_priority = section_raw.get("priority")
            if section_priority in (None, ""):
                section_priority = base_priority
            section_updated_at = _scalar_to_text(section_raw.get("updated_at") or base_updated_at)

            section_entry: dict[str, object] = {
                "title": section_title,
                "slug": section_key,
                "section": section_key,
                "section_key": section_key,
                "section_title": section_title,
                "section_description": _scalar_to_text(section_raw.get("section_description")),
                "assistant_hint": _scalar_to_text(section_raw.get("assistant_hint")),
                "payment_hint": _scalar_to_text(section_raw.get("payment_hint")),
                "fallback_text": _scalar_to_text(section_raw.get("fallback_text")),
                "status": section_status,
                "doc_type": "route",
            }
            if section_priority not in (None, ""):
                section_entry["priority"] = section_priority
            if section_updated_at:
                section_entry["updated_at"] = section_updated_at
            help_content = section_raw.get("help_content")
            if isinstance(help_content, dict):
                section_entry["help_content"] = help_content
            entries.append(section_entry)

            buttons = section_raw.get("buttons")
            if not isinstance(buttons, list):
                continue
            for button_idx, button_raw in enumerate(buttons, start=1):
                if not isinstance(button_raw, dict):
                    continue
                entry = dict(button_raw)
                entry.setdefault("title", _scalar_to_text(entry.get("button_title")) or f"{section_title} button {button_idx}")
                entry.setdefault(
                    "slug",
                    _scalar_to_text(entry.get("button_key")) or f"{section_key}-button-{button_idx}",
                )
                entry.setdefault("section", section_key)
                entry.setdefault("section_key", section_key)
                entry.setdefault("section_title", section_title)
                entry.setdefault("status", section_status)
                entry.setdefault("doc_type", "route")
                if "priority" not in entry and section_priority not in (None, ""):
                    entry["priority"] = section_priority
                if "updated_at" not in entry and section_updated_at:
                    entry["updated_at"] = section_updated_at
                entries.append(entry)
        return entries

    def _expand_payment_routes(self, payload: dict[str, object]) -> list[dict[str, object]]:
        routes = payload.get("routes")
        if not isinstance(routes, list):
            return []

        base_status = _scalar_to_text(payload.get("status"))
        base_priority = payload.get("priority")
        base_updated_at = _scalar_to_text(payload.get("updated_at"))

        entries: list[dict[str, object]] = []
        for route_idx, route_raw in enumerate(routes, start=1):
            if not isinstance(route_raw, dict):
                continue
            entry = dict(route_raw)
            route_key = _scalar_to_text(entry.get("route_key"))
            product_key = _scalar_to_text(entry.get("product_key"))
            product_title = _scalar_to_text(entry.get("product_title"))
            entry.setdefault("title", product_title or route_key or product_key or f"route-{route_idx}")
            entry.setdefault("slug", route_key or product_key or f"route-{route_idx}")
            entry.setdefault("doc_type", "route")
            entry.setdefault("status", _scalar_to_text(entry.get("status") or base_status) or "active")
            if "priority" not in entry and base_priority not in (None, ""):
                entry["priority"] = base_priority
            if "updated_at" not in entry and base_updated_at:
                entry["updated_at"] = base_updated_at
            section = self._infer_route_section(entry)
            if section:
                entry.setdefault("section", section)
            entries.append(entry)
        return entries

    @staticmethod
    def _infer_route_section(route: dict[str, object]) -> str:
        section = _scalar_to_text(route.get("section") or route.get("section_key") or route.get("from_section"))
        if section:
            return section
        entry_point = route.get("entry_point")
        if isinstance(entry_point, dict):
            section = _scalar_to_text(entry_point.get("from_section") or entry_point.get("section_key"))
            if section:
                return section
        payment_screen = route.get("payment_screen")
        if isinstance(payment_screen, dict):
            section = _scalar_to_text(payment_screen.get("section_key"))
            if section:
                return section
        return ""

    def _build_json_text(self, *, title: str, payload: dict[str, object]) -> str:
        preferred_fields = (
            "section_key",
            "section_title",
            "route_key",
            "product_key",
            "product_title",
            "payment_type",
            "summary",
            "description",
            "content",
            "question",
            "answer",
            "assistant_hint",
            "payment_hint",
            "fallback_text",
            "button_title",
            "from_section",
            "to_section",
            "action_type",
            "route_description",
            "program_format",
            "access_route",
        )
        metadata_keys = {"doc_type", "status", "priority", "updated_at", "section", "collection", "slug", "id"}
        lines = [title.strip()]
        seen_lines = {lines[0]} if lines[0] else set()
        used_keys = {"title", "name"}

        def append_line(label: str, value: str) -> None:
            text = (value or "").strip()
            if not text:
                return
            line = f"{label}: {text}" if label else text
            if line in seen_lines:
                return
            lines.append(line)
            seen_lines.add(line)

        for key in preferred_fields:
            value = _scalar_to_text(payload.get(key))
            if not value:
                continue
            append_line(key, value)
            used_keys.add(key)

        for path, value in _flatten_payload_items(payload):
            if not path:
                continue
            key = path.split(".", 1)[0]
            if key in used_keys or key in metadata_keys:
                continue
            if not value:
                continue
            append_line(path, value)
        return "\n".join(lines).strip()

    def _build_metadata(
        self,
        *,
        path: Path,
        collection_name: str,
        title: str,
        raw_metadata: dict[str, object],
    ) -> dict[str, object]:
        meta = dict(raw_metadata or {})
        slug_raw = _scalar_to_text(
            meta.get("slug")
            or meta.get("route_key")
            or meta.get("button_key")
            or meta.get("section_key")
            or meta.get("product_key")
            or meta.get("key")
            or meta.get("id")
        )
        if not slug_raw:
            slug_raw = path.stem
            if "__entry_index" in meta:
                slug_raw = f"{slug_raw}-{meta.get('__entry_index')}"
        slug = re.sub(r"[^a-z0-9._/-]+", "-", slug_raw.lower()).strip("-") or path.stem.lower()

        source_path = path.name
        try:
            source_path = path.resolve().relative_to(Path(self.data_dir).resolve()).as_posix()
        except Exception:
            source_path = path.as_posix()
        if "__entry_index" in meta:
            source_path = f"{source_path}#{int(meta.get('__entry_index') or 0)}"

        doc_type = self._normalize_doc_type(
            _scalar_to_text(meta.get("doc_type") or meta.get("type")),
            collection_name=collection_name,
            path=path,
        )
        status = self._normalize_status(_scalar_to_text(meta.get("status")))
        section = _scalar_to_text(
            meta.get("section")
            or meta.get("section_key")
            or meta.get("from_section")
            or meta.get("category")
        )
        if not section:
            entry_point = meta.get("entry_point")
            if isinstance(entry_point, dict):
                section = _scalar_to_text(entry_point.get("from_section") or entry_point.get("section_key"))
        if not section:
            payment_screen = meta.get("payment_screen")
            if isinstance(payment_screen, dict):
                section = _scalar_to_text(payment_screen.get("section_key"))

        try:
            priority = int(float(_scalar_to_text(meta.get("priority")) or "0"))
        except Exception:
            priority = 0

        updated_at = _scalar_to_text(meta.get("updated_at"))
        if not updated_at:
            try:
                updated_at = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC).isoformat(timespec="seconds")
            except Exception:
                updated_at = ""

        metadata: dict[str, object] = {
            "collection": collection_name,
            "slug": slug,
            "title": title,
            "doc_type": doc_type,
            "status": status,
            "source_path": source_path,
            "updated_at": updated_at,
            "priority": priority,
            "section": section,
        }
        for key, value in meta.items():
            if key.startswith("__"):
                continue
            if key in metadata:
                continue
            if isinstance(value, (str, int, float, bool, list)):
                metadata[key] = value
        return metadata

    def _normalize_doc_type(self, value: str, *, collection_name: str, path: Path) -> str:
        candidate = (value or "").strip().lower()
        if candidate in _ALLOWED_DOC_TYPES:
            return candidate
        name = path.stem.lower()
        if collection_name in {"menu_navigation", "payment_routes"}:
            return "route"
        if collection_name == "getcourse_programs":
            return "program"
        if collection_name in {"events", "gestalt"}:
            if "form" in name:
                return "form"
            return "card"
        if "faq" in name:
            return "faq"
        if "route" in name or "menu" in name:
            return "route"
        if "program" in name or "course" in name:
            return "program"
        if "policy" in name:
            return "policy_reference"
        return "card"

    @staticmethod
    def _normalize_status(value: str) -> str:
        candidate = (value or "").strip().lower()
        if candidate in _ALLOWED_STATUSES:
            return candidate
        return "active"

    def _iter_files(self, collection_dir: str | None = None) -> Iterable[Path]:
        root = Path(collection_dir or self.data_dir)
        if not root.exists() or not root.is_dir():
            return []
        files: list[Path] = []
        for ext in _TEXT_EXTS:
            files.extend(root.glob(ext))
        return sorted(path for path in files if path.is_file())

    @staticmethod
    def _read_text(path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8-sig").strip()
        except Exception:
            return ""

    @staticmethod
    def _extract_title(path: Path, text: str) -> str:
        for line in (text or "").splitlines():
            heading = _HEADING_RE.match(line)
            if heading:
                return heading.group(1).strip()
        stem = path.stem.replace("_", " ").replace("-", " ").strip()
        return stem or "Document"

    def _chunk_text(self, text: str) -> list[str]:
        paragraphs = [part.strip() for part in re.split(r"\n\s*\n+", text) if part.strip()]
        if not paragraphs:
            return []

        chunks: list[str] = []
        current: list[str] = []
        current_len = 0

        for paragraph in paragraphs:
            clean = _SPACES_RE.sub(" ", paragraph).strip()
            if not clean:
                continue
            proposed_len = current_len + len(clean) + (2 if current else 0)
            if current and proposed_len > self.max_chars:
                chunk_text = "\n\n".join(current).strip()
                if chunk_text:
                    chunks.append(chunk_text)
                overlap_tail = chunk_text[-self.overlap :] if self.overlap > 0 else ""
                current = [overlap_tail, clean] if overlap_tail else [clean]
                current_len = len("\n\n".join(current))
                while current_len > self.max_chars:
                    hard = "\n\n".join(current)
                    head = hard[: self.max_chars].strip()
                    if head:
                        chunks.append(head)
                    hard = hard[self.max_chars - self.overlap :].strip() if self.overlap else ""
                    current = [hard] if hard else []
                    current_len = len(hard)
            else:
                current.append(clean)
                current_len = proposed_len

        if current:
            tail = "\n\n".join(current).strip()
            if tail:
                chunks.append(tail)

        merged: list[str] = []
        for chunk in chunks:
            if merged and len(chunk) < self.min_chars:
                merged[-1] = f"{merged[-1]}\n\n{chunk}".strip()
            else:
                merged.append(chunk)
        return merged
