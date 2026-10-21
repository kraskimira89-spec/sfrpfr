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

# Тестовая точка синхронизации: после lookup, до claim/insert (без lock).
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

    root: Path
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
        """Вернуть document_id канона. Если checksum уже занят — id существующего."""
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
    """Единый приём байтов: replay → SHA → exact dupe / restore / new + job.

    ``doc_type`` / ``uploaded_by`` / ``upload_source`` — для production-адаптера.
    """
    _ = (doc_type, uploaded_by, upload_source)
    if not data:
        raise ValueError("empty file")

    replay_id = store.lookup_event(event_id=event_id, attachment_id=attachment_id)
    if replay_id:
        return AcceptResult(document_id=replay_id, replayed=True, row={"id": replay_id})

    checksum = sha256_hex(data)
    size_bytes = len(data)

    barrier = store.after_hash_lookup_barrier or _test_after_hash_lookup
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
            # Уже обработанный: OCR/classify не трогаем
            return AcceptResult(
                document_id=doc_id,
                deduped=True,
                job_id="",
                row=dict(canonical),
            )
        # Оригинал утрачен — восстановить байты, без новой строки и без re-OCR если processed
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
        # Гонка: другой поток успел claim — линкуем на канон
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
    # Счётчики OCR/classify — только при реальной обработке job; здесь mock в store
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


def wire_inmemory_store_methods(store: Any) -> None:
    """Дополнить InMemoryDocumentStore методами Protocol (вызывается из harness)."""

    def lookup_event(*, event_id: str | None, attachment_id: str | None) -> str | None:
        with store._lock:
            if event_id:
                found = store.events.get(f"event:{event_id}")
                if found:
                    return found
            if attachment_id:
                found = store.events.get(f"attach:{attachment_id}")
                if found:
                    return found
            return None

    def record_event(
        *,
        case_id: str,
        document_id: str,
        event_id: str | None,
        attachment_id: str | None,
        filename: str,
    ) -> None:
        _ = (case_id, filename)
        with store._lock:
            if event_id:
                store.events[f"event:{event_id}"] = document_id
            if attachment_id:
                store.events[f"attach:{attachment_id}"] = document_id

    def find_canonical(
        *, case_id: str, checksum: str, size_bytes: int
    ) -> dict[str, Any] | None:
        # size — prefilter: сначала кандидаты того же размера
        with store._lock:
            doc_id = store.checksum_index.get((case_id, checksum))
            if not doc_id:
                return None
            doc = store.documents.get(doc_id)
            if not doc:
                return None
            if doc.size_bytes != size_bytes:
                # size+sha must match; расхождение — не exact (не должно случаться)
                return None
            return {
                "id": doc.id,
                "case_id": doc.case_id,
                "checksum_sha256": doc.checksum_sha256,
                "size_bytes": doc.size_bytes,
                "storage_path": doc.storage_path,
                "content_preview": doc.content_preview,
                "ingest_status": doc.ingest_status,
            }

    def original_available(document_id: str) -> bool:
        with store._lock:
            doc = store.documents.get(document_id)
            if not doc or doc.original_lost:
                return False
            return doc.storage_path in store.permanent_files

    def restore_original(document_id: str, data: bytes) -> None:
        with store._lock:
            doc = store.documents[document_id]
            store.permanent_files[doc.storage_path] = data
            doc.original_lost = False

    def claim_canonical(
        *,
        case_id: str,
        checksum: str,
        size_bytes: int,
        document_id: str,
    ) -> str:
        _ = size_bytes
        with store._lock:
            existing = store.checksum_index.get((case_id, checksum))
            if existing:
                return existing
            store.checksum_index[(case_id, checksum)] = document_id
            return document_id

    def insert_new_document(
        *,
        case_id: str,
        document_id: str,
        filename: str,
        data: bytes,
        checksum: str,
        content_type: str,
    ) -> dict[str, Any]:
        _ = content_type
        from tests.unit.document_dedup_harness import _DocRow

        storage_path = f"{case_id}/{document_id}/{Path(filename).name}"
        with store._lock:
            # unique race: если другой уже claim'нул другой id — не должны сюда попасть
            row = _DocRow(
                id=document_id,
                case_id=case_id,
                filename=filename,
                checksum_sha256=checksum,
                size_bytes=len(data),
                storage_path=storage_path,
            )
            store.documents[document_id] = row
            store.permanent_files[storage_path] = data
            return {
                "id": document_id,
                "case_id": case_id,
                "storage_path": storage_path,
                "checksum_sha256": checksum,
                "size_bytes": len(data),
            }

    def enqueue_ingest(*, case_id: str, document_id: str) -> str:
        _ = case_id
        with store._lock:
            if document_id not in store.jobs:
                store.jobs.append(document_id)
            return f"job-{document_id}"

    def is_processed(document_id: str) -> bool:
        with store._lock:
            doc = store.documents.get(document_id)
            return bool(doc and doc.processed)

    store.lookup_event = lookup_event  # type: ignore[attr-defined]
    store.record_event = record_event  # type: ignore[attr-defined]
    store.find_canonical = find_canonical  # type: ignore[attr-defined]
    store.original_available = original_available  # type: ignore[attr-defined]
    store.restore_original = restore_original  # type: ignore[attr-defined]
    store.claim_canonical = claim_canonical  # type: ignore[attr-defined]
    store.insert_new_document = insert_new_document  # type: ignore[attr-defined]
    store.enqueue_ingest = enqueue_ingest  # type: ignore[attr-defined]
    store.is_processed = is_processed  # type: ignore[attr-defined]
