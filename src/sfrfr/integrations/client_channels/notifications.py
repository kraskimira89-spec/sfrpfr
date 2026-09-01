"""CTA-ссылки и рассылка уведомлений с учётом preferred_channel (ТЗ-09)."""

from __future__ import annotations

import logging
from typing import Any

from sfrfr.core.config import get_settings
from sfrfr.models.case_status import status_label_ru

logger = logging.getLogger("sfrfr.notifications")

# Клиентские этапы: не спамим на каждый промежуточный OCR-шаг.
CLIENT_NOTIFY_STATUSES = frozenset(
    {
        "documents_received",
        "audited",
        "draft_ready",
        "human_review",
        "completed",
        "failed",
    }
)


def cabinet_case_url(case_id: str | None = None, *, view: str | None = None) -> str:
    """Канонический deep-link кабинета: /cases/{id}[?view=…]."""
    settings = get_settings()
    base = settings.cabinet_public_url.rstrip("/")
    if not case_id:
        return f"{base}/"
    url = f"{base}/cases/{case_id}"
    if view:
        url = f"{url}?view={view}"
    return url


def notification_channel_links(
    *,
    preferred_channel: str | None,
    max_linked: bool,
    case_id: str | None = None,
) -> dict[str, Any]:
    """
    CTA уведомления: кабинет только на сайте.
    preferred_channel / max_linked сохранены для совместимости API (на порядок ссылок
    мини-приложения больше не влияют).
    """
    _ = preferred_channel, max_linked
    cabinet = cabinet_case_url(case_id)
    links = [
        {
            "channel": "web_cabinet",
            "label": "Кабинет на сайте",
            "url": cabinet,
            "copy": "Документы — только в кабинете на сайте; переписка — один чат в кабинете и MAX",
        },
    ]
    preferred = preferred_channel or "unset"
    return {
        "preferred_channel": preferred,
        "links": links,
        "note": "Клиентский кабинет — только сайт; чат по делу общий в MAX и кабинете",
        "warning": (
            "Мы готовим документы и план — подаёте через СФР или Госуслуги вы сами. "
            "Решение принимает СФР. Результат не гарантирован."
        ),
    }


def format_status_change_message(
    *,
    status_value: str,
    preferred_channel: str | None,
    max_linked: bool,
    case_id: str,
) -> str:
    """Нейтральный текст общего чата без номера дела, ПДн и ссылок."""
    label = status_label_ru(status_value)
    _ = preferred_channel, max_linked, case_id
    return (
        f"Статус вашего дела обновился: {label}.\n\n"
        "Откройте единый чат по делу в кабинете или MAX."
    )


REVIEW_ASK_AUDIT_ACTION = "max_review_ask_sent"


def format_soft_review_ask_message(*, review_url: str | None = None) -> str:
    """
    Мягкая просьба об отзыве после завершённой услуги (ТЗ-19).
    Без давления, без «поставьте 5», без серии напоминаний.
    Кнопки: MAX review_flow.soft_ask_attachments().
    """
    from sfrfr.integrations.max.review_flow import format_soft_ask_with_flow

    _ = review_url  # URL в кнопках; текст общий
    return format_soft_ask_with_flow()


def _review_ask_already_sent(case_id: str) -> bool:
    try:
        from sfrfr.db.session import get_supabase_client

        rows = (
            get_supabase_client()
            .table("access_audit")
            .select("id")
            .eq("case_id", case_id)
            .eq("action", REVIEW_ASK_AUDIT_ACTION)
            .limit(1)
            .execute()
            .data
            or []
        )
        return bool(rows)
    except Exception as exc:  # noqa: BLE001
        logger.warning("review_ask audit lookup failed case=%s: %s", case_id[:8], exc)
        return False


def _mark_review_ask_sent(case_id: str) -> None:
    try:
        from sfrfr.db.session import get_supabase_client

        get_supabase_client().table("access_audit").insert(
            {
                "case_id": case_id,
                "actor_id": None,
                "action": REVIEW_ASK_AUDIT_ACTION,
            }
        ).execute()
    except Exception as exc:  # noqa: BLE001
        logger.warning("review_ask audit write failed case=%s: %s", case_id[:8], exc)


def maybe_send_soft_review_ask(
    *,
    case_id: str,
    status_value: str,
    client: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Один раз после `completed`: мягкая просьба в MAX.
    Без авто-серии напоминаний (повтор только вручную оператором по ТЗ-19).
    """
    if status_value != "completed":
        return {"ok": True, "skipped": True, "reason": "not_completed"}

    client = client or {}
    max_user_id = client.get("max_user_id")
    if not max_user_id:
        return {"ok": True, "skipped": True, "reason": "no_max_user"}

    if _review_ask_already_sent(case_id):
        return {"ok": True, "skipped": True, "reason": "already_sent"}

    text = format_soft_review_ask_message()
    result: dict[str, Any] = {
        "ok": True,
        "skipped": False,
        "max_queued": False,
        "max_sent": False,
        "text": text,
    }
    try:
        from sfrfr.db.session import get_supabase_client
        from sfrfr.integrations.max.review_flow import soft_ask_attachments
        from sfrfr.services.case_chat_delivery import (
            enqueue_max_delivery,
            process_pending_outbox,
        )

        inserted = (
            get_supabase_client()
            .table("case_messages")
            .insert(
                {
                    "case_id": case_id,
                    "author_kind": "system",
                    "author_user_id": None,
                    "body": text,
                    "channel_origin": "bot",
                }
            )
            .execute()
        )
        message_row = (inserted.data or [{}])[0]
        message_id = str(message_row.get("id") or "").strip() or None
        queued = enqueue_max_delivery(
            case_id=case_id,
            message_id=message_id,
            max_user_id=str(max_user_id),
            body=text,
            attachments=soft_ask_attachments(),
        )
        result["max_queued"] = queued
        if queued:
            process_pending_outbox(limit=5)
            result["max_sent"] = bool(
                (
                    get_supabase_client()
                    .table("case_messages")
                    .select("delivered_at")
                    .eq("id", message_id)
                    .limit(1)
                    .execute()
                    .data
                    or [{}]
                )[0].get("delivered_at")
            )
        if queued:
            _mark_review_ask_sent(case_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("review_ask MAX failed case=%s: %s", case_id[:8], exc)
        result["ok"] = False
        result["error"] = str(exc)
    return result


def notify_case_status_change(
    *,
    case_id: str,
    status_value: str,
    previous_status: str | None = None,
    client: dict[str, Any] | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """
    Уведомить клиента о смене статуса: одно системное сообщение общего чата.
    Если MAX привязан, та же запись отправляется в его диалог без отдельного дубля.
    Email SMTP пока нет — фиксируем intent в результате (и в audit вызывающей стороны).
    После `completed` — одно мягкое приглашение к отзыву (без серии напоминаний).
    """
    if not force and status_value not in CLIENT_NOTIFY_STATUSES:
        return {"ok": True, "skipped": True, "reason": "status_not_client_facing"}
    if previous_status is not None and previous_status == status_value:
        return {"ok": True, "skipped": True, "reason": "unchanged"}

    client = client or {}
    max_user_id = client.get("max_user_id")
    preferred = client.get("preferred_channel") or "unset"
    max_linked = bool(max_user_id)
    text = format_status_change_message(
        status_value=status_value,
        preferred_channel=preferred,
        max_linked=max_linked,
        case_id=case_id,
    )
    result: dict[str, Any] = {
        "ok": True,
        "status": status_value,
        "preferred_channel": preferred,
        "max_queued": False,
        "max_sent": False,
        "case_message": False,
        "email_queued": False,
        "text": text,
        "review_ask": None,
    }

    # Системное сообщение в чате дела (видно в кабинете и MAX).
    message_id: str | None = None
    try:
        from sfrfr.db.session import get_supabase_client

        message_result = (
            get_supabase_client()
            .table("case_messages")
            .insert(
                {
                    "case_id": case_id,
                    "author_kind": "system",
                    "author_user_id": None,
                    "body": text,
                    "channel_origin": "bot",
                }
            )
            .execute()
        )
        message_id = str((message_result.data or [{}])[0].get("id") or "").strip() or None
        result["case_message"] = True
    except Exception as exc:  # noqa: BLE001 — уведомление не должно ломать смену статуса
        logger.warning("status notify case_message failed case=%s: %s", case_id[:8], exc)

    if max_user_id and message_id:
        try:
            from sfrfr.services.case_chat_delivery import (
                enqueue_max_delivery,
                process_pending_outbox,
            )

            queued = enqueue_max_delivery(
                case_id=case_id,
                message_id=message_id,
                max_user_id=str(max_user_id),
                body=text,
            )
            result["max_queued"] = queued
            if queued:
                process_pending_outbox(limit=5)
                result["max_sent"] = bool(
                    (
                        get_supabase_client()
                        .table("case_messages")
                        .select("delivered_at")
                        .eq("id", message_id)
                        .limit(1)
                        .execute()
                        .data
                        or [{}]
                    )[0].get("delivered_at")
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("status notify MAX failed case=%s: %s", case_id[:8], exc)

    email = client.get("email")
    if email:
        # SMTP не подключён: intent для будущей почтовой рассылки с теми же CTA.
        result["email_queued"] = True
        result["email_to"] = email
        logger.info(
            "status notify email intent case=%s to=%s preferred=%s",
            case_id[:8],
            email,
            preferred,
        )

    if status_value == "completed":
        result["review_ask"] = maybe_send_soft_review_ask(
            case_id=case_id,
            status_value=status_value,
            client=client,
        )
        # Сдвиг сделки amo на «Отзыв запрошен» (и задача-напоминание).
        try:
            from sfrfr.db.session import get_supabase_client
            from sfrfr.integrations.amocrm.sync import persist_crm_external_id, push_case_to_amocrm

            row = (
                get_supabase_client()
                .table("cases")
                .select(
                    "id, b2c_status, pipeline_status, crm_external_id, "
                    "clients(full_name, phone, email, preferred_channel)"
                )
                .eq("id", case_id)
                .limit(1)
                .execute()
            )
            case_row = (row.data or [None])[0]
            if case_row:
                amo = push_case_to_amocrm(case_row, task="review_ask")
                result["amocrm_review_stage"] = {
                    "ok": amo.get("ok"),
                    "lead_id": amo.get("lead_id"),
                    "amo_stage_key": amo.get("amo_stage_key"),
                    "task_ok": (amo.get("task") or {}).get("ok"),
                }
                lead_id = amo.get("lead_id")
                if lead_id and amo.get("ok") and not case_row.get("crm_external_id"):
                    persist_crm_external_id(case_id, str(lead_id))
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "review_ask amo stage failed case=%s: %s", case_id[:8], exc
            )
            result["amocrm_review_stage"] = {"ok": False, "error": str(exc)[:200]}

    return result
