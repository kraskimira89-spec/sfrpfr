"""Обработка апдейтов MAX → кейс SFRFR."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sfrfr.core.case_store import get_case_store
from sfrfr.core.config import get_settings
from sfrfr.integrations.max.attachments import download_file, extract_downloadable_files
from sfrfr.integrations.max.client import (
    MaxBotClient,
    inline_callback_keyboard,
)
from sfrfr.models.case_status import CaseStatus, status_label_ru
from sfrfr.security.login_otp import (
    CONFIRM_WEB_LOGIN_CALLBACK,
    CONFIRM_WEB_LOGIN_LABEL,
    confirm_web_login_message,
)
from sfrfr.security.login_pending import (
    approve,
    bind_max_by_code,
    callback_payload_for,
    get_pending,
    latest_for_max,
    manager_callback_payload_for,
    mark_manager_notified,
    mark_pending_manager,
    parse_confirm_callback,
    parse_manager_callback,
)
from sfrfr.storage.local import save_upload


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
        CONFIRM_WEB_LOGIN_CALLBACK,
        "confirm_web_login",
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
    return None


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


def _reply(
    bot: MaxBotClient,
    *,
    user_id: str | None,
    chat_id: int | str | None,
    text: str,
    attachments: list[dict[str, Any]] | None = None,
) -> None:
    try:
        bot.send_message(
            text=text,
            user_id=user_id,
            chat_id=chat_id,
            attachments=attachments,
        )
    except Exception:
        pass


def _login_menu_keyboard() -> list[dict[str, Any]]:
    # Без ticket — подтвердит последнюю сессию с ПК для этого max_user_id
    return inline_callback_keyboard(CONFIRM_WEB_LOGIN_LABEL, CONFIRM_WEB_LOGIN_CALLBACK)


def _channel_choice_text() -> str:
    """Следующий шаг входа — без длинной инструкции."""
    return "\n\nПришлите код с экрана компьютера."


def _ensure_supabase_max_client(max_user_id: str) -> None:
    """Неблокирующая регистрация клиента MAX в Supabase (единый профиль ТЗ-09)."""
    try:
        from sfrfr.db.client_channels import ClientChannelRepository

        ClientChannelRepository().ensure_for_max_user(max_user_id)
    except Exception:
        pass


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
    """Отправить руководителям кнопку одобрения. Вернуть число успешных отправок."""
    from sfrfr.db.staff_roles import list_manager_max_user_ids
    from sfrfr.security.login_otp import APPROVE_STAFF_LOGIN_LABEL

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
    text = f"Вход: {email}\nНажмите кнопку."
    attachments = inline_callback_keyboard(
        APPROVE_STAFF_LOGIN_LABEL,
        manager_callback_payload_for(pending.ticket_id),
    )
    sent = 0
    targets = manager_ids or [None] * max(1, len(chat_ids))
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
        except Exception:
            # fallback: только chat_id
            if cid and mid:
                try:
                    bot.send_message(text=text, chat_id=cid, attachments=attachments)
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
        reply = "Пришлите код с экрана компьютера."
        _reply(bot, user_id=user_id, chat_id=chat_id, text=reply)
        return MaxHandleResult(ok=False, action="login_no_pending", reply=reply)

    if pending.status == "pending_pair" or not pending.max_user_id:
        # ещё не ввели код — привяжем текущего пользователя и попросим подтвердить ещё раз
        _ensure_supabase_max_client(user_id)
        row = _client_row_by_max(user_id)
        if not row:
            reply = "Напишите /start."
            _reply(bot, user_id=user_id, chat_id=chat_id, text=reply)
            return MaxHandleResult(ok=False, action="login_need_start", reply=reply)
        contact = _auth_email_for_row(row, user_id)
        pending = bind_max_by_code(
            pair_code=pending.pair_code,
            max_user_id=user_id,
            contact=contact,
        ) or pending
        if pending.status != "pending_confirm":
            _send_confirm_button(bot, user_id=user_id, chat_id=chat_id, ticket_id=pending.ticket_id)
            reply = "Нажмите кнопку."
            return MaxHandleResult(ok=True, action="login_need_confirm", reply=reply)

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
        reply = "Ошибка входа. Попробуйте позже."
        _reply(bot, user_id=user_id, chat_id=chat_id, text=reply)
        return MaxHandleResult(ok=False, action="login_token_failed", reply=reply)
    email, token_hash = tokens
    approved = approve(ticket_id=pending.ticket_id, token_hash=token_hash, email=email)
    if not approved:
        reply = "Сессия устарела. Начните вход снова на компьютере."
        _reply(bot, user_id=user_id, chat_id=chat_id, text=reply)
        return MaxHandleResult(ok=False, action="login_expired", reply=reply)

    reply = "Готово. Смотрите компьютер."
    _reply(bot, user_id=user_id, chat_id=chat_id, text=reply)
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

    reply = "Готово."
    _reply(bot, user_id=user_id, chat_id=chat_id, text=reply)
    # уведомить сотрудника в MAX, если известен
    if pending.max_user_id and str(pending.max_user_id) != str(user_id):
        try:
            bot.send_message(
                text="Готово. Смотрите компьютер.",
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
    text = confirm_web_login_message()
    attachments = inline_callback_keyboard(
        CONFIRM_WEB_LOGIN_LABEL,
        callback_payload_for(ticket_id),
    )
    _reply(bot, user_id=user_id, chat_id=chat_id, text=text, attachments=attachments)


def _handle_pair_code(
    bot: MaxBotClient,
    *,
    user_id: str,
    chat_id: int | str | None,
    code: str,
) -> MaxHandleResult:
    _ensure_supabase_max_client(user_id)
    row = _client_row_by_max(user_id)
    if not row:
        reply = "Напишите /start."
        _reply(bot, user_id=user_id, chat_id=chat_id, text=reply)
        return MaxHandleResult(ok=False, action="pair_need_start", reply=reply)
    contact = _auth_email_for_row(row, user_id)
    pending = bind_max_by_code(pair_code=code, max_user_id=user_id, contact=contact)
    if not pending:
        reply = "Код не найден. Начните вход снова на компьютере."
        _reply(bot, user_id=user_id, chat_id=chat_id, text=reply)
        return MaxHandleResult(ok=False, action="pair_invalid", reply=reply)
    _send_confirm_button(bot, user_id=user_id, chat_id=chat_id, ticket_id=pending.ticket_id)
    reply = "Нажмите кнопку."
    return MaxHandleResult(ok=True, action="pair_ok", reply=reply)


def _send_confirm_web_login(
    bot: MaxBotClient,
    *,
    user_id: str,
    chat_id: int | str | None,
    callback_payload: str = "",
) -> MaxHandleResult:
    """Кнопка/команда подтверждения: завершает вход на ПК, не открывает ссылку на телефоне."""
    ticket_from_cb = parse_confirm_callback(callback_payload)
    if ticket_from_cb is None and callback_payload:
        # не наш callback
        ticket_from_cb = None
    ticket_id = ticket_from_cb if ticket_from_cb else None
    if ticket_from_cb == "":
        ticket_id = None
    return _complete_pc_login(bot, user_id=user_id, chat_id=chat_id, ticket_id=ticket_id)


def _docs_request_text(*, has_docs: bool) -> str:
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
    Сценарий MVP:
    /start — создать/продолжить кейс + кнопка входа в веб-кабинет
    «Подтвердить вход в веб кабинет» — одноразовая ссылка
    /status, /run, /draft, /docs, /help
    вложения — скачать по url или file_bytes
    """
    bot = bot or MaxBotClient()
    text = _text(update).strip()
    callback = _callback_payload(update)
    user_id = _user_id(update)
    chat_id = _chat_id(update)
    lower = text.lower()
    confirm_cb = parse_confirm_callback(callback)
    manager_ticket = parse_manager_callback(callback)
    login_hit = (
        confirm_cb is not None
        or lower in _LOGIN_TRIGGERS
        or lower.startswith("/login")
        or CONFIRM_WEB_LOGIN_LABEL.lower() in lower
    )

    if not user_id:
        return MaxHandleResult(ok=False, action="ignore", detail="no user_id")

    store = get_case_store()

    if manager_ticket:
        return _approve_staff_by_manager(
            bot,
            user_id=user_id,
            chat_id=chat_id,
            ticket_id=manager_ticket,
        )

    if login_hit:
        return _send_confirm_web_login(
            bot,
            user_id=user_id,
            chat_id=chat_id,
            callback_payload=callback,
        )

    # Код с экрана компьютера (6 цифр)
    digits_only = "".join(ch for ch in text if ch.isdigit())
    if len(digits_only) == 6 and len(text.replace(" ", "")) <= 8:
        return _handle_pair_code(bot, user_id=user_id, chat_id=chat_id, code=digits_only)

    if lower.startswith("/start") or lower in {"старт", "начать"}:
        _ensure_supabase_max_client(user_id)
        existing = store.find_by_max_user(user_id)
        if existing:
            reply = (
                f"Кейс {existing.case_id}: {status_label_ru(existing.ctx.status)}."
                + _channel_choice_text()
            )
            _reply(bot, user_id=user_id, chat_id=chat_id, text=reply)
            return MaxHandleResult(ok=True, action="resume", case_id=existing.case_id, reply=reply)

        record = store.create(
            client_name=f"MAX user {user_id}",
            snils_masked="***-***-*** **",
            consent_given=True,
        )
        store.bind_max(
            record.case_id,
            max_user_id=user_id,
            max_chat_id=str(chat_id) if chat_id is not None else None,
        )
        reply = "Пришлите код с экрана компьютера."
        _reply(bot, user_id=user_id, chat_id=chat_id, text=reply)
        return MaxHandleResult(ok=True, action="create", case_id=record.case_id, reply=reply)

    record = store.find_by_max_user(user_id)
    if record is None:
        reply = "Напишите /start."
        _reply(bot, user_id=user_id, chat_id=chat_id, text=reply)
        return MaxHandleResult(ok=True, action="need_start", reply=reply)

    if lower.startswith("/help") or lower in {"канал", "/cabinet", "/web"}:
        reply = "Пришлите код с экрана или документ. Команды: /docs /run /draft /status"
        _reply(
            bot,
            user_id=user_id,
            chat_id=chat_id,
            text=reply,
            attachments=_login_menu_keyboard(),
        )
        return MaxHandleResult(ok=True, action="help", case_id=record.case_id, reply=reply)

    if lower.startswith("/docs") or lower in {"документы", "что прислать"}:
        reply = _docs_request_text(has_docs=bool(record.ctx.document_paths))
        _reply(bot, user_id=user_id, chat_id=chat_id, text=reply)
        return MaxHandleResult(ok=True, action="docs_request", case_id=record.case_id, reply=reply)

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
            "Дальше: /docs или /run."
        )
        _reply(bot, user_id=user_id, chat_id=chat_id, text=reply)
        return MaxHandleResult(ok=True, action="status", case_id=record.case_id, reply=reply)

    if lower.startswith("/run"):
        if not record.ctx.document_paths and not record.ctx.ocr_texts:
            reply = "Сначала пришлите документ."
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
    if isinstance(file_name, str) and isinstance(file_bytes, (bytes, bytearray)):
        fresh = _ingest_bytes(store, record, file_name, bytes(file_bytes))
        reply = f"Файл принят ({len(fresh.ctx.document_paths)}). Пришлите ещё или /run."
        _reply(bot, user_id=user_id, chat_id=chat_id, text=reply)
        return MaxHandleResult(ok=True, action="upload", case_id=record.case_id, reply=reply)

    downloads = extract_downloadable_files(update)
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

    reply = "Пришлите код с экрана, документ или /help."
    _reply(
        bot,
        user_id=user_id,
        chat_id=chat_id,
        text=reply,
        attachments=_login_menu_keyboard(),
    )
    return MaxHandleResult(ok=True, action="ack", case_id=record.case_id, reply=reply)
