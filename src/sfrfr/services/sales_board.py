"""Канон причин отказа и колонок канбана продаж (кабинет staff, без amo)."""

from __future__ import annotations

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

# Колонки канбана реестра (упрощённая воронка продаж).
SALES_BOARD_COLUMNS: tuple[tuple[str, str], ...] = (
    ("new", "Новый лид"),
    ("in_touch", "В работе"),
    ("docs", "Документы"),
    ("payment", "Оплата"),
    ("delivery", "Выдача / СФР"),
    ("closed", "Закрыто"),
    ("lost", "Отказ"),
)


def sales_board_column(
    *,
    pipeline_status: str | None,
    b2c_status: str | None,
    waiting_on: str | None = None,
    finance_attention: str | None = None,
    loss_reason: str | None = None,
) -> str:
    """Ключ колонки канбана для дела."""
    p = (pipeline_status or "").strip().lower()
    b = (b2c_status or "").strip().lower()
    w = (waiting_on or "").strip().lower()
    fin = (finance_attention or "").strip().lower()
    loss = (loss_reason or "").strip()

    if b == "closed" or p in {"completed", "failed"}:
        return "lost" if loss else "closed"
    if fin in {"payable", "awaiting_invoice"} or w == "payment" or b == "success_fee_due":
        return "payment"
    if w in {"client", "archive"} or p == "documents_received":
        return "docs"
    if b in {"awaiting_client_submission", "result_pending"} or p in {
        "draft_ready",
        "human_review",
        "audited",
    }:
        return "delivery"
    if p == "intake" or b in {"lead", ""}:
        return "new"
    return "in_touch"
