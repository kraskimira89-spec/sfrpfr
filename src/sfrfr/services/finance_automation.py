"""Автоматизация счетов: черновик после соглашения, срок, этап после оплаты.

По умолчанию не шлёт MAX и не создаёт платёж ЮKassa — только черновик, задача и next_action.
При MAX_PAY_LINK_AUTO_SEND=1 после черновика: invoice ЮKassa + кнопка/QR в MAX.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sfrfr.services.public_tariffs import public_tariff, staff_package_label
from sfrfr.services.staff_finance import parse_dt, reminder_draft_text
from sfrfr.services.staff_work_queue import is_test_case

_OPEN_ORDER = {"draft", "pending", "awaiting_payment"}
DUE_SOON_HOURS = 24
OVERDUE_REMINDER_MIN_DAYS = 1
OVERDUE_REMINDER_MAX_DAYS = 3
DEFAULT_DUE_DAYS = 3
CHECK_PAYMENT_TITLE = "Проверить оплату"
PARTIAL_TITLE = "Частичная оплата — решить вручную"


def _load_case(repo: Any, case_id: str) -> dict[str, Any] | None:
    getter = getattr(repo, "get_case_row", None) or getattr(repo, "_case", None)
    if getter is None:
        return None
    return getter(case_id)


def _pkg_state(orders: list[dict[str, Any]], code: str) -> str:
    """paid | open | none."""
    rows = [o for o in orders if str(o.get("package_code") or "").upper() == code]
    if any(str(o.get("status") or "") == "paid" for o in rows):
        return "paid"
    if any(str(o.get("status") or "") in _OPEN_ORDER for o in rows):
        return "open"
    if any(str(o.get("invoice_status") or "") in _OPEN_ORDER | {"invoice_sent"} for o in rows):
        return "open"
    return "none"


def suggest_agreement_draft(
    case: dict[str, Any],
    orders: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Какой черновик создать после согласования услуги. Без SF_*."""
    if is_test_case(case):
        return None
    b2c = str(case.get("b2c_status") or "")
    diag = _pkg_state(orders, "DIAG")
    accomp = _pkg_state(orders, "ACCOMP")
    if diag == "none":
        tariff = public_tariff("DIAG") or {}
        return {
            "package_code": "DIAG",
            "amount_rub": float(tariff.get("amount_rub") or 3000),
            "service_label": str(tariff.get("name") or "Диагностика"),
        }
    # После webhook оплаты DIAG b2c уже diagnostic_paid, не contract_accepted.
    if diag == "paid" and accomp == "none" and b2c in {
        "contract_accepted",
        "diagnostic_paid",
    }:
        tariff = public_tariff("DOCS") or {}
        return {
            "package_code": "ACCOMP",
            "amount_rub": float(tariff.get("amount_rub") or 5000),
            "service_label": str(tariff.get("name") or "Подготовка документов"),
        }
    return None


def _due_iso(now: datetime | None = None) -> str:
    moment = now or datetime.now(UTC)
    return (moment + timedelta(days=DEFAULT_DUE_DAYS)).isoformat()


def ensure_agreement_draft_invoice(
    repo: Any,
    case_id: str,
    actor_id: str | None,
    *,
    now: datetime | None = None,
    update_queue: bool = True,
) -> dict[str, Any] | None:
    case = _load_case(repo, case_id)
    if not case:
        return None
    orders = repo.list_orders(case_id)
    draft = suggest_agreement_draft(case, orders)
    if not draft:
        return None
    order = repo.create_order(
        case_id,
        package_code=draft["package_code"],
        amount_rub=draft["amount_rub"],
        status_value="draft",
        actor_id=actor_id,
        due_at=_due_iso(now),
        service_label=draft["service_label"],
        invoice_status="draft",
    )
    from sfrfr.services.pay_link import maybe_auto_send_pay_link_after_draft

    auto = maybe_auto_send_pay_link_after_draft(
        repo=repo,
        order=order,
        case=case,
        actor_id=actor_id,
    )
    next_action = (
        "Проверить оплату"
        if auto and auto.get("sent")
        else "Выставить счёт"
    )
    if update_queue:
        try:
            repo.update_next_action(
                case_id,
                actor_id,
                next_action=next_action,
                waiting_on="payment",
            )
        except Exception:  # noqa: BLE001
            pass
    return order


def on_order_fully_paid(
    repo: Any,
    case_id: str,
    package_code: str,
    *,
    actor_id: str | None = None,
) -> None:
    """После полной оплаты: next_action, этап, черновик следующего счёта."""
    code = (package_code or "").upper()
    if code == "DIAG":
        action = "Провести диагностику"
        pipeline = "documents_received"
    elif code == "ACCOMP":
        action = "Готовить документы и проект обращения"
        pipeline = None
    else:
        action = "Закрыть этап оплаты"
        pipeline = None
    try:
        repo.update_next_action(
            case_id,
            actor_id,
            next_action=action,
            waiting_on="staff",
        )
    except Exception:  # noqa: BLE001
        pass
    if pipeline:
        try:
            case = _load_case(repo, case_id)
            current = str((case or {}).get("pipeline_status") or "")
            if current in {"", "intake", "new"}:
                repo.update_case_status(
                    case_id, pipeline, actor_id, notify=False
                )
        except Exception:  # noqa: BLE001
            pass
    if code == "DIAG":
        try:
            ensure_agreement_draft_invoice(
                repo, case_id, actor_id, update_queue=False
            )
        except Exception:  # noqa: BLE001
            pass


def ensure_staff_task(
    repo: Any,
    case_id: str,
    *,
    title: str,
    item_type: str,
    due_at: str | None,
    actor_id: str | None,
    note: str | None = None,
) -> bool:
    case = _load_case(repo, case_id)
    items = (case or {}).get("checklist_items") or []
    for item in items:
        if item.get("status") in {"done", "cancelled"}:
            continue
        if str(item.get("title") or "") == title:
            return False
    repo.upsert_checklist_item(
        case_id,
        title=title,
        item_type=item_type,
        owner="expert",
        actor_id=actor_id,
        due_at=due_at,
        note=note,
    )
    return True


def _already_audited(repo: Any, order_id: str, action: str) -> bool:
    try:
        rows = repo.list_finance_audit(order_id)
    except Exception:  # noqa: BLE001
        return False
    return any(str(row.get("action") or "") == action for row in rows)


def run_due_tick(repo: Any, *, now: datetime | None = None) -> dict[str, int]:
    """Ежедневная проверка сроков. Не отправляет клиенту сообщения."""
    moment = now or datetime.now(UTC)
    stats = {"due_soon": 0, "overdue_drafts": 0, "skipped": 0, "errors": 0}
    try:
        orders = repo.list_all_orders()
    except Exception:  # noqa: BLE001
        stats["errors"] += 1
        return stats
    for order in orders:
        status = str(order.get("status") or "")
        if status in {"paid", "cancelled", "canceled", "refund", "refunded"}:
            stats["skipped"] += 1
            continue
        case_id = str(order.get("case_id") or "")
        if not case_id:
            stats["skipped"] += 1
            continue
        try:
            case = _load_case(repo, case_id)
        except Exception:  # noqa: BLE001
            stats["errors"] += 1
            continue
        if not case or is_test_case(case):
            stats["skipped"] += 1
            continue
        due = parse_dt(str(order.get("due_at") or ""))
        if not due:
            stats["skipped"] += 1
            continue
        delta = due - moment
        hours = delta.total_seconds() / 3600
        oid = str(order.get("id") or "")
        service = staff_package_label(
            str(order.get("package_code") or ""), order.get("service_label")
        )
        if 0 < hours <= DUE_SOON_HOURS:
            if _already_audited(repo, oid, "due_check_task"):
                stats["skipped"] += 1
                continue
            created = ensure_staff_task(
                repo,
                case_id,
                title=CHECK_PAYMENT_TITLE,
                item_type="payment",
                due_at=str(order.get("due_at")),
                actor_id=None,
                note="Срок оплаты через сутки или меньше.",
            )
            try:
                repo.update_order_fields(
                    oid,
                    case_id=case_id,
                    actor_id=None,
                    action="due_check_task",
                    fields={"next_action": "Проверить оплату"},
                    audit_payload={"hours_left": round(hours, 1)},
                )
            except Exception:  # noqa: BLE001
                pass
            if created:
                stats["due_soon"] += 1
            else:
                stats["skipped"] += 1
            continue
        days_over = -delta.total_seconds() / 86400
        if OVERDUE_REMINDER_MIN_DAYS <= days_over <= OVERDUE_REMINDER_MAX_DAYS:
            if _already_audited(repo, oid, "overdue_reminder_draft"):
                stats["skipped"] += 1
                continue
            draft = reminder_draft_text(
                service=service,
                amount_rub=float(order.get("amount_rub") or 0),
                pay_url=order.get("pay_url"),
            )
            try:
                repo.update_order_fields(
                    oid,
                    case_id=case_id,
                    actor_id=None,
                    action="overdue_reminder_draft",
                    fields={
                        "reminder_draft": draft,
                        "next_action": "Напомнить клиенту",
                        "invoice_status": "overdue",
                    },
                    audit_payload={"days_overdue": round(days_over, 1)},
                )
                stats["overdue_drafts"] += 1
            except Exception:  # noqa: BLE001
                stats["errors"] += 1
            continue
        stats["skipped"] += 1
    return stats
