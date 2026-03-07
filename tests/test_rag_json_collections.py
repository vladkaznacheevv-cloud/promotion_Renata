from __future__ import annotations

from core.rag import RagRetriever, RagStore


def _write(path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_menu_navigation_sections_json_is_expanded_to_route_records(tmp_path):
    root = tmp_path / "rag_data"
    _write(
        root / "menu_navigation" / "menu_routes.json",
        """{
  "updated_at": "2026-03-07",
  "sections": [
    {
      "section_key": "help_menu",
      "section_title": "Помощь",
      "status": "active",
      "buttons": [
        {
          "button_key": "btn_help",
          "button_title": "Помощь",
          "aliases": ["где кнопка помощь", "как открыть помощь"],
          "assistant_hint": "Используется, когда нужно подсказать раздел помощи.",
          "fallback_text": "Нажмите кнопку «Помощь».",
          "status": "active",
          "priority": 100
        }
      ]
    }
  ]
}""",
    )

    store = RagStore(data_dir=str(root))
    chunks = store.load_chunks(collection_dir=str(root / "menu_navigation"))
    assert chunks, "expected route chunks from sections/buttons"

    help_button_chunks = [c for c in chunks if (c.metadata or {}).get("slug") == "btn_help"]
    assert help_button_chunks, "button record must be indexed as a separate chunk"
    metadata = help_button_chunks[0].metadata
    assert metadata.get("collection") == "menu_navigation"
    assert metadata.get("doc_type") == "route"
    assert metadata.get("status") == "active"
    assert metadata.get("section") == "help_menu"

    retriever = RagRetriever(store=store)
    result = retriever.retrieve(
        query="где кнопка помощь",
        collection_dir=str(root / "menu_navigation"),
        statuses=("active",),
    )
    assert result.top_chunks
    assert any((hit.metadata or {}).get("slug") == "btn_help" for hit in result.top_chunks)


def test_payment_routes_json_is_expanded_and_filters_statuses(tmp_path):
    root = tmp_path / "rag_data"
    _write(
        root / "payment_routes" / "payment_routes.json",
        """{
  "updated_at": "2026-03-07",
  "routes": [
    {
      "route_key": "payment-game10-main",
      "product_key": "game10-main",
      "product_title": "Игра 10:0",
      "status": "active",
      "payment_type": "online_checkout",
      "entry_point": {
        "from_section": "game10_menu",
        "button_title": "Оплатить 5 000 ₽"
      },
      "verification": {
        "button_title": "Я оплатил — проверить"
      },
      "fallback_if_no_access": {
        "assistant_message": "Если после оплаты не пришёл доступ, свяжитесь с менеджером."
      }
    },
    {
      "route_key": "payment-archive",
      "product_key": "archive",
      "product_title": "Архивный маршрут",
      "status": "archived",
      "payment_type": "online_checkout"
    }
  ]
}""",
    )

    store = RagStore(data_dir=str(root))
    chunks = store.load_chunks(collection_dir=str(root / "payment_routes"))
    assert chunks, "expected route chunks from payment routes"
    active_chunks = [c for c in chunks if (c.metadata or {}).get("slug") == "payment-game10-main"]
    assert active_chunks
    assert active_chunks[0].metadata.get("section") == "game10_menu"
    active_text = active_chunks[0].text.lower().replace("ё", "е")
    assert "assistant_steps:" in active_text
    assert "entry_button_title: оплатить 5 000 ₽".lower().replace("ё", "е") in active_text
    assert "verification_button_title:" in active_text
    assert "fallback_no_access_message:" in active_text

    retriever = RagRetriever(store=store)
    result = retriever.retrieve(
        query="не пришел доступ после оплаты",
        collection_dir=str(root / "payment_routes"),
        statuses=("active",),
    )
    assert result.top_chunks
    statuses = {(hit.metadata or {}).get("status") for hit in result.top_chunks}
    assert statuses == {"active"}
    assert any((hit.metadata or {}).get("slug") == "payment-game10-main" for hit in result.top_chunks)

    pay_result = retriever.retrieve(
        query="как оплатить игру 10:0",
        collection_dir=str(root / "payment_routes"),
        statuses=("active",),
    )
    assert pay_result.top_chunks
    assert (pay_result.top_chunks[0].metadata or {}).get("slug") == "payment-game10-main"
