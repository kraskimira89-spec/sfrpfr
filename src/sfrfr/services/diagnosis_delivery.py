"""Безопасная выдача PDF: event-driven триггеры 1–4 (ТЗ-28 + ТЗ-30).

published ≠ sent ≠ opened. Система готовит draft — сотрудник подтверждает.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from sfrfr.core.config import get_settings
from sfrfr.db.diagnosis_delivery_repository import DiagnosisDeliveryRepository
from sfrfr.db.diagnosis_feedback_repository import DiagnosisFeedbackRepository
from sfrfr.services.contact_policy import (
    can_contact,
    idempotency_notification,
    looks_like_bot_user_agent,
    next_daytime_window,
)

logger = logging.getLogger(__name__)

TEMPLATE_VERSION = "result_ready_v1"
SHARE_TTL_HOURS = 72
UNREAD_DELAY_HOURS = 72
MAX_VIEWS = 3
MAX_UNREAD_REMINDERS = 1

RESULT_READY_SUBJECT = "Диагностика документов готова — доступ в личном кабинете"
RESULT_UNREAD_SUBJECT = "Напоминание: результат диагностики доступен в кабинете"

_FORBIDDEN_MARKERS = (
    "снилс",
    "snils",
    "серия паспорта",
    "номер паспорта",
    "passport no",
    "илс №",
    "сумма пенсии",
    "прибавка к пенсии",
)

STAFF_TASK_PUBLISH = "Проверить и отправить уведомление о готовом результате"


def hash_share_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def new_share_token() -> str:
    # ~256 bit entropy
    return secrets.token_urlsafe(32)


def assert_safe_notify_text(text: str) -> None:
    low = (text or "").lower()
    for marker in _FORBIDDEN_MARKERS:
        if marker in low:
            raise ValueError(f"forbidden_marker:{marker}")


def build_result_ready_body(*, secure_link: str, cabinet_url: str) -> str:
    body = (
        "Здравствуйте!\n\n"
        "Диагностика документов по вашему обращению подготовлена. В ней указано, "
        "какие документы были проверены, какие вопросы требуют уточнения "
        "и какие действия можно выполнить дальше.\n\n"
        f"Откройте результат в защищённом личном кабинете:\n{secure_link}\n\n"
        "В целях безопасности не пересылайте выписку ИЛС, трудовую книжку, "
        "паспортные данные и другие документы по электронной почте или в открытые чаты.\n\n"
        "Решение о назначении или перерасчёте пенсии принимает СФР.\n\n"
        "С уважением,\n"
        "ООО «Под присмотром» / «Проверка стажа»\n"
        f"{cabinet_url.rstrip('/')}/"
    )
    assert_safe_notify_text(body)
    return body


def build_result_unread_body(*, secure_link: str) -> str:
    body = (
        "Здравствуйте!\n\n"
        "Напоминаем: результат диагностики доступен в защищённом личном кабинете.\n\n"
        f"{secure_link}\n\n"
        "Если возникла сложность со входом, ответьте на это письмо или напишите в MAX — "
        "подскажем порядок доступа.\n\n"
        "Это сервисное сообщение по вашему обращению. "
        "Для безопасности документы по e-mail не направляйте."
    )
    assert_safe_notify_text(body)
    return body


def build_max_result_ready(*, secure_link: str) -> str:
    body = (
        "Диагностика готова и доступна в защищённом кабинете.\n"
        f"{secure_link}\n\n"
        "После ознакомления напишите одним сообщением:\n"
        "1 — всё понятно\n"
        "2 — нужна помощь разобраться с планом\n"
        "3 — есть вопрос по документу"
    )
    assert_safe_notify_text(body)
    return body


def public_share_url(token: str) -> str:
    settings = get_settings()
    api = (settings.public_base_url or "").rstrip("/")
    return f"{api}/api/portal/diag-share/{token}"


class DiagnosisDeliveryService:
    def __init__(
        self,
        repo: DiagnosisDeliveryRepository | None = None,
        feedback: DiagnosisFeedbackRepository | None = None,
    ) -> None:
        self.repo = repo or DiagnosisDeliveryRepository()
        self.feedback = feedback or DiagnosisFeedbackRepository()

    def publish(
        self,
        *,
        case_id: str,
        document_id: str,
        actor_id: str | None,
        channels: list[str] | None = None,
        checksum: str | None = None,
        do_not_contact: bool = False,
        pd_consent_revoked: bool = False,
        case_archived: bool = False,
    ) -> dict[str, Any]:
        """Триггер 1: result → published + secure link + draft result_ready (idempotent)."""
        channels = channels or ["email", "max"]
        if not checksum:
            checksum = f"doc:{document_id}"
        if not actor_id:
            raise ValueError("reviewed_by_required")

        for ch in channels:
            decision = can_contact(
                message_type="service",
                channel=ch if ch in ("email", "max") else "email",  # type: ignore[arg-type]
                do_not_contact=do_not_contact,
                pd_consent_revoked=pd_consent_revoked,
                case_archived=case_archived,
            )
            if not decision.allowed:
                raise PermissionError(decision.reason)

        existing = self.repo.get_published_for_case(case_id)
        if existing:
            # Также закрываем delivered, если переиздаём
            self.repo.update_result(
                str(existing["id"]),
                {
                    "status": "revoked",
                    "revoked_at": _now(),
                    "updated_at": _now(),
                },
            )

        result = self.repo.insert_result(
            {
                "id": str(uuid4()),
                "case_id": case_id,
                "document_id": document_id,
                "status": "published",
                "version": 1,
                "checksum": checksum,
                "reviewed_by": actor_id,
                "published_at": _now(),
                "updated_at": _now(),
            }
        )
        result_id = str(result["id"])

        raw_token = new_share_token()
        token_hash = hash_share_token(raw_token)
        expires = datetime.now(UTC) + timedelta(hours=SHARE_TTL_HOURS)
        link = self.repo.insert_link(
            {
                "id": str(uuid4()),
                "diagnostic_result_id": result_id,
                "case_id": case_id,
                "token_hash": token_hash,
                "expires_at": expires.isoformat(),
                "max_views": MAX_VIEWS,
                "view_count": 0,
                "channel": "cabinet",
            }
        )
        share_url = public_share_url(raw_token)
        cabinet = (get_settings().cabinet_public_url or "").rstrip("/") + "/"

        jobs: list[dict[str, Any]] = []
        for channel in channels:
            if channel not in ("email", "max"):
                continue
            idem = idempotency_notification(result_id, "result_ready", version=f"{channel}-v1")
            prior = self.repo.get_job_by_idempotency(idem)
            if prior and prior.get("status") != "cancelled":
                jobs.append(prior)
                continue
            if channel == "email":
                body = build_result_ready_body(secure_link=share_url, cabinet_url=cabinet)
                subject = RESULT_READY_SUBJECT
            else:
                body = build_max_result_ready(secure_link=share_url)
                subject = None
            job = self.repo.insert_job(
                {
                    "id": str(uuid4()),
                    "case_id": case_id,
                    "diagnostic_result_id": result_id,
                    "job_type": "result_ready",
                    "channel": channel,
                    "template_version": TEMPLATE_VERSION,
                    "subject": subject,
                    "body": body,
                    "secure_share_link_id": link["id"],
                    "scheduled_at": _now(),
                    "status": "draft",
                    "requires_staff_approval": True,
                    "idempotency_key": idem,
                    "updated_at": _now(),
                }
            )
            jobs.append(job)

        self.feedback.mark_pdf_issued(case_id)
        self.feedback.patch(case_id, {"feedback_status": "nav_pending"})

        return {
            "result": result,
            "jobs": jobs,
            "share_token_once": raw_token,
            "share_url_once": share_url,
            "staff_task": STAFF_TASK_PUBLISH,
            "audit": "diagnostic_result_published",
        }

    def approve_and_send_email(
        self,
        *,
        job_id: str,
        actor_id: str | None,
        to_email: str,
        do_not_contact: bool = False,
        pd_consent_revoked: bool = False,
        active_manual_dialog_48h: bool = False,
        hard_bounce: bool = False,
    ) -> dict[str, Any]:
        """Триггер 2: draft → queued → sent (email)."""
        job = self.repo.get_job(job_id)
        if not job:
            raise LookupError("job_not_found")
        case_id = str(job["case_id"])
        since = (datetime.now(UTC) - timedelta(hours=48)).isoformat()
        decision = can_contact(
            message_type="service",
            channel="email",
            do_not_contact=do_not_contact,
            pd_consent_revoked=pd_consent_revoked,
            hard_bounce=hard_bounce,
            active_manual_dialog_48h=active_manual_dialog_48h,
            service_messages_last_48h=self.repo.count_service_sent_since(case_id, since),
        )
        if not decision.allowed:
            self.repo.update_job(
                job_id,
                {
                    "status": "cancelled",
                    "failure_reason": decision.reason,
                    "updated_at": _now(),
                },
            )
            return {"ok": False, "cancelled": True, "reason": decision.reason}
        if job.get("status") != "draft":
            raise ValueError(f"invalid_status:{job.get('status')}")
        if job.get("channel") != "email":
            raise ValueError("not_email_job")

        assert_safe_notify_text(str(job.get("body") or ""))
        self.repo.update_job(
            job_id,
            {
                "status": "queued",
                "approved_by": actor_id,
                "updated_at": _now(),
            },
        )
        from sfrfr.integrations.yandex_workspace import send_mail

        result = send_mail(
            to=to_email,
            template="custom",
            case_id=None,
            subject=str(job.get("subject") or RESULT_READY_SUBJECT),
            body=str(job.get("body") or ""),
        )
        if result.get("ok"):
            self.repo.update_job(
                job_id,
                {
                    "status": "sent",
                    "sent_at": _now(),
                    "provider_message_id": result.get("message_id") or result.get("id"),
                    "updated_at": _now(),
                },
            )
            if job.get("job_type") == "result_ready" and job.get("diagnostic_result_id"):
                self.repo.update_result(
                    str(job["diagnostic_result_id"]),
                    {"status": "delivered", "updated_at": _now()},
                )
                self.feedback.patch(case_id, {"feedback_status": "nav_sent"})
            return {"ok": True, "send": result, "job_id": job_id, "audit": "notification_sent"}

        self.repo.update_job(
            job_id,
            {
                "status": "failed",
                "failure_reason": str(
                    result.get("error") or result.get("reason") or "send_failed"
                ),
                "updated_at": _now(),
            },
        )
        return {"ok": False, "send": result, "job_id": job_id}

    def approve_max_draft(
        self,
        *,
        job_id: str,
        actor_id: str | None,
        do_not_contact: bool = False,
        pd_consent_revoked: bool = False,
        active_manual_dialog_48h: bool = False,
    ) -> dict[str, Any]:
        """Триггер 2 (MAX): draft → approved; текст сотруднику для ручной отправки."""
        job = self.repo.get_job(job_id)
        if not job:
            raise LookupError("job_not_found")
        decision = can_contact(
            message_type="service",
            channel="max",
            do_not_contact=do_not_contact,
            pd_consent_revoked=pd_consent_revoked,
            active_manual_dialog_48h=active_manual_dialog_48h,
        )
        if not decision.allowed:
            self.repo.update_job(
                job_id,
                {"status": "cancelled", "failure_reason": decision.reason, "updated_at": _now()},
            )
            return {"ok": False, "cancelled": True, "reason": decision.reason}
        if job.get("status") != "draft" or job.get("channel") != "max":
            raise ValueError("invalid_job")
        self.repo.update_job(
            job_id,
            {
                "status": "approved",
                "approved_by": actor_id,
                "updated_at": _now(),
            },
        )
        return {"ok": True, "body": job.get("body"), "job_id": job_id}

    def mark_max_sent(self, job_id: str) -> dict[str, Any]:
        job = self.repo.get_job(job_id)
        if not job:
            raise LookupError("job_not_found")
        self.repo.update_job(
            job_id,
            {"status": "sent", "sent_at": _now(), "updated_at": _now()},
        )
        if job.get("job_type") == "result_ready" and job.get("diagnostic_result_id"):
            self.repo.update_result(
                str(job["diagnostic_result_id"]),
                {"status": "delivered", "updated_at": _now()},
            )
            self.feedback.patch(str(job["case_id"]), {"feedback_status": "nav_sent"})
        return {"ok": True, "audit": "notification_sent"}

    def cancel_job(self, job_id: str) -> dict[str, Any]:
        self.repo.update_job(job_id, {"status": "cancelled", "updated_at": _now()})
        return {"ok": True}

    def cancel_pending_on_block(self, case_id: str) -> int:
        """Триггер 11: do_not_contact / consent / bounce — отменить очередь."""
        return self.repo.cancel_jobs(
            case_id,
            statuses=["draft", "approved", "queued"],
        )

    def resolve_share_token(
        self,
        raw_token: str,
        *,
        user_agent: str | None = None,
        count_as_open: bool = True,
    ) -> dict[str, Any]:
        """Триггер 3: открытие PDF → opened; отмена unread; schedule clarity +48h."""
        token_hash = hash_share_token(raw_token)
        link = self.repo.get_link_by_hash(token_hash)
        if not link:
            raise LookupError("invalid_token")
        if link.get("revoked_at"):
            raise PermissionError("revoked")
        expires = datetime.fromisoformat(str(link["expires_at"]).replace("Z", "+00:00"))
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=UTC)
        if expires < datetime.now(UTC):
            raise PermissionError("expired")
        views = int(link.get("view_count") or 0)
        max_views = int(link.get("max_views") or MAX_VIEWS)
        if views >= max_views:
            raise PermissionError("max_views")

        bot = looks_like_bot_user_agent(user_agent)
        record_open = count_as_open and not bot
        now = _now()
        link_fields: dict[str, Any] = {}
        if record_open:
            link_fields["view_count"] = views + 1
            link_fields["viewed_at"] = link.get("viewed_at") or now
            self.repo.update_link(str(link["id"]), link_fields)
        elif not bot:
            # Не считаем открытием, но ссылка валидна (например prefetch с флагом).
            pass

        case_id = str(link["case_id"])
        result_id = str(link["diagnostic_result_id"])
        result = self.repo.get_result(result_id)
        survey_campaign_id = None

        if record_open:
            self.feedback.patch(case_id, {"pdf_opened_at": now})
            self.repo.cancel_jobs(case_id, job_types=["result_unread"])
            if result and result.get("status") in ("published", "delivered", "opened"):
                self.repo.update_result(
                    result_id,
                    {"status": "opened", "updated_at": now},
                )
            try:
                from sfrfr.services.diagnosis_survey import DiagnosisSurveyService

                survey = DiagnosisSurveyService().schedule_clarity_after_open(
                    case_id=case_id,
                    diagnostic_result_id=result_id,
                )
                if survey:
                    survey_campaign_id = survey.get("id")
                    self.repo.update_result(
                        result_id,
                        {"status": "feedback_pending", "updated_at": now},
                    )
            except Exception as exc:  # noqa: BLE001
                logger.warning("survey schedule after open failed: %s", type(exc).__name__)

        return {
            "case_id": case_id,
            "document_id": (result or {}).get("document_id"),
            "diagnostic_result_id": result_id,
            "link_id": link["id"],
            "survey_campaign_id": survey_campaign_id,
            "counted_as_open": record_open,
            "bot_skipped": bot,
            "audit": "diagnostic_result_opened" if record_open else None,
        }

    def ensure_unread_reminder_draft(
        self,
        *,
        result_id: str,
        do_not_contact: bool = False,
        pd_consent_revoked: bool = False,
        active_manual_dialog_48h: bool = False,
    ) -> dict[str, Any] | None:
        """Триггер 4: result_ready sent >72h, не открыт → один draft result_unread."""
        result = self.repo.get_result(result_id)
        if not result or result.get("status") not in ("published", "delivered"):
            return None
        case_id = str(result["case_id"])
        link = self.repo.get_active_link_for_result(result_id)
        if not link or link.get("viewed_at"):
            return None

        ready_sent = [
            j
            for j in self.repo.list_jobs(case_id)
            if j.get("job_type") == "result_ready"
            and j.get("diagnostic_result_id") == result_id
            and j.get("status") == "sent"
            and j.get("sent_at")
        ]
        if not ready_sent:
            return None
        sent_at = min(
            datetime.fromisoformat(str(j["sent_at"]).replace("Z", "+00:00"))
            for j in ready_sent
        )
        if sent_at.tzinfo is None:
            sent_at = sent_at.replace(tzinfo=UTC)
        if datetime.now(UTC) - sent_at < timedelta(hours=UNREAD_DELAY_HOURS):
            return None

        unread_existing = [
            j
            for j in self.repo.list_jobs(case_id)
            if j.get("job_type") == "result_unread"
            and j.get("diagnostic_result_id") == result_id
            and j.get("status") not in ("cancelled", "skipped")
        ]
        if len(unread_existing) >= MAX_UNREAD_REMINDERS:
            return unread_existing[0]

        idem = idempotency_notification(result_id, "result_unread")
        prior = self.repo.get_job_by_idempotency(idem)
        if prior and prior.get("status") not in ("cancelled", "skipped"):
            return prior

        decision = can_contact(
            message_type="service",
            channel="email",
            do_not_contact=do_not_contact,
            pd_consent_revoked=pd_consent_revoked,
            active_manual_dialog_48h=active_manual_dialog_48h,
        )
        if not decision.allowed:
            return None

        # Нужен URL — только hash в БД; тело без нового токена: ссылка на кабинет.
        cabinet = (get_settings().cabinet_public_url or "").rstrip("/") + "/"
        body = build_result_unread_body(secure_link=cabinet)
        when = next_daytime_window()
        return self.repo.insert_job(
            {
                "id": str(uuid4()),
                "case_id": case_id,
                "diagnostic_result_id": result_id,
                "job_type": "result_unread",
                "channel": "email",
                "template_version": TEMPLATE_VERSION,
                "subject": RESULT_UNREAD_SUBJECT,
                "body": body,
                "secure_share_link_id": link.get("id"),
                "scheduled_at": when.isoformat(),
                "status": "draft",
                "requires_staff_approval": True,
                "idempotency_key": idem,
                "updated_at": _now(),
            }
        )

    def run_unread_tick(
        self,
        *,
        do_not_contact_by_case: dict[str, bool] | None = None,
    ) -> dict[str, int]:
        """Scheduler: создать draft unread для кандидатов (не автоотправка)."""
        flags = do_not_contact_by_case or {}
        stats = {"checked": 0, "created": 0, "skipped": 0}
        for result in self.repo.list_results_needing_unread_check():
            stats["checked"] += 1
            result_id = str(result["id"])
            case_id = str(result["case_id"])
            idem = idempotency_notification(result_id, "result_unread")
            prior = self.repo.get_job_by_idempotency(idem)
            if prior and prior.get("status") not in ("cancelled", "skipped"):
                stats["skipped"] += 1
                continue
            job = self.ensure_unread_reminder_draft(
                result_id=result_id,
                do_not_contact=bool(flags.get(case_id)),
            )
            if job and (not prior or prior.get("id") != job.get("id")):
                stats["created"] += 1
            elif job:
                stats["skipped"] += 1
            else:
                stats["skipped"] += 1
        return stats


def constant_time_token_eq(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


def _now() -> str:
    return datetime.now(UTC).isoformat()
