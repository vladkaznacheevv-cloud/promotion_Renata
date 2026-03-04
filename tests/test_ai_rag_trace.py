from __future__ import annotations

import asyncio
from types import SimpleNamespace

from core.ai.ai_service import AIService


class _DummyCompletions:
    def create(self, **kwargs):
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))])


class _DummyClient:
    def __init__(self) -> None:
        self.chat = SimpleNamespace(completions=_DummyCompletions())


async def _empty_event_context(*args, **kwargs):
    return "", {"user_events": 0, "consultations": 0, "active_events": 0, "catalog": 0, "webhooks": 0}


def _write(path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _service_for(rag_root, monkeypatch) -> AIService:
    monkeypatch.setenv("RAG_ENABLED", "true")
    monkeypatch.setenv("RAG_DATA_DIR", str(rag_root))
    service = AIService(api_key=None)
    service.client = _DummyClient()
    service._event_context = _empty_event_context  # type: ignore[method-assign]
    return service


def test_ai_rag_trace_uses_game10_collection_when_present(monkeypatch, tmp_path):
    rag_root = tmp_path / "rag_data"
    _write(rag_root / "game10" / "overview.md", "# Game10\n\nИгра 10:0 — закрытое сообщество.")
    _write(rag_root / "default.md", "# Default\n\nОбщий материал.")
    service = _service_for(rag_root, monkeypatch)

    asyncio.run(service.get_response("[FOCUS:GAME10]\nчто такое игра 10:0", include_events=True))
    trace = service.get_last_trace()

    assert trace.get("rag_requested_collection") == "game10"
    assert trace.get("rag_used_collection") == "game10"
    assert trace.get("rag_hits", 0) >= 1


def test_ai_rag_trace_falls_back_to_default_when_focus_collection_empty(monkeypatch, tmp_path):
    rag_root = tmp_path / "rag_data"
    (rag_root / "game10").mkdir(parents=True, exist_ok=True)
    _write(rag_root / "default.md", "# Default\n\nИгра 10:0 и ответы по продукту.")
    service = _service_for(rag_root, monkeypatch)

    asyncio.run(service.get_response("[FOCUS:GAME10]\nигра 10:0", include_events=True))
    trace = service.get_last_trace()

    assert trace.get("rag_requested_collection") == "game10"
    assert trace.get("rag_used_collection") == "default"
    assert trace.get("rag_fallback_to_default") is True
    assert isinstance(trace.get("fallback_to_model"), bool)
