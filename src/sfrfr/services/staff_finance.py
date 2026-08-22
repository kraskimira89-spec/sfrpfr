"""Очередь счетов сотрудника: статусы, KPI, следующий шаг.

Не считает процент от ЕДВ/пенсии. ЮKassa-статусы pending/paid сохраняем.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sfrfr.services.public_tariffs import (
    FINANCE_DISCLAIMER,
    PAYMENT_PURPOSE,
    PUBLIC_TARIFFS,
    staff_package_label,
)
from sfrfr.services.staff_work_queue import is_test_case

FINANCE_STATUS_LABELS: dict[str, str] = {
    "draft": "Черновик",
    "invoice_ready": "Счёт подготовлен",
    "invoice_sent": "Счёт отправлен",
    "pending_payment": "Ожидает оплату",
    "partially_paid": "Частично оплачено",
    "paid": "Оплачено",
    "overdue": "Просрочено",
    "cancelled": "Отменено",
    "refund": "Возврат",
    "reconciliation_error": "Ошибка сверки",
}

_PENDING_LIKE = {
    "pending",
    "awaiting_payment",
    "invoice_ready",
    "invoice_sent",
    "pending_payment",
}


def parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def invoice_number_from_id(order_id: str) -> str:
    hexpart = str(order_id or "").replace("-", "")[-8:]
    return f"СЧ-{hexpart.upper() or '00000000'}"


def _paid_at(order: dict[str, Any]) -> datetime | None:
    for payment in order.get("payments") or []:
        dt = parse_dt(str(payment.get("paid_at") or ""))
        if dt:
            return dt
    return None


def finance_status(order: dict[str, Any], *, now: datetime | None = None) -> str:
    moment = now or datetime.now(UTC)
    raw = str(order.get("status") or "").lower()
    overlay = str(order.get("invoice_status") or "").lower()
    if raw in {"cancelled", "canceled"} or overlay == "cancelled":
        return "cancelled"
    if raw in {"refund", "refunded"} or overlay == "refund":
        return "refund"
    if overlay == "reconciliation_error":
        return "reconciliation_error"
    if raw == "paid" or overlay == "paid":
        return "paid"
    if overlay == "partially_paid":
        return "partially_paid"
    if raw == "draft" or overlay == "draft":
        return "draft"
    if overlay == "invoice_ready":
        return "invoice_ready"
    due = parse_dt(str(order.get("due_at") or ""))
    if raw in _PENDING_LIKE or overlay in _PENDING_LIKE or overlay == "invoice_sent":
        if due and due < moment:
            return "overdue"
        if overlay == "invoice_sent" or order.get("sent_at") or order.get("pay_url"):
            return "invoice_sent"
        if overlay == "invoice_ready":
            return "invoice_ready"
        return "pending_payment"
    if raw in {"failed", "error"}:
        return "reconciliation_error"
    return overlay or raw or "pending_payment"


def derive_finance_next_action(order: dict[str, Any], status: str) -> str:
    stored = str(order.get("next_action") or "").strip()
    if stored:
        return stored
    code = str(order.get("package_code") or "")
    if status == "draft":
        return "Выставить счёт"
    if status == "invoice_ready":
        return "Отправить ссылку на оплату"
    if status == "overdue":
        return "Напомнить клиенту"
    if status == "invoice_sent" or status == "pending_payment":
        return "Проверить оплату"
    if status == "partially_paid":
        return "Решить вручную: частичная оплата"
    if status == "paid":
        if code == "DIAG":
            return "Передать в диагностику"
        if code == "ACCOMP":
            return "Передать в сопровождение"
        return "Закрыть этап оплаты"
    if status == "cancelled":
        return "Счёт отменён"
    if status == "refund":
        return "Оформить возврат"
    return "Уточнить статус оплаты"


def reminder_draft_text(*, service: str, amount_rub: float, pay_url: str | None) -> str:
    link = f" Ссылка на оплату: {pay_url}." if pay_url else ""
    return (
        "Здравствуйте! Напоминаем об оплате информационно-документарной поддержки "
        f"({service}, {int(amount_rub)} ₽).{link} "
        "Решение о пенсии и перерасчёте принимает СФР, результат не гарантирован."
    )


def serialize_order(
    order: dict[str, Any],
    case: dict[str, Any] | None,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    moment = now or datetime.now(UTC)
    status = finance_status(order, now=moment)
    client = (case or {}).get("clients") or {}
    payments = order.get("payments") or []
    history: list[dict[str, str]] = [
        {
            "at": str(order.get("created_at") or ""),
            "text": "счёт создан",
        }
    ]
    if order.get("sent_at"):
        channel = order.get("sent_channel") or "канал"
        history.append({"at": str(order["sent_at"]), "text": f"ссылка отправлена ({channel})"})
    for payment in payments:
        paid = payment.get("paid_at") or payment.get("status")
        if paid:
            history.append(
                {
                    "at": str(payment.get("paid_at") or ""),
                    "text": f"платёж: {payment.get('status') or 'обновлён'}",
                }
            )
    amount = float(order.get("amount_rub") or 0)
    service = staff_package_label(str(order.get("package_code") or ""), order.get("service_label"))
    qr_url = None
    oid = str(order.get("id") or "")
    if oid and order.get("pay_url"):
        from sfrfr.services.pay_link import public_qr_url

        qr_url = public_qr_url(oid)
    return {
        "id": oid,
        "case_id": str(order.get("case_id") or ""),
        "invoice_number": order.get("invoice_number")
        or invoice_number_from_id(str(order.get("id") or "")),
        "package_code": order.get("package_code"),
        "service_label": service,
        "amount_rub": amount,
        "status": order.get("status"),
        "finance_status": status,
        "due_at": order.get("due_at"),
        "created_at": order.get("created_at"),
        "pay_url": order.get("pay_url"),
        "qr_url": qr_url,
        "sent_channel": order.get("sent_channel"),
        "next_action": derive_finance_next_action(order, status),
        "client_name": client.get("full_name"),
        "expert_user_id": (case or {}).get("expert_user_id"),
        "is_test": is_test_case(case or {}),
        "reminder_draft": order.get("reminder_draft")
        or reminder_draft_text(service=service, amount_rub=amount, pay_url=order.get("pay_url")),
        "max_linked": bool(client.get("max_user_id")),
        "preferred_channel": client.get("preferred_channel") or "unset",
        "cancel_reason": order.get("cancel_reason"),
        "history": history,
        "payment_purpose": PAYMENT_PURPOSE,
    }


def _sum_amount(rows: list[dict[str, Any]]) -> float:
    return round(sum(float(r.get("amount_rub") or 0) for r in rows), 2)


def build_finance_snapshot(
    *,
    orders: list[dict[str, Any]],
    cases: list[dict[str, Any]],
    queue: str | None = None,
    include_test: bool = False,
    period: str | None = None,
    package_code: str | None = None,
    q: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    moment = now or datetime.now(UTC)
    by_case = {str(c.get("id")): c for c in cases}
    items: list[dict[str, Any]] = []
    for order in orders:
        case = by_case.get(str(order.get("case_id")))
        if case is None:
            continue
        if not include_test and is_test_case(case):
            continue
        items.append(serialize_order(order, case, now=moment))

    needle = (q or "").strip().lower()
    if needle:
        items = [
            row
            for row in items
            if needle
            in " ".join(
                [
                    str(row.get("id") or ""),
                    str(row.get("case_id") or ""),
                    str(row.get("invoice_number") or ""),
                    str(row.get("client_name") or ""),
                ]
            ).lower()
        ]
    if package_code:
        items = [row for row in items if row.get("package_code") == package_code]

    start: datetime | None = None
    if period == "today":
        start = moment.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "week":
        start = moment - timedelta(days=7)
    elif period == "month":
        start = moment - timedelta(days=30)
    if start:
        items = [
            row
            for row in items
            if (parse_dt(str(row.get("created_at") or "")) or moment) >= start
        ]

    def pick(status: str) -> list[dict[str, Any]]:
        return [row for row in items if row.get("finance_status") == status]

    payable = [
        row
        for row in items
        if row.get("finance_status") in {"pending_payment", "invoice_sent", "invoice_ready"}
    ]
    overdue = pick("overdue")
    drafts = pick("draft")
    refunds = [row for row in items if row.get("finance_status") in {"refund", "cancelled"}]
    start_today = moment.replace(hour=0, minute=0, second=0, microsecond=0)
    paid_today_rows = []
    for row in items:
        if row.get("finance_status") != "paid":
            continue
        paid_dt = parse_dt(str(row.get("created_at") or ""))
        for order in orders:
            if str(order.get("id")) == row["id"]:
                paid_dt = _paid_at(order) or paid_dt
                break
        if paid_dt and paid_dt >= start_today:
            paid_today_rows.append(row)

    no_order_cases = [
        case
        for case in cases
        if (include_test or not is_test_case(case))
        and str(case.get("b2c_status") or "") not in {"lead", "closed"}
        and str(case.get("id")) not in {str(o.get("case_id")) for o in orders}
    ]

    filtered = items
    if queue == "payable":
        filtered = payable
    elif queue == "overdue":
        filtered = overdue
    elif queue == "paid_today":
        filtered = paid_today_rows
    elif queue in {"awaiting_invoice", "draft"}:
        filtered = drafts
    elif queue in {"refunds", "cancelled"}:
        filtered = refunds
    elif queue and queue != "all":
        filtered = [row for row in items if row.get("finance_status") == queue]

    kpis = {
        "payable": {"count": len(payable), "amount_rub": _sum_amount(payable)},
        "overdue": {"count": len(overdue), "amount_rub": _sum_amount(overdue)},
        "paid_today": {"count": len(paid_today_rows), "amount_rub": _sum_amount(paid_today_rows)},
        "awaiting_invoice": {
            "count": len(drafts) + len(no_order_cases),
            "amount_rub": _sum_amount(drafts),
        },
        "refunds": {"count": len(refunds), "amount_rub": _sum_amount(refunds)},
    }
    return {
        "disclaimer": FINANCE_DISCLAIMER,
        "payment_purpose": PAYMENT_PURPOSE,
        "tariffs": PUBLIC_TARIFFS,
        "tariffs_url": "https://proverkastaza.ru/tarify/",
        "kpis": kpis,
        "orders": filtered,
        "total": len(filtered),
        "needs_invoice_cases": len(no_order_cases),
    }
