"""Тесты URL и полей amo для ссылок на дело / MAX."""

from __future__ import annotations

from sfrfr.integrations.amocrm.fields import MAX_DIALOG_URL, SFRFR_CASE_URL, build_lead_custom_fields
from sfrfr.integrations.amocrm.urls import admin_case_url, max_dialog_url


def test_admin_case_url(monkeypatch) -> None:
    monkeypatch.setenv("ADMIN_PUBLIC_URL", "https://admin.example")
    from sfrfr.core.config import get_settings

    get_settings.cache_clear()
    assert admin_case_url("abc") == "https://admin.example/?case=abc"
    get_settings.cache_clear()


def test_max_dialog_url_strips_startapp(monkeypatch) -> None:
    monkeypatch.setenv("MAX_CHAT_URL", "https://max.ru/bot?startapp")
    from sfrfr.core.config import get_settings

    get_settings.cache_clear()
    assert max_dialog_url() == "https://max.ru/bot"
    get_settings.cache_clear()


def test_build_lead_custom_fields_urls() -> None:
    fields = build_lead_custom_fields(
        case_id="c1",
        case_url="https://admin.example/?case=c1",
        max_dialog_url="https://max.ru/bot",
        max_user_id="48799013",
        pipeline_status="intake",
    )
    by_code = {f["field_code"]: f for f in fields}
    assert by_code[SFRFR_CASE_URL]["values"][0]["value"].startswith("https://")
    assert by_code[MAX_DIALOG_URL]["values"][0]["value"] == "https://max.ru/bot"
    assert by_code["MAX_USER_ID"]["values"][0]["value"] == "48799013"
