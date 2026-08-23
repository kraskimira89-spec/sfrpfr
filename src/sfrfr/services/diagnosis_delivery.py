"""Безопасная выдача PDF диагностики: publish → draft notify → staff approve (ТЗ-28)."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from sfrfr.core.config import get_settings
from sfrfr.db.diagnosis_delivery_repository import DiagnosisDeliveryRepository
from sfrfr.db.diagnosis_feedback_repository import DiagnosisFeedbackRepository

TEMPLATE_VERSION = "diag-delivery-v1"
SHARE_TTL_HOURS = 72
UNREAD_DELAY_HOURS = 72
MAX_VIEWS = 20

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


def hash_share_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def new_share_token() -> str:
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
    # Канон: без case_id в URL.
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
    ) -> dict[str, Any]:
        """Опубликовать PDF: result + share link + draft notification jobs."""
        channels = channels or ["email", "max"]
        existing = self.repo.get_published_for_case(case_id)
        if existing:
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
            if channel == "email":
                body = build_result_ready_body(secure_link=share_url, cabinet_url=cabinet)
                subject = RESULT_READY_SUBJECT
            elif channel == "max":
                body = build_max_result_ready(secure_link=share_url)
                subject = None
            else:
                continue
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
                    "updated_at": _now(),
                }
            )
            jobs.append(job)

        # Черновик напоминания на +72ч — не отправлять без approve.
        unread_at = datetime.now(UTC) + timedelta(hours=UNREAD_DELAY_HOURS)
        unread_body = build_result_unread_body(secure_link=share_url)
        unread_job = self.repo.insert_job(
            {
                "id": str(uuid4()),
                "case_id": case_id,
                "diagnostic_result_id": result_id,
                "job_type": "result_unread",
                "channel": "email",
                "template_version": TEMPLATE_VERSION,
                "subject": RESULT_UNREAD_SUBJECT,
                "body": unread_body,
                "secure_share_link_id": link["id"],
                "scheduled_at": unread_at.isoformat(),
                "status": "draft",
                "requires_staff_approval": True,
                "updated_at": _now(),
            }
        )
        jobs.append(unread_job)

        self.feedback.mark_pdf_issued(case_id)
        self.feedback.patch(case_id, {"feedback_status": "nav_pending"})

        return {
            "result": result,
            "jobs": jobs,
            # Токен отдать сотруднику один раз для проверки ссылки; в БД только hash.
            "share_token_once": raw_token,
            "share_url_once": share_url,
        }

    def approve_and_send_email(
        self,
        *,
        job_id: str,
        actor_id: str | None,
        to_email: str,
        do_not_contact: bool = False,
        pdn_revoked: bool = False,
    ) -> dict[str, Any]:
        job = self.repo.get_job(job_id)
        if not job:
            raise LookupError("job_not_found")
        if do_not_contact or pdn_revoked:
            self.repo.update_job(
                job_id,
                {
                    "status": "cancelled",
                    "failure_reason": "do_not_contact_or_pdn_revoked",
                    "updated_at": _now(),
                },
            )
            return {"ok": False, "cancelled": True, "reason": "do_not_contact_or_pdn_revoked"}
        if job.get("status") != "draft":
            raise ValueError(f"invalid_status:{job.get('status')}")
        if job.get("channel") != "email":
            raise ValueError("not_email_job")

        assert_safe_notify_text(str(job.get("body") or ""))
        from sfrfr.integrations.yandex_workspace import send_mail

        result = send_mail(
            to=to_email,
            template="custom",
            case_id=None,  # не светить case_id в шаблоне
            subject=str(job.get("subject") or RESULT_READY_SUBJECT),
            body=str(job.get("body") or ""),
        )
        if result.get("ok"):
            self.repo.update_job(
                job_id,
                {
                    "status": "sent",
                    "approved_by": actor_id,
                    "sent_at": _now(),
                    "updated_at": _now(),
                },
            )
            if job.get("job_type") == "result_ready":
                self.feedback.patch(str(job["case_id"]), {"feedback_status": "nav_sent"})
        else:
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
        return {"ok": bool(result.get("ok")), "send": result, "job_id": job_id}

    def approve_max_draft(
        self,
        *,
        job_id: str,
        actor_id: str | None,
        do_not_contact: bool = False,
    ) -> dict[str, Any]:
        """Вернуть текст для отправки сотрудником в MAX (не автопостинг без UI)."""
        job = self.repo.get_job(job_id)
        if not job:
            raise LookupError("job_not_found")
        if do_not_contact:
            self.repo.update_job(
                job_id,
                {"status": "cancelled", "updated_at": _now()},
            )
            return {"ok": False, "cancelled": True}
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
        if job.get("job_type") == "result_ready":
            self.feedback.patch(str(job["case_id"]), {"feedback_status": "nav_sent"})
        return {"ok": True}

    def cancel_job(self, job_id: str) -> dict[str, Any]:
        self.repo.update_job(job_id, {"status": "cancelled", "updated_at": _now()})
        return {"ok": True}

    def resolve_share_token(self, raw_token: str) -> dict[str, Any]:
        """Проверить токен, учесть просмотр, отменить unread-drafts."""
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

        now = _now()
        self.repo.update_link(
            str(link["id"]),
            {
                "view_count": views + 1,
                "viewed_at": link.get("viewed_at") or now,
            },
        )
        case_id = str(link["case_id"])
        self.feedback.patch(
            case_id,
            {"pdf_opened_at": now},
        )
        self.repo.cancel_jobs(case_id, job_types=["result_unread"])
        result = self.repo.get_result(str(link["diagnostic_result_id"]))
        survey_campaign_id = None
        try:
            from sfrfr.services.diagnosis_survey import DiagnosisSurveyService

            survey = DiagnosisSurveyService().schedule_clarity_after_open(
                case_id=case_id,
                diagnostic_result_id=str(link["diagnostic_result_id"]),
            )
            if survey:
                survey_campaign_id = survey.get("id")
        except Exception as exc:  # noqa: BLE001 — опрос не должен ломать выдачу PDF
            import logging

            logging.getLogger(__name__).warning(
                "survey schedule after open failed: %s", type(exc).__name__
            )
            survey_campaign_id = None
        return {
            "case_id": case_id,
            "document_id": (result or {}).get("document_id"),
            "diagnostic_result_id": link["diagnostic_result_id"],
            "link_id": link["id"],
            "survey_campaign_id": survey_campaign_id,
        }


def constant_time_token_eq(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


def _now() -> str:
    return datetime.now(UTC).isoformat()
