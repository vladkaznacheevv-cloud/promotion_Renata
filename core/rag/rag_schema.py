from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class RagChunk:
    source: str
    title: str
    text: str
    normalized: str
    tokens: tuple[str, ...]
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class RagHit:
    source: str
    title: str
    text: str
    score: float
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class RagRetrieveResult:
    top_chunks: list[RagHit]
    confidence: str
