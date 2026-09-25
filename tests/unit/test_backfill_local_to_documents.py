"""Тесты backfill local uploads → documents."""

from __future__ import annotations

from pathlib import Path

from sfrfr.services.backfill_local_to_documents import (
    _strip_local_prefix,
    backfill_local_uploads_to_documents,
)


def test_strip_local_prefix() -> None:
    assert _strip_local_prefix("a1b2c3d4_scan.pdf") == "scan.pdf"
    assert _strip_local_prefix("scan.pdf") == "scan.pdf"


def test_backfill_dry_run_counts(monkeypatch, tmp_path: Path) -> None:
    case = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    cdir = tmp_path / case
    cdir.mkdir()
    (cdir / "deadbeef_document.bin").write_bytes(b"%PDF-1.4 hello")

    monkeypatch.setattr(
        "sfrfr.storage.local.uploads_root",
        lambda: tmp_path,
    )

    class _FakeTable:
        def select(self, *_a, **_k):
            return self

        def eq(self, *_a, **_k):
            return self

        def limit(self, *_a, **_k):
            return self

        def execute(self):
            return type("R", (), {"data": [{"id": case}]})()

    class _FakeSB:
        def table(self, _name: str):
            return _FakeTable()

    monkeypatch.setattr(
        "sfrfr.db.session.get_supabase_client",
        lambda: _FakeSB(),
    )
    monkeypatch.setattr(
        "sfrfr.services.document_upload.find_duplicate_checksum",
        lambda *_a, **_k: False,
    )

    result = backfill_local_uploads_to_documents(dry_run=True)
    assert result["ok"] is True
    assert result["registered"] == 1
    assert result["dry_run"] is True
