from __future__ import annotations

from core.rag import RagRetriever, RagStore


def _write(path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_rag_store_populates_required_metadata_for_json_documents(tmp_path):
    root = tmp_path / "rag_data"
    _write(
        root / "events" / "event_cards.json",
        """[
  {
    "slug": "event-a",
    "title": "Event A",
    "doc_type": "card",
    "status": "active",
    "priority": 7,
    "section": "events",
    "summary": "Событие А"
  }
]""",
    )
    store = RagStore(data_dir=str(root))
    chunks = store.load_chunks(collection_dir=str(root / "events"))
    assert chunks, "expected at least one chunk"
    meta = chunks[0].metadata
    for field in ("collection", "slug", "title", "doc_type", "status", "source_path", "updated_at", "priority", "section"):
        assert field in meta
    assert meta["collection"] == "events"
    assert meta["status"] == "active"


def test_retriever_filters_out_draft_by_default_statuses(tmp_path):
    root = tmp_path / "rag_data"
    _write(
        root / "events" / "event_cards.json",
        """[
  {
    "slug": "event-active",
    "title": "Активное событие",
    "doc_type": "card",
    "status": "active",
    "summary": "мероприятие ресурс",
    "priority": 3
  },
  {
    "slug": "event-draft",
    "title": "Черновик события",
    "doc_type": "card",
    "status": "draft",
    "summary": "мероприятие ресурс",
    "priority": 9
  }
]""",
    )
    retriever = RagRetriever(store=RagStore(data_dir=str(root)))

    active_only = retriever.retrieve(
        query="мероприятие ресурс",
        collection_dir=str(root / "events"),
        statuses=("active",),
    )
    assert active_only.top_chunks, "active document should be retrievable"
    assert all((hit.metadata or {}).get("status") == "active" for hit in active_only.top_chunks)

    with_draft = retriever.retrieve(
        query="мероприятие ресурс",
        collection_dir=str(root / "events"),
        statuses=("active", "draft"),
    )
    statuses = {(hit.metadata or {}).get("status") for hit in with_draft.top_chunks}
    assert "draft" in statuses
