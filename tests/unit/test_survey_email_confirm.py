"""Тесты e-mail confirm page для сервисных опросов (ТЗ-29 P1)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from sfrfr.api import create_app
from sfrfr.services.diagnosis_survey import hash_action_token, new_action_token


class _MemSurveyRepo:
    def __init__(self) -> None:
        self.campaigns: dict[str, dict[str, Any]] = {}
        self.tokens: dict[str, dict[str, Any]] = {}
        self.by_hash: dict[str, str] = {}
        self.responses: dict[str, dict[str, Any]] = {}

    def get_token_by_hash(self, token_hash: str) -> dict[str, Any] | None:
        tid = self.by_hash.get(token_hash)
        return self.tokens.get(tid or "") if tid else None

    def get_campaign(self, campaign_id: str) -> dict[str, Any] | None:
        return self.campaigns.get(campaign_id)

    def get_response(self, campaign_id: str, question_code: str) -> dict[str, Any] | None:
        return self.responses.get(f"{campaign_id}:{question_code}")

    def insert_response(self, row: dict[str, Any]) -> dict[str, Any]:
        key = f"{row['campaign_id']}:{row['question_code']}"
        self.responses[key] = dict(row)
        return row

    def mark_token_used(self, token_id: str, *, used_at: str) -> None:
        if token_id in self.tokens:
            self.tokens[token_id]["used_at"] = used_at

    def update_campaign(self, campaign_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        self.campaigns.setdefault(campaign_id, {"id": campaign_id}).update(fields)
        return self.campaigns[campaign_id]

    def list_campaigns(self, case_id: str) -> list[dict[str, Any]]:
        return [c for c in self.campaigns.values() if c.get("case_id") == case_id]

    def cancel_open_campaigns(self, case_id: str, *, except_id: str | None = None) -> int:
        n = 0
        for c in self.campaigns.values():
            if c.get("case_id") != case_id:
                continue
            if except_id and c.get("id") == except_id:
                continue
            if c.get("status") in ("draft", "scheduled", "approved"):
                c["status"] = "cancelled"
                n += 1
        return n

    def has_suppression(self, case_id: str) -> bool:
        return False

    def insert_campaign(self, row: dict[str, Any]) -> dict[str, Any]:
        self.campaigns[row["id"]] = dict(row)
        return row

    def get_campaign_by_idempotency(self, key: str) -> dict[str, Any] | None:
        for c in self.campaigns.values():
            if c.get("idempotency_key") == key:
                return c
        return None

    def insert_token(self, row: dict[str, Any]) -> dict[str, Any]:
        self.tokens[row["id"]] = dict(row)
        self.by_hash[row["token_hash"]] = row["id"]
        return row


class _MemFeedback:
    def patch(self, case_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        return {"case_id": case_id, **fields}

    def get(self, case_id: str) -> dict[str, Any] | None:
        return None

    def ensure_row(self, case_id: str) -> dict[str, Any]:
        return {"case_id": case_id}


@pytest.fixture
def survey_client() -> tuple[TestClient, _MemSurveyRepo, str]:
    repo = _MemSurveyRepo()
    raw = new_action_token()
    camp_id = "camp-email-1"
    expires = (datetime.now(UTC) + timedelta(days=7)).isoformat()
    repo.campaigns[camp_id] = {
        "id": camp_id,
        "case_id": "case-1",
        "survey_type": "clarity",
        "channel": "email",
        "status": "sent",
        "body": "Тестовый опрос",
    }
    repo.insert_token(
        {
            "id": "tok-1",
            "campaign_id": camp_id,
            "token_hash": hash_action_token(raw),
            "answer_code": "clear",
            "expires_at": expires,
        }
    )
    app = create_app()
    client = TestClient(app)
    return client, repo, raw


SurveyClient = tuple[TestClient, _MemSurveyRepo, str]
_FEEDBACK_REPO = "sfrfr.services.diagnosis_survey.DiagnosisFeedbackRepository"


def test_survey_get_shows_confirm_page(survey_client: SurveyClient) -> None:
    client, repo, raw = survey_client
    feedback = _MemFeedback()
    with (
        patch("sfrfr.api.routes.survey_actions.DiagnosisSurveyRepository", return_value=repo),
        patch("sfrfr.services.diagnosis_survey.DiagnosisSurveyRepository", return_value=repo),
        patch(_FEEDBACK_REPO, return_value=feedback),
    ):
        resp = client.get(f"/api/portal/survey/{raw}", headers={"Accept": "text/html"})
    assert resp.status_code == 200
    assert "Подтвердить" in resp.text
    assert "Всё понятно" in resp.text
    assert repo.responses == {}


def test_survey_post_confirm_records_email(survey_client: SurveyClient) -> None:
    client, repo, raw = survey_client
    feedback = _MemFeedback()
    with (
        patch("sfrfr.api.routes.survey_actions.DiagnosisSurveyRepository", return_value=repo),
        patch("sfrfr.services.diagnosis_survey.DiagnosisSurveyRepository", return_value=repo),
        patch(_FEEDBACK_REPO, return_value=feedback),
    ):
        resp = client.post(f"/api/portal/survey/{raw}/confirm", headers={"Accept": "text/html"})
    assert resp.status_code == 200
    assert "Спасибо" in resp.text
    assert repo.campaigns["camp-email-1"]["status"] == "completed"
    resp_row = repo.responses.get("camp-email-1:clarity")
    assert resp_row is not None
    assert resp_row["confirmation_method"] == "email_confirm"
    assert resp_row["channel"] == "email"


def test_survey_email_link_helper() -> None:
    from sfrfr.services.diagnosis_survey import survey_email_link

    url = survey_email_link("abc123token", base_url="https://api.example.ru")
    assert url == "https://api.example.ru/api/portal/survey/abc123token"
