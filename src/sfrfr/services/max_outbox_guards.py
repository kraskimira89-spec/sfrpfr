"""Охрана outbox/доставки MAX для SFRFR-110 (чистые функции, без БД).

Фиксирует риски из case_chat_delivery: re-enqueue attachments, pre-send
актуальность, частичный сбой после send, семантика delivered.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any


class SendPersistOutcome(StrEnum):
    SENT_AND_RECORDED = "sent_and_recorded"
    UNKNOWN_AFTER_ACCEPT = "unknown_after_transport_accept"
    FAILED_BEFORE_OR_AT_SEND = "failed_before_or_at_send"
    PARTIAL_CASE_MESSAGE_UPDATE = "partial_case_message_update"


class DeliveredAtSemantics(StrEnum):
    """Поле delivered_at в воркере сейчас = момент после возврата send_message."""

    TRANSPORT_ACCEPTED_OR_HTTP_OK = "transport_return_time_not_read_receipt"
    NOT_CLIENT_READ = "not_proof_of_read"
    NOT_CLIENT_ACCEPTANCE = "not_proof_of_acceptance"


def delivered_at_means() -> dict[str, str]:
    return {
        "field": "case_messages.delivered_at / outbox sent_at",
        "semantics": DeliveredAtSemantics.TRANSPORT_ACCEPTED_OR_HTTP_OK.value,
        "not_read": DeliveredAtSemantics.NOT_CLIENT_READ.value,
        "not_acceptance": DeliveredAtSemantics.NOT_CLIENT_ACCEPTANCE.value,
        "max_client": "MaxBotClient.send_message → HTTP raise_for_status; "
        "не проверяет read/delivery receipt",
    }


def classify_send_persist_outcome(
    *,
    transport_accepted: bool,
    outbox_status_saved: bool,
    case_messages_updated: bool,
) -> SendPersistOutcome:
    """Исход после пары send + записи (см. риски §9.2)."""
    if not transport_accepted:
        return SendPersistOutcome.FAILED_BEFORE_OR_AT_SEND
    if transport_accepted and not outbox_status_saved:
        return SendPersistOutcome.UNKNOWN_AFTER_ACCEPT
    if transport_accepted and outbox_status_saved and not case_messages_updated:
        return SendPersistOutcome.PARTIAL_CASE_MESSAGE_UPDATE
    return SendPersistOutcome.SENT_AND_RECORDED


def may_blind_retry_after_unknown_accept() -> bool:
    """Слепой повтор при unknown_after_transport_accept запрещён без сверки."""
    return False


def reenqueue_attachments_safe(
    *,
    existing_body: str,
    new_body: str,
    new_attachments: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    """Повтор enqueue с тем же message_id: нельзя вешать новые кнопки на старый текст.

    Текущий enqueue_max_delivery обновляет attachments при pending, не трогая body.
    """
    same_text = (existing_body or "").strip() == (new_body or "").strip()
    if new_attachments and not same_text:
        return {
            "allow_attachment_update": False,
            "reason": "attachments_would_attach_to_stale_or_different_body",
        }
    return {"allow_attachment_update": True, "reason": "ok"}


def pre_send_still_allowed(
    *,
    cancelled: bool = False,
    superseded: bool = False,
    offer_refused_after_enqueue: bool = False,
    is_offer_message: bool = False,
    recipient_access_ok: bool = True,
    result_stale: bool = False,
) -> dict[str, Any]:
    """Адресная проверка перед фактической отправкой из outbox."""
    if not recipient_access_ok:
        return {"send": False, "reason": "no_recipient_access"}
    if cancelled:
        return {"send": False, "reason": "cancelled"}
    if superseded:
        return {"send": False, "reason": "superseded"}
    if result_stale:
        return {"send": False, "reason": "result_stale"}
    if is_offer_message and offer_refused_after_enqueue:
        return {"send": False, "reason": "offer_refused_after_enqueue"}
    return {"send": True, "reason": "ok"}


def concurrent_claim_required_for_outbox_workers() -> bool:
    """В process_pending_outbox нет атомарного claim — нужна инфраструктурная защита."""
    return True


def direct_send_bypasses_outbox() -> tuple[str, ...]:
    return (
        "mirror_staff_message_to_max.fallback_direct",
        "notify_client_new_chat_message.direct",
        "llm_chat.reply_to_free_text.direct_send",
        "channel_review.direct",
        "pay_link / invoice notify paths",
    )
