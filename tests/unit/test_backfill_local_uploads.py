"""dry_run backfill не читает содержимое файлов."""

from __future__ import annotations

from pathlib import Path

from sfrfr.integrations.yandex_workspace.backfill_local_uploads import (
    backfill_local_uploads_to_disk,
)


def test_dry_run_skips_read_bytes(tmp_path: Path, monkeypatch) -> None:
    case = tmp_path / "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    case.mkdir()
    blob = case / "deadbeef_scan.pdf"
    blob.write_bytes(b"\x00" * 50_000)

    reads = {"n": 0}
    real_read = Path.read_bytes

    def counting_read(self: Path) -> bytes:
        reads["n"] += 1
        return real_read(self)

    monkeypatch.setattr(Path, "read_bytes", counting_read)
    monkeypatch.setattr(
        "sfrfr.storage.local.uploads_root",
        lambda: tmp_path,
    )

    result = backfill_local_uploads_to_disk(dry_run=True)

    assert result["ok"] is True
    assert result["dry_run"] is True
    assert result["uploaded"] == 1
    assert reads["n"] == 0


def test_upload_reads_bytes_once(tmp_path: Path, monkeypatch) -> None:
    case = tmp_path / "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    case.mkdir()
    blob = case / "deadbeef_scan.pdf"
    blob.write_bytes(b"pdf-bytes")

    reads = {"n": 0}
    real_read = Path.read_bytes

    def counting_read(self: Path) -> bytes:
        reads["n"] += 1
        return real_read(self)

    monkeypatch.setattr(Path, "read_bytes", counting_read)
    monkeypatch.setattr("sfrfr.storage.local.uploads_root", lambda: tmp_path)
    monkeypatch.setattr(
        "sfrfr.integrations.yandex_workspace.case_mirror.mirror_case_document_safe",
        lambda *_a, **_k: {"ok": True},
    )

    result = backfill_local_uploads_to_disk(dry_run=False)

    assert result["uploaded"] == 1
    assert reads["n"] == 1
