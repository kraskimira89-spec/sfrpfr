"""Сервисные опросы после PDF: clarity MAX MVP (ТЗ-29)."""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

from sfrfr.db.diagnosis_feedback_repository import DiagnosisFeedbackRepository
from sfrfr.db.diagnosis_survey_repository import DiagnosisSurveyRepository

TEMPLATE_VERSION = "survey-clarity-v1"
CLARITY_DELAY_HOURS = 48
NOT_VIEWED_RETRY_DAYS = 6
FIRST_STEP_DELAY_DAYS = 10
TOKEN_TTL_DAYS = 14
MAX_SURVEY_TOUCHES = 2
MIN_HOURS_BETWEEN_SERVICE = 48
MSK = ZoneInfo("Europe/Moscow")

CLARITY_ANSWERS = {
    "clear": "Всё понятно",
    "needs_help": "Нужна помощь с планом",
    "question": "Есть вопрос по документу",
    "not_viewed": "Пока не успел(а) посмотреть",
}

CLARITY_BODY = (
    "Здравствуйте! Удалось ли посмотреть результат диагностики?\n"
    "Нам важно убедиться, что план действий понятен."
)


def hash_action_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def new_action_token() -> str:
    return secrets.token_urlsafe(16)


def is_night_msk(now: datetime | None = None) -> bool:
    local = (now or datetime.now(UTC)).astimezone(MSK)
    return local.hour >= 22 or local.hour < 8


def next_daytime_msk(after: datetime | None = None) -> datetime:
    """Сдвинуть на 10:00 MSK, если сейчас ночь."""
    local = (after or datetime.now(UTC)).astimezone(MSK)
    if local.hour >= 22:
        local = (local + timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0)
    elif local.hour < 8:
        local = local.replace(hour=10, minute=0, second=0, microsecond=0)
    return local.astimezone(UTC)


class DiagnosisSurveyService:
    def __init__(
        self,
        repo: DiagnosisSurveyRepository | None = None,
        feedback: DiagnosisFeedbackRepository | None = None,
    ) -> None:
        self.repo = repo or DiagnosisSurveyRepository()
        self.feedback = feedback or DiagnosisFeedbackRepository()

    def schedule_clarity_after_open(
        self,
        *,
        case_id: str,
        diagnostic_result_id: str | None,
        delay_hours: int = CLARITY_DELAY_HOURS,
    ) -> dict[str, Any] | None:
        """После открытия PDF — draft опроса понятности (+48ч, не ночью)."""
        if self.repo.has_suppression(case_id):
            return None
        existing = [
            c
            for c in self.repo.list_campaigns(case_id)
            if c.get("survey_type") == "clarity"
            and c.get("status") in ("draft", "scheduled", "approved", "sent", "completed")
        ]
        if existing:
            return existing[0]
        if self.repo.count_sent_surveys(case_id) >= MAX_SURVEY_TOUCHES:
            return None

        when = datetime.now(UTC) + timedelta(hours=delay_hours)
        when = next_daytime_msk(when)
        row = self.repo.insert_campaign(
            {
                "id": str(uuid4()),
                "case_id": case_id,
                "diagnostic_result_id": diagnostic_result_id,
                "survey_type": "clarity",
                "channel": "max",
                "status": "draft",
                "scheduled_at": when.isoformat(),
                "expires_at": (when + timedelta(days=TOKEN_TTL_DAYS)).isoformat(),
                "template_version": TEMPLATE_VERSION,
                "body": CLARITY_BODY,
                "touch_index": 1,
                "updated_at": _now(),
            }
        )
        return row

    def prepare_send_tokens(self, campaign_id: str) -> dict[str, str]:
        """Создать одноразовые токены для кнопок; вернуть raw token по answer_code."""
        campaign = self.repo.get_campaign(campaign_id)
        if not campaign:
            raise LookupError("campaign_not_found")
        expires = datetime.now(UTC) + timedelta(days=TOKEN_TTL_DAYS)
        raw_by_answer: dict[str, str] = {}
        for code in CLARITY_ANSWERS:
            raw = new_action_token()
            self.repo.insert_token(
                {
                    "id": str(uuid4()),
                    "campaign_id": campaign_id,
                    "token_hash": hash_action_token(raw),
                    "answer_code": code,
                    "expires_at": expires.isoformat(),
                }
            )
            raw_by_answer[code] = raw
        return raw_by_answer

    def approve_and_mark_sent(
        self,
        *,
        campaign_id: str,
        actor_id: str | None,
        last_staff_message_at: datetime | None = None,
        do_not_contact: bool = False,
    ) -> dict[str, Any]:
        """Подтвердить отправку: проверки частоты/ночи/suppression → tokens + body."""
        campaign = self.repo.get_campaign(campaign_id)
        if not campaign:
            raise LookupError("campaign_not_found")
        case_id = str(campaign["case_id"])
        if do_not_contact or self.repo.has_suppression(case_id):
            self.repo.update_campaign(
                campaign_id,
                {"status": "cancelled", "updated_at": _now()},
            )
            return {"ok": False, "cancelled": True, "reason": "suppressed"}
        if campaign.get("status") not in ("draft", "scheduled", "approved"):
            raise ValueError(f"invalid_status:{campaign.get('status')}")
        if self.repo.count_sent_surveys(case_id) >= MAX_SURVEY_TOUCHES:
            self.repo.update_campaign(
                campaign_id,
                {"status": "cancelled", "updated_at": _now()},
            )
            return {"ok": False, "cancelled": True, "reason": "max_touches"}
        if last_staff_message_at is not None:
            age = datetime.now(UTC) - last_staff_message_at.astimezone(UTC)
            if age < timedelta(hours=MIN_HOURS_BETWEEN_SERVICE):
                return {"ok": False, "deferred": True, "reason": "active_staff_dialog"}
        # Ночной тихий час — для автопланировщика; ручной approve сотрудника разрешён.

        tokens = self.prepare_send_tokens(campaign_id)
        self.repo.update_campaign(
            campaign_id,
            {
                "status": "sent",
                "sent_at": _now(),
                "staff_approved_by": actor_id,
                "updated_at": _now(),
            },
        )
        return {
            "ok": True,
            "campaign_id": campaign_id,
            "body": campaign.get("body") or CLARITY_BODY,
            "tokens": tokens,
            "labels": dict(CLARITY_ANSWERS),
        }

    def handle_action_token(self, raw_token: str) -> dict[str, Any]:
        """Обработать callback MAX; идемпотентно."""
        token_hash = hash_action_token(raw_token)
        row = self.repo.get_token_by_hash(token_hash)
        if not row:
            raise LookupError("invalid_token")
        campaign_id = str(row["campaign_id"])
        campaign = self.repo.get_campaign(campaign_id)
        if not campaign:
            raise LookupError("campaign_missing")
        answer = str(row["answer_code"])
        expires = datetime.fromisoformat(str(row["expires_at"]).replace("Z", "+00:00"))
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=UTC)
        if expires < datetime.now(UTC):
            raise PermissionError("expired")

        existing = self.repo.get_response(campaign_id, "clarity")
        if existing or row.get("used_at"):
            return {
                "ok": True,
                "idempotent": True,
                "answer_code": existing.get("answer_code") if existing else answer,
                "case_id": campaign["case_id"],
                "text": _ack_text(answer),
            }

        now = _now()
        self.repo.insert_response(
            {
                "id": str(uuid4()),
                "campaign_id": campaign_id,
                "question_code": "clarity",
                "answer_code": answer,
                "channel": "max",
                "submitted_at": now,
                "confirmation_method": "max_callback",
                "token_id": row["id"],
            }
        )
        self.repo.mark_token_used(str(row["id"]), used_at=now)
        self.repo.update_campaign(
            campaign_id,
            {"status": "completed", "completed_at": now, "updated_at": now},
        )
        side = self._apply_clarity_answer(
            case_id=str(campaign["case_id"]),
            diagnostic_result_id=campaign.get("diagnostic_result_id"),
            answer=answer,
            campaign=campaign,
        )
        return {
            "ok": True,
            "idempotent": False,
            "answer_code": answer,
            "case_id": campaign["case_id"],
            "text": _ack_text(answer),
            "side_effects": side,
        }

    def _apply_clarity_answer(
        self,
        *,
        case_id: str,
        diagnostic_result_id: str | None,
        answer: str,
        campaign: dict[str, Any],
    ) -> dict[str, Any]:
        effects: dict[str, Any] = {"answer": answer}
        if answer == "clear":
            self.feedback.patch(
                case_id,
                {"feedback_status": "understood", "clarity_score": 3},
            )
            # first_step draft через 10 дней (ещё не шлём)
            when = datetime.now(UTC) + timedelta(days=FIRST_STEP_DELAY_DAYS)
            when = next_daytime_msk(when)
            self.repo.insert_campaign(
                {
                    "id": str(uuid4()),
                    "case_id": case_id,
                    "diagnostic_result_id": diagnostic_result_id,
                    "survey_type": "first_step",
                    "channel": "max",
                    "status": "draft",
                    "scheduled_at": when.isoformat(),
                    "template_version": "survey-first-step-v1",
                    "body": "Получилось ли выполнить первый шаг из плана действий?",
                    "touch_index": 1,
                    "updated_at": _now(),
                }
            )
            effects["first_step_draft"] = True
        elif answer in ("needs_help", "question"):
            self.feedback.patch(
                case_id,
                {
                    "feedback_status": "need_help" if answer == "needs_help" else "has_question",
                },
            )
            cancelled = self.repo.cancel_open_campaigns(
                case_id,
                except_id=str(campaign["id"]),
            )
            effects["cancelled_campaigns"] = cancelled
            effects["requires_contact"] = True
            effects["priority"] = "high" if answer == "question" else "normal"
        elif answer == "not_viewed":
            touch = int(campaign.get("touch_index") or 1)
            if touch >= 2:
                self.feedback.patch(case_id, {"feedback_status": "nav_sent"})
                effects["no_more_retries"] = True
            else:
                when = datetime.now(UTC) + timedelta(days=NOT_VIEWED_RETRY_DAYS)
                when = next_daytime_msk(when)
                self.repo.insert_campaign(
                    {
                        "id": str(uuid4()),
                        "case_id": case_id,
                        "diagnostic_result_id": diagnostic_result_id,
                        "survey_type": "clarity",
                        "channel": "max",
                        "status": "draft",
                        "scheduled_at": when.isoformat(),
                        "template_version": TEMPLATE_VERSION,
                        "body": CLARITY_BODY,
                        "touch_index": touch + 1,
                        "updated_at": _now(),
                    }
                )
                effects["retry_scheduled"] = True
        return effects


def _ack_text(answer: str) -> str:
    if answer == "clear":
        return (
            "Спасибо! Рады, что план понятен. "
            "Если понадобится помощь с первым шагом — напишите в этот чат."
        )
    if answer == "needs_help":
        return (
            "Спасибо, что сказали. Передаём сотруднику — "
            "разберём план спокойно и уточним первый шаг."
        )
    if answer == "question":
        return (
            "Спасибо. Сотрудник посмотрит документ и ответит по вашему вопросу. "
            "Сканы и персональные данные в чат, пожалуйста, не отправляйте."
        )
    if answer == "not_viewed":
        return (
            "Хорошо. Когда откроете результат в кабинете, напишите — "
            "или ответьте на следующее короткое напоминание."
        )
    return "Ответ принят. Спасибо!"


def _now() -> str:
    return datetime.now(UTC).isoformat()
