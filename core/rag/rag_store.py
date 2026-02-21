from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from core.rag.rag_schema import RagChunk

_SPACES_RE = re.compile(r"\s+")
_HEADING_RE = re.compile(r"^\s*#{1,6}\s+(.+?)\s*$")
_TOKEN_RE = re.compile(r"[a-zA-Zа-яА-ЯёЁ0-9]{2,}")


def _normalize_text(value: str) -> str:
    return _SPACES_RE.sub(" ", (value or "").strip().lower().replace("ё", "е"))


def _tokenize(value: str) -> tuple[str, ...]:
    normalized = _normalize_text(value)
    return tuple(_TOKEN_RE.findall(normalized))


@dataclass(slots=True)
class RagStore:
    data_dir: str = "rag_data"
    min_chars: int = 300
    max_chars: int = 600
    overlap: int = 100

    def load_chunks(self) -> list[RagChunk]:
        files = list(self._iter_files())
        chunks: list[RagChunk] = []
        for path in files:
            text = self._read_text(path)
            if not text:
                continue
            title = self._extract_title(path, text)
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
                    )
                )
        return chunks

    def _iter_files(self) -> Iterable[Path]:
        root = Path(self.data_dir)
        if not root.exists() or not root.is_dir():
            return []
        files = []
        for ext in ("*.md", "*.txt"):
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
        for line in text.splitlines():
            heading = _HEADING_RE.match(line)
            if heading:
                return heading.group(1).strip()
        stem = path.stem.replace("_", " ").replace("-", " ").strip()
        return stem or "Документ"

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
