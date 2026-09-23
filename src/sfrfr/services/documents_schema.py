"""Совместимость схемы documents: полный ingest vs минимальные колонки на проде."""

from __future__ import annotations

import logging
import re
from functools import lru_cache
from typing import Any
from uuid import UUID

from sfrfr.db.session import get_supabase_client

logger = logging.getLogger(__name__)

_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
_MISSING_SCHEMA_CODES = frozenset({"42P01", "42703", "PGRST204", "PGRST205"})


def normalize_uploaded_by(uploaded_by: str | None) -> str | None:
    """Только валидный UUID auth.users; строки max:… и прочий мусор → None."""
    raw = str(uploaded_by or "").strip()
    if not raw or not _UUID_RE.match(raw):
        return None
    try:
        return str(UUID(raw))
    except ValueError:
        return None


def _is_missing_schema_error(exc: Exception) -> bool:
    code = str(getattr(exc, "code", "") or "").upper()
    if code in _MISSING_SCHEMA_CODES:
        return True
    message = str(exc).lower()
    return (
        ("column" in message and ("does not exist" in message or "not found" in message))
        or ("relation" in message and "does not exist" in message)
    )


@lru_cache(maxsize=1)
def documents_has_ingest_columns() -> bool:
    """True, если в documents есть ingest_status (миграции ТЗ-13 применены)."""
    try:
        get_supabase_client().table("documents").select("id,ingest_status").limit(1).execute()
        return True
    except Exception as exc:  # noqa: BLE001
        if _is_missing_schema_error(exc):
            logger.info("documents schema without ingest columns: %s", exc)
            return False
        logger.error("documents schema inspection failed; refusing legacy fallback", exc_info=True)
        raise


def clear_documents_schema_cache() -> None:
    documents_has_ingest_columns.cache_clear()


def insert_document_row(row: dict[str, Any]) -> dict[str, Any]:
    """INSERT documents: полный row или fallback на базовые колонки."""
    client = get_supabase_client()
    payload = dict(row)
    ub = normalize_uploaded_by(
        str(payload["uploaded_by"]) if payload.get("uploaded_by") is not None else None
    )
    if ub is None:
        payload.pop("uploaded_by", None)
    else:
        payload["uploaded_by"] = ub

    if documents_has_ingest_columns():
        response = client.table("documents").insert(payload).execute()
        return response.data[0] if response.data else payload

    minimal = {
        "id": payload["id"],
        "case_id": payload["case_id"],
        "storage_path": payload["storage_path"],
        "doc_type": payload.get("doc_type"),
    }
    if payload.get("uploaded_by"):
        minimal["uploaded_by"] = payload["uploaded_by"]
    # убрать None — PostgREST иногда ругается на null doc_type? обычно ок
    minimal = {k: v for k, v in minimal.items() if v is not None or k in {"doc_type"}}
    logger.warning(
        "documents insert minimal schema case=%s id=%s",
        str(payload.get("case_id") or "")[:8],
        str(payload.get("id") or "")[:8],
    )
    response = client.table("documents").insert(minimal).execute()
    return response.data[0] if response.data else minimal


def document_ingest_jobs_available() -> bool:
    try:
        get_supabase_client().table("document_ingest_jobs").select("id").limit(1).execute()
        return True
    except Exception as exc:  # noqa: BLE001
        if _is_missing_schema_error(exc):
            logger.info("document ingest jobs table is unavailable: %s", exc)
            return False
        logger.error("document ingest jobs inspection failed", exc_info=True)
        raise
