"""Яндекс Календарь: создание события (CalDAV) — этап C ТЗ-14."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from sfrfr.core.config import get_settings
from sfrfr.integrations.yandex_workspace.oauth import (
    oauth_headers,
    token_available,
    workspace_email,
)

# CalDAV домашний календарь пользователя (стандартный путь Яндекса).
_CALDAV_EVENTS = "https://caldav.yandex.ru/calendars/{email}/events-default/"


def _ics_escape(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
        .replace("\r", "")
    )


def create_event(
    *,
    case_id: str,
    summary: str | None = None,
    starts_at: datetime | None = None,
    duration_minutes: int = 30,
    description: str | None = None,
    telemost_url: str | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    if not settings.yandex_calendar_enabled:
        return {"ok": False, "skipped": True, "reason": "YANDEX_CALENDAR_ENABLED=false"}
    if not token_available():
        return {"ok": False, "skipped": True, "reason": "no YANDEX_OAUTH_ACCESS_TOKEN"}

    email = workspace_email()
    start = starts_at or (datetime.now(UTC) + timedelta(hours=1))
    if start.tzinfo is None:
        start = start.replace(tzinfo=UTC)
    end = start + timedelta(minutes=max(15, duration_minutes))
    uid = f"{uuid.uuid4()}@sfrfr"
    title = (summary or f"Консультация SFRFR {case_id[:8]}").strip()[:200]
    desc_parts = [f"case_id={case_id}"]
    if description:
        desc_parts.append(description[:500])
    if telemost_url:
        desc_parts.append(f"Телемост: {telemost_url}")
    desc = "\n".join(desc_parts)

    def _fmt(dt: datetime) -> str:
        return dt.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")

    ical = (
        "BEGIN:VCALENDAR\r\n"
        "VERSION:2.0\r\n"
        "PRODID:-//SFRFR//Yandex Workspace//RU\r\n"
        "BEGIN:VEVENT\r\n"
        f"UID:{uid}\r\n"
        f"DTSTAMP:{_fmt(datetime.now(UTC))}\r\n"
        f"DTSTART:{_fmt(start)}\r\n"
        f"DTEND:{_fmt(end)}\r\n"
        f"SUMMARY:{_ics_escape(title)}\r\n"
        f"DESCRIPTION:{_ics_escape(desc)}\r\n"
        "END:VEVENT\r\n"
        "END:VCALENDAR\r\n"
    )

    url = _CALDAV_EVENTS.format(email=email)
    event_url = f"{url}{uid}.ics"
    headers = oauth_headers()
    headers["Content-Type"] = "text/calendar; charset=utf-8"

    try:
        with httpx.Client(timeout=25.0) as client:
            response = client.put(event_url, headers=headers, content=ical.encode("utf-8"))
        if response.status_code in (200, 201, 204):
            return {
                "ok": True,
                "status_code": response.status_code,
                "uid": uid,
                "event_url": event_url,
                "starts_at": start.isoformat(),
            }
        return {
            "ok": False,
            "status_code": response.status_code,
            "detail": (response.text or "")[:300],
            "hint": "Нужны scopes календаря; CalDAV может требовать Яндекс 360",
        }
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": type(exc).__name__, "detail": str(exc)[:200]}
