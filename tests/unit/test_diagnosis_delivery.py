"""Unit-тесты выдачи PDF: триггеры 1–4 (ТЗ-28/30)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from sfrfr.services.contact_policy import can_contact, looks_like_bot_user_agent
from sfrfr.services.diagnosis_delivery import (
    assert_safe_notify_text,
    build_result_ready_body,
    hash_share_token,
    new_share_token,
)


def test_token_hash_stable_and_random() -> None:
    a = new_share_token()
    b = new_share_token()
    assert a != b
    assert hash_share_token(a) == hash_share_token(a)
    assert len(hash_share_token(a)) == 64


def test_result_ready_body_has_link_no_forbidden() -> None:
    body = build_result_ready_body(
        secure_link="https://api.example/api/portal/diag-share/tok",
        cabinet_url="https://cabinet.example",
    )
    assert "diag-share/tok" in body
    assert_safe_notify_text(body)


def test_forbidden_markers_raise() -> None:
    with pytest.raises(ValueError, match="forbidden_marker"):
        assert_safe_notify_text("Ваш СНИЛС 123")


def test_can_contact_blocks() -> None:
    assert can_contact(message_type="service", channel="email").allowed
    assert not can_contact(
        message_type="service", channel="email", do_not_contact=True
    ).allowed
    assert not can_contact(
        message_type="marketing", channel="max", marketing_consent_rows=[]
    ).allowed
    assert looks_like_bot_user_agent("Outlook-iOS/2.0")
    assert not looks_like_bot_user_agent("Mozilla/5.0 Chrome/120")


class _MemRepo:
    def __init__(self) -> None:
        self.results: dict[str, dict[str, Any]] = {}
        self.links: dict[str, dict[str, Any]] = {}
        self.jobs: dict[str, dict[str, Any]] = {}
        self.by_hash: dict[str, str] = {}
        self.by_idem: dict[str, str] = {}

    def insert_result(self, row: dict[str, Any]) -> dict[str, Any]:
        self.results[row["id"]] = dict(row)
        return self.results[row["id"]]

    def update_result(self, result_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        self.results.setdefault(result_id, {"id": result_id}).update(fields)
        return self.results[result_id]

    def get_result(self, result_id: str) -> dict[str, Any] | None:
        return self.results.get(result_id)

    def get_published_for_case(self, case_id: str) -> dict[str, Any] | None:
        for st in (
            "published",
            "delivered",
            "opened",
            "feedback_pending",
            "feedback_received",
        ):
            for row in self.results.values():
                if row.get("case_id") == case_id and row.get("status") == st:
                    return row
        return None

    def insert_link(self, row: dict[str, Any]) -> dict[str, Any]:
        self.links[row["id"]] = dict(row)
        self.by_hash[row["token_hash"]] = row["id"]
        return self.links[row["id"]]

    def get_link_by_hash(self, token_hash: str) -> dict[str, Any] | None:
        lid = self.by_hash.get(token_hash)
        return self.links.get(lid) if lid else None

    def update_link(self, link_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        self.links.setdefault(link_id, {"id": link_id}).update(fields)
        return self.links[link_id]

    def get_active_link_for_result(self, result_id: str) -> dict[str, Any] | None:
        for row in self.links.values():
            if row.get("diagnostic_result_id") == result_id and not row.get("revoked_at"):
                return row
        return None

    def insert_job(self, row: dict[str, Any]) -> dict[str, Any]:
        self.jobs[row["id"]] = dict(row)
        if row.get("idempotency_key"):
            self.by_idem[row["idempotency_key"]] = row["id"]
        return self.jobs[row["id"]]

    def get_job_by_idempotency(self, key: str) -> dict[str, Any] | None:
        jid = self.by_idem.get(key)
        return self.jobs.get(jid) if jid else None

    def list_jobs(self, case_id: str) -> list[dict[str, Any]]:
        return [j for j in self.jobs.values() if j.get("case_id") == case_id]

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        return self.jobs.get(job_id)

    def update_job(self, job_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        self.jobs.setdefault(job_id, {"id": job_id}).update(fields)
        return self.jobs[job_id]

    def cancel_jobs(
        self,
        case_id: str,
        *,
        job_types: list[str] | None = None,
        statuses: list[str] | None = None,
    ) -> int:
        statuses = statuses or ["draft", "approved"]
        n = 0
        for job in self.list_jobs(case_id):
            if job.get("status") not in statuses:
                continue
            if job_types and job.get("job_type") not in job_types:
                continue
            job["status"] = "cancelled"
            n += 1
        return n

    def count_service_sent_since(self, case_id: str, since_iso: str) -> int:
        return sum(
            1
            for j in self.list_jobs(case_id)
            if j.get("status") in ("sent", "delivered")
            and str(j.get("sent_at") or "") >= since_iso
        )

    def list_results_needing_unread_check(self, *, limit: int = 40) -> list[dict[str, Any]]:
        rows = [
            r
            for r in self.results.values()
            if r.get("status") in ("published", "delivered")
        ]
        return rows[:limit]

    def list_failed_jobs(self, *, limit: int = 50) -> list[dict[str, Any]]:
        return [j for j in self.jobs.values() if j.get("status") == "failed"][:limit]


class _MemFeedback:
    def __init__(self) -> None:
        self.rows: dict[str, dict[str, Any]] = {}

    def mark_pdf_issued(self, case_id: str, *, issued_at: str | None = None) -> dict[str, Any]:
        self.rows.setdefault(case_id, {"case_id": case_id})
        self.rows[case_id]["pdf_issued_at"] = issued_at or "t0"
        return self.rows[case_id]

    def patch(self, case_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        self.rows.setdefault(case_id, {"case_id": case_id}).update(fields)
        return self.rows[case_id]


def test_publish_creates_result_ready_only_with_idempotency() -> None:
    from sfrfr.services.diagnosis_delivery import DiagnosisDeliveryService

    repo = _MemRepo()
    fb = _MemFeedback()
    svc = DiagnosisDeliveryService(repo=repo, feedback=fb)  # type: ignore[arg-type]
    out = svc.publish(
        case_id="c1",
        document_id="d1",
        actor_id="u1",
        channels=["email", "max"],
        checksum="abc",
    )
    assert out["staff_task"]
    jobs = repo.list_jobs("c1")
    types = {j["job_type"] for j in jobs}
    assert types == {"result_ready"}
    assert all(j["status"] == "draft" for j in jobs)
    assert all(j.get("idempotency_key") for j in jobs)
    assert all(j["requires_staff_approval"] is True for j in jobs)
    assert repo.get_result(out["result"]["id"])["status"] == "published"


def test_open_sets_opened_and_cancels_unread() -> None:
    from sfrfr.services.diagnosis_delivery import DiagnosisDeliveryService

    repo = _MemRepo()
    fb = _MemFeedback()
    svc = DiagnosisDeliveryService(repo=repo, feedback=fb)  # type: ignore[arg-type]
    out = svc.publish(case_id="c2", document_id="d2", actor_id="u1", channels=["email"])
    rid = out["result"]["id"]
    # симулируем заранее созданный unread draft
    repo.insert_job(
        {
            "id": "u1",
            "case_id": "c2",
            "diagnostic_result_id": rid,
            "job_type": "result_unread",
            "channel": "email",
            "status": "draft",
            "body": "x",
        }
    )
    resolved = svc.resolve_share_token(
        out["share_token_once"],
        user_agent="Mozilla/5.0",
    )
    assert resolved["counted_as_open"] is True
    assert repo.get_result(rid)["status"] in ("opened", "feedback_pending")
    unread = [j for j in repo.list_jobs("c2") if j["job_type"] == "result_unread"]
    assert unread[0]["status"] == "cancelled"
    assert fb.rows["c2"].get("pdf_opened_at")


def test_bot_ua_does_not_count_open() -> None:
    from sfrfr.services.diagnosis_delivery import DiagnosisDeliveryService

    repo = _MemRepo()
    fb = _MemFeedback()
    svc = DiagnosisDeliveryService(repo=repo, feedback=fb)  # type: ignore[arg-type]
    out = svc.publish(case_id="c3", document_id="d3", actor_id="u1", channels=["email"])
    resolved = svc.resolve_share_token(
        out["share_token_once"],
        user_agent="Mozilla/5.0 (compatible; Googlebot/2.1)",
    )
    assert resolved["bot_skipped"] is True
    assert resolved["counted_as_open"] is False
    assert repo.get_result(out["result"]["id"])["status"] == "published"
    link = repo.get_active_link_for_result(out["result"]["id"])
    assert link is not None and link.get("viewed_at") is None


def test_unread_tick_after_72h() -> None:
    from sfrfr.services.diagnosis_delivery import DiagnosisDeliveryService

    repo = _MemRepo()
    fb = _MemFeedback()
    svc = DiagnosisDeliveryService(repo=repo, feedback=fb)  # type: ignore[arg-type]
    out = svc.publish(case_id="c4", document_id="d4", actor_id="u1", channels=["email"])
    rid = out["result"]["id"]
    ready = [j for j in repo.list_jobs("c4") if j["job_type"] == "result_ready"][0]
    repo.update_job(
        ready["id"],
        {
            "status": "sent",
            "sent_at": (datetime.now(UTC) - timedelta(hours=80)).isoformat(),
        },
    )
    repo.update_result(rid, {"status": "delivered"})
    job = svc.ensure_unread_reminder_draft(result_id=rid)
    assert job is not None
    assert job["job_type"] == "result_unread"
    assert job["status"] == "draft"
    # идемпотентность
    again = svc.ensure_unread_reminder_draft(result_id=rid)
    assert again is not None and again["id"] == job["id"]


def test_do_not_contact_cancels_on_approve() -> None:
    from sfrfr.services.diagnosis_delivery import DiagnosisDeliveryService

    repo = _MemRepo()
    fb = _MemFeedback()
    svc = DiagnosisDeliveryService(repo=repo, feedback=fb)  # type: ignore[arg-type]
    svc.publish(case_id="c5", document_id="d5", actor_id="u1", channels=["max"])
    job = [j for j in repo.list_jobs("c5") if j["channel"] == "max"][0]
    res = svc.approve_max_draft(job_id=job["id"], actor_id="s", do_not_contact=True)
    assert res.get("cancelled")
    assert repo.get_job(job["id"])["status"] == "cancelled"
