"""Upload harness: production accept path + in-memory store (unique like PG)."""

from __future__ import annotations

import hashlib
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4

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
    """Отдельные «сессии» через lock; unique (case_id, checksum) как в PG."""

    root: Path
    documents: dict[str, _DocRow] = field(default_factory=dict)
    checksum_index: dict[tuple[str, str], str] = field(default_factory=dict)
    events: dict[str, str] = field(default_factory=dict)  # event_id|attach → doc_id
    jobs: list[str] = field(default_factory=list)  # document_ids with ingest job
    permanent_files: dict[str, bytes] = field(default_factory=dict)  # storage_path → bytes
    ocr_calls: list[str] = field(default_factory=list)
    classify_calls: list[str] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock)
    # Test hook: after hash lookup, before insert/claim
    after_hash_lookup_barrier: threading.Barrier | None = None

    def document_ids(self, case_id: str) -> list[str]:
        with self._lock:
            return [
                d.id
                for d in self.documents.values()
                if d.case_id == case_id and not d.original_lost or d.case_id == case_id
            ]

    def canonical_document_ids(self, case_id: str) -> list[str]:
        """Основные записи (по одной на checksum)."""
        with self._lock:
            seen: set[str] = set()
            out: list[str] = []
            for (cid, _cs), doc_id in self.checksum_index.items():
                if cid != case_id or doc_id in seen:
                    continue
                seen.add(doc_id)
                out.append(doc_id)
            return out

    def permanent_originals(self, case_id: str) -> list[bytes]:
        with self._lock:
            out: list[bytes] = []
            for doc in self.documents.values():
                if doc.case_id != case_id:
                    continue
                if doc.id not in {v for (c, _), v in self.checksum_index.items() if c == case_id}:
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

    def attachment_document_id(self, attachment_id: str) -> str | None:
        with self._lock:
            return self.events.get(f"attach:{attachment_id}")

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

    def accept(
        self,
        *,
        case_id: str,
        event_id: str | None,
        attachment_id: str | None,
        filename: str,
        content: bytes,
        session_id: str | None = None,
    ) -> UploadResult:
        """Один приём = отдельная логическая сессия (свой session_id для логов)."""
        _ = session_id
        from sfrfr.services.document_deduplication import accept_case_document_bytes

        return accept_case_document_bytes(
            case_id=case_id,
            filename=filename,
            data=content,
            content_type="application/octet-stream",
            event_id=event_id,
            attachment_id=attachment_id,
            store=self,
        )


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# re-export for tests
__all__ = [
    "InMemoryDocumentStore",
    "UploadResult",
    "sha256",
    "sha256_hex",
    "uuid4",
]
