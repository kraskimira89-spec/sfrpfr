"""Юнит-тесты payload amoCRM (без сети)."""

from __future__ import annotations

from sfrfr.integrations.amocrm import AmoCrmClient, sync_case_to_amocrm
from sfrfr.integrations.amocrm.fields import CASE_ID, CONSENT, build_lead_custom_fields


def test_build_lead_custom_fields_codes() -> None:
    fields = build_lead_custom_fields(
        case_id="11111111-1111-1111-1111-111111111111",
        case_url="https://admin.proverkastaza.ru/?case=x",
        pipeline_status="intake",
        channel="max_miniapp",
        source="wordpress",
        consent=True,
        first_source="yandex",
        last_source="wordpress",
        utm_medium="cpc",
        utm_campaign="north",
        audience_segment="north_or_preferential",
        problem_type="lead:yandex:north_or_preferential",
    )
    codes = {item["field_code"] for item in fields}
    assert CASE_ID in codes
    assert CONSENT in codes
    assert "SFRFR_CASE_URL" in codes
    assert "FIRST_SOURCE" in codes
    assert "UTM_CAMPAIGN" in codes
    assert "AUDIENCE_SEGMENT" in codes
    consent = next(item for item in fields if item["field_code"] == CONSENT)
    assert consent["values"][0]["value"] is True


def test_lead_field_specs_russian_and_hidden_drafts() -> None:
    from sfrfr.integrations.amocrm.fields import LEAD_FIELD_SPECS

    by_code = {s["code"]: s for s in LEAD_FIELD_SPECS}
    assert by_code["CASE_ID"]["name"] == "ID дела (SFRFR)"
    assert by_code["FIRST_SOURCE"]["name"] == "Первый источник"
    assert by_code["LOSS_REASON"]["name"] == "Причина потери"
    for code in (
        "DIAGNOSTIC_PAID_AT",
        "SERVICE_PAID_AT",
        "RESULT_CONFIRMED_AT",
        "SUCCESS_FEE_DUE_AT",
        "SUCCESS_FEE_PAID_AT",
    ):
        assert by_code[code].get("is_api_only") is True
        assert "черновик" in by_code[code]["name"].lower()
    assert by_code["UTM_MEDIUM"].get("skip_label_sync") is True
    assert by_code["UTM_MEDIUM"]["name"] == "utm_medium"


def test_sync_skipped_without_credentials(monkeypatch) -> None:
    monkeypatch.setenv("AMO_SUBDOMAIN", "")
    monkeypatch.setenv("AMO_ACCESS_TOKEN", "")
    from sfrfr.core.config import get_settings

    get_settings.cache_clear()
    result = sync_case_to_amocrm(
        case_id="c1",
        b2c_status="lead",
        pipeline_status="intake",
    )
    assert result.get("skipped") is True
    assert result.get("ok") is False
    get_settings.cache_clear()


def test_lead_url_template(monkeypatch) -> None:
    monkeypatch.setenv("AMO_SUBDOMAIN", "demo")
    monkeypatch.setenv("AMO_ACCESS_TOKEN", "token")
    monkeypatch.setenv(
        "AMO_CASE_URL_TEMPLATE",
        "https://{subdomain}.amocrm.ru/leads/detail/{id}",
    )
    from sfrfr.core.config import get_settings

    get_settings.cache_clear()
    client = AmoCrmClient()
    assert client.available
    assert client.lead_url(42) == "https://demo.amocrm.ru/leads/detail/42"
    get_settings.cache_clear()
