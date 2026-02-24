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
