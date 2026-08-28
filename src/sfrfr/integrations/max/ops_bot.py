"""ТЗ-25: служебный (Ops) бот MAX — уведомления и approve staff."""

from __future__ import annotations

import logging
from typing import Any

from sfrfr.core.config import get_settings
from sfrfr.integrations.max.channel_ids import remember_chat_id
from sfrfr.integrations.max.client import MaxBotClient, inline_get_login_code_keyboard
from sfrfr.integrations.max.handler import MaxHandleResult
from sfrfr.security.login_otp import GET_CODE_CALLBACK, GET_CODE_IN_BROWSER_LABEL

logger = logging.getLogger(__name__)

OPS_BOT_DISPLAY_NAME = "Проверка стажа-Ops"

_OPS_LOGIN_TRIGGERS = frozenset(
    {
        "/login",
        "войти",
        "вход",
        GET_CODE_IN_BROWSER_LABEL.lower(),
        "получить код",
        "получить код для входа",
        GET_CODE_CALLBACK,
        "get_login_code",
    }
)


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
        "• черновики постов клиентского канала — в эту личку "
        "(одобрить / скопировать / прислать правку);",
        "",
        "Вход в кабинет сотрудника:",
        f"1) На {admin or 'admin'} укажите email и нажмите «Получить код».",
        "2) Нажмите «Перейти в MAX» и отправьте код из браузера сюда.",
        "3) Нажмите «Войти в кабинет сотрудника».",
        "",
        "Можете задать вопрос по процессу или стажу — ответит ИИ с опорой на базу знаний.",
        "Черновик поста: вставьте текст сюда или `/draft …`.",
        "В канале команды: упомяните бота или напишите /ask …",
    ]
    if admin:
        lines.extend(["", f"Кабинет сотрудников: {admin}"])
    if client_bot:
        lines.extend(["", f"Бот для клиентов: {client_bot}"])
    return "\n".join(lines)


def _ops_start_attachments() -> list[dict[str, Any]]:
    return inline_get_login_code_keyboard()


def _handle_ops_staff_login(
    bot: MaxBotClient,
    *,
    user_id: str,
    chat_id: int | str | None,
) -> MaxHandleResult:
    """Вход сотрудника: подсказка кода или авто-привязка pending с admin."""
    from sfrfr.integrations.max.handler import _complete_pc_login, _reply
    from sfrfr.security.login_pending import latest_for_max, latest_unbound_staff_pending

    pending = latest_for_max(user_id)
    if pending and pending.audience == "staff":
        return _complete_pc_login(
            bot,
            user_id=user_id,
            chat_id=chat_id,
            ticket_id=pending.ticket_id,
        )

    unbound = latest_unbound_staff_pending()
    if unbound:
        reply = (
            f"Код со страницы admin: {unbound.pair_code}\n\n"
            "Отправьте эти 6 цифр следующим сообщением в этот чат, "
            "затем нажмите «Войти в кабинет сотрудника»."
        )
        _reply(
            bot,
            user_id=user_id,
            chat_id=chat_id,
            text=reply,
            attachments=_ops_start_attachments(),
        )
        return MaxHandleResult(ok=True, action="ops_staff_pair_hint", reply=reply)

    settings = get_settings()
    admin = (settings.admin_public_url or "admin.proverkastaza.ru").rstrip("/")
    reply = (
        f"Сначала на {admin} укажите рабочий email и нажмите «Получить код».\n"
        "Затем «Перейти в MAX» и пришлите код сюда."
    )
    _reply(
        bot,
        user_id=user_id,
        chat_id=chat_id,
        text=reply,
        attachments=_ops_start_attachments(),
    )
    return MaxHandleResult(ok=True, action="ops_staff_login_hint", reply=reply)


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
            chat_id=None,
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
                chat_id=None,
                text=f"Не удалось опубликовать `{draft.id}`: {err}",
            )
            return MaxHandleResult(ok=False, action="chdraft_pub_fail", detail=str(err))
        url = published.get("url") or "(без публичной ссылки)"
        _reply(
            bot,
            user_id=user_id,
            chat_id=None,
            text=(
                f"Опубликовано в канал клиентов.\n"
                f"id: `{draft.id}`\n"
                f"{url}"
            ),
        )
        return MaxHandleResult(ok=True, action="chdraft_published", detail=draft_id)

    # Прислать правку — ждём следующее сообщение в личке ops-бота
    store.mark_waiting_edit(draft_id, user_id)
    if cb_id:
        try:
            bot.answer_callback(
                cb_id,
                notification="Вставьте правку следующим сообщением в этот чат",
            )
        except Exception:  # noqa: BLE001
            pass
    _reply(
        bot,
        user_id=user_id,
        chat_id=None,
        text=(
            f"Жду правку черновика `{draft.id}`.\n\n"
            "1) «Скопировать текст» (если ещё не скопировали).\n"
            "2) Вставьте в поле сообщения этого ops-бота, поправьте.\n"
            "3) Отправьте сюда — пришлю обновлённый черновик "
            "с кнопкой «Опубликовать» в этот же чат."
        ),
    )
    return MaxHandleResult(ok=True, action="chdraft_edit_wait", detail=draft_id)


def _handle_channel_draft_edit_message(
    bot: MaxBotClient,
    *,
    user_id: str,
    chat_id: int | str | None,
    text: str,
) -> MaxHandleResult | None:
    """Правка/новый черновик только в личке ops-бота — ответ тоже в личку."""
    from sfrfr.integrations.max.channel_drafts import (
        get_draft_store,
        looks_like_channel_post,
    )
    from sfrfr.integrations.max.channel_review import reply_draft_in_ops_dm
    from sfrfr.integrations.max.ops_llm import is_specialists_channel

    body = (text or "").strip()
    if not body:
        return None
    if is_specialists_channel(chat_id):
        # В канале команды черновики не ведём — только в личке ops.
        return None

    store = get_draft_store()
    lower = body.lower()

    # /draft текст… — явная отправка черновика в этот же чат
    if lower.startswith("/draft"):
        post = body[6:].lstrip(" \t\r\n:").strip()
        if not post:
            from sfrfr.integrations.max.handler import _reply

            _reply(
                bot,
                user_id=user_id,
                chat_id=None,
                text="Напишите: /draft и далее текст поста.",
            )
            return MaxHandleResult(ok=True, action="chdraft_draft_usage")
        draft = store.create(text=post)
        store.mark_waiting_edit(draft.id, user_id)
        reply_draft_in_ops_dm(bot, user_id=user_id, draft=draft)
        return MaxHandleResult(ok=True, action="chdraft_created", detail=draft.id)

    if body.startswith("/"):
        return None

    waiting = store.find_waiting_for_user(user_id)
    if waiting:
        if len(body) < 40:
            return None
        updated = store.update_text(waiting.id, body)
        if not updated:
            return None
        store.mark_waiting_edit(updated.id, user_id)
        reply_draft_in_ops_dm(bot, user_id=user_id, draft=updated)
        return MaxHandleResult(ok=True, action="chdraft_updated", detail=updated.id)

    # В личке: длинный/многострочный текст без ожидания — новый черновик
    if looks_like_channel_post(body):
        draft = store.create(text=body)
        store.mark_waiting_edit(draft.id, user_id)
        reply_draft_in_ops_dm(bot, user_id=user_id, draft=draft)
        return MaxHandleResult(ok=True, action="chdraft_created", detail=draft.id)

    return None



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
    from sfrfr.security.login_pending import parse_confirm_callback, parse_manager_callback

    bot = bot or get_ops_bot()
    text = _text(update).strip()
    callback = _callback_payload(update)
    user_id = _user_id(update)
    chat_id = _chat_id(update)
    update_type = str(update.get("update_type") or "")
    lower = text.lower()
    manager_ticket = parse_manager_callback(callback)
    confirm_ticket = parse_confirm_callback(callback)
    if confirm_ticket is not None:
        from sfrfr.integrations.max.handler import _complete_pc_login

        if not user_id:
            return MaxHandleResult(ok=False, action="ignore", detail="confirm no user")
        return _complete_pc_login(
            bot,
            user_id=user_id,
            chat_id=chat_id,
            ticket_id=confirm_ticket or None,
        )

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

    if callback.startswith("srev:"):
        from sfrfr.api.routes.public_site_reviews import (
            build_site_review_moderation_reply,
            parse_site_review_callback,
        )
        from sfrfr.core.site_reviews import set_status
        from sfrfr.integrations.max.handler import _callback_id, _reply

        parsed = parse_site_review_callback(callback)
        cb_id = _callback_id(update)
        if not parsed:
            if cb_id:
                try:
                    bot.answer_callback(cb_id, notification="Ошибка кнопки")
                except Exception:  # noqa: BLE001
                    pass
            return MaxHandleResult(ok=False, action="srev_bad", detail="bad payload")
        item_id, review_status = parsed
        result = set_status(item_id, review_status)
        raw_item = result.get("item")
        item: dict[str, Any] = raw_item if isinstance(raw_item, dict) else {}
        quote = str(item.get("text") or "").strip()
        if cb_id:
            try:
                toast = "Опубликован" if review_status == "published" else "Отклонён"
                bot.answer_callback(cb_id, notification=toast)
            except Exception:  # noqa: BLE001
                pass
        reply, attachments = build_site_review_moderation_reply(
            item_id=item_id,
            review_status=review_status,
            quote=quote,
            ok=bool(result.get("ok")),
            error=str(result.get("error") or "") or None,
        )
        _reply(bot, user_id=user_id or "", chat_id=chat_id, text=reply, attachments=attachments)
        return MaxHandleResult(ok=True, action="srev_moderate", reply=reply)

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
        _reply(
            bot,
            user_id=user_id,
            chat_id=chat_id,
            text=reply,
            attachments=_ops_start_attachments(),
        )
        return MaxHandleResult(ok=True, action="ops_start", reply=reply)

    if lower.startswith("/help") or lower in {"help", "помощь"}:
        reply = _ops_welcome_text()
        _reply(
            bot,
            user_id=user_id,
            chat_id=chat_id,
            text=reply,
            attachments=_ops_start_attachments(),
        )
        return MaxHandleResult(ok=True, action="ops_help", reply=reply)

    login_hit = callback == GET_CODE_CALLBACK or lower in _OPS_LOGIN_TRIGGERS
    if login_hit:
        return _handle_ops_staff_login(bot, user_id=user_id, chat_id=chat_id)

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
        _reply(
            bot,
            user_id=user_id,
            chat_id=chat_id,
            text=reply,
            attachments=_ops_start_attachments(),
        )
        return MaxHandleResult(ok=True, action="ops_greeting", reply=reply)

    from sfrfr.integrations.max.handler import _handle_pair_code

    digits_only = "".join(ch for ch in text if ch.isdigit())
    compact = "".join(ch for ch in text if not ch.isspace())
    if len(digits_only) == 6 and len(compact) <= 24:
        return _handle_pair_code(bot, user_id=user_id, chat_id=chat_id, code=digits_only)

    # Правка / новый черновик — только личка ops (не канал команды).
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
