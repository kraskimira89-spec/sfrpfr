"""MAX ingest: local-first — клиенту OK, даже если облако падает."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from sfrfr.integrations.max import handler as max_handler
from sfrfr.services.document_ingest_worker import create_quarantine_document
from sfrfr.services.max_document_upload import upload_max_document


@pytest.fixture()
def uploads_tmp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "uploads"
    root.mkdir()
    monkeypatch.setenv("STORAGE_LOCAL_PATH", str(root))
    from sfrfr.core.config import get_settings

    get_settings.cache_clear()
    yield root
    get_settings.cache_clear()


class _BoomStorage:
    def from_(self, _bucket: str) -> _BoomStorage:
        return self

    def upload(self, *_a: object, **_k: object) -> None:
        raise RuntimeError("permission denied for table buckets")

    def remove(self, *_a: object, **_k: object) -> None:
        return None


class _Client:
    storage = _BoomStorage()

    def table(self, *_a: object, **_k: object) -> MagicMock:
        raise AssertionError("table should not be required for local fallback")


def test_create_quarantine_local_fallback_when_storage_403(
    uploads_tmp: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "sfrfr.services.document_ingest_worker.get_supabase_client",
        lambda: _Client(),
    )
    monkeypatch.setattr(
        "sfrfr.services.document_ingest_worker.documents_has_ingest_columns",
        lambda: False,
    )
    monkeypatch.setattr(
        "sfrfr.services.document_ingest_worker.document_ingest_jobs_available",
        lambda: False,
    )
    monkeypatch.setattr(
        "sfrfr.services.document_ingest_worker.find_duplicate_checksum",
        lambda *_a, **_k: False,
    )

    row = create_quarantine_document(
        case_id="11111111-1111-1111-1111-111111111111",
        filename="document.bin",
        data=b"%PDF-1.4 from phone",
        content_type="application/octet-stream",
        doc_type=None,
        uploaded_by=None,
        upload_source="max",
        allow_local_fallback=True,
    )
    assert row["cloud_status"] == "pending"
    assert row["id"]
    assert row.get("local_path")
    assert list(uploads_tmp.rglob("*"))


def test_upload_max_document_ok_when_cloud_mock_fails(
    uploads_tmp: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "sfrfr.services.document_ingest_worker.get_supabase_client",
        lambda: _Client(),
    )
    monkeypatch.setattr(
        "sfrfr.services.document_ingest_worker.documents_has_ingest_columns",
        lambda: False,
    )
    monkeypatch.setattr(
        "sfrfr.services.document_ingest_worker.document_ingest_jobs_available",
        lambda: False,
    )
    monkeypatch.setattr(
        "sfrfr.services.document_ingest_worker.find_duplicate_checksum",
        lambda *_a, **_k: False,
    )
    row = upload_max_document(
        case_id="11111111-1111-1111-1111-111111111111",
        filename="document.bin",
        data=b"%PDF-1.4 from phone",
    )
    assert row is not None
    assert row.get("cloud_status") == "pending"
    assert str(row.get("id") or "")


def test_ingest_returns_id_when_cloud_pending(
    uploads_tmp: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import sfrfr.integrations.max.case_chat_log as clog
    import sfrfr.services.max_document_upload as mdu

    local_rel = "quarantine/case/doc.pdf"
    local_file = uploads_tmp / local_rel
    local_file.parent.mkdir(parents=True, exist_ok=True)
    local_file.write_bytes(b"%PDF-1.4")
    monkeypatch.setattr(
        mdu,
        "upload_max_document",
        lambda **_k: {
            "id": "doc-local-1",
            "cloud_status": "pending",
            "local_path": local_rel,
            "ingest_status": "needs_reupload",
        },
    )
    logged: list[dict] = []
    monkeypatch.setattr(clog, "append_case_chat_message", lambda **kwargs: logged.append(kwargs))
    monkeypatch.setattr(clog, "format_document_event", lambda **_k: "doc event")
    ok = max_handler._ingest_max_file(
        case_id="11111111-1111-1111-1111-111111111111",
        filename="document.bin",
        data=b"%PDF-1.4",
        store=MagicMock(),
        record=SimpleNamespace(case_id="local-1"),
    )
    assert ok == "doc-local-1"
    assert logged


def test_create_quarantine_local_fallback_when_client_unavailable(
    uploads_tmp: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _no_client() -> None:
        raise RuntimeError("supabase client unavailable")

    monkeypatch.setattr(
        "sfrfr.services.document_ingest_worker.get_supabase_client",
        _no_client,
    )
    monkeypatch.setattr(
        "sfrfr.services.document_ingest_worker.documents_has_ingest_columns",
        lambda: False,
    )
    monkeypatch.setattr(
        "sfrfr.services.document_ingest_worker.document_ingest_jobs_available",
        lambda: False,
    )
    monkeypatch.setattr(
        "sfrfr.services.document_ingest_worker.find_duplicate_checksum",
        lambda *_a, **_k: False,
    )

    row = create_quarantine_document(
        case_id="11111111-1111-1111-1111-111111111111",
        filename="document.bin",
        data=b"%PDF-1.4 from phone",
        content_type="application/octet-stream",
        doc_type=None,
        uploaded_by=None,
        upload_source="max",
        allow_local_fallback=True,
    )
    assert row["cloud_status"] == "pending"
    assert row.get("local_path")
    assert list(uploads_tmp.rglob("*"))


def test_client_ok_summary_template() -> None:
    from sfrfr.integrations.max import document_type_flow as flow

    text = flow.received_summary_ru(filename="скан трудовой", doc_type=None)
    assert "получили" in text.lower()
    assert "PDF" not in text
    assert "DOCX" not in text
