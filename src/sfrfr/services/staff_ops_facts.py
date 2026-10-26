"""Обезличенные факты дела для staff-LLM: сверка документов и оплаты.

Без ФИО, телефонов, работодателей из сырых файлов — только то, что уже
лежит в честном резюме / статусах счетов.
"""

from __future__ import annotations

from typing import Any

_PAID = frozenset({"paid", "succeeded"})
_PENDING = frozenset(
    {"pending", "pending_payment", "waiting_for_capture", "invoice_sent", "new", "created"}
)


def _pkg(order: dict[str, Any]) -> str:
    return str(order.get("package_code") or "").strip().upper()


def _status(order: dict[str, Any]) -> str:
    return str(order.get("status") or order.get("finance_status") or "").strip().lower()


def ops_facts_from_check_and_orders(
    *,
    check: dict[str, Any] | None,
    orders: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    """Собрать факты для подсказок «что ответить» и «что делать дальше»."""
    orders = [o for o in (orders or []) if isinstance(o, dict)]
    diag_paid = any(_pkg(o) == "DIAG" and _status(o) in _PAID for o in orders)
    diag_pending = any(_pkg(o) == "DIAG" and _status(o) in _PENDING for o in orders)
    support_pending = any(
        _pkg(o) in {"SUPPORT", "ACCOMP"} and _status(o) in _PENDING for o in orders
    )
    support_paid = any(_pkg(o) in {"SUPPORT", "ACCOMP"} and _status(o) in _PAID for o in orders)

    if not check:
        return {
            "check_status": "none",
            "discrepancies": [],
            "compare_summary": "",
            "diag_paid": diag_paid,
            "diag_pending": diag_pending,
            "support_or_accomp_pending": support_pending,
            "support_or_accomp_paid": support_paid,
            "staff_next": "run_document_check",
            "unique_documents": 0,
        }

    status = str(check.get("status") or "").strip().lower() or "unknown"
    raw_result = check.get("result")
    result: dict[str, Any] = raw_result if isinstance(raw_result, dict) else {}
    raw_brief = result.get("honest_brief")
    brief: dict[str, Any] = raw_brief if isinstance(raw_brief, dict) else {}
    raw_compare = result.get("stazh_compare")
    compare: dict[str, Any] = raw_compare if isinstance(raw_compare, dict) else {}
    if not compare:
        raw_brief_cmp = brief.get("compare")
        if isinstance(raw_brief_cmp, dict):
            compare = raw_brief_cmp

    discrepancies: list[str] = []
    for item in brief.get("items") or []:
        if not isinstance(item, dict) or str(item.get("evidence") or "") != "docs":
            continue
        title = str(item.get("text") or "").strip()
        basis = str(item.get("basis") or "").strip()
        line = title if not basis else f"{title} — {basis}"
        if line and line not in discrepancies:
            discrepancies.append(line[:280])
        if len(discrepancies) >= 3:
            break

    summary = str(compare.get("summary") or "").strip()
    if status in {"completed", "succeeded", "done", "needs_action"} and discrepancies:
        if diag_paid:
            staff_next = "prepare_analysis"
        elif diag_pending:
            staff_next = "wait_diag_payment"
        else:
            staff_next = "offer_or_wait_diag"
    elif status in {"completed", "succeeded", "done"} and compare.get("ran"):
        staff_next = "tell_client_clear" if not discrepancies else "prepare_analysis"
    elif status in {"queued", "running"}:
        staff_next = "wait_document_check"
    else:
        staff_next = "run_document_check"

    return {
        "check_status": status,
        "discrepancies": discrepancies,
        "compare_summary": summary[:240],
        "diag_paid": diag_paid,
        "diag_pending": diag_pending,
        "support_or_accomp_pending": support_pending,
        "support_or_accomp_paid": support_paid,
        "staff_next": staff_next,
        "unique_documents": int(result.get("unique_documents") or 0),
    }


def format_ops_facts_for_llm(facts: dict[str, Any] | None) -> str:
    """Текст блока «операционные факты» в user-промпт (без ПДн)."""
    if not facts:
        return "Операционные факты: нет данных проверки документов."
    lines = [
        f"Статус проверки документов: {facts.get('check_status') or '—'}",
        f"Уникальных файлов: {facts.get('unique_documents') or 0}",
        f"Рекомендуемый шаг сотрудника: {facts.get('staff_next') or '—'}",
    ]
    if facts.get("compare_summary"):
        lines.append(f"Итог сверки ИЛС↔трудовая: {facts['compare_summary']}")
    discs = facts.get("discrepancies") or []
    if discs:
        lines.append("Расхождения по документам:")
        for i, d in enumerate(discs, start=1):
            lines.append(f"  {i}. {d}")
    else:
        lines.append("Расхождений по документам: нет (или сверка ещё не дала пунктов).")
    if facts.get("diag_paid"):
        lines.append(
            "DIAG оплачен — не предлагай снова оплату DIAG; "
            "говори про разбор периодов / письменный результат."
        )
    elif facts.get("diag_pending"):
        lines.append(
            "Счёт DIAG уже выставлен — можно мягко напомнить про оплату, без нового счёта."
        )
    if facts.get("support_or_accomp_paid"):
        lines.append("Подготовка/сопровождение уже оплачены — не проси эту оплату снова.")
    elif facts.get("support_or_accomp_pending"):
        lines.append(
            "Ссылка на оплату подготовки/сопровождения уже могла уходить в чат — "
            "не дублируй просьбу об оплате, если клиент только подтвердил («хорошо»)."
        )
    return "\n".join(lines)


def load_staff_ops_facts(
    case_id: str, *, orders: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    """Загрузить факты по делу для staff LLM."""
    from sfrfr.services.staff_document_check import get_case_document_check

    check = None
    try:
        check = get_case_document_check(case_id)
    except Exception:  # noqa: BLE001
        check = None
    order_rows = list(orders or [])
    if not order_rows:
        try:
            from sfrfr.db.case_repository import CaseRepository

            order_rows = list(CaseRepository().list_orders(case_id) or [])
        except Exception:  # noqa: BLE001
            order_rows = []
    return ops_facts_from_check_and_orders(check=check, orders=order_rows)
