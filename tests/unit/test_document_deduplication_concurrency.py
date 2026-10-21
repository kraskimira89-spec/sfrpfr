"""Параллельные identical uploads: одна каноническая запись, без deadlock."""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pytest

from sfrfr.services.document_deduplication import set_test_after_hash_lookup_barrier
from document_dedup_harness import InMemoryDocumentStore, UploadResult


@pytest.fixture()
def store(tmp_path: Path) -> InMemoryDocumentStore:
    return InMemoryDocumentStore(root=tmp_path)


def test_5_parallel_identical_uploads_create_one_document(
    store: InMemoryDocumentStore,
) -> None:
    case_id = "cccccccc-cccc-cccc-cccc-cccccccccccc"
    content = b"SYNTHETIC DOCUMENT\nidentical upload payload\n"
    barrier = threading.Barrier(2, timeout=10)
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
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [
                pool.submit(
                    send,
                    event_id="synthetic-event-a",
                    attachment_id="synthetic-attachment-a",
                    filename="original.txt",
                ),
                pool.submit(
                    send,
                    event_id="synthetic-event-b",
                    attachment_id="synthetic-attachment-b",
                    filename="renamed-copy.txt",
                ),
            ]
            results = [f.result(timeout=15) for f in as_completed(futures)]
    finally:
        store.after_hash_lookup_barrier = None
        set_test_after_hash_lookup_barrier(None)

    document_ids = store.document_ids(case_id)
    originals = store.permanent_originals(case_id)
    job_document_ids = store.processing_job_document_ids(case_id)
    event_a = store.event_document_id("synthetic-event-a")
    event_b = store.event_document_id("synthetic-event-b")

    assert len(document_ids) == 1, f"дубли документов: {document_ids}"
    canonical_id = document_ids[0]
    assert {r.document_id for r in results} == {canonical_id}
    assert originals == [content]
    assert job_document_ids == [canonical_id]
    assert event_a == canonical_id
    assert event_b == canonical_id
    assert store.ocr_calls.count(canonical_id) == 1
