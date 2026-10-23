"""SFRFR-93: выборка кандидатов fiscal reconcile и фильтры окна/алерта.

Чистая логика без HTTP к ЮKassa — job/CLI вызывают ensure отдельно.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

# Канон дизайна rev11/rev12
RECONCILE_WINDOW_HOURS = 48
RECONCILE_GRACE_MINUTES = 2
PRE_ERROR_STREAK_ALERT = 12
MAX_RECONCILE_ATTEMPTS = 3


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
    """Предфильтр: fiscal_status IS DISTINCT FROM 'registered' (NULL тоже кандидат)."""
    status = row.get("fiscal_status")
    if status is None:
        return True
    return str(status).strip().lower() != "registered"


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
