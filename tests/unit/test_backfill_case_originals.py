"""Backfill старых загрузок → local + Disk FIO, идемпотентно."""

from __future__ import annotations

import hashlib
from pathlib import Path

from sfrfr.integrations.yandex_workspace.backfill_case_originals import (
    backfill_case_originals_to_fio,
    local_has_sha256,
    remote_basename,
)


def test_remote_basename_strips_local_prefix() -> None:
    assert remote_basename("deadbeef_scan.pdf") == "scan.pdf"
    assert remote_basename("scan.pdf") == "scan.pdf"


def test_local_has_sha256(tmp_path: Path) -> None:
    case = tmp_path / "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    case.mkdir()
    data = b"%PDF-original"
    (case / "aabbccdd_scan.pdf").write_bytes(data)
    digest = hashlib.sha256(data).hexdigest()
    assert local_has_sha256(case, digest) is True
    assert local_has_sha256(case, "0" * 64) is False


def test_backfill_dry_run_counts_without_mirror(tmp_path: Path, monkeypatch) -> None:
    cid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    case = tmp_path / cid
    case.mkdir()
    (case / "deadbeef_scan.pdf").write_bytes(b"pdf-bytes")

    calls: list[dict] = []

    monkeypatch.setattr(
        "sfrfr.storage.local.uploads_root",
        lambda: tmp_path,
    )
    monkeypatch.setattr(
        "sfrfr.integrations.yandex_workspace.backfill_case_originals._iter_storage_blobs",
        lambda **_kw: [],
    )
    monkeypatch.setattr(
        "sfrfr.integrations.yandex_workspace.case_mirror.mirror_case_document_safe",
        lambda *a, **k: calls.append({"a": a, "k": k}) or {"ok": True},
    )

    result = backfill_case_originals_to_fio(dry_run=True)
    assert result["ok"] is True
    assert result["dry_run"] is True
    assert result["cases"] == 1
    assert result["files"] == 1
    assert result["uploaded"] == 1
    assert calls == []


def test_backfill_skips_duplicate_sha_on_second_pass(tmp_path: Path, monkeypatch) -> None:
    cid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    case = tmp_path / cid
    case.mkdir()
    data = b"%PDF-same-bytes"
    (case / "deadbeef_scan.pdf").write_bytes(data)

    state = tmp_path / "backfill_fio_seen.json"
    mirrors: list[dict] = []

    monkeypatch.setattr("sfrfr.storage.local.uploads_root", lambda: tmp_path)
    monkeypatch.setattr(
        "sfrfr.integrations.yandex_workspace.backfill_case_originals._state_path",
        lambda: state,
    )
    monkeypatch.setattr(
        "sfrfr.integrations.yandex_workspace.backfill_case_originals._iter_storage_blobs",
        lambda **_kw: [],
    )
    monkeypatch.setattr(
        "sfrfr.integrations.yandex_workspace.case_mirror.mirror_case_document_safe",
        lambda *_a, **k: mirrors.append(k) or {"ok": True},
    )

    first = backfill_case_originals_to_fio(dry_run=False)
    second = backfill_case_originals_to_fio(dry_run=False)

    assert first["uploaded"] == 1
    assert second["uploaded"] == 0
    assert second["skipped"] == 1
    assert len(mirrors) == 1
    assert mirrors[0].get("persist_local") is False
