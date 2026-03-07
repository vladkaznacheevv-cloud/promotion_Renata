from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.ai.prompt_bridge import load_policy_prompt
from core.rag import RagRetriever, RagRouter, RagStore

DEFAULT_QUERIES = (
    "что такое игра 10:0",
    "как оплатить игру 10:0",
    "что делать после оплаты",
    "не пришёл доступ после оплаты",
    "как открыть getcourse",
    "где в меню курс",
    "какие есть мероприятия",
    "как записаться на консультацию",
    "как связаться с менеджером",
    "где кнопка помощь",
)


def _safe_print(value: str) -> None:
    encoding = sys.stdout.encoding or "utf-8"
    text = (value or "").encode(encoding, errors="replace").decode(encoding, errors="replace")
    print(text)


def _run_query(*, query: str, store: RagStore, retriever: RagRetriever, router: RagRouter, top_k: int) -> None:
    collections = store.list_collections(store.data_dir)
    route = router.route(query, available_collections=set(collections.keys()), max_collections=2)
    selected = [name for name in route.selected_collections if name in collections] or ["default"]
    _safe_print(f"query={query}")
    _safe_print(f"router_reason={route.reason} selected={selected}")
    combined = []
    for name in selected:
        result = retriever.retrieve(
            query=route.query,
            k=max(1, min(top_k, 10)),
            collection_dir=collections.get(name) or store.data_dir,
            statuses=("active",),
            exclude_doc_types=("policy_reference",),
        )
        for hit in result.top_chunks:
            combined.append((float(hit.score), name, hit))
    combined.sort(key=lambda item: item[0], reverse=True)
    hits = combined[: max(1, min(top_k, 10))]
    _safe_print(f"hits={len(hits)}")
    for idx, (_, name, hit) in enumerate(hits, start=1):
        meta = dict(hit.metadata or {})
        excerpt = (hit.text or "").replace("\n", " ").strip()
        excerpt = excerpt[:180] + ("..." if len(excerpt) > 180 else "")
        _safe_print(
            f"  {idx}. [{meta.get('collection', name)}/{meta.get('doc_type', 'card')}/{meta.get('status', 'active')}] "
            f"{hit.title} ({hit.source}) score={hit.score} | {excerpt}"
        )
    if not hits:
        _safe_print("  top chunks: none")
    _safe_print("")


def main() -> int:
    args = [item.strip() for item in sys.argv[1:] if item.strip()]
    data_dir = (os.getenv("RAG_DATA_DIR") or "rag_data").strip() or "rag_data"
    top_k_raw = (os.getenv("RAG_TOP_K") or "").strip()
    try:
        top_k = int(top_k_raw) if top_k_raw else 4
    except Exception:
        top_k = 4
    top_k = max(1, min(top_k, 10))

    policy = load_policy_prompt()
    _safe_print(f"policy_prompt_source={policy.source}")
    _safe_print(f"policy_prompt_loaded={bool(policy.content)}")
    _safe_print(f"rag_data_dir={data_dir}")
    _safe_print("")

    store = RagStore(data_dir=data_dir)
    retriever = RagRetriever(store=store)
    router = RagRouter()
    queries = args or list(DEFAULT_QUERIES)
    for query in queries:
        _run_query(query=query, store=store, retriever=retriever, router=router, top_k=top_k)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
