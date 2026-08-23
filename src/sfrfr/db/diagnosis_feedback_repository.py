"""Репозиторий diagnosis_feedback (ТЗ-27)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sfrfr.db.session import get_supabase_client


def _now() -> str:
    return datetime.now(UTC).isoformat()


class DiagnosisFeedbackRepository:
    def __init__(self, client: Any | None = None) -> None:
        self.client = client or get_supabase_client()

    def get(self, case_id: str) -> dict[str, Any] | None:
        resp = (
            self.client.table("diagnosis_feedback")
            .select("*")
            .eq("case_id", case_id)
            .limit(1)
            .execute()
        )
        rows = resp.data or []
        return rows[0] if rows else None

    def ensure_row(self, case_id: str) -> dict[str, Any]:
        existing = self.get(case_id)
        if existing:
            return existing
        resp = (
            self.client.table("diagnosis_feedback")
            .insert({"case_id": case_id})
            .execute()
        )
        rows = resp.data or []
        return rows[0] if rows else {"case_id": case_id}

    def mark_pdf_issued(self, case_id: str, *, issued_at: str | None = None) -> dict[str, Any]:
        """Фиксация выдачи PDF; планирует касание через 2–3 дня."""
        self.ensure_row(case_id)
        row = self.get(case_id) or {}
        if row.get("pdf_issued_at"):
            return row
        issued = issued_at or _now()
        due2 = (datetime.now(UTC) + timedelta(days=2)).isoformat()
        due3 = (datetime.now(UTC) + timedelta(days=10)).isoformat()
        payload = {
            "pdf_issued_at": issued,
            "feedback_status": "nav_pending",
            "touch2_due_at": due2,
            "touch3_due_at": due3,
            "updated_at": _now(),
        }
        resp = (
            self.client.table("diagnosis_feedback")
            .update(payload)
            .eq("case_id", case_id)
            .execute()
        )
        rows = resp.data or []
        return rows[0] if rows else {**row, **payload}

    def patch(self, case_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        self.ensure_row(case_id)
        allowed = {
            "pdf_issued_at",
            "pdf_opened_at",
            "feedback_status",
            "clarity_score",
            "expectation_match",
            "useful_section",
            "improvement_comment",
            "first_plan_step_status",
            "difficulty_category",
            "follow_up_service_requested",
            "review_publication_consent",
            "review_consent_version",
            "review_consent_at",
            "touch2_due_at",
            "touch3_due_at",
            "touch2_sent_at",
            "touch3_sent_at",
        }
        payload = {k: v for k, v in fields.items() if k in allowed}
        consent = payload.get("review_publication_consent")
        if consent == "granted":
            # Публикация без granted запрещена на уровне процесса.
            pass
        payload["updated_at"] = _now()
        resp = (
            self.client.table("diagnosis_feedback")
            .update(payload)
            .eq("case_id", case_id)
            .execute()
        )
        rows = resp.data or []
        return rows[0] if rows else payload
