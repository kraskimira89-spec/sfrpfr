"""Публичные тарифы — единый источник с /tarify/ и price-list.yml.

Не дублировать проценты ЕДВ/прибавки: фиксированные суммы за
информационно-документарную поддержку.
"""

from __future__ import annotations

from typing import Any

# Бренд сервиса (оферта / витрина). Юрлицо ООО «ПОД ПРИСМОТРОМ» — в реквизитах,
# не в description платежа. Название магазина в форме ЮKassa задаётся только в ЛК.
BRAND_NAME = "Проверка стажа"
SITE_CANON = "proverkastaza.ru"
PAYMENT_PURPOSE = (
    f"{BRAND_NAME} — информационно-документарная поддержка ({SITE_CANON})"
)
FINANCE_DISCLAIMER = (
    "Оплаты за информационно-документарную поддержку. "
    "Решение о назначении и перерасчёте пенсии принимает СФР. "
    "Оплата счёта означает принятие условий публичной оферты. "
    "Согласие на обработку персональных данных оформляется отдельно."
)
TARIFFS_SOURCE_URL = f"https://{SITE_CANON}/tarify/"

# Совпадает с scripts/assets/trust/tarify.html и yandex-business/price-list.yml
PUBLIC_TARIFFS: list[dict[str, Any]] = [
    {
        "code": "DIAG",
        "package_code": "DIAG",
        "name": "Шаг 1. Диагностика",
        "amount_rub": 3000,
        "includes": "Проверка документов и выписки ИЛС; первичный план; индивидуальный чек-лист",
        "status": "active",
    },
    {
        "code": "DOCS",
        "package_code": "ACCOMP",
        "name": "Шаг 2. Подготовка первичных обращений",
        "amount_rub": 5000,
        "includes": "Черновики первичных обращений в СФР, пояснения, список чего добрать",
        "status": "active",
    },
    {
        "code": "SUPPORT",
        "package_code": "SUPPORT",
        "name": "Шаг 3. Обращения по запросам / отказам / возражениям СФР",
        "amount_rub": 8000,
        "includes": "Подготовка обращений по запросам, отказам или возражениям СФР; план подачи",
        "status": "active",
    },
    {
        "code": "LABOR_WORD",
        "package_code": None,
        "name": "Перенос трудовой в таблицу Word",
        "amount_rub": 100,
        "unit": "за разворот",
        "includes": "Отдельный счёт после осмотра сканов при тяжёлом объёме",
        "status": "by_agreement",
    },
]

DEFAULT_PACKAGE_AMOUNT: dict[str, int] = {
    "DIAG": 3000,
    "ACCOMP": 5000,
    "SUPPORT": 8000,
}

STAFF_PACKAGE_LABELS: dict[str, str] = {
    "DIAG": "Диагностика документов",
    "ACCOMP": "Подготовка первичных обращений",
    "SUPPORT": "Обращения по запросам / отказам / возражениям СФР",
    "SF_LUMP": "Индивидуальное соглашение",
    "SF_MONTH": "Индивидуальное соглашение",
    "LABOR_WORD": "Перенос трудовой в таблицу Word",
}


def staff_package_label(package_code: str, service_label: str | None = None) -> str:
    if service_label and service_label.strip():
        return service_label.strip()
    return STAFF_PACKAGE_LABELS.get((package_code or "").upper(), package_code or "Услуга")


def payment_description(
    package_code: str = "",
    service_label: str | None = None,
) -> str:
    """description / receipt.items для ЮKassa: бренд + услуга (≤128 символов)."""
    code = (package_code or "").strip()
    custom = (service_label or "").strip()
    if custom:
        return f"{BRAND_NAME} — {custom}"[:128]
    if code.upper() in STAFF_PACKAGE_LABELS:
        return f"{BRAND_NAME} — {STAFF_PACKAGE_LABELS[code.upper()]}"[:128]
    return PAYMENT_PURPOSE[:128]


def public_tariff(code: str) -> dict[str, Any] | None:
    for row in PUBLIC_TARIFFS:
        if row.get("code") == code:
            return row
    return None
