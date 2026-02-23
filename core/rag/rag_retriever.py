from __future__ import annotations

import math
import os
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

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
    _index_cache: dict[str, tuple[list, dict[str, float], list[Counter[str]]]] = field(default_factory=dict)

    def _cache_key(self, collection_dir: str | None = None) -> str:
        target = collection_dir or self.store.data_dir
        try:
            return str(Path(target).resolve())
        except Exception:
            return str(target)

    def refresh(self, collection_dir: str | None = None) -> None:
        chunks = self.store.load_chunks(collection_dir=collection_dir)
        tf_by_chunk = [Counter(chunk.tokens) for chunk in chunks]

        total_docs = len(chunks)
        if total_docs == 0:
            idf: dict[str, float] = {}
            cache_key = self._cache_key(collection_dir)
            self._index_cache[cache_key] = (chunks, idf, tf_by_chunk)
            if collection_dir is None:
                self.chunks = chunks
                self.idf = idf
                self.tf_by_chunk = tf_by_chunk
            return

        df: Counter[str] = Counter()
        for chunk in chunks:
            for token in set(chunk.tokens):
                df[token] += 1

        idf = {token: math.log((total_docs + 1) / (count + 1)) + 1.0 for token, count in df.items()}
        cache_key = self._cache_key(collection_dir)
        self._index_cache[cache_key] = (chunks, idf, tf_by_chunk)
        if collection_dir is None:
            self.chunks = chunks
            self.idf = idf
            self.tf_by_chunk = tf_by_chunk

    def retrieve(
        self,
        query: str,
        k: int | None = None,
        min_score: float | None = None,
        collection_dir: str | None = None,
    ) -> RagRetrieveResult:
        cache_key = self._cache_key(collection_dir)
        if collection_dir is None:
            if not self.chunks:
                self.refresh()
            chunks = self.chunks
            tf_by_chunk = self.tf_by_chunk
            idf = self.idf
        else:
            if cache_key not in self._index_cache:
                self.refresh(collection_dir=collection_dir)
            chunks, idf, tf_by_chunk = self._index_cache.get(cache_key, ([], {}, []))

        top_k = k if k is not None else _env_int("RAG_TOP_K", 5)
        top_k = max(1, min(top_k, 20))
        threshold = min_score if min_score is not None else _env_float("RAG_MIN_SCORE", 0.08)

        query_tokens = _tokenize(query)
        if not query_tokens:
            return RagRetrieveResult(top_chunks=[], confidence="low")

        query_tf = Counter(query_tokens)
        scored: list[tuple[float, int]] = []
        for idx, tf in enumerate(tf_by_chunk):
            raw_score = 0.0
            for token, q_count in query_tf.items():
                d_count = tf.get(token, 0)
                if d_count == 0:
                    continue
                raw_score += q_count * d_count * idf.get(token, 1.0)

            if raw_score <= 0:
                continue
            norm = 1.0 + 0.015 * len(chunks[idx].tokens)
            score = raw_score / norm
            if score >= threshold:
                scored.append((score, idx))

        scored.sort(key=lambda item: item[0], reverse=True)
        hits = [
            RagHit(
                source=chunks[idx].source,
                title=chunks[idx].title,
                text=chunks[idx].text,
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
