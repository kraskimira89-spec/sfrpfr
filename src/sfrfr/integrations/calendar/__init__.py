"""Google Calendar: события только с case_id (без ФИО/телефона).

Календарь нужно расшарить на SA (GOOGLE_CALENDAR_CREDENTIALS_JSON → client_email).
GOOGLE_CALENDAR_ID — id календаря (не «primary» для чистого SA).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import quote

import httpx

from sfrfr.core.config import get_settings
from sfrfr.integrations.google_sa import access_token, load_service_account_info

_CALENDAR_SCOPE = "https://www.googleapis.com/auth/calendar"
_CALENDAR_API = "https://www.googleapis.com/calendar/v3"


class CalendarClient:
    def __init__(
        self,
        *,
        credentials_json: str | None = None,
        calendar_id: str | None = None,
    ) -> None:
        settings = get_settings()
        raw = (
            credentials_json
            if credentials_json is not None
            else settings.google_calendar_credentials_json
        )
        self._credentials_raw = (raw or "").strip()
        self.calendar_id = (
            calendar_id if calendar_id is not None else settings.google_calendar_id
        ).strip()

    @property
    def available(self) -> bool:
        return bool(self._credentials_raw and self.calendar_id)

    def _auth(self) -> tuple[dict[str, Any], dict[str, str]]:
        info = load_service_account_info(
            self._credentials_raw,
            env_name="GOOGLE_CALENDAR_CREDENTIALS_JSON",
        )
        token = access_token(info, scopes=[_CALENDAR_SCOPE])
        return info, {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    def list_events(self, *, max_results: int = 10) -> dict[str, Any]:
        if not self.available:
            return {
                "ok": False,
                "skipped": True,
                "reason": "no GOOGLE_CALENDAR credentials/id",
                "events": [],
            }
        try:
            info, headers = self._auth()
            cal = quote(self.calendar_id, safe="@.")
            with httpx.Client(timeout=45.0) as client:
                resp = client.get(
                    f"{_CALENDAR_API}/calendars/{cal}/events",
                    headers=headers,
                    params={
                        "maxResults": max(1, min(max_results, 50)),
                        "singleEvents": "true",
                        "orderBy": "startTime",
                        "timeMin": datetime.now(UTC).isoformat(),
                    },
                )
            if resp.status_code >= 400:
                return {
                    "ok": False,
                    "status_code": resp.status_code,
                    "error": (resp.text or "")[:500],
                    "events": [],
                    "sa_email": info.get("client_email"),
                }
            items = (resp.json() or {}).get("items") or []
            events = []
            for item in items:
                start = item.get("start") or {}
                events.append(
                    {
                        "id": item.get("id"),
                        "summary": item.get("summary"),
                        "start": start.get("dateTime") or start.get("date"),
                        "htmlLink": item.get("htmlLink"),
                    }
                )
            return {
                "ok": True,
                "status_code": resp.status_code,
                "events": events,
                "count": len(events),
                "calendar_id": self.calendar_id,
                "sa_email": info.get("client_email"),
            }
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"{type(exc).__name__}: {exc}", "events": []}

    def create_event(
        self,
        *,
        case_id: str,
        title: str,
        start: datetime,
        duration_minutes: int = 60,
        task_type: str = "consult",
    ) -> dict[str, Any]:
        """Создать событие: summary без ПДн, description = case_id + тип."""
        cid = (case_id or "").strip()
        if not cid:
            return {"ok": False, "error": "case_id required"}
        if any(ch in cid for ch in ("/", "\\", "\n", "\r")):
            return {"ok": False, "error": "invalid case_id"}
        if not self.available:
            return {
                "ok": False,
                "skipped": True,
                "reason": "no GOOGLE_CALENDAR credentials/id",
            }

        safe_title = (title or task_type or "task").strip()[:120]
        # не кладём ФИО в summary
        summary = f"[{cid[:36]}] {safe_title}"
        description = f"case_id={cid}\ntask={task_type}\nsource=sfrfr"
        if start.tzinfo is None:
            start = start.replace(tzinfo=UTC)
        end = start + timedelta(minutes=max(15, min(duration_minutes, 8 * 60)))

        try:
            info, headers = self._auth()
            cal = quote(self.calendar_id, safe="@.")
            body = {
                "summary": summary,
                "description": description,
                "start": {"dateTime": start.isoformat()},
                "end": {"dateTime": end.isoformat()},
            }
            with httpx.Client(timeout=45.0) as client:
                resp = client.post(
                    f"{_CALENDAR_API}/calendars/{cal}/events",
                    headers=headers,
                    json=body,
                )
            if resp.status_code >= 400:
                return {
                    "ok": False,
                    "status_code": resp.status_code,
                    "error": (resp.text or "")[:500],
                    "sa_email": info.get("client_email"),
                    "calendar_id": self.calendar_id,
                }
            payload = resp.json() or {}
            return {
                "ok": True,
                "status_code": resp.status_code,
                "id": payload.get("id"),
                "summary": payload.get("summary"),
                "htmlLink": payload.get("htmlLink"),
                "case_id": cid,
                "task_type": task_type,
                "sa_email": info.get("client_email"),
                "calendar_id": self.calendar_id,
            }
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
