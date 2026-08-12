"""ТЗ-25: служебный (Ops) бот MAX — уведомления и approve staff."""

from __future__ import annotations

from typing import Any

from sfrfr.core.config import get_settings
from sfrfr.integrations.max.client import MaxBotClient
from sfrfr.integrations.max.handler import MaxHandleResult


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
        "Служебный бот «Проверка стажа спец».",
        "",
        "Сюда приходят:",
        "• новые заявки с сайта;",
        "• запросы на вход сотрудников в кабинет.",
        "",
        "Диагностику клиента и вход в кабинет ведите в боте «Стаж и пенсия».",
    ]
    if admin:
        lines.extend(["", f"Кабинет сотрудников: {admin}"])
    if client_bot:
        lines.extend(["", f"Бот для клиентов: {client_bot}"])
    return "\n".join(lines)


def handle_ops_update(
    update: dict[str, Any],
    *,
    bot: MaxBotClient | None = None,
) -> MaxHandleResult:
    """
    Узкий обработчик ops-бота:
    approve staff, /start с подсказкой; без клиентского intake.
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
    lower = text.lower()
    manager_ticket = parse_manager_callback(callback)

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
    if lower in {"привет", "здравствуйте", "добрый день", "доброе утро", "добрый вечер", "hi", "hello"}:
        reply = _ops_welcome_text()
        _reply(bot, user_id=user_id, chat_id=chat_id, text=reply)
        return MaxHandleResult(ok=True, action="ops_greeting", reply=reply)

    settings = get_settings()
    client_bot = (settings.max_chat_url or "").strip()
    reply = (
        "Это служебный бот для сотрудников.\n"
        "Для диагностики и входа клиента откройте бот «Стаж и пенсия»"
        + (f":\n{client_bot}" if client_bot else ".")
    )
    _reply(bot, user_id=user_id, chat_id=chat_id, text=reply)
    return MaxHandleResult(ok=True, action="ops_redirect_client", reply=reply)
