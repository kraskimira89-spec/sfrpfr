"""Тесты URL и полей amo для ссылок на дело / MAX."""

from __future__ import annotations

from sfrfr.integrations.amocrm.fields import MAX_REPLY_HINT, SFRFR_CASE_URL, build_lead_custom_fields
from sfrfr.integrations.amocrm.urls import admin_case_url, max_operator_reply_hint


def test_admin_case_url(monkeypatch) -> None:
    monkeypatch.setenv("ADMIN_PUBLIC_URL", "https://admin.example")
    from sfrfr.core.config import get_settings

    get_settings.cache_clear()
    assert admin_case_url("abc") == "https://admin.example/?case=abc"
    get_settings.cache_clear()


def test_max_operator_reply_hint_includes_user_id() -> None:
    hint = max_operator_reply_hint("48799013")
    assert hint
    assert "48799013" in hint
    assert "admin" in hint


def test_build_lead_custom_fields_urls_and_hint() -> None:
    fields = build_lead_custom_fields(
        case_id="c1",
        case_url="https://admin.example/?case=c1",
        max_reply_hint="Ответ через admin",
        max_user_id="48799013",
        pipeline_status="intake",
    )
    by_code = {f["field_code"]: f for f in fields}
    assert by_code[SFRFR_CASE_URL]["values"][0]["value"].startswith("https://")
    assert by_code[MAX_REPLY_HINT]["values"][0]["value"] == "Ответ через admin"
    assert by_code["MAX_USER_ID"]["values"][0]["value"] == "48799013"
