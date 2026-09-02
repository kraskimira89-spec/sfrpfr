"""Сервисные опросы после PDF: clarity + first_step + quality + acquaint (ТЗ-29)."""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from sfrfr.db.diagnosis_feedback_repository import DiagnosisFeedbackRepository
from sfrfr.db.diagnosis_survey_repository import DiagnosisSurveyRepository
from sfrfr.services.contact_policy import (
    idempotency_survey,
    is_quiet_hours,
    next_daytime_window,
)

TEMPLATE_VERSION = "survey-clarity-v1"
CLARITY_DELAY_HOURS = 48
ACQUAINT_DELAY_HOURS = 60  # ~2.5 суток в окне 2–3 дня
NOT_VIEWED_RETRY_DAYS = 6
FIRST_STEP_DELAY_DAYS = 10
QUALITY_DELAY_DAYS = 7  # после понятности (clarity=clear)
TOKEN_TTL_DAYS = 14
MAX_SURVEY_TOUCHES = 2  # только clarity (не acquaint / first_step / quality)
MIN_HOURS_BETWEEN_SERVICE = 48

CLARITY_ANSWERS = {
    "clear": "Всё понятно",
    "needs_help": "Нужна помощь с планом",
    "question": "Есть вопрос по документу",
    "not_viewed": "Пока не успел(а) посмотреть",
}

FIRST_STEP_ANSWERS = {
    "done": "Да, выполнил(а)",
    "blocked": "Есть сложность",
    "deferred": "Пока отложил(а)",
}

ACQUAINT_ANSWERS = {
    "yes": "Да, ознакомился(ась)",
    "not_yet": "Пока нет",
}

QUALITY_ANSWERS = {
    "good": "Всё устроило",
    "mixed": "В целом ок, есть замечания",
    "poor": "Не хватило ясности или поддержки",
}

CLARITY_BODY = (
    "Здравствуйте! Удалось ли посмотреть результат диагностики?\n"
    "Нам важно убедиться, что план действий понятен."
)

FIRST_STEP_BODY = (
    "Здравствуйте! Получилось ли выполнить первый шаг из плана действий "
    "в диагностике?"
)

ACQUAINT_BODY = (
    "Здравствуйте! Удалось ли ознакомиться с результатом диагностики "
    "в защищённом кабинете?"
)

QUALITY_BODY = (
    "Здравствуйте! Коротко: насколько удобной и понятной оказалась "
    "подготовка документов и плана? Это сервисный вопрос, не реклама."
)


def hash_action_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def new_action_token() -> str:
    return secrets.token_urlsafe(16)


def survey_email_link(raw_token: str, *, base_url: str | None = None) -> str:
    """Публичная ссылка на страницу подтверждения (не фиксирует ответ по GET)."""
    from sfrfr.core.config import get_settings

    base = (base_url or get_settings().public_base_url or "").rstrip("/")
    return f"{base}/api/portal/survey/{raw_token}"


def is_night_msk(now: datetime | None = None) -> bool:
    return is_quiet_hours(now)


def next_daytime_msk(after: datetime | None = None) -> datetime:
    return next_daytime_window(after)


def _answers_for_type(survey_type: str) -> dict[str, str]:
    if survey_type == "first_step":
        return FIRST_STEP_ANSWERS
    if survey_type == "acquaint":
        return ACQUAINT_ANSWERS
    if survey_type == "quality":
        return QUALITY_ANSWERS
    return CLARITY_ANSWERS


def _body_for_type(survey_type: str, campaign: dict[str, Any]) -> str:
    custom = str(campaign.get("body") or "").strip()
    if custom:
        return custom
    if survey_type == "first_step":
        return FIRST_STEP_BODY
    if survey_type == "acquaint":
        return ACQUAINT_BODY
    if survey_type == "quality":
        return QUALITY_BODY
    return CLARITY_BODY

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
        """Триггер после открытия — survey clarity scheduled (+48ч)."""
        if self.repo.has_suppression(case_id):
            return None
        if diagnostic_result_id:
            idem = idempotency_survey(diagnostic_result_id, "clarity")
            prior = self.repo.get_campaign_by_idempotency(idem)
            if prior and prior.get("status") not in ("cancelled", "expired"):
                self.schedule_acquaint_after_open(
                    case_id=case_id,
                    diagnostic_result_id=diagnostic_result_id,
                )
                return prior
        else:
            idem = None
        existing = [
            c
            for c in self.repo.list_campaigns(case_id)
            if c.get("survey_type") == "clarity"
            and c.get("status") in ("draft", "scheduled", "approved", "sent", "completed")
        ]
        if existing:
            self.schedule_acquaint_after_open(
                case_id=case_id,
                diagnostic_result_id=diagnostic_result_id,
            )
            return existing[0]
        if self._clarity_touch_count(case_id) >= MAX_SURVEY_TOUCHES:
            return None

        when = datetime.now(UTC) + timedelta(hours=delay_hours)
        when = next_daytime_window(when)
        row = self.repo.insert_campaign(
            {
                "id": str(uuid4()),
                "case_id": case_id,
                "diagnostic_result_id": diagnostic_result_id,
                "survey_type": "clarity",
                "channel": "max",
                "status": "scheduled",
                "scheduled_at": when.isoformat(),
                "expires_at": (when + timedelta(days=TOKEN_TTL_DAYS)).isoformat(),
                "template_version": TEMPLATE_VERSION,
                "body": CLARITY_BODY,
                "touch_index": 1,
                "idempotency_key": idem,
                "updated_at": _now(),
            }
        )
        self.schedule_acquaint_after_open(
            case_id=case_id,
            diagnostic_result_id=diagnostic_result_id,
        )
        return row

    def schedule_acquaint_after_open(
        self,
        *,
        case_id: str,
        diagnostic_result_id: str | None,
        delay_hours: int = ACQUAINT_DELAY_HOURS,
    ) -> dict[str, Any] | None:
        """Один draft-касание «ознакомились?» через ~2.5 суток, если clarity ещё без ответа."""
        if self.repo.has_suppression(case_id):
            return None
        if diagnostic_result_id:
            idem = idempotency_survey(diagnostic_result_id, "acquaint")
            prior = self.repo.get_campaign_by_idempotency(idem)
            if prior and prior.get("status") not in ("cancelled", "expired"):
                return prior
        else:
            idem = None
        existing = [
            c
            for c in self.repo.list_campaigns(case_id)
            if c.get("survey_type") == "acquaint"
            and c.get("status") in ("draft", "scheduled", "approved", "sent", "completed")
        ]
        if existing:
            return existing[0]
        # Уже ответили на clarity — не нужно
        if self._clarity_answered(case_id):
            return None

        when = datetime.now(UTC) + timedelta(hours=delay_hours)
        when = next_daytime_window(when)
        return self.repo.insert_campaign(
            {
                "id": str(uuid4()),
                "case_id": case_id,
                "diagnostic_result_id": diagnostic_result_id,
                "survey_type": "acquaint",
                "channel": "max",
                "status": "scheduled",
                "scheduled_at": when.isoformat(),
                "expires_at": (when + timedelta(days=TOKEN_TTL_DAYS)).isoformat(),
                "template_version": "survey-acquaint-v1",
                "body": ACQUAINT_BODY,
                "touch_index": 1,
                "idempotency_key": idem,
                "updated_at": _now(),
            }
        )

    def prepare_send_tokens(self, campaign_id: str) -> dict[str, str]:
        campaign = self.repo.get_campaign(campaign_id)
        if not campaign:
            raise LookupError("campaign_not_found")
        answers = _answers_for_type(str(campaign.get("survey_type") or "clarity"))
        expires = datetime.now(UTC) + timedelta(days=TOKEN_TTL_DAYS)
        raw_by_answer: dict[str, str] = {}
        for code in answers:
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
        campaign = self.repo.get_campaign(campaign_id)
        if not campaign:
            raise LookupError("campaign_not_found")
        case_id = str(campaign["case_id"])
        survey_type = str(campaign.get("survey_type") or "clarity")
        if do_not_contact or self.repo.has_suppression(case_id):
            self.repo.update_campaign(
                campaign_id,
                {"status": "cancelled", "updated_at": _now()},
            )
            return {"ok": False, "cancelled": True, "reason": "suppressed"}
        if campaign.get("status") not in ("draft", "scheduled", "approved"):
            raise ValueError(f"invalid_status:{campaign.get('status')}")
        if survey_type == "clarity" and self._clarity_touch_count(case_id) >= MAX_SURVEY_TOUCHES:
            self.repo.update_campaign(
                campaign_id,
                {"status": "cancelled", "updated_at": _now()},
            )
            return {"ok": False, "cancelled": True, "reason": "max_touches"}
        if survey_type == "acquaint" and self._clarity_answered(case_id):
            self.repo.update_campaign(
                campaign_id,
                {"status": "cancelled", "updated_at": _now()},
            )
            return {"ok": False, "cancelled": True, "reason": "clarity_already_answered"}
        if last_staff_message_at is not None:
            age = datetime.now(UTC) - last_staff_message_at.astimezone(UTC)
            if age < timedelta(hours=MIN_HOURS_BETWEEN_SERVICE):
                return {"ok": False, "deferred": True, "reason": "active_staff_dialog"}

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
        answers = _answers_for_type(survey_type)
        return {
            "ok": True,
            "campaign_id": campaign_id,
            "survey_type": survey_type,
            "body": _body_for_type(survey_type, campaign),
            "tokens": tokens,
            "labels": dict(answers),
        }

    def run_due_tick(self) -> dict[str, int]:
        """scheduled с due scheduled_at → draft (без автоотправки)."""
        stats = {"checked": 0, "promoted": 0, "skipped": 0}
        now = datetime.now(UTC)
        for row in self.repo.list_due_scheduled(now_iso=now.isoformat()):
            stats["checked"] += 1
            cid = str(row["id"])
            st = str(row.get("survey_type") or "")
            if st == "acquaint" and self._clarity_answered(str(row["case_id"])):
                self.repo.update_campaign(
                    cid, {"status": "cancelled", "updated_at": _now()}
                )
                stats["skipped"] += 1
                continue
            if row.get("status") != "scheduled":
                stats["skipped"] += 1
                continue
            self.repo.update_campaign(
                cid,
                {"status": "draft", "updated_at": _now()},
            )
            stats["promoted"] += 1
        return stats

    def handle_action_token(
        self,
        raw_token: str,
        *,
        channel: str = "max",
        confirmation_method: str = "max_callback",
    ) -> dict[str, Any]:
        token_hash = hash_action_token(raw_token)
        row = self.repo.get_token_by_hash(token_hash)
        if not row:
            raise LookupError("invalid_token")
        campaign_id = str(row["campaign_id"])
        campaign = self.repo.get_campaign(campaign_id)
        if not campaign:
            raise LookupError("campaign_missing")
        survey_type = str(campaign.get("survey_type") or "clarity")
        question_code = (
            survey_type
            if survey_type in ("first_step", "acquaint", "quality")
            else "clarity"
        )
        answer = str(row["answer_code"])
        expires = datetime.fromisoformat(str(row["expires_at"]).replace("Z", "+00:00"))
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=UTC)
        if expires < datetime.now(UTC):
            raise PermissionError("expired")

        existing = self.repo.get_response(campaign_id, question_code)
        if existing or row.get("used_at"):
            return {
                "ok": True,
                "idempotent": True,
                "answer_code": existing.get("answer_code") if existing else answer,
                "case_id": campaign["case_id"],
                "text": _ack_text(survey_type, answer),
            }

        now = _now()
        self.repo.insert_response(
            {
                "id": str(uuid4()),
                "campaign_id": campaign_id,
                "question_code": question_code,
                "answer_code": answer,
                "channel": channel if channel in ("max", "email", "web") else "max",
                "submitted_at": now,
                "confirmation_method": confirmation_method,
                "token_id": row["id"],
            }
        )
        self.repo.mark_token_used(str(row["id"]), used_at=now)
        self.repo.update_campaign(
            campaign_id,
            {"status": "completed", "completed_at": now, "updated_at": now},
        )
        if survey_type == "first_step":
            side = self._apply_first_step_answer(
                case_id=str(campaign["case_id"]),
                answer=answer,
            )
        elif survey_type == "acquaint":
            side = self._apply_acquaint_answer(
                case_id=str(campaign["case_id"]),
                diagnostic_result_id=campaign.get("diagnostic_result_id"),
                answer=answer,
            )
        elif survey_type == "quality":
            side = self._apply_quality_answer(
                case_id=str(campaign["case_id"]),
                answer=answer,
            )
        else:
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
            "text": _ack_text(survey_type, answer),
            "side_effects": side,
        }

    def _clarity_touch_count(self, case_id: str) -> int:
        return sum(
            1
            for r in self.repo.list_campaigns(case_id)
            if r.get("survey_type") == "clarity"
            and r.get("status") in ("sent", "completed", "approved")
        )

    def _clarity_answered(self, case_id: str) -> bool:
        for c in self.repo.list_campaigns(case_id):
            if c.get("survey_type") != "clarity":
                continue
            if c.get("status") == "completed":
                return True
            resp = self.repo.get_response(str(c["id"]), "clarity")
            if resp:
                return True
        return False

    def _apply_clarity_answer(
        self,
        *,
        case_id: str,
        diagnostic_result_id: str | None,
        answer: str,
        campaign: dict[str, Any],
    ) -> dict[str, Any]:
        effects: dict[str, Any] = {"answer": answer}
        # Любой ответ clarity отменяет acquaint
        for c in self.repo.list_campaigns(case_id):
            if c.get("survey_type") == "acquaint" and c.get("status") in (
                "draft",
                "scheduled",
                "approved",
            ):
                self.repo.update_campaign(
                    str(c["id"]),
                    {"status": "cancelled", "updated_at": _now()},
                )
        if answer == "clear":
            self.feedback.patch(
                case_id,
                {
                    "feedback_status": "understood",
                    "clarity_score": 3,
                    "first_plan_step_status": "pending",
                },
            )
            when = datetime.now(UTC) + timedelta(days=FIRST_STEP_DELAY_DAYS)
            when = next_daytime_window(when)
            self.repo.insert_campaign(
                {
                    "id": str(uuid4()),
                    "case_id": case_id,
                    "diagnostic_result_id": diagnostic_result_id,
                    "survey_type": "first_step",
                    "channel": "max",
                    "status": "scheduled",
                    "scheduled_at": when.isoformat(),
                    "template_version": "survey-first-step-v1",
                    "body": FIRST_STEP_BODY,
                    "touch_index": 1,
                    "idempotency_key": (
                        idempotency_survey(str(diagnostic_result_id), "first_step")
                        if diagnostic_result_id
                        else None
                    ),
                    "updated_at": _now(),
                }
            )
            effects["first_step_draft"] = True
            effects["pipeline"] = "acts_alone"
            q_when = datetime.now(UTC) + timedelta(days=QUALITY_DELAY_DAYS)
            q_when = next_daytime_window(q_when)
            existing_q = [
                c
                for c in self.repo.list_campaigns(case_id)
                if c.get("survey_type") == "quality"
                and c.get("status")
                in ("draft", "scheduled", "approved", "sent", "completed")
            ]
            if not existing_q:
                self.repo.insert_campaign(
                    {
                        "id": str(uuid4()),
                        "case_id": case_id,
                        "diagnostic_result_id": diagnostic_result_id,
                        "survey_type": "quality",
                        "channel": "max",
                        "status": "scheduled",
                        "scheduled_at": q_when.isoformat(),
                        "expires_at": (
                            q_when + timedelta(days=TOKEN_TTL_DAYS)
                        ).isoformat(),
                        "template_version": "survey-quality-v1",
                        "body": QUALITY_BODY,
                        "touch_index": 1,
                        "idempotency_key": (
                            idempotency_survey(str(diagnostic_result_id), "quality")
                            if diagnostic_result_id
                            else None
                        ),
                        "updated_at": _now(),
                    }
                )
                effects["quality_draft"] = True
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
                when = next_daytime_window(when)
                self.repo.insert_campaign(
                    {
                        "id": str(uuid4()),
                        "case_id": case_id,
                        "diagnostic_result_id": diagnostic_result_id,
                        "survey_type": "clarity",
                        "channel": "max",
                        "status": "scheduled",
                        "scheduled_at": when.isoformat(),
                        "template_version": TEMPLATE_VERSION,
                        "body": CLARITY_BODY,
                        "touch_index": touch + 1,
                        "updated_at": _now(),
                    }
                )
                effects["retry_scheduled"] = True
        return effects

    def _apply_first_step_answer(self, *, case_id: str, answer: str) -> dict[str, Any]:
        status_map = {
            "done": "done",
            "blocked": "blocked",
            "deferred": "deferred",
        }
        step = status_map.get(answer, "pending")
        patch: dict[str, Any] = {"first_plan_step_status": step}
        if answer == "blocked":
            patch["feedback_status"] = "need_help"
        self.feedback.patch(case_id, patch)
        effects: dict[str, Any] = {"first_plan_step_status": step, "pipeline": "acts_alone"}
        if answer == "blocked":
            effects["requires_contact"] = True
        return effects

    def _apply_quality_answer(self, *, case_id: str, answer: str) -> dict[str, Any]:
        match_map = {"good": "yes", "mixed": "partial", "poor": "no"}
        patch: dict[str, Any] = {
            "expectation_match": match_map.get(answer),
            "feedback_status": "survey_done",
        }
        if answer == "poor":
            patch["feedback_status"] = "need_help"
        self.feedback.patch(case_id, patch)
        effects: dict[str, Any] = {
            "expectation_match": patch["expectation_match"],
            "answer": answer,
        }
        if answer in ("mixed", "poor"):
            effects["requires_contact"] = True
            if answer == "poor":
                effects["priority"] = "normal"
        return effects

    def _apply_acquaint_answer(
        self,
        *,
        case_id: str,
        diagnostic_result_id: str | None,
        answer: str,
    ) -> dict[str, Any]:
        effects: dict[str, Any] = {"answer": answer}
        if answer == "yes":
            # Подтолкнуть к clarity, если ещё нет sent/completed
            has_clarity = any(
                c.get("survey_type") == "clarity"
                and c.get("status") in ("draft", "scheduled", "approved", "sent", "completed")
                for c in self.repo.list_campaigns(case_id)
            )
            if not has_clarity:
                self.schedule_clarity_after_open(
                    case_id=case_id,
                    diagnostic_result_id=diagnostic_result_id,
                    delay_hours=0,
                )
                effects["clarity_scheduled"] = True
            else:
                # Promote due clarity to draft if still scheduled
                for c in self.repo.list_campaigns(case_id):
                    if c.get("survey_type") == "clarity" and c.get("status") == "scheduled":
                        self.repo.update_campaign(
                            str(c["id"]),
                            {"status": "draft", "updated_at": _now()},
                        )
                        effects["clarity_promoted"] = True
        return effects


def _ack_text(survey_type: str, answer: str) -> str:
    if survey_type == "first_step":
        if answer == "done":
            return (
                "Спасибо! Если появится ответ СФР или новые документы — "
                "загрузите в защищённый кабинет."
            )
        if answer == "blocked":
            return (
                "Спасибо, что сказали. Передаём сотруднику — уточним, что мешает, "
                "без обещания перерасчёта."
            )
        if answer == "deferred":
            return (
                "Хорошо. Когда будет удобно вернуться к плану — напишите в этот чат."
            )
        return "Ответ принят. Спасибо!"
    if survey_type == "quality":
        if answer == "good":
            return "Спасибо за оценку. Рады, что было удобно."
        if answer == "mixed":
            return (
                "Спасибо. Передадим замечание сотруднику — "
                "уточним, что улучшить в плане."
            )
        if answer == "poor":
            return (
                "Спасибо, что сказали. Сотрудник свяжется и разберёт, "
                "где не хватило ясности — без обещания перерасчёта."
            )
        return "Ответ принят. Спасибо!"
    if survey_type == "acquaint":
        if answer == "yes":
            return (
                "Спасибо! Скоро коротко спросим, понятен ли план действий."
            )
        return (
            "Хорошо. Когда откроете результат в кабинете — ответьте на следующее "
            "сообщение или напишите в чат."
        )
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
