"""╨Ю╨▒╤А╨░╨▒╨╛╤В╨║╨░ ╨░╨┐╨┤╨╡╨╣╤В╨╛╨▓ MAX тЖТ ╨║╨╡╨╣╤Б SFRFR."""

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
        "╨▓╨╛╨╣╤В╨╕",
        "╨▓╤Е╨╛╨┤",
        CONFIRM_WEB_LOGIN_LABEL.lower(),
        GET_CODE_IN_BROWSER_LABEL.lower(),
        "╨┐╨╛╨╗╤Г╤З╨╕╤В╤М ╨║╨╛╨┤",
        "╨┐╨╛╨╗╤Г╤З╨╕╤В╤М ╨║╨╛╨┤ ╨┤╨╗╤П ╨▓╤Е╨╛╨┤╨░",
        "╨┐╨╛╨┤╤В╨▓╨╡╤А╨┤╨╕╤В╤М ╨▓╤Е╨╛╨┤",
        CONFIRM_WEB_LOGIN_CALLBACK,
        GET_CODE_CALLBACK,
        "confirm_web_login",
        "get_login_code",
    }
)

_START_TRIGGERS = frozenset(
    {
        "/start",
        "╤Б╤В╨░╤А╤В",
        "╨╜╨░╤З╨░╤В╤М",
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
    """╨н╨▓╤А╨╕╤Б╤В╨╕╨║╨░: ╤Б╨╛╨▒╤Л╤В╨╕╨╡ ╨╕╨╖ ╨║╨░╨╜╨░╨╗╨░ (╨╜╨╡ ╨╗╨╕╤З╨╜╤Л╨╣ ╨┤╨╕╨░╨╗╨╛╨│)."""
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


def _append_client_case_message(
    *,
    case_id: str | None,
    text: str,
    max_user_id: str | None = None,
) -> None:
    """╨б╨╛╤Е╤А╨░╨╜╨╕╤В╤М ╤В╨╡╨║╤Б╤В ╨║╨╗╨╕╨╡╨╜╤В╨░ ╨▓ ╨╗╨╡╨╜╤В╤Г ╨┤╨╡╨╗╨░ (╨╕╨╗╨╕ ╨▓ ╨▒╤Г╤Д╨╡╤А ╨┤╨╛ ╨┐╨╛╤П╨▓╨╗╨╡╨╜╨╕╤П ╨┤╨╡╨╗╨░)."""
    from sfrfr.integrations.max.case_chat_log import append_client_case_message

    append_client_case_message(
        case_id=case_id,
        max_user_id=max_user_id,
        text=text,
    )


def _resolve_case_id_by_max_user(user_id: str | None) -> str | None:
    mid = str(user_id or "").strip()
    if not mid:
        return None
    try:
        from sfrfr.db.session import get_supabase_client

        client_row = (
            get_supabase_client()
            .table("clients")
            .select("id")
            .eq("max_user_id", mid)
            .limit(1)
            .execute()
            .data
            or []
        )
        if not client_row:
            return None
        client_id = client_row[0].get("id")
        cases = (
            get_supabase_client()
            .table("cases")
            .select("id")
            .eq("client_id", client_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
            .data
            or []
        )
        if not cases:
            return None
        cid = str(cases[0].get("id") or "")
        return cid if len(cid) >= 32 else None
    except Exception as exc:  # noqa: BLE001
        logger.warning("resolve case by max_user failed: %s", exc)
        return None


def _append_bot_case_message(
    *,
    case_id: str | None,
    text: str,
    attachments: list[dict[str, Any]] | None = None,
    max_user_id: str | None = None,
) -> None:
    """╨б╨╛╤Е╤А╨░╨╜╨╕╤В╤М ╨╛╤В╨▓╨╡╤В ╨▒╨╛╤В╨░ MAX (╤В╨╡╨║╤Б╤В + ╨┐╨╛╨┤╨┐╨╕╤Б╨╕ ╨║╨╜╨╛╨┐╨╛╨║) ╨▓ ╨╗╨╡╨╜╤В╤Г ╨┤╨╡╨╗╨░."""
    from sfrfr.integrations.max.case_chat_log import append_bot_case_message

    append_bot_case_message(
        case_id=case_id,
        max_user_id=max_user_id,
        text=text,
        attachments=attachments,
    )


def _case_id_for_max_user(user_id: str | None) -> str | None:
    """╨Ф╨╡╨╗╨╛ ╨┐╨╛ ╨║╨╗╨╕╨╡╨╜╤В╤Г MAX ╨╕╨╗╨╕ ╨┐╨╛ ╨░╨║╤В╨╕╨▓╨╜╨╛╨╣ ╨┤╨╕╨░╨│╨╜╨╛╤Б╤В╨╕╨║╨╡."""
    cid = _resolve_case_id_by_max_user(user_id)
    if cid:
        return cid
    mid = str(user_id or "").strip()
    if not mid:
        return None
    try:
        intake = get_intake_store().get_active(mid)
        if intake and intake.case_id and len(str(intake.case_id)) >= 32:
            return str(intake.case_id)
    except Exception:  # noqa: BLE001
        return None
    return None


def _text(update: dict[str, Any]) -> str:
    message = update.get("message") or update.get("message_created") or update
    if not isinstance(message, dict):
        return ""
    body = message.get("body") or message.get("text") or ""
    if isinstance(body, dict):
        return str(body.get("text") or "")
    return str(body or "")


def _callback_payload(update: dict[str, Any]) -> str:
    """payload/data ╨╕╨╖ message_callback."""
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
    """callback_id ╨┤╨╗╤П POST /answers."""
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
    case_id: str | None = None,
) -> bool:
    try:
        bot.send_message(
            text=text,
            user_id=user_id,
            chat_id=chat_id,
            attachments=attachments,
        )
        cid = case_id or _case_id_for_max_user(user_id)
        _append_bot_case_message(
            case_id=cid,
            text=text,
            attachments=attachments,
            max_user_id=str(user_id) if user_id else None,
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
    # ╨С╨╡╨╖ ticket тАФ ╨┐╨╛╨┤╤В╨▓╨╡╤А╨┤╨╕╤В ╨┐╨╛╤Б╨╗╨╡╨┤╨╜╤О╤О ╤Б╨╡╤Б╤Б╨╕╤О ╤Б ╨Я╨Ъ ╨┤╨╗╤П ╤Н╤В╨╛╨│╨╛ max_user_id
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
    """╨Я╤А╨╛╤Б╤М╨▒╨░ ╨╜╨░╤З╨░╤В╤М ╨┤╨╕╨░╨╗╨╛╨│ тАФ ╤Б╤В╨░╤А╤В╨╛╨▓╨╛╨╡ ╨╝╨╡╨╜╤О ╨┤╨╕╨░╨│╨╜╨╛╤Б╤В╨╕╨║╨╕."""
    return _handle_bot_start(
        bot,
        user_id=user_id,
        chat_id=chat_id,
        store=get_case_store(),
        welcome_text=welcome_text,
    )


def _ensure_client_row(max_user_id: str) -> dict[str, Any] | None:
    """╨У╨░╤А╨░╨╜╤В╨╕╤А╨╛╨▓╨░╨╜╨╜╨╛ ╨┐╨╛╨╗╤Г╤З╨╕╤В╤М/╤Б╨╛╨╖╨┤╨░╤В╤М ╤Б╤В╤А╨╛╨║╤Г clients ╨┤╨╗╤П max_user_id."""
    import logging

    log = logging.getLogger(__name__)
    try:
        from sfrfr.db.client_channels import ClientChannelRepository

        return ClientChannelRepository().ensure_for_max_user(str(max_user_id))
    except Exception as exc:  # noqa: BLE001
        log.exception("ensure_client_row_failed max=%s: %s", max_user_id, exc)
        return _client_row_by_max(max_user_id)


def _ensure_supabase_max_client(max_user_id: str) -> None:
    """╨Э╨╡╨▒╨╗╨╛╨║╨╕╤А╤Г╤О╤Й╨░╤П ╤А╨╡╨│╨╕╤Б╤В╤А╨░╤Ж╨╕╤П ╨║╨╗╨╕╨╡╨╜╤В╨░ MAX ╨▓ Supabase (╨╡╨┤╨╕╨╜╤Л╨╣ ╨┐╤А╨╛╤Д╨╕╨╗╤М ╨в╨Ч-09)."""
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
    """╨Х╤Б╨╗╨╕ ╨▓╤Е╨╛╨┤ ╤Г╨╢╨╡ ╨╢╨┤╤С╤В ╨┐╨╛╨┤╤В╨▓╨╡╤А╨╢╨┤╨╡╨╜╨╕╤П тАФ ╤Б╤А╨░╨╖╤Г ╨╖╨░╨▓╨╡╤А╤И╨╕╤В╤М (╨▒╨╡╨╖ ╨╗╨╕╤И╨╜╨╡╨╣ ╨║╨╜╨╛╨┐╨║╨╕)."""
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
    """╨б╨╛╨╖╨┤╨░╤В╤М ╨╕╨╗╨╕ ╨╜╨░╨╣╤В╨╕ ╨┤╨╡╨╗╨╛: ╤Б /start ╨┤╨╗╤П ╨╗╨╡╨╜╤В╤Л ╤З╨░╤В╨░; ╤В╨░╨║╨╢╨╡ ╨║╨░╨▒╨╕╨╜╨╡╤В / ╨╛╨┐╨╡╤А╨░╤В╨╛╤А."""

    def _finish(case_id: str) -> str:
        cid = str(case_id)
        try:
            from sfrfr.integrations.max.case_chat_log import flush_pending_case_chat

            flush_pending_case_chat(max_user_id=user_id, case_id=cid)
        except Exception as exc:  # noqa: BLE001
            logger.warning("flush pending chat failed max=%s: %s", user_id, exc)
        return cid

    if intake.case_id:
        return _finish(str(intake.case_id))

    # ╨Ы╨╛╨║╨░╨╗╤М╨╜╤Л╨╣ store тАФ ╨▒╤Л╤Б╤В╤А╤Л╨╣ ╨┐╤Г╤В╤М (╤В╨╡╤Б╤В╤Л / fallback).
    existing = store.find_by_max_user(user_id)
    if existing:
        intake.case_id = existing.case_id
        get_intake_store().save(intake)
        return _finish(existing.case_id)

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
        # ╨б╨╛╤Е╤А╨░╨╜╤П╨╡╨╝ ╨╗╨╛╨║╨░╨╗╤М╨╜╤Г╤О ╨┐╤А╨╕╨▓╤П╨╖╨║╤Г; id ╨╝╨╛╨╢╨╡╤В ╨╛╤В╨╗╨╕╤З╨░╤В╤М╤Б╤П тАФ ╨┤╨╗╤П ╨▒╨╛╤В╨░ ╨▓╨░╨╢╨╡╨╜ bind_max.
        store.bind_max(
            record.case_id,
            max_user_id=user_id,
            max_chat_id=str(chat_id) if chat_id is not None else None,
        )
        # ╨Я╤А╨╡╨┤╨┐╨╛╤З╨╕╤В╨░╨╡╨╝ supabase case_id ╨▓ deep-link.
        intake.case_id = case_id
        get_intake_store().save(intake)
        return _finish(case_id)

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
    return _finish(record.case_id)


def _try_create_supabase_case(*, user_id: str, intake) -> tuple[str, str] | None:
    """Best-effort ╤Б╨╛╨╖╨┤╨░╨╜╨╕╨╡ ╨┤╨╡╨╗╨░ ╨▓ Postgres ╤Б ╨║╨╛╤А╨╛╤В╨║╨╕╨╝ ╤В╨░╨╣╨╝╨░╤Г╤В╨╛╨╝."""
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
    if not case_id:
        return
    try:
        from sfrfr.db.session import get_supabase_client
        from sfrfr.integrations.amocrm.sync import persist_crm_external_id, push_case_to_amocrm

        rows = (
            get_supabase_client()
            .table("cases")
            .select(
                "id,b2c_status,pipeline_status,crm_external_id,"
                "clients(full_name,phone,email,preferred_channel,max_user_id)"
            )
            .eq("id", case_id)
            .limit(1)
            .execute()
            .data
            or []
        )
        if not rows:
            return
        case = rows[0]
        amo = push_case_to_amocrm(case, task="max_operator")
        lead_id = amo.get("lead_id") if isinstance(amo, dict) else None
        if lead_id and amo.get("ok"):
            persist_crm_external_id(case_id, str(lead_id))
        _notify_ops_max_operator(user_id=user_id, case_id=case_id, crm_url=amo.get("crm_url"))
    except Exception:
        import logging

        logging.getLogger(__name__).exception("max_operator_amocrm_failed max=%s", user_id)


def _notify_ops_max_operator(*, user_id: str, case_id: str, crm_url: str | None) -> None:
    """Ops-╨▒╨╛╤В: ╨║╨╗╨╕╨╡╨╜╤В ╨╢╨┤╤С╤В ╨╛╤В╨▓╨╡╤В╨░ ╨▓ MAX (╨╜╨╡ ╤Б╤Б╤Л╨╗╨║╨░ ╨╜╨░ ╨▒╨╛╤В╨░)."""
    try:
        from sfrfr.core.config import get_settings
        from sfrfr.db.staff_roles import list_manager_max_user_ids
        from sfrfr.integrations.amocrm.urls import (
            admin_case_max_reply_url,
            max_operator_reply_hint,
        )
        from sfrfr.integrations.max.ops_bot import get_ops_bot

        settings = get_settings()
        bot = get_ops_bot()
        if not bot.available:
            return
        admin = admin_case_max_reply_url(case_id) or ""
        text = (
            "╨Ъ╨╗╨╕╨╡╨╜╤В ╨╢╨┤╤С╤В ╨╛╤В╨▓╨╡╤В╨░ ╨▓ MAX\n"
            f"MAX user_id: {user_id}\n"
            f"╨Ю╤В╨▓╨╡╤В╨╕╤В╤М: {admin}\n"
            f"{max_operator_reply_hint(user_id)}\n"
        )
        if crm_url:
            text += f"amo: {crm_url}\n"
        manager_ids = list_manager_max_user_ids(
            extra_ids=settings.staff_login_approver_max_user_ids,
        )
        chat_ids = [
            p.strip()
            for p in (settings.staff_login_approver_max_chat_ids or "").split(",")
            if p.strip()
        ]
        team_channel = (settings.max_specialists_channel_chat_id or "").strip()
        for mid in manager_ids:
            try:
                bot.send_message(text=text, user_id=str(mid))
            except Exception:
                continue
        for cid in chat_ids:
            try:
                bot.send_message(text=text, chat_id=cid)
            except Exception:
                continue
        if team_channel:
            try:
                bot.send_message(text=text, chat_id=team_channel)
            except Exception:
                pass
    except Exception:
        import logging

        logging.getLogger(__name__).exception("max_ops_operator_notify_failed max=%s", user_id)


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
    """╨б╨╗╨╡╨┤╤Г╤О╤Й╨╕╨╣ ╤И╨░╨│ ╨┐╨╛╤Б╨╗╨╡ ╨╛╤В╨▓╨╡╤В╨░ ╨┐╤А╨╛ ╨Ш╨Ы╨б (╨╕╨╗╨╕ ╨┐╨╛╤Б╨╗╨╡ ╨╕╨╜╤Б╤В╤А╤Г╨║╤Ж╨╕╨╕ ╨У╨╛╤Б╤Г╤Б╨╗╤Г╨│)."""
    intake_store = get_intake_store()
    # ╨Э╨╛╨▓╤Л╨╣ ╨┐╨╛╤В╨╛╨║ ┬з10.1: ╨┐╨╛╤Б╨╗╨╡ ╨Ш╨Ы╨б ╤Б╤А╨░╨╖╤Г ╤Г╤Б╤В╤А╨╛╨╣╤Б╤В╨▓╨╛ (╨▒╨╡╨╖ employment)
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
            # ╨Э╨╛╨▓╤Л╨╣ ╨┐╨╛╤В╨╛╨║: ╨╜╨░╨╖╨░╨┤ ╨║ ╨╕╨╜╤Б╤В╤А╤Г╨║╤Ж╨╕╨╕ ╨Ш╨Ы╨б ╨╕╨╗╨╕ ╨║ ╨▓╨╛╨┐╤А╨╛╤Б╤Г ╨┐╤А╨╛ ╨Ш╨Ы╨б
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
            # Legacy: ╨╜╨░╨╖╨░╨┤ ╨║ ╤В╤А╤Г╨┤╨╛╨▓╤Л╨╝ ╨┤╨╛╨║╤Г╨╝╨╡╨╜╤В╨░╨╝ / howto
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

    # Legacy goal payloads (╤Б╤В╨░╤А╤Л╨╡ ╨║╨╜╨╛╨┐╨║╨╕ / ╤В╨╡╤Б╤В╤Л)
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
    """╨б╤В╨░╤А╤В: ╨╝╨╡╨╜╤О ╨┤╨╕╨░╨│╨╜╨╛╤Б╤В╨╕╨║╨╕ ╨╕ ╤А╨░╨╜╨╜╨╡╨╡ ╨┤╨╡╨╗╨╛ тАФ ╨┐╨╡╤А╨╡╨┐╨╕╤Б╨║╨░ ╤Б╤А╨░╨╖╤Г ╨▓ ╨║╨░╤А╤В╨╛╤З╨║╨╡."""
    resumed = _resume_pending_confirm_if_any(bot, user_id=user_id, chat_id=chat_id)
    if resumed is not None:
        return resumed

    _ensure_supabase_max_client(user_id)
    intake = get_intake_store().upsert_started(user_id)
    # ╨Ф╨╡╨╗╨╛ ╤Б /start: ╤Б╨╛╤В╤А╤Г╨┤╨╜╨╕╨║ ╨▓╨╕╨┤╨╕╤В ╨▒╨╛╤В╨░/╨║╨╜╨╛╨┐╨║╨╕ ╨┤╨╛ ╨║╨░╨▒╨╕╨╜╨╡╤В╨░ ╨╕ ┬л╨Я╨╛╨╖╨▓╨░╤В╤М ╤Б╨┐╨╡╤Ж╨╕╨░╨╗╨╕╤Б╤В╨░┬╗.
    case_id = _ensure_case_for_intake(
        user_id=user_id, chat_id=chat_id, intake=intake, store=store
    )
    text = welcome_text or WELCOME_TEXT
    _reply(
        bot,
        user_id=user_id,
        chat_id=chat_id,
        text=text,
        attachments=goal_keyboard(),
        case_id=case_id,
    )
    return MaxHandleResult(
        ok=True,
        action="max_intake_started",
        case_id=case_id,
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
    """hashed_token magic link ╨┤╨╗╤П ╤Г╨║╨░╨╖╨░╨╜╨╜╨╛╨│╨╛ email (╨▒╨╡╨╖ list_users)."""
    try:
        from sfrfr.db.session import get_supabase_client
        from sfrfr.db.staff_roles import (
            find_user_by_email,
            sync_staff_role_auth_user_id,
            user_id_of,
        )

        normalized = email.strip().lower()
        if "@" not in normalized:
            return None
        client = get_supabase_client()
        existing = find_user_by_email(normalized)
        if existing is None:
            try:
                client.auth.admin.create_user(
                    {
                        "email": normalized,
                        "email_confirm": True,
                        "app_metadata": {"role_source": "staff_max_login"},
                    }
                )
            except Exception as exc:
                err = str(exc).lower()
                if "already" not in err and "registered" not in err:
                    raise
                existing = find_user_by_email(normalized)
        try:
            link = client.auth.admin.generate_link({"type": "magiclink", "email": normalized})
        except Exception:
            if existing is None:
                existing = find_user_by_email(normalized)
            if existing is None:
                return None
            link = client.auth.admin.generate_link({"type": "magiclink", "email": normalized})
        props = getattr(link, "properties", None)
        if props is None and isinstance(link, dict):
            props = link.get("properties") or link
        hashed = None
        if props is not None:
            hashed = getattr(props, "hashed_token", None) or (
                props.get("hashed_token") if isinstance(props, dict) else None
            )
        auth_user = existing or find_user_by_email(normalized)
        if auth_user is not None:
            sync_staff_role_auth_user_id(email=normalized, auth_user_id=user_id_of(auth_user))
        return str(hashed) if hashed else None
    except Exception:
        return None


def _token_hash_for_max(max_user_id: str) -> tuple[str, str] | None:
    """(email, token_hash) ╨┤╨╗╤П Supabase session ╨╜╨░ ╨Я╨Ъ."""
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
    """╨Ю╤В╨┐╤А╨░╨▓╨╕╤В╤М ╤А╤Г╨║╨╛╨▓╨╛╨┤╨╕╤В╨╡╨╗╤П╨╝ ╨║╨╜╨╛╨┐╨║╤Г ╨╛╨┤╨╛╨▒╤А╨╡╨╜╨╕╤П ╤З╨╡╤А╨╡╨╖ ops-╨▒╨╛╤В (╨в╨Ч-25)."""
    from sfrfr.db.staff_roles import list_manager_max_user_ids
    from sfrfr.integrations.max.ops_bot import get_ops_bot
    from sfrfr.security.login_otp import APPROVE_STAFF_LOGIN_LABEL

    # ╨б╨╗╤Г╨╢╨╡╨▒╨╜╤Л╨╡ ╨║╨╜╨╛╨┐╨║╨╕ тАФ ╨▓╤Б╨╡╨│╨┤╨░ ops (fallback ╨╜╨░ ╨║╨╗╨╕╨╡╨╜╤В╤Б╨║╨╕╨╣ ╤В╨╛╨║╨╡╨╜, ╨╡╤Б╨╗╨╕ ops ╨╜╨╡ ╨╖╨░╨┤╨░╨╜).
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
    email = pending.staff_email or pending.contact or "╤Б╨╛╤В╤А╤Г╨┤╨╜╨╕╨║"
    text = (
        f"╨Ч╨░╨┐╤А╨╛╤Б ╨╜╨░ ╨▓╤Е╨╛╨┤ ╤Б╨╛╤В╤А╤Г╨┤╨╜╨╕╨║╨░ ╨▓ ╨║╨░╨▒╨╕╨╜╨╡╤В.\n"
        f"╨Я╨╛╤З╤В╨░: {email}\n\n"
        f"╨Э╨░╨╢╨╝╨╕╤В╨╡ ╨║╨╜╨╛╨┐╨║╤Г, ╤З╤В╨╛╨▒╤Л ╤А╨░╨╖╤А╨╡╤И╨╕╤В╤М ╨▓╤Е╨╛╨┤."
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
            # fallback: ╤В╨╛╨╗╤М╨║╨╛ chat_id
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
    """╨Я╨╛╨┤╤В╨▓╨╡╤А╨╢╨┤╨╡╨╜╨╕╨╡ ╤Б ╤В╨╡╨╗╨╡╤Д╨╛╨╜╨░ тЖТ ╤Б╨╡╤Б╤Б╨╕╤П ╨┤╨╗╤П poll ╨╜╨░ ╨Я╨Ъ
    (╨║╨╗╨╕╨╡╨╜╤В) ╨╕╨╗╨╕ ╨╛╨╢╨╕╨┤╨░╨╜╨╕╨╡ ╤А╤Г╨║╨╛╨▓╨╛╨┤╨╕╤В╨╡╨╗╤П (staff)."""
    pending = None
    if ticket_id:
        pending = get_pending(ticket_id)
    if pending is None:
        pending = latest_for_max(user_id)
    if pending is None or pending.status not in {
        "pending_confirm",
        "pending_pair",
        "code_sent",
    }:
        reply = ask_code_from_login_page()
        _reply(bot, user_id=user_id, chat_id=chat_id, text=reply)
        return MaxHandleResult(ok=False, action="login_no_pending", reply=reply)

    if pending.status == "pending_pair" or not pending.max_user_id:
        # ╨╡╤Й╤С ╨╜╨╡ ╨▓╨▓╨╡╨╗╨╕ ╨║╨╛╨┤ тАФ ╨┐╤А╨╕╨▓╤П╨╢╨╡╨╝ ╤В╨╡╨║╤Г╤Й╨╡╨│╨╛ ╨┐╨╛╨╗╤М╨╖╨╛╨▓╨░╤В╨╡╨╗╤П ╨╕ ╤Б╤А╨░╨╖╤Г ╨╖╨░╨▓╨╡╤А╤И╨╕╨╝ ╨▓╤Е╨╛╨┤
        if pending.audience == "staff":
            contact = (pending.staff_email or "").strip().lower()
            if not contact:
                reply = "╨б╨╡╤Б╤Б╨╕╤П ╤Г╤Б╤В╨░╤А╨╡╨╗╨░. ╨Э╨░╤З╨╜╨╕╤В╨╡ ╨▓╤Е╨╛╨┤ ╤Б╨╜╨╛╨▓╨░ ╨╜╨░ admin."
                _reply(bot, user_id=user_id, chat_id=chat_id, text=reply)
                return MaxHandleResult(ok=False, action="login_staff_no_email", reply=reply)
        else:
            row = _ensure_client_row(user_id)
            if not row:
                reply = "╨Э╨╡ ╤Г╨┤╨░╨╗╨╛╤Б╤М ╤Б╨▓╤П╨╖╨░╤В╤М ╨░╨║╨║╨░╤Г╨╜╤В. ╨Я╤А╨╕╤И╨╗╨╕╤В╨╡ 6-╨╖╨╜╨░╤З╨╜╤Л╨╣ ╨║╨╛╨┤ ╤Б╨╛ ╤Б╤В╤А╨░╨╜╨╕╤Ж╤Л ╨▓╤Е╨╛╨┤╨░."
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

    # Staff: ╨┐╨╡╤А╨▓╤Л╨╣ ╨▓╤Е╨╛╨┤ тАФ ╤А╤Г╨║╨╛╨▓╨╛╨┤╨╕╤В╨╡╨╗╤М; ╨┤╨░╨╗╤М╤И╨╡ ╤В╨╛╤В ╨╢╨╡ MAX ╨▓╤Е╨╛╨┤╨╕╤В ╤Б╨░╨╝
    if pending.audience == "staff":
        from sfrfr.db.staff_roles import (
            get_staff_role_by_email,
            is_staff_login_trusted,
        )

        staff_email = (pending.staff_email or "").strip().lower()
        if not staff_email or get_staff_role_by_email(staff_email) is None:
            reply = "╨Э╨╡╤В ╨┤╨╛╤Б╤В╤Г╨┐╨░. ╨Ю╨▒╤А╨░╤В╨╕╤В╨╡╤Б╤М ╨║ ╨░╨┤╨╝╨╕╨╜╨╕╤Б╤В╤А╨░╤В╨╛╤А╤Г."
            _reply(bot, user_id=user_id, chat_id=chat_id, text=reply)
            return MaxHandleResult(ok=False, action="login_not_staff", reply=reply)

        if is_staff_login_trusted(email=staff_email, max_user_id=user_id):
            token_hash = _token_hash_for_email(staff_email)
            if not token_hash:
                reply = "╨Ю╤И╨╕╨▒╨║╨░ ╨▓╤Е╨╛╨┤╨░. ╨Я╨╛╨┐╤А╨╛╨▒╤Г╨╣╤В╨╡ ╨┐╨╛╨╖╨╢╨╡."
                _reply(bot, user_id=user_id, chat_id=chat_id, text=reply)
                return MaxHandleResult(ok=False, action="login_token_failed", reply=reply)
            approved = approve(
                ticket_id=pending.ticket_id,
                token_hash=token_hash,
                email=staff_email,
            )
            if not approved:
                reply = "╨б╨╡╤Б╤Б╨╕╤П ╤Г╤Б╤В╨░╤А╨╡╨╗╨░. ╨Э╨░╤З╨╜╨╕╤В╨╡ ╨▓╤Е╨╛╨┤ ╤Б╨╜╨╛╨▓╨░ ╨╜╨░ ╨║╨╛╨╝╨┐╤М╤О╤В╨╡╤А╨╡."
                _reply(bot, user_id=user_id, chat_id=chat_id, text=reply)
                return MaxHandleResult(ok=False, action="login_expired", reply=reply)
            reply = "╨У╨╛╤В╨╛╨▓╨╛. ╨б╨╝╨╛╤В╤А╨╕╤В╨╡ ╨║╨╛╨╝╨┐╤М╤О╤В╨╡╤А."
            _reply(bot, user_id=user_id, chat_id=chat_id, text=reply)
            return MaxHandleResult(ok=True, action="login_approved_trusted", reply=reply)

        waiting = mark_pending_manager(ticket_id=pending.ticket_id)
        if not waiting:
            reply = "╨б╨╡╤Б╤Б╨╕╤П ╤Г╤Б╤В╨░╤А╨╡╨╗╨░. ╨Э╨░╤З╨╜╨╕╤В╨╡ ╨▓╤Е╨╛╨┤ ╤Б╨╜╨╛╨▓╨░ ╨╜╨░ ╨║╨╛╨╝╨┐╤М╤О╤В╨╡╤А╨╡."
            _reply(bot, user_id=user_id, chat_id=chat_id, text=reply)
            return MaxHandleResult(ok=False, action="login_expired", reply=reply)
        sent = _notify_managers_staff_login(bot, pending=waiting)
        if sent == 0:
            reply = "╨Э╨╡╤В ╤А╤Г╨║╨╛╨▓╨╛╨┤╨╕╤В╨╡╨╗╤П ╨▓ ╤Б╨╕╤Б╤В╨╡╨╝╨╡. ╨Ю╨▒╤А╨░╤В╨╕╤В╨╡╤Б╤М ╨║ ╨░╨┤╨╝╨╕╨╜╨╕╤Б╤В╤А╨░╤В╨╛╤А╤Г."
            _reply(bot, user_id=user_id, chat_id=chat_id, text=reply)
            return MaxHandleResult(
                ok=True,
                action="login_pending_manager_no_approvers",
                reply=reply,
            )
        reply = "╨Ц╨┤╨╕╤В╨╡ ╤А╤Г╨║╨╛╨▓╨╛╨┤╨╕╤В╨╡╨╗╤П."
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
        reply = "╨Ю╤И╨╕╨▒╨║╨░ ╨▓╤Е╨╛╨┤╨░. ╨Я╨╛╨┐╤А╨╛╨▒╤Г╨╣╤В╨╡ ╨┐╨╛╨╖╨╢╨╡."
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
        reply = "╨б╨╡╤Б╤Б╨╕╤П ╤Г╤Б╤В╨░╤А╨╡╨╗╨░. ╨Э╨░╤З╨╜╨╕╤В╨╡ ╨▓╤Е╨╛╨┤ ╤Б╨╜╨╛╨▓╨░ ╨╜╨░ ╨║╨╛╨╝╨┐╤М╤О╤В╨╡╤А╨╡."
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
    """╨а╤Г╨║╨╛╨▓╨╛╨┤╨╕╤В╨╡╨╗╤М ╤А╨░╨╖╤А╨╡╤И╨╕╨╗ ╨▓╤Е╨╛╨┤ ╤Б╨╛╤В╤А╤Г╨┤╨╜╨╕╨║╨░ ╨╜╨░ ╨Я╨Ъ."""
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
        reply = "╨Э╨╡╤В ╨┐╤А╨░╨▓╨░ ╨╜╨░ ╤Н╤В╨╛ ╨┤╨╡╨╣╤Б╤В╨▓╨╕╨╡."
        _reply(bot, user_id=user_id, chat_id=chat_id, text=reply)
        return MaxHandleResult(ok=False, action="manager_forbidden", reply=reply)

    pending = get_pending(ticket_id)
    if pending is None or pending.status != "pending_manager":
        reply = "╨Ч╨░╤П╨▓╨║╨░ ╤Г╨╢╨╡ ╨╛╨▒╤А╨░╨▒╨╛╤В╨░╨╜╨░ ╨╕╨╗╨╕ ╤Г╤Б╤В╨░╤А╨╡╨╗╨░."
        _reply(bot, user_id=user_id, chat_id=chat_id, text=reply)
        return MaxHandleResult(ok=False, action="manager_no_pending", reply=reply)

    staff_email = (pending.staff_email or "").strip().lower()
    if not staff_email or get_staff_role_by_email(staff_email) is None:
        reply = "╨б╨╛╤В╤А╤Г╨┤╨╜╨╕╨║ ╨╜╨╡ ╨╜╨░╨╣╨┤╨╡╨╜."
        _reply(bot, user_id=user_id, chat_id=chat_id, text=reply)
        return MaxHandleResult(ok=False, action="manager_not_staff", reply=reply)

    token_hash = _token_hash_for_email(staff_email)
    if not token_hash:
        reply = "╨Ю╤И╨╕╨▒╨║╨░ ╨▓╤Е╨╛╨┤╨░. ╨Я╨╛╨┐╤А╨╛╨▒╤Г╨╣╤В╨╡ ╨┐╨╛╨╖╨╢╨╡."
        _reply(bot, user_id=user_id, chat_id=chat_id, text=reply)
        return MaxHandleResult(ok=False, action="manager_token_failed", reply=reply)

    approved = approve(ticket_id=pending.ticket_id, token_hash=token_hash, email=staff_email)
    if not approved:
        reply = "╨б╨╡╤Б╤Б╨╕╤П ╤Г╤Б╤В╨░╤А╨╡╨╗╨░."
        _reply(bot, user_id=user_id, chat_id=chat_id, text=reply)
        return MaxHandleResult(ok=False, action="manager_expired", reply=reply)

    # ╨Ч╨░╨┐╨╛╨╝╨╜╨╕╤В╤М MAX ╤Б╨╛╤В╤А╤Г╨┤╨╜╨╕╨║╨░ тАФ ╤Б╨╗╨╡╨┤╤Г╤О╤Й╨╕╨╡ ╨▓╤Е╨╛╨┤╤Л ╨▒╨╡╨╖ ╤А╤Г╨║╨╛╨▓╨╛╨┤╨╕╤В╨╡╨╗╤П
    employee_max = str(pending.max_user_id or "").strip()
    if employee_max:
        try:
            trust_staff_login(email=staff_email, max_user_id=employee_max)
        except Exception:
            pass

    reply = "╨Т╤Е╨╛╨┤ ╤А╨░╨╖╤А╨╡╤И╤С╨╜."
    _reply(bot, user_id=user_id, chat_id=chat_id, text=reply)
    # ╤Г╨▓╨╡╨┤╨╛╨╝╨╕╤В╤М ╤Б╨╛╤В╤А╤Г╨┤╨╜╨╕╨║╨░ ╨▓ MAX, ╨╡╤Б╨╗╨╕ ╨╕╨╖╨▓╨╡╤Б╤В╨╡╨╜
    if pending.max_user_id and str(pending.max_user_id) != str(user_id):
        try:
            bot.send_message(
                text="╨Т╤Е╨╛╨┤ ╤А╨░╨╖╤А╨╡╤И╤С╨╜. ╨б╨╝╨╛╤В╤А╨╕╤В╨╡ ╤Н╨║╤А╨░╨╜ ╨║╨╛╨╝╨┐╤М╤О╤В╨╡╤А╨░.",
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
    """╨Ъ╨╜╨╛╨┐╨║╨░ ╨┐╨╛╨┤╤В╨▓╨╡╤А╨╢╨┤╨╡╨╜╨╕╤П: callback + link (╨╡╤Б╨╗╨╕ ╤Г╨┤╨░╨╗╨╛╤Б╤М ╨▓╤Л╨┐╤Г╤Б╤В╨╕╤В╤М URL)."""
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
        # ╨╖╨░╨┐╨░╤Б: ╤В╨╛╨╗╤М╨║╨╛ callback ╨▒╨╡╨╖ link
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
    """╨Т╤Л╨┤╨░╤В╤М ╨║╨╛╨┤ ╨▓ MAX ╨┤╨╗╤П ╨▓╨▓╨╛╨┤╨░ ╨╜╨░ ╤Б╤В╤А╨░╨╜╨╕╤Ж╨╡ ╨▓╤Е╨╛╨┤╨░ ╨║╨░╨▒╨╕╨╜╨╡╤В╨░."""
    from sfrfr.integrations.max.client import inline_link_keyboard

    row = _ensure_client_row(user_id)
    if not row:
        reply = "╨Э╨╡ ╤Г╨┤╨░╨╗╨╛╤Б╤М ╨┐╨╛╨┤╨│╨╛╤В╨╛╨▓╨╕╤В╤М ╨▓╤Е╨╛╨┤. ╨Я╨╛╨┐╤А╨╛╨▒╤Г╨╣╤В╨╡ ╨╡╤Й╤С ╤А╨░╨╖ ╤З╨╡╤А╨╡╨╖ ╨╝╨╕╨╜╤Г╤В╤Г."
        _reply(bot, user_id=user_id, chat_id=chat_id, text=reply)
        return MaxHandleResult(ok=False, action="login_no_client", reply=reply)

    contact = _auth_email_for_row(row, user_id)
    pending = ensure_pending_for_max(max_user_id=user_id, contact=contact)
    try:
        issued = issue_login_link(contact=contact, max_user_id=user_id)
    except Exception as exc:  # noqa: BLE001
        logger.exception("issue_login_link failed max=%s: %s", user_id, exc)
        reply = "╨Э╨╡ ╤Г╨┤╨░╨╗╨╛╤Б╤М ╤Б╨╛╨╖╨┤╨░╤В╤М ╨║╨╛╨┤. ╨Я╨╛╨┐╤А╨╛╨▒╤Г╨╣╤В╨╡ ╨┐╨╛╨╖╨╢╨╡."
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
    """Legacy/staff: ╨║╨╛╨┤ ╤Б ╤Н╨║╤А╨░╨╜╨░ ╨Я╨Ъ. ╨Ъ╨╗╨╕╨╡╨╜╤В╤Г тАФ ╨▓╤Л╨┤╨░╤В╤М ╨║╨╛╨┤ ╨┤╨╗╤П ╨▓╨▓╨╛╨┤╨░ ╨╜╨░ ╤Б╨░╨╣╤В╨╡."""
    row = _ensure_client_row(user_id)
    contact = (
        _auth_email_for_row(row, user_id)
        if row
        else f"max_{user_id}@clients.sfrfr.local"
    )
    pending = bind_max_by_code(
        pair_code=code, max_user_id=user_id, contact=contact
    )
    if pending:
        auth_event(
            "max_pair",
            outcome="ok",
            max_user_id=user_id,
            ticket=pending.ticket_id,
            status=pending.status,
        )
        if pending.audience == "staff":
            from sfrfr.security.login_otp import CONFIRM_STAFF_CABINET_LOGIN_LABEL

            reply = (
                "╨Ъ╨╛╨┤ ╨┐╤А╨╕╨╜╤П╤В.\n"
                f"╨Э╨░╨╢╨╝╨╕╤В╨╡ ┬л{CONFIRM_STAFF_CABINET_LOGIN_LABEL}┬╗ тАФ "
                "╨╜╨░ ╨║╨╛╨╝╨┐╤М╤О╤В╨╡╤А╨╡ ╨╛╤В╨║╤А╨╛╨╡╤В╤Б╤П ╨║╨░╨▒╨╕╨╜╨╡╤В ╤Б╨╛╤В╤А╤Г╨┤╨╜╨╕╨║╨░."
            )
            _reply(
                bot,
                user_id=user_id,
                chat_id=chat_id,
                text=reply,
                attachments=inline_confirm_login_keyboard(
                    ticket_id=pending.ticket_id,
                    label=CONFIRM_STAFF_CABINET_LOGIN_LABEL,
                ),
            )
            return MaxHandleResult(ok=True, action="staff_pair_accepted", reply=reply)
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
    """╨Ъ╨╗╨╕╨╡╨╜╤В ╨▓ ╤Б╨╕╤Б╤В╨╡╨╝╨╡: ╨┐╨╛╨┤╤В╨▓╨╡╤А╨┤╨╕╤В╤М ╨▓╤Е╨╛╨┤ ╨╜╨░ ╨Я╨Ъ. ╨Э╨╛╨▓╤Л╨╣ MAX тАФ ╨║╨╛╨┤ ╨┤╨╗╤П ╨▓╨▓╨╛╨┤╨░ ╨╜╨░ ╤Б╨░╨╣╤В╨╡."""
    ticket_from_cb = parse_confirm_callback(callback_payload)
    if ticket_from_cb is not None:
        return _complete_pc_login(
            bot,
            user_id=user_id,
            chat_id=chat_id,
            ticket_id=ticket_from_cb or None,
        )
    pending = latest_for_max(user_id)
    if pending and pending.audience == "staff":
        return _complete_pc_login(
            bot, user_id=user_id, chat_id=chat_id, ticket_id=pending.ticket_id
        )
    row = _ensure_client_row(user_id)
    if row:
        contact = _auth_email_for_row(row, user_id)
        if not pending or pending.audience == "client":
            if not pending:
                pending = ensure_pending_for_max(max_user_id=user_id, contact=contact)
            return _complete_pc_login(
                bot,
                user_id=user_id,
                chat_id=chat_id,
                ticket_id=pending.ticket_id,
            )
    return _issue_login_code_to_max(bot, user_id=user_id, chat_id=chat_id)


def _docs_request_text(*, has_docs: bool) -> str:
    if get_settings().app_env.strip().lower() == "production":
        return (
            "╨Ч╨░╨│╤А╤Г╨╖╨╕╤В╨╡ ╨┤╨╛╨║╤Г╨╝╨╡╨╜╤В╤Л ╨▓ ╨╖╨░╤Й╨╕╤Й╤С╨╜╨╜╨╛╨╝ ╨║╨░╨▒╨╕╨╜╨╡╤В╨╡ ╨┐╨╛╤Б╨╗╨╡ ╨┐╨╛╨┤╤В╨▓╨╡╤А╨╢╨┤╨╡╨╜╨╕╤П ╤Б╨╛╨│╨╗╨░╤Б╨╕╤П. "
            "╨з╨╡╤А╨╡╨╖ ╤Б╨╛╨╛╨▒╤Й╨╡╨╜╨╕╤П MAX ╨┤╨╛╨║╤Г╨╝╨╡╨╜╤В╤Л ╨╜╨╡ ╨┐╤А╨╕╨╜╨╕╨╝╨░╤О╤В╤Б╤П."
        )
    if has_docs:
        return "╨Я╤А╨╕╤И╨╗╨╕╤В╨╡ ╤Б╨╗╨╡╨┤╤Г╤О╤Й╨╕╨╣ ╨┤╨╛╨║╤Г╨╝╨╡╨╜╤В (PDF/JPG/PNG) ╨╕╨╗╨╕ /run."
    return "╨Я╤А╨╕╤И╨╗╨╕╤В╨╡ ╨▓╤Л╨┐╨╕╤Б╨║╤Г ╨Ш╨Ы╨б (PDF/JPG/PNG)."


def _draft_preview(record) -> str:  # noqa: ANN001 - CaseRecord
    draft = record.ctx.draft
    if not draft:
        return "╨з╨╡╤А╨╜╨╛╨▓╨╕╨║ ╨╡╤Й╤С ╨╜╨╡ ╨│╨╛╤В╨╛╨▓. ╨Я╤А╨╕╤И╨╗╨╕╤В╨╡ ╨┤╨╛╨║╤Г╨╝╨╡╨╜╤В╤Л, ╨╖╨░╤В╨╡╨╝ /run."
    body = (draft.body or "").strip()
    preview = body[:1500] + ("тАж" if len(body) > 1500 else "")
    title = draft.title or "╨з╨╡╤А╨╜╨╛╨▓╨╕╨║ ╨╖╨░╤П╨▓╨╗╨╡╨╜╨╕╤П"
    return f"{title}\n\n{preview}"


def _ingest_bytes(store, record, file_name: str, data: bytes):  # noqa: ANN001
    path = save_upload(record.case_id, file_name, data)
    fresh = store.add_document(record.case_id, str(path))
    try:
        from sfrfr.integrations.max.case_chat_log import (
            append_case_chat_message,
            format_document_event,
        )

        append_case_chat_message(
            case_id=record.case_id,
            author_kind="client",
            body=format_document_event(filename=file_name),
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("document case_message failed: %s", exc)
    return fresh


def _collect_max_files(update: dict[str, Any]) -> list[tuple[str, bytes]]:
    files: list[tuple[str, bytes]] = []
    file_name = update.get("file_name")
    file_bytes = update.get("file_bytes")
    if isinstance(file_name, str) and isinstance(file_bytes, (bytes, bytearray)):
        files.append((file_name, bytes(file_bytes)))
    for name, url in extract_downloadable_files(update):
        try:
            files.append((name, download_file(url)))
        except Exception:  # noqa: BLE001
            continue
    return files


def _try_max_payment_receipt(
    bot: MaxBotClient,
    *,
    user_id: str,
    chat_id: int | str | None,
    files: list[tuple[str, bytes]],
) -> MaxHandleResult | None:
    if not files:
        return None
    try:
        from sfrfr.services.payment_receipt import ingest_max_receipt
    except Exception:  # noqa: BLE001
        return None
    try:
        result = ingest_max_receipt(max_user_id=str(user_id), files=files)
    except Exception:  # noqa: BLE001
        logging.getLogger(__name__).info("max payment receipt skipped", exc_info=True)
        return None
    if not result:
        return None
    reply = str(result.get("client_message") or "╨з╨╡╨║ ╨┐╨╛╨╗╤Г╤З╨╕╨╗╨╕.")
    _reply(bot, user_id=user_id, chat_id=chat_id, text=reply)
    return MaxHandleResult(
        ok=result.get("status") in {"confirmed", "already_paid"},
        action=f"payment_receipt_{result.get('status')}",
        case_id=result.get("case_id"),
        reply=reply,
    )


def handle_max_update(
    update: dict[str, Any],
    *,
    bot: MaxBotClient | None = None,
) -> MaxHandleResult:
    """
    ╨б╤Ж╨╡╨╜╨░╤А╨╕╨╣ ╨в╨Ч-20 (+ ╨╗╨╡╨╜╤В╨░ ╤З╨░╤В╨░ ╤Б /start):
    /start тАФ ╨┤╨╕╨░╨│╨╜╨╛╤Б╤В╨╕╨║╨░ ╨╕ ╤А╨░╨╜╨╜╨╡╨╡ ╨┤╨╡╨╗╨╛ ╨┤╨╗╤П ╨┐╨╡╤А╨╡╨┐╨╕╤Б╨║╨╕ ╨▓ ╨║╨░╤А╤В╨╛╤З╨║╨╡
    intake:* тАФ ╤Ж╨╡╨╗╨╕ ╨╕ ╨▓╨╛╨┐╤А╨╛╤Б╤Л
    /login тАФ ╨▓╤Е╨╛╨┤ ╨▓ ╨▓╨╡╨▒-╨║╨░╨▒╨╕╨╜╨╡╤В ╨┐╨╛ ╨║╨╛╨┤╤Г
    /cabinet /status /documents /help тАФ ╨╝╨╡╨╜╤О ╨▓╨╡╤А╨╜╤Г╨▓╤И╨╡╨│╨╛╤Б╤П ╨║╨╗╨╕╨╡╨╜╤В╨░
    ╨▓╨╗╨╛╨╢╨╡╨╜╨╕╤П ╨▓ production тАФ ╨╛╤В╨║╨░╨╖ + CTA ╨║╨░╨▒╨╕╨╜╨╡╤В╨░
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

    # ╨Ъ╨░╨╜╨░╨╗/╨│╤А╤Г╨┐╨┐╨░: chat_id ╨╕╨╖ bot_added (GET /chats ╤Б╨╜╤П╤В ╤Б ╨╕╤О╨╜╤П 2026).
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

    # ╨а╨░╨╜╨╜╨╡╨╡ ╨┤╨╡╨╗╨╛ ╨┤╨╗╤П ╨╗╨╡╨╜╤В╤Л: ╨┤╨░╨╢╨╡ ╨┤╨╛ ╨║╨░╨▒╨╕╨╜╨╡╤В╨░ / ╨╛╨┐╨╡╤А╨░╤В╨╛╤А╨░ ╨┐╨╡╤А╨╡╨┐╨╕╤Б╨║╨░ ╨▓╨╕╨┤╨╜╨░ ╨▓ ╨║╨░╤А╤В╨╛╤З╨║╨╡.
    intake_early = get_intake_store().get_active(user_id)
    if intake_early is None and (
        callback or text or "bot_started" in update_type or start_hit
    ):
        intake_early = get_intake_store().upsert_started(user_id)
    if intake_early is not None and not intake_early.case_id:
        try:
            _ensure_case_for_intake(
                user_id=user_id,
                chat_id=chat_id,
                intake=intake_early,
                store=store,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("early case for chat failed max=%s: %s", user_id, exc)

    # ╨Э╨░╨╢╨░╤В╨╕╨╡ ╨║╨╜╨╛╨┐╨║╨╕ ╨▓ MAX тАФ ╨▓ ╨╗╨╡╨╜╤В╤Г ╨┤╨╡╨╗╨░ (╨╕╤Б╤В╨╛╤А╨╕╤П ╨┤╨╗╤П ╤Б╨╛╤В╤А╤Г╨┤╨╜╨╕╨║╨░).
    if callback:
        from sfrfr.integrations.max.case_chat_log import format_button_press

        _append_client_case_message(
            case_id=_case_id_for_max_user(user_id),
            max_user_id=user_id,
            text=format_button_press(callback),
        )
        # Soft-╨║╨╜╨╛╨┐╨║╨╕ ╨╛╤В DeepSeek тЖТ ╨┤╨░╨╗╤М╤И╨╡ ╨║╨░╨║ ╤Б╨▓╨╛╨▒╨╛╨┤╨╜╤Л╨╣ ╤В╨╡╨║╤Б╤В
        if callback.startswith("llmsoft:"):
            parts = callback.split(":", 2)
            soft = parts[2].strip() if len(parts) > 2 else ""
            if soft:
                text = soft
                callback = ""
                lower = text.lower()

    # ╨Э╨░╨╢╨░╤В╨╕╨╡ ┬л╨Э╨░╤З╨░╤В╤М┬╗ ╨▓ MAX ╨┐╤А╨╕╤Е╨╛╨┤╨╕╤В ╨║╨░╨║ bot_started тАФ ╤А╨░╨╜╤М╤И╨╡ ╨┐╨░╨┤╨░╨╗╨╛ ╨▓ ╤Б╤Г╤Е╨╛╨╣ fallback.
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

    if lower in {CALL_OPERATOR_LABEL.lower(), "╨┐╨╛╨╖╨▓╨░╤В╤М ╤Б╨┐╨╡╤Ж╨╕╨░╨╗╨╕╤Б╤В╨░", "╨╛╨┐╨╡╤А╨░╤В╨╛╤А"}:
        return _handle_operator(bot, user_id=user_id, chat_id=chat_id, store=store)

    if login_hit:
        return _send_confirm_web_login(
            bot,
            user_id=user_id,
            chat_id=chat_id,
            callback_payload=callback,
        )

    # ╨Ъ╨╛╨┤ ╤Б ╤Н╨║╤А╨░╨╜╨░ ╨║╨╛╨╝╨┐╤М╤О╤В╨╡╤А╨░ (6 ╤Ж╨╕╤Д╤А), ╨┤╨╛╨┐╤Г╤Б╨║╨░╨╡╨╝ ╨║╨╛╤А╨╛╤В╨║╨╕╨╡ ╤Д╤А╨░╨╖╤Л ╨▓╨╛╨║╤А╤Г╨│
    digits_only = "".join(ch for ch in text if ch.isdigit())
    compact = "".join(ch for ch in text if not ch.isspace())
    if len(digits_only) == 6 and len(compact) <= 24:
        return _handle_pair_code(bot, user_id=user_id, chat_id=chat_id, code=digits_only)

    intake = get_intake_store().get_active(user_id)
    record = store.find_by_max_user(user_id)

    # ╨Х╤Б╨╗╨╕ ╤Г╨╢╨╡ ╨╢╨┤╤С╨╝ ╨║╨╜╨╛╨┐╨║╤Г ╨┐╨╛╨┤╤В╨▓╨╡╤А╨╢╨┤╨╡╨╜╨╕╤П тАФ ╨╜╨╡ ╤В╨╡╤А╤П╨╡╨╝ ╨┐╨╛╨╗╤М╨╖╨╛╨▓╨░╤В╨╡╨╗╤П
    resumed = _resume_pending_confirm_if_any(bot, user_id=user_id, chat_id=chat_id)
    if resumed is not None and not lower.startswith("/"):
        return resumed

    if lower.startswith("/help") or lower in {"╨┐╨╛╨╝╨╛╤Й╤М", "╨║╨░╨╜╨░╨╗"}:
        pending = latest_for_max(user_id)
        if pending is not None and pending.status == "pending_confirm":
            return _complete_pc_login(
                bot,
                user_id=user_id,
                chat_id=chat_id,
                ticket_id=pending.ticket_id,
            )
        reply = (
            "╨Ъ╨╛╨╝╨░╨╜╨┤╤Л: /start тАФ ╨┤╨╕╨░╨│╨╜╨╛╤Б╤В╨╕╨║╨░, /cabinet тАФ ╨║╨░╨▒╨╕╨╜╨╡╤В, "
            "/documents тАФ ╨║╨░╨║╨╕╨╡ ╨┤╨╛╨║╤Г╨╝╨╡╨╜╤В╤Л ╨╜╤Г╨╢╨╜╤Л, /status тАФ ╤Б╤В╨░╤В╤Г╤Б ╨┤╨╡╨╗╨░, "
            f"/login тАФ ╨▓╤Е╨╛╨┤ ╤Б ╨║╨╛╨╝╨┐╤М╤О╤В╨╡╤А╨░. ╨Т╤Б╨╡╨│╨┤╨░ ╨╝╨╛╨╢╨╜╨╛ ╨┐╨╛╨╖╨▓╨░╤В╤М ╤Б╨┐╨╡╤Ж╨╕╨░╨╗╨╕╤Б╤В╨░. {POSITION_SHORT}"
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
            "╨Ю╤В╨║╤А╨╛╨╣╤В╨╡ ╨╗╨╕╤З╨╜╤Л╨╣ ╨║╨░╨▒╨╕╨╜╨╡╤В ╨┤╨╗╤П ╨┤╨╛╨║╤Г╨╝╨╡╨╜╤В╨╛╨▓. "
            "╨Т ╨╗╨╕╤З╨╜╨╛╨╝ ╨║╨░╨▒╨╕╨╜╨╡╤В╨╡ ╨┤╨╛╨║╤Г╨╝╨╡╨╜╤В╤Л ╨┐╨╡╤А╨╡╨┤╨░╤О╤В╤Б╤П ╨╖╨░╤Й╨╕╤Й╤С╨╜╨╜╨╛. ╨н╤В╨╛ ╨╖╨░╨╣╨╝╤С╤В 2тАУ3 ╨╝╨╕╨╜╤Г╤В╤Л. "
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
        or lower in {"╨┤╨╛╨║╤Г╨╝╨╡╨╜╤В╤Л", "╤З╤В╨╛ ╨┐╤А╨╕╤Б╨╗╨░╤В╤М"}
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
        # ╨г╨╢╨╡ ╨▒╤Л╨╗ /start, ╨╜╨╛ ╨┤╨╡╨╗╨╛ ╨╡╤Й╤С ╨╜╨╡ ╤Б╨╛╨╖╨┤╨░╨╜╨╛ тАФ ╨╜╨╡ ╨│╨╛╨╜╤П╨╡╨╝ ╨┐╨╛╨╗╨╜╤Л╨╣ welcome ╤Б╨╜╨╛╨▓╨░.
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
            f"╨Ф╨╛╨║╤Г╨╝╨╡╨╜╤В╨╛╨▓: {len(record.ctx.document_paths)}. "
            f"╨Ф╨░╨╗╤М╤И╨╡: /documents ╨╕╨╗╨╕ /cabinet. {POSITION_SHORT}"
        )
        _reply(bot, user_id=user_id, chat_id=chat_id, text=reply)
        return MaxHandleResult(ok=True, action="status", case_id=record.case_id, reply=reply)

    if lower.startswith("/run"):
        if not record.ctx.document_paths and not record.ctx.ocr_texts:
            reply = (
                "╨б╨╜╨░╤З╨░╨╗╨░ ╨╖╨░╨│╤А╤Г╨╖╨╕╤В╨╡ ╨┤╨╛╨║╤Г╨╝╨╡╨╜╤В ╨▓ ╨╖╨░╤Й╨╕╤Й╤С╨╜╨╜╨╛╨╝ ╨║╨░╨▒╨╕╨╜╨╡╤В╨╡."
                if get_settings().app_env.strip().lower() == "production"
                else "╨б╨╜╨░╤З╨░╨╗╨░ ╨┐╤А╨╕╤И╨╗╨╕╤В╨╡ ╨┤╨╛╨║╤Г╨╝╨╡╨╜╤В."
            )
            _reply(bot, user_id=user_id, chat_id=chat_id, text=reply)
            return MaxHandleResult(
                ok=False,
                action="run_blocked",
                case_id=record.case_id,
                reply=reply,
            )
        updated = store.run_until(record.case_id, stop_at=CaseStatus.HUMAN_REVIEW)
        draft_note = " ╨Ю╤В╨║╤А╨╛╨╣╤В╨╡ /draft." if updated.ctx.draft else ""
        reply = f"╨У╨╛╤В╨╛╨▓╨╛: {status_label_ru(updated.ctx.status)}.{draft_note}"
        _reply(bot, user_id=user_id, chat_id=chat_id, text=reply)
        return MaxHandleResult(ok=True, action="run", case_id=record.case_id, reply=reply)

    file_name = update.get("file_name")
    file_bytes = update.get("file_bytes")
    downloads = extract_downloadable_files(update)
    is_production = get_settings().app_env.strip().lower() == "production"
    max_files = _collect_max_files(update)
    receipt_handled = _try_max_payment_receipt(
        bot, user_id=user_id, chat_id=chat_id, files=max_files
    )
    if receipt_handled is not None:
        return receipt_handled
    if is_production and (isinstance(file_bytes, (bytes, bytearray)) or bool(downloads)):
        case_id = record.case_id
        attempt_names: list[str] = []
        if isinstance(file_name, str):
            attempt_names.append(file_name)
        attempt_names.extend(name for name, _url in downloads)
        label = attempt_names[0] if attempt_names else "╤Д╨░╨╣╨╗"
        _append_client_case_message(
            case_id=case_id or _case_id_for_max_user(user_id),
            max_user_id=user_id,
            text=f"[╨Ф╨╛╨║╤Г╨╝╨╡╨╜╤В] ╨┐╨╛╨┐╤Л╤В╨║╨░ ╨╛╤В╨┐╤А╨░╨▓╨╕╤В╤М ╨▓ ╤З╨░╤В: {label}",
        )
        max_url, web_url = cabinet_urls_for_case(case_id)
        _reply(
            bot,
            user_id=user_id,
            chat_id=chat_id,
            text=UPLOAD_BLOCKED_TEXT,
            attachments=upload_blocked_keyboard(cabinet_max_url=max_url, cabinet_web_url=web_url),
            case_id=case_id,
        )
        return MaxHandleResult(
            ok=False,
            action="upload_blocked",
            case_id=case_id,
            reply=UPLOAD_BLOCKED_TEXT,
        )
    if isinstance(file_name, str) and isinstance(file_bytes, (bytes, bytearray)):
        fresh = _ingest_bytes(store, record, file_name, bytes(file_bytes))
        reply = f"╨д╨░╨╣╨╗ ╨┐╤А╨╕╨╜╤П╤В ({len(fresh.ctx.document_paths)}). ╨Я╤А╨╕╤И╨╗╨╕╤В╨╡ ╨╡╤Й╤С ╨╕╨╗╨╕ /run."
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
            reply = f"╨д╨░╨╣╨╗╤Л ╨┐╤А╨╕╨╜╤П╤В╤Л ({len(fresh.ctx.document_paths)}). ╨Я╤А╨╕╤И╨╗╨╕╤В╨╡ ╨╡╤Й╤С ╨╕╨╗╨╕ /run."
            _reply(bot, user_id=user_id, chat_id=chat_id, text=reply)
            return MaxHandleResult(
                ok=True, action="upload_url", case_id=record.case_id, reply=reply
            )

    # ╨б╨▓╨╛╨▒╨╛╨┤╨╜╤Л╨╣ ╤В╨╡╨║╤Б╤В: DeepSeek (Yandex AI Studio) + ╨║╨╜╨╛╨┐╨║╨╕ ╤И╨░╨│╨░ / fallback nudge (╨в╨Ч-26).
    if text:
        if intake is None:
            get_intake_store().upsert_started(user_id)
            intake = get_intake_store().get_active(user_id)
        case_for_log = (
            (intake.case_id if intake else None)
            or (record.case_id if record else None)
            or _case_id_for_max_user(user_id)
        )
        _append_client_case_message(
            case_id=case_for_log,
            max_user_id=user_id,
            text=text,
        )
        from sfrfr.integrations.max.llm_chat import reply_to_free_text

        reply, attachments, action = reply_to_free_text(user_text=text, intake=intake)
        _reply(
            bot,
            user_id=user_id,
            chat_id=chat_id,
            text=reply,
            attachments=attachments,
            case_id=case_for_log,
        )
        return MaxHandleResult(
            ok=True,
            action=action,
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
