"""Юнит-тесты Яндекс Workspace (без сети / с моками)."""

from __future__ import annotations

from sfrfr.integrations.yandex_workspace import disk_status, ping, send_mail
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


def test_mail_rejects_snils_marker(monkeypatch) -> None:
    monkeypatch.setenv("YANDEX_OAUTH_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("YANDEX_MAIL_ENABLED", "true")
    from sfrfr.core.config import get_settings
    from sfrfr.integrations.yandex_workspace import oauth as oauth_mod

    oauth_mod._loaded = True
    get_settings.cache_clear()
    result = send_mail(
        to="client@example.com",
        template="custom",
        body="Мой СНИЛС 123",
    )
    assert result.get("ok") is False
    assert result.get("error") == "body_contains_forbidden_markers"
    get_settings.cache_clear()


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
    from sfrfr.integrations.yandex_workspace.disk import _path_allowed

    assert _path_allowed("disk:/SFRFR-ops/template.docx") is True
    assert _path_allowed("disk:/SFRFR-ops/cases/scan.pdf") is False
    assert _path_allowed("disk:/other/file.txt") is False
