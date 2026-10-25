"""Текст файла для проверки сотрудником, когда артефактов загрузки нет.

Старые загрузки хранят только content_preview в БД. Без запасного текста
«Принять текст» оставался неактивным и файл висел в manual_review.
"""

from __future__ import annotations

from typing import Any

# Сколько символов content_preview хранит БД после загрузки (обрезка в ingest-accept).
PREVIEW_LIMIT = 2000


def saved_text_payload(row: dict[str, Any]) -> dict[str, Any] | None:
    """Ответ ingest-artifacts из сохранённого текста; None — текста нет."""
    text = str(row.get("content_preview") or "").strip()
    if not text:
        return None
    return {
        "document_id": str(row.get("id") or ""),
        "extracted_text": text,
        "manifest": {"pages": [], "source": "saved_preview"},
        "fallback": True,
        "truncated": len(text) >= PREVIEW_LIMIT,
    }
