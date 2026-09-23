"""Тесты аудита и чистки папок SFRFR-cases (без сети)."""

from __future__ import annotations

from typing import Any

import pytest

from sfrfr.integrations.yandex_workspace import case_cleanup as cleanup

CID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
FIO = "Иванов Иван"


def _fake_listing(mapping: dict[str, list[dict[str, Any]]]):
    def fake(path: str) -> dict[str, Any]:
        items = mapping.get(path)
        if items is None:
            return {"ok": False, "status_code": 404, "path": path}
        return {"ok": True, "path": path, "count": len(items), "items": items}

    return fake


def _dir(name: str) -> dict[str, Any]:
    return {"name": name, "type": "dir"}


def _file(name: str) -> dict[str, Any]:
    return {"name": name, "type": "file"}


def test_dedupe_remote_name_keeps_readable_name() -> None:
    from sfrfr.integrations.yandex_workspace.disk import _dedupe_remote_name

    assert _dedupe_remote_name(set(), "scan.pdf") == "scan.pdf"
    assert _dedupe_remote_name({"scan.pdf"}, "scan.pdf") == "scan_2.pdf"
    assert _dedupe_remote_name({"scan.pdf", "scan_2.pdf"}, "scan.pdf") == "scan_3.pdf"
    assert _dedupe_remote_name({"noext"}, "noext") == "noext_2"
    assert _dedupe_remote_name(set(), "Извещение ИЛС.pdf") == "Извещение_ИЛС.pdf"


def test_mirror_uses_readable_name(monkeypatch: pytest.MonkeyPatch) -> None:
    from sfrfr.integrations.yandex_workspace import disk

    captured: dict[str, Any] = {}

    def fake_upload(case_id: str, **kwargs: Any) -> dict[str, Any]:
        captured["case_id"] = case_id
        captured.update(kwargs)
        return {"ok": True}

    monkeypatch.setattr(disk, "_list_remote_names", lambda _dest: set())
    monkeypatch.setattr(disk, "upload_case_file", fake_upload)
    result = disk.mirror_case_document(CID, "Извещение ИЛС.pdf", b"data")

    assert result["remote_name"] == "Извещение_ИЛС.pdf"
    assert result["subfolder"] == "incoming"
    assert captured["remote_name"] == "Извещение_ИЛС.pdf"


def test_root_files_allowed_only_for_service_ops() -> None:
    from sfrfr.integrations.yandex_workspace.disk import _cases_path_allowed

    legacy = f"disk:/SFRFR-cases/{CID}/old_scan.pdf"
    assert _cases_path_allowed(legacy) is False
    assert _cases_path_allowed(legacy, allow_root_files=True) is True
    assert _cases_path_allowed(f"disk:/SFRFR-cases/{CID}/incoming/x.pdf", case_id=CID) is True


@pytest.fixture
def duplicate_setup(monkeypatch: pytest.MonkeyPatch) -> dict[str, list[dict[str, Any]]]:
    """UUID-папка и ФИО-папка с тем же содержимым (префикс 8-hex)."""
    mapping = {
        "disk:/SFRFR-cases": [_dir(CID), _dir(FIO)],
        f"disk:/SFRFR-cases/{CID}": [_dir("incoming"), _file("meta.txt")],
        f"disk:/SFRFR-cases/{CID}/incoming": [
            _file("031f5639_Извещение_ИЛС.pdf"),
            _file("72abea36_scan.pdf"),
        ],
        f"disk:/SFRFR-cases/{FIO}": [_dir("incoming"), _file("meta.txt")],
        f"disk:/SFRFR-cases/{FIO}/incoming": [
            _file("Извещение_ИЛС.pdf"),
            _file("scan.pdf"),
        ],
    }
    monkeypatch.setattr(cleanup, "list_case_dir", _fake_listing(mapping))
    monkeypatch.setattr(cleanup, "lookup_case_client_full_name", lambda _cid: FIO)
    return mapping


def test_audit_reports_legacy_and_prefixes(
    duplicate_setup: dict[str, list[dict[str, Any]]],
) -> None:
    result = cleanup.audit_case_folders()

    assert result["ok"] is True
    assert result["count"] == 2
    assert result["uuid_folders"] == 1
    by_name = {row["folder"]: row for row in result["folders"]}
    assert by_name[CID]["is_uuid"] is True
    assert len(by_name[CID]["prefixed_names"]) == 2
    assert by_name[CID]["legacy_root_files"] == ["meta.txt"]


def test_cleanup_dry_run_marks_duplicate(
    duplicate_setup: dict[str, list[dict[str, Any]]],
) -> None:
    result = cleanup.cleanup_duplicate_uuid_folders(dry_run=True)

    assert result["deleted"] == 1
    assert result["actions"] == [{"action": "would_delete", "folder": CID, "duplicate_of": FIO}]


def test_cleanup_keeps_uuid_folder_when_files_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mapping = {
        "disk:/SFRFR-cases": [_dir(CID), _dir(FIO)],
        f"disk:/SFRFR-cases/{CID}": [_dir("incoming")],
        f"disk:/SFRFR-cases/{CID}/incoming": [_file("only_here.pdf")],
        f"disk:/SFRFR-cases/{FIO}": [_dir("incoming")],
        f"disk:/SFRFR-cases/{FIO}/incoming": [],
    }
    monkeypatch.setattr(cleanup, "list_case_dir", _fake_listing(mapping))
    monkeypatch.setattr(cleanup, "lookup_case_client_full_name", lambda _cid: FIO)

    result = cleanup.cleanup_duplicate_uuid_folders(dry_run=True)

    assert result["deleted"] == 0
    assert result["actions"][0]["reason"] == "files_not_in_fio_folder"


def test_normalize_legacy_plan(monkeypatch: pytest.MonkeyPatch) -> None:
    mapping = {
        "disk:/SFRFR-cases": [_dir(CID)],
        f"disk:/SFRFR-cases/{CID}": [
            _file("031f5639_scan.pdf"),
            _file("meta.txt"),
        ],
    }
    monkeypatch.setattr(cleanup, "list_case_dir", _fake_listing(mapping))

    result = cleanup.normalize_legacy_folders(dry_run=True)

    assert result["normalized"] == 1
    assert result["actions"][0]["move_to_incoming"] == ["031f5639_scan.pdf"]
    assert result["actions"][0]["ensure_meta"] is False
