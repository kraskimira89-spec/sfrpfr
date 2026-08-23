"""Unit-тесты безопасной выдачи PDF (ТЗ-28) без живого Supabase."""

from __future__ import annotations

from typing import Any

import pytest

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
    assert hash_share_token(a) != hash_share_token(b)
    assert len(hash_share_token(a)) == 64


def test_result_ready_body_has_link_no_forbidden() -> None:
    body = build_result_ready_body(
        secure_link="https://api.example/api/portal/diag-share/tok",
        cabinet_url="https://cabinet.example",
    )
    assert "diag-share/tok" in body
    assert "СФР" in body
    assert_safe_notify_text(body)


def test_forbidden_markers_raise() -> None:
    with pytest.raises(ValueError, match="forbidden_marker"):
        assert_safe_notify_text("Ваш СНИЛС 123")


class _MemRepo:
    def __init__(self) -> None:
        self.results: dict[str, dict[str, Any]] = {}
        self.links: dict[str, dict[str, Any]] = {}
        self.jobs: dict[str, dict[str, Any]] = {}
        self.by_hash: dict[str, str] = {}

    def insert_result(self, row: dict[str, Any]) -> dict[str, Any]:
        self.results[row["id"]] = dict(row)
        return self.results[row["id"]]

    def update_result(self, result_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        self.results.setdefault(result_id, {"id": result_id}).update(fields)
        return self.results[result_id]

    def get_result(self, result_id: str) -> dict[str, Any] | None:
        return self.results.get(result_id)

    def get_published_for_case(self, case_id: str) -> dict[str, Any] | None:
        for row in self.results.values():
            if row.get("case_id") == case_id and row.get("status") == "published":
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

    def insert_job(self, row: dict[str, Any]) -> dict[str, Any]:
        self.jobs[row["id"]] = dict(row)
        return self.jobs[row["id"]]

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


def test_publish_creates_draft_jobs_and_share() -> None:
    from sfrfr.services.diagnosis_delivery import DiagnosisDeliveryService

    repo = _MemRepo()
    fb = _MemFeedback()
    svc = DiagnosisDeliveryService(repo=repo, feedback=fb)  # type: ignore[arg-type]
    out = svc.publish(
        case_id="c1",
        document_id="d1",
        actor_id="u1",
        channels=["email", "max"],
    )
    assert out["share_token_once"]
    assert "diag-share/" in out["share_url_once"]
    jobs = repo.list_jobs("c1")
    types = {j["job_type"] for j in jobs}
    assert "result_ready" in types
    assert "result_unread" in types
    assert all(j["status"] == "draft" for j in jobs)
    assert all(j["requires_staff_approval"] is True for j in jobs)


def test_view_cancels_unread_draft() -> None:
    from sfrfr.services.diagnosis_delivery import DiagnosisDeliveryService, hash_share_token

    repo = _MemRepo()
    fb = _MemFeedback()
    svc = DiagnosisDeliveryService(repo=repo, feedback=fb)  # type: ignore[arg-type]
    out = svc.publish(case_id="c2", document_id="d2", actor_id="u1", channels=["email"])
    token = out["share_token_once"]
    resolved = svc.resolve_share_token(token)
    assert resolved["document_id"] == "d2"
    unread = [j for j in repo.list_jobs("c2") if j["job_type"] == "result_unread"]
    assert unread and unread[0]["status"] == "cancelled"
    assert fb.rows["c2"].get("pdf_opened_at")
    # повтор с тем же hash
    assert repo.get_link_by_hash(hash_share_token(token))
