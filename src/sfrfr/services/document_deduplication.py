"""Exact-dupe до OCR/ИИ: SHA-256 + size; event/attachment replay; restore.

Имена не являются ключом слияния. Size — prefilter; time — только hint.
Реестр канонических checksums: unique (case_id, checksum_sha256).
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol
from uuid import uuid4

from sfrfr.services.document_ingest import sha256_hex

logger = logging.getLogger(__name__)

# Тестовая точка: после hash lookup, до claim/insert (без удерживаемого lock).
_test_after_hash_lookup: threading.Barrier | None = None


def set_test_after_hash_lookup_barrier(barrier: threading.Barrier | None) -> None:
    """Только для тестов гонки; в проде не вызывать."""
    global _test_after_hash_lookup
    _test_after_hash_lookup = barrier


@dataclass(frozen=True)
class AcceptResult:
    document_id: str
    deduped: bool = False
    replayed: bool = False
    restored: bool = False
    job_id: str = ""
    row: dict[str, Any] | None = None


class DocumentAcceptStore(Protocol):
    """Хранилище приёма: in-memory (тесты) или Supabase-адаптер."""

    ocr_calls: list[str]
    classify_calls: list[str]
    after_hash_lookup_barrier: threading.Barrier | None

    def lookup_event(self, *, event_id: str | None, attachment_id: str | None) -> str | None: ...

    def record_event(
        self,
        *,
        case_id: str,
        document_id: str,
        event_id: str | None,
        attachment_id: str | None,
        filename: str,
    ) -> None: ...

    def find_canonical(
        self, *, case_id: str, checksum: str, size_bytes: int
    ) -> dict[str, Any] | None: ...

    def original_available(self, document_id: str) -> bool: ...

    def restore_original(self, document_id: str, data: bytes) -> None: ...

    def claim_canonical(
        self,
        *,
        case_id: str,
        checksum: str,
        size_bytes: int,
        document_id: str,
    ) -> str:
        """Вернуть id канона. Если checksum занят — id существующего."""
        ...

    def insert_new_document(
        self,
        *,
        case_id: str,
        document_id: str,
        filename: str,
        data: bytes,
        checksum: str,
        content_type: str,
    ) -> dict[str, Any]: ...

    def enqueue_ingest(self, *, case_id: str, document_id: str) -> str: ...

    def is_processed(self, document_id: str) -> bool: ...


def accept_case_document_bytes(
    *,
    case_id: str,
    filename: str,
    data: bytes,
    content_type: str,
    event_id: str | None = None,
    attachment_id: str | None = None,
    store: DocumentAcceptStore,
    doc_type: str | None = None,
    uploaded_by: str | None = None,
    upload_source: str = "test",
) -> AcceptResult:
    """Единый приём байтов: replay → SHA → exact dupe / restore / new + job."""
    _ = (doc_type, uploaded_by, upload_source)
    if not data:
        raise ValueError("empty file")

    replay_id = store.lookup_event(event_id=event_id, attachment_id=attachment_id)
    if replay_id:
        return AcceptResult(document_id=replay_id, replayed=True, row={"id": replay_id})

    checksum = sha256_hex(data)
    size_bytes = len(data)

    barrier = getattr(store, "after_hash_lookup_barrier", None) or _test_after_hash_lookup
    if barrier is not None:
        barrier.wait()

    canonical = store.find_canonical(case_id=case_id, checksum=checksum, size_bytes=size_bytes)
    if canonical is not None:
        doc_id = str(canonical["id"])
        if store.original_available(doc_id):
            store.record_event(
                case_id=case_id,
                document_id=doc_id,
                event_id=event_id,
                attachment_id=attachment_id,
                filename=filename,
            )
            return AcceptResult(
                document_id=doc_id,
                deduped=True,
                job_id="",
                row=dict(canonical),
            )
        store.restore_original(doc_id, data)
        store.record_event(
            case_id=case_id,
            document_id=doc_id,
            event_id=event_id,
            attachment_id=attachment_id,
            filename=filename,
        )
        return AcceptResult(
            document_id=doc_id,
            restored=True,
            deduped=True,
            job_id="",
            row=dict(canonical),
        )

    document_id = str(uuid4())
    claimed = store.claim_canonical(
        case_id=case_id,
        checksum=checksum,
        size_bytes=size_bytes,
        document_id=document_id,
    )
    if claimed != document_id:
        store.record_event(
            case_id=case_id,
            document_id=claimed,
            event_id=event_id,
            attachment_id=attachment_id,
            filename=filename,
        )
        if not store.original_available(claimed):
            store.restore_original(claimed, data)
            return AcceptResult(
                document_id=claimed,
                deduped=True,
                restored=True,
                row={"id": claimed},
            )
        return AcceptResult(document_id=claimed, deduped=True, row={"id": claimed})

    row = store.insert_new_document(
        case_id=case_id,
        document_id=document_id,
        filename=filename,
        data=data,
        checksum=checksum,
        content_type=content_type,
    )
    job_id = store.enqueue_ingest(case_id=case_id, document_id=document_id)
    if not store.is_processed(document_id):
        store.ocr_calls.append(document_id)
        store.classify_calls.append(document_id)

    store.record_event(
        case_id=case_id,
        document_id=document_id,
        event_id=event_id,
        attachment_id=attachment_id,
        filename=filename,
    )
    return AcceptResult(
        document_id=document_id,
        job_id=job_id,
        row=row,
    )


def find_canonical_by_checksum(
    *,
    case_id: str,
    checksum: str,
    size_bytes: int | None = None,
) -> dict[str, Any] | None:
    """Production lookup: documents с тем же checksum в деле (size — prefilter)."""
    if not checksum:
        return None
    try:
        from sfrfr.db.session import get_supabase_client

        query = (
            get_supabase_client()
            .table("documents")
            .select(
                "id, case_id, checksum_sha256, size_bytes, storage_path, local_path, "
                "content_preview, ingest_status, created_at"
            )
            .eq("case_id", case_id)
            .eq("checksum_sha256", checksum)
            .order("created_at", desc=False)
            .limit(5)
        )
        rows = query.execute().data or []
    except Exception as exc:  # noqa: BLE001
        logger.info("find_canonical_by_checksum skipped: %s", type(exc).__name__)
        return None
    if not rows:
        return None
    if size_bytes is not None:
        sized = [
            r
            for r in rows
            if r.get("size_bytes") is None or int(r.get("size_bytes") or 0) == size_bytes
        ]
        if sized:
            rows = sized
    return rows[0] if rows else None


def claim_case_checksum(
    *,
    case_id: str,
    checksum: str,
    size_bytes: int,
    document_id: str,
) -> str:
    """Запись в case_document_checksums; при unique conflict — id существующего.

    Без таблицы (миграция ещё не на проде) — fallback на find_canonical.
    """
    if not checksum:
        return document_id
    try:
        from sfrfr.db.session import get_supabase_client

        client = get_supabase_client()
        client.table("case_document_checksums").insert(
            {
                "case_id": case_id,
                "checksum_sha256": checksum,
                "size_bytes": size_bytes,
                "document_id": document_id,
            }
        ).execute()
        return document_id
    except Exception as exc:  # noqa: BLE001
        # Unique / missing table → lookup
        existing = find_canonical_by_checksum(
            case_id=case_id, checksum=checksum, size_bytes=size_bytes
        )
        if existing:
            return str(existing["id"])
        logger.info("claim_case_checksum fallback: %s", type(exc).__name__)
        return document_id


def record_upload_event(
    *,
    case_id: str,
    document_id: str,
    event_id: str | None,
    attachment_id: str | None,
    filename: str | None = None,
) -> None:
    if not event_id and not attachment_id:
        return
    try:
        from sfrfr.db.session import get_supabase_client

        payload: dict[str, Any] = {
            "case_id": case_id,
            "document_id": document_id,
            "filename": (filename or "")[:240] or None,
        }
        if event_id:
            payload["event_id"] = str(event_id)[:200]
        if attachment_id:
            payload["attachment_id"] = str(attachment_id)[:200]
        get_supabase_client().table("document_upload_events").insert(payload).execute()
    except Exception as exc:  # noqa: BLE001
        logger.info("record_upload_event skipped: %s", type(exc).__name__)


def lookup_upload_event(
    *,
    case_id: str,
    event_id: str | None,
    attachment_id: str | None,
) -> str | None:
    if not event_id and not attachment_id:
        return None
    try:
        from sfrfr.db.session import get_supabase_client

        client = get_supabase_client()
        if event_id:
            rows = (
                client.table("document_upload_events")
                .select("document_id")
                .eq("case_id", case_id)
                .eq("event_id", str(event_id)[:200])
                .limit(1)
                .execute()
                .data
                or []
            )
            if rows:
                return str(rows[0]["document_id"])
        if attachment_id:
            rows = (
                client.table("document_upload_events")
                .select("document_id")
                .eq("case_id", case_id)
                .eq("attachment_id", str(attachment_id)[:200])
                .limit(1)
                .execute()
                .data
                or []
            )
            if rows:
                return str(rows[0]["document_id"])
    except Exception as exc:  # noqa: BLE001
        logger.info("lookup_upload_event skipped: %s", type(exc).__name__)
    return None


def canonical_original_available(row: dict[str, Any]) -> bool:
    """Есть ли постоянная копия (local hash-ok или storage_path не local-pending)."""
    storage = str(row.get("storage_path") or "")
    local = str(row.get("local_path") or "").strip()
    if local:
        try:
            from sfrfr.storage.local import path_from_uploads_relative

            path = path_from_uploads_relative(local)
            if path is not None and path.is_file() and path.stat().st_size > 0:
                return True
        except Exception:  # noqa: BLE001
            pass
    if storage.startswith("local-pending/"):
        return False
    return bool(storage)


def restore_canonical_bytes(
    *,
    case_id: str,
    document_id: str,
    filename: str,
    data: bytes,
    checksum: str,
    row: dict[str, Any],
) -> None:
    """Восстановить оригинал канона из новых байтов (без новой строки documents)."""
    from sfrfr.storage.local import confirm_local_file, save_quarantine_upload

    try:
        qpath = save_quarantine_upload(
            case_id,
            document_id=document_id,
            filename=Path(filename or "document").name,
            data=data,
        )
        confirm_local_file(qpath, expected_sha256=checksum, expected_size=len(data))
    except Exception as exc:  # noqa: BLE001
        logger.warning("restore local failed: %s", type(exc).__name__)

    storage_path = str(row.get("storage_path") or "")
    if storage_path and not storage_path.startswith("local-pending/"):
        try:
            from sfrfr.db.session import get_supabase_client
            from sfrfr.security.integrations import PRIVATE_STORAGE_BUCKET

            get_supabase_client().storage.from_(PRIVATE_STORAGE_BUCKET).upload(
                storage_path,
                data,
                {"content-type": "application/octet-stream", "x-upsert": "true"},
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("restore storage failed: %s", type(exc).__name__)
