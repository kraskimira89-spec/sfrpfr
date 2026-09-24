"""Phase 1: OCR source resolver — local → Disk(temp) → Storage fallback."""

from __future__ import annotations

import hashlib
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from sfrfr.core.config import get_settings
from sfrfr.services.ocr_source_resolver import (
    OcrSourceUnresolved,
    ResolvedBytes,
    resolve_ocr_bytes,
    resolve_ocr_bytes_ctx,
)

CASE_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_local_hash_match_skips_storage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    payload = b"%PDF-local-ok"
    digest = _sha(payload)
    case_dir = tmp_path / CASE_ID
    case_dir.mkdir()
    (case_dir / "deadbeef_scan.pdf").write_bytes(payload)

    monkeypatch.setenv("STORAGE_LOCAL_PATH", str(tmp_path))
    get_settings.cache_clear()

    storage_dl = MagicMock(side_effect=AssertionError("storage must not be called"))
    disk_dl = MagicMock(side_effect=AssertionError("disk must not be called"))

    resolved = resolve_ocr_bytes(
        {
            "checksum_sha256": digest,
            "size_bytes": len(payload),
            "storage_path": "quarantine/x/scan.pdf",
        },
        case_id=CASE_ID,
        storage_download=storage_dl,
        disk_download_to_temp=disk_dl,
        storage_fallback=True,
    )

    assert isinstance(resolved, ResolvedBytes)
    assert resolved.source_used == "local_storage"
    assert resolved.data == payload
    assert resolved.sha256 == digest
    storage_dl.assert_not_called()
    disk_dl.assert_not_called()


def test_local_hash_mismatch_skips_to_disk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    wrong = b"wrong-bytes"
    want = b"correct-bytes"
    want_digest = _sha(want)
    case_dir = tmp_path / CASE_ID
    case_dir.mkdir()
    bad = case_dir / "aaaa_bad.pdf"
    bad.write_bytes(wrong)

    monkeypatch.setenv("STORAGE_LOCAL_PATH", str(tmp_path))
    get_settings.cache_clear()

    temp = tmp_path / "disk-temp.pdf"
    temp.write_bytes(want)

    disk_dl = MagicMock(return_value=temp)
    storage_dl = MagicMock(side_effect=AssertionError("storage must not be called"))

    resolved = resolve_ocr_bytes(
        {
            "checksum_sha256": want_digest,
            "local_path": str(bad),
            "yandex_disk_path": "disk:/SFRFR-cases/Ivanov/incoming/scan.pdf",
            "storage_path": "quarantine/x/scan.pdf",
        },
        case_id=CASE_ID,
        storage_download=storage_dl,
        disk_download_to_temp=disk_dl,
        storage_fallback=True,
    )

    assert resolved.source_used == "yandex_disk"
    assert resolved.data == want
    assert resolved.temp_path == temp
    disk_dl.assert_called_once()
    storage_dl.assert_not_called()


def test_local_path_outside_uploads_root_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """local_path вне storage/uploads не читается, даже при совпадении hash."""
    payload = b"secret-outside"
    digest = _sha(payload)
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    outside = tmp_path / "etc" / "passwd-like.bin"
    outside.parent.mkdir()
    outside.write_bytes(payload)

    monkeypatch.setenv("STORAGE_LOCAL_PATH", str(uploads))
    get_settings.cache_clear()

    disk_dl = MagicMock(side_effect=AssertionError("disk must not be called"))
    storage_dl = MagicMock(return_value=payload)

    resolved = resolve_ocr_bytes(
        {
            "checksum_sha256": digest,
            "local_path": str(outside),
            "storage_path": "quarantine/x/scan.pdf",
        },
        case_id=CASE_ID,
        storage_download=storage_dl,
        disk_download_to_temp=disk_dl,
        storage_fallback=True,
    )

    assert resolved.source_used == "supabase_storage"
    storage_dl.assert_called_once()
    disk_dl.assert_not_called()


def test_disk_temp_deleted_in_ctx_finally(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    payload = b"from-disk"
    digest = _sha(payload)
    temp = tmp_path / "yd-temp.bin"
    temp.write_bytes(payload)
    monkeypatch.setenv("STORAGE_LOCAL_PATH", str(tmp_path / "empty-uploads"))
    get_settings.cache_clear()

    with resolve_ocr_bytes_ctx(
        {
            "checksum_sha256": digest,
            "yandex_disk_path": "disk:/SFRFR-cases/uuid/incoming/a.pdf",
        },
        case_id=CASE_ID,
        disk_download_to_temp=lambda _p: temp,
        storage_fallback=False,
    ) as resolved:
        assert resolved.source_used == "yandex_disk"
        assert temp.exists()

    assert not temp.exists()


def test_fallback_false_raises_without_local_disk(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("STORAGE_LOCAL_PATH", str(tmp_path))
    monkeypatch.setenv("INGEST_OCR_STORAGE_FALLBACK", "false")
    get_settings.cache_clear()

    storage_dl = MagicMock(return_value=b"from-storage")

    with pytest.raises(OcrSourceUnresolved):
        resolve_ocr_bytes(
            {
                "checksum_sha256": _sha(b"x"),
                "storage_path": "quarantine/x/scan.pdf",
            },
            case_id=CASE_ID,
            storage_download=storage_dl,
            storage_fallback=False,
        )

    storage_dl.assert_not_called()


def test_fallback_true_uses_storage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    payload = b"storage-bytes"
    digest = _sha(payload)
    monkeypatch.setenv("STORAGE_LOCAL_PATH", str(tmp_path))
    get_settings.cache_clear()

    storage_dl = MagicMock(return_value=payload)

    resolved = resolve_ocr_bytes(
        {
            "checksum_sha256": digest,
            "size_bytes": len(payload),
            "storage_path": "quarantine/case/doc.pdf",
        },
        case_id=CASE_ID,
        storage_download=storage_dl,
        storage_fallback=True,
    )

    assert resolved.source_used == "supabase_storage"
    assert resolved.data == payload
    storage_dl.assert_called_once_with("quarantine/case/doc.pdf")


def test_unresolved_when_all_fail(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STORAGE_LOCAL_PATH", str(tmp_path))
    get_settings.cache_clear()

    with pytest.raises(OcrSourceUnresolved) as exc:
        resolve_ocr_bytes(
            {"checksum_sha256": _sha(b"missing")},
            case_id=CASE_ID,
            storage_fallback=False,
        )
    assert "trace" in str(exc.value).lower() or exc.value.trace


def test_no_fio_lookup_on_resolve(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Resolver не ищет путь на Диске по ФИО."""
    import sfrfr.services.ocr_source_resolver as mod
    from sfrfr.integrations.yandex_workspace import case_mirror

    monkeypatch.setenv("STORAGE_LOCAL_PATH", str(tmp_path))
    get_settings.cache_clear()
    fio = MagicMock(return_value="Иванов Иван")
    monkeypatch.setattr(mod, "lookup_case_client_full_name", fio, raising=False)
    monkeypatch.setattr(case_mirror, "lookup_case_client_full_name", fio)

    with pytest.raises(OcrSourceUnresolved):
        resolve_ocr_bytes(
            {"storage_path": ""},
            case_id=CASE_ID,
            storage_fallback=False,
        )

    fio.assert_not_called()


def test_worker_uses_resolver_not_bare_storage(monkeypatch: pytest.MonkeyPatch) -> None:
    """process_document_ingest_job берёт байты через resolver, не голый Storage.download."""
    from contextlib import contextmanager

    from sfrfr.services import document_ingest_worker as worker
    from sfrfr.services.ocr_source_resolver import ResolvedBytes

    payload = b"%PDF-via-resolver"
    digest = _sha(payload)
    storage_download_calls: list[str] = []

    class _Bucket:
        def download(self, path: str) -> bytes:
            storage_download_calls.append(path)
            raise AssertionError("bare storage.download must not run")

        def upload(self, *_a, **_k) -> None:
            return None

        def remove(self, *_a, **_k) -> None:
            return None

    class _Storage:
        def from_(self, _bucket: str) -> _Bucket:
            return _Bucket()

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
                        "id": "doc-1",
                        "case_id": CASE_ID,
                        "storage_path": "quarantine/x/a.pdf",
                        "checksum_sha256": digest,
                        "mime_verified": "application/pdf",
                        "security_reason": "manual_expert_approval",
                    }
                ]
            )

    client = MagicMock()
    client.storage = _Storage()
    client.table = MagicMock(return_value=_Table())

    @contextmanager
    def _fake_ctx(*_a, **_k):
        yield ResolvedBytes(
            data=payload,
            sha256=digest,
            size_bytes=len(payload),
            source_used="local_storage",
            local_path="/tmp/x.pdf",
        )

    monkeypatch.setattr(worker, "get_supabase_client", lambda: client)
    monkeypatch.setattr(worker, "resolve_ocr_bytes_ctx", _fake_ctx)
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
    monkeypatch.setattr(worker, "_scenario_codes", lambda *a, **k: [])
    monkeypatch.setattr(worker, "_update_job", lambda *a, **k: None)
    monkeypatch.setattr(worker, "_update_document", lambda *a, **k: None)

    out = worker.process_document_ingest_job(
        {
            "id": "job-1",
            "status": "queued",
            "document_id": "doc-1",
            "case_id": CASE_ID,
            "attempts": 0,
            "max_attempts": 3,
        }
    )
    assert out.get("ocr_source_used") == "local_storage"
    assert storage_download_calls == []
