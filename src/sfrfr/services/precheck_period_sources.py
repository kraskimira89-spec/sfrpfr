"""Периоды для предпроверки: pipeline или эфемерное извлечение.

Не пишет в case_pipeline_data — не затирает staff_date_correction.
"""

from __future__ import annotations

from typing import Any

from sfrfr.ai.agents.extractor import extract_periods


def classify_period_source_state(
    *,
    has_documents: bool,
    ils: list[dict[str, Any]],
    labor: list[dict[str, Any]],
    extract_attempted: bool,
    extract_error: str | None,
) -> str:
    if not has_documents:
        return "documents_missing"
    if ils or labor:
        return "periods_ready"
    if extract_error:
        return "extract_failed"
    if not extract_attempted:
        return "extract_not_run"
    return "extract_empty_unreadable"


def periods_for_precheck(
    *,
    pipeline_row: dict[str, Any] | None,
    analyzed_documents: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str, str | None]:
    """Вернуть (ils, labor, source_state, extract_error)."""
    row = pipeline_row or {}
    ils = [dict(p) for p in (row.get("ils_periods") or []) if isinstance(p, dict)]
    labor = [dict(p) for p in (row.get("labor_periods") or []) if isinstance(p, dict)]
    if ils or labor:
        return ils, labor, "periods_ready", None

    if not analyzed_documents:
        return [], [], "documents_missing", None

    extract_error: str | None = None
    ils_out: list[dict[str, Any]] = []
    labor_out: list[dict[str, Any]] = []
    tried = False
    for doc in analyzed_documents:
        if not isinstance(doc, dict):
            continue
        text = str(doc.get("text_sample") or doc.get("content_preview") or "").strip()
        if not text or text.startswith("[ocr_"):
            continue
        tried = True
        guessed = str(doc.get("guessed_type") or doc.get("doc_type") or "").lower()
        try:
            extracted = extract_periods(text)
        except Exception as exc:  # noqa: BLE001
            extract_error = type(exc).__name__
            continue
        periods = []
        for p in extracted.periods or []:
            raw = p.model_dump() if hasattr(p, "model_dump") else dict(p)  # type: ignore[arg-type]
            if not isinstance(raw, dict):
                continue
            raw.setdefault("period_id", f"ephem:{doc.get('id')}:{len(periods)}")
            raw.setdefault("employer", raw.get("employer") or "не указан")
            raw["value_source"] = "ocr_extract"
            periods.append(raw)
        if "ils" in guessed or "сзи" in guessed or "лицевой" in text.casefold():
            ils_out.extend(periods)
        elif "labor" in guessed or "труд" in guessed or "workbook" in guessed:
            labor_out.extend(periods)
        else:
            # неизвестный тип — в labor как подтверждающий документ
            labor_out.extend(periods)

    state = classify_period_source_state(
        has_documents=True,
        ils=ils_out,
        labor=labor_out,
        extract_attempted=tried,
        extract_error=extract_error,
    )
    return ils_out, labor_out, state, extract_error
