"""Извлечение сумм пенсии из OCR/текста входящих ответов (ступень 11).

Не обещает выплату: только цифры из документа для проверки сотрудником.
null / «Не указано» — не ноль; назначено ≠ деньги получены.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Literal, Protocol

from sfrfr.ai.guardrails import redact_for_llm

logger = logging.getLogger(__name__)

AMOUNT_KINDS = frozenset(
    {"total_pension", "component", "increase", "arrears", "other"}
)
PAYMENT_STATUSES = frozenset(
    {"appointed", "accrued", "paid_confirmed", "unknown"}
)

SYSTEM = """Ты извлекаешь ЧИСЛА из текстов входящих ответов органов для проверки сотрудником.

Правила:
- бери только суммы, явно написанные в тексте;
- не выдумывай; если суммы нет — null (не 0);
- различай: общий размер пенсии (total_pension), составляющую (component),
  прибавку/увеличение (increase), задолженность/доплату за период (arrears);
- «назначено к выплате» / «начислено» ≠ «деньги получены»; paid_confirmed только
  при отдельном подтверждении фактической выплаты;
- не складывай единовременные суммы из разных файлов автоматически (могут описывать одно и то же);
- если документы противоречат — две строки chronology с одним conflict_group и warnings;
- хронологию строй по effective_date (дата, с которой изменён размер); если нет —
  effective_date=null (в UI «не указана»); отдельно document_date / received_date если есть;
- у каждой строки: filename, page (если есть), basis_quote (короткая цитата);
- ответь ТОЛЬКО JSON без пояснений:
{
  "monthly_before_rub": number|null,
  "monthly_after_rub": number|null,
  "monthly_increase_rub": number|null,
  "lump_sum_rub": number|null,
  "chronology": [{
    "effective_date": "YYYY-MM-DD"|null,
    "document_date": "YYYY-MM-DD"|null,
    "received_date": "YYYY-MM-DD"|null,
    "filename": string,
    "page": string|null,
    "monthly_before_rub": number|null,
    "monthly_after_rub": number|null,
    "lump_sum_rub": number|null,
    "amount_kind": "total_pension"|"component"|"increase"|"arrears"|"other",
    "payment_status": "appointed"|"accrued"|"paid_confirmed"|"unknown",
    "basis_quote": string,
    "conflict_group": string|null,
    "note": string
  }],
  "warnings": [string],
  "source_quote": string|null
}
- положительный ответ органа ≠ фактическая выплата.
"""


class _LLM(Protocol):
    @property
    def available(self) -> bool: ...

    def chat(self, *, system: str, user: str, temperature: float = 0.0) -> str: ...


def _as_float(value: Any, *, allow_zero: bool = False) -> float | None:
    """0 без явной цитаты трактуем как null, если allow_zero=False и нет контекста."""
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        n = float(value)
        if n < 0:
            return None
        if n == 0 and not allow_zero:
            return None
        return n
    raw = str(value).strip().replace("\u00a0", " ").replace(" ", "").replace(",", ".")
    raw = re.sub(r"[^\d.]+", "", raw)
    if not raw:
        return None
    try:
        n = float(raw)
    except ValueError:
        return None
    if n < 0:
        return None
    if n == 0 and not allow_zero:
        return None
    return n


def _date_or_none(value: Any) -> str | None:
    if not value:
        return None
    s = str(value).strip()[:10]
    return s or None


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


def _parse_chrono_row(row: dict[str, Any]) -> dict[str, Any] | None:
    filename = str(row.get("filename") or "").strip()[:240]
    note = str(row.get("note") or "").strip()[:500]
    quote = str(row.get("basis_quote") or "").strip()[:500]
    kind = str(row.get("amount_kind") or "other").strip().lower()
    if kind not in AMOUNT_KINDS:
        kind = "other"
    status = str(row.get("payment_status") or "unknown").strip().lower()
    if status not in PAYMENT_STATUSES:
        status = "unknown"
    page = row.get("page")
    page_s = str(page).strip()[:40] if page not in (None, "") else None
    conflict = row.get("conflict_group")
    conflict_s = str(conflict).strip()[:80] if conflict else None
    # Явный 0 в строке с цитатой допускаем только если есть basis_quote.
    allow0 = bool(quote)
    before = _as_float(row.get("monthly_before_rub"), allow_zero=allow0)
    after = _as_float(row.get("monthly_after_rub"), allow_zero=allow0)
    lump = _as_float(row.get("lump_sum_rub"), allow_zero=allow0)
    eff = _date_or_none(row.get("effective_date") or row.get("date"))
    has_amt = before is not None or after is not None or lump is not None
    if not (filename or note or quote or eff or has_amt):
        return None
    return {
        "effective_date": eff,
        "document_date": _date_or_none(row.get("document_date")),
        "received_date": _date_or_none(row.get("received_date")),
        "filename": filename or "—",
        "page": page_s,
        "monthly_before_rub": before,
        "monthly_after_rub": after,
        "lump_sum_rub": lump,
        "amount_kind": kind,
        "payment_status": status,
        "basis_quote": quote or None,
        "conflict_group": conflict_s,
        "note": note,
        # legacy alias for older UI
        "date": eff,
    }


def parse_amounts_payload(raw: str) -> dict[str, Any]:
    data = _extract_json_object(raw) or {}
    chronology_raw = data.get("chronology")
    chronology: list[dict[str, Any]] = []
    if isinstance(chronology_raw, list):
        for row in chronology_raw:
            if not isinstance(row, dict):
                continue
            parsed = _parse_chrono_row(row)
            if parsed:
                chronology.append(parsed)
    warnings_raw = data.get("warnings")
    warnings: list[str] = []
    if isinstance(warnings_raw, list):
        for w in warnings_raw:
            s = str(w or "").strip()
            if s:
                warnings.append(s[:400])
    quote = data.get("source_quote")
    return {
        "monthly_before_rub": _as_float(data.get("monthly_before_rub")),
        "monthly_after_rub": _as_float(data.get("monthly_after_rub")),
        "monthly_increase_rub": _as_float(data.get("monthly_increase_rub")),
        "lump_sum_rub": _as_float(data.get("lump_sum_rub")),
        "chronology": chronology,
        "warnings": warnings,
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
        "monthly_increase_rub": None,
        "lump_sum_rub": None,
        "chronology": [],
        "warnings": [],
        "source_quote": None,
        "source": "template",
        "reason": "no_text",
        "partial": False,
    }
    usable = [
        s
        for s in snippets
        if isinstance(s, dict) and str(s.get("text") or "").strip()
    ]
    missing = [
        str(s.get("filename") or s.get("document_id") or "файл")
        for s in snippets
        if isinstance(s, dict) and not str(s.get("text") or "").strip()
    ]
    partial = bool(missing) and bool(usable)
    if not usable:
        out = {**empty, "warnings": [f"нет текста OCR: {n}" for n in missing[:8]]}
        if missing:
            out["reason"] = "no_text"
            out["partial"] = True
        return out

    client: _LLM | None
    if llm == "auto":
        from sfrfr.ai.llm import LLMClient

        client = LLMClient.for_analyze(allow_fallback=True, foreign_ok=True)
    else:
        client = llm  # type: ignore[assignment]

    if client is None or not getattr(client, "available", False):
        warn = ["ИИ недоступен — суммы не извлечены"]
        if missing:
            warn.extend(f"нет OCR: {n}" for n in missing[:6])
        return {
            **empty,
            "chronology": [
                {
                    "effective_date": None,
                    "document_date": None,
                    "received_date": None,
                    "filename": str(s.get("filename") or "файл")[:240],
                    "page": None,
                    "monthly_before_rub": None,
                    "monthly_after_rub": None,
                    "lump_sum_rub": None,
                    "amount_kind": "other",
                    "payment_status": "unknown",
                    "basis_quote": None,
                    "conflict_group": None,
                    "note": "текст есть, суммы не извлечены (ИИ недоступен)",
                    "date": None,
                }
                for s in usable
            ],
            "warnings": warn,
            "source": "template",
            "reason": "llm_unavailable",
            "partial": partial,
        }

    blocks: list[str] = []
    for s in usable[:8]:
        name = str(s.get("filename") or "файл")[:120]
        text = redact_for_llm(str(s.get("text") or ""))[:3500]
        blocks.append(f"### Файл: {name}\n{text}")
    user = (
        f"Дело (без ПДн): {redact_for_llm(case_ref)}\n\n"
        f"Тексты входящих ответов:\n\n" + "\n\n".join(blocks) + "\n\n"
        "Извлеки суммы строго по правилам system. Только JSON."
    )
    try:
        raw = client.chat(system=SYSTEM, user=user, temperature=0.0)
    except Exception as exc:  # noqa: BLE001
        logger.warning("amounts extract llm_error %s", type(exc).__name__)
        return {
            **empty,
            "reason": "llm_error",
            "source": "template",
            "partial": partial,
            "warnings": [f"нет OCR: {n}" for n in missing[:6]],
        }

    parsed = parse_amounts_payload(str(raw or ""))
    warn = list(parsed.get("warnings") or [])
    if missing:
        warn.extend(f"нет OCR: {n}" for n in missing[:6])
        parsed["partial"] = True
    else:
        parsed["partial"] = False
    parsed["warnings"] = warn

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
                    "effective_date": None,
                    "document_date": None,
                    "received_date": None,
                    "filename": str(s.get("filename") or "файл")[:240],
                    "page": None,
                    "monthly_before_rub": None,
                    "monthly_after_rub": None,
                    "lump_sum_rub": None,
                    "amount_kind": "other",
                    "payment_status": "unknown",
                    "basis_quote": None,
                    "conflict_group": None,
                    "note": "суммы в тексте не найдены",
                    "date": None,
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
