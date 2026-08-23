"""Репозиторий безопасной выдачи PDF (ТЗ-28)."""

from __future__ import annotations

from typing import Any

from sfrfr.db.session import get_supabase_client


class DiagnosisDeliveryRepository:
    def __init__(self, client: Any | None = None) -> None:
        self.client = client or get_supabase_client()

    def insert_result(self, row: dict[str, Any]) -> dict[str, Any]:
        resp = self.client.table("diagnostic_results").insert(row).execute()
        return (resp.data or [row])[0]

    def update_result(self, result_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        resp = (
            self.client.table("diagnostic_results")
            .update(fields)
            .eq("id", result_id)
            .execute()
        )
        return (resp.data or [fields])[0]

    def get_result(self, result_id: str) -> dict[str, Any] | None:
        resp = (
            self.client.table("diagnostic_results")
            .select("*")
            .eq("id", result_id)
            .limit(1)
            .execute()
        )
        rows = resp.data or []
        return rows[0] if rows else None

    def get_published_for_case(self, case_id: str) -> dict[str, Any] | None:
        """Активный результат (ещё не closed/revoked)."""
        for status in (
            "published",
            "link_issued",
            "delivered",
            "opened",
            "feedback_pending",
            "feedback_received",
        ):
            resp = (
                self.client.table("diagnostic_results")
                .select("*")
                .eq("case_id", case_id)
                .eq("status", status)
                .limit(1)
                .execute()
            )
            rows = resp.data or []
            if rows:
                return rows[0]
        return None

    def insert_link(self, row: dict[str, Any]) -> dict[str, Any]:
        resp = self.client.table("secure_share_links").insert(row).execute()
        return (resp.data or [row])[0]

    def get_link_by_hash(self, token_hash: str) -> dict[str, Any] | None:
        resp = (
            self.client.table("secure_share_links")
            .select("*")
            .eq("token_hash", token_hash)
            .limit(1)
            .execute()
        )
        rows = resp.data or []
        return rows[0] if rows else None

    def update_link(self, link_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        resp = (
            self.client.table("secure_share_links")
            .update(fields)
            .eq("id", link_id)
            .execute()
        )
        return (resp.data or [fields])[0]

    def insert_job(self, row: dict[str, Any]) -> dict[str, Any]:
        resp = self.client.table("notification_jobs").insert(row).execute()
        return (resp.data or [row])[0]

    def get_job_by_idempotency(self, key: str) -> dict[str, Any] | None:
        resp = (
            self.client.table("notification_jobs")
            .select("*")
            .eq("idempotency_key", key)
            .limit(1)
            .execute()
        )
        rows = resp.data or []
        return rows[0] if rows else None

    def list_jobs(self, case_id: str) -> list[dict[str, Any]]:
        resp = (
            self.client.table("notification_jobs")
            .select("*")
            .eq("case_id", case_id)
            .order("created_at", desc=True)
            .limit(40)
            .execute()
        )
        return list(resp.data or [])

    def list_failed_jobs(self, *, limit: int = 50) -> list[dict[str, Any]]:
        resp = (
            self.client.table("notification_jobs")
            .select(
                "id, case_id, job_type, channel, status, failure_reason, "
                "updated_at, failed_at, retry_count"
            )
            .eq("status", "failed")
            .order("updated_at", desc=True)
            .limit(min(max(limit, 1), 100))
            .execute()
        )
        return list(resp.data or [])

    def count_service_sent_since(self, case_id: str, since_iso: str) -> int:
        jobs = self.list_jobs(case_id)
        n = 0
        for job in jobs:
            if job.get("status") not in ("sent", "delivered", "queued", "approved"):
                continue
            sent = job.get("sent_at") or job.get("updated_at") or ""
            if str(sent) >= since_iso:
                n += 1
        return n

    def get_active_link_for_result(self, result_id: str) -> dict[str, Any] | None:
        resp = (
            self.client.table("secure_share_links")
            .select("*")
            .eq("diagnostic_result_id", result_id)
            .is_("revoked_at", "null")
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        rows = resp.data or []
        return rows[0] if rows else None

    def list_results_needing_unread_check(self, *, limit: int = 40) -> list[dict[str, Any]]:
        """Published/delivered без opened — кандидаты на reminder."""
        resp = (
            self.client.table("diagnostic_results")
            .select("*")
            .in_("status", ["published", "link_issued", "delivered"])
            .order("published_at", desc=True)
            .limit(min(max(limit, 1), 100))
            .execute()
        )
        return list(resp.data or [])

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        resp = (
            self.client.table("notification_jobs")
            .select("*")
            .eq("id", job_id)
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

    def cancel_jobs(
        self,
        case_id: str,
        *,
        job_types: list[str] | None = None,
        statuses: list[str] | None = None,
    ) -> int:
        statuses = statuses or ["draft", "approved"]
        # Fetch then update — PostgREST filter combinations vary by client.
        jobs = self.list_jobs(case_id)
        n = 0
        for job in jobs:
            if job.get("status") not in statuses:
                continue
            if job_types and job.get("job_type") not in job_types:
                continue
            self.update_job(
                str(job["id"]),
                {"status": "cancelled", "updated_at": _now()},
            )
            n += 1
        return n


def _now() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).isoformat()
