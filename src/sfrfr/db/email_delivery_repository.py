"""Репозиторий delivery_events и contact_delivery_status (ТЗ-31)."""

from __future__ import annotations

from typing import Any

from sfrfr.db.session import get_supabase_client


class EmailDeliveryRepository:
    def __init__(self, client: Any | None = None) -> None:
        self.client = client or get_supabase_client()

    def fingerprint_exists(self, fingerprint: str) -> bool:
        resp = (
            self.client.table("delivery_events")
            .select("id")
            .eq("event_fingerprint", fingerprint)
            .limit(1)
            .execute()
        )
        return bool(resp.data)

    def insert_event(self, row: dict[str, Any]) -> dict[str, Any]:
        resp = self.client.table("delivery_events").insert(row).execute()
        return (resp.data or [row])[0]

    def get_job_by_provider_message_id(self, message_id: str) -> dict[str, Any] | None:
        resp = (
            self.client.table("notification_jobs")
            .select("*")
            .eq("provider_message_id", message_id)
            .limit(1)
            .execute()
        )
        rows = resp.data or []
        return rows[0] if rows else None

    def update_job(self, job_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        resp = (
            self.client.table("notification_jobs")
            .update(fields)
            .eq("id", job_id)
            .execute()
        )
        return (resp.data or [fields])[0]

    def cancel_pending_email_jobs(self, *, contact_key: str | None, case_id: str | None) -> int:
        n = 0
        query = self.client.table("notification_jobs").select("id, status, channel, recipient_contact_key, case_id")
        if case_id:
            query = query.eq("case_id", case_id)
        resp = query.limit(80).execute()
        for job in resp.data or []:
            if job.get("channel") != "email":
                continue
            if contact_key and job.get("recipient_contact_key") not in (None, contact_key):
                if job.get("recipient_contact_key") != contact_key:
                    continue
            if job.get("status") not in ("draft", "approved", "queued", "accepted", "deferred", "sent"):
                continue
            self.update_job(str(job["id"]), {"status": "cancelled", "updated_at": _now()})
            n += 1
        return n

    def upsert_contact_status(
        self,
        *,
        contact_key: str,
        channel: str,
        status: str,
        reason: str | None,
    ) -> dict[str, Any]:
        row = {
            "contact_key": contact_key,
            "channel": channel,
            "status": status,
            "reason": reason,
            "updated_at": _now(),
        }
        resp = (
            self.client.table("contact_delivery_status")
            .upsert(row, on_conflict="contact_key,channel")
            .execute()
        )
        return (resp.data or [row])[0]

    def get_contact_status(self, contact_key: str, channel: str) -> dict[str, Any] | None:
        resp = (
            self.client.table("contact_delivery_status")
            .select("*")
            .eq("contact_key", contact_key)
            .eq("channel", channel)
            .limit(1)
            .execute()
        )
        rows = resp.data or []
        return rows[0] if rows else None

    def dashboard_counts(self) -> dict[str, int]:
        """Агрегаты без ПДн."""
        counts = {
            "delivered": 0,
            "deferred": 0,
            "hard_bounce": 0,
            "soft_bounce": 0,
            "complained": 0,
            "failed": 0,
            "opened_email": 0,
            "clicked": 0,
            "unmatched": 0,
        }
        resp = (
            self.client.table("delivery_events")
            .select("event_type, unmatched")
            .order("received_at", desc=True)
            .limit(500)
            .execute()
        )
        for row in resp.data or []:
            et = str(row.get("event_type") or "")
            if row.get("unmatched"):
                counts["unmatched"] += 1
            if et == "delivered":
                counts["delivered"] += 1
            elif et == "deferred":
                counts["deferred"] += 1
            elif et == "hard_bounce":
                counts["hard_bounce"] += 1
            elif et == "soft_bounce":
                counts["soft_bounce"] += 1
            elif et == "complained":
                counts["complained"] += 1
            elif et == "failed":
                counts["failed"] += 1
            elif et == "opened":
                counts["opened_email"] += 1
            elif et == "clicked":
                counts["clicked"] += 1
        return counts

    def list_unmatched(self, *, limit: int = 40) -> list[dict[str, Any]]:
        resp = (
            self.client.table("delivery_events")
            .select(
                "id, provider, provider_message_id, event_type, occurred_at, "
                "severity, unmatched, payload_redacted"
            )
            .eq("unmatched", True)
            .order("received_at", desc=True)
            .limit(min(max(limit, 1), 100))
            .execute()
        )
        return list(resp.data or [])


def _now() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).isoformat()
