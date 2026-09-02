"""Уведомления о новых заявках: email + чат сотрудников (без amo при AMOCRM_ENABLED=0)."""

from __future__ import annotations

import logging
from typing import Any

from sfrfr.core.config import get_settings
from sfrfr.utils.case_display import case_catalog_code

logger = logging.getLogger(__name__)

_STAFF_CHAT_LINK_LABEL = "Открыть чат в кабинете сотрудника"


def _channel_label_ru(channel: str) -> str:
    mapping = {
        "site": "Сайт",
        "web_cabinet": "Веб-кабинет",
        "max_miniapp": "MAX",
        "max": "MAX",
        "cabinet": "Кабинет на сайте",
        "admin": "Админ",
    }
    key = (channel or "").strip().lower()
    return mapping.get(key, channel or "не указан")


def staff_case_chat_url(case_id: str) -> str | None:
    from sfrfr.integrations.amocrm.urls import admin_case_max_reply_url

    return admin_case_max_reply_url(case_id)


def build_lead_notify_text(
    *,
    case_id: str,
    full_name: str,
    phone: str | None = None,
    email: str | None = None,
    contact: str | None = None,
    channel: str,
    source_label: str,
    max_user_id: str | None = None,
    crm_url: str | None = None,
) -> tuple[str, str, str | None]:
    """subject, plain body, staff chat URL."""
    from sfrfr.integrations.max.ops_client_label import format_ops_client_block

    settings = get_settings()
    catalog = case_catalog_code(case_id, full_name=full_name)
    staff_url = staff_case_chat_url(case_id)
    phone_line = (phone or "").strip()
    email_line = (email or "").strip()
    if not phone_line and contact:
        phone_line = contact.strip()
    lines = [
        f"Новая заявка {source_label}",
        f"Дело: {catalog}",
        format_ops_client_block(max_user_id=max_user_id, full_name=full_name),
    ]
    if phone_line:
        lines.append(f"Телефон: {phone_line}")
    if email_line:
        lines.append(f"Email: {email_line}")
    lines.append(f"Канал: {_channel_label_ru(channel)}")
    if staff_url:
        lines.append(f"Чат сотрудника: {staff_url}")
    if settings.amocrm_enabled and crm_url:
        lines.append(f"amoCRM: {crm_url}")
    lines.append("Ответьте клиенту в чате кабинета сотрудника — ссылка выше.")
    subject = f"Проверка стажа: заявка {catalog}"
    return subject, "\n".join(lines), staff_url


def _lead_notify_html(
    *,
    subject: str,
    body: str,
    staff_url: str | None,
) -> str:
    link = (
        f'<p><a href="{staff_url}">{_STAFF_CHAT_LINK_LABEL}</a></p>'
        if staff_url
        else ""
    )
    safe_body = body.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return (
        f"<p><b>{subject}</b></p>"
        f"<pre style='font-family:sans-serif;white-space:pre-wrap'>{safe_body}</pre>"
        f"{link}"
    )


def notify_email_ops_new_lead(
    *,
    case_id: str,
    full_name: str,
    phone: str | None = None,
    email: str | None = None,
    contact: str | None = None,
    channel: str,
    source_label: str,
    max_user_id: str | None = None,
    crm_url: str | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    to_addr = (settings.ops_notify_email or "").strip()
    if not to_addr or "@" not in to_addr:
        return {"ok": False, "skipped": True, "reason": "no OPS_NOTIFY_EMAIL"}
    try:
        from sfrfr.integrations.yandex_workspace.mail import send_mail
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": type(exc).__name__}

    subject, body, staff_url = build_lead_notify_text(
        case_id=case_id,
        full_name=full_name,
        phone=phone,
        email=email,
        contact=contact,
        channel=channel,
        source_label=source_label,
        max_user_id=max_user_id,
        crm_url=crm_url,
    )
    result = send_mail(
        to=to_addr,
        template="custom",
        subject=subject,
        body=body,
        html=_lead_notify_html(subject=subject, body=body, staff_url=staff_url),
        from_name="Проверка стажа",
    )
    if not result.get("ok"):
        logger.warning("email lead notify failed: %s", result)
    return result


def notify_max_managers_new_lead(
    *,
    case_id: str,
    full_name: str,
    phone: str | None = None,
    email: str | None = None,
    contact: str | None = None,
    channel: str,
    source_label: str,
    crm_url: str | None = None,
    max_user_id: str | None = None,
) -> dict[str, Any]:
    try:
        from sfrfr.db.staff_roles import list_manager_max_user_ids
        from sfrfr.integrations.max.client import inline_buttons_keyboard
        from sfrfr.integrations.max.ops_bot import get_ops_bot
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": type(exc).__name__}

    settings = get_settings()
    bot = get_ops_bot()
    if not bot.available:
        return {"ok": False, "skipped": True, "reason": "no MAX bot token"}

    manager_ids = list_manager_max_user_ids(
        extra_ids=settings.staff_login_approver_max_user_ids,
    )
    chat_ids = [
        p.strip()
        for p in (settings.staff_login_approver_max_chat_ids or "").split(",")
        if p.strip()
    ]
    team_channel = (settings.max_specialists_channel_chat_id or "").strip()
    if not manager_ids and not chat_ids and not team_channel:
        return {"ok": False, "skipped": True, "reason": "no managers"}

    _subject, text, staff_url = build_lead_notify_text(
        case_id=case_id,
        full_name=full_name,
        phone=phone,
        email=email,
        contact=contact,
        channel=channel,
        source_label=source_label,
        max_user_id=max_user_id,
        crm_url=crm_url,
    )
    attachments: list[dict[str, Any]] | None = None
    if staff_url:
        attachments = inline_buttons_keyboard(
            [[{"type": "link", "text": _STAFF_CHAT_LINK_LABEL, "url": staff_url}]]
        )

    sent = 0
    channel_sent = False
    if manager_ids or chat_ids:
        targets: list[str | None] = (
            list(manager_ids) if manager_ids else [None] * len(chat_ids)
        )
        for i, mid in enumerate(targets):
            cid = chat_ids[i] if i < len(chat_ids) else None
            try:
                bot.send_message(
                    text=text,
                    user_id=str(mid) if mid else None,
                    chat_id=cid,
                    attachments=attachments,
                )
                sent += 1
            except Exception as exc:  # noqa: BLE001
                logger.warning("max lead notify failed: %s", exc)

    if team_channel:
        try:
            bot.send_message(text=text, chat_id=team_channel, attachments=attachments)
            sent += 1
            channel_sent = True
        except Exception as exc:  # noqa: BLE001
            logger.warning("max lead notify team channel failed: %s", exc)

    return {
        "ok": sent > 0,
        "sent": sent,
        "team_channel_sent": channel_sent,
    }


def notify_ops_new_lead(
    *,
    case_id: str,
    full_name: str,
    phone: str | None = None,
    email: str | None = None,
    contact: str | None = None,
    channel: str,
    source_label: str,
    max_user_id: str | None = None,
    crm_url: str | None = None,
) -> dict[str, Any]:
    """Email на OPS_NOTIFY_EMAIL + MAX чат сотрудников."""
    email_result = notify_email_ops_new_lead(
        case_id=case_id,
        full_name=full_name,
        phone=phone,
        email=email,
        contact=contact,
        channel=channel,
        source_label=source_label,
        max_user_id=max_user_id,
        crm_url=crm_url,
    )
    max_result = notify_max_managers_new_lead(
        case_id=case_id,
        full_name=full_name,
        phone=phone,
        email=email,
        contact=contact,
        channel=channel,
        source_label=source_label,
        max_user_id=max_user_id,
        crm_url=crm_url,
    )
    return {"email": email_result, "max": max_result}
