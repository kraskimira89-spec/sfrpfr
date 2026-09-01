"""Публичные тарифы — единый источник с /tarify/ и price-list.yml.

Не дублировать проценты ЕДВ/прибавки: фиксированные суммы за
информационно-документарную поддержку.
"""

from __future__ import annotations

from typing import Any

PAYMENT_PURPOSE = (
    "Оплата за информационно-документарную поддержку согласно выбранной услуге/договору"
)
FINANCE_DISCLAIMER = (
    "Оплаты за информационно-документарную поддержку. "
    "Решение о назначении и перерасчёте пенсии принимает СФР."
)
TARIFFS_SOURCE_URL = "https://proverkastaza.ru/tarify/"

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
        "name": "Шаг 2. Подготовка документов",
        "amount_rub": 5000,
        "includes": "Сборка комплекта, черновики запросов и пояснений, список чего добрать",
        "status": "active",
    },
    {
        "code": "SUPPORT",
        "package_code": "ACCOMP",
        "name": "Шаг 3. Сопровождение до подачи",
        "amount_rub": 8000,
        "includes": "Проект обращения, пошаговый план подачи через СФР/МФЦ/Госуслуги",
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
    "ACCOMP": 8000,
}

STAFF_PACKAGE_LABELS: dict[str, str] = {
    "DIAG": "Диагностика",
    "ACCOMP": "Подготовка документов / сопровождение",
    "SF_LUMP": "Индивидуальное соглашение",
    "SF_MONTH": "Индивидуальное соглашение",
    "LABOR_WORD": "Перенос трудовой в таблицу Word",
}


def staff_package_label(package_code: str, service_label: str | None = None) -> str:
    if service_label and service_label.strip():
        return service_label.strip()
    return STAFF_PACKAGE_LABELS.get((package_code or "").upper(), package_code or "Услуга")


def public_tariff(code: str) -> dict[str, Any] | None:
    for row in PUBLIC_TARIFFS:
        if row.get("code") == code:
            return row
    return None
