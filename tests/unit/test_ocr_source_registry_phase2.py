"""Phase 2: реестр local/Disk paths + audit OCR source (mocks, без сети)."""

from __future__ import annotations

import hashlib
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from sfrfr.core.config import get_settings
from sfrfr.services.ocr_source_resolver import (
    OcrSourceUnresolved,
    ResolvedBytes,
    resolve_ocr_bytes,
    sanitize_resolve_trace,
)
from sfrfr.storage.local import (
    confirm_local_file,
    path_from_uploads_relative,
    relative_to_uploads,
    save_quarantine_upload,
)

CASE_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
DOC_ID = "11111111-2222-3333-4444-555555555555"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_relative_local_path_resolves_inside_uploads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    payload = b"%PDF-rel-ok"
    digest = _sha(payload)
    monkeypatch.setenv("STORAGE_LOCAL_PATH", str(tmp_path))
    get_settings.cache_clear()

    qdir = tmp_path / "quarantine" / CASE_ID
    qdir.mkdir(parents=True)
    (qdir / "abcd1234_scan.pdf").write_bytes(payload)
    rel = f"quarantine/{CASE_ID}/abcd1234_scan.pdf"

    storage_dl = MagicMock(side_effect=AssertionError("storage must not be called"))
    resolved = resolve_ocr_bytes(
        {
            "checksum_sha256": digest,
            "size_bytes": len(payload),
            "local_path": rel,
            "storage_path": "quarantine/x/scan.pdf",
        },
        case_id=CASE_ID,
        storage_download=storage_dl,
        storage_fallback=True,
    )
    assert resolved.source_used == "local_storage"
    assert resolved.data == payload
    storage_dl.assert_not_called()


def test_relative_path_with_dotdot_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("STORAGE_LOCAL_PATH", str(tmp_path))
    get_settings.cache_clear()
    assert path_from_uploads_relative("../etc/passwd") is None
    assert path_from_uploads_relative(f"{CASE_ID}/../../secret.pdf") is None

    payload = b"x"
    storage_dl = MagicMock(return_value=payload)
    resolved = resolve_ocr_bytes(
        {
            "checksum_sha256": _sha(payload),
            "local_path": f"{CASE_ID}/../../outside.pdf",
            "storage_path": "q/x.pdf",
        },
        case_id=CASE_ID,
        storage_download=storage_dl,
        storage_fallback=True,
    )
    assert resolved.source_used == "supabase_storage"


def test_confirm_local_rejects_hash_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("STORAGE_LOCAL_PATH", str(tmp_path))
    get_settings.cache_clear()
    path = save_quarantine_upload(
        CASE_ID, document_id=DOC_ID, filename="a.pdf", data=b"real-bytes"
    )
    assert confirm_local_file(path, expected_sha256=_sha(b"other"), expected_size=10) is None
    rel = confirm_local_file(
        path, expected_sha256=_sha(b"real-bytes"), expected_size=len(b"real-bytes")
    )
    assert rel is not None
    assert not rel.startswith("/")
    assert rel.startswith("quarantine/")
    assert ".." not in rel


def test_create_quarantine_writes_relative_local_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from sfrfr.services import document_ingest_worker as worker

    payload = b"%PDF-create-q"
    digest = _sha(payload)
    monkeypatch.setenv("STORAGE_LOCAL_PATH", str(tmp_path))
    get_settings.cache_clear()

    inserted: dict = {}

    class _Bucket:
        def upload(self, *_a, **_k) -> None:
            return None

        def remove(self, *_a, **_k) -> None:
            return None

    class _Storage:
        def from_(self, _b: str) -> _Bucket:
            return _Bucket()

    client = MagicMock()
    client.storage = _Storage()

    def _insert(row: dict) -> dict:
        inserted.update(row)
        return dict(row)

    monkeypatch.setattr(worker, "get_supabase_client", lambda: client)
    monkeypatch.setattr(worker, "documents_has_ingest_columns", lambda: True)
    monkeypatch.setattr(worker, "document_ingest_jobs_available", lambda: True)
    monkeypatch.setattr(worker, "find_duplicate_checksum", lambda *_a, **_k: False)
    monkeypatch.setattr(worker, "insert_document_row", _insert)
    monkeypatch.setattr(worker, "enqueue_document_ingest_job", lambda **_k: "job-1")
    monkeypatch.setattr(
        worker,
        "validate_file_bytes",
        lambda *_a, **_k: MagicMock(ok=True, detected_mime="application/pdf", client_message=None),
    )

    out = worker.create_quarantine_document(
        case_id=CASE_ID,
        filename="scan.pdf",
        data=payload,
        content_type="application/pdf",
        doc_type="labor_book",
        uploaded_by=None,
    )
    assert out.get("job_id") == "job-1"
    assert inserted.get("checksum_sha256") == digest
    assert inserted.get("size_bytes") == len(payload)
    assert inserted.get("document_version") == 1
    assert inserted.get("local_status") == "quarantine"
    assert inserted.get("primary_ocr_source") == "local_storage"
    local_path = inserted.get("local_path")
    assert isinstance(local_path, str)
    assert local_path.startswith(f"quarantine/{CASE_ID}/")
    assert not local_path.startswith("/")
    assert (tmp_path / local_path).is_file()


def test_create_quarantine_skips_local_path_on_hash_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from sfrfr.services import document_ingest_worker as worker

    monkeypatch.setenv("STORAGE_LOCAL_PATH", str(tmp_path))
    get_settings.cache_clear()
    inserted: dict = {}

    class _Bucket:
        def upload(self, *_a, **_k) -> None:
            return None

        def remove(self, *_a, **_k) -> None:
            return None

    client = MagicMock()
    client.storage = MagicMock()
    client.storage.from_ = lambda _b: _Bucket()

    monkeypatch.setattr(worker, "get_supabase_client", lambda: client)
    monkeypatch.setattr(worker, "documents_has_ingest_columns", lambda: True)
    monkeypatch.setattr(worker, "document_ingest_jobs_available", lambda: True)
    monkeypatch.setattr(worker, "find_duplicate_checksum", lambda *_a, **_k: False)
    monkeypatch.setattr(worker, "insert_document_row", lambda row: inserted.update(row) or row)
    monkeypatch.setattr(worker, "enqueue_document_ingest_job", lambda **_k: "job-1")
    monkeypatch.setattr(
        worker,
        "validate_file_bytes",
        lambda *_a, **_k: MagicMock(ok=True, detected_mime="application/pdf", client_message=None),
    )
    monkeypatch.setattr(
        worker,
        "confirm_local_file",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        worker,
        "save_quarantine_upload",
        lambda *_a, **_k: tmp_path / "x.pdf",
    )

    worker.create_quarantine_document(
        case_id=CASE_ID,
        filename="scan.pdf",
        data=b"%PDF-no-path",
        content_type="application/pdf",
        doc_type=None,
        uploaded_by=None,
    )
    assert "local_path" not in inserted
    assert inserted.get("size_bytes") == len(b"%PDF-no-path")


def test_mirror_ok_persists_yandex_disk_path(monkeypatch: pytest.MonkeyPatch) -> None:
    from sfrfr.services import document_ingest_worker as worker

    updates: list[dict] = []
    client = MagicMock()
    monkeypatch.setattr(worker, "get_supabase_client", lambda: client)
    monkeypatch.setattr(
        worker,
        "_update_document",
        lambda _c, _id, fields: updates.append(fields),
    )

    with patch(
        "sfrfr.integrations.yandex_workspace.case_mirror.mirror_case_document_safe",
        return_value={
            "ok": True,
            "path": "disk:/SFRFR-cases/folder/incoming/scan.pdf",
            "remote_name": "scan.pdf",
        },
    ):
        worker._mirror_document_after_security(
            case_id=CASE_ID,
            filename="scan.pdf",
            data=b"x",
            doc_type="labor_book",
            document_id=DOC_ID,
        )

    assert updates == [
        {
            "yandex_disk_path": "disk:/SFRFR-cases/folder/incoming/scan.pdf",
            "yandex_disk_status": "mirrored",
        }
    ]


def test_mirror_fail_does_not_clear_yandex_disk_path(monkeypatch: pytest.MonkeyPatch) -> None:
    from sfrfr.services import document_ingest_worker as worker

    updates: list[dict] = []
    monkeypatch.setattr(worker, "get_supabase_client", lambda: MagicMock())
    monkeypatch.setattr(
        worker,
        "_update_document",
        lambda _c, _id, fields: updates.append(fields),
    )

    with patch(
        "sfrfr.integrations.yandex_workspace.case_mirror.mirror_case_document_safe",
        return_value={"ok": False, "error": "timeout"},
    ):
        worker._mirror_document_after_security(
            case_id=CASE_ID,
            filename="scan.pdf",
            data=b"x",
            doc_type="labor_book",
            document_id=DOC_ID,
        )

    assert updates == []


def test_audit_after_resolve_and_safe_trace(monkeypatch: pytest.MonkeyPatch) -> None:
    from contextlib import contextmanager

    from sfrfr.services import document_ingest_worker as worker

    payload = b"%PDF-audit"
    digest = _sha(payload)
    doc_updates: list[dict] = []
    job_updates: list[dict] = []

    class _Table:
        def select(self, *_a, **_k) -> _Table:
            return self

        def eq(self, *_a, **_k) -> _Table:
            return self

        def limit(self, *_a, **_k) -> _Table:
            return self

        def update(self, *_a, **_k) -> _Table:
            return self

        def execute(self) -> MagicMock:
            return MagicMock(
                data=[
                    {
                        "id": "job-1",
                        "document_id": "doc-1",
                        "case_id": CASE_ID,
                        "status": "queued",
                        "attempts": 0,
                        "max_attempts": 3,
                        "storage_path": "quarantine/x/a.pdf",
                        "checksum_sha256": digest,
                        "mime_verified": "application/pdf",
                        "security_reason": "manual_expert_approval",
                        "local_path": f"quarantine/{CASE_ID}/a.pdf",
                    }
                ]
            )

    client = MagicMock()
    client.table = MagicMock(return_value=_Table())
    client.storage = MagicMock()

    @contextmanager
    def _fake_ctx(*_a, **_k):
        yield ResolvedBytes(
            data=payload,
            sha256=digest,
            size_bytes=len(payload),
            source_used="local_storage",
            local_path=f"quarantine/{CASE_ID}/a.pdf",
            resolve_trace=("local_scan_no_hash_match",),
        )

    monkeypatch.setattr(worker, "get_supabase_client", lambda: client)
    monkeypatch.setattr(worker, "resolve_ocr_bytes_ctx", _fake_ctx)
    monkeypatch.setattr(
        worker,
        "_update_document",
        lambda _c, _id, fields: doc_updates.append(dict(fields)),
    )
    monkeypatch.setattr(
        worker,
        "_update_job",
        lambda _c, _id, fields: job_updates.append(dict(fields)),
    )
    monkeypatch.setattr(
        worker,
        "run_document_ingest_v2",
        lambda **k: {
            "ingest_status": "under_review",
            "current_stage": "under_review",
            "progress_message": "ok",
            "placement_suggestion": {},
            "quality_report": {},
            "ingest_review_required": False,
            "extracted_text": "t",
            "manifest": {},
            "ingest_engine": "text_layer",
            "page_count": 1,
            "labor_timeline_drafts": [],
        },
    )
    monkeypatch.setattr(worker, "_store_verified_copy", lambda *a, **k: None)
    monkeypatch.setattr(worker, "_store_artifacts", lambda *a, **k: ("e", "m"))
    monkeypatch.setattr(worker, "_store_labor_drafts", lambda *a, **k: None)
    monkeypatch.setattr(worker, "_mirror_document_after_security", lambda **k: None)
    monkeypatch.setattr(worker, "_process_payment_receipt", lambda **k: None)
    monkeypatch.setattr(worker, "_scenario_codes", lambda *a, **k: set())

    out = worker.process_document_ingest_job("job-1")
    assert out.get("ocr_source_used") == "local_storage"

    audit_docs = [u for u in doc_updates if "ocr_source_used" in u]
    assert audit_docs
    assert audit_docs[0]["ocr_source_used"] == "local_storage"
    assert "ocr_source_verified_at" in audit_docs[0]

    audit_jobs = [u for u in job_updates if u.get("bytes_sha256")]
    assert audit_jobs
    assert audit_jobs[0]["bytes_sha256"] == digest
    assert audit_jobs[0]["ocr_source_used"] == "local_storage"
    assert "local_scan_no_hash_match" in (audit_jobs[0].get("resolve_trace") or [])

    verified = [u for u in doc_updates if u.get("local_status") == "verified"]
    assert verified


def test_unresolved_does_not_set_false_source_used(monkeypatch: pytest.MonkeyPatch) -> None:
    from contextlib import contextmanager

    from sfrfr.services import document_ingest_worker as worker

    job_updates: list[dict] = []
    doc_updates: list[dict] = []

    class _Table:
        def select(self, *_a, **_k) -> _Table:
            return self

        def eq(self, *_a, **_k) -> _Table:
            return self

        def limit(self, *_a, **_k) -> _Table:
            return self

        def execute(self) -> MagicMock:
            return MagicMock(
                data=[
                    {
                        "id": "job-1",
                        "document_id": "doc-1",
                        "case_id": CASE_ID,
                        "status": "queued",
                        "attempts": 0,
                        "max_attempts": 3,
                        "storage_path": "",
                        "checksum_sha256": _sha(b"x"),
                    }
                ]
            )

    @contextmanager
    def _boom(*_a, **_k):
        raise OcrSourceUnresolved(
            "ocr_source_unresolved",
            trace=["local_scan_no_hash_match", "yandex_disk_path_absent"],
        )
        yield  # pragma: no cover

    mock_client = MagicMock(table=MagicMock(return_value=_Table()))
    monkeypatch.setattr(worker, "get_supabase_client", lambda: mock_client)
    monkeypatch.setattr(worker, "resolve_ocr_bytes_ctx", _boom)
    monkeypatch.setattr(
        worker,
        "_update_document",
        lambda _c, _id, fields: doc_updates.append(fields),
    )
    monkeypatch.setattr(
        worker,
        "_update_job",
        lambda _c, _id, fields: job_updates.append(fields),
    )

    out = worker.process_document_ingest_job("job-1")
    assert out["status"] == "ocr_source_unresolved"
    assert all("ocr_source_used" not in u for u in doc_updates)
    assert all(u.get("ocr_source_used") is None or "ocr_source_used" not in u for u in job_updates)
    assert any(
        "local_scan_no_hash_match" in (u.get("resolve_trace") or []) for u in job_updates
    )


def test_sanitize_resolve_trace_strips_paths_and_pii() -> None:
    dirty = [
        "local_path_miss_or_hash_mismatch",
        "disk:/SFRFR-cases/Иванов/incoming/a.pdf",
        "/opt/sfrfr/storage/uploads/x.pdf",
        "yandex_disk_error:TimeoutError",
        "token=secret",
        "https://cloud.example/x",
        "abc123deadbeef" * 2,
    ]
    clean = sanitize_resolve_trace(dirty)
    assert clean == [
        "local_path_miss_or_hash_mismatch",
        "yandex_disk_error:TimeoutError",
    ]
    joined = " ".join(clean)
    assert "Иванов" not in joined
    assert "/" not in joined
    assert "http" not in joined.lower()


def test_legacy_doc_without_paths_uses_storage_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    payload = b"legacy-storage-only"
    digest = _sha(payload)
    monkeypatch.setenv("STORAGE_LOCAL_PATH", str(tmp_path))
    get_settings.cache_clear()
    storage_dl = MagicMock(return_value=payload)
    resolved = resolve_ocr_bytes(
        {
            "checksum_sha256": digest,
            "storage_path": "quarantine/old/doc.pdf",
            # no local_path / yandex_disk_path / size_bytes
        },
        case_id=CASE_ID,
        storage_download=storage_dl,
        storage_fallback=True,
    )
    assert resolved.source_used == "supabase_storage"
    storage_dl.assert_called_once()


def test_fallback_still_default_true() -> None:
    from sfrfr.core.config import Settings

    assert Settings.model_fields["ingest_ocr_storage_fallback"].default is True


def test_relative_to_uploads_no_leading_slash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("STORAGE_LOCAL_PATH", str(tmp_path))
    get_settings.cache_clear()
    f = tmp_path / "a" / "b.pdf"
    f.parent.mkdir()
    f.write_bytes(b"1")
    rel = relative_to_uploads(f)
    assert rel == "a/b.pdf"
