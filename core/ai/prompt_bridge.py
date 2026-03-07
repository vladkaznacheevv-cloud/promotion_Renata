from __future__ import annotations

from dataclasses import dataclass

from core.ai.prompts import SYSTEM_PROMPT

POLICY_PROMPT_SOURCE = "core/ai/prompts.py"


@dataclass(slots=True)
class PolicyPrompt:
    source: str
    content: str


def load_policy_prompt() -> PolicyPrompt:
    return PolicyPrompt(
        source=POLICY_PROMPT_SOURCE,
        content=(SYSTEM_PROMPT or "").strip(),
    )


def rag_policy_hint() -> str:
    return (
        "Policy layer is fixed by SYSTEM_PROMPT from core/ai/prompts.py. "
        "RAG context is factual knowledge only (products, events, programs, menu routes, payment routes). "
        "If exact facts are missing, say so and suggest уточнение у менеджера."
    )
