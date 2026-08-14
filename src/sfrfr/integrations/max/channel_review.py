"""Отправка черновика специалистам (ops-бот) и публикация в клиентский канал."""

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


def review_recipient_user_ids() -> list[str]:
    """MAX user_id специалистов для премодерации в личке ops-бота."""
    settings = get_settings()
    raw = (settings.staff_login_approver_max_user_ids or "").strip()
    return [p.strip() for p in raw.split(",") if p.strip()]


def send_draft_for_review(
    draft: ChannelDraft,
    *,
    ops_bot: MaxBotClient | None = None,
    chat_id: str | None = None,
    user_ids: list[str] | None = None,
    to_channel: bool = False,
) -> dict[str, Any]:
    """
    Черновик на одобрение.

    По умолчанию — в личку ops-бота каждому из STAFF_LOGIN_APPROVER_MAX_USER_IDS.
    Канал команды — только при to_channel=True или явном chat_id.
    """
    settings = get_settings()
    if ops_bot is None:
        from sfrfr.integrations.max.ops_bot import get_ops_bot

        bot = get_ops_bot()
    else:
        bot = ops_bot
    if not bot.available:
        return {"ok": False, "error": "ops-бот недоступен (MAX_OPS_BOT_TOKEN)"}

    text = format_review_message(draft)
    attachments = review_keyboard(draft)
    store = get_draft_store()

    # Явный chat_id или флаг — в канал / указанный чат.
    if to_channel or (chat_id or "").strip():
        target = (chat_id or settings.max_specialists_channel_chat_id or "").strip()
        if not target:
            return {
                "ok": False,
                "error": "MAX_SPECIALISTS_CHANNEL_CHAT_ID не задан",
            }
        try:
            result = bot.send_message(
                text=text,
                chat_id=target,
                attachments=attachments,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("channel_draft_review_send_failed: %s", exc)
            return {"ok": False, "error": str(exc)}
        return {
            "ok": True,
            "mode": "channel",
            "chat_id": target,
            "draft_id": draft.id,
            "result": result,
        }

    recipients = list(user_ids) if user_ids is not None else review_recipient_user_ids()
    if not recipients:
        # Запасной путь — канал команды, если лички не настроены.
        channel = (settings.max_specialists_channel_chat_id or "").strip()
        if channel:
            return send_draft_for_review(
                draft,
                ops_bot=bot,
                chat_id=channel,
                to_channel=True,
            )
        return {
            "ok": False,
            "error": "Задайте STAFF_LOGIN_APPROVER_MAX_USER_IDS "
            "(личка ops) или MAX_SPECIALISTS_CHANNEL_CHAT_ID",
        }

    results: list[dict[str, Any]] = []
    errors: list[str] = []
    for uid in recipients:
        try:
            result = bot.send_message(
                text=text,
                user_id=uid,
                attachments=attachments,
            )
            store.mark_waiting_edit(draft.id, uid)
            results.append({"user_id": uid, "result": result})
        except Exception as exc:  # noqa: BLE001
            logger.warning("channel_draft_review_dm_failed user_id=%s: %s", uid, exc)
            errors.append(f"{uid}:{exc}")

    if not results:
        return {"ok": False, "error": "; ".join(errors) or "не удалось отправить"}
    return {
        "ok": True,
        "mode": "ops_dm",
        "user_ids": [r["user_id"] for r in results],
        "draft_id": draft.id,
        "results": results,
        "errors": errors,
    }


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
    to_channel: bool = False,
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
    sync = _sync_draft_to_vps(draft)
    sent = send_draft_for_review(draft, to_channel=to_channel)
    return {
        "draft": {"id": draft.id, "source_id": draft.source_id},
        "vps_sync": sync,
        **sent,
    }


def _sync_draft_to_vps(draft: ChannelDraft) -> dict[str, Any]:
    """Чтобы webhook на VPS видел черновик при нажатии «Опубликовать»."""
    import httpx

    settings = get_settings()
    base = (settings.public_base_url or "").rstrip("/")
    if not base or "localhost" in base or "127.0.0.1" in base:
        return {"ok": False, "skipped": True, "reason": "no public_base_url"}
    token = (
        (settings.max_ops_bot_token or "").strip()
        or (settings.max_bot_token or "").strip()
    )
    if not token:
        return {"ok": False, "skipped": True, "reason": "no token"}
    url = f"{base}/api/integrations/max/channel-drafts"
    try:
        with httpx.Client(timeout=20.0) as client:
            resp = client.post(
                url,
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "id": draft.id,
                    "text": draft.text,
                    "cta_label": draft.cta_label,
                    "cta_kind": draft.cta_kind,
                    "cta_url": draft.cta_url,
                    "pin": draft.pin,
                    "source_id": draft.source_id,
                },
            )
            resp.raise_for_status()
            data = resp.json() if resp.content else {}
            return {"ok": True, "result": data}
    except Exception as exc:  # noqa: BLE001
        logger.warning("channel_draft_vps_sync_failed: %s", exc)
        return {"ok": False, "error": str(exc)}


def reply_draft_in_ops_dm(
    bot: MaxBotClient,
    *,
    user_id: str,
    draft: ChannelDraft,
) -> bool:
    """Показать черновик с кнопками в личке ops-бота (не в канал команды)."""
    from sfrfr.integrations.max.handler import _reply

    return _reply(
        bot,
        user_id=user_id,
        chat_id=None,
        text=format_review_message(draft),
        attachments=review_keyboard(draft),
    )
