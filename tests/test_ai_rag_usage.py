from __future__ import annotations

import asyncio
from types import SimpleNamespace

from core.ai.ai_service import AIService


class _DummyCompletions:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))]
        )


class _DummyClient:
    def __init__(self) -> None:
        self.chat = SimpleNamespace(completions=_DummyCompletions())


async def _empty_event_context(*args, **kwargs):
    return "", {"user_events": 0, "consultations": 0, "active_events": 0, "catalog": 0, "webhooks": 0}


def _write_doc(path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_ai_service_uses_rag_and_falls_back_to_default(monkeypatch, tmp_path):
    rag_root = tmp_path / "rag_data"
    _write_doc(rag_root / "default.md", "# Default\n\nТревога и напряжение. Консультации и поддержка.")
    _write_doc(rag_root / "game10" / "overview.md", "# Game10\n\nМатериал про игру и сообщество.")

    monkeypatch.setenv("RAG_ENABLED", "true")
    monkeypatch.setenv("RAG_DATA_DIR", str(rag_root))
    service = AIService(api_key=None)
    service.client = _DummyClient()
    service._event_context = _empty_event_context  # type: ignore[method-assign]

    response = asyncio.run(
        service.get_response("[FOCUS:game10]\nтревога и поддержка", include_events=True, response_mode="auto_lite")
    )

    assert response == "ok"
    trace = service.get_last_trace()
    assert trace["rag_used"] is True
    assert trace["rag_collection"] == "default"
    assert trace["rag_fallback_to_default"] is True
    assert isinstance(trace["fallback_to_model"], bool)

    calls = service.client.chat.completions.calls
    assert calls, "AI client should receive a request"
    messages = calls[-1]["messages"]
    system_texts = [msg["content"] for msg in messages if msg.get("role") == "system"]
    assert any("тревога" in str(text).lower() for text in system_texts)


def test_ai_service_autodiscovers_nested_collection(monkeypatch, tmp_path):
    rag_root = tmp_path / "rag_data"
    _write_doc(rag_root / "faq.md", "# FAQ\n\nОбщий контент.")
    _write_doc(
        rag_root / "programs" / "supervision" / "program.md",
        "# Супервизорская группа\n\nСупервизорская группа для психологов и практиков.",
    )

    monkeypatch.setenv("RAG_ENABLED", "true")
    monkeypatch.setenv("RAG_DATA_DIR", str(rag_root))
    service = AIService(api_key=None)
    service.client = _DummyClient()
    service._event_context = _empty_event_context  # type: ignore[method-assign]

    asyncio.run(
        service.get_response(
            "[FOCUS:programs/supervision]\nсупервизорская группа для психологов",
            include_events=True,
        )
    )

    trace = service.get_last_trace()
    assert trace["rag_used"] is True
    assert trace["rag_collection"] == "programs/supervision"
    snapshot = service.rag_debug_snapshot("супервизорская группа")
    assert "programs/supervision" in snapshot.get("discovered_collections", [])


def test_ai_service_prioritizes_payment_routes_for_payment_intent(monkeypatch, tmp_path):
    rag_root = tmp_path / "rag_data"
    _write_doc(
        rag_root / "game10" / "overview.md",
        "# Game10\n\nИгра 10:0 игра 10:0 игра 10:0. Это описание программы и контента сообщества.",
    )
    _write_doc(
        rag_root / "payment_routes" / "payment_routes.json",
        """{
  "updated_at": "2026-03-07",
  "routes": [
    {
      "route_key": "payment-game10-main",
      "product_key": "game10-main",
      "product_title": "Игра 10:0",
      "status": "active",
      "payment_type": "online_checkout",
      "provider": "YooKassa",
      "entry_point": {
        "from_section": "game10_menu",
        "button_title": "Оплатить 5 000 ₽"
      },
      "payment_screen": {
        "elements": ["QR-код", "кнопка «Открыть оплату»"]
      },
      "open_payment": {
        "button_title": "Открыть оплату",
        "provider": "YooKassa",
        "link_ttl_minutes": 10
      },
      "verification": {
        "button_title": "Я оплатил — проверить",
        "success_result": "Бот отправляет ссылку на закрытую группу."
      },
      "refresh": {
        "button_title": "Обновить ссылку"
      },
      "fallback_if_no_access": {
        "assistant_message": "Если доступ не пришёл, перейдите в «Связаться с менеджером»."
      }
    }
  ]
}""",
    )

    monkeypatch.setenv("RAG_ENABLED", "true")
    monkeypatch.setenv("RAG_DATA_DIR", str(rag_root))
    service = AIService(api_key=None)
    service.client = _DummyClient()
    service._event_context = _empty_event_context  # type: ignore[method-assign]

    response = asyncio.run(service.get_response("как оплатить игру 10:0?", include_events=True))
    assert response == "ok"

    calls = service.client.chat.completions.calls
    assert calls, "AI client should receive a request"
    system_texts = [str(msg.get("content") or "") for msg in calls[-1]["messages"] if msg.get("role") == "system"]
    rag_context = next((text for text in system_texts if "Knowledge context (facts):" in text), "")
    assert rag_context
    rag_lines = [line for line in rag_context.splitlines() if line.strip()]
    assert len(rag_lines) >= 2
    assert "[payment_routes/" in rag_lines[1]
    assert "assistant_steps:" in rag_context
    assert "entry_button_title:" in rag_context
    assert "exact information is not available yet" not in "\n".join(system_texts)

    trace = service.get_last_trace()
    assert trace.get("payment_intent") is True
    assert trace.get("payment_routes_prioritized") is True
    assert trace.get("payment_route_actionable") is True
