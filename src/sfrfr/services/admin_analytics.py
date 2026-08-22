"""Обезличенная операционная аналитика для кабинета сотрудника (ТЗ-17)."""

from __future__ import annotations

import csv
import io
import json
import statistics
from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import Any

from sfrfr.services.staff_work_queue import (
    build_work_item,
    is_closed,
    is_test_case,
    parse_dt,
)

FORBIDDEN_EXPORT_KEYS = frozenset(
    {
        "full_name",
        "phone",
        "email",
        "snils",
        "address",
        "storage_path",
        "body",
        "ocr_text",
        "ocr_texts",
        "analysis_notes",
        "draft",
    }
)

CHANNEL_LABELS: dict[str, str] = {
    "max_miniapp": "MAX mini-app",
    "web_cabinet": "Личный кабинет сайта",
    "unset": "Канал не определён",
    "phone": "Телефон",
    "email": "E-mail",
    "site": "Сайт",
}

B2C_ORDER = (
    "lead",
    "consent_accepted",
    "diagnostic_paid",
    "contract_accepted",
    "service_paid",
    "package_delivered",
    "awaiting_client_submission",
    "result_pending",
    "result_confirmed",
    "success_fee_due",
    "success_fee_paid",
    "closed",
)

FUNNEL_STAGES: list[tuple[str, str]] = [
    ("lead", "Заявка"),
    ("channel", "Выбран канал связи"),
    ("consent", "Получено согласие на ПДн"),
    ("checklist", "Направлен чек-лист"),
    ("documents", "Получены документы"),
    ("diagnostic", "Диагностика"),
    ("plan", "Сформирован план действий"),
    ("payment", "Счёт / оплата"),
    ("completed", "Завершено"),
]

TOPIC_RULES: list[tuple[str, str]] = [
    ("ils", "Проверка ИЛС"),
    ("стаж", "Неучтённый период работы"),
    ("архив", "Архивная справка"),
    ("расхожд", "Расхождения трудовой и ИЛС"),
    ("север", "Северный стаж"),
    ("льгот", "Льготный стаж"),
    ("сфр", "Ответ / отказ СФР"),
    ("родствен", "Помощь родственнику"),
    ("represent", "Помощь родственнику"),
]


def _b2c_rank(status: str) -> int:
    try:
        return B2C_ORDER.index(status)
    except ValueError:
        return -1


def resolve_period_bounds(
    *,
    period: str,
    date_from: str | None,
    date_to: str | None,
    now: datetime | None = None,
) -> tuple[datetime, datetime]:
    now = now or datetime.now(UTC)
    end = now
    p = (period or "30d").strip().lower()
    if p == "today":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif p == "7d":
        start = now - timedelta(days=7)
    elif p == "30d":
        start = now - timedelta(days=30)
    elif p in {"month", "current_month"}:
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    elif p in {"prev_month", "last_month"}:
        first_this = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end = first_this - timedelta(microseconds=1)
        start = end.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    elif p == "custom" and date_from and date_to:
        start = parse_dt(date_from) or (now - timedelta(days=30))
        end = parse_dt(date_to) or now
        if start > end:
            start, end = end, start
    else:
        start = now - timedelta(days=30)
    return start, end


def _in_period(created_at: str | None, start: datetime, end: datetime) -> bool:
    dt = parse_dt(created_at)
    if not dt:
        return False
    return start <= dt <= end


def case_to_analytics_row(case: dict[str, Any]) -> dict[str, Any]:
    client = case.get("clients") or {}
    orders = case.get("orders") or []
    codes = {str(o.get("package_code")) for o in orders}
    paid = {str(o.get("package_code")) for o in orders if o.get("status") == "paid"}
    pending_statuses = {"pending", "awaiting_payment"}
    pending = {
        str(o.get("package_code"))
        for o in orders
        if o.get("status") in pending_statuses
    }
    evidence_list = case.get("result_evidence") or []
    evidence = evidence_list[0] if evidence_list else {}
    before = float((evidence or {}).get("monthly_before_rub") or 0)
    after = float((evidence or {}).get("monthly_after_rub") or 0)
    preferred = client.get("preferred_channel") or "unset"
    max_linked = bool(client.get("max_user_id"))
    web_linked = bool(client.get("user_id"))
    b2c = str(case.get("b2c_status") or "lead")
    pipeline = str(case.get("pipeline_status") or "intake")
    docs = case.get("documents") or []
    checklist = case.get("checklist_items") or []
    consents = case.get("consents") or []
    created = parse_dt(case.get("created_at"))
    first_contact = parse_dt(case.get("first_contact_at"))
    response_hours: float | None = None
    if created and first_contact and first_contact >= created:
        response_hours = round((first_contact - created).total_seconds() / 3600, 2)

    channel_conflict = (preferred == "max_miniapp" and not max_linked) or (
        preferred == "web_cabinet" and not web_linked
    )

    return {
        "case_id": str(case.get("id")),
        "segment": case.get("segment"),
        "region_bucket": case.get("region_bucket"),
        "stage": b2c,
        "pipeline": pipeline,
        "problem_type": case.get("problem_type"),
        "created_at": case.get("created_at"),
        "first_contact_at": case.get("first_contact_at"),
        "response_hours": response_hours,
        "paid_diag": "DIAG" in paid,
        "paid_service": "ACCOMP" in paid,
        "pending_order": bool(pending),
        "result_confirmed": b2c
        in {"result_confirmed", "success_fee_due", "success_fee_paid", "closed"}
        or (after > before and bool(evidence)),
        "result_band": "confirmed_change"
        if after > before and evidence
        else ("flat" if evidence else "unknown"),
        "sf_due": bool({"SF_LUMP", "SF_MONTH"} & codes),
        "sf_paid": bool({"SF_LUMP", "SF_MONTH"} & paid),
        "preferred_channel": preferred,
        "max_linked": max_linked,
        "web_linked": web_linked,
        "channel_conflict": channel_conflict,
        "has_consent": bool(consents) or _b2c_rank(b2c) >= _b2c_rank("consent_accepted"),
        "has_checklist": bool(checklist),
        "has_documents": bool(docs) or pipeline in {
            "documents_received",
            "ocr_done",
            "classified",
            "extracted",
            "audited",
            "draft_ready",
            "human_review",
            "completed",
        },
        "has_expert": bool(case.get("expert_user_id")),
        "is_new": b2c == "lead" or pipeline == "intake",
        "is_in_progress": not is_closed(case),
        "is_completed": pipeline == "completed" or b2c == "closed",
    }


def classify_topic(problem_type: str | None) -> str:
    raw = (problem_type or "").strip().lower()
    if not raw:
        return "Другая тема"
    for needle, label in TOPIC_RULES:
        if needle in raw:
            return label
    return "Другая тема"


def _funnel_count(rows: list[dict[str, Any]], key: str) -> int:
    checks = {
        "lead": lambda r: True,
        "channel": lambda r: r["preferred_channel"] != "unset",
        "consent": lambda r: r["has_consent"],
        "checklist": lambda r: r["has_checklist"],
        "documents": lambda r: r["has_documents"],
        "diagnostic": lambda r: r["paid_diag"]
        or _b2c_rank(r["stage"]) >= _b2c_rank("diagnostic_paid"),
        "plan": lambda r: r["pipeline"] in {"draft_ready", "human_review", "completed", "audited"},
        "payment": lambda r: r["paid_diag"]
        or r["paid_service"]
        or r["pending_order"]
        or r["sf_due"]
        or r["sf_paid"],
        "completed": lambda r: r["is_completed"],
    }
    fn = checks.get(key, lambda _r: False)
    return sum(1 for r in rows if fn(r))


def _pct(part: int, whole: int) -> int | None:
    if whole <= 0:
        return None
    return round(part * 100 / whole)


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    return round(float(statistics.median(values)), 2)


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return round(float(statistics.mean(values)), 2)


def build_admin_analytics(
    *,
    cases: list[dict[str, Any]],
    orders: list[dict[str, Any]],
    period: str = "30d",
    date_from: str | None = None,
    date_to: str | None = None,
    channel: str | None = None,
    package_code: str | None = None,
    pipeline_status: str | None = None,
    include_finance: bool = False,
    now: datetime | None = None,
) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    start, end = resolve_period_bounds(
        period=period, date_from=date_from, date_to=date_to, now=now
    )

    source_cases = [c for c in cases if not is_test_case(c)]
    all_rows = [case_to_analytics_row(c) for c in source_cases]
    rows = [r for r in all_rows if _in_period(r.get("created_at"), start, end)]

    if channel:
        rows = [r for r in rows if r["preferred_channel"] == channel]
    if pipeline_status:
        rows = [r for r in rows if r["pipeline"] == pipeline_status]
    if package_code:
        case_ids_with_pkg = {
            str(o.get("case_id"))
            for o in orders
            if str(o.get("package_code")) == package_code
        }
        rows = [r for r in rows if r["case_id"] in case_ids_with_pkg]

    work_items = [
        item
        for case in source_cases
        if (item := build_work_item(case, now=now, show_contact=False))
        and _in_period(case.get("created_at"), start, end)
    ]
    if channel:
        work_items = [i for i in work_items if i.get("channel") == channel]

    response_hours = [
        float(r["response_hours"]) for r in rows if r.get("response_hours") is not None
    ]
    overdue = sum(1 for i in work_items if i.get("deadline_status") == "overdue")
    waiting_staff = sum(1 for i in work_items if i.get("waiting_on") == "staff")
    waiting_client = sum(1 for i in work_items if i.get("waiting_on") in {"client", "archive"})
    no_next = sum(
        1
        for i in work_items
        if not i.get("next_action_at") and i.get("waiting_on") == "staff"
    )
    no_expert = sum(1 for r in rows if not r["has_expert"] and r["is_in_progress"])
    no_channel = sum(1 for r in rows if r["preferred_channel"] == "unset")
    no_consent = sum(1 for r in rows if not r["has_consent"] and r["is_in_progress"])
    channel_conflicts = sum(1 for r in rows if r["channel_conflict"])

    total = len(rows)
    funnel_raw: list[dict[str, Any]] = []
    prev_count = total
    for key, label in FUNNEL_STAGES:
        count = _funnel_count(rows, key)
        conv = _pct(count, prev_count) if key != "lead" else 100
        funnel_raw.append(
            {
                "key": key,
                "label": label,
                "count": count,
                "conversion_from_previous_pct": conv,
                "registry_filter": _registry_filter_for_funnel(key),
            }
        )
        prev_count = max(count, 1)

    by_channel: dict[str, int] = dict(Counter(r["preferred_channel"] for r in rows))
    channel_rows: list[dict[str, Any]] = []
    for ch, count in sorted(by_channel.items(), key=lambda x: (-x[1], x[0])):
        ch_rows = [r for r in rows if r["preferred_channel"] == ch]
        ch_items = [i for i in work_items if i.get("channel") == ch]
        ch_resp = [
            float(r["response_hours"])
            for r in ch_rows
            if r.get("response_hours") is not None
        ]
        channel_rows.append(
            {
                "channel": ch,
                "label": CHANNEL_LABELS.get(ch, ch),
                "count": count,
                "share_pct": _pct(count, total),
                "with_expert": sum(1 for r in ch_rows if r["has_expert"]),
                "conflicts": sum(1 for r in ch_rows if r["channel_conflict"]),
                "avg_response_hours": _mean(ch_resp),
                "overdue_sla": sum(1 for i in ch_items if i.get("deadline_status") == "overdue"),
                "registry_filter": {"preferred_channel": ch},
                "alert": ch == "unset" and count > 0,
            }
        )

    topics = Counter(classify_topic(r.get("problem_type")) for r in rows)
    topic_rows = [
        {"topic": name, "count": cnt, "share_pct": _pct(cnt, total)}
        for name, cnt in topics.most_common()
    ]

    risks = [
        {
            "key": "no_consent",
            "label": "Нет согласия на ПДн",
            "count": no_consent,
            "registry_filter": {"queue": "noconsent"},
        },
        {
            "key": "no_channel",
            "label": "Канал не определён",
            "count": no_channel,
            "registry_filter": {"preferred_channel": "unset"},
        },
        {
            "key": "no_next_action",
            "label": "Нет следующего действия",
            "count": no_next,
            "registry_filter": {"queue": "reply"},
        },
        {
            "key": "no_expert",
            "label": "Нет назначенного ответственного",
            "count": no_expert,
            "registry_filter": {"queue": "active"},
        },
        {
            "key": "sla_overdue",
            "label": "Просрочено SLA",
            "count": overdue,
            "registry_filter": {"queue": "overdue"},
        },
        {
            "key": "waiting_docs",
            "label": "Ждём документы",
            "count": waiting_client,
            "registry_filter": {"queue": "docs"},
        },
        {
            "key": "channel_conflicts",
            "label": "Конфликт / дублирование каналов",
            "count": channel_conflicts,
            "registry_filter": {"queue": "conflicts"},
        },
    ]

    finance: dict[str, Any] | None = None
    if include_finance:
        scoped_orders = [
            o
            for o in orders
            if str(o.get("case_id")) in {r["case_id"] for r in rows}
        ]
        paid_diag = sum(1 for r in rows if r["paid_diag"])
        paid_service = sum(1 for r in rows if r["paid_service"])
        pending_orders = [
            o
            for o in scoped_orders
            if o.get("status") in {"pending", "awaiting_payment"}
        ]
        paid_orders = [o for o in scoped_orders if o.get("status") == "paid"]
        diag_paid_cases = {r["case_id"] for r in rows if r["paid_diag"]}
        service_after_diag = sum(
            1 for r in rows if r["paid_service"] and r["case_id"] in diag_paid_cases
        )
        finance = {
            "paid_diagnostics": paid_diag,
            "paid_accompaniment": paid_service,
            "pending_invoices": len(pending_orders),
            "pending_amount_rub": round(
                sum(float(o.get("amount_rub") or 0) for o in pending_orders), 2
            ),
            "paid_orders_count": len(paid_orders),
            "paid_amount_rub": round(
                sum(float(o.get("amount_rub") or 0) for o in paid_orders), 2
            ),
            "avg_check_rub": round(
                sum(float(o.get("amount_rub") or 0) for o in paid_orders) / len(paid_orders),
                2,
            )
            if paid_orders
            else None,
            "diag_to_service_conversion_pct": _pct(service_after_diag, paid_diag),
        }

    kpi = {
        "total_cases": total,
        "new_cases": sum(1 for r in rows if r["is_new"]),
        "in_progress": sum(1 for r in rows if r["is_in_progress"]),
        "paid_diagnostics": sum(1 for r in rows if r["paid_diag"]),
        "paid_accompaniment": sum(1 for r in rows if r["paid_service"]),
        "confirmed_result_changes": sum(1 for r in rows if r["result_confirmed"]),
        "avg_first_response_hours": _mean(response_hours),
        "median_first_response_hours": _median(response_hours),
        "sla_overdue": overdue,
        "no_next_action": no_next,
        "no_channel": no_channel,
        "no_expert": no_expert,
        "waiting_on_staff": waiting_staff,
    }

    return {
        "period": {
            "key": period,
            "from": start.isoformat(),
            "to": end.isoformat(),
        },
        "filters_applied": {
            "channel": channel,
            "package_code": package_code,
            "pipeline_status": pipeline_status,
        },
        "note": (
            "Обезличенные агрегированные данные: без ФИО, контактов, "
            "СНИЛС, файлов, текста документов и сообщений."
        ),
        "kpi": kpi,
        "funnel": funnel_raw,
        "channels": channel_rows,
        "topics": topic_rows,
        "risks": [r for r in risks if r.get("count")],
        "finance": finance,
        "export_row_count": len(rows),
        "suppress_small_groups": total < 5,
    }


def _registry_filter_for_funnel(key: str) -> dict[str, str]:
    mapping = {
        "lead": {"queue": "new"},
        "channel": {"queue": "active"},
        "consent": {"queue": "noconsent"},
        "documents": {"queue": "docs"},
        "payment": {"queue": "payment"},
        "completed": {"pipeline_status": "completed"},
    }
    return mapping.get(key, {})


def filtered_analytics_rows(
    *,
    cases: list[dict[str, Any]],
    orders: list[dict[str, Any]],
    period: str = "30d",
    date_from: str | None = None,
    date_to: str | None = None,
    channel: str | None = None,
    package_code: str | None = None,
    pipeline_status: str | None = None,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    now = now or datetime.now(UTC)
    start, end = resolve_period_bounds(
        period=period, date_from=date_from, date_to=date_to, now=now
    )
    rows = [
        case_to_analytics_row(c)
        for c in cases
        if not is_test_case(c) and _in_period(c.get("created_at"), start, end)
    ]
    if channel:
        rows = [r for r in rows if r["preferred_channel"] == channel]
    if pipeline_status:
        rows = [r for r in rows if r["pipeline"] == pipeline_status]
    if package_code:
        case_ids = {
            str(o.get("case_id"))
            for o in orders
            if str(o.get("package_code")) == package_code
        }
        rows = [r for r in rows if r["case_id"] in case_ids]
    assert_no_forbidden_fields(rows)
    return rows


def analytics_export_rows(
    cases: list[dict[str, Any]],
    orders: list[dict[str, Any]],
    **filters: Any,
) -> list[dict[str, Any]]:
    return filtered_analytics_rows(cases=cases, orders=orders, **filters)


def assert_no_forbidden_fields(rows: list[dict[str, Any]]) -> None:
    for row in rows:
        for key in row:
            if key in FORBIDDEN_EXPORT_KEYS:
                raise ValueError(f"forbidden analytics field: {key}")


def rows_to_csv(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return ""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue()


def rows_to_json(rows: list[dict[str, Any]]) -> str:
    assert_no_forbidden_fields(rows)
    return json.dumps(rows, ensure_ascii=False, indent=2)
