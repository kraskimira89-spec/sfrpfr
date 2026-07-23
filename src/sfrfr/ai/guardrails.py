"""Guardrails: маскирование ПДн и пометки черновиков перед LLM / выдачей."""

from __future__ import annotations

from sfrfr.ai.pii.depersonalize import depersonalize_text
from sfrfr.ai.schemas.agents import DraftResult


def redact_for_llm(text: str, *, client_name: str | None = None) -> str:
    """Маскирует ПДн перед отправкой в модель (обёртка над depersonalize_text)."""
    return depersonalize_text(text, client_name=client_name)


def ensure_needs_human_review(draft: DraftResult) -> DraftResult:
    """Критерий ТЗ-08: черновик заявления всегда с needs_human_review=True."""
    if draft.needs_human_review:
        return draft
    return draft.model_copy(update={"needs_human_review": True})
