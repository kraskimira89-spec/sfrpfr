"""Upload harness: production accept path + in-memory store (unique like PG)."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4

from sfrfr.services.document_deduplication import AcceptResult, accept_case_document_bytes
from sfrfr.services.document_ingest import sha256_hex


@dataclass
class UploadResult:
    document_id: str
    deduped: bool = False
    replayed: bool = False
    restored: bool = False
    job_id: str = ""


@dataclass
class _DocRow:
    id: str
    case_id: str
    filename: str
    checksum_sha256: str
    size_bytes: int
    storage_path: str
    content_preview: str | None = None
    ingest_status: str = "security_check"
    original_lost: bool = False
    processed: bool = False


@dataclass
class InMemoryDocumentStore:
    """Отдельные логические сессии; unique (case_id, checksum) как в PG."""

    root: Path
    documents: dict[str, _DocRow] = field(default_factory=dict)
    checksum_index: dict[tuple[str, str], str] = field(default_factory=dict)
    events: dict[str, str] = field(default_factory=dict)
    jobs: list[str] = field(default_factory=list)
    permanent_files: dict[str, bytes] = field(default_factory=dict)
    ocr_calls: list[str] = field(default_factory=list)
    classify_calls: list[str] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock)
    after_hash_lookup_barrier: threading.Barrier | None = None

    def lookup_event(self, *, event_id: str | None, attachment_id: str | None) -> str | None:
        with self._lock:
            if event_id:
                found = self.events.get(f"event:{event_id}")
                if found:
                    return found
            if attachment_id:
                return self.events.get(f"attach:{attachment_id}")
            return None

    def record_event(
        self,
        *,
        case_id: str,
        document_id: str,
        event_id: str | None,
        attachment_id: str | None,
        filename: str,
    ) -> None:
        _ = (case_id, filename)
        with self._lock:
            if event_id:
                self.events[f"event:{event_id}"] = document_id
            if attachment_id:
                self.events[f"attach:{attachment_id}"] = document_id

    def find_canonical(
        self, *, case_id: str, checksum: str, size_bytes: int
    ) -> dict[str, Any] | None:
        with self._lock:
            doc_id = self.checksum_index.get((case_id, checksum))
            if not doc_id:
                # size prefilter alone never merges
                return None
            doc = self.documents.get(doc_id)
            if not doc or doc.size_bytes != size_bytes:
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

    def original_available(self, document_id: str) -> bool:
        with self._lock:
            doc = self.documents.get(document_id)
            if not doc or doc.original_lost:
                return False
            return doc.storage_path in self.permanent_files

    def restore_original(self, document_id: str, data: bytes) -> None:
        with self._lock:
            doc = self.documents[document_id]
            self.permanent_files[doc.storage_path] = data
            doc.original_lost = False

    def claim_canonical(
        self,
        *,
        case_id: str,
        checksum: str,
        size_bytes: int,
        document_id: str,
    ) -> str:
        _ = size_bytes
        with self._lock:
            existing = self.checksum_index.get((case_id, checksum))
            if existing:
                return existing
            self.checksum_index[(case_id, checksum)] = document_id
            return document_id

    def insert_new_document(
        self,
        *,
        case_id: str,
        document_id: str,
        filename: str,
        data: bytes,
        checksum: str,
        content_type: str,
    ) -> dict[str, Any]:
        _ = content_type
        storage_path = f"{case_id}/{document_id}/{Path(filename).name}"
        with self._lock:
            row = _DocRow(
                id=document_id,
                case_id=case_id,
                filename=filename,
                checksum_sha256=checksum,
                size_bytes=len(data),
                storage_path=storage_path,
            )
            self.documents[document_id] = row
            self.permanent_files[storage_path] = data
            return {
                "id": document_id,
                "case_id": case_id,
                "storage_path": storage_path,
                "checksum_sha256": checksum,
                "size_bytes": len(data),
            }

    def enqueue_ingest(self, *, case_id: str, document_id: str) -> str:
        _ = case_id
        with self._lock:
            if document_id not in self.jobs:
                self.jobs.append(document_id)
            return f"job-{document_id}"

    def is_processed(self, document_id: str) -> bool:
        with self._lock:
            doc = self.documents.get(document_id)
            return bool(doc and doc.processed)

    def document_ids(self, case_id: str) -> list[str]:
        with self._lock:
            return [d.id for d in self.documents.values() if d.case_id == case_id]

    def permanent_originals(self, case_id: str) -> list[bytes]:
        with self._lock:
            out: list[bytes] = []
            for (_cid, _cs), doc_id in self.checksum_index.items():
                if _cid != case_id:
                    continue
                doc = self.documents.get(doc_id)
                if not doc:
                    continue
                blob = self.permanent_files.get(doc.storage_path)
                if blob is not None:
                    out.append(blob)
            return out

    def processing_job_document_ids(self, case_id: str) -> list[str]:
        with self._lock:
            return [
                did
                for did in self.jobs
                if did in self.documents and self.documents[did].case_id == case_id
            ]

    def event_document_id(self, event_id: str) -> str | None:
        with self._lock:
            return self.events.get(f"event:{event_id}")

    def mark_original_lost(self, document_id: str) -> None:
        with self._lock:
            doc = self.documents[document_id]
            doc.original_lost = True
            self.permanent_files.pop(doc.storage_path, None)

    def mark_processed(self, document_id: str, *, preview: str = "extracted text") -> None:
        with self._lock:
            doc = self.documents[document_id]
            doc.processed = True
            doc.content_preview = preview
            doc.ingest_status = "under_review"
            # уже «обработан» — счётчики OCR не должны расти при дубле
            while document_id in self.ocr_calls:
                self.ocr_calls.remove(document_id)
            while document_id in self.classify_calls:
                self.classify_calls.remove(document_id)

    def upload(
        self,
        *,
        case_id: str,
        event_id: str | None,
        attachment_id: str | None,
        filename: str,
        content: bytes,
    ) -> UploadResult:
        """Production accept path через accept_case_document_bytes."""
        result: AcceptResult = accept_case_document_bytes(
            case_id=case_id,
            filename=filename,
            data=content,
            content_type="application/octet-stream",
            event_id=event_id,
            attachment_id=attachment_id,
            store=self,
            upload_source="harness",
        )
        return UploadResult(
            document_id=result.document_id,
            deduped=result.deduped,
            replayed=result.replayed,
            restored=result.restored,
            job_id=result.job_id,
        )


__all__ = [
    "InMemoryDocumentStore",
    "UploadResult",
    "sha256_hex",
    "uuid4",
]
