"""Загрузка → зеркало оригинала на Яндекс.Диск (без полного ingest)."""

from __future__ import annotations


def test_create_quarantine_mirrors_original_when_no_jobs(monkeypatch) -> None:
    from sfrfr.services import document_ingest_worker as worker

    mirrored: list[tuple[str, str, bytes, str | None]] = []

    monkeypatch.setattr(worker, "validate_file_bytes", lambda *a, **k: type("S", (), {
        "ok": True,
        "detected_mime": "application/pdf",
        "client_message": None,
    })())
    monkeypatch.setattr(worker, "sha256_hex", lambda data: "abc")
    monkeypatch.setattr(worker, "find_duplicate_checksum", lambda *a, **k: False)
    monkeypatch.setattr(worker, "documents_has_ingest_columns", lambda: False)
    monkeypatch.setattr(worker, "document_ingest_jobs_available", lambda: False)
    monkeypatch.setattr(worker, "normalize_uploaded_by", lambda x: None)
    monkeypatch.setattr(
        worker,
        "insert_document_row",
        lambda row: {**row, "id": row["id"]},
    )

    class _Storage:
        def from_(self, _bucket: str) -> _Storage:
            return self

        def upload(self, *_a, **_k) -> None:
            return None

        def remove(self, *_a, **_k) -> None:
            return None

    monkeypatch.setattr(
        worker,
        "get_supabase_client",
        lambda: type("C", (), {"storage": _Storage()})(),
    )

    def _mirror(
        *,
        case_id: str,
        filename: str,
        data: bytes,
        doc_type: str | None,
        document_id: str | None = None,
    ) -> None:
        mirrored.append((case_id, filename, data, doc_type, document_id))

    monkeypatch.setattr(worker, "_mirror_document_after_security", _mirror)
    # Phase 2 early local — без записи на диск в этом unit-тесте.
    monkeypatch.setattr(worker, "save_quarantine_upload", lambda *a, **k: None)
    monkeypatch.setattr(worker, "confirm_local_file", lambda *a, **k: None)

    original = b"%PDF-1.4-real-upload"
    row = worker.create_quarantine_document(
        case_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        filename="ils_scan.pdf",
        data=original,
        content_type="application/pdf",
        doc_type="ils",
        uploaded_by=None,
        upload_source="max",
    )
    assert row.get("id")
    assert len(mirrored) == 1
    assert mirrored[0][:4] == (
        "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        "ils_scan.pdf",
        original,
        "ils",
    )
    assert mirrored[0][4] == row["id"]


def test_create_quarantine_defers_mirror_when_jobs_exist(monkeypatch) -> None:
    from sfrfr.services import document_ingest_worker as worker

    mirrored: list[object] = []

    monkeypatch.setattr(worker, "validate_file_bytes", lambda *a, **k: type("S", (), {
        "ok": True,
        "detected_mime": "application/pdf",
        "client_message": None,
    })())
    monkeypatch.setattr(worker, "sha256_hex", lambda data: "abc")
    monkeypatch.setattr(worker, "find_duplicate_checksum", lambda *a, **k: False)
    monkeypatch.setattr(worker, "documents_has_ingest_columns", lambda: True)
    monkeypatch.setattr(worker, "document_ingest_jobs_available", lambda: True)
    monkeypatch.setattr(worker, "normalize_uploaded_by", lambda x: None)
    monkeypatch.setattr(worker, "insert_document_row", lambda row: {**row, "id": row["id"]})
    monkeypatch.setattr(worker, "enqueue_document_ingest_job", lambda **k: "job-1")

    class _Storage:
        def from_(self, _bucket: str) -> _Storage:
            return self

        def upload(self, *_a, **_k) -> None:
            return None

        def remove(self, *_a, **_k) -> None:
            return None

    monkeypatch.setattr(
        worker,
        "get_supabase_client",
        lambda: type("C", (), {"storage": _Storage()})(),
    )
    monkeypatch.setattr(
        worker,
        "_mirror_document_after_security",
        lambda **k: mirrored.append(k),
    )

    row = worker.create_quarantine_document(
        case_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        filename="ils_scan.pdf",
        data=b"%PDF",
        content_type="application/pdf",
        doc_type="ils",
        uploaded_by=None,
    )
    assert row.get("job_id") == "job-1"
    assert mirrored == []
