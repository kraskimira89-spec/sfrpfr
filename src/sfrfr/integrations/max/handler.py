"""Обработка апдейтов MAX → кейс SFRFR."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from sfrfr.core.case_store import get_case_store
from sfrfr.core.config import get_settings
from sfrfr.core.copy import POSITION_SHORT
from sfrfr.integrations.max.attachments import download_file, extract_downloadable_files
from sfrfr.integrations.max.channel_ids import remember_chat_id
from sfrfr.integrations.max.client import (
    MaxBotClient,
    inline_callback_keyboard,
    inline_channel_choice_keyboard,
    inline_confirm_login_keyboard,
)
from sfrfr.integrations.max.intake import (
    CALL_OPERATOR_LABEL,
    DOCS_BASE_TEXT,
    DOCS_GOSUSLUGI_TEXT,
    DOCS_INFO_TEXT,
    DOCS_MISSING_TEXT,
    DOCS_SPECIAL_TEXT,
    DOCS_STAZH_TEXT,
    EMP_HOWTO_TEXT,
    FALLBACK_MENU_TEXT,
    ILS_HOWTO_MFC_TEXT,
    ILS_HOWTO_TEXT,
    OPERATOR_CONFIRM_TEXT,
    SUMMARY_TEXT,
    UPLOAD_BLOCKED_TEXT,
    WELCOME_TEXT,
    cabinet_urls_for_case,
    device_keyboard,
    device_question,
    docs_info_keyboard,
    docs_section_keyboard,
    emp_howto_keyboard,
    employment_keyboard,
    employment_question,
    format_welcome_text,
    free_text_nudge,
    get_intake_store,
    goal_keyboard,
    ils_howto_keyboard,
    ils_keyboard,
    ils_question,
    pension_keyboard,
    pension_question,
    problem_keyboard,
    problem_question,
    problem_type_for_goal,
    summary_keyboard,
    upload_blocked_keyboard,
    whom_keyboard,
)
from sfrfr.models.case_status import CaseStatus, status_label_ru
from sfrfr.ops.auth_log import auth_event
from sfrfr.security.login_otp import (
    CONFIRM_WEB_LOGIN_CALLBACK,
    CONFIRM_WEB_LOGIN_LABEL,
    GET_CODE_CALLBACK,
    GET_CODE_IN_BROWSER_LABEL,
    OPEN_CABINET_BUTTON_LABEL,
    START_DIALOG_CALLBACK,
    START_DIALOG_LABEL,
    ask_code_from_login_page,
    cabinet_login_with_verify_url,
    channel_choice_after_login_message,
    confirm_web_login_message,
    issue_login_link,
    login_code_message,
)
from sfrfr.security.login_pending import (
    approve,
    attach_otp_verify_ticket,
    bind_max_by_code,
    ensure_pending_for_max,
    get_pending,
    latest_for_max,
    manager_callback_payload_for,
    mark_manager_notified,
    mark_pending_manager,
    parse_confirm_callback,
    parse_manager_callback,
)
from sfrfr.storage.local import save_upload

logger = logging.getLogger(__name__)


@dataclass
class MaxHandleResult:
    ok: bool
    action: str
    case_id: str | None = None
    reply: str | None = None
    detail: str = ""


_LOGIN_TRIGGERS = frozenset(
    {
        "/login",
        "войти",
        "вход",
        CONFIRM_WEB_LOGIN_LABEL.lower(),
        GET_CODE_IN_BROWSER_LABEL.lower(),
        "получить код",
        "получить код для входа",
        "подтвердить вход",
        CONFIRM_WEB_LOGIN_CALLBACK,
        GET_CODE_CALLBACK,
        "confirm_web_login",
        "get_login_code",
    }
)

_START_TRIGGERS = frozenset(
    {
        "/start",
        "старт",
        "начать",
        START_DIALOG_LABEL.lower(),
        START_DIALOG_CALLBACK,
    }
)


def _user_id(update: dict[str, Any]) -> str | None:
    for key in ("user_id", "sender_id", "from_id"):
        if key in update and update[key] is not None:
            return str(update[key])
    callback = update.get("callback") or {}
    if isinstance(callback, dict):
        user = callback.get("user") or callback.get("from") or {}
        if isinstance(user, dict) and user.get("user_id") is not None:
            return str(user["user_id"])
        if callback.get("user_id") is not None:
            return str(callback["user_id"])
    message = update.get("message") or update.get("message_created") or {}
    if isinstance(message, dict):
        sender = message.get("sender") or message.get("from") or {}
        if isinstance(sender, dict) and sender.get("user_id") is not None:
            return str(sender["user_id"])
        if message.get("user_id") is not None:
            return str(message["user_id"])
    user = update.get("user") or {}
    if isinstance(user, dict) and user.get("user_id") is not None:
        return str(user["user_id"])
    return None


def _user_dict(update: dict[str, Any]) -> dict[str, Any]:
    for key in ("user", "sender", "from"):
        raw = update.get(key)
        if isinstance(raw, dict) and raw:
            return raw
    callback = update.get("callback") or {}
    if isinstance(callback, dict):
        for key in ("user", "from"):
            raw = callback.get(key)
            if isinstance(raw, dict) and raw:
                return raw
    message = update.get("message") or update.get("message_created") or {}
    if isinstance(message, dict):
        for key in ("sender", "from", "user"):
            raw = message.get(key)
            if isinstance(raw, dict) and raw:
                return raw
    return {}


def _display_name_from_update(update: dict[str, Any], user_id: str | None = None) -> str | None:
    user = _user_dict(update)
    for key in ("first_name", "firstName", "name", "username"):
        val = user.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    last = user.get("last_name") or user.get("lastName")
    first = user.get("first_name") or user.get("firstName")
    if isinstance(first, str) and isinstance(last, str) and first.strip():
        return f"{first.strip()} {last.strip()}".strip()
    if user_id:
        row = _client_row_by_max(user_id)
        if row:
            full = (row.get("full_name") or "").strip()
            if full and not full.lower().startswith("max "):
                return full
    return None


def _welcome_for_update(update: dict[str, Any], user_id: str | None) -> str:
    return format_welcome_text(display_name=_display_name_from_update(update, user_id))

def _chat_id(update: dict[str, Any]) -> int | str | None:
    if update.get("chat_id") is not None:
        return update["chat_id"]
    callback = update.get("callback") or {}
    if isinstance(callback, dict):
        if callback.get("chat_id") is not None:
            return callback["chat_id"]
        msg = callback.get("message") or {}
        if isinstance(msg, dict) and msg.get("chat_id") is not None:
            return msg["chat_id"]
    message = update.get("message") or {}
    if isinstance(message, dict):
        if message.get("chat_id") is not None:
            return message["chat_id"]
        recipient = message.get("recipient") or {}
        if isinstance(recipient, dict) and recipient.get("chat_id") is not None:
            return recipient["chat_id"]
    recipient = update.get("recipient") or {}
    if isinstance(recipient, dict) and recipient.get("chat_id") is not None:
        return recipient["chat_id"]
    chat = update.get("chat")
    if isinstance(chat, dict) and chat.get("chat_id") is not None:
        return chat["chat_id"]
    if isinstance(chat, dict) and chat.get("id") is not None:
        return chat["id"]
    return None


def _looks_like_channel_update(update: dict[str, Any]) -> bool:
    """Эвристика: событие из канала (не личный диалог)."""
    for key in ("chat", "recipient", "message"):
        block = update.get(key)
        if isinstance(block, dict):
            chat_type = str(block.get("type") or block.get("chat_type") or "").upper()
            if chat_type in {"CHANNEL", "CHAT"}:
                return True
            nested = block.get("chat") or block.get("recipient")
            if isinstance(nested, dict):
                nested_type = str(nested.get("type") or nested.get("chat_type") or "").upper()
                if nested_type in {"CHANNEL", "CHAT"}:
                    return True
    return False


def _text(update: dict[str, Any]) -> str:
    message = update.get("message") or update.get("message_created") or update
    if not isinstance(message, dict):
        return ""
    body = message.get("body") or message.get("text") or ""
    if isinstance(body, dict):
        return str(body.get("text") or "")
    return str(body or "")


def _callback_payload(update: dict[str, Any]) -> str:
    """payload/data из message_callback."""
    update_type = str(update.get("update_type") or update.get("type") or "")
    for key in ("callback", "message_callback"):
        block = update.get(key)
        if isinstance(block, dict):
            raw = block.get("payload") or block.get("data") or block.get("callback_data")
            if raw is not None:
                return str(raw).strip()
    if "callback" in update_type or update.get("callback_id") is not None:
        raw = update.get("payload") or update.get("data") or update.get("callback_data")
        if raw is not None:
            return str(raw).strip()
    return ""


def _callback_id(update: dict[str, Any]) -> str:
    """callback_id для POST /answers."""
    for key in ("callback", "message_callback"):
        block = update.get(key)
        if isinstance(block, dict) and block.get("callback_id") is not None:
            return str(block["callback_id"]).strip()
    if update.get("callback_id") is not None:
        return str(update["callback_id"]).strip()
    return ""


def _reply(
    bot: MaxBotClient,
    *,
    user_id: str | None,
    chat_id: int | str | None,
    text: str,
    attachments: list[dict[str, Any]] | None = None,
) -> bool:
    try:
        bot.send_message(
            text=text,
            user_id=user_id,
            chat_id=chat_id,
            attachments=attachments,
        )
        return True
    except Exception as exc:  # noqa: BLE001
        import logging

        logging.getLogger(__name__).warning(
            "max_reply_failed user_id=%s chat_id=%s err=%s",
            user_id,
            chat_id,
            exc,
        )
        return False


def _login_menu_keyboard() -> list[dict[str, Any]]:
    # Без ticket — подтвердит последнюю сессию с ПК для этого max_user_id
    return inline_callback_keyboard(CONFIRM_WEB_LOGIN_LABEL, CONFIRM_WEB_LOGIN_CALLBACK)


def _start_dialog_keyboard() -> list[dict[str, Any]]:
    return inline_callback_keyboard(START_DIALOG_LABEL, START_DIALOG_CALLBACK)


def _channel_choice_text() -> str:
    return channel_choice_after_login_message()


def _reply_need_start(
    bot: MaxBotClient,
    *,
    user_id: str,
    chat_id: int | str | None,
    welcome_text: str | None = None,
) -> MaxHandleResult:
    """Просьба начать диалог — стартовое меню диагностики."""
    return _handle_bot_start(
        bot,
        user_id=user_id,
        chat_id=chat_id,
        store=get_case_store(),
        welcome_text=welcome_text,
    )


def _ensure_client_row(max_user_id: str) -> dict[str, Any] | None:
    """Гарантированно получить/создать строку clients для max_user_id."""
    import logging

    log = logging.getLogger(__name__)
    try:
        from sfrfr.db.client_channels import ClientChannelRepository

        return ClientChannelRepository().ensure_for_max_user(str(max_user_id))
    except Exception as exc:  # noqa: BLE001
        log.exception("ensure_client_row_failed max=%s: %s", max_user_id, exc)
        return _client_row_by_max(max_user_id)


def _ensure_supabase_max_client(max_user_id: str) -> None:
    """Неблокирующая регистрация клиента MAX в Supabase (единый профиль ТЗ-09)."""
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_service_role_key:
        return

    import threading

    def _work() -> None:
        try:
            from sfrfr.db.client_channels import ClientChannelRepository

            ClientChannelRepository().ensure_for_max_user(str(max_user_id))
        except Exception:
            import logging

            logging.getLogger(__name__).exception(
                "ensure_supabase_max_client_failed max=%s", max_user_id
            )

    threading.Thread(target=_work, daemon=True, name="max-ensure-client").start()


def _resume_pending_confirm_if_any(
    bot: MaxBotClient,
    *,
    user_id: str,
    chat_id: int | str | None,
) -> MaxHandleResult | None:
    """Если вход уже ждёт подтверждения — сразу завершить (без лишней кнопки)."""
    pending = latest_for_max(user_id)
    if pending is None or pending.status != "pending_confirm":
        return None
    return _complete_pc_login(
        bot,
        user_id=user_id,
        chat_id=chat_id,
        ticket_id=pending.ticket_id,
    )


def _ensure_case_for_intake(
    *,
    user_id: str,
    chat_id: int | str | None,
    intake,
    store,
) -> str:
    """Создать или найти дело только при переходе в кабинет / вызове оператора."""
    if intake.case_id:
        return str(intake.case_id)

    # Локальный store — быстрый путь (тесты / fallback).
    existing = store.find_by_max_user(user_id)
    if existing:
        intake.case_id = existing.case_id
        get_intake_store().save(intake)
        return existing.case_id

    supabase_case = _try_create_supabase_case(user_id=user_id, intake=intake)
    if supabase_case:
        case_id, client_id = supabase_case
        intake.case_id = case_id
        intake.client_id = client_id
        get_intake_store().save(intake)
        record = store.create(
            client_name=f"MAX user {user_id}",
            snils_masked="***-***-*** **",
            consent_given=False,
        )
        # Сохраняем локальную привязку; id может отличаться — для бота важен bind_max.
        store.bind_max(
            record.case_id,
            max_user_id=user_id,
            max_chat_id=str(chat_id) if chat_id is not None else None,
        )
        # Предпочитаем supabase case_id в deep-link.
        intake.case_id = case_id
        get_intake_store().save(intake)
        return case_id

    record = store.create(
        client_name=f"MAX user {user_id}",
        snils_masked="***-***-*** **",
        consent_given=False,
    )
    store.bind_max(
        record.case_id,
        max_user_id=user_id,
        max_chat_id=str(chat_id) if chat_id is not None else None,
    )
    intake.case_id = record.case_id
    get_intake_store().save(intake)
    return record.case_id


def _try_create_supabase_case(*, user_id: str, intake) -> tuple[str, str] | None:
    """Best-effort создание дела в Postgres с коротким таймаутом."""
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_service_role_key:
        return None

    from concurrent.futures import ThreadPoolExecutor
    from concurrent.futures import TimeoutError as FuturesTimeout

    def _work() -> tuple[str, str] | None:
        client_row = _ensure_client_row(user_id)
        if not client_row or not client_row.get("id"):
            return None
        from sfrfr.db.case_repository import CaseRepository
        from sfrfr.db.session import get_supabase_client

        client_id = str(client_row["id"])
        sb = get_supabase_client()
        open_rows = (
            sb.table("cases")
            .select("id")
            .eq("client_id", client_id)
            .neq("pipeline_status", "closed")
            .order("created_at", desc=True)
            .limit(1)
            .execute()
            .data
            or []
        )
        if open_rows:
            return str(open_rows[0]["id"]), client_id
        created = CaseRepository().create_case_for_client(
            client_id=client_id,
            actor_id=None,
            problem_type=problem_type_for_goal(intake.goal),
        )
        return str(created["id"]), client_id

    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(_work).result(timeout=2.5)
    except (FuturesTimeout, Exception):
        import logging

        logging.getLogger(__name__).warning("ensure_case_supabase_timeout_or_error max=%s", user_id)
        return None


def _notify_operator_amocrm(*, user_id: str, intake, case_id: str | None) -> None:
    try:
        from sfrfr.integrations.amocrm import sync_case_to_amocrm

        sync_case_to_amocrm(
            case_id=case_id or f"max-intake-{intake.id}",
            b2c_status="lead",
            pipeline_status="intake",
            full_name=f"MAX {user_id}",
            channel="max_chat",
            source="max_intake_operator",
            consent=False,
            task="Продолжить диалог MAX",
        )
    except Exception:
        import logging

        logging.getLogger(__name__).exception("max_operator_amocrm_failed max=%s", user_id)


def _handle_operator(
    bot: MaxBotClient,
    *,
    user_id: str,
    chat_id: int | str | None,
    store,
    intake=None,
) -> MaxHandleResult:
    intake_store = get_intake_store()
    if intake is None:
        intake = intake_store.upsert_started(user_id)
    if intake.goal is None:
        intake.goal = "operator"
    step = intake.step()
    case_id = _ensure_case_for_intake(user_id=user_id, chat_id=chat_id, intake=intake, store=store)
    from datetime import UTC, datetime

    intake.status = "handed_to_operator"
    intake.completed_at = datetime.now(UTC).isoformat()
    intake_store.save(intake)
    _notify_operator_amocrm(user_id=user_id, intake=intake, case_id=case_id)
    _reply(bot, user_id=user_id, chat_id=chat_id, text=OPERATOR_CONFIRM_TEXT)
    return MaxHandleResult(
        ok=True,
        action="max_operator_requested",
        case_id=case_id,
        reply=OPERATOR_CONFIRM_TEXT,
        detail=step,
    )


def _show_summary(
    bot: MaxBotClient,
    *,
    user_id: str,
    chat_id: int | str | None,
    store,
    intake,
) -> MaxHandleResult:
    from datetime import UTC, datetime

    case_id = _ensure_case_for_intake(user_id=user_id, chat_id=chat_id, intake=intake, store=store)
    intake.status = "completed"
    intake.completed_at = datetime.now(UTC).isoformat()
    get_intake_store().save(intake)
    max_url, web_url = cabinet_urls_for_case(case_id)
    attachments = summary_keyboard(
        device=intake.device_preference,
        cabinet_max_url=max_url,
        cabinet_web_url=web_url,
    )
    _reply(
        bot,
        user_id=user_id,
        chat_id=chat_id,
        text=SUMMARY_TEXT,
        attachments=attachments,
    )
    return MaxHandleResult(
        ok=True,
        action="max_intake_completed",
        case_id=case_id,
        reply=SUMMARY_TEXT,
    )


def _ask_next_after_goal(
    bot: MaxBotClient,
    *,
    user_id: str,
    chat_id: int | str | None,
    store,
    intake,
) -> MaxHandleResult:
    if intake.goal == "operator":
        return _handle_operator(bot, user_id=user_id, chat_id=chat_id, store=store, intake=intake)
    _reply(
        bot,
        user_id=user_id,
        chat_id=chat_id,
        text=ils_question(),
        attachments=ils_keyboard(),
    )
    return MaxHandleResult(
        ok=True,
        action="max_goal_selected",
        case_id=intake.case_id,
        reply=ils_question(),
        detail=str(intake.goal),
    )


def _show_ils_howto(
    bot: MaxBotClient,
    *,
    user_id: str,
    chat_id: int | str | None,
    text: str | None = None,
) -> MaxHandleResult:
    reply = text or ILS_HOWTO_TEXT
    _reply(
        bot,
        user_id=user_id,
        chat_id=chat_id,
        text=reply,
        attachments=ils_howto_keyboard(),
    )
    return MaxHandleResult(ok=True, action="ils_howto", reply=reply)


def _continue_after_ils(
    bot: MaxBotClient,
    *,
    user_id: str,
    chat_id: int | str | None,
    store,
    intake,
) -> MaxHandleResult:
    """Следующий шаг после ответа про ИЛС (или после инструкции Госуслуг)."""
    intake_store = get_intake_store()
    # Новый поток §10.1: после ИЛС сразу устройство (без employment)
    if intake.for_whom is not None or intake.problem_type is not None:
        _reply(
            bot,
            user_id=user_id,
            chat_id=chat_id,
            text=device_question(),
            attachments=device_keyboard(),
        )
        return MaxHandleResult(ok=True, action="intake_ils", reply=device_question())
    if intake.goal == "sfr_question":
        intake.device_preference = intake.device_preference or "max"
        intake_store.save(intake)
        return _show_summary(bot, user_id=user_id, chat_id=chat_id, store=store, intake=intake)
    _reply(
        bot,
        user_id=user_id,
        chat_id=chat_id,
        text=employment_question(),
        attachments=employment_keyboard(),
    )
    return MaxHandleResult(ok=True, action="intake_ils", reply=employment_question())


def _continue_after_emp(
    bot: MaxBotClient,
    *,
    user_id: str,
    chat_id: int | str | None,
    store,
    intake,
) -> MaxHandleResult:
    _reply(
        bot,
        user_id=user_id,
        chat_id=chat_id,
        text=device_question(),
        attachments=device_keyboard(),
    )
    return MaxHandleResult(ok=True, action="intake_emp", reply=device_question())


def _handle_intake_callback(
    bot: MaxBotClient,
    *,
    user_id: str,
    chat_id: int | str | None,
    store,
    payload: str,
) -> MaxHandleResult | None:
    if not payload.startswith("intake:"):
        return None
    intake_store = get_intake_store()
    intake = intake_store.get_active(user_id) or intake_store.upsert_started(user_id)
    parts = payload.split(":")
    kind = parts[1] if len(parts) > 1 else ""
    value = parts[2] if len(parts) > 2 else ""

    if kind == "restart":
        intake = intake_store.restart(user_id)
        text = format_welcome_text()
        _reply(
            bot,
            user_id=user_id,
            chat_id=chat_id,
            text=text,
            attachments=whom_keyboard(),
        )
        return MaxHandleResult(ok=True, action="max_intake_restart", reply=text)

    if kind == "operator" or payload == "intake:goal:operator":
        if kind == "goal":
            intake.goal = "operator"
            intake_store.save(intake)
        return _handle_operator(bot, user_id=user_id, chat_id=chat_id, store=store, intake=intake)

    if kind == "docs_info" or (kind == "docs" and value == "menu"):
        case_id = intake.case_id
        if case_id:
            max_url, web_url = cabinet_urls_for_case(case_id)
        else:
            max_url = get_settings().max_miniapp_url or get_settings().cabinet_public_url
            web_url = get_settings().cabinet_public_url
        _reply(
            bot,
            user_id=user_id,
            chat_id=chat_id,
            text=DOCS_INFO_TEXT,
            attachments=docs_info_keyboard(
                cabinet_max_url=max_url, cabinet_web_url=web_url
            ),
        )
        return MaxHandleResult(ok=True, action="docs_info", case_id=case_id, reply=DOCS_INFO_TEXT)

    if kind == "docs" and value in {
        "base",
        "stazh",
        "special",
        "gosuslugi",
        "missing",
        "ils_howto",
    }:
        texts = {
            "base": DOCS_BASE_TEXT,
            "stazh": DOCS_STAZH_TEXT,
            "special": DOCS_SPECIAL_TEXT,
            "gosuslugi": DOCS_GOSUSLUGI_TEXT,
            "missing": DOCS_MISSING_TEXT,
            "ils_howto": ILS_HOWTO_TEXT,
        }
        reply = texts[value]
        attachments = (
            ils_howto_keyboard() if value == "ils_howto" else docs_section_keyboard()
        )
        _reply(
            bot,
            user_id=user_id,
            chat_id=chat_id,
            text=reply,
            attachments=attachments,
        )
        return MaxHandleResult(
            ok=True, action=f"docs_{value}", case_id=intake.case_id, reply=reply
        )

    if kind == "back":
        step = intake.step()
        if step == "ils_howto":
            intake.ils_available = None
            intake.ils_howto_done = False
            intake_store.save(intake)
            _reply(
                bot,
                user_id=user_id,
                chat_id=chat_id,
                text=ils_question(),
                attachments=ils_keyboard(),
            )
            return MaxHandleResult(ok=True, action="intake_back", reply=ils_question())
        if step == "emp_howto":
            intake.employment_records_available = None
            intake.emp_howto_done = False
            intake_store.save(intake)
            _reply(
                bot,
                user_id=user_id,
                chat_id=chat_id,
                text=employment_question(),
                attachments=employment_keyboard(),
            )
            return MaxHandleResult(ok=True, action="intake_back", reply=employment_question())
        if step == "device":
            intake.device_preference = None
            # Новый поток: назад к инструкции ИЛС или к вопросу про ИЛС
            if intake.for_whom is not None or intake.problem_type is not None:
                if intake.ils_available in {"need", "no", "unknown"}:
                    intake.ils_howto_done = False
                    intake_store.save(intake)
                    return _show_ils_howto(bot, user_id=user_id, chat_id=chat_id)
                intake.ils_available = None
                intake.ils_howto_done = False
                intake_store.save(intake)
                _reply(
                    bot,
                    user_id=user_id,
                    chat_id=chat_id,
                    text=ils_question(),
                    attachments=ils_keyboard(),
                )
                return MaxHandleResult(ok=True, action="intake_back", reply=ils_question())
            # Legacy: назад к трудовым документам / howto
            if intake.employment_records_available == "no":
                intake.emp_howto_done = False
                intake_store.save(intake)
                _reply(
                    bot,
                    user_id=user_id,
                    chat_id=chat_id,
                    text=EMP_HOWTO_TEXT,
                    attachments=emp_howto_keyboard(),
                )
                return MaxHandleResult(ok=True, action="intake_back", reply=EMP_HOWTO_TEXT)
            intake.employment_records_available = None
            intake.emp_howto_done = False
            intake_store.save(intake)
            _reply(
                bot,
                user_id=user_id,
                chat_id=chat_id,
                text=employment_question(),
                attachments=employment_keyboard(),
            )
            return MaxHandleResult(ok=True, action="intake_back", reply=employment_question())
        if step == "ils":
            if intake.for_whom is not None:
                intake.problem_type = None
                intake.goal = None
                intake_store.save(intake)
                _reply(
                    bot,
                    user_id=user_id,
                    chat_id=chat_id,
                    text=problem_question(),
                    attachments=problem_keyboard(),
                )
                return MaxHandleResult(ok=True, action="intake_back", reply=problem_question())
            intake.ils_available = None
            intake.ils_howto_done = False
            intake.employment_records_available = None
            intake.emp_howto_done = False
            intake.device_preference = None
            intake_store.save(intake)
            _reply(
                bot,
                user_id=user_id,
                chat_id=chat_id,
                text=ils_question(),
                attachments=ils_keyboard(),
            )
            return MaxHandleResult(ok=True, action="intake_back", reply=ils_question())
        if step == "problem":
            intake.pension_status = None
            intake_store.save(intake)
            _reply(
                bot,
                user_id=user_id,
                chat_id=chat_id,
                text=pension_question(),
                attachments=pension_keyboard(),
            )
            return MaxHandleResult(ok=True, action="intake_back", reply=pension_question())
        if step == "pension":
            intake.for_whom = None
            intake_store.save(intake)
            _reply(
                bot,
                user_id=user_id,
                chat_id=chat_id,
                text=WELCOME_TEXT,
                attachments=whom_keyboard(),
            )
            return MaxHandleResult(ok=True, action="intake_back", reply=WELCOME_TEXT)
        if step in {"employment", "summary"}:
            intake.ils_available = None
            intake.ils_howto_done = False
            intake.employment_records_available = None
            intake.emp_howto_done = False
            intake.device_preference = None
            intake_store.save(intake)
            _reply(
                bot,
                user_id=user_id,
                chat_id=chat_id,
                text=ils_question(),
                attachments=ils_keyboard(),
            )
            return MaxHandleResult(ok=True, action="intake_back", reply=ils_question())
        _reply(
            bot,
            user_id=user_id,
            chat_id=chat_id,
            text=WELCOME_TEXT,
            attachments=whom_keyboard(),
        )
        return MaxHandleResult(ok=True, action="intake_back", reply=WELCOME_TEXT)

    if kind == "whom" and value in {"self", "relative"}:
        intake.for_whom = value  # type: ignore[assignment]
        intake.pension_status = None
        intake.problem_type = None
        intake.goal = None
        intake.ils_available = None
        intake.ils_howto_done = False
        intake.device_preference = None
        intake.status = "started"
        intake_store.save(intake)
        _reply(
            bot,
            user_id=user_id,
            chat_id=chat_id,
            text=pension_question(),
            attachments=pension_keyboard(),
        )
        return MaxHandleResult(ok=True, action="intake_whom", reply=pension_question())

    if kind == "pension" and value in {"before", "assigned"}:
        intake.pension_status = value  # type: ignore[assignment]
        intake.problem_type = None
        intake.goal = None
        intake.ils_available = None
        intake.ils_howto_done = False
        intake.device_preference = None
        intake_store.save(intake)
        _reply(
            bot,
            user_id=user_id,
            chat_id=chat_id,
            text=problem_question(),
            attachments=problem_keyboard(),
        )
        return MaxHandleResult(ok=True, action="intake_pension", reply=problem_question())

    if kind == "problem" and value in {"ils_stazh", "north", "documents", "sfr_refusal"}:
        intake.problem_type = value  # type: ignore[assignment]
        intake.sync_goal_from_problem()
        intake.ils_available = None
        intake.ils_howto_done = False
        intake.device_preference = None
        intake_store.save(intake)
        _reply(
            bot,
            user_id=user_id,
            chat_id=chat_id,
            text=ils_question(),
            attachments=ils_keyboard(),
        )
        return MaxHandleResult(
            ok=True,
            action="intake_problem",
            reply=ils_question(),
            detail=str(intake.problem_type),
        )

    # Legacy goal payloads (старые кнопки / тесты)
    if kind == "goal" and value in {
        "check_experience",
        "missing_period",
        "sfr_question",
        "operator",
    }:
        intake.goal = value  # type: ignore[assignment]
        intake.ils_available = None
        intake.employment_records_available = None
        intake.device_preference = None
        intake.status = "started"
        intake_store.save(intake)
        return _ask_next_after_goal(
            bot, user_id=user_id, chat_id=chat_id, store=store, intake=intake
        )

    if kind == "ils" and value in {"yes", "no", "unknown", "need"}:
        intake.ils_available = value  # type: ignore[assignment]
        if value == "yes":
            intake.ils_howto_done = True
            intake_store.save(intake)
            return _continue_after_ils(
                bot, user_id=user_id, chat_id=chat_id, store=store, intake=intake
            )
        intake.ils_howto_done = False
        intake_store.save(intake)
        return _show_ils_howto(bot, user_id=user_id, chat_id=chat_id)

    if kind == "ils_guide" and value in {"done", "mfc"}:
        if value == "mfc":
            return _show_ils_howto(
                bot, user_id=user_id, chat_id=chat_id, text=ILS_HOWTO_MFC_TEXT
            )
        intake.ils_howto_done = True
        if intake.ils_available is None:
            intake.ils_available = "need"
        intake_store.save(intake)
        return _continue_after_ils(
            bot, user_id=user_id, chat_id=chat_id, store=store, intake=intake
        )

    if kind == "emp" and value in {"yes", "partial", "no"}:
        intake.employment_records_available = value  # type: ignore[assignment]
        if value == "no":
            intake.emp_howto_done = False
            intake_store.save(intake)
            _reply(
                bot,
                user_id=user_id,
                chat_id=chat_id,
                text=EMP_HOWTO_TEXT,
                attachments=emp_howto_keyboard(),
            )
            return MaxHandleResult(ok=True, action="emp_howto", reply=EMP_HOWTO_TEXT)
        intake.emp_howto_done = True
        intake_store.save(intake)
        return _continue_after_emp(
            bot, user_id=user_id, chat_id=chat_id, store=store, intake=intake
        )

    if kind == "emp_guide" and value == "done":
        intake.emp_howto_done = True
        if intake.employment_records_available is None:
            intake.employment_records_available = "no"
        intake_store.save(intake)
        return _continue_after_emp(
            bot, user_id=user_id, chat_id=chat_id, store=store, intake=intake
        )

    if kind == "device" and value in {"max", "web", "help"}:
        intake.device_preference = value  # type: ignore[assignment]
        intake_store.save(intake)
        if value == "help":
            return _handle_operator(
                bot, user_id=user_id, chat_id=chat_id, store=store, intake=intake
            )
        return _show_summary(bot, user_id=user_id, chat_id=chat_id, store=store, intake=intake)

    return MaxHandleResult(ok=False, action="intake_unknown", detail=payload)


def _handle_bot_start(
    bot: MaxBotClient,
    *,
    user_id: str,
    chat_id: int | str | None,
    store,
    welcome_text: str | None = None,
) -> MaxHandleResult:
    """Старт: меню диагностики без создания дела (ТЗ-20)."""
    resumed = _resume_pending_confirm_if_any(bot, user_id=user_id, chat_id=chat_id)
    if resumed is not None:
        return resumed

    _ensure_supabase_max_client(user_id)
    get_intake_store().upsert_started(user_id)
    text = welcome_text or WELCOME_TEXT
    _reply(
        bot,
        user_id=user_id,
        chat_id=chat_id,
        text=text,
        attachments=goal_keyboard(),
    )
    return MaxHandleResult(
        ok=True,
        action="max_intake_started",
        case_id=None,
        reply=text,
    )


def _client_row_by_max(max_user_id: str) -> dict[str, Any] | None:
    try:
        from sfrfr.db.session import get_supabase_client

        rows = (
            get_supabase_client()
            .table("clients")
            .select("*")
            .eq("max_user_id", str(max_user_id))
            .limit(1)
            .execute()
            .data
            or []
        )
        return rows[0] if rows else None
    except Exception:
        return None


def _auth_email_for_row(row: dict[str, Any], max_user_id: str) -> str:
    email = (row.get("email") or "").strip().lower()
    if email and "@" in email:
        return email
    return f"max_{max_user_id}@clients.sfrfr.local"


def _token_hash_for_email(email: str) -> str | None:
    """hashed_token magic link для указанного email (без создания клиента)."""
    try:
        from sfrfr.db.session import get_supabase_client
        from sfrfr.db.staff_roles import find_user_by_email

        normalized = email.strip().lower()
        if "@" not in normalized:
            return None
        client = get_supabase_client()
        if find_user_by_email(normalized) is None:
            client.auth.admin.create_user(
                {
                    "email": normalized,
                    "email_confirm": True,
                    "app_metadata": {"role_source": "staff_max_login"},
                }
            )
        link = client.auth.admin.generate_link({"type": "magiclink", "email": normalized})
        props = getattr(link, "properties", None)
        if props is None and isinstance(link, dict):
            props = link.get("properties") or link
        hashed = None
        if props is not None:
            hashed = getattr(props, "hashed_token", None) or (
                props.get("hashed_token") if isinstance(props, dict) else None
            )
        return str(hashed) if hashed else None
    except Exception:
        return None


def _token_hash_for_max(max_user_id: str) -> tuple[str, str] | None:
    """(email, token_hash) для Supabase session на ПК."""
    try:
        from sfrfr.db.session import get_supabase_client
        from sfrfr.db.staff_roles import find_user_by_email

        _ensure_supabase_max_client(max_user_id)
        row = _client_row_by_max(max_user_id)
        if not row:
            return None
        email = _auth_email_for_row(row, max_user_id)
        client = get_supabase_client()
        existing = find_user_by_email(email)
        if existing is None:
            client.auth.admin.create_user(
                {
                    "email": email,
                    "email_confirm": True,
                    "app_metadata": {"role_source": "max_otp_login"},
                }
            )
        hashed = _token_hash_for_email(email)
        if not hashed:
            return None
        return email, hashed
    except Exception:
        return None


def _notify_managers_staff_login(
    bot: MaxBotClient,
    *,
    pending,
) -> int:
    """Отправить руководителям кнопку одобрения через ops-бот (ТЗ-25)."""
    from sfrfr.db.staff_roles import list_manager_max_user_ids
    from sfrfr.integrations.max.ops_bot import get_ops_bot
    from sfrfr.security.login_otp import APPROVE_STAFF_LOGIN_LABEL

    # Служебные кнопки — всегда ops (fallback на клиентский токен, если ops не задан).
    _ = bot
    notify_bot = get_ops_bot()
    settings = get_settings()
    manager_ids = list_manager_max_user_ids(
        extra_ids=settings.staff_login_approver_max_user_ids,
    )
    chat_ids = [
        p.strip()
        for p in (settings.staff_login_approver_max_chat_ids or "").split(",")
        if p.strip()
    ]
    if not manager_ids and not chat_ids:
        return 0
    email = pending.staff_email or pending.contact or "сотрудник"
    text = (
        f"Запрос на вход сотрудника в кабинет.\n"
        f"Почта: {email}\n\n"
        f"Нажмите кнопку, чтобы разрешить вход."
    )
    attachments = inline_callback_keyboard(
        APPROVE_STAFF_LOGIN_LABEL,
        manager_callback_payload_for(pending.ticket_id),
    )
    sent = 0
    targets: list[str | None] = list(manager_ids) if manager_ids else [None] * max(1, len(chat_ids))
    for i, mid in enumerate(targets):
        cid = chat_ids[i] if i < len(chat_ids) else None
        try:
            notify_bot.send_message(
                text=text,
                user_id=str(mid) if mid else None,
                chat_id=cid,
                attachments=attachments,
            )
            sent += 1
        except Exception:
            # fallback: только chat_id
            if cid and mid:
                try:
                    notify_bot.send_message(
                        text=text, chat_id=cid, attachments=attachments
                    )
                    sent += 1
                except Exception:
                    continue
            continue
    if sent:
        mark_manager_notified(ticket_id=pending.ticket_id)
    return sent


def _complete_pc_login(
    bot: MaxBotClient,
    *,
    user_id: str,
    chat_id: int | str | None,
    ticket_id: str | None,
) -> MaxHandleResult:
    """Подтверждение с телефона → сессия для poll на ПК
    (клиент) или ожидание руководителя (staff)."""
    pending = None
    if ticket_id:
        pending = get_pending(ticket_id)
    if pending is None:
        pending = latest_for_max(user_id)
    if pending is None or pending.status not in {"pending_confirm", "pending_pair"}:
        reply = ask_code_from_login_page()
        _reply(bot, user_id=user_id, chat_id=chat_id, text=reply)
        return MaxHandleResult(ok=False, action="login_no_pending", reply=reply)

    if pending.status == "pending_pair" or not pending.max_user_id:
        # ещё не ввели код — привяжем текущего пользователя и сразу завершим вход
        row = _ensure_client_row(user_id)
        if not row:
            reply = "Не удалось связать аккаунт. Пришлите 6-значный код со страницы входа."
            _reply(bot, user_id=user_id, chat_id=chat_id, text=reply)
            return MaxHandleResult(ok=False, action="login_no_client", reply=reply)
        contact = _auth_email_for_row(row, user_id)
        pending = (
            bind_max_by_code(
                pair_code=pending.pair_code,
                max_user_id=user_id,
                contact=contact,
            )
            or pending
        )
        if pending.status != "pending_confirm":
            reply = ask_code_from_login_page()
            _reply(bot, user_id=user_id, chat_id=chat_id, text=reply)
            return MaxHandleResult(ok=False, action="login_need_code", reply=reply)

    # Staff: первый вход — руководитель; дальше тот же MAX входит сам
    if pending.audience == "staff":
        from sfrfr.db.staff_roles import (
            get_staff_role_by_email,
            is_staff_login_trusted,
        )

        staff_email = (pending.staff_email or "").strip().lower()
        if not staff_email or get_staff_role_by_email(staff_email) is None:
            reply = "Нет доступа. Обратитесь к администратору."
            _reply(bot, user_id=user_id, chat_id=chat_id, text=reply)
            return MaxHandleResult(ok=False, action="login_not_staff", reply=reply)

        if is_staff_login_trusted(email=staff_email, max_user_id=user_id):
            token_hash = _token_hash_for_email(staff_email)
            if not token_hash:
                reply = "Ошибка входа. Попробуйте позже."
                _reply(bot, user_id=user_id, chat_id=chat_id, text=reply)
                return MaxHandleResult(ok=False, action="login_token_failed", reply=reply)
            approved = approve(
                ticket_id=pending.ticket_id,
                token_hash=token_hash,
                email=staff_email,
            )
            if not approved:
                reply = "Сессия устарела. Начните вход снова на компьютере."
                _reply(bot, user_id=user_id, chat_id=chat_id, text=reply)
                return MaxHandleResult(ok=False, action="login_expired", reply=reply)
            reply = "Готово. Смотрите компьютер."
            _reply(bot, user_id=user_id, chat_id=chat_id, text=reply)
            return MaxHandleResult(ok=True, action="login_approved_trusted", reply=reply)

        waiting = mark_pending_manager(ticket_id=pending.ticket_id)
        if not waiting:
            reply = "Сессия устарела. Начните вход снова на компьютере."
            _reply(bot, user_id=user_id, chat_id=chat_id, text=reply)
            return MaxHandleResult(ok=False, action="login_expired", reply=reply)
        sent = _notify_managers_staff_login(bot, pending=waiting)
        if sent == 0:
            reply = "Нет руководителя в системе. Обратитесь к администратору."
            _reply(bot, user_id=user_id, chat_id=chat_id, text=reply)
            return MaxHandleResult(
                ok=True,
                action="login_pending_manager_no_approvers",
                reply=reply,
            )
        reply = "Ждите руководителя."
        _reply(bot, user_id=user_id, chat_id=chat_id, text=reply)
        return MaxHandleResult(ok=True, action="login_pending_manager", reply=reply)

    tokens = _token_hash_for_max(user_id)
    if not tokens:
        auth_event(
            "max_login",
            outcome="error",
            max_user_id=user_id,
            ticket=pending.ticket_id,
            reason="login_token_failed",
        )
        reply = "Ошибка входа. Попробуйте позже."
        _reply(bot, user_id=user_id, chat_id=chat_id, text=reply)
        return MaxHandleResult(ok=False, action="login_token_failed", reply=reply)
    email, token_hash = tokens
    approved = approve(ticket_id=pending.ticket_id, token_hash=token_hash, email=email)
    if not approved:
        auth_event(
            "max_login",
            outcome="denied",
            max_user_id=user_id,
            ticket=pending.ticket_id,
            reason="login_expired",
        )
        reply = "Сессия устарела. Начните вход снова на компьютере."
        _reply(bot, user_id=user_id, chat_id=chat_id, text=reply)
        return MaxHandleResult(ok=False, action="login_expired", reply=reply)

    auth_event(
        "max_login",
        outcome="ok",
        max_user_id=user_id,
        ticket=pending.ticket_id,
        status="approved",
    )
    _send_open_cabinet_link(bot, user_id=user_id, chat_id=chat_id, contact=email)
    reply = channel_choice_after_login_message()
    return MaxHandleResult(ok=True, action="login_approved", reply=reply)


def _approve_staff_by_manager(
    bot: MaxBotClient,
    *,
    user_id: str,
    chat_id: int | str | None,
    ticket_id: str,
) -> MaxHandleResult:
    """Руководитель разрешил вход сотрудника на ПК."""
    from sfrfr.db.staff_roles import (
        get_staff_role_by_email,
        list_manager_max_user_ids,
        trust_staff_login,
    )

    settings = get_settings()
    manager_ids = list_manager_max_user_ids(
        extra_ids=settings.staff_login_approver_max_user_ids,
    )
    if str(user_id) not in {str(m) for m in manager_ids}:
        reply = "Нет права на это действие."
        _reply(bot, user_id=user_id, chat_id=chat_id, text=reply)
        return MaxHandleResult(ok=False, action="manager_forbidden", reply=reply)

    pending = get_pending(ticket_id)
    if pending is None or pending.status != "pending_manager":
        reply = "Заявка уже обработана или устарела."
        _reply(bot, user_id=user_id, chat_id=chat_id, text=reply)
        return MaxHandleResult(ok=False, action="manager_no_pending", reply=reply)

    staff_email = (pending.staff_email or "").strip().lower()
    if not staff_email or get_staff_role_by_email(staff_email) is None:
        reply = "Сотрудник не найден."
        _reply(bot, user_id=user_id, chat_id=chat_id, text=reply)
        return MaxHandleResult(ok=False, action="manager_not_staff", reply=reply)

    token_hash = _token_hash_for_email(staff_email)
    if not token_hash:
        reply = "Ошибка входа. Попробуйте позже."
        _reply(bot, user_id=user_id, chat_id=chat_id, text=reply)
        return MaxHandleResult(ok=False, action="manager_token_failed", reply=reply)

    approved = approve(ticket_id=pending.ticket_id, token_hash=token_hash, email=staff_email)
    if not approved:
        reply = "Сессия устарела."
        _reply(bot, user_id=user_id, chat_id=chat_id, text=reply)
        return MaxHandleResult(ok=False, action="manager_expired", reply=reply)

    # Запомнить MAX сотрудника — следующие входы без руководителя
    employee_max = str(pending.max_user_id or "").strip()
    if employee_max:
        try:
            trust_staff_login(email=staff_email, max_user_id=employee_max)
        except Exception:
            pass

    reply = "Вход разрешён."
    _reply(bot, user_id=user_id, chat_id=chat_id, text=reply)
    # уведомить сотрудника в MAX, если известен
    if pending.max_user_id and str(pending.max_user_id) != str(user_id):
        try:
            bot.send_message(
                text="Вход разрешён. Смотрите экран компьютера.",
                user_id=str(pending.max_user_id),
            )
        except Exception:
            pass
    return MaxHandleResult(ok=True, action="manager_approved", reply=reply)


def _send_confirm_button(
    bot: MaxBotClient,
    *,
    user_id: str,
    chat_id: int | str | None,
    ticket_id: str,
) -> None:
    """Кнопка подтверждения: callback + link (если удалось выпустить URL)."""
    login_url: str | None = None
    try:
        _ensure_supabase_max_client(user_id)
        row = _client_row_by_max(user_id)
        if row:
            contact = _auth_email_for_row(row, user_id)
            login_url = issue_login_link(
                contact=contact,
                max_user_id=str(user_id),
            ).login_url
    except Exception as exc:  # noqa: BLE001
        import logging

        logging.getLogger(__name__).warning("max_login_link_failed: %s", exc)

    text = confirm_web_login_message()
    if login_url:
        text = f"{text}\n{login_url}"
    attachments = inline_confirm_login_keyboard(
        ticket_id=ticket_id,
        login_url=login_url,
        label=CONFIRM_WEB_LOGIN_LABEL,
    )
    ok = _reply(bot, user_id=user_id, chat_id=chat_id, text=text, attachments=attachments)
    if not ok:
        # запас: только callback без link
        _reply(
            bot,
            user_id=user_id,
            chat_id=chat_id,
            text=confirm_web_login_message(),
            attachments=inline_callback_keyboard(
                CONFIRM_WEB_LOGIN_LABEL,
                f"confirm_web_login|{ticket_id}",
            ),
        )


def _send_open_cabinet_link(
    bot: MaxBotClient,
    *,
    user_id: str,
    chat_id: int | str | None,
    contact: str,
) -> None:
    settings = get_settings()
    issued = issue_login_link(contact=contact, max_user_id=str(user_id))
    app_url = (settings.max_miniapp_url or settings.max_chat_url).rstrip("/") + "/"
    attachments = inline_channel_choice_keyboard(
        app_url=app_url,
        cabinet_url=issued.login_url,
    )
    _reply(
        bot,
        user_id=user_id,
        chat_id=chat_id,
        text=channel_choice_after_login_message(),
        attachments=attachments,
    )


def _issue_login_code_to_max(
    bot: MaxBotClient,
    *,
    user_id: str,
    chat_id: int | str | None,
) -> MaxHandleResult:
    """Выдать код в MAX для ввода на странице входа кабинета."""
    from sfrfr.integrations.max.client import inline_link_keyboard

    row = _ensure_client_row(user_id)
    if not row:
        reply = "Не удалось подготовить вход. Попробуйте ещё раз через минуту."
        _reply(bot, user_id=user_id, chat_id=chat_id, text=reply)
        return MaxHandleResult(ok=False, action="login_no_client", reply=reply)

    contact = _auth_email_for_row(row, user_id)
    pending = ensure_pending_for_max(max_user_id=user_id, contact=contact)
    try:
        issued = issue_login_link(contact=contact, max_user_id=user_id)
    except Exception as exc:  # noqa: BLE001
        logger.exception("issue_login_link failed max=%s: %s", user_id, exc)
        reply = "Не удалось создать код. Попробуйте позже."
        _reply(bot, user_id=user_id, chat_id=chat_id, text=reply)
        return MaxHandleResult(ok=False, action="login_code_failed", reply=reply)

    attach_otp_verify_ticket(
        ticket_id=pending.ticket_id,
        otp_verify_ticket=issued.ticket,
        otp_code=issued.code,
        max_user_id=user_id,
        contact=contact,
    )
    login_url = cabinet_login_with_verify_url(verify_ticket=issued.ticket)
    reply = login_code_message(code=issued.code, login_url=login_url)
    _reply(
        bot,
        user_id=user_id,
        chat_id=chat_id,
        text=reply,
        attachments=inline_link_keyboard(OPEN_CABINET_BUTTON_LABEL, login_url),
    )
    auth_event(
        "max_login_code",
        outcome="ok",
        max_user_id=user_id,
        ticket=pending.ticket_id,
        status="code_sent",
    )
    return MaxHandleResult(
        ok=True,
        action="login_code_sent",
        reply=reply,
        detail=pending.ticket_id,
    )


def _handle_pair_code(
    bot: MaxBotClient,
    *,
    user_id: str,
    chat_id: int | str | None,
    code: str,
) -> MaxHandleResult:
    """Legacy/staff: код с экрана ПК. Клиенту — выдать код для ввода на сайте."""
    row = _ensure_client_row(user_id)
    contact = (
        _auth_email_for_row(row, user_id)
        if row
        else f"max_{user_id}@clients.sfrfr.local"
    )
    pending = bind_max_by_code(
        pair_code=code, max_user_id=user_id, contact=contact
    )
    if pending and pending.audience == "staff":
        auth_event(
            "max_pair",
            outcome="ok",
            max_user_id=user_id,
            ticket=pending.ticket_id,
            status=pending.status,
        )
        return _complete_pc_login(
            bot,
            user_id=user_id,
            chat_id=chat_id,
            ticket_id=pending.ticket_id,
        )
    return _issue_login_code_to_max(bot, user_id=user_id, chat_id=chat_id)


def _send_confirm_web_login(
    bot: MaxBotClient,
    *,
    user_id: str,
    chat_id: int | str | None,
    callback_payload: str = "",
) -> MaxHandleResult:
    """Клиент: выдать код. Staff/confirm: завершить вход на ПК."""
    ticket_from_cb = parse_confirm_callback(callback_payload)
    if ticket_from_cb:
        return _complete_pc_login(
            bot, user_id=user_id, chat_id=chat_id, ticket_id=ticket_from_cb
        )
    pending = latest_for_max(user_id)
    if pending and pending.audience == "staff":
        return _complete_pc_login(
            bot, user_id=user_id, chat_id=chat_id, ticket_id=pending.ticket_id
        )
    return _issue_login_code_to_max(bot, user_id=user_id, chat_id=chat_id)


def _docs_request_text(*, has_docs: bool) -> str:
    if get_settings().app_env.strip().lower() == "production":
        return (
            "Загрузите документы в защищённом кабинете после подтверждения согласия. "
            "Через сообщения MAX документы не принимаются."
        )
    if has_docs:
        return "Пришлите следующий документ (PDF/JPG/PNG) или /run."
    return "Пришлите выписку ИЛС (PDF/JPG/PNG)."


def _draft_preview(record) -> str:  # noqa: ANN001 - CaseRecord
    draft = record.ctx.draft
    if not draft:
        return "Черновик ещё не готов. Пришлите документы, затем /run."
    body = (draft.body or "").strip()
    preview = body[:1500] + ("…" if len(body) > 1500 else "")
    title = draft.title or "Черновик заявления"
    return f"{title}\n\n{preview}"


def _ingest_bytes(store, record, file_name: str, data: bytes):  # noqa: ANN001
    path = save_upload(record.case_id, file_name, data)
    return store.add_document(record.case_id, str(path))


def handle_max_update(
    update: dict[str, Any],
    *,
    bot: MaxBotClient | None = None,
) -> MaxHandleResult:
    """
    Сценарий ТЗ-20:
    /start — диагностика без создания дела
    intake:* — цели и вопросы
    /login — вход в веб-кабинет по коду
    /cabinet /status /documents /help — меню вернувшегося клиента
    вложения в production — отказ + CTA кабинета
    """
    bot = bot or MaxBotClient()
    text = _text(update).strip()
    callback = _callback_payload(update)
    user_id = _user_id(update)
    chat_id = _chat_id(update)
    update_type = str(update.get("update_type") or update.get("type") or "").lower()
    lower = text.lower()
    confirm_cb = parse_confirm_callback(callback)
    manager_ticket = parse_manager_callback(callback)
    start_hit = (
        callback == START_DIALOG_CALLBACK or lower in _START_TRIGGERS or lower.startswith("/start")
    )
    login_hit = (
        confirm_cb is not None
        or lower in _LOGIN_TRIGGERS
        or lower.startswith("/login")
        or CONFIRM_WEB_LOGIN_LABEL.lower() in lower
    )

    # Канал/группа: chat_id из bot_added (GET /chats снят с июня 2026).
    if "bot_added" in update_type or update_type.endswith("bot_added"):
        entry = remember_chat_id(
            chat_id,
            source="webhook_bot_added",
            update_type=update_type,
        )
        logger.info("max_bot_added chat_id=%s user_id=%s", chat_id, user_id)
        return MaxHandleResult(
            ok=True,
            action="bot_added",
            detail=f"chat_id={chat_id}" if entry else "no chat_id",
        )
    if "bot_removed" in update_type:
        logger.info("max_bot_removed chat_id=%s user_id=%s", chat_id, user_id)
        return MaxHandleResult(ok=True, action="bot_removed", detail=f"chat_id={chat_id}")

    if chat_id is not None and _looks_like_channel_update(update):
        remember_chat_id(chat_id, source="webhook_channel_message", update_type=update_type)

    if not user_id:
        return MaxHandleResult(ok=False, action="ignore", detail="no user_id")

    store = get_case_store()
    welcome_text = _welcome_for_update(update, user_id)

    # Нажатие «Начать» в MAX приходит как bot_started — раньше падало в сухой fallback.
    if "bot_started" in update_type:
        return _handle_bot_start(
            bot,
            user_id=user_id,
            chat_id=chat_id,
            store=store,
            welcome_text=welcome_text,
        )

    if manager_ticket:
        return _approve_staff_by_manager(
            bot,
            user_id=user_id,
            chat_id=chat_id,
            ticket_id=manager_ticket,
        )

    if start_hit:
        return _handle_bot_start(
            bot,
            user_id=user_id,
            chat_id=chat_id,
            store=store,
            welcome_text=welcome_text,
        )

    intake_result = _handle_intake_callback(
        bot,
        user_id=user_id,
        chat_id=chat_id,
        store=store,
        payload=callback,
    )
    if intake_result is not None:
        return intake_result

    if callback.startswith("review:"):
        from sfrfr.integrations.max.review_flow import handle_review_callback

        review = handle_review_callback(user_id=user_id, payload=callback)
        if review is not None:
            text = str(review.get("text") or "")
            _reply(
                bot,
                user_id=user_id,
                chat_id=chat_id,
                text=text,
                attachments=review.get("attachments"),
            )
            return MaxHandleResult(ok=True, action="review_flow", reply=text)

    if lower in {CALL_OPERATOR_LABEL.lower(), "позвать специалиста", "оператор"}:
        return _handle_operator(bot, user_id=user_id, chat_id=chat_id, store=store)

    if login_hit:
        return _send_confirm_web_login(
            bot,
            user_id=user_id,
            chat_id=chat_id,
            callback_payload=callback,
        )

    # Код с экрана компьютера (6 цифр), допускаем короткие фразы вокруг
    digits_only = "".join(ch for ch in text if ch.isdigit())
    compact = "".join(ch for ch in text if not ch.isspace())
    if len(digits_only) == 6 and len(compact) <= 24:
        return _handle_pair_code(bot, user_id=user_id, chat_id=chat_id, code=digits_only)

    intake = get_intake_store().get_active(user_id)
    record = store.find_by_max_user(user_id)

    # Если уже ждём кнопку подтверждения — не теряем пользователя
    resumed = _resume_pending_confirm_if_any(bot, user_id=user_id, chat_id=chat_id)
    if resumed is not None and not lower.startswith("/"):
        return resumed

    if lower.startswith("/help") or lower in {"помощь", "канал"}:
        pending = latest_for_max(user_id)
        if pending is not None and pending.status == "pending_confirm":
            return _complete_pc_login(
                bot,
                user_id=user_id,
                chat_id=chat_id,
                ticket_id=pending.ticket_id,
            )
        reply = (
            "Команды: /start — диагностика, /cabinet — кабинет, "
            "/documents — какие документы нужны, /status — статус дела, "
            f"/login — вход с компьютера. Всегда можно позвать специалиста. {POSITION_SHORT}"
        )
        _reply(
            bot,
            user_id=user_id,
            chat_id=chat_id,
            text=reply,
            attachments=goal_keyboard() if intake is None or intake.goal is None else None,
        )
        return MaxHandleResult(
            ok=True,
            action="help",
            case_id=(intake.case_id if intake else None) or (record.case_id if record else None),
            reply=reply,
        )

    if lower.startswith("/cabinet") or lower.startswith("/web"):
        if intake is None:
            intake = get_intake_store().upsert_started(user_id)
        case_id = _ensure_case_for_intake(
            user_id=user_id, chat_id=chat_id, intake=intake, store=store
        )
        max_url, web_url = cabinet_urls_for_case(case_id)
        reply = (
            "Откройте личный кабинет для документов. "
            "В личном кабинете документы передаются защищённо. Это займёт 2–3 минуты. "
            f"{POSITION_SHORT}"
        )
        _reply(
            bot,
            user_id=user_id,
            chat_id=chat_id,
            text=reply,
            attachments=upload_blocked_keyboard(cabinet_max_url=max_url, cabinet_web_url=web_url),
        )
        return MaxHandleResult(ok=True, action="cabinet_links", case_id=case_id, reply=reply)

    if (
        lower.startswith("/docs")
        or lower.startswith("/documents")
        or lower in {"документы", "что прислать"}
    ):
        if intake is None:
            intake = get_intake_store().upsert_started(user_id)
        reply = DOCS_INFO_TEXT
        docs_case_id: str | None = (intake.case_id if intake else None) or (
            record.case_id if record else None
        )
        if docs_case_id:
            max_url, web_url = cabinet_urls_for_case(docs_case_id)
        else:
            max_url = get_settings().max_miniapp_url or get_settings().cabinet_public_url
            web_url = get_settings().cabinet_public_url
        _reply(
            bot,
            user_id=user_id,
            chat_id=chat_id,
            text=reply,
            attachments=docs_info_keyboard(
                cabinet_max_url=max_url, cabinet_web_url=web_url
            ),
        )
        return MaxHandleResult(
            ok=True, action="docs_request", case_id=docs_case_id, reply=reply
        )

    if record is None:
        # Уже был /start, но дело ещё не создано — не гоняем полный welcome снова.
        if text and intake is not None:
            reply, attachments = free_text_nudge(intake=intake)
            _reply(
                bot,
                user_id=user_id,
                chat_id=chat_id,
                text=reply,
                attachments=attachments,
            )
            return MaxHandleResult(
                ok=True,
                action="free_text_nudge",
                case_id=None,
                reply=reply,
            )
        return _reply_need_start(
            bot, user_id=user_id, chat_id=chat_id, welcome_text=welcome_text
        )

    if lower.startswith("/draft"):
        reply = _draft_preview(record)
        _reply(bot, user_id=user_id, chat_id=chat_id, text=reply)
        return MaxHandleResult(
            ok=bool(record.ctx.draft),
            action="draft",
            case_id=record.case_id,
            reply=reply,
        )

    if lower.startswith("/status"):
        reply = (
            f"{status_label_ru(record.ctx.status)}. "
            f"Документов: {len(record.ctx.document_paths)}. "
            f"Дальше: /documents или /cabinet. {POSITION_SHORT}"
        )
        _reply(bot, user_id=user_id, chat_id=chat_id, text=reply)
        return MaxHandleResult(ok=True, action="status", case_id=record.case_id, reply=reply)

    if lower.startswith("/run"):
        if not record.ctx.document_paths and not record.ctx.ocr_texts:
            reply = (
                "Сначала загрузите документ в защищённом кабинете."
                if get_settings().app_env.strip().lower() == "production"
                else "Сначала пришлите документ."
            )
            _reply(bot, user_id=user_id, chat_id=chat_id, text=reply)
            return MaxHandleResult(
                ok=False,
                action="run_blocked",
                case_id=record.case_id,
                reply=reply,
            )
        updated = store.run_until(record.case_id, stop_at=CaseStatus.HUMAN_REVIEW)
        draft_note = " Откройте /draft." if updated.ctx.draft else ""
        reply = f"Готово: {status_label_ru(updated.ctx.status)}.{draft_note}"
        _reply(bot, user_id=user_id, chat_id=chat_id, text=reply)
        return MaxHandleResult(ok=True, action="run", case_id=record.case_id, reply=reply)

    file_name = update.get("file_name")
    file_bytes = update.get("file_bytes")
    downloads = extract_downloadable_files(update)
    is_production = get_settings().app_env.strip().lower() == "production"
    if is_production and (isinstance(file_bytes, (bytes, bytearray)) or bool(downloads)):
        case_id = record.case_id
        max_url, web_url = cabinet_urls_for_case(case_id)
        _reply(
            bot,
            user_id=user_id,
            chat_id=chat_id,
            text=UPLOAD_BLOCKED_TEXT,
            attachments=upload_blocked_keyboard(cabinet_max_url=max_url, cabinet_web_url=web_url),
        )
        return MaxHandleResult(
            ok=False,
            action="upload_blocked",
            case_id=case_id,
            reply=UPLOAD_BLOCKED_TEXT,
        )
    if isinstance(file_name, str) and isinstance(file_bytes, (bytes, bytearray)):
        fresh = _ingest_bytes(store, record, file_name, bytes(file_bytes))
        reply = f"Файл принят ({len(fresh.ctx.document_paths)}). Пришлите ещё или /run."
        _reply(bot, user_id=user_id, chat_id=chat_id, text=reply)
        return MaxHandleResult(ok=True, action="upload", case_id=record.case_id, reply=reply)

    if downloads:
        names: list[str] = []
        fresh = record
        for name, url in downloads:
            try:
                data = download_file(url)
                fresh = _ingest_bytes(store, fresh, name, data)
                names.append(name)
            except Exception:
                continue
        if names:
            reply = f"Файлы приняты ({len(fresh.ctx.document_paths)}). Пришлите ещё или /run."
            _reply(bot, user_id=user_id, chat_id=chat_id, text=reply)
            return MaxHandleResult(
                ok=True, action="upload_url", case_id=record.case_id, reply=reply
            )

    # Свободный текст без LLM: короткая подсказка + кнопки текущего шага (ТЗ-20).
    if text:
        if intake is None:
            get_intake_store().upsert_started(user_id)
            intake = get_intake_store().get_active(user_id)
        reply, attachments = free_text_nudge(intake=intake)
        _reply(
            bot,
            user_id=user_id,
            chat_id=chat_id,
            text=reply,
            attachments=attachments,
        )
        return MaxHandleResult(
            ok=True,
            action="free_text_nudge",
            case_id=record.case_id,
            reply=reply,
        )

    reply = FALLBACK_MENU_TEXT
    _reply(
        bot,
        user_id=user_id,
        chat_id=chat_id,
        text=reply,
        attachments=goal_keyboard(),
    )
    return MaxHandleResult(ok=True, action="ack", case_id=record.case_id, reply=reply)
