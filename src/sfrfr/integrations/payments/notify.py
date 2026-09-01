"""Уведомления после успешной оплаты: MAX + чат дела + заметка amoCRM.

Фискальный чек 54-ФЗ остаётся у ЮKassa (email/ОФД). Здесь только сервисные
сообщения, не замена чека.
"""

from __future__ import annotations

import logging
from typing import Any

from sfrfr.core.config import get_settings
from sfrfr.integrations.client_channels.notifications import cabinet_case_url

logger = logging.getLogger("sfrfr.payment_notify")

_PACKAGE_LABELS = {
    "DIAG": "диагностика",
    "ACCOMP": "сопровождение",
    "SF_LUMP": "успех-фи (разово)",
    "SF_MONTH": "успех-фи (ежемесячно)",
}


def format_payment_succeeded_message(
    *,
    case_id: str,
    package_code: str | None = None,
    amount_value: str | None = None,
    customer_email: str | None = None,
    receipt_via_yookassa: bool = True,
    source: str = "yookassa",
) -> str:
    """Текст клиенту: оплата + где чек + ссылка в кабинет."""
    pkg = _PACKAGE_LABELS.get((package_code or "").upper(), package_code or "услуга")
    if source == "receipt":
        lines = [
            "Оплата подтверждена по чеку: реквизиты совпали.",
            f"Услуга: {pkg}.",
        ]
        if amount_value:
            lines.append(f"Сумма: {amount_value} ₽.")
        lines.append("Чек сохранён в деле. Присылать ещё один не нужно.")
    else:
        lines = [
            "Оплата получена.",
            f"Услуга: {pkg}.",
        ]
        if amount_value:
            lines.append(f"Сумма: {amount_value} ₽.")
        lines.append("Чек присылать не нужно — уведомление об оплате уже пришло.")
        if receipt_via_yookassa:
            lines.append("Фискальный чек отправлен на email из профиля оплаты.")
    lines.extend(
        [
            "",
            "Откройте раздел «Оплаты» в кабинете на сайте.",
            "",
            "Мы готовим документы и план — подаёте через СФР или Госуслуги вы сами. "
            "Решение принимает СФР. Результат не гарантирован.",
        ]
    )
    return "\n".join(lines)


def format_amocrm_payment_note(
    *,
    case_id: str,
    package_code: str | None = None,
    amount_value: str | None = None,
    provider_payment_id: str | None = None,
) -> str:
    """Заметка в сделку: факт оплаты без ПДн-сканов."""
    pkg = package_code or "—"
    parts = [
        "SFRFR: оплата прошла",
        f"case={case_id}",
        f"package={pkg}",
    ]
    if amount_value:
        parts.append(f"amount={amount_value} RUB")
    if provider_payment_id:
        parts.append(f"yookassa={provider_payment_id}")
    parts.append("Чек 54-ФЗ — через ЮKassa (не через CRM).")
    return " | ".join(parts)


def notify_payment_succeeded(
    *,
    case_id: str,
    package_code: str | None = None,
    amount_value: str | None = None,
    provider_payment_id: str | None = None,
    customer_email: str | None = None,
    source: str = "yookassa",
) -> dict[str, Any]:
    """
    После payment.succeeded: сообщение в деле, MAX (если linked), заметка/sync amoCRM.
    Ошибки каналов глотаем — webhook ЮKassa должен ответить 200.
    """
    result: dict[str, Any] = {
        "ok": True,
        "case_id": case_id,
        "case_message": False,
        "max_queued": False,
        "max_sent": False,
        "amocrm_note": False,
        "amocrm_sync": False,
    }
    if not case_id:
        return {"ok": False, "skipped": True, "reason": "no case_id"}

    client_row: dict[str, Any] = {}
    case_row: dict[str, Any] = {}
    try:
        from sfrfr.db.session import get_supabase_client

        rows = (
            get_supabase_client()
            .table("cases")
            .select(
                "id, b2c_status, pipeline_status, crm_external_id, "
                "clients(full_name, phone, email, max_user_id, preferred_channel)"
            )
            .eq("id", case_id)
            .limit(1)
            .execute()
            .data
            or []
        )
        if rows:
            case_row = rows[0]
            client_row = case_row.get("clients") or {}
            if isinstance(client_row, list):
                client_row = client_row[0] if client_row else {}
    except Exception as exc:  # noqa: BLE001
        logger.warning("payment notify load case failed case=%s: %s", case_id[:8], exc)

    email = (customer_email or client_row.get("email") or "").strip() or None
    settings = get_settings()
    text = format_payment_succeeded_message(
        case_id=case_id,
        package_code=package_code,
        amount_value=amount_value,
        customer_email=email,
        receipt_via_yookassa=bool(settings.yookassa_send_receipt),
        source=source,
    )
    result["text"] = text

    max_user_id = client_row.get("max_user_id")
    button_label = "Открыть оплаты"
    button_url = cabinet_case_url(case_id, view="payments")
    message_text = text
    if max_user_id:
        try:
            # Sprint 2: опционально — защищённая ссылка на согласие (без cutover FSM)
            if (
                settings.max_secure_link_buttons_enabled
                and settings.secure_action_links_enabled
            ):
                try:
                    from sfrfr.secure_links.actions import issue_consent_link

                    issued = issue_consent_link(
                        case_id=case_id,
                        max_user_id=str(max_user_id),
                        issued_via="max",
                        actor="payment_notify",
                    )
                    button_label = "Подтвердить согласие"
                    button_url = str(issued["url"])
                    message_text = (
                        text
                        + "\n\n"
                        + "Чтобы безопасно передать документы позже, "
                        + "сначала подтвердите согласие по кнопке ниже. "
                        + "Регистрация не нужна. Сканы в чат не отправляйте."
                    )
                    result["secure_consent_prefix"] = issued.get("token_prefix")
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "payment notify secure consent link skipped case=%s: %s",
                        case_id[:8],
                        exc,
                    )
        except Exception as exc:  # noqa: BLE001
            logger.warning("payment notify secure link failed case=%s: %s", case_id[:8], exc)

    message_id: str | None = None
    try:
        from sfrfr.db.session import get_supabase_client

        inserted = (
            get_supabase_client()
            .table("case_messages")
            .insert(
                {
                    "case_id": case_id,
                    "author_kind": "system",
                    "author_user_id": None,
                    "body": message_text,
                    "channel_origin": "bot",
                }
            )
            .execute()
        )
        message_id = str((inserted.data or [{}])[0].get("id") or "").strip() or None
        result["case_message"] = True
    except Exception as exc:  # noqa: BLE001
        logger.warning("payment notify case_message failed case=%s: %s", case_id[:8], exc)

    if max_user_id and message_id:
        try:
            from sfrfr.integrations.max.client import inline_link_keyboard
            from sfrfr.services.case_chat_delivery import (
                enqueue_max_delivery,
                process_pending_outbox,
            )

            queued = enqueue_max_delivery(
                case_id=case_id,
                message_id=message_id,
                max_user_id=str(max_user_id),
                body=message_text,
                attachments=inline_link_keyboard(button_label, button_url),
            )
            result["max_queued"] = queued
            if queued:
                result["max_sent"] = process_pending_outbox(limit=5) > 0
        except Exception as exc:  # noqa: BLE001
            logger.warning("payment notify MAX queue failed case=%s: %s", case_id[:8], exc)

    # amoCRM: обновить сделку (b2c уже в БД) + заметка об оплате
    try:
        from sfrfr.integrations.amocrm import AmoCrmClient
        from sfrfr.integrations.amocrm.sync import persist_crm_external_id, push_case_to_amocrm

        case_for_amo = {
            **case_row,
            "id": case_id,
            "clients": client_row,
        }
        amo = push_case_to_amocrm(case_for_amo, task=f"paid:{package_code or 'order'}")
        result["amocrm_sync"] = bool(amo.get("ok"))
        lead_id = amo.get("lead_id") or case_row.get("crm_external_id")
        if lead_id and amo.get("ok") and not case_row.get("crm_external_id"):
            persist_crm_external_id(case_id, str(lead_id))
        if lead_id:
            note = format_amocrm_payment_note(
                case_id=case_id,
                package_code=package_code,
                amount_value=amount_value,
                provider_payment_id=provider_payment_id,
            )
            note_res = AmoCrmClient().add_lead_note(str(lead_id), note)
            result["amocrm_note"] = bool(note_res.get("ok"))
            note_keys = ("ok", "skipped", "status_code", "reason")
            result["amocrm_note_detail"] = {
                k: note_res.get(k) for k in note_keys if k in note_res
            }
    except Exception as exc:  # noqa: BLE001
        logger.warning("payment notify amoCRM failed case=%s: %s", case_id[:8], exc)

    return result
