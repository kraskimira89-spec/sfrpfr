"""Папка дела по ФИО + байт-в-байт оригинал (local + Яндекс.Диск)."""

from __future__ import annotations

from sfrfr.utils.case_folder_name import format_case_disk_folder_name


def test_format_case_disk_folder_name_fio() -> None:
    cid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    assert (
        format_case_disk_folder_name("иванов иван иванович", case_id=cid)
        == "Иванов Иван Иванович"
    )


def test_format_case_disk_folder_name_fallback_uuid() -> None:
    cid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    assert format_case_disk_folder_name(None, case_id=cid) == cid
    assert format_case_disk_folder_name("Клиент", case_id=cid) == cid


def test_format_case_disk_folder_name_strips_path_chars() -> None:
    cid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    name = format_case_disk_folder_name("Иванов/Иван\\Иванович", case_id=cid)
    assert "/" not in name
    assert "\\" not in name
    assert "Иванов" in name


def test_mirror_uses_fio_folder_and_same_bytes(monkeypatch, tmp_path) -> None:
    """Зеркало: путь с ФИО, тело файла = исходные байты; local = тот же оригинал."""
    from sfrfr.integrations.yandex_workspace import case_mirror as cm
    from sfrfr.integrations.yandex_workspace import disk as disk_mod

    cid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    original = b"%PDF-1.4-original-bytes-xyz"
    uploaded: list[dict] = []

    monkeypatch.setenv("YANDEX_DISK_ENABLED", "true")
    monkeypatch.setenv("YANDEX_OAUTH_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("STORAGE_LOCAL_PATH", str(tmp_path / "uploads"))
    from sfrfr.core.config import get_settings
    from sfrfr.integrations.yandex_workspace import oauth as oauth_mod

    oauth_mod._loaded = True
    get_settings.cache_clear()

    def _fake_put(*, path: str, content: bytes, overwrite: bool) -> dict:
        uploaded.append({"path": path, "content": content, "overwrite": overwrite})
        return {"ok": True, "path": path, "status_code": 201}

    monkeypatch.setattr(disk_mod, "_put_upload", _fake_put)
    monkeypatch.setattr(
        disk_mod,
        "_ensure_disk_folder",
        lambda target, *, allow_cases=False: {"ok": True, "path": target, "exists": True},
    )
    monkeypatch.setattr(
        cm, "lookup_case_client_full_name", lambda _cid: "Петров Пётр Петрович"
    )
    monkeypatch.setattr(
        cm, "maybe_export_case_chat_throttled", lambda _cid: {"ok": False, "skipped": True}
    )

    result = cm.mirror_case_document_safe(cid, "скан ИЛС.pdf", original, doc_type="ils")
    assert result.get("ok") is True
    assert uploaded, "ожидалась загрузка на Диск"
    path = uploaded[0]["path"]
    assert "Петров Пётр Петрович" in path
    assert "/incoming/" in path
    folder_seg = path.split("/")[2]
    assert cid not in folder_seg
    assert uploaded[0]["content"] == original

    local_files = list((tmp_path / "uploads" / cid).glob("*"))
    assert len(local_files) == 1
    assert local_files[0].read_bytes() == original
    get_settings.cache_clear()


def test_mirror_skips_bank_no_local(monkeypatch, tmp_path) -> None:
    from sfrfr.integrations.yandex_workspace import case_mirror as cm

    monkeypatch.setenv("STORAGE_LOCAL_PATH", str(tmp_path / "uploads"))
    from sfrfr.core.config import get_settings

    get_settings.cache_clear()
    result = cm.mirror_case_document_safe(
        "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        "bank.pdf",
        b"%PDF",
        doc_type="bank_statement",
    )
    assert result.get("skipped") is True
    root = tmp_path / "uploads"
    assert (not root.exists()) or (not list(root.rglob("*")))
    get_settings.cache_clear()
