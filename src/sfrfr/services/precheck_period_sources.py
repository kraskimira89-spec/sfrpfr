"""Периоды для предпроверки: pipeline или эфемерное извлечение.

Не пишет в case_pipeline_data — не затирает staff_date_correction.
Пустой pipeline ≠ отсутствие стажа; ошибка OCR ≠ отсутствие расхождений.
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
    if ils and labor:
        return "periods_ready"
    if ils or labor:
        # Одна сторона — частичное извлечение, не полный комплект.
        return "extract_partial"
    if extract_error:
        return "extract_failed"
    if not extract_attempted:
        return "extract_not_run"
    return "extract_empty_unreadable"


def _doc_text_candidates(doc: dict[str, Any]) -> list[tuple[str, str]]:
    """(source_tag, text) из сохранённых артефактов OCR/extract без полного re-OCR."""
    out: list[tuple[str, str]] = []
    for key, tag in (
        ("text_sample", "text_sample"),
        ("content_preview", "content_preview"),
        ("ocr_text", "ocr_artifact"),
        ("extracted_text", "extracted_text"),
        ("text_content", "text_content"),
    ):
        raw = str(doc.get(key) or "").strip()
        if not raw:
            continue
        if raw.startswith("[ocr_"):
            # маркер «OCR не готов / failed» — не текст периодов
            continue
        out.append((tag, raw))
    return out


def periods_for_precheck(
    *,
    pipeline_row: dict[str, Any] | None,
    analyzed_documents: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str, str | None]:
    """Вернуть (ils, labor, source_state, extract_error).

    При пустом pipeline — эфемерный extract по пригодным артефактам.
    Каждая запись периода помечается value_source / extract_provenance.
    """
    row = pipeline_row or {}
    ils = [dict(p) for p in (row.get("ils_periods") or []) if isinstance(p, dict)]
    labor = [dict(p) for p in (row.get("labor_periods") or []) if isinstance(p, dict)]
    if ils or labor:
        for p in ils + labor:
            p.setdefault("value_source", "pipeline")
            p.setdefault("extract_provenance", "case_pipeline_data")
        state = classify_period_source_state(
            has_documents=True,
            ils=ils,
            labor=labor,
            extract_attempted=False,
            extract_error=None,
        )
        return ils, labor, state, None

    if not analyzed_documents:
        return [], [], "documents_missing", None

    extract_error: str | None = None
    ils_out: list[dict[str, Any]] = []
    labor_out: list[dict[str, Any]] = []
    tried = False
    for doc in analyzed_documents:
        if not isinstance(doc, dict):
            continue
        candidates = _doc_text_candidates(doc)
        if not candidates:
            continue
        tried = True
        guessed = str(doc.get("guessed_type") or doc.get("doc_type") or "").lower()
        tag, text = candidates[0]
        try:
            extracted = extract_periods(text)
        except Exception as exc:  # noqa: BLE001
            extract_error = type(exc).__name__
            continue
        periods: list[dict[str, Any]] = []
        for item in extracted.periods or []:
            raw_obj: Any = (
                item.model_dump() if hasattr(item, "model_dump") else item
            )
            raw = dict(raw_obj) if isinstance(raw_obj, dict) else {}
            if not raw:
                continue
            raw.setdefault("period_id", f"ephem:{doc.get('id')}:{len(periods)}")
            raw.setdefault("employer", raw.get("employer") or "не указан")
            raw["value_source"] = "ephemeral_extract"
            raw["extract_provenance"] = tag
            raw["source_document_id"] = str(doc.get("id") or "")
            periods.append(raw)
        blob = text.casefold()
        if "ils" in guessed or "сзи" in guessed or "лицевой" in blob:
            ils_out.extend(periods)
        elif "labor" in guessed or "труд" in guessed or "workbook" in guessed:
            labor_out.extend(periods)
        else:
            labor_out.extend(periods)

    state = classify_period_source_state(
        has_documents=True,
        ils=ils_out,
        labor=labor_out,
        extract_attempted=tried,
        extract_error=extract_error,
    )
    return ils_out, labor_out, state, extract_error
