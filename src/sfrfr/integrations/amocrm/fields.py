"""Коды custom fields сделки amoCRM (ТЗ-12 + marketing-sales foundation §9)."""

from __future__ import annotations

from typing import Any

# Стабильные field_code — заполнение через API без хардкода field_id.
CASE_ID = "CASE_ID"
SFRFR_CASE_URL = "SFRFR_CASE_URL"
PIPELINE_STATUS = "PIPELINE_STATUS"
CHANNEL = "CHANNEL"
SOURCE = "SOURCE"
CONSENT = "CONSENT"
FIRST_SOURCE = "FIRST_SOURCE"
LAST_SOURCE = "LAST_SOURCE"
UTM_MEDIUM = "UTM_MEDIUM"
UTM_CAMPAIGN = "UTM_CAMPAIGN"
UTM_CONTENT = "UTM_CONTENT"
UTM_TERM = "UTM_TERM"
LANDING_VARIANT = "LANDING_VARIANT"
AUDIENCE_SEGMENT = "AUDIENCE_SEGMENT"
REGION_BUCKET = "REGION_BUCKET"
REFERRAL_CODE = "REFERRAL_CODE"
PROBLEM_TYPE = "PROBLEM_TYPE"
LOSS_REASON = "LOSS_REASON"
# Черновик: код не пишет значения до юр. модели / оплаты в sync — скрыты в UI (is_api_only)
DIAGNOSTIC_PAID_AT = "DIAGNOSTIC_PAID_AT"
SERVICE_PAID_AT = "SERVICE_PAID_AT"
RESULT_CONFIRMED_AT = "RESULT_CONFIRMED_AT"
SUCCESS_FEE_DUE_AT = "SUCCESS_FEE_DUE_AT"
SUCCESS_FEE_PAID_AT = "SUCCESS_FEE_PAID_AT"

LOSS_REASON_VALUES = (
    "нецелевой вопрос",
    "нет связи",
    "не готов передавать документы",
    "цена",
    "хочет гарантию результата",
    "нет необходимых исходных документов",
    "выбрал самостоятельный путь",
    "выбрал другого исполнителя",
    "неудобен канал",
    "другое",
)

# is_api_only=True — поле не показывается оператору в карточке (только API).
LEAD_FIELD_SPECS: tuple[dict[str, Any], ...] = (
    {"code": CASE_ID, "name": "ID дела (SFRFR)", "type": "text"},
    {"code": SFRFR_CASE_URL, "name": "Ссылка на дело SFRFR", "type": "url"},
    {"code": PIPELINE_STATUS, "name": "Статус пайплайна SFRFR", "type": "text"},
    {"code": CHANNEL, "name": "Канал клиента", "type": "text"},
    {"code": SOURCE, "name": "Источник лида", "type": "text"},
    {"code": CONSENT, "name": "Согласие на связь", "type": "checkbox"},
    {"code": FIRST_SOURCE, "name": "Первый источник", "type": "text"},
    {"code": LAST_SOURCE, "name": "Последний источник", "type": "text"},
    # Системные tracking_data amo: имя зафиксировано (utm_*), в UI уже is_api_only
    {
        "code": UTM_MEDIUM,
        "name": "utm_medium",
        "type": "text",
        "skip_label_sync": True,
        "is_api_only": True,
    },
    {
        "code": UTM_CAMPAIGN,
        "name": "utm_campaign",
        "type": "text",
        "skip_label_sync": True,
        "is_api_only": True,
    },
    {
        "code": UTM_CONTENT,
        "name": "utm_content",
        "type": "text",
        "skip_label_sync": True,
        "is_api_only": True,
    },
    {
        "code": UTM_TERM,
        "name": "utm_term",
        "type": "text",
        "skip_label_sync": True,
        "is_api_only": True,
    },
    {"code": LANDING_VARIANT, "name": "Вариант лендинга", "type": "text"},
    {"code": AUDIENCE_SEGMENT, "name": "Сегмент аудитории", "type": "text"},
    {"code": REGION_BUCKET, "name": "Регион (корзина)", "type": "text"},
    {"code": REFERRAL_CODE, "name": "Реферальный код", "type": "text"},
    {"code": PROBLEM_TYPE, "name": "Тип проблемы", "type": "text"},
    {"code": LOSS_REASON, "name": "Причина потери", "type": "text"},
    {
        "code": DIAGNOSTIC_PAID_AT,
        "name": "Дата оплаты диагностики (черновик)",
        "type": "text",
        "is_api_only": True,
    },
    {
        "code": SERVICE_PAID_AT,
        "name": "Дата оплаты услуги (черновик)",
        "type": "text",
        "is_api_only": True,
    },
    {
        "code": RESULT_CONFIRMED_AT,
        "name": "Дата подтверждения результата (черновик)",
        "type": "text",
        "is_api_only": True,
    },
    {
        "code": SUCCESS_FEE_DUE_AT,
        "name": "Вознаграждение за результат: к оплате (черновик)",
        "type": "text",
        "is_api_only": True,
    },
    {
        "code": SUCCESS_FEE_PAID_AT,
        "name": "Вознаграждение за результат: оплачено (черновик)",
        "type": "text",
        "is_api_only": True,
    },
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
    first_source: str | None = None,
    last_source: str | None = None,
    utm_medium: str | None = None,
    utm_campaign: str | None = None,
    utm_content: str | None = None,
    utm_term: str | None = None,
    landing_variant: str | None = None,
    audience_segment: str | None = None,
    region_bucket: str | None = None,
    referral_code: str | None = None,
    problem_type: str | None = None,
    loss_reason: str | None = None,
) -> list[dict[str, Any]]:
    """Собрать custom_fields_values для сделки (без ПДн-сканов)."""
    out: list[dict[str, Any]] = [cf_text(CASE_ID, case_id)]
    pairs = (
        (SFRFR_CASE_URL, case_url),
        (PIPELINE_STATUS, pipeline_status),
        (CHANNEL, channel),
        (SOURCE, source),
        (FIRST_SOURCE, first_source),
        (LAST_SOURCE, last_source),
        (UTM_MEDIUM, utm_medium),
        (UTM_CAMPAIGN, utm_campaign),
        (UTM_CONTENT, utm_content),
        (UTM_TERM, utm_term),
        (LANDING_VARIANT, landing_variant),
        (AUDIENCE_SEGMENT, audience_segment),
        (REGION_BUCKET, region_bucket),
        (REFERRAL_CODE, referral_code),
        (PROBLEM_TYPE, problem_type),
        (LOSS_REASON, loss_reason),
    )
    for code, value in pairs:
        if value:
            out.append(cf_text(code, str(value)[:500]))
    if consent is not None:
        out.append(cf_checkbox(CONSENT, consent))
    return out
