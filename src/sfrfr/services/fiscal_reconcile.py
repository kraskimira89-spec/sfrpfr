"""SFRFR-93: выборка кандидатов fiscal reconcile и фильтры окна/алерта.

Чистая логика без HTTP к ЮKassa — job/CLI вызывают ensure отдельно.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

# Канон дизайна rev12
RECONCILE_WINDOW_HOURS = 48
RECONCILE_GRACE_MINUTES = 2
PRE_ERROR_STREAK_ALERT = 12
MAX_RECONCILE_ATTEMPTS = 3
LEASE_SECS = 120
UNKNOWN_HTTP_STATUSES = frozenset({408, 429, 500, 502, 503, 504})

# Явный select без reconcile_post_payload (PII email/phone) — для list_*.
# Payload подтягивается отдельным select при повторе TTL.
RECONCILE_PAYMENT_COLUMNS = (
    "id, order_id, status, provider, provider_payment_id, fiscal_status, "
    "paid_at, created_at, reconcile_attempts, reconcile_pre_error_streak, "
    "last_reconcile_at, reconcile_post_at, reconcile_last_outcome, "
    "reconcile_alerted_at, orders(id, case_id)"
)

# Терминальные статусы вне reconcile-выборки (чек есть / чек не требуется).
FISCAL_TERMINAL_STATUSES = frozenset({"registered", "not_required"})
# PostgREST: NULL + не terminal (neq.registered AND neq.not_required).
FISCAL_STATUS_OR = (
    "fiscal_status.is.null,"
    "and(fiscal_status.neq.registered,fiscal_status.neq.not_required)"
)

# Окно/алерт в list_* могут брать now() процесса (±секунды OK).
# Lease, TTL Idempotence-Key и cutover — только now() БД (SQL/RPC), не Python.


def to_iso_z(dt: datetime) -> str:
    return _as_utc(dt).isoformat().replace("+00:00", "Z")


def reconcile_window_or_filter(
    *,
    now: datetime,
    window_hours: int = RECONCILE_WINDOW_HOURS,
    grace_minutes: int = RECONCILE_GRACE_MINUTES,
) -> str:
    """PostgREST or_: paid_at в окне ИЛИ (paid_at null и created_at в окне)."""
    now_u = _as_utc(now)
    oldest = to_iso_z(now_u - timedelta(hours=window_hours))
    newest = to_iso_z(now_u - timedelta(minutes=grace_minutes))
    return (
        f"and(paid_at.gte.{oldest},paid_at.lte.{newest}),"
        f"and(paid_at.is.null,created_at.gte.{oldest},created_at.lte.{newest})"
    )


def stale_alert_or_filter(
    *,
    now: datetime,
    alert_since: datetime,
    window_hours: int = RECONCILE_WINDOW_HOURS,
) -> str:
    """Старше 48ч и не раньше ALERT_SINCE (paid_at или created_at)."""
    now_u = _as_utc(now)
    since_u = _as_utc(alert_since)
    cutoff = to_iso_z(now_u - timedelta(hours=window_hours))
    since = to_iso_z(since_u)
    return (
        f"and(paid_at.lt.{cutoff},paid_at.gte.{since}),"
        f"and(paid_at.is.null,created_at.lt.{cutoff},created_at.gte.{since})"
    )


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _parse_ts(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return _as_utc(value)
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return _as_utc(datetime.fromisoformat(text))
    except ValueError:
        return None


def payment_effective_paid_at(row: dict[str, Any]) -> datetime | None:
    """coalesce(paid_at, created_at) — единое правило для окна и алерта 48ч."""
    return _parse_ts(row.get("paid_at")) or _parse_ts(row.get("created_at"))


def fiscal_status_needs_reconcile(row: dict[str, Any]) -> bool:
    """Предфильтр: NULL/pending и пр. в выборке; registered/not_required — нет."""
    status = row.get("fiscal_status")
    if status is None:
        return True
    return str(status).strip().lower() not in FISCAL_TERMINAL_STATUSES


def payment_in_reconcile_window(
    row: dict[str, Any],
    *,
    now: datetime,
    window_hours: int = RECONCILE_WINDOW_HOURS,
    grace_minutes: int = RECONCILE_GRACE_MINUTES,
) -> bool:
    """paid в [now - window, now - grace]."""
    paid = payment_effective_paid_at(row)
    if paid is None:
        return False
    now_u = _as_utc(now)
    oldest = now_u - timedelta(hours=window_hours)
    newest = now_u - timedelta(minutes=grace_minutes)
    return oldest <= paid <= newest


def payment_needs_stale_alert(
    row: dict[str, Any],
    *,
    now: datetime,
    alert_since: datetime,
    window_hours: int = RECONCILE_WINDOW_HOURS,
) -> bool:
    """48ч без registered + cutover ALERT_SINCE + alerted_at IS NULL."""
    if row.get("reconcile_alerted_at") is not None:
        return False
    if not fiscal_status_needs_reconcile(row):
        return False
    if str(row.get("status") or "").lower() != "succeeded":
        return False
    if not str(row.get("provider_payment_id") or "").strip():
        return False
    paid = payment_effective_paid_at(row)
    if paid is None:
        return False
    now_u = _as_utc(now)
    since_u = _as_utc(alert_since)
    if paid < since_u:
        return False
    return paid < now_u - timedelta(hours=window_hours)


def filter_reconcile_candidates(
    rows: list[dict[str, Any]],
    *,
    now: datetime,
    window_hours: int = RECONCILE_WINDOW_HOURS,
    grace_minutes: int = RECONCILE_GRACE_MINUTES,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        if str(row.get("status") or "").lower() != "succeeded":
            continue
        if not str(row.get("provider_payment_id") or "").strip():
            continue
        if not fiscal_status_needs_reconcile(row):
            continue
        if not payment_in_reconcile_window(
            row, now=now, window_hours=window_hours, grace_minutes=grace_minutes
        ):
            continue
        out.append(row)
    return out


def filter_stale_alert_candidates(
    rows: list[dict[str, Any]],
    *,
    now: datetime,
    alert_since: datetime,
    window_hours: int = RECONCILE_WINDOW_HOURS,
) -> list[dict[str, Any]]:
    return [
        row
        for row in rows
        if payment_needs_stale_alert(
            row, now=now, alert_since=alert_since, window_hours=window_hours
        )
    ]


def reconcile_idempotence_key(yk_payment_id: str, attempt: int) -> str:
    key = f"reconcile:{yk_payment_id}:{attempt}"
    return key


def stable_receipt_snapshot(payload: dict[str, Any]) -> dict[str, Any]:
    """Канон: sort_keys + separators; amount.value — строка (не float)."""
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    out = json.loads(text)
    return out if isinstance(out, dict) else dict(payload)


def classify_create_receipt_result(result: dict[str, Any]) -> str:
    """Исход после create_receipt → reconcile_last_outcome."""
    phase = str(result.get("phase") or "")
    if phase == "pre_post":
        return "error_before_post"
    if phase == "transport":
        return "unknown_after_post"
    if result.get("ok"):
        status = str(result.get("status") or "").strip().lower()
        if status == "succeeded":
            return "succeeded"
        if status == "pending":
            return "pending"
        if status in {"canceled", "cancelled"}:
            return "canceled"
        return "pending"
    code = result.get("status_code")
    try:
        code_i = int(code) if code is not None else -1
    except (TypeError, ValueError):
        code_i = -1
    if code_i in UNKNOWN_HTTP_STATUSES:
        return "unknown_after_post"
    if 400 <= code_i < 500:
        return "rejected"
    if code_i >= 500:
        return "unknown_after_post"
    return "unknown_after_post"


def is_unknown_outcome(outcome: str | None) -> bool:
    return str(outcome or "") in {"unknown_after_post", "post_started"}


def attempts_block_new_post(
    *,
    attempts: int,
    outcome: str | None,
    ttl_alive: bool,
    bypass_limit: bool = False,
) -> bool:
    """attempts>=3 блокирует новый +1, кроме CLI bypass и ветки same-key."""
    if bypass_limit:
        return False
    if attempts < MAX_RECONCILE_ATTEMPTS:
        return False
    if is_unknown_outcome(outcome) and ttl_alive:
        return False  # повтор того же ключа ещё возможен
    return True


def should_alert_attempts(
    *,
    attempts: int,
    outcome: str | None,
    ttl_alive: bool,
) -> bool:
    if attempts < MAX_RECONCILE_ATTEMPTS:
        return False
    if is_unknown_outcome(outcome) and ttl_alive:
        return False
    return True


def should_alert_streak(streak: int) -> bool:
    return streak >= PRE_ERROR_STREAK_ALERT
