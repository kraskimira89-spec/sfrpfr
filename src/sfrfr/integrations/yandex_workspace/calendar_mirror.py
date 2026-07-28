"""Зеркалирование Google Calendar → Яндекс Календарь (операционка, без ПДн)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sfrfr.integrations.calendar import CalendarClient
from sfrfr.integrations.yandex_workspace.calendar_yandex import create_event


def _parse_start(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        if "T" in raw:
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        # all-day
        return datetime.fromisoformat(f"{raw}T09:00:00+03:00")
    except ValueError:
        return None


def mirror_google_to_yandex(
    *,
    max_results: int = 25,
    include_past_days: int = 0,
) -> dict[str, Any]:
    """
    Скопировать ближайшие события Google → Яндекс CalDAV.
    Description содержит google_event_id + case_id (если был в summary).
    """
    google = CalendarClient()
    listed = google.list_events(max_results=max_results)
    if not listed.get("ok"):
        return {
            "ok": False,
            "google": listed,
            "mirrored": [],
            "reason": listed.get("reason") or listed.get("error") or "google_list_failed",
        }

    events = list(listed.get("events") or [])
    # list_events уже с timeMin=now; include_past_days оставлен для будущего расширения
    _ = include_past_days

    mirrored: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for item in events:
        start = _parse_start(item.get("start"))
        if start is None:
            errors.append({"id": item.get("id"), "error": "bad_start"})
            continue
        if start.tzinfo is None:
            start = start.replace(tzinfo=UTC)
        summary = (item.get("summary") or "SFRFR").strip()[:180]
        # case_id из формата Google: "[uuid] title"
        case_id = "google-mirror"
        if summary.startswith("[") and "]" in summary:
            case_id = summary[1 : summary.index("]")].strip() or case_id
        result = create_event(
            case_id=case_id[:64],
            summary=summary,
            starts_at=start,
            duration_minutes=60,
            description=f"source=google_mirror\ngoogle_event_id={item.get('id')}",
        )
        entry = {
            "google_id": item.get("id"),
            "summary": summary,
            "start": start.isoformat(),
            "yandex": {
                "ok": result.get("ok"),
                "uid": result.get("uid"),
                "status_code": result.get("status_code"),
                "error": result.get("error"),
            },
        }
        if result.get("ok"):
            mirrored.append(entry)
        else:
            errors.append(entry)

    return {
        "ok": True,
        "google_count": len(events),
        "mirrored_count": len(mirrored),
        "mirrored": mirrored,
        "errors": errors,
        "note": (
            "Google пока source of truth для create через CLI; "
            "Yandex получает копию (dual-write / mirror)."
        ),
    }


def create_on_both(
    *,
    case_id: str,
    title: str,
    start: datetime,
    duration_minutes: int = 60,
    task_type: str = "consult",
) -> dict[str, Any]:
    """Создать событие в Google и сразу дублировать в Яндекс."""
    google = CalendarClient().create_event(
        case_id=case_id,
        title=title,
        start=start,
        duration_minutes=duration_minutes,
        task_type=task_type,
    )
    yandex = create_event(
        case_id=case_id,
        summary=f"[{case_id[:36]}] {(title or task_type).strip()[:120]}",
        starts_at=start,
        duration_minutes=duration_minutes,
        description=f"case_id={case_id}\ntask={task_type}\nsource=sfrfr_dual",
    )
    google_ok = bool(google.get("ok") or google.get("skipped"))
    yandex_ok = bool(yandex.get("ok") or yandex.get("skipped"))
    return {
        "ok": google_ok and yandex_ok and (google.get("ok") or yandex.get("ok")),
        "google": google,
        "yandex": yandex,
    }
