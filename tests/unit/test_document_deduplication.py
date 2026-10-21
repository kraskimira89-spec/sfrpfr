"""Регрессия exact-dupe: SHA-256 через production accept path (harness)."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.unit.document_dedup_harness import InMemoryDocumentStore, sha256_hex


@pytest.fixture()
def store(tmp_path: Path) -> InMemoryDocumentStore:
    return InMemoryDocumentStore(root=tmp_path)


@pytest.fixture()
def case_a() -> str:
    return "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"


@pytest.fixture()
def case_b() -> str:
    return "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"


def test_1_same_bytes_different_names(store: InMemoryDocumentStore, case_a: str) -> None:
    content = b"%PDF-1.4 SYNTHETIC SAME BYTES\n"
    r1 = store.upload(
        case_id=case_a,
        event_id="ev-1",
        attachment_id="att-1",
        filename="first.pdf",
        content=content,
    )
    r2 = store.upload(
        case_id=case_a,
        event_id="ev-2",
        attachment_id="att-2",
        filename="renamed-copy.pdf",
        content=content,
    )
    assert r1.document_id == r2.document_id
    assert r2.deduped is True
    assert store.document_ids(case_a) == [r1.document_id]
    assert store.permanent_originals(case_a) == [content]
    assert store.processing_job_document_ids(case_a) == [r1.document_id]
    assert store.event_document_id("ev-1") == r1.document_id
    assert store.event_document_id("ev-2") == r1.document_id
    assert store.ocr_calls.count(r1.document_id) == 1


def test_2_same_size_and_time_different_bytes(
    store: InMemoryDocumentStore, case_a: str
) -> None:
    """ГЛАВНЫЙ: одинаковые размер/время ≠ exact dupe без SHA."""
    a = b"AAAAAAAA" + b"X" * 40
    b = b"BBBBBBBB" + b"Y" * 40
    assert len(a) == len(b)
    assert sha256_hex(a) != sha256_hex(b)
    r1 = store.upload(
        case_id=case_a,
        event_id="ev-a",
        attachment_id="att-a",
        filename="same-size-a.pdf",
        content=a,
    )
    r2 = store.upload(
        case_id=case_a,
        event_id="ev-b",
        attachment_id="att-b",
        filename="same-size-b.pdf",
        content=b,
    )
    assert r1.document_id != r2.document_id
    assert r2.deduped is False
    assert set(store.document_ids(case_a)) == {r1.document_id, r2.document_id}
    originals = store.permanent_originals(case_a)
    assert len(originals) == 2
    assert set(originals) == {a, b}
    assert set(store.processing_job_document_ids(case_a)) == {
        r1.document_id,
        r2.document_id,
    }
    assert len(store.ocr_calls) == 2


def test_3_same_bytes_different_time(store: InMemoryDocumentStore, case_a: str) -> None:
    content = b"SYNTHETIC TIME-INDEPENDENT\n"
    r1 = store.upload(
        case_id=case_a,
        event_id="t1",
        attachment_id="a1",
        filename="morning.pdf",
        content=content,
    )
    r2 = store.upload(
        case_id=case_a,
        event_id="t2",
        attachment_id="a2",
        filename="evening.pdf",
        content=content,
    )
    assert r1.document_id == r2.document_id
    assert r2.deduped is True
    assert store.processing_job_document_ids(case_a) == [r1.document_id]


def test_4_replay_event(store: InMemoryDocumentStore, case_a: str) -> None:
    content = b"REPLAY PAYLOAD\n"
    r1 = store.upload(
        case_id=case_a,
        event_id="same-event",
        attachment_id="same-att",
        filename="doc.pdf",
        content=content,
    )
    r2 = store.upload(
        case_id=case_a,
        event_id="same-event",
        attachment_id="same-att",
        filename="doc.pdf",
        content=content,
    )
    assert r2.replayed is True
    assert r2.document_id == r1.document_id
    assert store.document_ids(case_a) == [r1.document_id]
    assert store.processing_job_document_ids(case_a) == [r1.document_id]
    assert store.ocr_calls.count(r1.document_id) == 1


def test_6_different_cases(
    store: InMemoryDocumentStore, case_a: str, case_b: str
) -> None:
    content = b"CROSS-CASE SAME BYTES\n"
    r1 = store.upload(
        case_id=case_a,
        event_id="c1",
        attachment_id="x1",
        filename="a.pdf",
        content=content,
    )
    r2 = store.upload(
        case_id=case_b,
        event_id="c2",
        attachment_id="x2",
        filename="b.pdf",
        content=content,
    )
    assert r1.document_id != r2.document_id
    assert store.document_ids(case_a) == [r1.document_id]
    assert store.document_ids(case_b) == [r2.document_id]
    assert store.permanent_originals(case_a) == [content]
    assert store.permanent_originals(case_b) == [content]


def test_7_canonical_missing_restore(store: InMemoryDocumentStore, case_a: str) -> None:
    content = b"RESTORE ME PLEASE\n"
    r1 = store.upload(
        case_id=case_a,
        event_id="r1",
        attachment_id="ra1",
        filename="lost.pdf",
        content=content,
    )
    store.mark_original_lost(r1.document_id)
    assert store.permanent_originals(case_a) == []
    r2 = store.upload(
        case_id=case_a,
        event_id="r2",
        attachment_id="ra2",
        filename="lost-again.pdf",
        content=content,
    )
    assert r2.document_id == r1.document_id
    assert r2.restored is True
    assert store.permanent_originals(case_a) == [content]
    assert store.document_ids(case_a) == [r1.document_id]
    assert store.processing_job_document_ids(case_a) == [r1.document_id]


def test_8_already_processed_no_re_ocr(store: InMemoryDocumentStore, case_a: str) -> None:
    content = b"ALREADY PROCESSED TEXT\n"
    r1 = store.upload(
        case_id=case_a,
        event_id="p1",
        attachment_id="pa1",
        filename="done.pdf",
        content=content,
    )
    store.mark_processed(r1.document_id, preview="full extracted")
    ocr_before = list(store.ocr_calls)
    classify_before = list(store.classify_calls)
    r2 = store.upload(
        case_id=case_a,
        event_id="p2",
        attachment_id="pa2",
        filename="done-copy.pdf",
        content=content,
    )
    assert r2.deduped is True
    assert r2.document_id == r1.document_id
    assert store.ocr_calls == ocr_before
    assert store.classify_calls == classify_before
    assert store.documents[r1.document_id].content_preview == "full extracted"
    assert store.documents[r1.document_id].ingest_status == "under_review"


def test_name_never_merge_key(store: InMemoryDocumentStore, case_a: str) -> None:
    """Одинаковое имя, разные байты → два документа."""
    r1 = store.upload(
        case_id=case_a,
        event_id="n1",
        attachment_id="na1",
        filename="same-name.pdf",
        content=b"CONTENT ONE\n",
    )
    r2 = store.upload(
        case_id=case_a,
        event_id="n2",
        attachment_id="na2",
        filename="same-name.pdf",
        content=b"CONTENT TWO\n",
    )
    assert r1.document_id != r2.document_id
    assert len(store.document_ids(case_a)) == 2
