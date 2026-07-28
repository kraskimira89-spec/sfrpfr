from __future__ import annotations

import pytest
from fastapi import HTTPException

from sfrfr.api.routes.public_leads import (
    _from_wpforms_payload,
    _normalize_channel,
    _require_amocrm_lead,
)


def test_wpforms_payload_does_not_invent_consent() -> None:
    payload = _from_wpforms_payload(
        {
            "fields": {
                "1": {"name": "Имя", "value": "Иван Иванов"},
                "2": {"name": "Телефон", "value": "+7 900 000-00-00"},
            }
        }
    )

    assert payload is not None
    assert payload.consent is False


def test_wpforms_payload_keeps_explicit_consent() -> None:
    payload = _from_wpforms_payload(
        {
            "fields": {
                "1": {"name": "Имя", "value": "Иван Иванов"},
                "2": {"name": "Телефон", "value": "+7 900 000-00-00"},
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
                "1": {"name": "Имя", "value": "Иван"},
                "2": {"name": "Телефон", "value": "+79001112233"},
                "5": {"name": "Предпочтительный канал", "value": "MAX (мессенджер)"},
                "3": {"name": "Согласие", "value": "Да"},
            }
        }
    )
    assert payload is not None
    assert payload.preferred_channel == "max_miniapp"


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
