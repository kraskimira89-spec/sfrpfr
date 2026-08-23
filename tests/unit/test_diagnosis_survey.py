"""Unit-тесты сервисных опросов clarity (ТЗ-29) без живого Supabase."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from sfrfr.services.diagnosis_survey import (
    CLARITY_ANSWERS,
    DiagnosisSurveyService,
    hash_action_token,
    is_night_msk,
    new_action_token,
    next_daytime_msk,
)


def test_action_token_hash() -> None:
    a = new_action_token()
    b = new_action_token()
    assert a != b
    assert hash_action_token(a) == hash_action_token(a)
    assert len(hash_action_token(a)) == 64


def test_next_daytime_avoids_night() -> None:
    night = datetime(2026, 8, 23, 23, 30, tzinfo=UTC)  # ~02:30 MSK
    day = next_daytime_msk(night)
    assert not is_night_msk(day)


class _MemSurveyRepo:
    def __init__(self) -> None:
        self.campaigns: dict[str, dict[str, Any]] = {}
        self.tokens: dict[str, dict[str, Any]] = {}
        self.by_hash: dict[str, str] = {}
        self.responses: dict[str, dict[str, Any]] = {}
        self.suppressions: set[str] = set()

    def get_campaign_by_idempotency(self, key: str) -> dict[str, Any] | None:
        for c in self.campaigns.values():
            if c.get("idempotency_key") == key:
                return c
        return None

    def insert_campaign(self, row: dict[str, Any]) -> dict[str, Any]:
        self.campaigns[row["id"]] = dict(row)
        return self.campaigns[row["id"]]

    def get_campaign(self, campaign_id: str) -> dict[str, Any] | None:
        return self.campaigns.get(campaign_id)

    def update_campaign(self, campaign_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        self.campaigns.setdefault(campaign_id, {"id": campaign_id}).update(fields)
        return self.campaigns[campaign_id]

    def list_campaigns(self, case_id: str) -> list[dict[str, Any]]:
        return [c for c in self.campaigns.values() if c.get("case_id") == case_id]

    def list_due_scheduled(self, *, now_iso: str, limit: int = 50) -> list[dict[str, Any]]:
        out = []
        for c in self.campaigns.values():
            if c.get("status") != "scheduled":
                continue
            if str(c.get("scheduled_at") or "") <= now_iso:
                out.append(c)
        return out[:limit]

    def count_sent_surveys(self, case_id: str) -> int:
        return sum(
            1
            for r in self.list_campaigns(case_id)
            if r.get("status") in ("sent", "completed", "approved")
        )

    def insert_token(self, row: dict[str, Any]) -> dict[str, Any]:
        self.tokens[row["id"]] = dict(row)
        self.by_hash[row["token_hash"]] = row["id"]
        return self.tokens[row["id"]]

    def get_token_by_hash(self, token_hash: str) -> dict[str, Any] | None:
        tid = self.by_hash.get(token_hash)
        return self.tokens.get(tid) if tid else None

    def mark_token_used(self, token_id: str, *, used_at: str) -> None:
        self.tokens[token_id]["used_at"] = used_at

    def insert_response(self, row: dict[str, Any]) -> dict[str, Any]:
        key = f"{row['campaign_id']}:{row['question_code']}"
        self.responses[key] = dict(row)
        return self.responses[key]

    def get_response(self, campaign_id: str, question_code: str) -> dict[str, Any] | None:
        return self.responses.get(f"{campaign_id}:{question_code}")

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
            row["status"] = "cancelled"
            n += 1
        return n

    def has_suppression(self, case_id: str) -> bool:
        return case_id in self.suppressions

    def add_suppression(
        self,
        *,
        case_id: str,
        reason: str,
        source: str | None = None,
    ) -> dict[str, Any]:
        self.suppressions.add(case_id)
        return {"case_id": case_id, "reason": reason, "source": source}


class _MemFeedback:
    def __init__(self) -> None:
        self.rows: dict[str, dict[str, Any]] = {}

    def patch(self, case_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        self.rows.setdefault(case_id, {"case_id": case_id}).update(fields)
        return self.rows[case_id]


def _svc() -> tuple[DiagnosisSurveyService, _MemSurveyRepo, _MemFeedback]:
    repo = _MemSurveyRepo()
    fb = _MemFeedback()
    return DiagnosisSurveyService(repo=repo, feedback=fb), repo, fb  # type: ignore[arg-type]


def test_schedule_clarity_draft_once() -> None:
    svc, repo, _fb = _svc()
    a = svc.schedule_clarity_after_open(case_id="c1", diagnostic_result_id="r1", delay_hours=48)
    b = svc.schedule_clarity_after_open(case_id="c1", diagnostic_result_id="r1", delay_hours=48)
    assert a is not None and b is not None
    assert a["id"] == b["id"]
    assert a["status"] == "scheduled"
    assert a["survey_type"] == "clarity"
    clarity = [c for c in repo.list_campaigns("c1") if c["survey_type"] == "clarity"]
    acquaint = [c for c in repo.list_campaigns("c1") if c["survey_type"] == "acquaint"]
    assert len(clarity) == 1
    assert len(acquaint) == 1


def test_clear_schedules_first_step_and_cancels_acquaint() -> None:
    svc, repo, fb = _svc()
    camp = svc.schedule_clarity_after_open(case_id="c4", diagnostic_result_id="r4", delay_hours=0)
    assert camp is not None
    cid = str(camp["id"])
    tokens = svc.prepare_send_tokens(cid)
    repo.update_campaign(cid, {"status": "sent"})
    out = svc.handle_action_token(tokens["clear"])
    assert out["side_effects"].get("first_step_draft")
    assert out["side_effects"].get("pipeline") == "acts_alone"
    assert fb.rows["c4"]["feedback_status"] == "understood"
    assert fb.rows["c4"]["first_plan_step_status"] == "pending"
    types = {c["survey_type"]: c["status"] for c in repo.list_campaigns("c4")}
    assert "first_step" in types
    acquaint = [c for c in repo.list_campaigns("c4") if c["survey_type"] == "acquaint"]
    assert all(c["status"] == "cancelled" for c in acquaint)


def test_first_step_answers() -> None:
    svc, repo, fb = _svc()
    camp = svc.schedule_clarity_after_open(case_id="c10", diagnostic_result_id="r10", delay_hours=0)
    assert camp is not None
    tokens = svc.prepare_send_tokens(str(camp["id"]))
    repo.update_campaign(str(camp["id"]), {"status": "sent"})
    svc.handle_action_token(tokens["clear"])
    fs = [c for c in repo.list_campaigns("c10") if c["survey_type"] == "first_step"][0]
    out = svc.approve_and_mark_sent(campaign_id=str(fs["id"]), actor_id="staff")
    assert out.get("ok")
    assert set(out["tokens"]) == {"done", "blocked", "deferred"}
    blocked = svc.handle_action_token(out["tokens"]["blocked"])
    assert blocked["side_effects"]["first_plan_step_status"] == "blocked"
    assert fb.rows["c10"]["first_plan_step_status"] == "blocked"


def test_due_tick_promotes_scheduled() -> None:
    svc, repo, _fb = _svc()
    past = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    repo.insert_campaign(
        {
            "id": "due1",
            "case_id": "c11",
            "survey_type": "first_step",
            "status": "scheduled",
            "scheduled_at": past,
        }
    )
    stats = svc.run_due_tick()
    assert stats["promoted"] >= 1
    assert repo.get_campaign("due1")["status"] == "draft"


def test_not_viewed_one_retry() -> None:
    svc, repo, _fb = _svc()
    camp = svc.schedule_clarity_after_open(case_id="c5", diagnostic_result_id="r5", delay_hours=0)
    assert camp is not None
    cid = str(camp["id"])
    tokens = svc.prepare_send_tokens(cid)
    repo.update_campaign(cid, {"status": "sent", "touch_index": 1})
    svc.handle_action_token(tokens["not_viewed"])
    clarity = [c for c in repo.list_campaigns("c5") if c["survey_type"] == "clarity"]
    assert len(clarity) == 2
    retry = [c for c in clarity if c["id"] != cid][0]
    assert retry["status"] == "scheduled"
    assert retry["touch_index"] == 2


def test_expired_token_raises() -> None:
    svc, repo, _fb = _svc()
    camp = svc.schedule_clarity_after_open(case_id="c6", diagnostic_result_id=None, delay_hours=0)
    assert camp is not None
    cid = str(camp["id"])
    raw = new_action_token()
    repo.insert_token(
        {
            "id": "t1",
            "campaign_id": cid,
            "token_hash": hash_action_token(raw),
            "answer_code": "clear",
            "expires_at": (datetime.now(UTC) - timedelta(hours=1)).isoformat(),
        }
    )
    with pytest.raises(PermissionError, match="expired"):
        svc.handle_action_token(raw)


def test_do_not_contact_cancels_on_approve() -> None:
    svc, repo, _fb = _svc()
    camp = svc.schedule_clarity_after_open(case_id="c7", diagnostic_result_id=None, delay_hours=0)
    assert camp is not None
    out = svc.approve_and_mark_sent(
        campaign_id=str(camp["id"]),
        actor_id="s",
        do_not_contact=True,
    )
    assert out.get("cancelled")
    assert repo.get_campaign(str(camp["id"]))["status"] == "cancelled"
