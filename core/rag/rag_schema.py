from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class RagChunk:
    source: str
    title: str
    text: str
    normalized: str
    tokens: tuple[str, ...]


@dataclass(slots=True)
class RagHit:
    source: str
    title: str
    text: str
    score: float


@dataclass(slots=True)
class RagRetrieveResult:
    top_chunks: list[RagHit]
    confidence: str
