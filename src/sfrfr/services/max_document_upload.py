"""Загрузка документов из MAX в единый Supabase Storage."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from sfrfr.services.document_ingest_worker import create_quarantine_document
from sfrfr.services.file_security import validate_file_bytes

logger = logging.getLogger(__name__)

_MIME_TO_SUFFIX = {
    "application/pdf": ".pdf",
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
}


def _filename_for_mime(filename: str, mime: str | None) -> str:
    """Подставить расширение по содержимому, если имя с телефона врёт или пустое."""
    name = Path(filename or "document").name or "document"
    want = _MIME_TO_SUFFIX.get((mime or "").strip())
    if not want:
        return name
    suffix = Path(name).suffix.lower()
    if suffix == want or (want == ".jpg" and suffix == ".jpeg"):
        return name
    stem = Path(name).stem if suffix else name
    stem = (stem or "document").strip() or "document"
    return f"{stem}{want}"


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
    if not data:
        return None
    security = validate_file_bytes(data, filename=filename, allow_signed=False)
    if not security.ok:
        logger.info("max upload rejected: %s", security.internal_reason)
        return None
    safe_name = _filename_for_mime(filename, security.detected_mime)
    try:
        row = create_quarantine_document(
            case_id=case_id,
            filename=safe_name,
            data=data,
            content_type=security.detected_mime or "application/octet-stream",
            doc_type=doc_type,
            uploaded_by=uploaded_by,
            upload_source="max",
            scenario_rows=scenario_rows,
            allow_local_fallback=True,
        )
        if row and str(row.get("cloud_status") or "") == "pending":
            logger.warning(
                "max upload local-only case=%s file=%s",
                str(case_id)[:8],
                safe_name[:80],
            )
        return row
    except Exception as exc:  # noqa: BLE001
        logger.warning("max supabase upload failed: %s", exc)
        return None
