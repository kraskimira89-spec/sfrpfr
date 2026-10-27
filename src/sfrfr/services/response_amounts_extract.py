"""Извлечение сумм пенсии из OCR/текста ответа СФР (ступень 11).

Не обещает выплату: только цифры, явно указанные в документе, для проверки сотрудником.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Literal, Protocol

from sfrfr.ai.guardrails import redact_for_llm

logger = logging.getLogger(__name__)

SYSTEM = """Ты извлекаешь ЧИСЛА из текста ответа/решения СФР для проверки сотрудником.

Правила:
- бери только суммы, явно написанные в тексте (как было / как стало / единовременная);
- не выдумывай и не округляй «примерно»; если суммы нет — null;
- chronology: по каждому файлу дата документа (если есть), имя файла и краткая заметка по суммам;
- ответь ТОЛЬКО JSON-объектом без пояснений:
{
  "monthly_before_rub": number|null,
  "monthly_after_rub": number|null,
  "lump_sum_rub": number|null,
  "chronology": [{"date": "YYYY-MM-DD"|null, "filename": string, "note": string}],
  "source_quote": string|null
}
- положительный ответ СФР ≠ фактическая выплата; ты только читаешь цифры.
"""


class _LLM(Protocol):
    @property
    def available(self) -> bool: ...

    def chat(self, *, system: str, user: str, temperature: float = 0.0) -> str: ...


def _as_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        n = float(value)
        return n if n >= 0 else None
    raw = str(value).strip().replace("\u00a0", " ").replace(" ", "").replace(",", ".")
    raw = re.sub(r"[^\d.]+", "", raw)
    if not raw:
        return None
    try:
        n = float(raw)
    except ValueError:
        return None
    return n if n >= 0 else None


def _extract_json_object(raw: str) -> dict[str, Any] | None:
    text = (raw or "").strip()
    if not text:
        return None
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL | re.IGNORECASE)
    if fence:
        text = fence.group(1)
    else:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            text = text[start : end + 1]
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def parse_amounts_payload(raw: str) -> dict[str, Any]:
    data = _extract_json_object(raw) or {}
    chronology_raw = data.get("chronology")
    chronology: list[dict[str, Any]] = []
    if isinstance(chronology_raw, list):
        for row in chronology_raw:
            if not isinstance(row, dict):
                continue
            filename = str(row.get("filename") or "").strip()[:240]
            note = str(row.get("note") or "").strip()[:500]
            date_raw = row.get("date")
            date_s = None
            if date_raw:
                date_s = str(date_raw).strip()[:10] or None
            if filename or note or date_s:
                chronology.append(
                    {"date": date_s, "filename": filename or "—", "note": note}
                )
    quote = data.get("source_quote")
    return {
        "monthly_before_rub": _as_float(data.get("monthly_before_rub")),
        "monthly_after_rub": _as_float(data.get("monthly_after_rub")),
        "lump_sum_rub": _as_float(data.get("lump_sum_rub")),
        "chronology": chronology,
        "source_quote": (str(quote).strip()[:800] if quote else None) or None,
    }


def extract_amounts_from_texts(
    *,
    case_ref: str,
    snippets: list[dict[str, str]],
    llm: _LLM | Literal["auto"] | None = "auto",
) -> dict[str, Any]:
    empty: dict[str, Any] = {
        "monthly_before_rub": None,
        "monthly_after_rub": None,
        "lump_sum_rub": None,
        "chronology": [],
        "source_quote": None,
        "source": "template",
        "reason": "no_text",
    }
    usable = [
        s
        for s in snippets
        if isinstance(s, dict) and str(s.get("text") or "").strip()
    ]
    if not usable:
        return empty

    client: _LLM | None
    if llm == "auto":
        from sfrfr.ai.llm import LLMClient

        client = LLMClient.for_analyze(allow_fallback=True, foreign_ok=True)
    else:
        client = llm  # type: ignore[assignment]

    if client is None or not getattr(client, "available", False):
        # Без ИИ — хронология по именам файлов, суммы пустые.
        return {
            **empty,
            "chronology": [
                {
                    "date": None,
                    "filename": str(s.get("filename") or "файл")[:240],
                    "note": "текст есть, суммы не извлечены (ИИ недоступен)",
                }
                for s in usable
            ],
            "source": "template",
            "reason": "llm_unavailable",
        }

    blocks: list[str] = []
    for s in usable[:8]:
        name = str(s.get("filename") or "файл")[:120]
        text = redact_for_llm(str(s.get("text") or ""))[:3500]
        blocks.append(f"### Файл: {name}\n{text}")
    user = (
        f"Дело (без ПДн): {redact_for_llm(case_ref)}\n\n"
        f"Тексты ответов СФР:\n\n" + "\n\n".join(blocks) + "\n\n"
        "Извлеки суммы строго по правилам system. Только JSON."
    )
    try:
        raw = client.chat(system=SYSTEM, user=user, temperature=0.0)
    except Exception as exc:  # noqa: BLE001
        logger.warning("amounts extract llm_error %s", type(exc).__name__)
        return {**empty, "reason": "llm_error", "source": "template"}

    parsed = parse_amounts_payload(str(raw or ""))
    if (
        parsed["monthly_before_rub"] is None
        and parsed["monthly_after_rub"] is None
        and parsed["lump_sum_rub"] is None
        and not parsed["chronology"]
    ):
        return {
            **parsed,
            "chronology": [
                {
                    "date": None,
                    "filename": str(s.get("filename") or "файл")[:240],
                    "note": "суммы в тексте не найдены",
                }
                for s in usable
            ],
            "source": "ai",
            "reason": "no_amounts_in_text",
            "llm_provider": getattr(client, "last_provider_used", None)
            or getattr(client, "provider", None),
        }
    return {
        **parsed,
        "source": "ai",
        "reason": None,
        "llm_provider": getattr(client, "last_provider_used", None)
        or getattr(client, "provider", None),
    }
