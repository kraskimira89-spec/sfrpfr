"""Оценка и заказ переноса трудовой книжки в Word."""

from __future__ import annotations

from typing import Any

from sfrfr.services.public_tariffs import public_tariff

LABOR_RATE_PER_SPREAD_RUB = 100
MIN_READABLE_SPREADS = 1


def count_labor_spreads(documents: list[Any] | None) -> int:
    """Подсчитать развороты по загруженным файлам трудовой (оценка)."""
    count = 0
    for doc in documents or []:
        if not isinstance(doc, dict):
            continue
        dtype = str(doc.get("doc_type") or "").lower()
        if dtype not in {"workbook", "labor"}:
            continue
        pages = doc.get("page_count")
        if isinstance(pages, int) and pages > 0:
            count += max(1, (pages + 1) // 2)
        else:
            count += 1
    return max(count, MIN_READABLE_SPREADS) if count else 0


def estimate_transcription(documents: list[Any] | None) -> dict[str, Any]:
    spreads = count_labor_spreads(documents)
    if spreads <= 0:
        return {
            "status": "no_labor_scans",
            "pages_count": 0,
            "rate_per_spread_rub": LABOR_RATE_PER_SPREAD_RUB,
            "preliminary_total_rub": 0,
            "message": (
                "Сначала загрузите читаемые сканы трудовой книжки. "
                "Мы оценим количество разворотов после осмотра."
            ),
        }
    total = spreads * LABOR_RATE_PER_SPREAD_RUB
    tariff = public_tariff("LABOR_WORD") or {}
    return {
        "status": "estimate_ready",
        "pages_count": spreads,
        "rate_per_spread_rub": LABOR_RATE_PER_SPREAD_RUB,
        "preliminary_total_rub": total,
        "message": (
            f"Загружено разворотов (оценка): {spreads}. "
            f"Предварительная стоимость: {total} ₽. "
            f"{tariff.get('includes', '')}"
        ),
    }
