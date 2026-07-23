"""Guardrails: маскирование ПДн перед вызовом LLM."""

from __future__ import annotations

from sfrfr.ai.pii.depersonalize import depersonalize_text


def redact_for_llm(text: str, *, client_name: str | None = None) -> str:
    """Маскирует ПДн перед отправкой в модель (обёртка над depersonalize_text)."""
    return depersonalize_text(text, client_name=client_name)
