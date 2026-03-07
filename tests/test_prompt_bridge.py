from __future__ import annotations

from core.ai.prompt_bridge import load_policy_prompt, rag_policy_hint


def test_policy_prompt_loader_uses_prompts_module_source():
    payload = load_policy_prompt()
    assert payload.source == "core/ai/prompts.py"
    assert isinstance(payload.content, str)
    assert payload.content.strip() != ""


def test_rag_policy_hint_mentions_policy_and_rag_separation():
    hint = rag_policy_hint().lower()
    assert "policy" in hint
    assert "rag" in hint
