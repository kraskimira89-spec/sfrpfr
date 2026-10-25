"""Postgres store для public.tracker_sync_outbox (срез 1)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sfrfr.db.session import get_supabase_client
from sfrfr.integrations.yandex_tracker.outbox import TrackerOutboxEvent


def _row_to_event(row: dict[str, Any]) -> TrackerOutboxEvent:
    created = row.get("created_at")
    processed = row.get("processed_at")
    if isinstance(created, str):
        created_at = datetime.fromisoformat(created.replace("Z", "+00:00"))
    elif isinstance(created, datetime):
        created_at = created
    else:
        created_at = datetime.now(UTC)
    processed_at: datetime | None = None
    if isinstance(processed, str):
        processed_at = datetime.fromisoformat(processed.replace("Z", "+00:00"))
    elif isinstance(processed, datetime):
        processed_at = processed
    return TrackerOutboxEvent(
        event_id=str(row["event_id"]),
        event_type=str(row["event_type"]),
        case_ref=str(row["case_ref"]),
        issue_key=str(row["issue_key"]),
        case_revision=int(row.get("case_revision") or 0),
        payload=dict(row.get("payload") or {}),
        case_id=str(row["case_id"]) if row.get("case_id") else None,
        status=str(row.get("status") or "pending"),
        attempts=int(row.get("attempts") or 0),
        last_error=str(row["last_error"]) if row.get("last_error") else None,
        origin=str(row.get("origin") or "app"),
        created_at=created_at,
        processed_at=processed_at,
    )


class PostgresTrackerOutboxStore:
    """Идемпотентный outbox по event_id через unique constraint."""

    def enqueue(self, event: TrackerOutboxEvent) -> TrackerOutboxEvent:
        client = get_supabase_client()
        existing = (
            client.table("tracker_sync_outbox")
            .select("*")
            .eq("event_id", event.event_id)
            .limit(1)
            .execute()
        )
        rows = list(existing.data or [])
        if rows:
            prev = _row_to_event(rows[0])
            if (
                prev.event_type == event.event_type
                and prev.case_ref == event.case_ref
                and prev.issue_key == event.issue_key
                and prev.case_revision == event.case_revision
                and prev.payload == event.payload
            ):
                return prev
            raise ValueError("tracker_outbox_event_conflict")
        payload = {
            "event_id": event.event_id,
            "event_type": event.event_type,
            "case_id": event.case_id,
            "case_ref": event.case_ref,
            "issue_key": event.issue_key,
            "case_revision": event.case_revision,
            "payload": event.payload,
            "status": "pending",
            "attempts": 0,
            "origin": event.origin or "app",
        }
        inserted = client.table("tracker_sync_outbox").insert(payload).execute()
        data = list(inserted.data or [])
        if not data:
            raise RuntimeError("tracker_outbox_insert_failed")
        return _row_to_event(data[0])

    def list_pending(self, *, limit: int) -> list[TrackerOutboxEvent]:
        client = get_supabase_client()
        res = (
            client.table("tracker_sync_outbox")
            .select("*")
            .eq("status", "pending")
            .order("created_at")
            .limit(max(1, min(limit, 100)))
            .execute()
        )
        return [_row_to_event(r) for r in (res.data or [])]

    def mark_done(self, event_id: str, *, tracker_version: int | None) -> None:
        client = get_supabase_client()
        patch: dict[str, Any] = {
            "status": "done",
            "processed_at": datetime.now(UTC).isoformat(),
            "last_error": None,
        }
        if tracker_version is not None:
            row = (
                client.table("tracker_sync_outbox")
                .select("payload")
                .eq("event_id", event_id)
                .limit(1)
                .execute()
            )
            payload = dict((row.data or [{}])[0].get("payload") or {})
            payload["last_observed_tracker_version"] = tracker_version
            patch["payload"] = payload
        client.table("tracker_sync_outbox").update(patch).eq("event_id", event_id).execute()

    def mark_retry(self, event_id: str, error: str) -> None:
        client = get_supabase_client()
        row = (
            client.table("tracker_sync_outbox")
            .select("attempts")
            .eq("event_id", event_id)
            .limit(1)
            .execute()
        )
        attempts = int((row.data or [{"attempts": 0}])[0].get("attempts") or 0) + 1
        client.table("tracker_sync_outbox").update(
            {"attempts": attempts, "last_error": error[:300], "status": "pending"}
        ).eq("event_id", event_id).execute()

    def mark_error(self, event_id: str, error: str) -> None:
        client = get_supabase_client()
        row = (
            client.table("tracker_sync_outbox")
            .select("attempts")
            .eq("event_id", event_id)
            .limit(1)
            .execute()
        )
        attempts = int((row.data or [{"attempts": 0}])[0].get("attempts") or 0) + 1
        client.table("tracker_sync_outbox").update(
            {"attempts": attempts, "last_error": error[:300], "status": "error"}
        ).eq("event_id", event_id).execute()
