"""Параллельные identical uploads: одна каноническая запись, без deadlock.

Покрытие: accept harness (5 потоков) + create_quarantine_document (реальный handler).
"""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor, wait
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from document_dedup_harness import InMemoryDocumentStore, UploadResult

from sfrfr.services.document_deduplication import set_test_after_hash_lookup_barrier
from sfrfr.services.document_ingest import sha256_hex
from sfrfr.services.document_ingest_worker import create_quarantine_document


@pytest.fixture()
def store(tmp_path: Path) -> InMemoryDocumentStore:
    return InMemoryDocumentStore(root=tmp_path)


def test_5_parallel_identical_uploads_create_one_document(
    store: InMemoryDocumentStore,
) -> None:
    case_id = "cccccccc-cccc-cccc-cccc-cccccccccccc"
    content = b"SYNTHETIC DOCUMENT\nidentical upload payload\n"
    n = 5
    barrier = threading.Barrier(n, timeout=10)
    store.after_hash_lookup_barrier = barrier
    set_test_after_hash_lookup_barrier(barrier)

    def send(
        *,
        event_id: str,
        attachment_id: str,
        filename: str,
    ) -> UploadResult:
        return store.upload(
            case_id=case_id,
            event_id=event_id,
            attachment_id=attachment_id,
            filename=filename,
            content=content,
        )

    try:
        with ThreadPoolExecutor(max_workers=n) as pool:
            futures = [
                pool.submit(
                    send,
                    event_id=f"synthetic-event-{i}",
                    attachment_id=f"synthetic-attachment-{i}",
                    filename=f"copy-{i}.txt",
                )
                for i in range(n)
            ]
            done, not_done = wait(futures, timeout=20)
            assert not not_done, f"таймаут гонки: {len(not_done)} незавершённых"
            results = [f.result(timeout=1) for f in done]
    finally:
        store.after_hash_lookup_barrier = None
        set_test_after_hash_lookup_barrier(None)

    document_ids = store.document_ids(case_id)
    originals = store.permanent_originals(case_id)
    job_document_ids = store.processing_job_document_ids(case_id)

    assert len(document_ids) == 1, f"дубли документов: {document_ids}"
    canonical_id = document_ids[0]
    assert {r.document_id for r in results} == {canonical_id}
    assert originals == [content]
    assert job_document_ids == [canonical_id]
    for i in range(n):
        assert store.event_document_id(f"synthetic-event-{i}") == canonical_id
    assert store.ocr_calls.count(canonical_id) == 1
    assert sum(1 for r in results if r.job_id) <= 1


class _RaceChecksumRegistry:
    """Независимые claim-и под UNIQUE (case_id, checksum), без строки documents."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.rows: dict[tuple[str, str], str] = {}
        self.events: dict[str, str] = {}
        self.documents: dict[str, dict[str, Any]] = {}
        self.jobs: list[str] = []
        self.storage_blobs: dict[str, bytes] = {}

    def claim(self, *, case_id: str, checksum: str, document_id: str) -> str:
        with self._lock:
            key = (case_id, checksum)
            existing = self.rows.get(key)
            if existing:
                raise RuntimeError("23505 unique_violation")
            self.rows[key] = document_id
            return document_id

    def lookup_claim(self, *, case_id: str, checksum: str) -> str | None:
        with self._lock:
            return self.rows.get((case_id, checksum))


@pytest.fixture()
def uploads_tmp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "uploads"
    root.mkdir()
    monkeypatch.setenv("STORAGE_LOCAL_PATH", str(root))
    from sfrfr.core.config import get_settings

    get_settings.cache_clear()
    yield root
    get_settings.cache_clear()


def test_create_quarantine_parallel_identical_one_document(
    uploads_tmp: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Реальный create_quarantine_document + управляемая гонка claim/registry."""
    case_id = "dddddddd-dddd-dddd-dddd-dddddddddddd"
    content = b"%PDF-1.4 PARALLEL QUARANTINE\n"
    checksum = sha256_hex(content)
    registry = _RaceChecksumRegistry()
    n = 2
    barrier = threading.Barrier(n, timeout=10)

    def _find_canonical(*, case_id: str, checksum: str, size_bytes: int | None = None):
        _ = size_bytes
        with registry._lock:
            doc_id = registry.rows.get((case_id, checksum))
            if not doc_id:
                return None
            return registry.documents.get(doc_id)

    def _claim(*, case_id: str, checksum: str, size_bytes: int, document_id: str) -> str:
        _ = size_bytes
        try:
            return registry.claim(
                case_id=case_id, checksum=checksum, document_id=document_id
            )
        except RuntimeError:
            found = registry.lookup_claim(case_id=case_id, checksum=checksum)
            if found:
                return found
            return document_id

    def _lookup_event(*, case_id: str, event_id: str | None, attachment_id: str | None):
        _ = case_id
        with registry._lock:
            if event_id and event_id in registry.events:
                return registry.events[event_id]
            if attachment_id and f"a:{attachment_id}" in registry.events:
                return registry.events[f"a:{attachment_id}"]
        return None

    def _record_event(
        *,
        case_id: str,
        document_id: str,
        event_id: str | None,
        attachment_id: str | None,
        filename: str | None = None,
    ) -> None:
        _ = (case_id, filename)
        with registry._lock:
            if event_id:
                registry.events[event_id] = document_id
            if attachment_id:
                registry.events[f"a:{attachment_id}"] = document_id

    def _insert_document_row(row: dict[str, Any]) -> dict[str, Any]:
        with registry._lock:
            registry.documents[str(row["id"])] = dict(row)
            path = str(row.get("storage_path") or "")
            if path:
                registry.storage_blobs[path] = content
        return dict(row)

    def _enqueue(*, case_id: str, document_id: str) -> str:
        _ = case_id
        with registry._lock:
            if document_id not in registry.jobs:
                registry.jobs.append(document_id)
        return f"job-{document_id}"

    class _OkStorage:
        def from_(self, _bucket: str) -> _OkStorage:
            return self

        def upload(self, path: str, data: bytes, *_a: object, **_k: object) -> None:
            with registry._lock:
                registry.storage_blobs[path] = data

        def remove(self, *_a: object, **_k: object) -> None:
            return None

    class _Client:
        storage = _OkStorage()

        def table(self, *_a: object, **_k: object) -> MagicMock:
            raise AssertionError("table via get_supabase_client only for storage path")

    monkeypatch.setattr(
        "sfrfr.services.document_ingest_worker.get_supabase_client",
        lambda: _Client(),
    )
    monkeypatch.setattr(
        "sfrfr.services.document_ingest_worker.documents_has_ingest_columns",
        lambda: True,
    )
    monkeypatch.setattr(
        "sfrfr.services.document_ingest_worker.document_ingest_jobs_available",
        lambda: True,
    )
    monkeypatch.setattr(
        "sfrfr.services.document_ingest_worker.find_duplicate_checksum",
        lambda *_a, **_k: False,
    )
    monkeypatch.setattr(
        "sfrfr.services.document_ingest_worker.insert_document_row",
        _insert_document_row,
    )
    monkeypatch.setattr(
        "sfrfr.services.document_ingest_worker.enqueue_document_ingest_job",
        _enqueue,
    )
    monkeypatch.setattr(
        "sfrfr.services.document_deduplication.find_canonical_by_checksum",
        _find_canonical,
    )
    monkeypatch.setattr(
        "sfrfr.services.document_deduplication.claim_case_checksum",
        _claim,
    )
    monkeypatch.setattr(
        "sfrfr.services.document_deduplication.lookup_upload_event",
        _lookup_event,
    )
    monkeypatch.setattr(
        "sfrfr.services.document_deduplication.record_upload_event",
        _record_event,
    )
    # create_quarantine импортирует функции локально из модуля — патчим там же
    monkeypatch.setattr(
        "sfrfr.services.document_ingest_worker.find_canonical_by_checksum",
        _find_canonical,
        raising=False,
    )
    # Импорт внутри функции — патчим на источнике; re-bind через wrapper
    import sfrfr.services.document_deduplication as dedup_mod

    monkeypatch.setattr(dedup_mod, "find_canonical_by_checksum", _find_canonical)
    monkeypatch.setattr(dedup_mod, "claim_case_checksum", _claim)
    monkeypatch.setattr(dedup_mod, "lookup_upload_event", _lookup_event)
    monkeypatch.setattr(dedup_mod, "record_upload_event", _record_event)

    set_test_after_hash_lookup_barrier(barrier)

    def send(i: int) -> dict[str, Any]:
        return create_quarantine_document(
            case_id=case_id,
            filename=f"parallel-{i}.pdf",
            data=content,
            content_type="application/pdf",
            doc_type=None,
            uploaded_by=None,
            upload_source="cabinet",
            event_id=f"q-event-{i}",
            attachment_id=f"q-att-{i}",
            allow_local_fallback=True,
        )

    try:
        with ThreadPoolExecutor(max_workers=n) as pool:
            futures = [pool.submit(send, i) for i in range(n)]
            done, not_done = wait(futures, timeout=20)
            assert not not_done, f"таймаут: {len(not_done)}"
            rows = [f.result(timeout=1) for f in done]
    finally:
        set_test_after_hash_lookup_barrier(None)

    ids = {str(r["id"]) for r in rows}
    assert len(ids) == 1, f"ожидали один документ, получили {ids}"
    canonical = next(iter(ids))
    assert len(registry.documents) == 1
    assert canonical in registry.documents
    assert registry.jobs == [canonical]
    assert registry.events["q-event-0"] == canonical
    assert registry.events["q-event-1"] == canonical
    assert len(registry.storage_blobs) == 1
    assert list(registry.storage_blobs.values()) == [content]
    assert checksum == sha256_hex(content)
