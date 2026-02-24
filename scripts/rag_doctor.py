from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.rag import RagRetriever, RagStore  # noqa: E402


def _safe_print(value: str) -> None:
    encoding = sys.stdout.encoding or "utf-8"
    text = (value or "").encode(encoding, errors="replace").decode(encoding, errors="replace")
    print(text)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="RAG diagnostics (collections, chunks, retrieval hits)")
    parser.add_argument("--list", action="store_true", help="List collections, documents and chunk counts")
    parser.add_argument("--query", type=str, default="", help="Run retrieval query and print top hits")
    parser.add_argument("--top-k", type=int, default=3, help="Top hits per collection for --query")
    parser.add_argument("--collection", type=str, default="", help="Optional collection name (default: all)")
    parser.add_argument(
        "--collections",
        type=str,
        default="",
        help="Collection selector: 'all' (default behavior) or collection name (alias for --collection)",
    )
    return parser


def _env_data_dir() -> str:
    return (os.getenv("RAG_DATA_DIR") or "rag_data").strip() or "rag_data"


def _iter_target_collections(store: RagStore, selected: str | None = None) -> list[tuple[str, str]]:
    collections = store.list_collections(store.data_dir)
    if selected:
        key = selected.strip().lower()
        if key in collections:
            return [(key, collections[key])]
        return [("default", collections.get("default", store.data_dir))]
    return sorted(collections.items(), key=lambda item: (item[0] != "default", item[0]))


def _print_list(store: RagStore) -> None:
    _safe_print(f"base_dir={store.data_dir}")
    for name, collection_dir in _iter_target_collections(store):
        docs = list(store._iter_files(collection_dir=collection_dir))
        chunks = store.load_chunks(collection_dir=collection_dir)
        _safe_print(f"[{name}] dir={collection_dir}")
        _safe_print(f"  docs={len(docs)} chunks={len(chunks)}")
        for path in docs[:20]:
            try:
                size = path.stat().st_size
            except Exception:
                size = -1
            _safe_print(f"  - {path.name} ({size} bytes)")


def _print_query(store: RagStore, query: str, top_k: int, selected: str | None = None) -> None:
    retriever = RagRetriever(store=store)
    _safe_print(f"query={query}")
    for name, collection_dir in _iter_target_collections(store, selected):
        result = retriever.retrieve(query=query, k=max(1, min(top_k, 10)), collection_dir=collection_dir)
        _safe_print(
            f"[{name}] dir={collection_dir} confidence={result.confidence} top_chunks_count={len(result.top_chunks)}"
        )
        for idx, hit in enumerate(result.top_chunks[: max(1, min(top_k, 10))], start=1):
            excerpt = (hit.text or "").replace("\n", " ").strip()
            excerpt = excerpt[:280] + ("..." if len(excerpt) > 280 else "")
            _safe_print(f"  {idx}. {hit.title} ({hit.source}) score={hit.score} | {excerpt}")


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    store = RagStore(data_dir=_env_data_dir())

    if not args.list and not args.query:
        parser.print_help()
        return 1

    if args.list:
        _print_list(store)
        if args.query:
            _safe_print("")

    if args.query:
        selected = (args.collection or "").strip() or (args.collections or "").strip()
        if selected.lower() == "all":
            selected = ""
        _print_query(store, args.query.strip(), args.top_k, selected or None)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
