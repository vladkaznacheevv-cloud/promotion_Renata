from __future__ import annotations

from core.rag import RagStore


def test_list_collections_auto_discovers_nested_dirs(tmp_path):
    root = tmp_path / "rag_data"
    root.mkdir()
    (root / "faq.md").write_text("# FAQ\n\nБазовый контент.", encoding="utf-8")
    (root / "game10").mkdir()
    (root / "game10" / "overview.md").write_text("# Game10\n\nКонтент game10.", encoding="utf-8")
    (root / "programs").mkdir()
    (root / "programs" / "supervision").mkdir(parents=True, exist_ok=True)
    (root / "programs" / "supervision" / "notes.txt").write_text("Супервизорская группа", encoding="utf-8")

    store = RagStore(data_dir=str(root))
    collections = store.list_collections()

    assert "default" in collections
    assert "game10" in collections
    assert "programs/supervision" in collections
    # Parent dir without docs should not become a collection.
    assert "programs" not in collections


def test_default_collection_uses_root_files_only(tmp_path):
    root = tmp_path / "rag_data"
    root.mkdir()
    (root / "root.md").write_text("# Root\n\nкорневой документ для default коллекции", encoding="utf-8")
    (root / "game10").mkdir()
    (root / "game10" / "only.md").write_text("# G10\n\nтолько в game10", encoding="utf-8")

    store = RagStore(data_dir=str(root))
    default_chunks = store.load_chunks(collection_dir=store.list_collections()["default"])
    game10_chunks = store.load_chunks(collection_dir=store.list_collections()["game10"])

    assert any("корневой" in chunk.text for chunk in default_chunks)
    assert not any("только в game10" in chunk.text for chunk in default_chunks)
    assert any("только в game10" in chunk.text for chunk in game10_chunks)
