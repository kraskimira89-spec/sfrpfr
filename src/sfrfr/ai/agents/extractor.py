"""Агент: извлечение периодов из OCR-текста."""

from __future__ import annotations

import json
import re

from sfrfr.ai.guardrails import redact_for_llm
from sfrfr.ai.llm import LLMClient
from sfrfr.ai.prompts import EXTRACT_SYSTEM
from sfrfr.ai.schemas.agents import ExtractResult, Period

_DATE_RE = re.compile(r"\b(\d{2}[./]\d{2}[./]\d{4}|\d{4}-\d{2}-\d{2})\b")


def extract_periods(
    text: str,
    *,
    client_name: str | None = None,
    llm: LLMClient | None = None,
) -> ExtractResult:
    """Извлечение периодов: LLM (если есть ключ) или грубая эвристика по датам."""
    safe = redact_for_llm(text, client_name=client_name)
    llm = llm or LLMClient()

    if llm.available:
        raw = llm.chat(system=EXTRACT_SYSTEM, user=safe[:6000])
        try:
            data = json.loads(raw)
            return ExtractResult.model_validate(data)
        except (json.JSONDecodeError, ValueError):
            pass

    dates = _DATE_RE.findall(safe)
    periods: list[Period] = []
    if len(dates) >= 2:
        periods.append(Period(date_from=dates[0], date_to=dates[1]))
    elif len(dates) == 1:
        periods.append(Period(date_from=dates[0], date_to=None))

    return ExtractResult(periods=periods, raw_hints=[f"dates_found={len(dates)}"])
