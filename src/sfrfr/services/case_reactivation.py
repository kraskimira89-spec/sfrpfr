"""Реанимация зависших CRM-дел и orphan MAX (playbook-case-reactivation).

По умолчанию тик классифицирует и пишет аудит; MAX-отправка — при
CASE_REACTIVATION_AUTO_SEND=1 или --send, только сервисные касания A/B/C/O
в дневном окне и через contact_policy.
"""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from sfrfr.services.contact_policy import can_contact, is_quiet_hours
from sfrfr.services.staff_work_queue import is_test_case

logger = logging.getLogger(__name__)

Basket = Literal["A", "B", "C", "D", "E", "F", "O", "S"]

TOUCH1_AFTER_DAYS = 6
TOUCH2_AFTER_DAYS = 7
MAX_SILENT_FOR_AUTO = 45  # старше — только ручной E, не автотик
AUTO_SEND_BASKETS = frozenset({"A", "B", "C", "O"})
CLOSED_STATUSES = frozenset({"closed", "lost", "completed", "archived"})

MSG_A1 = (
    "Здравствуйте! Подскажите, пожалуйста, на каком шаге вы сейчас: "
    "выписка ИЛС, документы или вопрос по диагностике?\n\n"
    "Если вопрос пока не актуален — достаточно коротко ответить, "
    "и мы не будем беспокоить.\n"
    "Сканы в этот чат отправлять не нужно, пока не договоримся о следующем шаге."
)
MSG_A2 = (
    "Здравствуйте! Напомню про проверку стажа.\n"
    "Если вопрос пока не актуален, отвечать не обязательно — "
    "мы не будем беспокоить дальше.\n\n"
    "Когда вернётесь, напишите в этот же чат: «Нужна проверка» "
    "или «ИЛС получил(а)»."
)
MSG_B1 = (
    "Здравствуйте! Получилось ли заказать выписку ИЛС по чек-листу?\n\n"
    "Если она уже готова, достаточно ответить: «ИЛС получил(а)».\n"
    "Если возникла сложность — напишите, на каком шаге, "
    "и мы подскажем, что делать дальше.\n\n"
    "Напоминаю: сканы и персональные документы в чат отправлять не нужно."
)
MSG_B2 = MSG_A2
MSG_C1 = (
    "Здравствуйте! Напоминаю про диагностику документов — 3 000 ₽:\n"
    "сверка по доступным источникам и понятный план дальше.\n"
    "Решение о пенсии принимает только СФР; мы не обещаем перерасчёт.\n\n"
    "Если удобно продолжить — напишите «Нужна диагностика» "
    "или откройте ссылку на оплату в кабинете.\n"
    "Если пока рано — отвечать не обязательно."
)
MSG_C2 = MSG_A2
MSG_O1 = (
    "Здравствуйте! Ранее вы писали про проверку стажа.\n"
    "Если вопрос снова актуален, ответьте «Нужна проверка» — "
    "подскажем следующий шаг (документы, диагностика). "
    "Сканы сразу не присылайте.\n\n"
    "Мы готовим документы и план; подачу через СФР или Госуслуги делаете вы сами."
)
MSG_O2 = MSG_A2


def auto_send_enabled(*, force_send: bool | None = None) -> bool:
    if force_send is not None:
        return bool(force_send)
    raw = (os.environ.get("CASE_REACTIVATION_AUTO_SEND") or "1").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def basket_for_case(
    case: dict[str, Any],
    *,
    now: datetime,
    silent_days: float,
    open_diag_invoice: bool,
    paid_stalled: bool,
) -> Basket | None:
    """Корзина CRM-дела или None (не трогать автотиком)."""
    if is_test_case(case):
        return None
    if bool(case.get("do_not_contact")):
        return "F"
    status = str(case.get("pipeline_status") or case.get("b2c_status") or "").lower()
    if status in CLOSED_STATUSES or case.get("loss_reason"):
        # LOSS с причиной — не реанимируем автоматом (корзина E вручную)
        if case.get("loss_reason") or status in {"closed", "lost", "completed", "archived"}:
            return None
    waiting = str(case.get("waiting_on") or "").lower()
    if waiting == "archive":
        return None
    if silent_days < 3:
        return None
    if silent_days > MAX_SILENT_FOR_AUTO:
        return None
    if paid_stalled:
        return "D"
    if open_diag_invoice and silent_days >= 5:
        return "C"
    if status in {"docs", "documents"}:
        return "B"
    if status in {"new", "lead", "qualify"} and silent_days >= 2:
        return "S"
    if status in {"in_touch", "payment"} or waiting in {"client", "payment", "none", ""}:
        return "A"
    return "A"


def basket_for_orphan(
    *,
    max_user_id: str,
    open_cases: int,
    do_not_contact: bool,
) -> Basket | None:
    if do_not_contact:
        return "F"
    mid = (max_user_id or "").strip()
    if not mid:
        return None
    if open_cases > 0:
        return None
    return "O"


def touch_number_due(*, touches_sent: int, silent_days: float) -> int | None:
    if touches_sent <= 0 and silent_days >= TOUCH1_AFTER_DAYS:
        return 1
    if touches_sent == 1 and silent_days >= TOUCH1_AFTER_DAYS + TOUCH2_AFTER_DAYS:
        return 2
    return None


def message_for_touch(basket: str, touch_no: int) -> str:
    key = (basket.upper(), int(touch_no))
    table: dict[tuple[str, int], str] = {
        ("A", 1): MSG_A1,
        ("A", 2): MSG_A2,
        ("B", 1): MSG_B1,
        ("B", 2): MSG_B2,
        ("C", 1): MSG_C1,
        ("C", 2): MSG_C2,
        ("O", 1): MSG_O1,
        ("O", 2): MSG_O2,
        ("S", 1): MSG_A1,
        ("S", 2): MSG_A2,
    }
    return table.get(key, MSG_A1)


def should_send_touch(
    *,
    auto_send: bool,
    quiet_hours: bool,
    contact_allowed: bool,
    basket: str,
    touch_no: int,
) -> bool:
    if not auto_send:
        return False
    if quiet_hours:
        return False
    if not contact_allowed:
        return False
    if basket not in AUTO_SEND_BASKETS:
        return False
    if touch_no not in (1, 2):
        return False
    return True


def _parse_dt(raw: Any) -> datetime | None:
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=UTC)
    text = str(raw).strip()
    if not text:
        return None
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _silent_days(case: dict[str, Any], *, now: datetime) -> float:
    candidates: list[datetime] = []
    for key in ("last_client_message_at", "updated_at", "next_action_at", "created_at"):
        dt = _parse_dt(case.get(key))
        if dt:
            candidates.append(dt)
    if not candidates:
        return 0.0
    latest = max(candidates)
    return max(0.0, (now - latest).total_seconds() / 86400.0)


def run_due_tick(
    *,
    cases: list[dict[str, Any]] | None = None,
    orphans: list[dict[str, Any]] | None = None,
    now: datetime | None = None,
    dry_run: bool = False,
    force_send: bool | None = None,
    limit: int = 40,
    send_fn: Any | None = None,
    record_touch_fn: Any | None = None,
) -> dict[str, Any]:
    """Тик реанимации. Без cases/orphans — загрузка из Supabase (прод)."""
    ts = now or datetime.now(UTC)
    auto = auto_send_enabled(force_send=force_send)
    quiet = is_quiet_hours(ts)
    stats: dict[str, Any] = {
        "ts": ts.isoformat(),
        "dry_run": dry_run,
        "auto_send": auto,
        "quiet_hours": quiet,
        "candidates": 0,
        "sent": 0,
        "skipped": 0,
        "staff_tasks": 0,
        "orphan_sent": 0,
        "reasons": {},
        "items": [],
    }

    if cases is None and orphans is None:
        cases, orphans = _load_from_db(limit=max(limit * 3, 80))
    cases = cases or []
    orphans = orphans or []

    planned: list[dict[str, Any]] = []

    for case in cases:
        cid = str(case.get("id") or "").strip()
        if not cid:
            continue
        touches = int(case.get("reactivation_touches") or 0)
        silent = float(case.get("silent_days") or _silent_days(case, now=ts))
        basket = basket_for_case(
            case,
            now=ts,
            silent_days=silent,
            open_diag_invoice=bool(case.get("open_diag_invoice")),
            paid_stalled=bool(case.get("paid_stalled")),
        )
        if basket is None:
            continue
        if basket == "F":
            stats["skipped"] += 1
            _bump(stats["reasons"], "do_not_contact")
            continue
        # Нет чата — только задача staff, без MAX.
        if case.get("no_chat") and basket in AUTO_SEND_BASKETS:
            basket = "S"
        touch_no = touch_number_due(touches_sent=touches, silent_days=silent)
        if basket == "D":
            planned.append(
                {
                    "kind": "case",
                    "case_id": cid,
                    "basket": "D",
                    "touch_no": None,
                    "action": "staff_task",
                    "body": None,
                }
            )
            continue
        if basket == "S" and touch_no is None and silent >= 2:
            planned.append(
                {
                    "kind": "case",
                    "case_id": cid,
                    "basket": "S",
                    "touch_no": None,
                    "action": "staff_task",
                    "body": None,
                }
            )
            continue
        if touch_no is None:
            continue
        body = message_for_touch(basket, touch_no)
        decision = can_contact(
            message_type="service",
            channel="max",
            do_not_contact=bool(case.get("do_not_contact")),
            channel_available=bool(str(case.get("max_user_id") or "").strip()),
            service_messages_last_48h=int(case.get("service_messages_last_48h") or 0),
        )
        send = should_send_touch(
            auto_send=auto,
            quiet_hours=quiet,
            contact_allowed=decision.allowed,
            basket=basket,
            touch_no=touch_no,
        )
        planned.append(
            {
                "kind": "case",
                "case_id": cid,
                "max_user_id": str(case.get("max_user_id") or "").strip() or None,
                "basket": basket,
                "touch_no": touch_no,
                "action": "send" if send else "skip",
                "skip_reason": None
                if send
                else (
                    "dry_or_no_auto"
                    if not auto
                    else ("quiet_hours" if quiet else decision.reason)
                ),
                "body": body,
            }
        )

    for row in orphans:
        mid = str(row.get("max_user_id") or "").strip()
        client_id = str(row.get("client_id") or "").strip() or None
        basket = basket_for_orphan(
            max_user_id=mid,
            open_cases=int(row.get("open_cases") or 0),
            do_not_contact=bool(row.get("do_not_contact")),
        )
        if basket != "O":
            continue
        touches = int(row.get("reactivation_touches") or 0)
        silent = float(row.get("silent_days") or 30)
        touch_no = touch_number_due(touches_sent=touches, silent_days=silent)
        if touch_no is None:
            continue
        body = message_for_touch("O", touch_no)
        decision = can_contact(
            message_type="service",
            channel="max",
            do_not_contact=bool(row.get("do_not_contact")),
            channel_available=True,
            service_messages_last_48h=int(row.get("service_messages_last_48h") or 0),
        )
        send = should_send_touch(
            auto_send=auto,
            quiet_hours=quiet,
            contact_allowed=decision.allowed,
            basket="O",
            touch_no=touch_no,
        )
        planned.append(
            {
                "kind": "orphan",
                "case_id": None,
                "client_id": client_id,
                "max_user_id": mid,
                "basket": "O",
                "touch_no": touch_no,
                "action": "send" if send else "skip",
                "skip_reason": None
                if send
                else (
                    "dry_or_no_auto"
                    if not auto
                    else ("quiet_hours" if quiet else decision.reason)
                ),
                "body": body,
            }
        )

    # приоритет D, C, A/B, S, O
    order = {"D": 0, "C": 1, "A": 2, "B": 2, "S": 3, "O": 4}
    planned.sort(key=lambda x: (order.get(str(x.get("basket")), 9), str(x.get("case_id") or "")))
    planned = planned[:limit]
    stats["candidates"] = len(planned)
    stats["items"] = planned if dry_run else []

    if dry_run:
        stats["skipped"] = sum(1 for p in planned if p.get("action") != "send")
        stats["staff_tasks"] = sum(1 for p in planned if p.get("action") == "staff_task")
        return stats

    for item in planned:
        action = item.get("action")
        if action == "staff_task":
            stats["staff_tasks"] += 1
            _bump(stats["reasons"], "staff_task")
            if record_touch_fn:
                record_touch_fn(item, sent=False, staff_task=True)
            continue
        if action != "send":
            stats["skipped"] += 1
            _bump(stats["reasons"], str(item.get("skip_reason") or "skip"))
            if record_touch_fn:
                record_touch_fn(item, sent=False, staff_task=False)
            continue
        ok = False
        if send_fn is not None:
            ok = bool(send_fn(item))
        else:
            ok = _default_send(item)
        if ok:
            stats["sent"] += 1
            if item.get("kind") == "orphan":
                stats["orphan_sent"] += 1
            if record_touch_fn:
                record_touch_fn(item, sent=True, staff_task=False)
            else:
                _default_record_touch(item, sent=True)
        else:
            stats["skipped"] += 1
            _bump(stats["reasons"], "send_failed")
    return stats


def _bump(reasons: dict[str, int], key: str) -> None:
    reasons[key] = int(reasons.get(key) or 0) + 1


def _load_from_db(*, limit: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Загрузка кандидатов без ПДн в логах."""
    try:
        from sfrfr.db.session import get_supabase_client

        sb = get_supabase_client()
        now = datetime.now(UTC)
        since = (now - timedelta(days=MAX_SILENT_FOR_AUTO)).isoformat()
        rows = (
            sb.table("cases")
            .select(
                "id,client_id,is_test,pipeline_status,b2c_status,waiting_on,"
                "next_action_at,created_at,loss_reason"
            )
            .gte("created_at", since)
            .order("created_at", desc=False)
            .limit(limit)
            .execute()
            .data
            or []
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("reactivation_db_unavailable err=%s", type(exc).__name__)
        return [], []

    client_ids = [str(r.get("client_id") or "") for r in rows if r.get("client_id")]
    max_by_client: dict[str, str] = {}
    if client_ids:
        try:
            clients = (
                sb.table("clients")
                .select("id,max_user_id")
                .in_("id", list({c for c in client_ids if c})[:200])
                .execute()
                .data
                or []
            )
            for c in clients:
                mid = str(c.get("max_user_id") or "").strip()
                if mid:
                    max_by_client[str(c.get("id"))] = mid
        except Exception as exc:  # noqa: BLE001
            logger.debug("reactivation_clients_skipped err=%s", type(exc).__name__)

    touch_counts: dict[str, int] = {}
    try:
        touch_rows = (
            sb.table("case_reactivation_touches")
            .select("case_id,client_id,touch_no,sent_at")
            .execute()
            .data
            or []
        )
        for t in touch_rows:
            if t.get("sent_at"):
                key = str(t.get("case_id") or t.get("client_id") or "")
                if key:
                    touch_counts[key] = max(touch_counts.get(key, 0), int(t.get("touch_no") or 0))
    except Exception:  # noqa: BLE001
        touch_counts = {}

    cases_out: list[dict[str, Any]] = []
    open_by_client: dict[str, int] = {}
    case_ids = [str(r.get("id") or "") for r in rows if r.get("id")]
    last_msg_at: dict[str, datetime] = {}
    if case_ids:
        try:
            # Последняя активность в чате (без тел сообщений).
            msg_rows = (
                sb.table("case_messages")
                .select("case_id,created_at")
                .in_("case_id", case_ids[:200])
                .order("created_at", desc=True)
                .limit(500)
                .execute()
                .data
                or []
            )
            for m in msg_rows:
                cid_m = str(m.get("case_id") or "")
                if not cid_m or cid_m in last_msg_at:
                    continue
                dt = _parse_dt(m.get("created_at"))
                if dt:
                    last_msg_at[cid_m] = dt
        except Exception as exc:  # noqa: BLE001
            logger.debug("reactivation_messages_skipped err=%s", type(exc).__name__)

    for r in rows:
        cid = str(r.get("id") or "")
        client_id = str(r.get("client_id") or "")
        status = str(r.get("pipeline_status") or "").lower()
        if status not in CLOSED_STATUSES and not r.get("loss_reason"):
            if client_id:
                open_by_client[client_id] = open_by_client.get(client_id, 0) + 1
        r2 = dict(r)
        r2["max_user_id"] = max_by_client.get(client_id)
        r2["reactivation_touches"] = touch_counts.get(cid, 0)
        if cid in last_msg_at:
            r2["last_client_message_at"] = last_msg_at[cid].isoformat()
        else:
            # Нет переписки — не авторассылка; только staff (корзина S).
            r2["no_chat"] = True
        r2["silent_days"] = _silent_days(r2, now=now)
        if r2["silent_days"] < 3:
            continue
        r2["open_diag_invoice"] = False
        r2["paid_stalled"] = str(r.get("waiting_on") or "") == "staff" and status in {
            "delivery",
            "payment",
        }
        cases_out.append(r2)

    orphans_out: list[dict[str, Any]] = []
    try:
        all_clients = (
            sb.table("clients")
            .select("id,max_user_id")
            .not_.is_("max_user_id", "null")
            .limit(500)
            .execute()
            .data
            or []
        )
        for c in all_clients:
            mid = str(c.get("max_user_id") or "").strip()
            cid = str(c.get("id") or "")
            if not mid or not cid:
                continue
            if open_by_client.get(cid, 0) > 0:
                continue
            orphans_out.append(
                {
                    "client_id": cid,
                    "max_user_id": mid,
                    "open_cases": 0,
                    "reactivation_touches": touch_counts.get(cid, 0),
                    "silent_days": 30.0,
                    "do_not_contact": False,
                    "service_messages_last_48h": 0,
                }
            )
    except Exception as exc:  # noqa: BLE001
        logger.debug("orphan_scan_skipped err=%s", type(exc).__name__)

    return cases_out, orphans_out[:limit]


def _default_send(item: dict[str, Any]) -> bool:
    mid = str(item.get("max_user_id") or "").strip()
    body = str(item.get("body") or "").strip()
    if not mid or not body:
        return False
    try:
        from sfrfr.integrations.max.client import MaxBotClient

        bot = MaxBotClient()
        if not bot.available:
            return False
        case_id = str(item.get("case_id") or "").strip()
        if case_id:
            try:
                from sfrfr.db.case_messages_write import insert_case_message
                from sfrfr.services.case_chat_delivery import enqueue_max_delivery

                msg = insert_case_message(
                    {
                        "case_id": case_id,
                        "author_kind": "system",
                        "body": body,
                        "channel_origin": "admin",
                    }
                )
                mid_msg = str(msg.get("id") or "").strip()
                if mid_msg:
                    enqueue_max_delivery(
                        case_id=case_id,
                        message_id=mid_msg,
                        max_user_id=mid,
                        body=body,
                    )
                    return True
            except Exception as exc:  # noqa: BLE001
                logger.info("reactivation_outbox_fallback err=%s", type(exc).__name__)
        bot.send_message(text=body, user_id=mid)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("reactivation_send_failed err=%s", type(exc).__name__)
        return False


def _default_record_touch(item: dict[str, Any], *, sent: bool) -> None:
    if not sent:
        return
    try:
        from sfrfr.db.session import get_supabase_client

        sb = get_supabase_client()
        payload = {
            "case_id": item.get("case_id"),
            "client_id": item.get("client_id"),
            "max_user_id": item.get("max_user_id"),
            "basket": item.get("basket"),
            "touch_no": item.get("touch_no"),
            "sent_at": datetime.now(UTC).isoformat(),
            "channel": "max",
        }
        sb.table("case_reactivation_touches").insert(payload).execute()
        case_id = str(item.get("case_id") or "").strip()
        if case_id and item.get("touch_no") == 2:
            sb.table("cases").update({"waiting_on": "archive"}).eq("id", case_id).execute()
    except Exception as exc:  # noqa: BLE001
        logger.debug("reactivation_record_skipped err=%s", type(exc).__name__)
