from __future__ import annotations

from core.rag import RagRetriever, RagRetrieveResult, RagStore


def test_retrieve_returns_rag_retrieve_result_with_contract(tmp_path):
    root = tmp_path / "rag_data"
    root.mkdir()
    (root / "faq.md").write_text("# FAQ\n\nИгра 10:0 и гештальт.", encoding="utf-8")

    retriever = RagRetriever(store=RagStore(data_dir=str(root)))
    result = retriever.retrieve(query="игра 10:0", k=3)

    assert isinstance(result, RagRetrieveResult)
    assert hasattr(result, "confidence")
    assert hasattr(result, "top_chunks")
    assert isinstance(result.top_chunks, list)
    for hit in result.top_chunks:
        assert hasattr(hit, "source")
        assert hasattr(hit, "score")
        assert hasattr(hit, "text")


def test_retrieve_returns_empty_top_chunks_list_for_empty_query(tmp_path):
    root = tmp_path / "rag_data"
    root.mkdir()
    (root / "faq.md").write_text("# FAQ\n\nТест.", encoding="utf-8")
    retriever = RagRetriever(store=RagStore(data_dir=str(root)))

    result = retriever.retrieve(query="   ")
    assert isinstance(result, RagRetrieveResult)
    assert isinstance(result.top_chunks, list)
    assert result.top_chunks == []
