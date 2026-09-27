"""Письма со ссылками входа уходят без набора конфигурации (без подмены ссылок Postbox)."""

from __future__ import annotations

import json

import pytest

from sfrfr.core.config import get_settings
from sfrfr.integrations.yandex_postbox import send as postbox


class _Resp:
    status_code = 200
    text = '{"MessageId":"m1"}'

    def json(self) -> dict:
        return {"MessageId": "m1"}


@pytest.fixture
def captured(monkeypatch) -> list[dict]:
    monkeypatch.setenv("YANDEX_POSTBOX_ENABLED", "1")
    monkeypatch.setenv("YANDEX_POSTBOX_FROM_EMAIL", "noreply@example.ru")
    monkeypatch.setenv("YANDEX_POSTBOX_ACCESS_KEY_ID", "k")
    monkeypatch.setenv("YANDEX_POSTBOX_SECRET_ACCESS_KEY", "s")
    monkeypatch.setenv("YANDEX_POSTBOX_CONFIGURATION_SET", "sfrfr-default")
    get_settings.cache_clear()
    payloads: list[dict] = []

    class _Client:
        def __init__(self, **_kw) -> None: ...

        def __enter__(self):
            return self

        def __exit__(self, *_a) -> None: ...

        def post(self, _url, *, content, headers):  # noqa: ANN001
            payloads.append(json.loads(content))
            return _Resp()

    monkeypatch.setattr(postbox.httpx, "Client", _Client)
    return payloads


def test_default_uses_configuration_set(captured: list[dict]) -> None:
    assert postbox.send_email_postbox(to="a@b.ru", subject="s", text="t")["ok"]
    assert captured[-1]["ConfigurationSetName"] == "sfrfr-default"


def test_track_links_off_omits_configuration_set(captured: list[dict]) -> None:
    assert postbox.send_email_postbox(to="a@b.ru", subject="s", text="t", track_links=False)["ok"]
    assert "ConfigurationSetName" not in captured[-1]


def test_send_mail_passes_track_links(captured: list[dict]) -> None:
    from sfrfr.integrations.yandex_workspace.mail import send_mail

    assert send_mail(to="a@b.ru", template="custom", body="x", track_links=False)["ok"]
    assert "ConfigurationSetName" not in captured[-1]
