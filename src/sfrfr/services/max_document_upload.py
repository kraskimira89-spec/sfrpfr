"""Загрузка документов из MAX в единый Supabase Storage."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from sfrfr.services.document_ingest_worker import create_quarantine_document
from sfrfr.services.file_security import validate_file_bytes

logger = logging.getLogger(__name__)

_ALLOWED_SUFFIXES = {".pdf", ".jpg", ".jpeg", ".png"}


def upload_max_document(
    *,
    case_id: str,
    filename: str,
    data: bytes,
    doc_type: str | None = None,
    uploaded_by: str | None = None,
    scenario_rows: list[Any] | None = None,
) -> dict[str, Any] | None:
    """Сохранить файл дела в Supabase; None при ошибке или неподдерживаемом типе."""
    suffix = Path(filename or "document").suffix.lower()
    if suffix not in _ALLOWED_SUFFIXES or not data:
        return None
    security = validate_file_bytes(data, filename=filename, allow_signed=False)
    if not security.ok:
        logger.info("max upload rejected: %s", security.internal_reason)
        return None
    try:
        row = create_quarantine_document(
            case_id=case_id,
            filename=filename,
            data=data,
            content_type=security.detected_mime or "application/octet-stream",
            doc_type=doc_type,
            uploaded_by=uploaded_by,
            upload_source="max",
            scenario_rows=scenario_rows,
        )
        return row
    except Exception as exc:  # noqa: BLE001
        logger.warning("max supabase upload failed: %s", exc)
        return None
