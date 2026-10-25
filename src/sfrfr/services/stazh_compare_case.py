"""Сверка ИЛС с трудовой для «Проверить документы»: полный текст файлов → расхождения в резюме."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import date
from typing import Any

from sfrfr.core.stazh_compare import compare_stazh
from sfrfr.core.stazh_parse import parse_ils_rows, parse_workbook_periods

logger = logging.getLogger(__name__)

_ILS_TYPES = frozenset({"ils"})
_BOOK_TYPES = frozenset({"workbook", "labor"})
_DOCS_LABEL = "подтверждено документами"


def _load_full_text(doc: dict[str, Any]) -> str:
    """Весь текстовый слой файла (превью в БД обрезано и для сверки не годится)."""
    from sfrfr.services.ocr_source_resolver import resolve_ocr_bytes_ctx
    from sfrfr.services.staff_document_check import _extract_embedded_from_bytes, _filename_of

    with resolve_ocr_bytes_ctx(doc, case_id=str(doc.get("case_id") or "")) as resolved:
        return _extract_embedded_from_bytes(resolved.data, _filename_of(doc))


def _texts_of(
    kinds: frozenset[str],
    docs_by_id: dict[str, dict[str, Any]],
    analyzed: list[dict[str, Any]],
    load_text: Callable[[dict[str, Any]], str],
) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for row in analyzed:
        kind = str(row.get("guessed_type") or row.get("doc_type") or "").lower()
        doc = docs_by_id.get(str(row.get("id") or ""))
        key = str(row.get("checksum_sha256") or row.get("id") or "")
        if kind not in kinds or doc is None or key in seen:
            continue
        seen.add(key)
        try:
            text = load_text(doc) or ""
        except Exception as exc:  # noqa: BLE001
            logger.info("stazh_compare text skipped doc=%s err=%s", key[:8], type(exc).__name__)
            continue
        if text.strip() and not text.startswith("[ocr_"):
            out.append(text)
    return out


def run_case_stazh_compare(
    docs: list[dict[str, Any]],
    analyzed: list[dict[str, Any]],
    *,
    load_text: Callable[[dict[str, Any]], str] | None = None,
) -> dict[str, Any] | None:
    """None — в деле нет ИЛС или трудовой; иначе результат compare_stazh."""
    loader = load_text or _load_full_text
    docs_by_id = {str(d.get("id") or ""): d for d in docs if isinstance(d, dict)}
    ils = _texts_of(_ILS_TYPES, docs_by_id, analyzed, loader)
    books = _texts_of(_BOOK_TYPES, docs_by_id, analyzed, loader)
    if not ils or not books:
        return None
    ils_text = max(ils, key=lambda t: len(parse_ils_rows(t)))
    today = date.today()
    book_text = max(books, key=lambda t: len(parse_workbook_periods(t, today=today)))
    return compare_stazh(book_text, ils_text, today=today)


def merge_compare_into_brief(
    brief: dict[str, Any] | None,
    compare: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Расхождения сверки → первые пункты честного резюме с основанием «документы»."""
    if not compare or not compare.get("ran"):
        return brief
    merged = dict(brief or {})
    found = [d for d in compare.get("discrepancies") or [] if isinstance(d, dict)]
    doc_items = [
        {
            "text": str(d.get("title") or ""),
            "evidence": "docs",
            "evidence_label": _DOCS_LABEL,
            "basis": str(d.get("detail") or ""),
        }
        for d in found
    ]
    merged["items"] = doc_items + [i for i in merged.get("items") or [] if isinstance(i, dict)]
    summary = str(compare.get("summary") or "")
    merged["compare"] = {"ran": True, "discrepancies": len(found), "summary": summary}
    if found:
        merged["has_justified_discrepancy"] = True
        merged["offer_diag_allowed"] = bool(merged.get("current", True))
        merged["offer_amount_rub"] = 3000
        merged["headline"] = "Сверка трудовой книжки с выпиской ИЛС: есть расхождения"
    elif not any(i.get("evidence") == "docs" for i in merged["items"]):
        merged["headline"] = summary
    return merged
