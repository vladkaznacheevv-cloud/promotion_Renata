from __future__ import annotations

import argparse
import os
import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.ai.prompt_bridge import load_policy_prompt  # noqa: E402
from core.rag import RagRetriever, RagRouter, RagStore  # noqa: E402


def _safe_print(value: str) -> None:
    encoding = sys.stdout.encoding or "utf-8"
    text = (value or "").encode(encoding, errors="replace").decode(encoding, errors="replace")
    print(text)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="RAG diagnostics (collections, metadata, statuses, retrieval hits)")
    parser.add_argument("--list", action="store_true", help="List collections, documents and chunk counts")
    parser.add_argument("--query", type=str, default="", help="Run retrieval query and print top hits")
    parser.add_argument("--top-k", type=int, default=3, help="Top hits per collection for --query")
    parser.add_argument("--collection", type=str, default="", help="Optional collection name (default: router/all)")
    parser.add_argument(
        "--collections",
        type=str,
        default="",
        help="Collection selector: 'all' or comma-separated collection names",
    )
    parser.add_argument(
        "--status",
        type=str,
        default="active",
        help="Comma-separated statuses for retrieval (active,draft,archived)",
    )
    parser.add_argument(
        "--include-policy",
        action="store_true",
        help="Include policy_reference doc_type in retrieval diagnostics",
    )
    return parser


def _env_data_dir() -> str:
    return (os.getenv("RAG_DATA_DIR") or "rag_data").strip() or "rag_data"


def _resolve_collection_names(store: RagStore, *, collection: str, collections_arg: str) -> list[str]:
    registry = store.list_collections(store.data_dir)
    if collections_arg.strip():
        if collection.strip():
            _safe_print("warning: both --collection and --collections provided; using --collections")
        raw = collections_arg.strip()
        if raw.lower() == "all":
            return sorted(registry.keys(), key=lambda name: (name != "default", name))
        names: list[str] = []
        for item in raw.split(","):
            key = item.strip().lower()
            if key and key not in names:
                names.append(key)
        return names
    if collection.strip():
        return [collection.strip().lower()]
    return []


def _resolve_statuses(raw: str) -> tuple[str, ...]:
    items = [item.strip().lower() for item in (raw or "").split(",") if item.strip()]
    allowed = {"active", "draft", "archived"}
    resolved = tuple(item for item in items if item in allowed)
    return resolved or ("active",)


def _collection_summary(store: RagStore, collection_dir: str) -> tuple[int, int, dict[str, int], dict[str, int]]:
    docs = list(store._iter_files(collection_dir=collection_dir))
    chunks = store.load_chunks(collection_dir=collection_dir)
    metadata_docs = store.list_collection_documents(collection_dir=collection_dir)
    statuses: Counter[str] = Counter()
    doc_types: Counter[str] = Counter()
    for item in metadata_docs:
        statuses[str(item.get("status") or "active").lower()] += 1
        doc_types[str(item.get("doc_type") or "card").lower()] += 1
    return len(docs), len(chunks), dict(statuses), dict(doc_types)


def _print_list(store: RagStore) -> None:
    policy = load_policy_prompt()
    _safe_print(f"base_dir={store.data_dir}")
    _safe_print(f"policy_prompt_source={policy.source}")
    _safe_print(f"policy_prompt_loaded={bool(policy.content)}")
    collections = store.list_collections(store.data_dir)
    for name, collection_dir in sorted(collections.items(), key=lambda item: (item[0] != "default", item[0])):
        docs_count, chunks_count, statuses, doc_types = _collection_summary(store, collection_dir)
        _safe_print(f"[{name}] dir={collection_dir}")
        _safe_print(f"  docs={docs_count} chunks={chunks_count}")
        _safe_print(f"  statuses={statuses}")
        _safe_print(f"  doc_types={doc_types}")
        for path in list(store._iter_files(collection_dir=collection_dir))[:20]:
            try:
                size = path.stat().st_size
            except Exception:
                size = -1
            _safe_print(f"  - {path.name} ({size} bytes)")


def _query_collections(
    *,
    store: RagStore,
    retriever: RagRetriever,
    router: RagRouter,
    query: str,
    statuses: tuple[str, ...],
    top_k: int,
    selected_collections: list[str],
    include_policy: bool,
) -> None:
    registry = store.list_collections(store.data_dir)
    if selected_collections:
        targets = [name for name in selected_collections if name in registry]
        route_reason = "manual"
    else:
        route = router.route(query, available_collections=set(registry.keys()), max_collections=2)
        targets = [name for name in route.selected_collections if name in registry]
        route_reason = route.reason
        _safe_print(f"router_query={route.query}")
    if not targets:
        targets = ["default"]

    _safe_print(f"query={query}")
    _safe_print(f"router_reason={route_reason}")
    _safe_print(f"selected_collections={targets}")
    _safe_print(f"statuses={list(statuses)}")
    for name in targets:
        collection_dir = registry.get(name) or store.data_dir
        _safe_print(f"==== {name} ====")
        _safe_print(f"collection_dir={collection_dir}")
        result = retriever.retrieve(
            query=query,
            k=max(1, min(top_k, 10)),
            collection_dir=collection_dir,
            statuses=statuses,
            exclude_doc_types=None if include_policy else ("policy_reference",),
        )
        _safe_print(f"confidence={result.confidence} top_chunks_count={len(result.top_chunks)}")
        if not result.top_chunks:
            _safe_print("  top chunks: none")
            continue
        for idx, hit in enumerate(result.top_chunks[: max(1, min(top_k, 10))], start=1):
            meta = dict(hit.metadata or {})
            excerpt = (hit.text or "").replace("\n", " ").strip()
            excerpt = excerpt[:220] + ("..." if len(excerpt) > 220 else "")
            _safe_print(
                "  "
                + f"{idx}. [{meta.get('collection', name)}/{meta.get('doc_type', 'card')}/{meta.get('status', 'active')}] "
                + f"{hit.title} ({hit.source}) score={hit.score} slug={meta.get('slug', '')} | {excerpt}"
            )


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    store = RagStore(data_dir=_env_data_dir())
    retriever = RagRetriever(store=store)
    router = RagRouter()

    if not args.list and not args.query:
        parser.print_help()
        return 1

    statuses = _resolve_statuses(args.status)
    selected_names = _resolve_collection_names(
        store,
        collection=(args.collection or ""),
        collections_arg=(args.collections or ""),
    )

    if args.list:
        _print_list(store)
        if args.query:
            _safe_print("")

    if args.query:
        _query_collections(
            store=store,
            retriever=retriever,
            router=router,
            query=args.query.strip(),
            statuses=statuses,
            top_k=args.top_k,
            selected_collections=selected_names,
            include_policy=bool(args.include_policy),
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
