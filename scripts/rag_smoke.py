from __future__ import annotations

import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core.rag import RagRetriever, RagStore


def _safe_print(value: str) -> None:
    encoding = sys.stdout.encoding or "utf-8"
    text = (value or "").encode(encoding, errors="replace").decode(encoding, errors="replace")
    print(text)


def main() -> int:
    query = " ".join(sys.argv[1:]).strip() or "как записаться на консультацию"
    data_dir = (os.getenv("RAG_DATA_DIR") or "rag_data").strip() or "rag_data"
    top_k_raw = (os.getenv("RAG_TOP_K") or "").strip()
    try:
        top_k = int(top_k_raw) if top_k_raw else 5
    except Exception:
        top_k = 5
    top_k = max(1, min(top_k, 20))

    store = RagStore(data_dir=data_dir)
    retriever = RagRetriever(store=store)
    result = retriever.retrieve(query, k=top_k)

    _safe_print(f"query={query}")
    _safe_print(f"confidence={result.confidence} hits={len(result.top_chunks)}")
    for idx, hit in enumerate(result.top_chunks, start=1):
        preview = hit.text.replace("\n", " ").strip()[:200]
        _safe_print(f"{idx}. source={hit.source} score={hit.score} text={preview}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
