from __future__ import annotations

import pytest
from fastapi import HTTPException

from sfrfr.api.routes.public_leads import (
    _captcha_mode,
    _from_wpforms_payload,
    _normalize_channel,
    _require_amocrm_lead,
)


def test_wpforms_payload_does_not_invent_consent() -> None:
    payload = _from_wpforms_payload(
        {
            "fields": {
                "1": {"name": "Имя", "type": "name", "value": "Иван Иванов"},
                "2": {"name": "Телефон", "type": "phone", "value": "+7 900 000-00-00"},
            }
        }
    )

    assert payload is not None
    assert payload.consent is False
    assert payload.phone == "+7 900 000-00-00"


def test_wpforms_payload_keeps_explicit_consent() -> None:
    payload = _from_wpforms_payload(
        {
            "fields": {
                "1": {"name": "Имя", "type": "name", "value": "Иван Иванов"},
                "2": {"name": "Телефон", "type": "phone", "value": "+7 900 000-00-00"},
                "3": {"name": "Согласие", "value": "Да"},
            }
        }
    )

    assert payload is not None
    assert payload.consent is True


def test_wpforms_payload_reads_preferred_channel() -> None:
    payload = _from_wpforms_payload(
        {
            "fields": {
                "1": {"name": "Имя", "type": "name", "value": "Иван"},
                "2": {"name": "Телефон", "type": "phone", "value": "+79001112233"},
                "5": {"name": "Предпочтительный канал", "value": "MAX (мессенджер)"},
                "3": {"name": "Согласие", "value": "Да"},
            }
        }
    )
    assert payload is not None
    assert payload.preferred_channel == "max_miniapp"


def test_wpforms_payload_email_without_phone() -> None:
    payload = _from_wpforms_payload(
        {
            "fields": {
                "1": {"name": "Имя", "type": "name", "value": "Анна"},
                "6": {"name": "Электронная почта", "type": "email", "value": "a@example.com"},
                "3": {"name": "Согласие", "value": "Да"},
            }
        }
    )
    assert payload is not None
    assert payload.email == "a@example.com"
    assert not payload.phone


def test_wpforms_payload_requires_email_or_phone() -> None:
    payload = _from_wpforms_payload(
        {
            "fields": {
                "1": {"name": "Имя", "type": "name", "value": "Анна"},
                "3": {"name": "Согласие", "value": "Да"},
            }
        }
    )
    assert payload is None


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("max_miniapp", "max_miniapp"),
        ("MAX (мессенджер)", "max_miniapp"),
        ("Личный кабинет на сайте", "web_cabinet"),
        ("", "unset"),
        (None, "unset"),
    ],
)
def test_normalize_channel(raw: str | None, expected: str) -> None:
    assert _normalize_channel(raw) == expected


def test_require_amocrm_fails_without_lead(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FakeAmo:
        available = True

        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

    monkeypatch.setenv("APP_ENV", "production")
    from sfrfr.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setattr("sfrfr.api.routes.public_leads.AmoCrmClient", _FakeAmo)
    with pytest.raises(HTTPException) as exc:
        _require_amocrm_lead({"ok": False, "skipped": False})
    assert exc.value.status_code == 502
    get_settings.cache_clear()


def test_require_amocrm_fails_when_not_configured_in_prod(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FakeAmo:
        available = False

        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

    monkeypatch.setenv("APP_ENV", "production")
    from sfrfr.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setattr("sfrfr.api.routes.public_leads.AmoCrmClient", _FakeAmo)
    with pytest.raises(HTTPException) as exc:
        _require_amocrm_lead({"ok": False, "skipped": True})
    assert exc.value.status_code == 503
    get_settings.cache_clear()


def test_production_forces_yandex_captcha(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("CAPTCHA_PROVIDER", "google")
    from sfrfr.core.config import get_settings

    get_settings.cache_clear()
    assert _captcha_mode() == "yandex"
    get_settings.cache_clear()
