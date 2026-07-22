"""Guardrails: маскирование ПДн перед вызовом LLM."""

from __future__ import annotations

import re

from sfrfr.utils.redact_pii import mask_snils, redact_fio

_SNILS_RE = re.compile(r"\b\d{3}[-\s]?\d{3}[-\s]?\d{3}[-\s]?\d{2}\b")
_PASSPORT_RE = re.compile(r"\b\d{4}\s?\d{6}\b")


def redact_for_llm(text: str, *, client_name: str | None = None) -> str:
    """Маскирует СНИЛС, паспорт и (опционально) ФИО перед отправкой в модель."""
    out = _SNILS_RE.sub(lambda m: mask_snils(m.group(0)), text)
    out = _PASSPORT_RE.sub("**** ******", out)
    if client_name and client_name.strip():
        redacted = redact_fio(client_name)
        # грубая замена полного ФИО, если встречается в тексте
        out = out.replace(client_name, redacted)
    return out
