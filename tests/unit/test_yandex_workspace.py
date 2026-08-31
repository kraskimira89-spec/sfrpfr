"""Юнит-тесты Яндекс Workspace (без сети / с моками)."""

from __future__ import annotations

from sfrfr.integrations.yandex_workspace import disk_status, ping
from sfrfr.integrations.yandex_workspace.mail import _xoauth2_string
from sfrfr.integrations.yandex_workspace.telemost import create_conference


def test_ping_skipped_without_token(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("YANDEX_OAUTH_ACCESS_TOKEN", "")
    from sfrfr.core.config import get_settings
    from sfrfr.integrations.yandex_workspace import oauth as oauth_mod

    oauth_mod._loaded = False
    monkeypatch.setattr(oauth_mod, "_DEFAULT_SECRETS", tmp_path / "missing.env")
    get_settings.cache_clear()
    result = ping()
    assert result.get("skipped") is True
    get_settings.cache_clear()


def test_telemost_skipped_when_disabled(monkeypatch) -> None:
    monkeypatch.setenv("YANDEX_OAUTH_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("YANDEX_TELEMOST_ENABLED", "false")
    from sfrfr.core.config import get_settings
    from sfrfr.integrations.yandex_workspace import oauth as oauth_mod

    oauth_mod._loaded = True
    get_settings.cache_clear()
    result = create_conference()
    assert result.get("skipped") is True
    assert "TELEMOST" in (result.get("reason") or "")
    get_settings.cache_clear()


def test_mail_redacts_snils_marker(monkeypatch) -> None:
    from sfrfr.integrations.yandex_workspace.mail import redact_outbound_body

    redacted = redact_outbound_body("Мой СНИЛС 123 и паспорт")
    assert "снилс" not in redacted.lower()
    assert "паспорт" not in redacted.lower()
    assert "[…]" in redacted


def test_xoauth2_encoding() -> None:
    encoded = _xoauth2_string("a@yandex.ru", "token123")
    assert isinstance(encoded, str) and len(encoded) > 10


def test_disk_disabled_when_flag_false(monkeypatch) -> None:
    monkeypatch.setenv("YANDEX_DISK_ENABLED", "false")
    from sfrfr.core.config import get_settings
    from sfrfr.integrations.yandex_workspace import oauth as oauth_mod

    oauth_mod._loaded = True
    get_settings.cache_clear()
    result = disk_status()
    assert result.get("skipped") is True
    get_settings.cache_clear()


def test_disk_path_policy() -> None:
    from sfrfr.integrations.yandex_workspace.disk import _cases_path_allowed, _path_allowed

    assert _path_allowed("disk:/SFRFR-ops/template.docx") is True
    assert _path_allowed("disk:/SFRFR-ops/cases/scan.pdf") is False
    assert _path_allowed("disk:/other/file.txt") is False
    assert _path_allowed("disk:/SFRFR-cases/x") is False

    cid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    assert _cases_path_allowed("disk:/SFRFR-cases") is True
    assert _cases_path_allowed(f"disk:/SFRFR-cases/{cid}") is True
    assert _cases_path_allowed(f"disk:/SFRFR-cases/{cid}/scan.pdf", case_id=cid) is True
    assert _cases_path_allowed("disk:/SFRFR-cases/not-a-uuid/f.pdf") is False
    other = "11111111-1111-1111-1111-111111111111"
    assert _cases_path_allowed(f"disk:/SFRFR-cases/{cid}/f.pdf", case_id=other) is False
    assert _cases_path_allowed("disk:/SFRFR-ops/x") is False


def test_upload_case_file_skipped_when_disabled(monkeypatch) -> None:
    monkeypatch.setenv("YANDEX_DISK_ENABLED", "false")
    from sfrfr.core.config import get_settings
    from sfrfr.integrations.yandex_workspace import oauth as oauth_mod
    from sfrfr.integrations.yandex_workspace.disk import upload_case_file

    oauth_mod._loaded = True
    get_settings.cache_clear()
    result = upload_case_file(
        "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        remote_name="doc.pdf",
        content=b"%PDF",
    )
    assert result.get("skipped") is True
    get_settings.cache_clear()


def test_mirror_case_document_invalid_case_id(monkeypatch) -> None:
    monkeypatch.setenv("YANDEX_DISK_ENABLED", "true")
    monkeypatch.setenv("YANDEX_OAUTH_ACCESS_TOKEN", "tok")
    from sfrfr.core.config import get_settings
    from sfrfr.integrations.yandex_workspace import oauth as oauth_mod
    from sfrfr.integrations.yandex_workspace.case_mirror import mirror_case_document_safe

    oauth_mod._loaded = True
    get_settings.cache_clear()
    result = mirror_case_document_safe("local-not-uuid", "a.pdf", b"x")
    assert result.get("ok") is False
    assert result.get("error") == "invalid_case_id"
    get_settings.cache_clear()


def test_imap_skipped_when_disabled(monkeypatch) -> None:
    monkeypatch.setenv("YANDEX_OAUTH_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("YANDEX_MAIL_ENABLED", "true")
    monkeypatch.setenv("YANDEX_MAIL_IMAP_ENABLED", "false")
    from sfrfr.core.config import get_settings
    from sfrfr.integrations.yandex_workspace import oauth as oauth_mod
    from sfrfr.integrations.yandex_workspace.mail_imap import imap_ping, list_inbox

    oauth_mod._loaded = True
    get_settings.cache_clear()
    ping_result = imap_ping()
    list_result = list_inbox()
    assert ping_result.get("skipped") is True
    assert "IMAP" in (ping_result.get("reason") or "")
    assert list_result.get("skipped") is True
    get_settings.cache_clear()


def test_fetch_invalid_uid(monkeypatch) -> None:
    monkeypatch.setenv("YANDEX_OAUTH_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("YANDEX_MAIL_ENABLED", "true")
    monkeypatch.setenv("YANDEX_MAIL_IMAP_ENABLED", "true")
    from sfrfr.core.config import get_settings
    from sfrfr.integrations.yandex_workspace import oauth as oauth_mod
    from sfrfr.integrations.yandex_workspace.mail_imap import fetch_message

    oauth_mod._loaded = True
    get_settings.cache_clear()
    result = fetch_message("not-a-uid")
    assert result.get("ok") is False
    assert result.get("error") == "invalid_uid"
    get_settings.cache_clear()
