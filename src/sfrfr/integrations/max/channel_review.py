"""Отправка черновика в канал команды и публикация в клиентский канал."""

from __future__ import annotations

import logging
from typing import Any

from sfrfr.core.config import get_settings
from sfrfr.integrations.max.channel_drafts import (
    ChannelDraft,
    client_cta_attachments,
    format_review_message,
    get_draft_store,
    review_keyboard,
)
from sfrfr.integrations.max.client import MaxBotClient

logger = logging.getLogger(__name__)


def send_draft_for_review(
    draft: ChannelDraft,
    *,
    ops_bot: MaxBotClient | None = None,
    chat_id: str | None = None,
) -> dict[str, Any]:
    """Пост черновика в канал специалистов (ops-бот)."""
    settings = get_settings()
    target = (chat_id or settings.max_specialists_channel_chat_id or "").strip()
    if not target:
        return {
            "ok": False,
            "error": "MAX_SPECIALISTS_CHANNEL_CHAT_ID не задан",
        }
    if ops_bot is None:
        from sfrfr.integrations.max.ops_bot import get_ops_bot

        bot = get_ops_bot()
    else:
        bot = ops_bot
    if not bot.available:
        return {"ok": False, "error": "ops-бот недоступен (MAX_OPS_BOT_TOKEN)"}
    text = format_review_message(draft)
    attachments = review_keyboard(draft)
    try:
        result = bot.send_message(
            text=text,
            chat_id=target,
            attachments=attachments,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("channel_draft_review_send_failed: %s", exc)
        return {"ok": False, "error": str(exc)}
    return {"ok": True, "chat_id": target, "draft_id": draft.id, "result": result}


def publish_draft_to_client_channel(
    draft: ChannelDraft,
    *,
    client_bot: MaxBotClient | None = None,
    channel_chat_id: str | None = None,
) -> dict[str, Any]:
    """Публикация в клиентский канал (клиентский бот — админ канала)."""
    settings = get_settings()
    target = (channel_chat_id or settings.max_channel_chat_id or "").strip()
    if not target:
        return {"ok": False, "error": "MAX_CHANNEL_CHAT_ID не задан"}
    bot = client_bot or MaxBotClient()
    if not bot.available:
        return {"ok": False, "error": "MAX_BOT_TOKEN не задан"}
    attachments = client_cta_attachments(draft)
    try:
        result = bot.send_message(
            text=draft.text,
            chat_id=target,
            attachments=attachments,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("channel_draft_publish_failed: %s", exc)
        return {"ok": False, "error": str(exc)}

    mid = ""
    public_url = ""
    msg = result.get("message") if isinstance(result, dict) else None
    if isinstance(msg, dict):
        public_url = str(msg.get("url") or "")
        body = msg.get("body")
        if isinstance(body, dict):
            mid = str(body.get("mid") or "")

    pin_result = None
    if draft.pin and mid:
        try:
            pin_result = bot.pin_message(chat_id=target, message_id=mid, notify=True)
        except Exception as exc:  # noqa: BLE001
            logger.warning("channel_draft_pin_failed: %s", exc)
            pin_result = {"error": str(exc)}

    get_draft_store().mark_published(draft.id, url=public_url, mid=mid)
    return {
        "ok": True,
        "chat_id": target,
        "draft_id": draft.id,
        "mid": mid,
        "url": public_url,
        "pin": pin_result,
        "result": result,
    }


def create_and_send_review(
    *,
    text: str,
    cta_label: str = "",
    cta_kind: str = "",
    cta_url: str = "",
    pin: bool = False,
    source_id: str = "",
    draft_id: str | None = None,
) -> dict[str, Any]:
    draft = get_draft_store().create(
        text=text,
        cta_label=cta_label,
        cta_kind=cta_kind,
        cta_url=cta_url,
        pin=pin,
        source_id=source_id,
        draft_id=draft_id,
    )
    sent = send_draft_for_review(draft)
    return {"draft": {"id": draft.id, "source_id": draft.source_id}, **sent}
