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
    Две ссылки (кабинет + MAX); порядок по предпочтению канала.
    Не блокирует другой канал — только порядок CTA.
    """
    settings = get_settings()
    cabinet = cabinet_case_url(case_id)

    max_url = settings.max_public_bot_url
    miniapp = settings.max_miniapp_url.rstrip("/") + "/"
    if case_id:
        miniapp = f"{miniapp}?case={case_id}" if "?" not in miniapp else f"{miniapp}&case={case_id}"

    links = [
        {
            "channel": "web_cabinet",
            "label": "Веб-кабинет",
            "url": cabinet,
            "copy": "В браузере — удобнее с компьютера и большим экраном",
        },
        {
            "channel": "max_miniapp",
            "label": "Мини-приложение MAX",
            "url": miniapp if max_linked else max_url,
            "copy": "В MAX — быстро из мессенджера",
            "bot_url": max_url,
        },
    ]
    preferred = preferred_channel or "unset"
    if preferred == "max_miniapp":
        links = list(reversed(links))
    return {
        "preferred_channel": preferred,
        "links": links,
        "note": "Оба варианта: одни и те же документы и статус дела",
        "warning": "Решение принимает СФР. Результат не гарантирован.",
    }


def format_status_change_message(
    *,
    status_value: str,
    preferred_channel: str | None,
    max_linked: bool,
    case_id: str,
) -> str:
    """Текст уведомления: статус + две CTA в порядке preferred_channel."""
    label = status_label_ru(status_value)
    payload = notification_channel_links(
        preferred_channel=preferred_channel,
        max_linked=max_linked,
        case_id=case_id,
    )
    lines = [
        f"Статус вашего дела обновился: {label}.",
        "",
        "Открыть дело:",
    ]
    for item in payload["links"]:
        lines.append(f"• {item['label']}: {item['url']}")
    lines.extend(["", payload["warning"]])
    return "\n".join(lines)


def notify_case_status_change(
    *,
    case_id: str,
    status_value: str,
    previous_status: str | None = None,
    client: dict[str, Any] | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """
    Уведомить клиента о смене статуса: MAX (если linked) + системное сообщение в деле.
    Email SMTP пока нет — фиксируем intent в результате (и в audit вызывающей стороны).
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
        "max_sent": False,
        "case_message": False,
        "email_queued": False,
        "text": text,
    }

    # Системное сообщение в чате дела (видно в кабинете и mini-app).
    try:
        from sfrfr.db.session import get_supabase_client

        get_supabase_client().table("case_messages").insert(
            {
                "case_id": case_id,
                "author_kind": "system",
                "author_user_id": None,
                "body": text,
            }
        ).execute()
        result["case_message"] = True
    except Exception as exc:  # noqa: BLE001 — уведомление не должно ломать смену статуса
        logger.warning("status notify case_message failed case=%s: %s", case_id[:8], exc)

    if max_user_id:
        try:
            from sfrfr.integrations.max.client import MaxBotClient

            bot = MaxBotClient()
            send = bot.send_message(text=text, user_id=max_user_id)
            result["max_sent"] = not send.get("skipped")
            result["max_response"] = send
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

    return result
