"""Канон причин отказа и колонок канбана продаж (кабинет staff, без amo).

ТЗ-33: колонки воронки 3/5/8 — см. funnel_board.compute_funnel_column.
"""

from __future__ import annotations

from typing import Any

from sfrfr.services.funnel_board import (
    FUNNEL_BOARD_COLUMNS,
    compute_funnel_column,
)

# Совпадает с sfrfr.integrations.amocrm.fields.LOSS_REASON_VALUES (резерв amo).
LOSS_REASON_VALUES: tuple[str, ...] = (
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

# Колонки канбана реестра (= FUNNEL_BOARD_COLUMNS, ТЗ-33).
SALES_BOARD_COLUMNS: tuple[tuple[str, str], ...] = FUNNEL_BOARD_COLUMNS


def sales_board_column(
    *,
    pipeline_status: str | None,
    b2c_status: str | None,
    waiting_on: str | None = None,
    finance_attention: str | None = None,
    loss_reason: str | None = None,
    orders: list[dict[str, Any]] | None = None,
    diagnosis_delivered: bool | None = None,
    docs_package_ready: bool | None = None,
    case: dict[str, Any] | None = None,
) -> str:
    """Ключ колонки канбана для дела (делегирует в compute_funnel_column)."""
    row = dict(case or {})
    if pipeline_status is not None:
        row["pipeline_status"] = pipeline_status
    if b2c_status is not None:
        row["b2c_status"] = b2c_status
    if loss_reason is not None:
        row["loss_reason"] = loss_reason
    if waiting_on is not None:
        row["waiting_on"] = waiting_on
    return compute_funnel_column(
        row,
        orders,
        diagnosis_delivered=diagnosis_delivered,
        docs_package_ready=docs_package_ready,
        waiting_on=waiting_on,
        finance_attention=finance_attention,
    )
