"""Обработка webhook доставки e-mail: идемпотентность + переходы (ТЗ-31).

delivered ≠ PDF opened. opened/click e-mail — только аналитика.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from sfrfr.db.email_delivery_repository import EmailDeliveryRepository
from sfrfr.services.email_delivery_normalize import NormalizedDeliveryEvent, new_event_id

logger = logging.getLogger(__name__)

# Статусы job, которые меняет webhook (не PDF)
_JOB_STATUS = {
    "accepted": "accepted",
    "delivered": "delivered",
    "deferred": "deferred",
    "hard_bounce": "hard_bounce",
    "soft_bounce": "soft_bounce",
    "failed": "failed",
}


class EmailDeliveryWebhookService:
    def __init__(self, repo: EmailDeliveryRepository | None = None) -> None:
        self.repo = repo or EmailDeliveryRepository()

    def process_events(
        self,
        events: list[NormalizedDeliveryEvent],
    ) -> dict[str, Any]:
        """Сохранить события и применить переходы. Всегда идемпотентно."""
        stats = {
            "received": len(events),
            "stored": 0,
            "duplicates": 0,
            "unmatched": 0,
            "transitions": 0,
            "staff_tasks": 0,
        }
        for event in events:
            if self.repo.fingerprint_exists(event.event_fingerprint):
                stats["duplicates"] += 1
                continue

            job = self.repo.get_job_by_provider_message_id(event.provider_message_id)
            unmatched = job is None
            if unmatched:
                stats["unmatched"] += 1

            self.repo.insert_event(
                {
                    "id": new_event_id(),
                    "notification_job_id": job["id"] if job else None,
                    "provider": event.provider,
                    "provider_event_id": event.provider_event_id,
                    "provider_message_id": event.provider_message_id,
                    "event_type": event.event_type,
                    "occurred_at": event.occurred_at.isoformat(),
                    "received_at": datetime.now(UTC).isoformat(),
                    "severity": event.severity,
                    "error_code": event.error_code,
                    "error_category": event.error_category,
                    "event_fingerprint": event.event_fingerprint,
                    "payload_redacted": event.payload_redacted,
                    "unmatched": unmatched,
                }
            )
            stats["stored"] += 1

            if not job:
                logger.warning(
                    "email_webhook unmatched message_id provider=%s",
                    event.provider,
                )
                continue

            applied = self.apply_delivery_transition(job, event)
            if applied.get("transitioned"):
                stats["transitions"] += 1
            if applied.get("staff_task"):
                stats["staff_tasks"] += 1

        return {"ok": True, **stats}

    def apply_delivery_transition(
        self,
        job: dict[str, Any],
        event: NormalizedDeliveryEvent,
    ) -> dict[str, Any]:
        """Обновить job / стоп-лист. Не трогает diagnostic_result.opened."""
        out: dict[str, Any] = {"transitioned": False, "staff_task": False}
        et = event.event_type
        now = datetime.now(UTC).isoformat()
        job_id = str(job["id"])
        contact_key = job.get("recipient_contact_key")
        case_id = str(job.get("case_id") or "")

        if et in _JOB_STATUS:
            fields: dict[str, Any] = {
                "status": _JOB_STATUS[et],
                "updated_at": now,
            }
            if et == "accepted":
                fields["accepted_at"] = now
            elif et == "delivered":
                fields["delivered_at"] = now
            elif et in ("failed", "hard_bounce", "soft_bounce"):
                fields["failed_at"] = now
                fields["error_code"] = event.error_code
                fields["error_category"] = event.error_category or et
            elif et == "deferred":
                fields["error_category"] = "deferred"
                fields["retry_count"] = int(job.get("retry_count") or 0) + 1
            self.repo.update_job(job_id, fields)
            out["transitioned"] = True

        # analytics only — не меняем PDF
        if et in ("opened", "clicked"):
            return out

        if et == "deferred" or et == "soft_bounce":
            if contact_key:
                self.repo.upsert_contact_status(
                    contact_key=str(contact_key),
                    channel="email",
                    status="temporary_problem",
                    reason=event.error_category or et,
                )
            # retry backoff — только метка; воркер P1
            out["retry_suggested"] = [15, 60, 240]
            return out

        if et == "hard_bounce":
            if contact_key:
                self.repo.upsert_contact_status(
                    contact_key=str(contact_key),
                    channel="email",
                    status="hard_bounce",
                    reason=event.error_category or "hard_bounce",
                )
                self.repo.cancel_pending_email_jobs(
                    contact_key=str(contact_key),
                    case_id=case_id or None,
                )
            out["staff_task"] = True
            out["staff_task_title"] = "Проверьте e-mail: постоянная ошибка доставки"
            self._try_staff_task(case_id, out["staff_task_title"])
            return out

        if et == "complained":
            if contact_key:
                self.repo.upsert_contact_status(
                    contact_key=str(contact_key),
                    channel="email",
                    status="complained",
                    reason="spam_complaint",
                )
                self.repo.cancel_pending_email_jobs(
                    contact_key=str(contact_key),
                    case_id=case_id or None,
                )
            out["staff_task"] = True
            out["staff_task_title"] = "Жалоба на e-mail: остановить необязательные сообщения"
            self._try_staff_task(case_id, out["staff_task_title"], security=True)
            return out

        if et == "unsubscribed":
            if contact_key:
                self.repo.upsert_contact_status(
                    contact_key=str(contact_key),
                    channel="email",
                    status="unsubscribed",
                    reason="provider_webhook",
                )
                try:
                    from sfrfr.db.marketing_consent_repository import MarketingConsentRepository

                    MarketingConsentRepository().record_event(
                        contact_key=str(contact_key),
                        channel="email",
                        status="revoked",
                        source="provider_webhook",
                        consent_text_version="webhook-unsub-v1",
                        case_id=case_id or None,
                        suppression_reason="unsubscribe",
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.warning("marketing revoke on unsub failed: %s", type(exc).__name__)
            return out

        return out

    def _try_staff_task(
        self,
        case_id: str,
        title: str,
        *,
        security: bool = False,
    ) -> None:
        if not case_id:
            return
        try:
            from sfrfr.db.case_repository import CaseRepository
            from sfrfr.services.finance_automation import ensure_staff_task

            repo = CaseRepository()
            ensure_staff_task(
                repo,
                case_id,
                title=title,
                item_type="task",
                due_at=None,
                actor_id=None,
                note="security" if security else "delivery",
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("staff_task from webhook failed: %s", type(exc).__name__)
