"""ТЗ-25: служебный (Ops) бот MAX — уведомления и approve staff."""

from __future__ import annotations

import logging
from typing import Any

from sfrfr.core.config import get_settings
from sfrfr.integrations.max.channel_ids import remember_chat_id
from sfrfr.integrations.max.client import MaxBotClient
from sfrfr.integrations.max.handler import MaxHandleResult

logger = logging.getLogger(__name__)

OPS_BOT_DISPLAY_NAME = "Проверка стажа-Ops"


def get_ops_bot() -> MaxBotClient:
    """Клиент для служебных уведомлений (лиды, approve)."""
    return MaxBotClient.for_ops()


def ops_bot_configured() -> bool:
    return bool((get_settings().max_ops_bot_token or "").strip())


def _ops_welcome_text() -> str:
    settings = get_settings()
    admin = (settings.admin_public_url or "").rstrip("/")
    client_bot = (settings.max_chat_url or "").strip()
    lines = [
        f"Служебный бот «{OPS_BOT_DISPLAY_NAME}».",
        "",
        "Сюда приходят:",
        "• новые заявки с сайта;",
        "• запросы на вход сотрудников в кабинет;",
        "• черновики постов клиентского канала (одобрить / править).",
        "",
        "Можете задать вопрос по процессу или стажу — ответит ИИ с опорой на базу знаний.",
        "В канале команды: упомяните бота или напишите /ask …",
        "",
        "Диагностику клиента и вход в кабинет ведите в боте «Стаж и пенсия».",
    ]
    if admin:
        lines.extend(["", f"Кабинет сотрудников: {admin}"])
    if client_bot:
        lines.extend(["", f"Бот для клиентов: {client_bot}"])
    return "\n".join(lines)


def _handle_channel_draft_callback(
    bot: MaxBotClient,
    *,
    update: dict[str, Any],
    user_id: str,
    chat_id: int | str | None,
    payload: str,
) -> MaxHandleResult | None:
    from sfrfr.integrations.max.channel_drafts import (
        get_draft_store,
        parse_draft_callback,
    )
    from sfrfr.integrations.max.channel_review import (
        publish_draft_to_client_channel,
    )
    from sfrfr.integrations.max.handler import _callback_id, _reply

    parsed = parse_draft_callback(payload)
    if not parsed:
        return None
    action, draft_id = parsed
    store = get_draft_store()
    draft = store.get(draft_id)
    cb_id = _callback_id(update)

    if not draft:
        if cb_id:
            try:
                bot.answer_callback(cb_id, notification="Черновик не найден")
            except Exception:  # noqa: BLE001
                pass
        return MaxHandleResult(ok=True, action="chdraft_missing", detail=draft_id)

    if draft.status == "published":
        if cb_id:
            try:
                bot.answer_callback(
                    cb_id,
                    notification="Уже опубликовано",
                )
            except Exception:  # noqa: BLE001
                pass
        url = draft.published_url or "в канале клиентов"
        _reply(
            bot,
            user_id=user_id,
            chat_id=chat_id,
            text=f"Черновик `{draft.id}` уже опубликован: {url}",
        )
        return MaxHandleResult(ok=True, action="chdraft_already", detail=draft_id)

    if action == "pub":
        if cb_id:
            try:
                bot.answer_callback(cb_id, notification="Публикуем…")
            except Exception:  # noqa: BLE001
                pass
        published = publish_draft_to_client_channel(draft)
        if not published.get("ok"):
            err = published.get("error") or "ошибка"
            _reply(
                bot,
                user_id=user_id,
                chat_id=chat_id,
                text=f"Не удалось опубликовать `{draft.id}`: {err}",
            )
            return MaxHandleResult(ok=False, action="chdraft_pub_fail", detail=str(err))
        url = published.get("url") or "(без публичной ссылки)"
        _reply(
            bot,
            user_id=user_id,
            chat_id=chat_id,
            text=(
                f"Опубликовано в канал клиентов.\n"
                f"id: `{draft.id}`\n"
                f"{url}"
            ),
        )
        return MaxHandleResult(ok=True, action="chdraft_published", detail=draft_id)

    # edit
    store.mark_waiting_edit(draft_id, user_id)
    if cb_id:
        try:
            bot.answer_callback(
                cb_id,
                notification="Скопируйте текст кнопкой ниже и вставьте в поле",
            )
        except Exception:  # noqa: BLE001
            pass
    # Только clipboard + напоминание (полная клавиатура уже на исходном черновике)
    clip_only = [
        {
            "type": "inline_keyboard",
            "payload": {
                "buttons": [
                    [
                        {
                            "type": "clipboard",
                            "text": "Скопировать текст в буфер",
                            "payload": draft.text
                            if len(draft.text.encode("utf-8")) <= 4000
                            else draft.text[:3500] + "\n…",
                        }
                    ]
                ]
            },
        }
    ]
    _reply(
        bot,
        user_id=user_id,
        chat_id=chat_id,
        text=(
            f"Редактирование черновика `{draft.id}`.\n\n"
            "1) Нажмите «Скопировать текст в буфер».\n"
            "2) Вставьте в поле сообщения (вставить / Ctrl+V).\n"
            "3) Поправьте текст и отправьте сюда.\n\n"
            "После отправки пришлём обновлённый черновик с кнопкой «Опубликовать»."
        ),
        attachments=clip_only,
    )
    return MaxHandleResult(ok=True, action="chdraft_edit_wait", detail=draft_id)


def _handle_channel_draft_edit_message(
    bot: MaxBotClient,
    *,
    user_id: str,
    chat_id: int | str | None,
    text: str,
) -> MaxHandleResult | None:
    from sfrfr.integrations.max.channel_drafts import (
        format_review_message,
        get_draft_store,
        review_keyboard,
    )
    from sfrfr.integrations.max.handler import _reply

    body = (text or "").strip()
    if not body or body.startswith("/"):
        return None
    # Не перехватывать /ask и упоминания — их обработает LLM ниже, если нет waiting.
    store = get_draft_store()
    draft = store.find_waiting_for_user(user_id)
    if not draft:
        return None
    updated = store.update_text(draft.id, body)
    if not updated:
        return None
    _reply(
        bot,
        user_id=user_id,
        chat_id=chat_id,
        text=format_review_message(updated),
        attachments=review_keyboard(updated),
    )
    return MaxHandleResult(ok=True, action="chdraft_updated", detail=updated.id)


def handle_ops_update(
    update: dict[str, Any],
    *,
    bot: MaxBotClient | None = None,
) -> MaxHandleResult:
    """
    Узкий обработчик ops-бота:
    approve staff, черновики канала, /start; без клиентского intake.
    """
    from sfrfr.integrations.max.handler import (
        _approve_staff_by_manager,
        _callback_payload,
        _chat_id,
        _reply,
        _text,
        _user_id,
    )
    from sfrfr.security.login_pending import parse_manager_callback

    bot = bot or get_ops_bot()
    text = _text(update).strip()
    callback = _callback_payload(update)
    user_id = _user_id(update)
    chat_id = _chat_id(update)
    update_type = str(update.get("update_type") or "")
    lower = text.lower()
    manager_ticket = parse_manager_callback(callback)

    # Канал команды: chat_id из bot_added (также доступен через GET /chats у ops-бота).
    if "bot_added" in update_type or update_type.endswith("bot_added"):
        entry = remember_chat_id(
            chat_id,
            source="ops_webhook_bot_added",
            update_type=update_type,
        )
        logger.info("ops_bot_added chat_id=%s user_id=%s", chat_id, user_id)
        return MaxHandleResult(
            ok=True,
            action="bot_added",
            detail=f"chat_id={chat_id}" if entry else "no chat_id",
        )
    if "bot_removed" in update_type:
        logger.info("ops_bot_removed chat_id=%s user_id=%s", chat_id, user_id)
        return MaxHandleResult(ok=True, action="bot_removed", detail=f"chat_id={chat_id}")

    if callback.startswith("chdraft:"):
        if not user_id:
            return MaxHandleResult(ok=False, action="ignore", detail="chdraft no user")
        handled = _handle_channel_draft_callback(
            bot,
            update=update,
            user_id=user_id,
            chat_id=chat_id,
            payload=callback,
        )
        if handled is not None:
            return handled

    if not user_id and not manager_ticket:
        return MaxHandleResult(ok=False, action="ignore", detail="no user_id")
    if manager_ticket:
        return _approve_staff_by_manager(
            bot,
            user_id=user_id or "",
            chat_id=chat_id,
            ticket_id=manager_ticket,
        )

    if not user_id:
        return MaxHandleResult(ok=False, action="ignore", detail="no user_id")

    if lower in {"/start", "start", "начать"} or lower.startswith("/start"):
        reply = _ops_welcome_text()
        _reply(bot, user_id=user_id, chat_id=chat_id, text=reply)
        return MaxHandleResult(ok=True, action="ops_start", reply=reply)

    if lower.startswith("/help") or lower in {"help", "помощь"}:
        reply = _ops_welcome_text()
        _reply(bot, user_id=user_id, chat_id=chat_id, text=reply)
        return MaxHandleResult(ok=True, action="ops_help", reply=reply)

    # Приветствия — то же служебное меню, без англицизмов.
    greetings = {
        "привет",
        "здравствуйте",
        "добрый день",
        "доброе утро",
        "добрый вечер",
        "hi",
        "hello",
    }
    if lower in greetings:
        reply = _ops_welcome_text()
        _reply(bot, user_id=user_id, chat_id=chat_id, text=reply)
        return MaxHandleResult(ok=True, action="ops_greeting", reply=reply)

    # Правка черновика: следующее сообщение после «Редактировать».
    edit_result = _handle_channel_draft_edit_message(
        bot,
        user_id=user_id,
        chat_id=chat_id,
        text=text,
    )
    if edit_result is not None:
        return edit_result

    from sfrfr.integrations.max.ops_llm import (
        answer_specialist_question,
        extract_ops_question,
        is_specialists_channel,
        ops_llm_enabled,
    )

    in_channel = is_specialists_channel(chat_id)
    if ops_llm_enabled():
        question = extract_ops_question(text, in_channel=in_channel)
        if in_channel and question is None:
            # Обычные сообщения канала не трогаем.
            return MaxHandleResult(ok=True, action="ops_channel_ignore")
        if question:
            reply = answer_specialist_question(question)
            _reply(bot, user_id=user_id, chat_id=chat_id, text=reply)
            return MaxHandleResult(ok=True, action="ops_llm_answer", reply=reply)

    if in_channel:
        return MaxHandleResult(ok=True, action="ops_channel_ignore")

    settings = get_settings()
    client_bot = (settings.max_chat_url or "").strip()
    reply = (
        "Это служебный бот для сотрудников.\n"
        "Для диагностики и входа клиента откройте бот «Стаж и пенсия»"
        + (f":\n{client_bot}" if client_bot else ".")
    )
    _reply(bot, user_id=user_id, chat_id=chat_id, text=reply)
    return MaxHandleResult(ok=True, action="ops_redirect_client", reply=reply)
