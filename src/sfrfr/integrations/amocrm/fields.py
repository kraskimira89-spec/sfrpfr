"""Коды custom fields сделки amoCRM (ТЗ-12)."""

from __future__ import annotations

from typing import Any

# Стабильные field_code — заполнение через API без хардкода field_id.
CASE_ID = "CASE_ID"
SFRFR_CASE_URL = "SFRFR_CASE_URL"
PIPELINE_STATUS = "PIPELINE_STATUS"
CHANNEL = "CHANNEL"
SOURCE = "SOURCE"
CONSENT = "CONSENT"

LEAD_FIELD_SPECS: tuple[dict[str, Any], ...] = (
    {"code": CASE_ID, "name": "Case ID (SFRFR)", "type": "text"},
    {"code": SFRFR_CASE_URL, "name": "Ссылка на дело SFRFR", "type": "url"},
    {"code": PIPELINE_STATUS, "name": "Pipeline status", "type": "text"},
    {"code": CHANNEL, "name": "Канал клиента", "type": "text"},
    {"code": SOURCE, "name": "Источник лида", "type": "text"},
    {"code": CONSENT, "name": "Согласие на связь", "type": "checkbox"},
)


def cf_text(code: str, value: str) -> dict[str, Any]:
    return {"field_code": code, "values": [{"value": value}]}


def cf_checkbox(code: str, value: bool) -> dict[str, Any]:
    return {"field_code": code, "values": [{"value": bool(value)}]}


def build_lead_custom_fields(
    *,
    case_id: str,
    case_url: str | None = None,
    pipeline_status: str | None = None,
    channel: str | None = None,
    source: str | None = None,
    consent: bool | None = None,
) -> list[dict[str, Any]]:
    """Собрать custom_fields_values для сделки (без ПДн-сканов)."""
    out: list[dict[str, Any]] = [cf_text(CASE_ID, case_id)]
    if case_url:
        out.append(cf_text(SFRFR_CASE_URL, case_url))
    if pipeline_status:
        out.append(cf_text(PIPELINE_STATUS, pipeline_status))
    if channel:
        out.append(cf_text(CHANNEL, channel))
    if source:
        out.append(cf_text(SOURCE, source))
    if consent is not None:
        out.append(cf_checkbox(CONSENT, consent))
    return out
