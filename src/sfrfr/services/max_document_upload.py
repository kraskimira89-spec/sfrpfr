"""Загрузка документов из MAX в единый Supabase Storage."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any
from uuid import uuid4

from sfrfr.db.session import get_supabase_client

logger = logging.getLogger(__name__)

PRIVATE_STORAGE_BUCKET = "pension-docs"
_ALLOWED_SUFFIXES = {".pdf", ".jpg", ".jpeg", ".png"}


def _guess_content_type(filename: str) -> str:
    suffix = Path(filename or "").suffix.lower()
    if suffix == ".pdf":
        return "application/pdf"
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".png":
        return "image/png"
    return "application/octet-stream"


def upload_max_document(
    *,
    case_id: str,
    filename: str,
    data: bytes,
    doc_type: str | None = None,
    uploaded_by: str | None = None,
) -> dict[str, Any] | None:
    """Сохранить файл дела в Supabase; None при ошибке или неподдерживаемом типе."""
    suffix = Path(filename or "document").suffix.lower()
    if suffix not in _ALLOWED_SUFFIXES:
        logger.info("max upload rejected extension: %s", suffix)
        return None
    if not data:
        return None
    document_id = str(uuid4())
    safe_name = Path(filename or "document").name
    storage_path = f"{case_id}/{document_id}/{safe_name}"
    content_type = _guess_content_type(safe_name)
    client = get_supabase_client()
    try:
        client.storage.from_(PRIVATE_STORAGE_BUCKET).upload(
            storage_path,
            data,
            {"content-type": content_type, "x-upsert": "false"},
        )
        row: dict[str, Any] = {
            "id": document_id,
            "case_id": case_id,
            "storage_path": storage_path,
            "doc_type": doc_type,
        }
        if uploaded_by:
            row["uploaded_by"] = uploaded_by
        response = client.table("documents").insert(row).execute()
        return response.data[0] if response.data else row
    except Exception as exc:  # noqa: BLE001
        logger.warning("max supabase upload failed: %s", exc)
        return None
