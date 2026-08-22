"""Рабочая очередь кабинета сотрудника: приоритет, SLA, следующий шаг."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

_TEST_NAME = re.compile(r"тест|test|amo token|e2e|recheck", re.IGNORECASE)

WAITING_ON = ("staff", "client", "archive", "sfr", "payment", "none")
CLOSED_PIPELINE = {"completed", "failed"}
CLOSED_B2C = {"closed"}
EXTERNAL_WAIT = {"client", "archive", "sfr"}

Priority = Literal["urgent", "today", "standard"]
DeadlineStatus = Literal["overdue", "soon", "today", "ok", "waiting"]


def parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        try:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def human_age(delta: timedelta) -> str:
    seconds = max(0, int(delta.total_seconds()))
    if seconds < 60:
        return "только что"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} мин"
    hours = minutes // 60
    if hours < 48:
        return f"{hours} ч"
    return f"{hours // 24} дн."


def is_test_case(case: dict[str, Any]) -> bool:
    if case.get("is_test") is True:
        return True
    name = str((case.get("clients") or {}).get("full_name") or "")
    return bool(_TEST_NAME.search(name))


def is_closed(case: dict[str, Any]) -> bool:
    pipeline = str(case.get("pipeline_status") or "")
    b2c = str(case.get("b2c_status") or "")
    return pipeline in CLOSED_PIPELINE or b2c in CLOSED_B2C


def _open_items(case: dict[str, Any]) -> list[dict[str, Any]]:
    items = case.get("checklist_items") or []
    return [i for i in items if i.get("status") not in ("done", "cancelled")]


def _title_blob(case: dict[str, Any]) -> str:
    parts = [str(i.get("title") or "") for i in _open_items(case)]
    parts.append(str(case.get("next_action") or ""))
    return " ".join(parts).lower()


def derive_waiting_on(case: dict[str, Any]) -> str:
    stored = str(case.get("waiting_on") or "").strip()
    if stored in WAITING_ON and stored != "none":
        return stored
    if is_closed(case):
        return "none"
    b2c = str(case.get("b2c_status") or "")
    pipeline = str(case.get("pipeline_status") or "")
    if b2c == "client_silent_escalation":
        return "client"
    if b2c in {"awaiting_client_submission"}:
        return "client"
    if b2c in {"result_pending"}:
        return "sfr"
    if b2c in {"success_fee_due"}:
        return "payment"
    orders = case.get("orders") or []
    if any(o.get("status") == "pending" for o in orders):
        return "payment"
    blob = _title_blob(case)
    if "архив" in blob:
        return "archive"
    docs = [
        i
        for i in _open_items(case)
        if i.get("item_type") == "document" and i.get("owner") == "client"
    ]
    if docs or "илс" in blob or "трудов" in blob or "согласи" in blob:
        if pipeline in {"intake", "documents_received"} or b2c == "lead":
            return "client"
    if pipeline in {"draft_ready", "human_review", "audited"}:
        return "staff"
    if pipeline == "intake" or b2c == "lead":
        return "staff"
    return "staff"


def derive_next_action(case: dict[str, Any], waiting_on: str) -> str:
    stored = str(case.get("next_action") or "").strip()
    if stored:
        return stored
    open_items = _open_items(case)
    open_items.sort(key=lambda item: (item.get("sort_order") or 0, item.get("title") or ""))
    staff_owned = [i for i in open_items if i.get("owner") == "expert" and i.get("title")]
    if staff_owned:
        return str(staff_owned[0]["title"])
    client_owned = [i for i in open_items if i.get("owner") == "client" and i.get("title")]
    if client_owned:
        return str(client_owned[0]["title"])
    pipeline = str(case.get("pipeline_status") or "")
    if waiting_on == "payment":
        return "Проверить оплату"
    if waiting_on == "archive":
        return "Напомнить об архивной справке"
    if waiting_on == "sfr":
        return "Дождаться ответа СФР"
    if waiting_on == "client":
        return "Запросить документы или напомнить клиенту"
    if pipeline in {"draft_ready", "human_review"}:
        return "Проверить проект обращения"
    if pipeline in {"audited", "extracted"}:
        return "Разобрать расхождения"
    if pipeline == "documents_received":
        return "Проверить документы"
    return "Связаться с клиентом"


def derive_next_action_at(
    case: dict[str, Any],
    waiting_on: str,
    *,
    now: datetime,
) -> datetime | None:
    stored = parse_dt(case.get("next_action_at"))
    if stored:
        return stored
    due_dates = [parse_dt(i.get("due_at")) for i in _open_items(case)]
    due = [d for d in due_dates if d]
    if due:
        return min(due)
    if waiting_on == "staff" and (
        str(case.get("pipeline_status") or "") == "intake"
        or str(case.get("b2c_status") or "") == "lead"
    ):
        created = parse_dt(case.get("first_contact_at")) or parse_dt(case.get("created_at"))
        if created:
            return created + timedelta(hours=1)
    return None


def last_event(case: dict[str, Any], waiting_on: str, *, now: datetime) -> str:
    created = parse_dt(case.get("first_contact_at")) or parse_dt(case.get("created_at"))
    age = human_age(now - created) if created else ""
    pipeline = str(case.get("pipeline_status") or "")
    if pipeline == "intake" or str(case.get("b2c_status") or "") == "lead":
        return f"Новое обращение{f' {age} назад' if age else ''}"
    if waiting_on == "client":
        return "Ожидаем документы или ответ клиента"
    if waiting_on == "archive":
        return "Ожидаем архивную справку"
    if waiting_on == "sfr":
        return "Ожидаем ответ СФР"
    if waiting_on == "payment":
        return "Отправлен счёт, ждём оплату"
    if pipeline in {"draft_ready", "human_review"}:
        return "Проект обращения готов к проверке"
    if pipeline == "audited":
        return "Есть расхождения по документам"
    return "Дело в работе"


def deadline_status(
    waiting_on: str,
    next_at: datetime | None,
    *,
    now: datetime,
) -> DeadlineStatus:
    if waiting_on in EXTERNAL_WAIT:
        return "waiting"
    if waiting_on == "payment":
        if next_at and next_at < now:
            return "overdue"
        return "waiting"
    if not next_at:
        return "ok"
    if next_at < now:
        return "overdue"
    if next_at <= now + timedelta(hours=1):
        return "soon"
    if next_at.date() == now.date():
        return "today"
    return "ok"


def priority_for(
    waiting_on: str,
    next_at: datetime | None,
    status: DeadlineStatus,
    *,
    now: datetime,
    created: datetime | None,
) -> Priority:
    if waiting_on == "staff" and status == "overdue":
        return "urgent"
    if waiting_on == "staff" and created and (now - created) >= timedelta(minutes=30):
        if status in {"overdue", "soon"}:
            return "urgent"
    if waiting_on == "staff" and created and (now - created) >= timedelta(hours=1):
        if str(status) != "waiting":
            return "urgent"
    if next_at and next_at.date() == now.date():
        return "today"
    if status == "soon":
        return "today"
    return "standard"


def doc_flags(case: dict[str, Any], waiting_on: str) -> dict[str, bool]:
    blob = _title_blob(case)
    pipeline = str(case.get("pipeline_status") or "")
    b2c = str(case.get("b2c_status") or "")
    return {
        "consent_missing": b2c == "lead",
        "ils_missing": "илс" in blob or "выписк" in blob,
        "labor_missing": "трудов" in blob,
        "archive_needed": waiting_on == "archive" or "архив" in blob,
        "discrepancy": pipeline == "audited" or "расхожд" in blob or "не учт" in blob,
        "extra_info": waiting_on == "client" and "илс" not in blob and "трудов" not in blob,
        "project_ready": pipeline in {"draft_ready", "human_review"},
        "sfr_reply": b2c in {"result_pending", "result_confirmed"},
    }


def build_work_item(
    case: dict[str, Any],
    *,
    now: datetime | None = None,
    show_contact: bool = True,
) -> dict[str, Any] | None:
    if is_closed(case):
        return None
    now = now or datetime.now(UTC)
    waiting_on = derive_waiting_on(case)
    next_action = derive_next_action(case, waiting_on)
    next_at = derive_next_action_at(case, waiting_on, now=now)
    created = parse_dt(case.get("first_contact_at")) or parse_dt(case.get("created_at"))
    status = deadline_status(waiting_on, next_at, now=now)
    client = case.get("clients") or {}
    return {
        "case_id": str(case.get("id") or ""),
        "client_name": client.get("full_name") if show_contact else None,
        "priority": priority_for(waiting_on, next_at, status, now=now, created=created),
        "pipeline_status": str(case.get("pipeline_status") or ""),
        "b2c_status": str(case.get("b2c_status") or ""),
        "waiting_on": waiting_on,
        "last_event": last_event(case, waiting_on, now=now),
        "next_action": next_action,
        "next_action_at": next_at.isoformat() if next_at else None,
        "deadline_status": status,
        "channel": client.get("preferred_channel") or "unset",
        "expert_user_id": str(case["expert_user_id"]) if case.get("expert_user_id") else None,
        "created_at": case.get("created_at"),
        "doc_flags": doc_flags(case, waiting_on),
        "waiting_days": max(0, (now - created).days) if created else 0,
    }


def _sort_key(item: dict[str, Any]) -> tuple[int, int, str]:
    prio = {"urgent": 0, "today": 1, "standard": 2}.get(str(item.get("priority")), 9)
    dead = {"overdue": 0, "soon": 1, "today": 2, "ok": 3, "waiting": 4}.get(
        str(item.get("deadline_status")), 9
    )
    return (prio, dead, str(item.get("next_action_at") or "9999"))


def build_dashboard_snapshot(
    cases: list[dict[str, Any]],
    orders: list[dict[str, Any]],
    *,
    now: datetime | None = None,
    show_contact: bool = True,
) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    items = [
        item
        for case in cases
        if not is_test_case(case)
        and (item := build_work_item(case, now=now, show_contact=show_contact))
    ]
    items.sort(key=_sort_key)

    needs_reply = [i for i in items if i["waiting_on"] == "staff"]
    overdue_staff = [i for i in needs_reply if i["deadline_status"] == "overdue"]
    due_1h = [i for i in needs_reply if i["deadline_status"] == "soon"]
    due_today = [
        i
        for i in items
        if i["next_action_at"]
        and parse_dt(i["next_action_at"])
        and parse_dt(i["next_action_at"]).date() == now.date()  # type: ignore[union-attr]
    ]
    waiting_docs = [i for i in items if i["waiting_on"] in {"client", "archive"}]
    waiting_external = [i for i in items if i["waiting_on"] in EXTERNAL_WAIT]
    paused = [
        i
        for i in items
        if i["b2c_status"] == "client_silent_escalation"
    ]
    over_30m = []
    for item in needs_reply:
        created = parse_dt(item.get("created_at"))
        intake_like = item["pipeline_status"] == "intake" or item["b2c_status"] == "lead"
        if created and (now - created) >= timedelta(minutes=30) and (
            item["deadline_status"] in {"overdue", "soon"} or intake_like
        ):
            over_30m.append(item)

    pending_orders = [o for o in orders if o.get("status") == "pending"]
    paid_today = [
        o
        for o in orders
        if o.get("status") == "paid"
        and (paid_at := parse_dt(o.get("paid_at") or o.get("updated_at") or o.get("created_at")))
        and paid_at.date() == now.date()
    ]
    pending_amount = sum(float(o.get("amount_rub") or 0) for o in pending_orders)
    paid_today_amount = sum(float(o.get("amount_rub") or 0) for o in paid_today)

    doc_status = {
        "consent_missing": 0,
        "ils_missing": 0,
        "labor_missing": 0,
        "archive_needed": 0,
        "discrepancy": 0,
        "extra_info": 0,
        "project_ready": 0,
        "sfr_reply": 0,
    }
    for item in items:
        flags = item.get("doc_flags") or {}
        for key in doc_status:
            if flags.get(key):
                doc_status[key] += 1

    wait_days = [i["waiting_days"] for i in waiting_docs]
    by_pipeline: dict[str, int] = {}
    by_b2c: dict[str, int] = {}
    for case in cases:
        if is_test_case(case):
            continue
        by_pipeline[str(case.get("pipeline_status"))] = by_pipeline.get(
            str(case.get("pipeline_status")), 0
        ) + 1
        by_b2c[str(case.get("b2c_status"))] = by_b2c.get(str(case.get("b2c_status")), 0) + 1

    new_leads = by_b2c.get("lead", 0)
    my_tasks = [i for i in items if i["priority"] in {"urgent", "today"}][:8]

    return {
        "new_leads": new_leads,
        "by_pipeline": by_pipeline,
        "by_b2c": by_b2c,
        "needs_reply": len(needs_reply),
        "needs_reply_over_30m": len(over_30m),
        "deadline_today": len(due_today),
        "waiting_docs": len(waiting_docs),
        "waiting_docs_max_days": max(wait_days) if wait_days else 0,
        "sla_risk": len(overdue_staff),
        "greeting_priority_count": len(my_tasks),
        "payments_pending": len(pending_orders),
        "payments_paid": sum(1 for o in orders if o.get("status") == "paid"),
        "payments_pending_amount": round(pending_amount, 2),
        "payments_paid_today": len(paid_today),
        "payments_paid_today_amount": round(paid_today_amount, 2),
        "sla_control": {
            "overdue": len(overdue_staff),
            "due_1h": len(due_1h),
            "due_today": len([i for i in due_today if i["waiting_on"] == "staff"]),
            "waiting_external": len(waiting_external),
            "paused": len(paused),
        },
        "doc_status": doc_status,
        "work_queue": items[:80],
        "my_tasks_today": my_tasks,
        "silent": {
            "30": 0,
            "90": 0,
            "150": 0,
            "180": 0,
        },
    }
