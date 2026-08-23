"""Репозиторий сервисных опросов (ТЗ-29)."""

from __future__ import annotations

from typing import Any

from sfrfr.db.session import get_supabase_client


class DiagnosisSurveyRepository:
    def __init__(self, client: Any | None = None) -> None:
        self.client = client or get_supabase_client()

    def insert_campaign(self, row: dict[str, Any]) -> dict[str, Any]:
        resp = self.client.table("survey_campaigns").insert(row).execute()
        return (resp.data or [row])[0]

    def get_campaign_by_idempotency(self, key: str) -> dict[str, Any] | None:
        resp = (
            self.client.table("survey_campaigns")
            .select("*")
            .eq("idempotency_key", key)
            .limit(1)
            .execute()
        )
        rows = resp.data or []
        return rows[0] if rows else None

    def get_campaign(self, campaign_id: str) -> dict[str, Any] | None:
        resp = (
            self.client.table("survey_campaigns")
            .select("*")
            .eq("id", campaign_id)
            .limit(1)
            .execute()
        )
        rows = resp.data or []
        return rows[0] if rows else None

    def update_campaign(self, campaign_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        resp = (
            self.client.table("survey_campaigns")
            .update(fields)
            .eq("id", campaign_id)
            .execute()
        )
        return (resp.data or [fields])[0]

    def list_campaigns(self, case_id: str) -> list[dict[str, Any]]:
        resp = (
            self.client.table("survey_campaigns")
            .select("*")
            .eq("case_id", case_id)
            .order("created_at", desc=True)
            .limit(40)
            .execute()
        )
        return list(resp.data or [])

    def list_due_scheduled(self, *, now_iso: str, limit: int = 50) -> list[dict[str, Any]]:
        """Кампании status=scheduled с scheduled_at <= now."""
        resp = (
            self.client.table("survey_campaigns")
            .select("*")
            .eq("status", "scheduled")
            .lte("scheduled_at", now_iso)
            .order("scheduled_at")
            .limit(min(max(limit, 1), 100))
            .execute()
        )
        return list(resp.data or [])

    def count_sent_surveys(self, case_id: str) -> int:
        rows = self.list_campaigns(case_id)
        return sum(1 for r in rows if r.get("status") in ("sent", "completed", "approved"))

    def insert_token(self, row: dict[str, Any]) -> dict[str, Any]:
        resp = self.client.table("survey_action_tokens").insert(row).execute()
        return (resp.data or [row])[0]

    def get_token_by_hash(self, token_hash: str) -> dict[str, Any] | None:
        resp = (
            self.client.table("survey_action_tokens")
            .select("*")
            .eq("token_hash", token_hash)
            .limit(1)
            .execute()
        )
        rows = resp.data or []
        return rows[0] if rows else None

    def mark_token_used(self, token_id: str, *, used_at: str) -> None:
        self.client.table("survey_action_tokens").update({"used_at": used_at}).eq(
            "id", token_id
        ).execute()

    def insert_response(self, row: dict[str, Any]) -> dict[str, Any]:
        resp = self.client.table("survey_responses").insert(row).execute()
        return (resp.data or [row])[0]

    def get_response(self, campaign_id: str, question_code: str) -> dict[str, Any] | None:
        resp = (
            self.client.table("survey_responses")
            .select("*")
            .eq("campaign_id", campaign_id)
            .eq("question_code", question_code)
            .limit(1)
            .execute()
        )
        rows = resp.data or []
        return rows[0] if rows else None

    def cancel_open_campaigns(
        self,
        case_id: str,
        *,
        except_id: str | None = None,
    ) -> int:
        n = 0
        for row in self.list_campaigns(case_id):
            if row.get("status") not in ("draft", "scheduled", "approved", "sent"):
                continue
            if except_id and str(row.get("id")) == except_id:
                continue
            self.update_campaign(
                str(row["id"]),
                {"status": "cancelled", "updated_at": _now()},
            )
            n += 1
        return n

    def has_suppression(self, case_id: str) -> bool:
        resp = (
            self.client.table("survey_suppressions")
            .select("id")
            .eq("case_id", case_id)
            .limit(1)
            .execute()
        )
        return bool(resp.data)

    def add_suppression(
        self,
        *,
        case_id: str,
        reason: str,
        source: str | None = None,
    ) -> dict[str, Any]:
        row = {
            "case_id": case_id,
            "reason": reason,
            "source": source or "system",
        }
        resp = self.client.table("survey_suppressions").insert(row).execute()
        return (resp.data or [row])[0]


def _now() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).isoformat()
