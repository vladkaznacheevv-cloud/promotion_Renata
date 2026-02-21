from __future__ import annotations

import math
import os
import re
from collections import Counter
from dataclasses import dataclass, field

from core.rag.rag_schema import RagHit, RagRetrieveResult
from core.rag.rag_store import RagStore

_TOKEN_RE = re.compile(r"[a-zA-Zа-яА-ЯёЁ0-9]{2,}")
_SPACES_RE = re.compile(r"\s+")


def _normalize_text(value: str) -> str:
    return _SPACES_RE.sub(" ", (value or "").strip().lower().replace("ё", "е"))


def _tokenize(value: str) -> tuple[str, ...]:
    return tuple(_TOKEN_RE.findall(_normalize_text(value)))


def _env_int(name: str, default: int) -> int:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except Exception:
        return default


def _env_float(name: str, default: float) -> float:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except Exception:
        return default


@dataclass(slots=True)
class RagRetriever:
    store: RagStore
    chunks: list = field(default_factory=list)
    idf: dict[str, float] = field(default_factory=dict)
    tf_by_chunk: list[Counter[str]] = field(default_factory=list)

    def refresh(self) -> None:
        self.chunks = self.store.load_chunks()
        self.tf_by_chunk = [Counter(chunk.tokens) for chunk in self.chunks]

        total_docs = len(self.chunks)
        if total_docs == 0:
            self.idf = {}
            return

        df: Counter[str] = Counter()
        for chunk in self.chunks:
            for token in set(chunk.tokens):
                df[token] += 1

        self.idf = {token: math.log((total_docs + 1) / (count + 1)) + 1.0 for token, count in df.items()}

    def retrieve(
        self,
        query: str,
        k: int | None = None,
        min_score: float | None = None,
    ) -> RagRetrieveResult:
        if not self.chunks:
            self.refresh()

        top_k = k if k is not None else _env_int("RAG_TOP_K", 5)
        top_k = max(1, min(top_k, 20))
        threshold = min_score if min_score is not None else _env_float("RAG_MIN_SCORE", 0.08)

        query_tokens = _tokenize(query)
        if not query_tokens:
            return RagRetrieveResult(top_chunks=[], confidence="low")

        query_tf = Counter(query_tokens)
        scored: list[tuple[float, int]] = []
        for idx, tf in enumerate(self.tf_by_chunk):
            raw_score = 0.0
            for token, q_count in query_tf.items():
                d_count = tf.get(token, 0)
                if d_count == 0:
                    continue
                raw_score += q_count * d_count * self.idf.get(token, 1.0)

            if raw_score <= 0:
                continue
            norm = 1.0 + 0.015 * len(self.chunks[idx].tokens)
            score = raw_score / norm
            if score >= threshold:
                scored.append((score, idx))

        scored.sort(key=lambda item: item[0], reverse=True)
        hits = [
            RagHit(
                source=self.chunks[idx].source,
                title=self.chunks[idx].title,
                text=self.chunks[idx].text,
                score=round(score, 4),
            )
            for score, idx in scored[:top_k]
        ]

        if not hits:
            return RagRetrieveResult(top_chunks=[], confidence="low")

        top_score = hits[0].score
        if top_score >= 0.6:
            confidence = "high"
        elif top_score >= 0.25:
            confidence = "medium"
        else:
            confidence = "low"
        return RagRetrieveResult(top_chunks=hits, confidence=confidence)
